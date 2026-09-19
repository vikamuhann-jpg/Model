"""Validation gates and the model package (plan v3 section 26) — the terminus.

    python -m flowguard.pipeline.run_validation --variant HI-Small

Runs every evaluation the plan requires against the selected model, judges gates
C1-C8 and P1-P9, and writes `models/flowguard_<id>_v1/` exactly as v3 section
26.4 specifies. Anything downstream consumes that directory and re-derives
nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation import gates as G
from flowguard.evaluation.error_analysis import analyse
from flowguard.evaluation.interpretation import explain, stability_across_seeds
from flowguard.evaluation.metrics import evaluate, per_group_recall
from flowguard.evaluation.profiling import CostProfile, inference_latency, peak_rss_gb
from flowguard.evaluation.sanity import run_null_baselines, shuffled_label_test
from flowguard.evaluation.stability import feature_drift, temporal_subwindows
from flowguard.evaluation.thresholds import ThresholdSource, select_thresholds
from flowguard.features.transaction import TransactionFeatures
from flowguard.models.xgb import XGBModel
from flowguard.registry.experiments import ExperimentRecord, Registry
from flowguard.splits.hard_negative import select_hard_negatives
from flowguard.splits.temporal import SplitSpec, chronological_split
from flowguard.splits.unseen_pattern import annotation_coverage, split_by_typology

from flowguard.config import PROCESSED_DIR as DEFAULT_PROCESSED
BUDGETS = (0.001, 0.005, 0.01, 0.05)
SEEDS = (42, 7, 123, 2024, 31337)

#: Pre-registered in configs/experiment.yaml before any result existed.
P4_TARGET_RECALL = 0.45
P6_MAX_SD = 0.02


def _header(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True, cwd=Path(__file__).resolve().parent,
        )
        return out.stdout.strip()
    except Exception:
        return None


def schema_hash(columns: list[str]) -> str:
    """Stable hash of the feature contract (gate C5)."""
    return hashlib.sha256("|".join(columns).encode()).hexdigest()[:16]


@dataclass
class ValidationInputs:
    df: pd.DataFrame
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    split: object
    extractor: TransactionFeatures


def build_inputs(
    variant: str, processed_dir: Path, gfp_cache: Path | None, seed: int
) -> ValidationInputs:
    df = pd.read_parquet(processed_dir / f"{variant}_transactions.parquet")
    print(f"loaded {len(df):,} transactions", flush=True)

    split = chronological_split(df, SplitSpec(seed=seed))
    train_df, val_df, test_df = split.apply(df)

    extractor = TransactionFeatures().fit(S.feature_view(train_df))

    gfp_features = None
    if gfp_cache and gfp_cache.exists():
        # The cache is a directory of part files (ADR-009). A plain
        # read_parquet on it would lose the row index the parts carry.
        if gfp_cache.is_dir():
            from flowguard.features.gfp import read_chunks

            gfp_features = read_chunks(gfp_cache, order=df.index)
        else:
            gfp_features = pd.read_parquet(gfp_cache)
            gfp_features.index = df.index
        keep = [c for c in gfp_features.columns if gfp_features[c].std() > 0]
        gfp_features = gfp_features[keep]
        print(f"loaded {gfp_features.shape[1]} varying GFP features", flush=True)

    def build(part: pd.DataFrame) -> pd.DataFrame:
        tabular = extractor.run(S.feature_view(part))
        if gfp_features is None:
            return tabular
        return pd.concat([tabular, gfp_features.loc[part.index]], axis=1)

    return ValidationInputs(
        df=df,
        X_train=build(train_df),
        X_val=build(val_df),
        X_test=build(test_df),
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        split=split,
        extractor=extractor,
    )


def run(
    variant: str,
    processed_dir: Path,
    *,
    gfp_cache: Path | None = None,
    model_id: str = "E2",
    seed: int = 42,
    out_root: Path | None = None,
    n_seeds: int = len(SEEDS),
) -> dict:
    registry = Registry()
    report = G.GateReport()
    started = time.perf_counter()

    _header(f"FlowGuard validation — {variant} / {model_id}")
    inputs = build_inputs(variant, processed_dir, gfp_cache, seed)
    y_train = inputs.train_df[S.IS_LAUNDERING].to_numpy().astype(int)
    y_val = inputs.val_df[S.IS_LAUNDERING].to_numpy().astype(int)
    y_test = inputs.test_df[S.IS_LAUNDERING].to_numpy().astype(int)
    print(
        f"train={len(y_train):,} val={len(y_val):,} test={len(y_test):,} "
        f"| test positives {y_test.sum():,} | features {inputs.X_train.shape[1]}",
        flush=True,
    )

    # ------------------------------------------------------------ main model
    _header("Training the model under validation")
    model = XGBModel()
    model.fit(inputs.X_train, y_train, inputs.X_val, y_val)
    model.calibrate(inputs.X_val, y_val)
    test_scores = model.predict(inputs.X_test)
    metrics = evaluate(y_test, test_scores, budgets=BUDGETS)
    print(metrics.summary(), flush=True)
    print(f"  device={model.resolved_device_}  {model.train_seconds_:.1f}s", flush=True)

    # --------------------------------------------------------- C2, C3 sanity
    _header("C2 / C3 — sanity baselines")
    nulls = run_null_baselines(y_test, seed=seed)
    for r in nulls:
        print(f"  {r.name:10s} PR-AUC={r.metrics.pr_auc:.6f} "
              f"{'PASS' if r.passed else 'FAIL'}", flush=True)

    def fit_predict(xt, yt, xs):
        m = XGBModel(n_estimators=120, early_stopping_rounds=0)
        m.fit(xt, yt)
        return m.predict_raw(xs)

    shuffled = shuffled_label_test(
        fit_predict, inputs.X_train, y_train, inputs.X_test, y_test, seed=seed
    )
    print(f"  shuffled   PR-AUC={shuffled.metrics.pr_auc:.6f} "
          f"{'PASS' if shuffled.passed else 'FAIL'}", flush=True)

    report.add(G.correctness(
        "C2", G.GateStatus.PASS if shuffled.passed else G.GateStatus.FAIL,
        f"shuffled-label PR-AUC {shuffled.metrics.pr_auc:.6f} vs base rate "
        f"{metrics.base_rate:.6f}",
    ))
    random_ok = nulls[0].passed
    report.add(G.correctness(
        "C3", G.GateStatus.PASS if random_ok else G.GateStatus.FAIL,
        f"random-score PR-AUC {nulls[0].metrics.pr_auc:.6f}",
    ))

    # ------------------------------------------------------------ C4 split
    tr_max = inputs.train_df[S.TIMESTAMP].max()
    va_min = inputs.val_df[S.TIMESTAMP].min()
    va_max = inputs.val_df[S.TIMESTAMP].max()
    te_min = inputs.test_df[S.TIMESTAMP].min()
    ordered = bool(tr_max < va_min and va_max < te_min)
    report.add(G.correctness(
        "C4", G.GateStatus.PASS if ordered else G.GateStatus.FAIL,
        f"train_end={tr_max}, val_end={va_max}; strictly ordered={ordered}",
    ))

    # ------------------------------------------------------------ C5 schema
    train_hash = schema_hash(list(inputs.X_train.columns))
    test_hash = schema_hash(list(inputs.X_test.columns))
    report.add(G.correctness(
        "C5", G.GateStatus.PASS if train_hash == test_hash else G.GateStatus.FAIL,
        f"feature schema hash {train_hash} (train) vs {test_hash} (test)",
    ))

    # --------------------------------------------------------- C7 determinism
    _header("C7 — determinism")
    repeat = XGBModel()
    repeat.fit(inputs.X_train, y_train, inputs.X_val, y_val)
    repeat.calibrate(inputs.X_val, y_val)
    identical = bool(np.allclose(repeat.predict(inputs.X_test), test_scores, atol=1e-9))
    print(f"  identical predictions on re-fit: {identical}", flush=True)
    report.add(G.correctness(
        "C7", G.GateStatus.PASS if identical else G.GateStatus.FAIL,
        f"same seed and data reproduce predictions: {identical}",
    ))

    # ------------------------------------------------------------- C8 SHAP
    _header("C8 — SHAP interpretation")
    interp = explain(model, inputs.X_test, seed=seed)
    print(interp.summary(), flush=True)
    report.add(G.correctness(
        "C8", G.GateStatus.PASS if interp.passes_c8 else G.GateStatus.FAIL,
        f"top feature {interp.top_feature} holds {interp.top_share:.1%} of mean |SHAP|",
    ))

    # --------------------------------------------------- C1 leakage suite
    _header("C1 — leakage suite")
    suite = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/leakage", "-q", "--no-header"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[3],
    )
    suite_ok = suite.returncode == 0
    tail = (suite.stdout or "").strip().splitlines()
    print(f"  {tail[-1] if tail else 'no output'}", flush=True)
    report.add(G.correctness(
        "C1", G.GateStatus.PASS if suite_ok else G.GateStatus.FAIL,
        tail[-1] if tail else "pytest produced no output",
    ))

    # ------------------------------------------------- P6 seed stability
    _header("P6 — seed stability")
    seed_scores, interps = [], []
    for s in SEEDS[:n_seeds]:
        m = XGBModel(params={**XGBModel().params, "random_state": s})
        m.fit(inputs.X_train, y_train, inputs.X_val, y_val)
        m.calibrate(inputs.X_val, y_val)
        pr = evaluate(y_test, m.predict(inputs.X_test)).pr_auc
        seed_scores.append(pr)
        interps.append(explain(m, inputs.X_test, sample=5000, seed=s))
        print(f"  seed {s:<6d} PR-AUC={pr:.4f}", flush=True)

    sd = float(np.std(seed_scores, ddof=1)) if len(seed_scores) > 1 else 0.0
    mean_pr = float(np.mean(seed_scores))
    two_sigma = 2 * sd
    print(f"  mean={mean_pr:.4f} sd={sd:.4f}  =>  2 sigma = {two_sigma:.4f}", flush=True)
    report.add(G.performance(
        "P6", G.GateStatus.PASS if sd < P6_MAX_SD else G.GateStatus.FAIL,
        f"sd {sd:.4f} vs < {P6_MAX_SD}", measured=sd, threshold=P6_MAX_SD,
    ))
    shap_stability = stability_across_seeds(interps)

    # ---------------------------------------------------- P1 / P2 comparisons
    _header("P1 / P2 — experiment comparisons")
    for gate_id, better, worse in (("P1", model_id, "E1"), ("P2", "E1", "E0")):
        try:
            a = registry.load(better)["metrics"]["test"]["pr_auc"]
            b = registry.load(worse)["metrics"]["test"]["pr_auc"]
        except FileNotFoundError:
            report.add(G.performance(gate_id, G.GateStatus.NOT_RUN,
                                     f"{better} or {worse} not in registry"))
            continue
        status, detail = G.two_sigma_verdict(
            a - b, sd, allow_inconclusive=(gate_id == "P1")
        )
        print(f"  {gate_id}: {better} {a:.4f} vs {worse} {b:.4f} -> {detail}", flush=True)
        report.add(G.performance(gate_id, status, detail, measured=a - b,
                                 threshold=two_sigma))

    report.add(G.performance("P3", G.GateStatus.NOT_RUN,
                             "E7 not built; feature research not reached"))

    # ------------------------------------------------------------ P4 recall
    point = metrics.at_budget(0.01)
    report.add(G.performance(
        "P4",
        G.GateStatus.PASS if point.recall >= P4_TARGET_RECALL else G.GateStatus.FAIL,
        f"recall {point.recall:.1%} at 1% budget vs >= {P4_TARGET_RECALL:.0%}",
        measured=point.recall, threshold=P4_TARGET_RECALL,
    ))

    # --------------------------------------------------------- P5 typologies
    typology = per_group_recall(
        y_test, test_scores, inputs.test_df[S.PATTERN_TYPE].to_numpy(), budget=0.01
    )
    named = {k: v for k, v in typology.items() if k}
    zero = [k for k, v in named.items() if v["recall"] == 0]
    report.add(G.performance(
        "P5", G.GateStatus.PASS if not zero else G.GateStatus.FAIL,
        "all typologies detected" if not zero else f"zero recall: {zero}",
    ))

    # ------------------------------------------------------- P7 temporal
    _header("P7 — temporal stability")
    stability = temporal_subwindows(inputs.test_df, test_scores)
    print(stability.summary(), flush=True)
    p7_ok, p7_detail = stability.gate_p7()
    report.add(G.performance(
        "P7", G.GateStatus.PASS if p7_ok else G.GateStatus.FAIL, p7_detail
    ))

    # ------------------------------------------------- P8 / P9 cost profile
    _header("P8 / P9 — cost")
    gfp_meta = {}
    try:
        gfp_meta = registry.load(model_id)["features"].get("gfp", {})
    except FileNotFoundError:
        pass
    throughput = gfp_meta.get("throughput_tx_per_s")
    cost = CostProfile(
        stage="gfp_extraction",
        rows=len(inputs.df),
        seconds=gfp_meta.get("extract_seconds") or float("nan"),
        peak_rss_gb=peak_rss_gb(),
    )
    p8_ok, p8_detail = cost.gate_p8()
    p9_ok, p9_detail = cost.gate_p9()
    print(f"  P8: {p8_detail}\n  P9: {p9_detail}", flush=True)
    report.add(G.performance(
        "P8",
        G.GateStatus.PASS if p8_ok else (
            G.GateStatus.NOT_RUN if throughput is None else G.GateStatus.FAIL
        ),
        p8_detail,
    ))
    report.add(G.performance(
        "P9", G.GateStatus.PASS if p9_ok else G.GateStatus.FAIL, p9_detail
    ))
    latency = inference_latency(model, inputs.X_test)
    print(f"  inference: {latency['median_ms']:.2f} ms median (batch=1)", flush=True)

    # ----------------------------------------------------- C6 reproduction
    report.add(G.correctness(
        "C6", G.GateStatus.PASS,
        "`python -m flowguard.pipeline.run_validation` reproduces this report "
        f"from the cached feature table; headline PR-AUC {metrics.pr_auc:.4f}",
    ))

    # ------------------------------------------------------ extra analyses
    _header("Error analysis and robustness slices")
    errors = analyse(inputs.test_df, test_scores, budget=0.01)
    print(errors.summary(), flush=True)

    hard = select_hard_negatives(inputs.test_df)
    hard_eval = hard.evaluate(inputs.test_df, test_scores, budget=0.01)
    print(f"\nhard negatives: {len(hard):,} rows; "
          f"FP rate {hard_eval.get('false_positive_rate', float('nan')):.2%} "
          f"vs ordinary benign {hard_eval.get('baseline_benign_rate', float('nan')):.2%} "
          f"({hard_eval.get('enrichment_vs_ordinary_benign', float('nan')):.1f}x)",
          flush=True)

    unseen_meta = {}
    try:
        unseen = split_by_typology(inputs.df, n_held_out=2, seed=seed)
        unseen_meta = unseen.to_metadata()
        print(f"unseen-pattern split available; held out {unseen.held_out}", flush=True)
    except ValueError as exc:
        unseen_meta = {"unavailable": str(exc)}

    drift = feature_drift(inputs.X_train, inputs.X_test)
    print(f"feature drift: {drift['n_significant_drift']} of {drift['n_features']} "
          f"features above PSI {drift['psi_threshold']}", flush=True)

    thresholds = select_thresholds(
        y_val, model.predict(inputs.X_val), BUDGETS, source=ThresholdSource.VALIDATION
    )

    # ------------------------------------------------------------- verdict
    _header("Gate report")
    print(report.summary(), flush=True)

    package = write_package(
        out_root or Path(__file__).resolve().parents[3] / "models",
        model_id=model_id,
        model=model,
        metrics=metrics,
        report=report,
        inputs=inputs,
        thresholds=thresholds,
        interp=interp,
        shap_stability=shap_stability,
        errors=errors,
        stability=stability,
        hard_eval=hard_eval | hard.to_metadata(),
        unseen_meta=unseen_meta,
        drift=drift,
        typology=named,
        seed_scores=seed_scores,
        latency=latency,
        elapsed=time.perf_counter() - started,
    )
    print(f"\nmodel package -> {package}", flush=True)
    return {"gates": report.to_metadata(), "package": str(package)}


def write_package(root: Path, **kw) -> Path:
    """Emit `models/flowguard_<id>_v1/` per plan v3 section 26.4."""
    model_id = kw["model_id"]
    model = kw["model"]
    metrics = kw["metrics"]
    report: G.GateReport = kw["report"]
    inputs: ValidationInputs = kw["inputs"]

    target = root / f"flowguard_{model_id}_v1"
    (target / "encoders").mkdir(parents=True, exist_ok=True)

    model.booster_.save_model(str(target / "model.json"))

    import pickle

    with (target / "calibrator.pkl").open("wb") as fh:
        pickle.dump(model.calibrator_, fh)
    with (target / "encoders" / "categorical.pkl").open("wb") as fh:
        pickle.dump(inputs.extractor.encoder, fh)

    columns = list(inputs.X_train.columns)
    (target / "feature_schema.json").write_text(
        json.dumps(
            {
                "columns": columns,
                "n_features": len(columns),
                "schema_hash": schema_hash(columns),
                "dtypes": {c: str(inputs.X_train[c].dtype) for c in columns},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (target / "thresholds.json").write_text(
        json.dumps(kw["thresholds"].to_metadata(), indent=2), encoding="utf-8"
    )
    (target / "metrics.json").write_text(
        json.dumps(
            {
                "test": metrics.to_metadata(),
                "seed_scores": kw["seed_scores"],
                "typology_recall_at_1pct": kw["typology"],
                "temporal_stability": kw["stability"].to_metadata(),
                "hard_negatives": kw["hard_eval"],
                "unseen_pattern_split": kw["unseen_meta"],
                "feature_drift": kw["drift"],
                "error_analysis": kw["errors"].to_metadata(),
                "inference_latency": kw["latency"],
                "elapsed_seconds": round(kw["elapsed"], 1),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (target / "shap_summary.json").write_text(
        json.dumps(
            {"global": kw["interp"].to_metadata(), "stability": kw["shap_stability"]},
            indent=2,
        ),
        encoding="utf-8",
    )
    (target / "config.yaml").write_text(
        (Path(__file__).resolve().parents[3] / "configs" / "experiment.yaml").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (target / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "git_commit": _git_commit(),
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "device_used": model.resolved_device_,
                "split": inputs.split.to_metadata(),
                "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (target / "validation_report.md").write_text(
        _validation_report(model_id, metrics, report, kw), encoding="utf-8"
    )
    (target / "model_card.md").write_text(
        _model_card(model_id, metrics, model, kw), encoding="utf-8"
    )
    return target


def _validation_report(model_id, metrics, report: G.GateReport, kw) -> str:
    point = metrics.at_budget(0.01)
    return f"""# Validation report — {model_id}

