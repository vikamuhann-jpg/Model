"""Run the baseline ladder: sanity checks, E0 and E1 (plan v3 Phase 8).

Single reproduction command for the headline baseline numbers::

    python -m flowguard.pipeline.run_baseline --variant HI-Small

Order is deliberate. The sanity baselines run *first*: if a random scorer beats
the base rate, or a model trained on shuffled labels finds signal, the pipeline
is leaking and every subsequent number would be meaningless.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate, per_group_recall
from flowguard.evaluation.sanity import (
    run_null_baselines,
    shuffled_label_test,
    single_feature_baselines,
)
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.rules import RuleBaseline
from flowguard.models.xgb import XGBModel
from flowguard.registry.experiments import ExperimentRecord, Registry
from flowguard.splits.temporal import SplitSpec, chronological_split

DEFAULT_PROCESSED = Path("/mnt/c/Users/vikam/flowguard_data/processed")


def _print_header(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def run(
    variant: str,
    processed_dir: Path,
    registry_root: Path | None = None,
    *,
    seed: int = 42,
    sample: int | None = None,
) -> dict:
    registry = Registry(registry_root) if registry_root else Registry()
    results: dict = {}

    _print_header(f"FlowGuard baseline ladder -- {variant}")
    tx_path = processed_dir / f"{variant}_transactions.parquet"
    df = pd.read_parquet(tx_path)
    if sample:
        # Head-sampling would be time-biased; take an even stride instead.
        df = df.iloc[:: max(1, len(df) // sample)].reset_index(drop=True)
    print(f"loaded {len(df):,} transactions from {tx_path.name}")

    summary = S.summarise(df)
    dataset_meta = {"variant": variant, **summary.to_metadata()}

    # ---------------------------------------------------------------- split
    _print_header("Split")
    split = chronological_split(df, SplitSpec(seed=seed))
    train_df, val_df, test_df = split.apply(df)
    print(f"train={len(train_df):,}  val={len(val_df):,}  test={len(test_df):,}")
    print(f"boundaries: train_end={split.train_end}  val_end={split.val_end}")
    print(f"test positives: {int(test_df[S.IS_LAUNDERING].sum()):,}")
    for note in split.notes:
        print(f"note: {note}")

    y_train = train_df[S.IS_LAUNDERING].to_numpy()
    y_val = val_df[S.IS_LAUNDERING].to_numpy()
    y_test = test_df[S.IS_LAUNDERING].to_numpy()
    split_meta = split.to_metadata()

    # ------------------------------------------------------------- features
    _print_header("Features (label-blind)")
    extractor = TransactionFeatures()
    extractor.fit(S.feature_view(train_df))
    X_train = extractor.run(S.feature_view(train_df))
    X_val = extractor.run(S.feature_view(val_df))
    X_test = extractor.run(S.feature_view(test_df))
    print(f"{X_train.shape[1]} features: {', '.join(list(X_train.columns)[:6])}, ...")

    # --------------------------------------------------------------- sanity
    _print_header("Sanity baselines (must all pass)")
    sanity_results = run_null_baselines(y_test, seed=seed)

    def fit_predict(xt, yt, xs):
        model = XGBModel()
        model.n_estimators = 100
        model.fit(xt, yt)
        return model.predict_raw(xs)

    started = time.perf_counter()
    shuffled = shuffled_label_test(
        fit_predict, X_train, y_train, X_test, y_test, seed=seed
    )
    sanity_results.append(shuffled)
    print(f"(shuffled-label run took {time.perf_counter() - started:.1f}s)")

    all_passed = True
    for result in sanity_results:
        status = "PASS" if result.passed else "FAIL"
        pr = result.metrics.pr_auc
        print(f"  [{status}] {result.name:16s} PR-AUC={pr:.6f}   {result.criterion}")
        all_passed &= result.passed

    if not all_passed:
        print("\n!! SANITY FAILURE -- pipeline is leaking. Later numbers are void.")
    results["sanity"] = [r.to_metadata() for r in sanity_results]
    results["sanity_passed"] = all_passed

    # ------------------------------------------------------------------ E0
    _print_header("E0 -- rule baseline")
    started = time.perf_counter()
    rules = RuleBaseline().fit(train_df)
    e0_test = evaluate(y_test, rules.score(test_df))
    e0_seconds = time.perf_counter() - started
    print(e0_test.summary())

    registry.log(
        ExperimentRecord(
            experiment_id="E0",
            description="Rule-based baseline: fixed thresholds, no memory, no graph",
            dataset=dataset_meta,
            split=split_meta,
            features={"family": "rules", "count": len(rules.weights)},
            model=rules.to_metadata(),
            metrics={
                "test": e0_test.to_metadata(),
                "val": evaluate(y_val, rules.score(val_df)).to_metadata(),
            },
            cost={"train_seconds": round(e0_seconds, 2)},
            notes=["Thresholds fitted on the training partition only."],
        )
    )
    results["E0"] = e0_test.to_metadata()

    # ------------------------------------------------------------------ E1
    _print_header("E1 -- transaction-only XGBoost")
    model = XGBModel()
    model.fit(X_train, y_train, X_val, y_val)
    model.calibrate(X_val, y_val)
    e1_test = evaluate(y_test, model.predict(X_test))
    e1_val = evaluate(y_val, model.predict(X_val))
    print(e1_test.summary())
    print(f"  trained in {model.train_seconds_:.1f}s, "
          f"best_iteration={model.best_iteration_}")

    print("\n  top features by gain:")
    importance = model.importance(top=10)
    total_gain = sum(importance.values()) or 1.0
    for name, gain in importance.items():
        print(f"    {name:28s} {gain / total_gain:6.1%}")

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
            experiment_id="E1",
            description="Transaction-only XGBoost: row-local features, no graph",
            dataset=dataset_meta,
            split=split_meta,
            features=extractor.to_metadata() | {"count": X_train.shape[1]},
            model=model.to_metadata(),
            metrics={
                "test": e1_test.to_metadata(),
                "val": e1_val.to_metadata(),
                "typology_recall_at_1pct": typology_recall,
                "importance_gain": importance,
            },
            cost={"train_seconds": round(model.train_seconds_ or 0.0, 2)},
            notes=[
                "No cross-row information; this is the floor E2's graph "
                "features must clear.",
            ],
        )
    )
    results["E1"] = e1_test.to_metadata()

    # ------------------------------------------------- single-feature check
    _print_header("Single-feature baselines (C8 early warning)")
    for result in single_feature_baselines(X_test, y_test, top=5):
        print(f"  {result.name:40s} PR-AUC={result.metrics.pr_auc:.5f}")
    print(f"  {'[E1 full model]':40s} PR-AUC={e1_test.pr_auc:.5f}")

    # ----------------------------------------------------------- comparison
    _print_header("Comparison")
    print(f"  {'experiment':10s} {'PR-AUC':>9s} {'lift':>8s} {'R@1%':>8s} {'P@1%':>8s}")
    for name, metrics in (("E0", e0_test), ("E1", e1_test)):
        point = metrics.at_budget(0.01)
        print(
            f"  {name:10s} {metrics.pr_auc:>9.4f} {metrics.lift:>7.1f}x "
            f"{point.recall:>7.1%} {point.precision:>7.2%}"
        )
    delta = e1_test.pr_auc - e0_test.pr_auc
    print(f"\n  P2 gate (E1 beats E0): delta PR-AUC = {delta:+.4f}")

    results["comparison"] = {
        "e0_pr_auc": e0_test.pr_auc,
        "e1_pr_auc": e1_test.pr_auc,
        "delta_pr_auc": delta,
    }
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="HI-Small")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sample", type=int, default=None, help="stride-sample to N rows (smoke runs)"
    )
    parser.add_argument("--out", type=Path, default=None, help="write results JSON")
    args = parser.parse_args(argv)

    results = run(
        args.variant,
        args.processed_dir,
        args.registry,
        seed=args.seed,
        sample=args.sample,
    )
    if args.out:
        args.out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
