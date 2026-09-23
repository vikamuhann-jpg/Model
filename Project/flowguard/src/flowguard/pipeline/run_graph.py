"""E2 -- graph-feature XGBoost (plan v3 Phases 6-8).

    python -m flowguard.pipeline.run_graph --variant HI-Small

Extracts GFP features over the whole corpus in chronological order, then trains
on the same split, with the same protocol and the same evaluation code as E1.
That identity is the entire basis on which E1 and E2 can be compared.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate, per_group_recall
from flowguard.features.gfp import GFPFeatures
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.xgb import XGBModel
from flowguard.registry.experiments import ExperimentRecord, Registry
from flowguard.splits.temporal import SplitSpec, chronological_split

from flowguard.config import GFP_CACHE, PROCESSED_DIR as DEFAULT_PROCESSED


def _header(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def run(
    variant: str,
    processed_dir: Path,
    registry_root: Path | None = None,
    *,
    seed: int = 42,
    sample: int | None = None,
    cache: Path | None = None,
    window_days: float = 2.0,
    experiment_id: str = "E2",
) -> dict:
    registry = Registry(registry_root) if registry_root else Registry()

    _header(f"E2 -- graph features + XGBoost ({variant})")
    df = pd.read_parquet(processed_dir / f"{variant}_transactions.parquet")
    if sample:
        df = df.iloc[:: max(1, len(df) // sample)].reset_index(drop=True)
    print(f"loaded {len(df):,} transactions")

    dataset_meta = {"variant": variant, **S.summarise(df).to_metadata()}

    # ------------------------------------------------------------- features
    _header("GFP extraction (streaming, batch_size=1)")
    # The GFP time_window bounds the internal graph. At 10 days (the whole
    # corpus) nothing is ever evicted, so every transform searches an
    # ever-growing structure and extraction does not terminate in useful time.
    from flowguard.features.gfp import windowed_params

    # Shared with pipeline/score.py so training and inference cannot drift.
    params = windowed_params(window_days)
    chunk_dir = cache.parent / f"{cache.stem}_parts" if cache else None
    gfp = GFPFeatures(params=params, chunk_dir=chunk_dir)
    print(f"GFP time_window = {window_days} days")
    view = S.feature_view(df)

    if cache and cache.exists():
        print(f"loading cached features from {cache.name}")
        gfp_features = pd.read_parquet(cache)
        gfp_features.index = df.index
        # Features came from a potentially different machine (e.g. WSL extraction
        # loaded on Windows). Record current platform as training_platform and
        # note the cache origin so provenance is unambiguous.
        extraction_platform: str | None = platform.platform()
    else:
        extraction_platform = None  # extraction and training on the same machine
        print("extracting -- transform inserts each edge once, one edge at a time")
        started = time.perf_counter()
        gfp_features = gfp.run_streaming(view)
        print(
            f"  {gfp.n_engineered_} features over {gfp.n_vertices_:,} vertices "
            f"in {time.perf_counter() - started:.0f}s "
            f"({gfp.n_edges_inserted_ / (gfp.extract_seconds_ or 1):,.0f} tx/s)"
        )
        if cache and chunk_dir is None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            gfp_features.to_parquet(cache, index=False)
            print(f"  cached to {cache}")
        elif chunk_dir is not None:
            # The part files are the cache. Writing a monolithic copy as well
            # would double the disk and re-introduce the 4.4 GB peak that
            # chunking exists to avoid.
            print(f"  cache = {self_parts} ({len(list(chunk_dir.glob('part_*.parquet')))} parts)"
                  .replace("{self_parts}", str(chunk_dir)))

    # Drop all-constant columns: GFP emits a fixed feature block regardless of
    # which patterns actually occur, so many are structurally zero here.
    #
    # Memory matters from here on. The full block is 5M x 215 float32 = 4.4 GB,
    # and the train/val/test concats copy slices of it again. Selecting the
    # varying columns by name and releasing the original keeps the peak near one
    # copy instead of three.
    keep = [c for c in gfp_features.columns if gfp_features[c].std() > 0]
    n_total = gfp_features.shape[1]
    varying = gfp_features[keep].copy()
    del gfp_features
    gc.collect()
    print(f"  {varying.shape[1]} of {n_total} features vary", flush=True)

    tx_extractor = TransactionFeatures()

    # ---------------------------------------------------------------- split
    split = chronological_split(df, SplitSpec(seed=seed))
    train_df, val_df, test_df = split.apply(df)
    y_train = train_df[S.IS_LAUNDERING].to_numpy()
    y_val = val_df[S.IS_LAUNDERING].to_numpy()
    y_test = test_df[S.IS_LAUNDERING].to_numpy()
    print(
        f"\nsplit: train={len(train_df):,} val={len(val_df):,} test={len(test_df):,} "
        f"(test positives {int(y_test.sum()):,})"
    )

    tx_extractor.fit(S.feature_view(train_df))

    def build(part: pd.DataFrame) -> pd.DataFrame:
        tabular = tx_extractor.run(S.feature_view(part))
        return pd.concat([tabular, varying.loc[part.index]], axis=1)

    X_train, X_val, X_test = build(train_df), build(val_df), build(test_df)
    del varying
    gc.collect()
    print(f"combined feature count: {X_train.shape[1]}", flush=True)

    # ------------------------------------------------------------------ fit
    _header("Training")
    model = XGBModel()
    model.fit(X_train, y_train, X_val, y_val)
    model.calibrate(X_val, y_val)
    metrics = evaluate(y_test, model.predict(X_test))
    print(metrics.summary())
    print(f"  trained in {model.train_seconds_:.1f}s, best_iteration={model.best_iteration_}")

    importance = model.importance(top=15)
    total = sum(importance.values()) or 1.0
    print("\n  top features by gain:")
    for name, gain in importance.items():
        marker = "graph" if name.startswith("gfp_") else "tab  "
        print(f"    [{marker}] {name:26s} {gain / total:6.1%}")

    gfp_share = sum(
        gain for name, gain in importance.items() if name.startswith("gfp_")
    ) / total
    print(f"\n  graph features hold {gfp_share:.1%} of top-15 gain")

    typology_recall = per_group_recall(
        y_test, model.predict(X_test), test_df[S.PATTERN_TYPE].to_numpy(), budget=0.01
    )
    if typology_recall:
        print("\n  recall per typology @1% budget:")
        for typology, stats in sorted(typology_recall.items()):
            print(
                f"    {typology:18s} {stats['recall']:6.1%} "
                f"({stats['caught']}/{stats['positives']})"
            )

    registry.log(
        ExperimentRecord(
            experiment_id=experiment_id,
            description=(
                f"GFP graph features ({window_days}d window) + transaction "
                "features, XGBoost"
            ),
            dataset=dataset_meta,
            split=split.to_metadata(),
            features={
                "family": "gfp+tx",
                "count": X_train.shape[1],
                "gfp": gfp.to_metadata(),
                "gfp_varying": int(varying.shape[1]),
            },
            model=model.to_metadata(),
            metrics={
                "test": metrics.to_metadata(),
                "val": evaluate(y_val, model.predict(X_val)).to_metadata(),
                "typology_recall_at_1pct": typology_recall,
                "importance_gain": importance,
                "gfp_share_of_top15_gain": gfp_share,
            },
            cost={
                "train_seconds": round(model.train_seconds_ or 0.0, 2),
                "extract_seconds": gfp.extract_seconds_,
            },
            notes=[
                "batch_size=1: GFP's transform lets an edge see later edges in "
                "the same batch, so larger batches leak future structure.",
                "Self-transfers excluded from the graph, retained as rows.",
            ],
            extraction_platform=extraction_platform,
        )
    )

    # ----------------------------------------------------------- comparison
    _header("E1 vs E2 (gate P1)")
    try:
        e1 = registry.load("E1")["metrics"]["test"]
        delta = metrics.pr_auc - e1["pr_auc"]
        print(f"  E1 PR-AUC = {e1['pr_auc']:.4f}")
        print(f"  E2 PR-AUC = {metrics.pr_auc:.4f}")
        print(f"  delta     = {delta:+.4f}")
        e1_r = next(b for b in e1["budgets"] if b["budget"] == 0.01)["recall"]
        e2_r = metrics.at_budget(0.01).recall
        print(f"  recall@1%: {e1_r:.1%} -> {e2_r:.1%}  ({e2_r - e1_r:+.1%})")
    except FileNotFoundError:
        print("  E1 not in the registry; run run_baseline first")
        delta = None

    return {
        "E2": metrics.to_metadata(),
        "delta_vs_e1": delta,
        "gfp_share_of_top15_gain": gfp_share,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="HI-Small")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--cache", type=Path, default=None,
                        help="path to GFP feature parquet; defaults to paths.yaml gfp_cache"
                             " when --cache is not supplied (set to GFP_CACHE in config.py)")
    parser.add_argument("--window-days", type=float, default=2.0)
    parser.add_argument("--chunk-rows", type=int, default=250_000)
    parser.add_argument("--experiment-id", default="E2")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    results = run(
        args.variant,
        args.processed_dir,
        args.registry,
        seed=args.seed,
        sample=args.sample,
        cache=args.cache,
        window_days=args.window_days,
        experiment_id=args.experiment_id,
    )
    if args.out:
        args.out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
