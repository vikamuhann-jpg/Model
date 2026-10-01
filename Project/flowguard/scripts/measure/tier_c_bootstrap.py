"""How much of the Tier C delta survives having only 20 positive accounts?

The pre-registered 2-sigma rule compares arms against the SEED spread. That is
the right test for "would a different initialisation change this" and the wrong
one for "would a different sample of accounts change this". With 20 positives in
the scored set, sampling uncertainty dominates and the seed bar says nothing
about it.

So: refit both arms once, keep the per-account scores, and bootstrap over the
scored accounts to get an interval on the delta that reflects the sample size.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.account_level import aggregate_to_accounts
from sklearn.metrics import average_precision_score
from flowguard.features.gfp import read_varying_chunks
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.xgb import XGBModel
from flowguard.pipeline.run_transfer import partition_accounts
from flowguard.splits.temporal import BoundaryPolicy, SplitSpec, chronological_split
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

P = (DATA / "processed")
LO, HI = (DATA / "eth_slice.txt").read_text().split("|")
N_BOOT = 2000
RNG = np.random.default_rng(0)

df = pd.read_parquet(P / "ETH_transactions.parquet")
df = df[
    (df[S.TIMESTAMP] >= pd.Timestamp(LO, tz="UTC"))
    & (df[S.TIMESTAMP] < pd.Timestamp(HI, tz="UTC"))
].reset_index(drop=True)

# ETH_gfp_parts (the default until 2026-09-22) was extracted with the
# double-insertion defect (ADR-015); ETH_gfp_parts_v2 is the corrected extraction.
PARTS = sys.argv[1] if len(sys.argv) > 1 else "ETH_gfp_parts_v2"
gfp = read_varying_chunks(P / PARTS)
df = df.loc[df.index.intersection(gfp.index)].sort_index()
gfp = gfp.loc[df.index]
gfp = gfp[[c for c in gfp.columns if gfp[c].std() > 0]]
print(f"prefix {len(df):,} rows, {gfp.shape[1]} graph features", flush=True)

labels = pd.read_parquet(P / "ETH_labels.parquet")
accounts = set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT])
labels = partition_accounts(
    labels[labels.account_id.isin(accounts)].reset_index(drop=True)
)
train_illicit = set(
    labels.loc[(labels.is_illicit == 1) & (labels.side == "train"), "account_id"]
)
eval_labels = labels.loc[labels.side == "eval", ["account_id", "is_illicit"]]

split = chronological_split(df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT))
train_df, val_df, test_df = split.apply(df)


def proxy(part):
    hit = part[S.SOURCE_ACCOUNT].isin(train_illicit) | part[
        S.DESTINATION_ACCOUNT
    ].isin(train_illicit)
    return hit.to_numpy().astype(int)


scored = {}
for name, use_gfp in (("T1", False), ("T2", True)):
    ex = TransactionFeatures(include_payment_type=False).fit(S.feature_view(train_df))

    def build(part, _g=use_gfp):
        tab = ex.run(S.feature_view(part))
        return pd.concat([tab, gfp.loc[part.index]], axis=1) if _g else tab

    model = XGBModel(params={**XGBModel().params, "random_state": 42})
    model.fit(build(train_df), proxy(train_df), build(val_df), proxy(val_df))
    model.calibrate(build(val_df), proxy(val_df))
    acc = aggregate_to_accounts(test_df, model.predict(build(test_df))).to_frame()
    merged = acc.merge(eval_labels, on="account_id", how="inner")
    scored[name] = merged
    print(
        f"{name}: {len(merged):,} scored accounts, "
        f"{int(merged.is_illicit.sum())} positive",
        flush=True,
    )

# Both arms score the same account set; align them so each bootstrap resample
# draws the SAME accounts for both, making the delta paired rather than two
# independent noisy estimates.
a = scored["T1"].set_index("account_id").sort_index()
b = scored["T2"].set_index("account_id").sort_index()
assert a.index.equals(b.index), "arms scored different accounts"
y = a.is_illicit.to_numpy().astype(int)
s1, s2 = a.score.to_numpy(), b.score.to_numpy()
n = len(y)
print(
    f"\npaired bootstrap over {n:,} accounts, {y.sum()} positive, {N_BOOT} resamples",
    flush=True,
)

point1 = average_precision_score(y, s1)
point2 = average_precision_score(y, s2)

d1, d2, dd = [], [], []
for _ in range(N_BOOT):
    idx = RNG.integers(0, n, n)
    yy = y[idx]
    if yy.sum() < 2:  # a resample with no positives has no PR-AUC
        continue
    m1 = average_precision_score(yy, s1[idx])
    m2 = average_precision_score(yy, s2[idx])
    d1.append(m1)
    d2.append(m2)
    dd.append(m2 - m1)

q = lambda v, p: float(np.percentile(v, p))
result = {
    "n_accounts_scored": int(n),
    "n_positive": int(y.sum()),
    "base_rate": float(y.mean()),
    "n_resamples_used": len(dd),
    "T1": {"point": float(point1), "ci95": [q(d1, 2.5), q(d1, 97.5)]},
    "T2": {"point": float(point2), "ci95": [q(d2, 2.5), q(d2, 97.5)]},
    "delta": {
        "point": float(point2 - point1),
        "ci95": [q(dd, 2.5), q(dd, 97.5)],
        "fraction_of_resamples_favouring_graph": float(np.mean(np.array(dd) > 0)),
    },
}
print(json.dumps(result, indent=2))
(DATA / "runs" / f"P2_eth_bootstrap_{PARTS}.json").write_text(
    json.dumps(result, indent=2)
)
print("\nBOOTSTRAP DONE", flush=True)