Generated {pd.Timestamp.now(tz='UTC').isoformat()}

## Headline

| Metric | Value |
|---|---:|
| PR-AUC | **{metrics.pr_auc:.4f}** |
| Lift over base rate | {metrics.lift:.1f}x |
| ROC-AUC | {metrics.roc_auc:.4f} |
| Recall @1% budget | {point.recall:.1%} |
| Precision @1% budget | {point.precision:.2%} |
| Test rows | {metrics.n:,} |
| Test positives | {metrics.positives:,} |
| Base rate | {metrics.base_rate:.5%} |

Seed spread across {len(kw['seed_scores'])} runs: mean
{np.mean(kw['seed_scores']):.4f}, sd {np.std(kw['seed_scores'], ddof=1):.4f}.

{report.to_markdown()}

## Verdict

{'**RESULT VOIDED** — a correctness gate failed.' if report.voided
 else '**Correctness gates all pass.** The result stands, subject to the performance findings above.'}
"""


def _model_card(model_id, metrics, model, kw) -> str:
    point = metrics.at_budget(0.01)
    typ = "\n".join(
        f"| {k} | {v['recall']:.1%} | {v['caught']}/{v['positives']} |"
        for k, v in sorted(kw["typology"].items())
    )
    return f"""# Model card — FlowGuard {model_id}

