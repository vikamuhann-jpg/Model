"""P4 typology hinting and P6 unsupervised spike, measured against their gates.

Both are candidates, not commitments. P4 ships as a documented negative result
if macro-F1 does not clear a stratified-random baseline by 2 sigma; P6 is
expected to be rejected outright and is written up either way.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.features.transaction import TransactionFeatures
from gslice import covered_index, graph_slice, keep_columns
from flowguard.models.typology import TypologyHinter, expected_calibration_error
from flowguard.models.xgb import XGBModel
from flowguard.splits.temporal import BoundaryPolicy, SplitSpec, chronological_split
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

P = (DATA / "processed")
OUT = (DATA / "p4p6.json")
SEEDS = (42, 7, 123)
BUDGET = 0.01

PARTS = P / "HI-Small_gfp_w2_parts"
df = pd.read_parquet(P / "HI-Small_transactions.parquet")
KEEP, TOTAL = keep_columns(PARTS)
df = df.loc[df.index.intersection(covered_index(PARTS))].sort_index()
print(f"{len(df):,} rows | {len(KEEP)} of {TOTAL} graph features vary", flush=True)

split = chronological_split(df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT))
tr, va, te = split.apply(df)


def y(d):
    return d[S.IS_LAUNDERING].to_numpy().astype(int)


ex = TransactionFeatures(include_payment_type=False).fit(S.feature_view(tr))


def build(part):
    """One split's feature frame, graph rows streamed per part file.

    Holding all three splits plus the full graph block at once is what OOM-killed
    the first attempt, so frames are built on demand and dropped by the caller.
    """
    tabular = ex.run(S.feature_view(part)).reset_index(drop=True).astype("float32")
    return pd.concat([tabular, graph_slice(PARTS, part.index, KEEP)], axis=1)


X = {n: build(d) for n, d in (("tr", tr), ("va", va), ("te", te))}
print(
    f"train {len(tr):,} val {len(va):,} test {len(te):,} | features {X['tr'].shape[1]}",
    flush=True,
)

out = {}

# ---------------------------------------------------------------- P4
print("\n=== P4 typology hinting ===", flush=True)
lab = {
    n: d["pattern_type"].reset_index(drop=True)
    for n, d in (("tr", tr), ("va", va), ("te", te))
}
for n in ("tr", "va", "te"):
    print(f"  {n}: {lab[n].notna().sum():,} annotated", flush=True)

test_seen = lab["te"].notna()
y_true = lab["te"][test_seen]
macro, eces, per_class = [], [], []
for seed in SEEDS:
    h = TypologyHinter(params={**TypologyHinter().params, "seed": seed})
    h.fit(X["tr"], lab["tr"], X["va"], lab["va"])
    proba = h.predict_proba(X["te"][test_seen.to_numpy()])
    pred = proba.idxmax(axis=1)
    macro.append(f1_score(y_true, pred, average="macro", zero_division=0))
    conf = proba.max(axis=1).to_numpy()
    eces.append(expected_calibration_error(conf, pred.to_numpy() == y_true.to_numpy()))
    per_class.append(
        f1_score(y_true, pred, average=None, labels=h.classes_, zero_division=0)
    )
    print(f"  seed {seed}: macro-F1 {macro[-1]:.4f}  ECE {eces[-1]:.4f}", flush=True)

# Stratified-random baseline on the same test labels, same seeds.
rand = []
prior = lab["tr"].dropna().value_counts(normalize=True)
for seed in SEEDS:
    rng = np.random.default_rng(seed)
    guess = rng.choice(prior.index.to_numpy(), size=len(y_true), p=prior.to_numpy())
    rand.append(f1_score(y_true, guess, average="macro", zero_division=0))

sd = float(np.std(macro + rand, ddof=1))
delta = float(np.mean(macro) - np.mean(rand))
p4a = bool(delta > 2 * sd)
p4b = bool(np.mean(eces) < 0.10)
print(f"\n  macro-F1 {np.mean(macro):.4f} vs random {np.mean(rand):.4f}", flush=True)
verdict_a = "PASS" if p4a else "FAIL"
verdict_b = "PASS" if p4b else "FAIL"
print(f"  delta {delta:+.4f} vs 2 sigma {2 * sd:.4f} -> P4-a {verdict_a}", flush=True)
print(f"  ECE {np.mean(eces):.4f} -> P4-b {verdict_b}", flush=True)
classes = sorted(lab["tr"].dropna().unique())
mean_pc = np.mean(per_class, axis=0)
for c, f in zip(classes, mean_pc):
    print(f"    {c:16s} F1 {f:.3f}", flush=True)

out["P4"] = {
    "macro_f1": float(np.mean(macro)),
    "macro_f1_sd": float(np.std(macro, ddof=1)),
    "random_baseline": float(np.mean(rand)),
    "delta": delta,
    "two_sigma": 2 * sd,
    "ece": float(np.mean(eces)),
    "p4a_pass": p4a,
    "p4b_pass": p4b,
    "n_test_annotated": int(test_seen.sum()),
    "per_class_f1": {c: float(f) for c, f in zip(classes, mean_pc)},
}

# ---------------------------------------------------------------- P6
print("\n=== P6 unsupervised spike ===", flush=True)
sup = []
for seed in SEEDS:
    m = XGBModel(params={**XGBModel().params, "random_state": seed})
    m.fit(X["tr"], y(tr), X["va"], y(va))
    m.calibrate(X["va"], y(va))
    sup.append(m.predict(X["te"]))
sup_pr = [evaluate(y(te), s, budgets=(BUDGET,)).pr_auc for s in sup]
print(f"  supervised PR-AUC {np.mean(sup_pr):.4f}", flush=True)

iso_scores = []
for seed in SEEDS:
    iso = IsolationForest(
        n_estimators=100, max_samples=100_000, random_state=seed, n_jobs=-1
    )
    iso.fit(X["tr"].sample(200_000, random_state=seed))
    iso_scores.append(-iso.score_samples(X["te"]))
iso_pr = [evaluate(y(te), s, budgets=(BUDGET,)).pr_auc for s in iso_scores]
print(f"  isolation forest PR-AUC {np.mean(iso_pr):.4f}", flush=True)

# P6-a: unique catches at the 1% budget.
k = int(BUDGET * len(te))
yt = y(te)
uniques = []
for s_sup, s_iso in zip(sup, iso_scores):
    sup_hit = set(np.argsort(-s_sup)[:k]) & set(np.flatnonzero(yt))
    iso_hit = set(np.argsort(-s_iso)[:k]) & set(np.flatnonzero(yt))
    uniques.append(len(iso_hit - sup_hit))
print(
    f"  positives caught by IF and missed by supervised: {uniques} "
    f"(mean {np.mean(uniques):.1f})",
    flush=True,
)


def rank(v):
    return np.argsort(np.argsort(v)) / max(len(v) - 1, 1)


ens_pr = [
    evaluate(yt, (rank(a) + rank(b)) / 2, budgets=(BUDGET,)).pr_auc
    for a, b in zip(sup, iso_scores)
]
sd6 = float(np.std(sup_pr + ens_pr, ddof=1))
d6 = float(np.mean(ens_pr) - np.mean(sup_pr))
p6a = bool(np.mean(uniques) >= 5)
p6b = bool(d6 > 2 * sd6)
print(
    f"  ensemble PR-AUC {np.mean(ens_pr):.4f}  delta {d6:+.4f} vs 2 sigma {2 * sd6:.4f}",
    flush=True,
)
v6a = "PASS" if p6a else "FAIL"
v6b = "PASS" if p6b else "FAIL"
print(f"  P6-a {v6a} | P6-b {v6b}", flush=True)

out["P6"] = {
    "supervised_pr_auc": float(np.mean(sup_pr)),
    "isolation_forest_pr_auc": float(np.mean(iso_pr)),
    "ensemble_pr_auc": float(np.mean(ens_pr)),
    "delta": d6,
    "two_sigma": 2 * sd6,
    "unique_catches": [int(u) for u in uniques],
    "mean_unique_catches": float(np.mean(uniques)),
    "p6a_pass": p6a,
    "p6b_pass": p6b,
}

OUT.write_text(json.dumps(out, indent=2))
print(f"\nwrote {OUT}\nP4P6 DONE", flush=True)
