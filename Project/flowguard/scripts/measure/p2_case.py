"""P2 deliverable: one real exported case, end to end.

Real corpus, real trace, real SHAP from the shipped E2 model, real threshold
provenance. The fixtures prove the contracts; this proves the pieces compose.
"""
import json, pickle
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb

from flowguard.data import schema as S
from flowguard.evaluation.interpretation import local_contributions
from flowguard.evidence import EvidenceBundle, build_bundle
from flowguard.features.gfp import read_varying_chunks
from flowguard.features.transaction import TransactionFeatures
from flowguard.graph.trace import TraceIndex, TraceLimits
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

P = (DATA / "processed")
ROOT = (REPO / "Project/flowguard")
PKG, OUT = ROOT / "models/flowguard_E2_v1", ROOT / "reports/cases"

prov = json.loads((PKG / "PROVENANCE.json").read_text())
thr = json.loads((PKG / "thresholds.json").read_text())
metrics = json.loads((PKG / "metrics.json").read_text())
fschema = json.loads((PKG / "feature_schema.json").read_text())

budget = thr["thresholds"]["0.01"]          # the 1% alert budget
print(f"threshold {budget['value']:.8f} from {budget['source']} "
      f"(precision {budget['selection_precision']:.4f})", flush=True)

booster = xgb.Booster(); booster.load_model(str(PKG / "model.json"))
calibrator = pickle.loads((PKG / "calibrator.pkl").read_bytes())

df = pd.read_parquet(P / "HI-Small_transactions.parquet")
val_end = pd.Timestamp(prov["split"]["boundaries"]["val_end"])
mask = df[S.TIMESTAMP] > val_end
print(f"corpus {len(df):,} rows; test period {int(mask.sum()):,} after {val_end}",
      flush=True)

gfp = read_varying_chunks(P / "HI-Small_gfp_w2_parts").reindex(df.index)
# The SHIPPED package is E2 -- the 168-feature model that still carries the
# payment_type artifact (ADR-007). The artifact-free A4 arm was measured but
# never packaged, so a case built from what actually ships inherits the
# ACH dependence. That is precisely why the bundle carries a coverage warning.
extractor = TransactionFeatures(include_payment_type=True).fit(
    S.feature_view(df[~mask]))
test_df = df[mask].reset_index(drop=True)
X = pd.concat(
    [extractor.run(S.feature_view(test_df)),
     gfp[mask.to_numpy()].reset_index(drop=True)], axis=1)
X = X[fschema["columns"]]
print(f"features {X.shape}", flush=True)

raw = booster.predict(xgb.DMatrix(X, feature_names=fschema["columns"]))
scores = calibrator.predict(raw) if hasattr(calibrator, "predict") else raw
test_df = test_df.assign(_score=np.asarray(scores))

# Highest-scoring TRUE positive, so the case is a real detection rather than a
# cherry-picked alert.
row = test_df[test_df[S.IS_LAUNDERING] == 1].nlargest(1, "_score").iloc[0]
print(f"\nsubject {row[S.SOURCE_ACCOUNT]} score {row['_score']:.6f} "
      f"rail {row[S.PAYMENT_TYPE]} amount {row[S.AMOUNT]:,.2f}", flush=True)

result = TraceIndex(test_df).trace(
    row[S.SOURCE_ACCOUNT], horizon=3, at=row[S.TIMESTAMP],
    limits=TraceLimits(degree_cap=16, edge_budget=200))
print(result.summary(), flush=True)

bundle = build_bundle(
    result,
    score=float(row["_score"]),
    threshold=float(budget["value"]),
    threshold_source=f"{budget['source']} @ {budget['budget']:.1%} alert budget",
    model={"model_id": "flowguard_E2_v1",
           "git_commit": prov["git_commit"],
           "device_used": prov["device_used"],
           "test_pr_auc": metrics["test"]["pr_auc"],
           "feature_schema_hash": fschema["schema_hash"],
           "split_val_end": prov["split"]["boundaries"]["val_end"]},
    contributions=local_contributions(booster, X.loc[result.edges.index]),
    transactions=test_df,
)
print("\n" + bundle.summary(), flush=True)

path = bundle.write(OUT / f"{bundle.case_id}.json")
assert EvidenceBundle.read(path).to_json() == bundle.to_json(), "round trip differs"
EvidenceBundle.read(path).check_internal_consistency()
print(f"\nwrote {path.name} ({path.stat().st_size:,} bytes); round-trip identical",
      flush=True)
print(f"reasons {len(bundle.reasons)}, opaque "
      f"{sum(r.opaque for r in bundle.reasons)}/{len(bundle.reasons)}", flush=True)
print(f"rails in case: {bundle.coverage['rails']}", flush=True)
print("P2 CASE DONE", flush=True)
