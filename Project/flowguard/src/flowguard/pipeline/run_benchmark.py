"""Benchmark protocol -- the GFP paper's HI-Small setup (WINNING_PLAN.md, S1).

    python -m flowguard.pipeline.run_benchmark --batch-size 128 \
        --processed-dir /mnt/c/Users/vikam/flowguard_data/processed/benchmark \
        --cache /mnt/c/Users/vikam/flowguard_data/processed/benchmark/gfp_b128 \
        --out /mnt/c/Users/vikam/flowguard_data/s1_b128.json

Deliberately NOT the A4 protocol. It follows Blanusa et al. (Table 4, "Data
split"): the untrimmed corpus, a 60/20/20 chronological split, GFP fed in
batches, mean over five runs, minority-class F1. Batches above 1 let an edge
see later batch-mates (ADR-004) -- that is the paper's protocol, and running
the same thing at --batch-size 1 measures how much of the number it explains.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.features.behaviour import behaviour_features
from flowguard.features.gfp import (
    DAY,
    DEFAULT_GFP_PARAMS,
    GFPFeatures,
    read_varying_chunks,
    timestamp_stat_columns,
    windowed_params,
)
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.tuning import search
from flowguard.models.xgb import DEFAULT_PARAMS, XGBModel
from flowguard.splits.temporal import SplitSpec, chronological_split

SEEDS = (42, 7, 123, 2024, 31337)

#: The GFP paper's AML configuration ("Graph Feature Preprocessor setup"):
#: scatter-gather over 6 hours, every other pattern and the vertex statistics
#: over 1 day, cycle length 10, vertex statistics on Amount AND Timestamp.
PAPER_GFP_PARAMS = {
    **DEFAULT_GFP_PARAMS,
    "time_window": DAY,
    "fan_tw": DAY, "degree_tw": DAY, "temp-cycle_tw": DAY, "lc-cycle_tw": DAY,
    "vertex_stats_tw": DAY,
    "scatter-gather_tw": 6 * 3600,
    "vertex_stats_cols": [3, 4],  # edge columns: 3 = timestamp, 4 = amount
}

#: WINNING_PLAN S2. Covers the paper's ranges (Table 3) on a coarse grid. The
#: paper searches scale_pos_weight over 1-10; our default is negatives/positives
#: (~980), which is the single largest departure from it.
TUNE_SPACE: dict[str, list] = {
    "max_depth": [4, 6, 8, 10, 12],
    "learning_rate": [0.01, 0.03, 0.05, 0.1],
    "subsample": [0.6, 0.8, 1.0],
    "colsample_bytree": [0.5, 0.75, 1.0],
    "min_child_weight": [1, 5, 20],
    "reg_lambda": [0.01, 0.1, 1.0, 10.0, 100.0],
    "scale_pos_weight": [1, 2, 5, 10, 30, 100],
}


def f1_at(y: np.ndarray, scores: np.ndarray, threshold: float) -> float:
    pred = scores >= threshold
    tp = int((pred & (y == 1)).sum())
    denom = int(pred.sum()) + int(y.sum())
    return 2 * tp / denom if denom else 0.0


def gfp_block(
    df: pd.DataFrame, cache: Path, batch_size: int, window_days: float | None,
    paper_params: bool = False,
) -> tuple[pd.DataFrame, dict]:
    if paper_params:
        params = dict(PAPER_GFP_PARAMS)
    else:
        params = windowed_params(window_days) if window_days else dict(DEFAULT_GFP_PARAMS)
    info = {"batch_size": batch_size, "window_days": window_days, "params": params}
    if not any(cache.glob("part_*.parquet")):
        print(f"extracting GFP, batch_size={batch_size} -> {cache}", flush=True)
        gfp = GFPFeatures(params=params, batch_size=batch_size, chunk_dir=cache)
        gfp.run_streaming(S.feature_view(df), assemble=False)
        info["extract_seconds"] = gfp.extract_seconds_
        info["tx_per_s"] = len(df) / (gfp.extract_seconds_ or 1)
        print(f"  {info['extract_seconds']:.0f}s, {info['tx_per_s']:,.0f} tx/s", flush=True)
    else:
        print(f"reusing GFP parts in {cache}", flush=True)
    return read_varying_chunks(cache, order=df.index), info


def run(
    processed_dir: Path,
    cache: Path,
    *,
    batch_size: int,
    window_days: float | None,
    include_payment_type: bool,
    seeds: tuple[int, ...] = SEEDS,
    tune: int = 0,
    behaviour: bool = False,
    paper_params: bool = False,
    params_from: Path | None = None,
    n_estimators_override: int | None = None,
    drop_timestamp_stats: bool = False,
    variant: str = "HI-Small",
) -> dict:
    df = pd.read_parquet(processed_dir / f"{variant}_transactions.parquet")
    print(f"loaded {len(df):,} transactions, {int(df[S.IS_LAUNDERING].sum()):,} positives")
    gfp, extraction = gfp_block(df, cache, batch_size, window_days, paper_params)
    if drop_timestamp_stats:
        dropped = timestamp_stat_columns(gfp.columns, extraction["params"])
        gfp = gfp.drop(columns=dropped)
        extraction["timestamp_stats_dropped"] = dropped
        print(f"dropped {len(dropped)} timestamp-statistic columns", flush=True)
    if behaviour:
        # Whole corpus, before the split: a validation row keeps its history.
        started = time.perf_counter()
        gfp = gfp.join(behaviour_features(S.feature_view(df)))
        print(f"behaviour features in {time.perf_counter() - started:.0f}s", flush=True)

    split = chronological_split(df, SplitSpec(train_frac=0.6, val_frac=0.2))
    parts = split.apply(df)
    tx = TransactionFeatures(include_payment_type=include_payment_type).fit(
        S.feature_view(parts[0])
    )
    # float32 throughout: XGBoost bins values anyway, and the float64
    # transaction block pushed S2's tuning to 11.4 GB RSS in an 11 GB WSL.
    X_train, X_val, X_test = (
        pd.concat([tx.run(S.feature_view(p)), gfp.loc[p.index]], axis=1).astype("float32")
        for p in parts
    )
    y_train, y_val, y_test = (p[S.IS_LAUNDERING].to_numpy().astype(int) for p in parts)
    del gfp, df
    gc.collect()
    print(f"split {split.sizes}; {X_train.shape[1]} features; "
          f"test positives {int(y_test.sum()):,}", flush=True)

    params, n_estimators, tuning = dict(DEFAULT_PARAMS), 300, None
    if params_from:
        # Hold the model fixed so a comparison measures features, not tuning.
        params = json.loads(Path(params_from).read_text())["params"]
        n_estimators = 1000
        tuning = {"params_from": str(params_from)}
    if n_estimators_override:
        n_estimators = n_estimators_override
    if tune:
        # Rolling-origin folds inside the training partition only; validation
        # and test are never seen. The categorical encoder was fitted on the
        # whole training partition -- vocabulary only, no labels.
        result = search(
            parts[0], lambda _fit, apply: X_train.loc[apply.index],
            base_params=params, space=TUNE_SPACE, budget=tune, n_folds=2,
            n_estimators=1000, early_stopping_rounds=50,
        )
        tuning = result.to_metadata()
        params.update(result.best_params)
        n_estimators = n_estimators_override or 1000
        print(f"tuned in {result.seconds:.0f}s: {result.best_params} "
              f"(fold PR-AUC {result.best_score:.4f})", flush=True)

    runs = []
    for seed in seeds:
        started = time.perf_counter()
        model = XGBModel(params={**params, "random_state": seed}, n_estimators=n_estimators)
        model.fit(X_train, y_train, X_val, y_val)
        val_scores, test_scores = model.predict_raw(X_val), model.predict_raw(X_test)
        # The threshold comes from validation; test best-F1 is an oracle, kept
        # only as the upper bound a tuned threshold could reach.
        val_m = evaluate(y_val, val_scores)
        threshold = val_m.best_f1_threshold
        m = evaluate(y_test, test_scores)
        runs.append({
            "seed": seed,
            "val_pr_auc": val_m.pr_auc,
            "f1_val_threshold": f1_at(y_test, test_scores, threshold),
            "f1_oracle": m.best_f1,
            "pr_auc": m.pr_auc,
            "roc_auc": m.roc_auc,
            "recall_at_1pct": m.at_budget(0.01).recall,
            "best_iteration": model.best_iteration_,
            "device": model.resolved_device_,
            "fit_seconds": round(time.perf_counter() - started, 1),
        })
        print(f"  seed {seed}: F1 {runs[-1]['f1_val_threshold']:.4f} "
              f"(oracle {m.best_f1:.4f})  PR-AUC {m.pr_auc:.4f}", flush=True)

    summary = {
        k: {"mean": float(np.mean([r[k] for r in runs])),
            "sd": float(np.std([r[k] for r in runs], ddof=1)) if len(runs) > 1 else 0.0}
        for k in ("f1_val_threshold", "f1_oracle", "pr_auc", "roc_auc", "recall_at_1pct",
                  "val_pr_auc")
    }
    print(f"\nF1 {summary['f1_val_threshold']['mean']:.4f} "
          f"± {summary['f1_val_threshold']['sd']:.4f}  "
          f"PR-AUC {summary['pr_auc']['mean']:.4f} ± {summary['pr_auc']['sd']:.4f}")
    return {
        "protocol": "GFP paper: untrimmed, 60/20/20, batched GFP",
        "variant": variant,
        "extraction": extraction,
        "include_payment_type": include_payment_type,
        "behaviour_features": behaviour,
        "split": split.to_metadata(),
        "n_features": X_train.shape[1],
        "params": params,
        "tuning": tuning,
        "runs": runs,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--variant", default="HI-Small", help="corpus, e.g. LI-Small")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--window-days", type=float, default=None,
                        help="cap GFP windows as A4 does; default = library params")
    parser.add_argument("--no-payment-type", action="store_true")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--tune", type=int, default=0, metavar="TRIALS",
                        help="random-search budget (S2); 0 = default params")
    parser.add_argument("--behaviour", action="store_true",
                        help="add the S4 account-history features")
    parser.add_argument("--paper-params", action="store_true",
                        help="the GFP paper's windows and vertex-stat columns")
    parser.add_argument("--params-from", type=Path, default=None,
                        help="reuse the model params of an earlier run's JSON")
    parser.add_argument("--n-estimators", type=int, default=None)
    parser.add_argument("--drop-timestamp-stats", action="store_true",
                        help="drop GFP vertex statistics on the timestamp column")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run(
        args.processed_dir, args.cache,
        batch_size=args.batch_size, window_days=args.window_days,
        include_payment_type=not args.no_payment_type, seeds=tuple(args.seeds),
        tune=args.tune, behaviour=args.behaviour, paper_params=args.paper_params,
        params_from=args.params_from, n_estimators_override=args.n_estimators,
        drop_timestamp_stats=args.drop_timestamp_stats, variant=args.variant,
    )
    args.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
