"""P3: does routing only the top K% to the graph extractor meet the gate?

Recall is measured exactly, not simulated: the graph features are already cached
for both corpora, so the full-extraction arm and the cascade arm are scored by
the same models on the same rows. Only the ROUTING differs.

Tier-1 throughput is the steady-state figure already recorded for each corpus
(ADR-006 / ADR-013); re-measuring extraction is what this phase exists to avoid.

**Memory staging.** A first attempt held the graph frame, both tier feature sets
and all three splits at once and was OOM-killed at 5.6 GB. Nothing here holds the
graph frame beside a fitted arm: the cached chunks are re-read per stage, which
costs disk time and bounds peak memory. The measurement is unchanged -- only the
order it is computed in.
"""
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.features.cascade import cascade
from flowguard.features.transaction import TransactionFeatures
from gslice import covered_index, graph_slice, keep_columns
from flowguard.models.xgb import XGBModel
from flowguard.splits.temporal import BoundaryPolicy, SplitSpec, chronological_split
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

P = (DATA / "processed")
OUT = (DATA / "p3_cascade.json")
SEEDS = (42, 7, 123)
KS = (0.01, 0.02, 0.05, 0.10)
BUDGET = 0.01
TIER1_RATE = {"HI-Small": 450.0, "ETH": 139.0}

FEATURE_COLS = [
    S.TRANSACTION_ID,
    S.TIMESTAMP,
    S.SOURCE_ACCOUNT,
    S.DESTINATION_ACCOUNT,
    S.AMOUNT,
    S.CURRENCY,
    S.IS_LAUNDERING,
]


CORPORA = [
    ("HI-Small", "HI-Small_transactions.parquet", "HI-Small_gfp_w2_parts"),
    ("ETH", "ETH_transactions.parquet", "ETH_gfp_parts"),
]
# One corpus per process: each arm's peak is independent, and a crash on the
# second no longer discards the first's results.
if len(sys.argv) > 1:
    CORPORA = [c for c in CORPORA if c[0] == sys.argv[1]]
    OUT = OUT.with_name(f"p3_cascade_{sys.argv[1]}.json")

results = {}

