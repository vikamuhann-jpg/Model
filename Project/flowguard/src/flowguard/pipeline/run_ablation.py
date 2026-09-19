"""Controlled ablations — one change at a time (plan v3 section 21).

    python -m flowguard.pipeline.run_ablation --variant HI-Small

Two rules make an ablation mean anything, and both are enforced here:

* **One change per arm.** Everything else — split, protocol, evaluation code,
  search budget — is identical across arms.
* **Repeated across seeds.** A single run on this corpus carries roughly
  +/-0.002 PR-AUC of noise, so a difference is only real above the 2-sigma bar
  measured from the seed spread itself.

The first ablation the project needs is `payment_type`, which is a generator
artifact rather than a feature (docs/ADR-007-payment-type-artifact.md).
"""

from __future__ import annotations

import argparse
import gc
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate
from flowguard.features.adaptive import AdaptiveFeatures
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.xgb import XGBModel
from flowguard.registry.experiments import ExperimentRecord, Registry
from flowguard.splits.temporal import SplitSpec, chronological_split

from flowguard.config import PROCESSED_DIR as DEFAULT_PROCESSED
SEEDS = (42, 7, 123, 2024, 31337)


@dataclass
class Arm:
    """One ablation arm: a name, and the single thing that differs."""

    name: str
    description: str
    include_payment_type: bool = True
    include_gfp: bool = False
    include_adaptive: bool = False
    scores: list[float] = field(default_factory=list)
    recalls: list[float] = field(default_factory=list)
    n_features: int | None = None
    is_leaky: bool = False

    @property
    def mean(self) -> float:
        return float(np.mean(self.scores)) if self.scores else float("nan")

    @property
    def sd(self) -> float:
        return float(np.std(self.scores, ddof=1)) if len(self.scores) > 1 else 0.0

    @property
    def mean_recall(self) -> float:
        return float(np.mean(self.recalls)) if self.recalls else float("nan")

    def to_metadata(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "include_payment_type": self.include_payment_type,
            "include_gfp": self.include_gfp,
            "include_adaptive": self.include_adaptive,
            "n_features": self.n_features,
            "pr_auc_runs": self.scores,
            "pr_auc_mean": self.mean,
            "pr_auc_sd": self.sd,
            "recall_at_1pct_mean": self.mean_recall,
        }


