"""Gates, stability, hard negatives, unseen-pattern and tuning."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.evaluation import gates as G
from flowguard.evaluation.error_analysis import analyse, flag_at_budget
from flowguard.evaluation.stability import (
    population_stability_index,
    temporal_subwindows,
)
from flowguard.models.tuning import rolling_origin_folds, sample_params
from flowguard.splits.hard_negative import select_hard_negatives
from flowguard.splits.unseen_pattern import (
    annotation_coverage,
    available_typologies,
    split_by_typology,
)


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def test_correctness_failure_voids_the_report():
    report = G.GateReport()
    report.add(G.correctness("C1", G.GateStatus.PASS))
    report.add(G.performance("P4", G.GateStatus.FAIL, "recall short"))
    assert not report.voided, "a performance failure must not void the result"

    report.add(G.correctness("C8", G.GateStatus.FAIL, "one feature dominates"))
    assert report.voided


def test_two_sigma_verdict_distinguishes_real_from_noise():
    sigma = 0.0017
    assert G.two_sigma_verdict(0.010, sigma)[0] is G.GateStatus.PASS
    assert G.two_sigma_verdict(0.001, sigma)[0] is G.GateStatus.FAIL
    status, detail = G.two_sigma_verdict(0.001, sigma, allow_inconclusive=True)
    assert status is G.GateStatus.INCONCLUSIVE
    assert "within 2 sigma" in detail


def test_gate_report_renders_markdown():
    report = G.GateReport()
    report.add(G.correctness("C2", G.GateStatus.PASS, "at base rate"))
    report.add(G.performance("P6", G.GateStatus.PASS, "sd 0.002"))
    md = report.to_markdown()
    assert "## Correctness gates" in md and "C2" in md and "P6" in md


# --------------------------------------------------------------------------
# stability
# --------------------------------------------------------------------------


def test_monotone_decline_fails_p7(transactions):
    """A model decaying across the test period has a shelf life; P7 says so."""
    ts = transactions[S.TIMESTAMP]
    span = (ts - ts.min()).dt.total_seconds().to_numpy()
    # Score well early, badly late, so recall decays monotonically.
    y = transactions[S.IS_LAUNDERING].to_numpy()
    decay = 1 - span / span.max()
    scores = np.where(y == 1, decay, 0.0)

    stability = temporal_subwindows(transactions, scores, n_windows=5)
    if len(stability.scores) < 3:
        pytest.skip("fixture produced too few evaluable sub-windows")
    assert stability.is_monotone_decline
    assert stability.gate_p7()[0] is False


def test_stable_scores_pass_p7(transactions):
    rng = np.random.default_rng(0)
    stability = temporal_subwindows(
        transactions, rng.random(len(transactions)), n_windows=5
    )
    assert stability.gate_p7()[0] is True


def test_psi_is_zero_for_identical_distributions():
    rng = np.random.default_rng(0)
    x = rng.normal(size=5000)
    assert population_stability_index(x, x) == pytest.approx(0.0, abs=1e-9)


def test_psi_detects_a_shift():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 5000)
    b = rng.normal(2, 1, 5000)
    assert population_stability_index(a, b) > 0.25


# --------------------------------------------------------------------------
# error analysis
# --------------------------------------------------------------------------


def test_flag_at_budget_selects_the_right_volume():
    scores = np.linspace(0, 1, 1000)
    assert flag_at_budget(scores, 0.01).sum() == 10


def test_error_analysis_counts_partition_the_test_set(transactions):
    rng = np.random.default_rng(0)
    scores = rng.random(len(transactions))
    result = analyse(transactions, scores, budget=0.05)

    total = (result.true_positives + result.false_positives
             + result.false_negatives + result.true_negatives)
    assert total == len(transactions)
    assert "typology" in result.slices


def test_error_analysis_reports_position_within_pattern(transactions):
    scores = np.random.default_rng(0).random(len(transactions))
    result = analyse(transactions, scores, budget=0.05)
    # Early hops have less history to detect; that slice must exist.
    assert "pattern_position" in result.slices


# --------------------------------------------------------------------------
# hard negatives
# --------------------------------------------------------------------------


def test_hard_negatives_contain_no_positives(transactions):
    hard = select_hard_negatives(transactions)
    assert transactions.loc[hard.index, S.IS_LAUNDERING].sum() == 0


def test_hard_negative_slice_is_a_subset_not_the_population(transactions):
    hard = select_hard_negatives(transactions)
    benign = int((transactions[S.IS_LAUNDERING] == 0).sum())
    assert 0 <= len(hard) < benign


def test_hard_negative_evaluation_reports_enrichment(transactions):
    hard = select_hard_negatives(transactions)
    if len(hard) == 0:
        pytest.skip("fixture produced no structurally complex benign accounts")
    scores = np.random.default_rng(0).random(len(transactions))
    out = hard.evaluate(transactions, scores, budget=0.05)
    assert out["n"] > 0
    assert 0.0 <= out["false_positive_rate"] <= 1.0


# --------------------------------------------------------------------------
# unseen pattern
# --------------------------------------------------------------------------


def test_held_out_typologies_never_appear_in_training(transactions):
    split = split_by_typology(transactions, n_held_out=2)
    train, test = split.apply(transactions)

    train_types = set(train[S.PATTERN_TYPE].dropna())
    assert not (train_types & set(split.held_out)), (
        "a held-out typology leaked into the training side"
    )


def test_unseen_split_reports_its_annotation_coverage(transactions):
    split = split_by_typology(transactions, n_held_out=1)
    assert 0.0 <= split.coverage <= 1.0
    assert any("typology annotation" in n for n in split.notes)
    assert any("not chronological" in n for n in split.notes)


def test_unseen_split_requires_annotations(unlabelled_patterns):
    with pytest.raises(ValueError, match="no pattern_type annotations"):
        split_by_typology(unlabelled_patterns)


def test_cannot_hold_out_every_typology(transactions):
    everything = available_typologies(transactions)
    with pytest.raises(ValueError, match="cannot hold out every typology"):
        split_by_typology(transactions, held_out=everything)


def test_annotation_coverage_matches_the_data(transactions):
    positives = transactions[transactions[S.IS_LAUNDERING] == 1]
    expected = positives[S.PATTERN_TYPE].notna().mean()
    assert annotation_coverage(transactions) == pytest.approx(expected)


# --------------------------------------------------------------------------
# tuning
# --------------------------------------------------------------------------


def test_search_budget_is_respected():
    space = {"max_depth": [3, 4, 5, 6], "learning_rate": [0.05, 0.1]}
    assert len(list(sample_params(space, 5, seed=0))) == 5


def test_search_samples_are_distinct_and_deterministic():
    space = {"max_depth": [3, 4, 5, 6], "learning_rate": [0.05, 0.1, 0.2]}
    a = list(sample_params(space, 6, seed=1))
    b = list(sample_params(space, 6, seed=1))
    assert a == b
    assert len({tuple(sorted(d.items())) for d in a}) == len(a)


def test_rolling_origin_rejects_impossible_fold_counts(transactions):
    with pytest.raises(ValueError):
        rolling_origin_folds(transactions.head(3), n_folds=5)