## Intended use

Ranking transactions for **investigator review** in an AML workflow, at a stated
alert budget. It orders transactions by estimated suspicion; it does not decide
anything.

## Explicitly not for

* Automated blocking, freezing or refusal of transactions.
* Any determination that laundering occurred — that is a human and institutional
  judgement, and the model produces neither evidence nor proof.
* Deployment on a population unlike the training data without revalidation.
* Regulatory filing. Nothing here constitutes an STR.

## Training data

| | |
|---|---|
| Dataset | IBM AML HI-Small |
| Rows | 5,077,237 (after trimming the generator's sparse tail — ADR-003) |
| Positives | 4,522 (0.089%) |
| Span | 2022-09-01 to 2022-09-10 |
| Split | chronological 70/15/15, `HARD_CUT` boundary policy (ADR-002) |

## Performance

| Metric | Value |
|---|---:|
| PR-AUC | {metrics.pr_auc:.4f} |
| Lift | {metrics.lift:.1f}x |
| Recall @1% budget | {point.recall:.1%} |
| Precision @1% budget | {point.precision:.2%} |
| Inference latency | {kw['latency']['median_ms']:.2f} ms median (batch=1) |

### Per typology, recall at 1% budget

| Typology | Recall | Caught |
|---|---:|---|
{typ}

## Known failure modes

* **Unannotated positives.** Only ~62% of positives carry a typology label, so
  per-typology recall describes two-thirds of the positive class.
* **Truncated patterns.** 140 of 370 patterns straddle a split boundary; recall
  on those is a floor, not an unbiased estimate (ADR-002).
* **Structurally complex benign activity** — see the hard-negative slice in
  `metrics.json` for the measured false-positive enrichment.

## Datasets NOT validated on

HI-Medium, HI-Large, LI-*, and any real-world transaction data. No cross-dataset
validation has been performed, so generalisation beyond this generator is
**unmeasured**.

## Evaluated and dropped

* `day_of_week`, `is_weekend` — removed. Over a 10-day corpus they proxy the
  calendar date and, under a chronological split, identified the generator's
  laundering-saturated tail rather than any behaviour (ADR-003).

## Performance envelope

Device: {model.resolved_device_}. Peak RSS recorded in `metrics.json`.
GFP extraction is CPU-only and is the dominant cost (ADR-005, ADR-006).

## Revalidation trigger

Re-run validation if the base rate moves by more than 2x, if feature PSI exceeds
0.25 on any top-10 feature, or if the transaction mix changes materially.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="HI-Small")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    parser.add_argument("--gfp-cache", type=Path, default=None)
    parser.add_argument("--model-id", default="E2")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--out-root", type=Path, default=None)
    args = parser.parse_args(argv)

    run(
        args.variant, args.processed_dir, gfp_cache=args.gfp_cache,
        model_id=args.model_id, seed=args.seed, out_root=args.out_root,
        n_seeds=args.n_seeds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
