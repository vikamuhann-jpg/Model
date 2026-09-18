"""Evaluation metrics and sanity baselines."""

from __future__ import annotations

import numpy as np
import pytest

from flowguard.evaluation.metrics import evaluate, per_group_recall
from flowguard.evaluation.sanity import run_null_baselines, shuffled_label_test


@pytest.fixture
def imbalanced():
    """1,000 rows at a 1% base rate, mirroring the real class balance."""
    rng = np.random.default_rng(0)
    y = np.zeros(1000, dtype=int)
    y[:10] = 1
    rng.shuffle(y)
    return y


def test_perfect_scores_give_pr_auc_one(imbalanced):
    metrics = evaluate(imbalanced, imbalanced.astype(float))
    assert metrics.pr_auc == pytest.approx(1.0)
    assert metrics.positives == 10


def test_random_scores_land_near_base_rate(imbalanced):
    rng = np.random.default_rng(1)
    metrics = evaluate(imbalanced, rng.random(len(imbalanced)))
    assert metrics.pr_auc < 0.05
    assert metrics.base_rate == pytest.approx(0.01)


def test_lift_is_relative_to_base_rate(imbalanced):
    metrics = evaluate(imbalanced, imbalanced.astype(float))
    assert metrics.lift == pytest.approx(100.0)


def test_budget_point_alerts_match_the_budget(imbalanced):
    metrics = evaluate(imbalanced, np.arange(len(imbalanced), dtype=float))
    point = metrics.at_budget(0.01)
    assert point.alerts == 10
    assert 0.0 <= point.precision <= 1.0
    assert 0.0 <= point.recall <= 1.0


def test_perfect_ranking_catches_everything_within_budget(imbalanced):
    # Score = label, so all positives rank first.
    metrics = evaluate(imbalanced, imbalanced.astype(float))
    assert metrics.at_budget(0.01).recall == pytest.approx(1.0)


def test_degenerate_single_class_does_not_raise():
    y = np.zeros(100, dtype=int)
    metrics = evaluate(y, np.random.default_rng(0).random(100))
    assert np.isnan(metrics.pr_auc)
    assert metrics.budgets == []


def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError, match="length mismatch"):
        evaluate(np.zeros(10), np.zeros(5))


def test_null_baselines_pass_on_clean_data(imbalanced):
    for result in run_null_baselines(imbalanced):
        assert result.passed, f"{result.name} should sit at the base rate"


def test_shuffled_label_test_passes_when_there_is_no_leak(imbalanced):
    """A model that cannot see the label must collapse to the base rate."""
    rng = np.random.default_rng(3)
    import pandas as pd

    X = pd.DataFrame({"noise": rng.random(len(imbalanced))})

    def fit_predict(xt, yt, xs):
        return rng.random(len(xs))

    result = shuffled_label_test(fit_predict, X, imbalanced, X, imbalanced)
    assert result.passed


def test_shuffled_label_test_catches_a_deliberate_leak(imbalanced):
    """If the 'model' can see the true label, the test must fail."""
    import pandas as pd

    X = pd.DataFrame({"leak": imbalanced.astype(float)})

    def leaky_fit_predict(xt, yt, xs):
        return xs["leak"].to_numpy()  # ignores yt, reads the label directly

    result = shuffled_label_test(leaky_fit_predict, X, imbalanced, X, imbalanced)
    assert not result.passed, "the shuffled-label test failed to detect a leak"


def test_per_group_recall_handles_unlabelled_rows(imbalanced):
    groups = np.array(["CYCLE" if v else None for v in imbalanced], dtype=object)
    out = per_group_recall(imbalanced, imbalanced.astype(float), groups, budget=0.01)
    assert out["CYCLE"]["positives"] == 10
    assert out["CYCLE"]["recall"] == pytest.approx(1.0)
