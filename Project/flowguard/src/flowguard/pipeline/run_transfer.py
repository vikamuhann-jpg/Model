"""Tier C -- does graph structure carry signal on a real network?

Two arms on a contiguous slice of the XBlock ETH phishing graph: T1 uses
row-local tabular features only, T2 adds GFP graph features. Evaluation is
account-level (S4).

This result is **never** comparable to the HI-Small numbers. HI-Small asks "is
this transaction part of laundering?"; ETH asks "is this account a phisher?".
Different question, different unit, different base rate. Report side by side,
never merged.

The corpus has no transaction-level truth, so training uses a weak proxy: a
transaction is suspicious if an endpoint is a known phisher. That proxy is the
hazard -- see :func:`partition_accounts` and ADR-012.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.data.capabilities import detect
from flowguard.evaluation.account_level import evaluate_accounts
from flowguard.features.gfp import (
    DAY,
    DEFAULT_GFP_PARAMS,
    GFPFeatures,
    read_varying_chunks,
)
from flowguard.features.behaviour import behaviour_features
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.xgb import XGBModel
from flowguard.splits.temporal import BoundaryPolicy, SplitSpec, chronological_split

SEEDS = (42, 7, 123)
EVAL_FRACTION = 0.30


def partition_accounts(
    labels: pd.DataFrame, eval_fraction: float = EVAL_FRACTION
) -> pd.DataFrame:
    """Split labelled accounts into a train side and an eval side.

    A chronological split is not enough when training labels are derived from
    account-level truth. An account persists across the time boundary, so a hub
    labelled illicit would contribute positive proxy rows to training and then be
    scored from its own label at test time. The model never sees an account id,
    but GFP features describe structural position, and a persistent hub's
    structure is close to an identifier -- so it could be memorised.

    Worse, the leak is not symmetric: graph features identify an account far
    better than row-local ones do, so it would inflate T2 over T1, which is
    exactly the contrast being measured.

    Hashing rather than shuffling keeps the partition identical across seeds, so
    the repeats differ only in model initialisation. See ADR-012.
    """
    out = labels.copy()
    cut = int(eval_fraction * 100)

    def side(account_id: str) -> str:
        digest = hashlib.blake2b(account_id.encode(), digest_size=8).digest()
        return "eval" if int.from_bytes(digest, "big") % 100 < cut else "train"

    out["side"] = [side(a) for a in out.account_id]
    return out


def run(
    processed_dir: Path,
    slice_start: str,
    slice_end: str,
    out_path: Path,
    chunk_dir: Path | None = None,
    window_days: float = 2.0,
    reuse_chunks: bool = False,
) -> dict:
    processed_dir = Path(processed_dir)
    df = pd.read_parquet(processed_dir / "ETH_transactions.parquet")
    df = df[
        (df[S.TIMESTAMP] >= pd.Timestamp(slice_start, tz="UTC"))
        & (df[S.TIMESTAMP] < pd.Timestamp(slice_end, tz="UTC"))
    ].reset_index(drop=True)

    labels = pd.read_parquet(processed_dir / "ETH_labels.parquet")
    accounts = set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT])
    labels = labels[labels.account_id.isin(accounts)].reset_index(drop=True)
    print(
        f"slice {slice_start[:10]}..{slice_end[:10]}  {len(df):,} rows  "
        f"{len(accounts):,} accounts  {int(labels.is_illicit.sum()):,} illicit",
        flush=True,
    )

    caps = detect(df, "ETH-Phishing", account_labels=labels)
    print("\n" + caps.summary(), flush=True)

    labels = partition_accounts(labels)
    train_illicit = set(
        labels.loc[(labels.is_illicit == 1) & (labels.side == "train"), "account_id"]
    )
    eval_labels = labels.loc[labels.side == "eval", ["account_id", "is_illicit"]]
    print(
        f"\naccount partition: {len(train_illicit):,} illicit usable for training, "
        f"{int(eval_labels.is_illicit.sum()):,} held out for evaluation "
        f"({len(eval_labels):,} eval accounts)",
        flush=True,
    )

    # No typology annotations, so the purge policy cannot derive a buffer.
    split = chronological_split(df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT))
    train_df, val_df, test_df = split.apply(df)
    print(
        f"train={len(train_df):,} val={len(val_df):,} test={len(test_df):,}", flush=True
    )

    def proxy(part: pd.DataFrame) -> np.ndarray:
        """Weak training signal only. Never enters a reported metric."""
        hit = part[S.SOURCE_ACCOUNT].isin(train_illicit) | part[
            S.DESTINATION_ACCOUNT
        ].isin(train_illicit)
        return hit.to_numpy().astype(int)

    params = dict(DEFAULT_GFP_PARAMS)
    window = int(window_days * DAY)
    params["time_window"] = window
    for key in ("vertex_stats_tw", "scatter-gather_tw", "temp-cycle_tw", "lc-cycle_tw"):
        params[key] = min(params[key], window)

    truncated_from = None
    if reuse_chunks:
        # Extraction cost on this corpus is super-linear in the rows already
        # inserted -- each 250k block cost roughly twice the one before, so the
        # full slice projected past fifteen hours. Chunked persistence
        # (ADR-009) means the completed prefix survives the stop, and a
        # *contiguous* prefix preserves graph topology, which a stride sample
        # would not. So the experiment runs on what was extracted.
        print("\n=== reusing GFP chunks ===", flush=True)
        gfp = read_varying_chunks(chunk_dir)
        covered = df.index.intersection(gfp.index)
        if len(covered) < len(df):
            truncated_from = int(len(df))
            print(
                f"  chunks cover {len(covered):,} of {len(df):,} rows "
                f"({len(covered) / len(df):.1%}); truncating the slice to that "
                f"contiguous prefix",
                flush=True,
            )
            df = df.loc[covered].sort_index()
            # Labels and the account partition must follow the truncation, or
            # the eval set would contain accounts the model never saw.
            accounts = set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT])
            labels = labels[labels.account_id.isin(accounts)]
            train_illicit &= accounts
            eval_labels = eval_labels[eval_labels.account_id.isin(accounts)]
            split = chronological_split(
                df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
            )
            train_df, val_df, test_df = split.apply(df)
            print(
                f"  after truncation: {len(train_illicit):,} illicit for training, "
                f"{int(eval_labels.is_illicit.sum()):,} held out "
                f"({len(eval_labels):,} eval accounts)",
                flush=True,
            )
            print(
                f"  train={len(train_df):,} val={len(val_df):,} test={len(test_df):,}",
                flush=True,
            )
        gfp = gfp.loc[df.index]
    else:
        print("\n=== GFP extraction ===", flush=True)
        if chunk_dir is not None:
            shutil.rmtree(chunk_dir, ignore_errors=True)
            Path(chunk_dir).mkdir(parents=True)
        started = time.perf_counter()
        gfp = GFPFeatures(
            params=params, progress_every=250_000, chunk_dir=chunk_dir
        ).run_streaming(S.feature_view(df))
        elapsed = time.perf_counter() - started
        print(f"extracted in {elapsed:.0f}s ({len(df) / elapsed:,.0f} tx/s)", flush=True)

    gfp = gfp[[c for c in gfp.columns if gfp[c].std() > 0]]
    gc.collect()
    print(f"{gfp.shape[1]} varying graph features", flush=True)

    # T3 tests the HI-Small behaviour features (WINNING_PLAN S4) on a real network:
    # the check that they describe behaviour rather than the synthetic generator.
    history = behaviour_features(S.feature_view(df))

    results: dict = {}
    for name, use_gfp, use_bh in (("T1", False, False), ("T2", True, False),
                                  ("T3", True, True)):
        extractor = TransactionFeatures(include_payment_type=False).fit(
            S.feature_view(train_df)
        )

        def build(part: pd.DataFrame, _gfp: bool = use_gfp, _bh: bool = use_bh) -> pd.DataFrame:
            blocks = [extractor.run(S.feature_view(part))]
            if _gfp:
                blocks.append(gfp.loc[part.index])
            if _bh:
                blocks.append(history.loc[part.index])
            return pd.concat(blocks, axis=1)

        x_train, x_val, x_test = build(train_df), build(val_df), build(test_df)
        y_train, y_val = proxy(train_df), proxy(val_df)
        scores = []
        for seed in SEEDS:
            model = XGBModel(params={**XGBModel().params, "random_state": seed})
            model.fit(x_train, y_train, x_val, y_val)
            model.calibrate(x_val, y_val)
            report = evaluate_accounts(test_df, model.predict(x_test), eval_labels)
            scores.append(report.primary.pr_auc)
            print(
                f"  {name} seed {seed}: account PR-AUC {report.primary.pr_auc:.4f}",
                flush=True,
            )
        results[name] = {
            "features": int(x_train.shape[1]),
            "pr_auc_runs": scores,
            "mean": float(np.mean(scores)),
            "sd": float(np.std(scores, ddof=1)),
            "n_labelled": int(report.n_labelled),
            "n_positive": int(report.n_positive),
            "base_rate": float(report.n_positive / report.n_labelled),
        }
        print(
            f"{name}: {x_train.shape[1]} feat  account PR-AUC "
            f"{np.mean(scores):.4f} +/- {np.std(scores, ddof=1):.4f}",
            flush=True,
        )
        del x_train, x_val, x_test
        gc.collect()

    sd = float(np.mean([results[k]["sd"] for k in ("T1", "T2")]))
    delta = results["T2"]["mean"] - results["T1"]["mean"]
    print(
        f"\nT2 - T1 = {delta:+.4f}   2 sigma = {2 * sd:.4f}   "
        f"=> {'REAL' if abs(delta) > 2 * sd else 'WITHIN NOISE'}",
        flush=True,
    )
    sd3 = float(np.mean([results[k]["sd"] for k in ("T2", "T3")]))
    delta3 = results["T3"]["mean"] - results["T2"]["mean"]
    print(f"T3 - T2 = {delta3:+.4f}   2 sigma = {2 * sd3:.4f}   "
          f"=> {'REAL' if abs(delta3) > 2 * sd3 else 'WITHIN NOISE'}", flush=True)
    results["verdict"] = {
        "delta": delta,
        "two_sigma": 2 * sd,
        "real": bool(abs(delta) > 2 * sd),
        "behaviour_delta_T3_minus_T2": delta3,
        "behaviour_two_sigma": 2 * sd3,
        "behaviour_real": bool(abs(delta3) > 2 * sd3),
        "slice": [slice_start, slice_end],
        "rows": int(len(df)),
        "protocol": "chronological split + account-disjoint labels (hash, 30% eval)",
        "training_signal": "weak proxy: endpoint in a TRAIN-side illicit account",
        "truncated_from_rows": truncated_from,
        "capabilities": caps.to_metadata(),
    }
    Path(out_path).write_text(json.dumps(results, indent=2, default=str))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--slice-start", required=True)
    parser.add_argument("--slice-end", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chunk-dir", type=Path, default=None)
    parser.add_argument("--window-days", type=float, default=2.0)
    parser.add_argument(
        "--reuse-chunks",
        action="store_true",
        help="Skip extraction and use the part files already in --chunk-dir, "
        "truncating the slice to the contiguous prefix they cover.",
    )
    args = parser.parse_args(argv)
    run(
        args.processed_dir,
        args.slice_start,
        args.slice_end,
        args.out,
        chunk_dir=args.chunk_dir,
        window_days=args.window_days,
        reuse_chunks=args.reuse_chunks,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