def run(
    variant: str,
    processed_dir: Path,
    *,
    gfp_cache: Path | None = None,
    seeds: tuple[int, ...] = SEEDS,
    out: Path | None = None,
) -> dict:
    df = pd.read_parquet(processed_dir / f"{variant}_transactions.parquet")
    split = chronological_split(df, SplitSpec())
    train_df, val_df, test_df = split.apply(df)
    y_train = train_df[S.IS_LAUNDERING].to_numpy().astype(int)
    y_val = val_df[S.IS_LAUNDERING].to_numpy().astype(int)
    y_test = test_df[S.IS_LAUNDERING].to_numpy().astype(int)

    gfp = None
    if gfp_cache and gfp_cache.exists():
        if gfp_cache.is_dir():
            from flowguard.features.gfp import read_varying_chunks

            gfp = read_varying_chunks(gfp_cache, order=df.index)
        else:
            gfp = pd.read_parquet(gfp_cache)
            gfp.index = df.index
            gfp = gfp.loc[:, gfp.std(numeric_only=True) > 0]
        gc.collect()
        print(f"GFP features available: {gfp.shape[1]}", flush=True)

    arms = [
        Arm("A1", "transaction features, payment_type included", True, False),
        Arm("A2", "transaction features, payment_type REMOVED", False, False),
    ]
    if gfp is not None:
        arms += [
            Arm("A3", "+ GFP graph features, payment_type included", True, True),
            Arm("A4", "+ GFP graph features, payment_type REMOVED", False, True),
        ]
    arms.append(Arm("A5", "+ adaptive neighbourhood, no graph", False, False))
    arms[-1].include_adaptive = True
    if gfp is not None:
        arms.append(Arm("A6", "+ GFP graph + adaptive neighbourhood", False, True))
        arms[-1].include_adaptive = True
    arms.append(Arm("E_LEAK", "deliberate leak: random split, global fit", False, False, is_leaky=True))

    print(f"\n{len(arms)} arms x {len(seeds)} seeds "
          f"| train={len(y_train):,} test={len(y_test):,} "
          f"| test positives={y_test.sum():,}\n", flush=True)

    for arm in arms:
        if arm.is_leaky:
            # Deliberate leak: random split instead of chronological, and fit on entire df
            from sklearn.model_selection import train_test_split
            train_idx, test_idx = train_test_split(df.index, test_size=0.15, random_state=42)
            train_idx, val_idx = train_test_split(train_idx, test_size=0.15/0.85, random_state=42)
            arm_train_df = df.loc[train_idx]
            arm_val_df = df.loc[val_idx]
            arm_test_df = df.loc[test_idx]
            fit_df = df  # Fit on everything!
        else:
            arm_train_df, arm_val_df, arm_test_df = train_df, val_df, test_df
            fit_df = train_df
            
        extractor = TransactionFeatures(
            include_payment_type=arm.include_payment_type
        ).fit(S.feature_view(fit_df))

        adaptive = None
        if arm.include_adaptive:
            adaptive = AdaptiveFeatures().fit(S.feature_view(fit_df))

        def build(part: pd.DataFrame) -> pd.DataFrame:
            blocks = [extractor.run(S.feature_view(part))]
            if arm.include_gfp and gfp is not None:
                blocks.append(gfp.loc[part.index])
            if adaptive is not None:
                blocks.append(adaptive.run(S.feature_view(part)))
            return pd.concat(blocks, axis=1) if len(blocks) > 1 else blocks[0]

        X_train, X_val, X_test = build(arm_train_df), build(arm_val_df), build(arm_test_df)
        arm_y_train = arm_train_df[S.IS_LAUNDERING].to_numpy().astype(int)
        arm_y_val = arm_val_df[S.IS_LAUNDERING].to_numpy().astype(int)
        arm_y_test = arm_test_df[S.IS_LAUNDERING].to_numpy().astype(int)
        
        arm.n_features = X_train.shape[1]

        for seed in seeds:
            model = XGBModel(params={**XGBModel().params, "random_state": seed})
            model.fit(X_train, arm_y_train, X_val, arm_y_val)
            model.calibrate(X_val, arm_y_val)
            m = evaluate(arm_y_test, model.predict(X_test))
            arm.scores.append(m.pr_auc)
            arm.recalls.append(m.at_budget(0.01).recall)

        print(f"  {arm.name}  {arm.description:48s} "
              f"{arm.n_features:>4d} feat  "
              f"PR-AUC {arm.mean:.4f} +/- {arm.sd:.4f}  "
              f"R@1% {arm.mean_recall:.1%}", flush=True)

        # Release before the next arm allocates. Seven arms each holding a
        # train/val/test set on top of the GFP block exceeded the memory
        # ceiling and killed the VM outright.
        del X_train, X_val, X_test, extractor, adaptive
        gc.collect()

    # Pooled seed sd sets the bar every comparison is judged against.
    pooled_sd = float(np.mean([a.sd for a in arms if a.sd > 0]))
    two_sigma = 2 * pooled_sd

    print(f"\npooled seed sd = {pooled_sd:.4f}  =>  2 sigma = {two_sigma:.4f}", flush=True)
    print("\ncomparisons:", flush=True)
    comparisons = []
    pairs = [("A1", "A2", "cost of removing the payment_type artifact")]
    if gfp is not None:
        pairs += [
            ("A3", "A1", "graph features, artifact present"),
            ("A4", "A2", "graph features, artifact removed"),
            ("A5", "A2", "adaptive neighbourhood alone"),
            ("A6", "A4", "adaptive ON TOP of graph -- the Tier B question"),
        ]
    index = {a.name: a for a in arms}
    for better, worse, label in pairs:
        if better not in index or worse not in index:
            continue
        delta = index[better].mean - index[worse].mean
        verdict = (
            "REAL" if abs(delta) > two_sigma else "within noise"
        )
        sign = "+" if delta >= 0 else ""
        print(f"  {better} - {worse}  {label:44s} {sign}{delta:.4f}  {verdict}", flush=True)
        comparisons.append({
            "arms": [better, worse], "label": label, "delta": delta,
            "two_sigma": two_sigma, "verdict": verdict,
        })

    registry = Registry()
    registry.log(ExperimentRecord(
        experiment_id="ABLATION",
        description="payment_type artifact and GFP graph features, 5 seeds per arm",
        dataset={"variant": variant, **S.summarise(df).to_metadata()},
        split=split.to_metadata(),
        features={"family": "ablation", "count": max(a.n_features or 0 for a in arms)},
        model={"model": "XGBoost", "seeds": list(seeds)},
        metrics={
            "arms": [a.to_metadata() for a in arms],
            "pooled_seed_sd": pooled_sd,
            "two_sigma": two_sigma,
            "comparisons": comparisons,
        },
        cost={},
        notes=[
            "One change per arm; split, protocol and evaluation identical throughout.",
            "payment_type is a generator artifact: 2,553 of 2,554 annotated pattern "
            "rows are ACH (ADR-007).",
        ],
    ))

    result = {
        "arms": [a.to_metadata() for a in arms],
        "pooled_seed_sd": pooled_sd,
        "two_sigma": two_sigma,
        "comparisons": comparisons,
    }
    if out:
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {out}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="HI-Small")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--gfp-cache", type=Path, default=None)
    parser.add_argument("--seeds", type=int, nargs="*", default=list(SEEDS))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    run(args.variant, args.processed_dir, gfp_cache=args.gfp_cache,
        seeds=tuple(args.seeds), out=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