for corpus, parquet, parts_name in CORPORA:
    print(f"\n{'=' * 60}\n{corpus}\n{'=' * 60}", flush=True)

    parts = P / parts_name
    cols = list(FEATURE_COLS)
    if corpus == "HI-Small":
        cols.append(S.PAYMENT_TYPE)
    df = pd.read_parquet(P / parquet, columns=cols)

    keep, total_cols = keep_columns(parts)
    covered = covered_index(parts)
    df = df.loc[df.index.intersection(covered)].sort_index()
    del covered
    gc.collect()
    print(f"{len(df):,} rows | {len(keep)} of {total_cols} graph features vary",
          flush=True)

    if corpus == "ETH":
        from flowguard.pipeline.run_transfer import partition_accounts

        labels = pd.read_parquet(P / "ETH_labels.parquet")
        accts = set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT])
        labels = partition_accounts(
            labels[labels.account_id.isin(accts)].reset_index(drop=True)
        )
        illicit = set(
            labels.loc[
                (labels.is_illicit == 1) & (labels.side == "train"), "account_id"
            ]
        )
        proxy = (
            (
                df[S.SOURCE_ACCOUNT].isin(illicit)
                | df[S.DESTINATION_ACCOUNT].isin(illicit)
            )
            .to_numpy()
            .astype(int)
        )
        df = df.assign(**{S.IS_LAUNDERING: proxy})
        del labels, illicit, accts
        gc.collect()

    split = chronological_split(df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT))
    tr, va, te = split.apply(df)
    idx = {"tr": tr.index, "va": va.index, "te": te.index}
    y = {
        n: d[S.IS_LAUNDERING].to_numpy().astype(int)
        for n, d in (("tr", tr), ("va", va), ("te", te))
    }
    print(
        f"train {len(tr):,} val {len(va):,} test {len(te):,} | "
        f"test positives {y['te'].sum():,}",
        flush=True,
    )

    extractor = TransactionFeatures(include_payment_type=False).fit(S.feature_view(tr))

    def tabular(part):
        frame = extractor.run(S.feature_view(part))
        return frame.reset_index(drop=True).astype("float32")

    # ---- tier 0: row-local only. Cheap, so it also carries the timing. ----
    t0_tr, t0_va, t0_te = tabular(tr), tabular(va), tabular(te)
    started = time.perf_counter()
    tier0 = []
    for seed in SEEDS:
        m = XGBModel(params={**XGBModel().params, "random_state": seed})
        m.fit(t0_tr, y["tr"], t0_va, y["va"])
        m.calibrate(t0_va, y["va"])
        tier0.append(m.predict(t0_te))
    tier0_rate = len(te) * len(SEEDS) / (time.perf_counter() - started)
    ev0 = evaluate(y["te"], tier0[0], budgets=(BUDGET,))
    print(
        f"  tier0: PR-AUC {ev0.pr_auc:.4f} recall@1% "
        f"{ev0.at_budget(BUDGET).recall:.4f} | {tier0_rate:,.0f} tx/s",
        flush=True,
    )
    del t0_te
    gc.collect()

    # ---- tier 1: fit on train+val with graph features, then free them ----
    g_tr = graph_slice(parts, idx["tr"], keep)
    g_va = graph_slice(parts, idx["va"], keep)
    f_tr = pd.concat([t0_tr, g_tr], axis=1)
    f_va = pd.concat([t0_va, g_va], axis=1)
    del t0_tr, t0_va, g_tr, g_va
    gc.collect()

    models = []
    for seed in SEEDS:
        m = XGBModel(params={**XGBModel().params, "random_state": seed})
        m.fit(f_tr, y["tr"], f_va, y["va"])
        m.calibrate(f_va, y["va"])
        models.append(m)
    del f_tr, f_va
    gc.collect()

    g_te = graph_slice(parts, idx["te"], keep)
    f_te = pd.concat([tabular(te), g_te], axis=1)
    del g_te
    gc.collect()
    tier1 = [m.predict(f_te) for m in models]
    del f_te, models
    gc.collect()

    ev1 = evaluate(y["te"], tier1[0], budgets=(BUDGET,))
    print(
        f"  tier1: PR-AUC {ev1.pr_auc:.4f} recall@1% "
        f"{ev1.at_budget(BUDGET).recall:.4f}",
        flush=True,
    )

    full_recall = float(
        np.mean(
            [
                evaluate(y["te"], r, budgets=(BUDGET,)).at_budget(BUDGET).recall
                for r in tier1
            ]
        )
    )
    corpus_out = {
        "rows": int(len(df)),
        "test_rows": int(len(te)),
        "test_positives": int(y["te"].sum()),
        "n_graph_features": len(keep),
        "full_extraction_recall": full_recall,
        "tier0_rate": tier0_rate,
        "tier1_rate": TIER1_RATE[corpus],
        "by_k": {},
    }

    for k in KS:
        recalls, prs = [], []
        for r0, r1 in zip(tier0, tier1):
            res = cascade(
                r0, r1, k=k, tier0_rate=tier0_rate, tier1_rate=TIER1_RATE[corpus]
            )
            ev = evaluate(y["te"], res.scores, budgets=(BUDGET,))
            recalls.append(ev.at_budget(BUDGET).recall)
            prs.append(ev.pr_auc)
        rate = 1.0 / (1.0 / tier0_rate + k / TIER1_RATE[corpus])
        retained = float(np.mean(recalls)) / full_recall if full_recall else float("nan")
        corpus_out["by_k"][f"{k}"] = {
            "recall": float(np.mean(recalls)),
            "recall_sd": float(np.std(recalls, ddof=1)),
            "pr_auc": float(np.mean(prs)),
            "retained_fraction": retained,
            "end_to_end_tx_per_s": rate,
            "gate_a_pass": bool(rate >= 1000),
            "gate_b_pass": bool(retained >= 0.95),
        }
        va_ = "PASS" if rate >= 1000 else "FAIL"
        vb_ = "PASS" if retained >= 0.95 else "FAIL"
        print(
            f"  K={k:5.0%}  recall {np.mean(recalls):.4f} ({retained:6.1%} of full)  "
            f"{rate:9,.0f} tx/s  throughput {va_}  recall {vb_}",
            flush=True,
        )

    results[corpus] = corpus_out
    del df, tr, va, te, tier0, tier1, y, idx
    gc.collect()

OUT.write_text(json.dumps(results, indent=2))
print(f"\nwrote {OUT}\nP3 DONE", flush=True)
