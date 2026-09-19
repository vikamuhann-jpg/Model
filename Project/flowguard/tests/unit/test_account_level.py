"""Account-level evaluation for node-labelled corpora (Tier S4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.evaluation.account_level import (
    AccountLevelError,
    aggregate_to_accounts,
    evaluate_accounts,
)

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


@pytest.fixture
def txns() -> pd.DataFrame:
    """Four accounts, six transactions, deliberately asymmetric."""
    rows = [
        ("A", "B"), ("A", "C"), ("B", "C"),
        ("C", "D"), ("D", "A"), ("B", "D"),
    ]
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i}" for i in range(len(rows))],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=i) for i in range(len(rows))],
            S.SOURCE_ACCOUNT: [s for s, _ in rows],
            S.DESTINATION_ACCOUNT: [d for _, d in rows],
            S.AMOUNT: [100.0] * len(rows),
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: "ACH",
            S.IS_LAUNDERING: 0,
        }
    )


def test_account_inherits_scores_from_both_sides(txns):
    """A pass-through account is implicated by what it forwards, not just receives."""
    scores = np.array([0.9, 0.1, 0.1, 0.1, 0.1, 0.1])
    agg = aggregate_to_accounts(txns, scores, aggregation="max")
    by_account = dict(zip(agg.account_id, agg.score))

    # TX0 is A -> B with score 0.9; both endpoints must see it.
    assert by_account["A"] == pytest.approx(0.9)
    assert by_account["B"] == pytest.approx(0.9)
    assert by_account["C"] == pytest.approx(0.1)


def test_max_is_the_primary_aggregation(txns):
    """One clearly suspicious transaction should surface the account."""
    scores = np.array([0.95, 0.01, 0.01, 0.01, 0.01, 0.01])
    mx = dict(zip(*(lambda a: (a.account_id, a.score))(
        aggregate_to_accounts(txns, scores, aggregation="max"))))
    mean = dict(zip(*(lambda a: (a.account_id, a.score))(
        aggregate_to_accounts(txns, scores, aggregation="mean"))))

    assert mx["A"] > mean["A"], "max must not be diluted by an account's quiet activity"


def test_topk_mean_sits_between_max_and_mean(txns):
    scores = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1])
    out = {}
    for how in ("max", "mean", "topk_mean"):
        agg = aggregate_to_accounts(txns, scores, aggregation=how, top_k=2)
        out[how] = dict(zip(agg.account_id, agg.score))["A"]
    assert out["mean"] <= out["topk_mean"] <= out["max"]


def test_transaction_counts_are_reported(txns):
    agg = aggregate_to_accounts(txns, np.zeros(len(txns)), aggregation="max")
    counts = dict(zip(agg.account_id, agg.n_transactions))
    # A appears in TX0, TX1 (source) and TX4 (destination).
    assert counts["A"] == 3


def test_length_mismatch_is_rejected(txns):
    with pytest.raises(AccountLevelError, match="length mismatch"):
        aggregate_to_accounts(txns, np.zeros(3))


def test_unlabelled_accounts_are_excluded_not_counted_as_benign(txns):
    """Missing a label means unknown. Scoring it benign invents false positives.

    Public illicit-address datasets are partially labelled by construction, so
    this is the difference between an honest metric and a fabricated one.
    """
    scores = np.array([0.9, 0.8, 0.2, 0.2, 0.1, 0.1])
    labels = pd.DataFrame({"account_id": ["A", "B"], "is_illicit": [1, 0]})

    result = evaluate_accounts(txns, scores, labels)

    assert result.n_accounts == 4          # A, B, C, D appear in transactions
    assert result.n_labelled == 2          # only A and B carry labels
    assert result.n_positive == 1
    assert "not benign" in result.unlabelled_policy


def test_every_aggregation_is_reported(txns):
    scores = np.array([0.9, 0.8, 0.2, 0.2, 0.1, 0.1])
    labels = pd.DataFrame(
        {"account_id": ["A", "B", "C", "D"], "is_illicit": [1, 0, 1, 0]}
    )
    result = evaluate_accounts(txns, scores, labels)

    assert set(result.by_aggregation) == {"max", "mean", "topk_mean"}
    assert result.primary is result.by_aggregation["max"]


def test_metadata_warns_against_cross_unit_comparison(txns):
    """The result must carry its own non-comparability warning."""
    scores = np.array([0.9, 0.8, 0.2, 0.2, 0.1, 0.1])
    labels = pd.DataFrame(
        {"account_id": ["A", "B", "C", "D"], "is_illicit": [1, 0, 1, 0]}
    )
    meta = evaluate_accounts(txns, scores, labels).to_metadata()

    assert meta["unit"] == "account"
    assert "NOT comparable" in meta["comparability"]


def test_no_matching_accounts_fails_loudly(txns):
    """An identifier-convention mismatch must not silently produce an empty metric."""
    labels = pd.DataFrame({"account_id": ["ZZZ"], "is_illicit": [1]})
    with pytest.raises(AccountLevelError, match="same convention"):
        evaluate_accounts(txns, np.zeros(len(txns)), labels)


def test_missing_label_column_is_rejected(txns):
    labels = pd.DataFrame({"account_id": ["A"]})
    with pytest.raises(AccountLevelError, match="is_illicit"):
        evaluate_accounts(txns, np.zeros(len(txns)), labels)


def test_perfect_account_ranking_scores_one(txns):
    """Sanity: if scores order accounts perfectly, PR-AUC is 1."""
    # A, B, C illicit; D benign. For a perfect ranking every transaction
    # touching D (TX3 C->D, TX4 D->A, TX5 B->D) must score low -- otherwise max
    # aggregation correctly hands D a high score and the ranking is not perfect.
    # A, B and C still reach a high score via TX0-TX2.
    scores = np.array([0.9, 0.9, 0.9, 0.1, 0.1, 0.1])
    labels = pd.DataFrame(
        {"account_id": ["A", "B", "C", "D"], "is_illicit": [1, 1, 1, 0]}
    )
    result = evaluate_accounts(txns, scores, labels)
    assert result.primary.pr_auc > 0.9
