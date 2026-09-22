"""Does the shipped package work, unchanged, on a corpus it never saw? (WINNING_PLAN G1)

    python scripts/measure/transfer_zero_shot.py LI-Small gfp_paper_b1_LI

Loads models/flowguard_V2_v1 exactly as scoring does, builds its feature matrix
over the whole target corpus (graph parts extracted with the package's own
graph.json settings, behaviour features over full history), and evaluates on the
target's last 20% -- the same 60/20/20 split the benchmark uses. No refit, no
recalibration: the package's own threshold is applied as shipped. A threshold
re-chosen on the target's validation 20% is reported separately, as the cost of
a one-step local calibration.
"""
import json
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.features.behaviour import behaviour_features
from flowguard.pipeline.run_benchmark import f1_at
from flowguard.pipeline.score import load_package
from flowguard.splits.temporal import SplitSpec, chronological_split
from _paths import DATA, REPO  # noqa: E402

variant, cache = sys.argv[1], sys.argv[2]
BENCH = DATA / "processed" / "benchmark"
pkg = load_package(REPO / "Project/flowguard/models/flowguard_V2_v1")

df = pd.read_parquet(BENCH / f"{variant}_transactions.parquet")
_, val, test = chronological_split(df, SplitSpec(train_frac=0.6, val_frac=0.2)).apply(df)
rows = val.index.union(test.index)

# Not read_varying_chunks: which columns vary is a property of the corpus, and
# the package needs its own columns even where LI-Small holds them constant.
# Only the scored 40% of rows is kept, part by part, to stay inside WSL memory.
parts = sorted((BENCH / cache).glob("part_*.parquet"))
graph_cols = [c for c in pkg.columns if c in pq.read_schema(parts[0]).names]
graph = pd.concat(
    [g[g.index.isin(rows)] for g in
     (pd.read_parquet(p, columns=["_row"] + graph_cols).set_index("_row") for p in parts)]
)
X = pd.concat(
    [pkg.extractor.run(S.feature_view(df.loc[rows])), graph.loc[rows],
     behaviour_features(S.feature_view(df)).loc[rows]],  # history: the whole corpus
    axis=1,
)
missing = [c for c in pkg.columns if c not in X.columns]
assert not missing, f"package features absent: {missing[:5]}"
X = X[pkg.columns].astype("float32")
del graph

out = {"package": pkg.model_id, "variant": variant, "cache": cache,
       "package_threshold": pkg.threshold, "threshold_source": pkg.threshold_source}
for name, part in (("validation", val), ("test", test)):
    y = part[S.IS_LAUNDERING].to_numpy().astype(int)
    rail = part[S.PAYMENT_TYPE].astype(str).to_numpy()
    raw = pkg.model.predict_raw(X.loc[part.index])
    cal = pkg.model.calibrator_.predict(raw)
    m = evaluate(y, raw)
    alerts, top = cal >= pkg.threshold, raw >= np.quantile(raw, 0.99)
    tp = int((alerts & (y == 1)).sum())
    out[name] = {
        "rows": len(y), "positives": int(y.sum()),
        "pr_auc": m.pr_auc, "roc_auc": m.roc_auc, "f1_oracle": m.best_f1,
        "recall_at_1pct": m.at_budget(0.01).recall,
        "precision_at_1pct": m.at_budget(0.01).precision,
        "shipped_threshold": {"alert_rate": float(alerts.mean()), "recall": tp / max(1, y.sum()),
                              "precision": tp / max(1, alerts.sum()),
                              "f1": 2 * tp / max(1, alerts.sum() + y.sum())},
        "recall_at_1pct_by_rail": {
            r: {"positives": int(((y == 1) & (rail == r)).sum()),
                "recall": float((top & (y == 1) & (rail == r)).sum() / ((y == 1) & (rail == r)).sum())}
            for r in sorted(set(rail[y == 1]))
        },
    }
    if name == "validation":
        local_threshold = m.best_f1_threshold
    else:
        out[name]["f1_local_val_threshold"] = f1_at(y, raw, local_threshold)
    print(f"{name}: PR-AUC {m.pr_auc:.4f}  recall@1% {out[name]['recall_at_1pct']:.3f}  "
          f"F1 shipped-threshold {out[name]['shipped_threshold']['f1']:.4f}  "
          f"oracle {m.best_f1:.4f}", flush=True)

path = DATA / "runs" / f"G1_zero_shot_{variant}.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"F1 at a threshold re-chosen on {variant} validation: "
      f"{out['test']['f1_local_val_threshold']:.4f}\nwrote {path}")
