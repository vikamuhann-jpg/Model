"""Null baselines and the shuffled-label leak test (plan v3 section 14.1).

These run before any real model. They cost one training run each and are the
cheapest available evidence that the pipeline is measuring something real.

The shuffled-label test is the important one: train on labels that have been
randomly permuted, destroying any genuine signal. If the result still scores
meaningfully above the base rate, information about the label is reaching the
model through a path other than the label itself, and every downstream number
is fiction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from flowguard.evaluation.metrics import Metrics, evaluate


@dataclass(frozen=True)
class SanityResult:
    name: str
    metrics: Metrics
    passed: bool
    criterion: str

    def to_metadata(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "criterion": self.criterion,
            "metrics": self.metrics.to_metadata(),
        }


def random_scores(n: int, seed: int = 42) -> np.ndarray:
    return np.random.default_rng(seed).random(n)


def constant_scores(n: int) -> np.ndarray:
    return np.full(n, 0.5)


def run_null_baselines(
    y_true: np.ndarray, *, seed: int = 42, tolerance: float = 2.0
) -> list[SanityResult]:
    """Random and constant scorers. Both must land at the base rate.

    ``tolerance`` is the multiple of the base rate a null scorer may reach
    before it is treated as a failure (gate C3).
    """
    y_true = np.asarray(y_true).astype(int)
    n = len(y_true)
    base_rate = y_true.mean() if n else 0.0
    results = []

    for name, scores in (
        ("random", random_scores(n, seed)),
        ("constant", constant_scores(n)),
    ):
        metrics = evaluate(y_true, scores)
        ceiling = base_rate * tolerance
        passed = bool(np.isnan(metrics.pr_auc) or metrics.pr_auc <= ceiling)
        results.append(
            SanityResult(
                name=name,
                metrics=metrics,
                passed=passed,
                criterion=f"PR-AUC <= {tolerance}x base rate ({ceiling:.6f})",
            )
        )
    return results


def shuffled_label_test(
    fit_predict,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    *,
    seed: int = 42,
    tolerance: float = 2.0,
) -> SanityResult:
    """Train on permuted labels; the result must collapse to the base rate.

    Parameters
    ----------
    fit_predict
        Callable ``(X_train, y_train, X_test) -> scores``. Passing the real
        training routine is the point -- the test is only meaningful if it
        exercises the same code path the experiment uses.
    """
    rng = np.random.default_rng(seed)
    y_shuffled = np.asarray(y_train).copy()
    rng.shuffle(y_shuffled)

    scores = fit_predict(X_train, y_shuffled, X_test)
    metrics = evaluate(np.asarray(y_test).astype(int), scores)

    base_rate = np.asarray(y_test).astype(int).mean()
    ceiling = base_rate * tolerance
    passed = bool(np.isnan(metrics.pr_auc) or metrics.pr_auc <= ceiling)

    return SanityResult(
        name="shuffled_label",
        metrics=metrics,
        passed=passed,
        criterion=(
            f"PR-AUC <= {tolerance}x base rate ({ceiling:.6f}); "
            "a higher value means label information is leaking"
        ),
    )


def single_feature_baselines(
    X_test: pd.DataFrame, y_test: np.ndarray, *, top: int = 5
) -> list[SanityResult]:
    """Rank each feature used alone.

    A single raw feature scoring near the full model is a warning: either the
    problem is trivial, or that feature encodes the label.
    """
    y_test = np.asarray(y_test).astype(int)
    scored: list[SanityResult] = []

    for col in X_test.columns:
        values = pd.to_numeric(X_test[col], errors="coerce").to_numpy(dtype="float64")
        if not np.isfinite(values).any():
            continue
        values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        if values.std() == 0:
            continue
        metrics = evaluate(y_test, values)
        scored.append(
            SanityResult(
                name=f"single_feature:{col}",
                metrics=metrics,
                passed=True,  # informational; judged against the model, not alone
                criterion="informational -- compare against the trained model",
            )
        )

    scored.sort(key=lambda r: (np.nan_to_num(r.metrics.pr_auc, nan=-1)), reverse=True)
    return scored[:top]
