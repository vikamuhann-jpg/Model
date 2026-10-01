"""Should scoring use every tree, or stop at the early-stopping best iteration?

    python scripts/measure/tree_range.py

Training used early stopping, which chose iteration 740 -- 741 trees. Scoring
calls ``inplace_predict``, which uses all 841. Nobody decided that: it is what
the library defaults to. The gap surfaced because ``shap`` truncates at
``best_iteration`` while scoring did not, so every explanation described a model
that never produced the score (fixed 2026-09-26; see WINNING_PLAN).

The trees past the best iteration are the ones validation said had stopped
helping, so they are either mild overfitting or harmless. This measures both
arms on the test partition the package reports, at the shipped threshold, and
leaves the answer in runs/COMP1_tree_range.json.
"""
import json

import numpy as np
import pandas as pd
import xgboost as xgb

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.pipeline.score import feature_matrix, graph_features, load_package
from _paths import DATA, REPO  # noqa: E402

BENCH = DATA / "processed" / "benchmark"
CACHE = BENCH / "gfp_paper_b1"
pkg = load_package(REPO / "Project/flowguard/models/flowguard_V2_v1")

best = int(pkg.model.booster_.best_iteration)
total = int(pkg.model.booster_.num_boosted_rounds())
print(f"best_iteration {best} ({best + 1} trees) of {total} trained", flush=True)

# Only the columns the features need: the corpus is 5M rows and the host is short
# of memory. Behaviour features need the whole history rather than the scored
# rows, so the frame stays full-length while the feature matrix does not.
columns = [S.TRANSACTION_ID, S.TIMESTAMP, S.SOURCE_ACCOUNT, S.DESTINATION_ACCOUNT,
           S.AMOUNT, S.CURRENCY, S.AMOUNT_RECEIVED, S.CURRENCY_RECEIVED,
           S.PAYMENT_TYPE, S.IS_LAUNDERING, S.IS_SELF_TRANSFER]
tx = pd.read_parquet(BENCH / "HI-Small_transactions.parquet", columns=columns)
val_end = pd.Timestamp(pkg.provenance["split"]["boundaries"]["val_end"])
test_rows = tx.index[tx[S.TIMESTAMP] > val_end]
y = tx.loc[test_rows, S.IS_LAUNDERING].to_numpy().astype(int)
print(f"test partition {len(test_rows):,} rows, {int(y.sum()):,} positives", flush=True)

X = feature_matrix(
    pkg, tx, graph_features(tx, CACHE, pkg.graph["params"], rows=test_rows), rows=test_rows
)
del tx
matrix = xgb.DMatrix(X, feature_names=list(X.columns))

out = {"best_iteration": best, "trees_trained": total, "test_rows": len(X),
       "test_positives": int(y.sum()), "threshold": pkg.threshold, "arms": {}}
for label, rng in (("all_trees", (0, 0)), ("best_iteration", (0, best + 1))):
    raw = pkg.model.booster_.predict(matrix, iteration_range=rng)
    calibrated = np.asarray(pkg.model.calibrator_.predict(raw), dtype=float)
    metrics = evaluate(y, raw)
    alerts = calibrated >= pkg.threshold
    caught = int((alerts & (y == 1)).sum())
    out["arms"][label] = {
        "trees": total if rng == (0, 0) else best + 1,
        "pr_auc": metrics.pr_auc,
        "roc_auc": metrics.roc_auc,
        "best_f1": metrics.best_f1,
        "recall_at_1pct": metrics.at_budget(0.01).recall,
        "precision_at_1pct": metrics.at_budget(0.01).precision,
        "at_shipped_threshold": {
            "alerts": int(alerts.sum()),
            "recall": caught / max(1, int(y.sum())),
            "precision": caught / max(1, int(alerts.sum())),
            "f1": 2 * caught / max(1, int(alerts.sum()) + int(y.sum())),
        },
    }
    print(f"{label:>15}: PR-AUC {metrics.pr_auc:.4f}  best-F1 {metrics.best_f1:.4f}  "
          f"recall@1% {metrics.at_budget(0.01).recall:.4f}", flush=True)

a, b = out["arms"]["all_trees"], out["arms"]["best_iteration"]
out["delta_all_minus_best"] = {
    key: a[key] - b[key] for key in ("pr_auc", "best_f1", "recall_at_1pct")
}
# The published seed spread for this configuration (S4b, five seeds). A
# difference smaller than that is not one we can act on.
out["seed_spread_f1"] = 0.003
out["verdict"] = (
    "inside the seed spread -- keep all trees, and say so explicitly"
    if abs(out["delta_all_minus_best"]["best_f1"]) <= 0.003
    else "outside the seed spread -- the choice changes the model"
)
print("\ndelta (all - best):", json.dumps(out["delta_all_minus_best"], indent=2))
print(out["verdict"])

path = DATA / "runs" / "COMP1_tree_range.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"wrote {path}")
