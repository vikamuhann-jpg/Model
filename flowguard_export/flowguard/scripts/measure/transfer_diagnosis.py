"""Why does the shipped model fail on LI-Small? Patterned or untagged laundering?

    python scripts/measure/transfer_diagnosis.py [LI-Small-2M] [gfp_paper_b1_LI2M]

G1 found recall at 1% of 13.3% on the LI-Small prefix, against 78.0% on HI-Small.
That number cannot say whether the *method* fails to transfer or whether LI-Small
simply holds a different kind of laundering. Only 29% of LI-Small's positives
carry an injected-pattern annotation, against 62% of HI-Small's; the rest are
laundering transactions with no typology attached.

So this splits recall two ways. If the model still catches the patterned positives
and misses the untagged ones, the graph method works and what it misses is
laundering with no graph shape to find. If it misses both, the method itself does
not carry over. The two readings call for different next steps.
"""
import json
import sys

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import per_group_recall
from flowguard.pipeline.score import feature_matrix, graph_features, load_package
from flowguard.splits.temporal import SplitSpec, chronological_split
from _paths import DATA, REPO  # noqa: E402

variant = sys.argv[1] if len(sys.argv) > 1 else "LI-Small-2M"
cache = sys.argv[2] if len(sys.argv) > 2 else "gfp_paper_b1_LI2M"
BENCH = DATA / "processed" / "benchmark"
BUDGET = 0.01

pkg = load_package(REPO / "Project/flowguard/models/flowguard_V2_v1")
tx = pd.read_parquet(BENCH / f"{variant}_transactions.parquet")
_, _, test = chronological_split(tx, SplitSpec(train_frac=0.6, val_frac=0.2)).apply(tx)
rows = test.index

graph_columns = [c for c in pkg.columns if c.startswith("gfp_")]
X = feature_matrix(pkg, tx, graph_features(tx, BENCH / cache, pkg.graph["params"],
                                           rows=rows, columns=graph_columns), rows=rows)
raw = pkg.model.predict_raw(X)
y = test[S.IS_LAUNDERING].to_numpy().astype(int)
percentile = pd.Series(raw).rank(pct=True).to_numpy()
# "Caught at 1%" ranks by the RAW score. It has no ties, so the answer is the
# same on every run, and it is the order scores.csv ranks alerts in (score, then
# raw_score; isotonic calibration is monotone, so that is the raw order). Ranking
# by the calibrated score instead is not reproducible: calibration ties heavily,
# and which tied rows fall inside the top 1% changed between two runs of the same
# model (1,402 vs 1,400 caught). The shipped record's headline uses calibrated
# scores, so it differs from these counts by a handful of cases -- stated in
# docs/CLAIMS_REGISTER.md rather than hidden.
flagged = percentile > 1 - BUDGET

typology = test[S.PATTERN_TYPE].astype("object").where(test[S.PATTERN_TYPE].notna(), "")
patterned = (typology != "").to_numpy()
rail = test[S.PAYMENT_TYPE].astype(str).to_numpy()


def group(mask):
    """Recall at the budget, and where the positives in ``mask`` actually rank."""
    positive = mask & (y == 1)
    n = int(positive.sum())
    if not n:
        return {"positives": 0}
    return {
        "positives": n,
        "caught": int((positive & flagged).sum()),
        "recall": float((positive & flagged).sum() / n),
        # A median near 100 means "almost caught"; near 50 means "invisible".
        "median_percentile": round(float(np.median(percentile[positive])) * 100, 1),
    }


out = {
    "variant": variant, "budget": BUDGET, "test_rows": len(y), "positives": int(y.sum()),
    "all": group(np.ones_like(y, dtype=bool)),
    "patterned": group(patterned),
    "untagged": group(~patterned),
    "patterned_on_ach": group(patterned & (rail == "ACH")),
    "untagged_on_ach": group(~patterned & (rail == "ACH")),
    "untagged_off_ach": group(~patterned & (rail != "ACH")),
    "by_typology": per_group_recall(y, raw, typology.to_numpy(), budget=BUDGET),
    "by_rail": {r: group(rail == r) for r in sorted(set(rail[y == 1]))},
}

for key in ("all", "patterned", "untagged", "patterned_on_ach", "untagged_on_ach",
            "untagged_off_ach"):
    g = out[key]
    if g["positives"]:
        print(f"{key:>18}: {g['caught']:>3}/{g['positives']:<3} caught  "
              f"recall {g['recall']:.1%}  median rank {g['median_percentile']}th pct")
print("\nby typology:", {k: f"{v['caught']}/{v['positives']}"
                         for k, v in out["by_typology"].items()})

path = DATA / "runs" / f"G1_diagnosis_{variant}.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"wrote {path}")
