"""Merge-blocking leakage tests (plan v3 section 11).

These are a first-class category, not assertions buried in a notebook. A failure
here means every downstream number is invalid, so they run before model code
exists and stay in CI forever.

Covered from the v3 section 11 table (the rest arrive with the components they
test -- extractors, encoders, thresholds):

    test_split_boundaries_ordered   -> test_boundaries_strictly_ordered
    test_extractor_label_blind      -> test_extractor_rejects_*
    test_deterministic_split        -> test_split_is_deterministic
"""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.schema import LabelLeakageError
from flowguard.features.base import FeatureExtractor
from flowguard.splits.temporal import (
    BoundaryPolicy,
    SplitSpec,
    chronological_split,
)

pytestmark = pytest.mark.leakage

# Policies that guarantee strict chronological separation. PATTERN_START is
# excluded by design: it moves a pattern's later rows back to the split holding
# its first transaction, which blurs the boundary on purpose.
ORDERED_POLICIES = [BoundaryPolicy.PURGE, BoundaryPolicy.HARD_CUT]


class _Echo(FeatureExtractor):
    """Minimal extractor used to prove the label gate fires."""

    family = "probe"

    def _extract(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"amount_log": tx_view[S.AMOUNT]}, index=tx_view.index)


# --------------------------------------------------------------------------
# Split ordering
# --------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ORDERED_POLICIES)
def test_boundaries_strictly_ordered(transactions, policy):
    """max(train) < min(val) and max(val) < min(test). The core invariant."""
    split = chronological_split(transactions, SplitSpec(boundary_policy=policy))
    train, val, test = split.apply(transactions)

    assert not train.empty and not val.empty and not test.empty

    assert train[S.TIMESTAMP].max() < val[S.TIMESTAMP].min()
    assert val[S.TIMESTAMP].max() < test[S.TIMESTAMP].min()


@pytest.mark.parametrize("policy", list(BoundaryPolicy))
def test_partitions_are_disjoint_and_complete(transactions, policy):
    """No row appears twice, and only purge may drop rows."""
    split = chronological_split(transactions, SplitSpec(boundary_policy=policy))

    combined = split.train_idx.append(split.val_idx).append(split.test_idx)
    assert combined.is_unique, "a row landed in more than one partition"

    dropped = len(transactions) - len(combined)
    assert dropped == split.purged_rows
    if policy is not BoundaryPolicy.PURGE:
        assert dropped == 0, "only PURGE may discard rows"


def test_identical_timestamps_never_span_a_boundary():
    """A single instant must not be split across partitions.

    Constructed adversarially: a coarse timestamp grid with heavy ties, which is
    what a naive positional quantile gets wrong.
    """
    from tests.conftest import make_transactions

    df = make_transactions(n=300)
    # Collapse onto a 6-value day grid: 50 rows share each instant, so a
    # positional 70% boundary lands mid-run.
    df[S.TIMESTAMP] = pd.Timestamp("2026-01-01T00:00:00Z") + pd.to_timedelta(
        [i // 50 for i in range(len(df))], unit="D"
    )

    split = chronological_split(
        df, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
    )
    train, val, test = split.apply(df)

    for earlier, later in ((train, val), (val, test)):
        if earlier.empty or later.empty:
            continue
        overlap = set(earlier[S.TIMESTAMP]) & set(later[S.TIMESTAMP])
        assert not overlap, f"instant(s) {overlap} span a boundary"


def test_split_is_deterministic(transactions):
    """Same config and data produce identical boundaries."""
    a = chronological_split(transactions, SplitSpec())
    b = chronological_split(transactions, SplitSpec())

    assert a.train_end == b.train_end
    assert a.val_end == b.val_end
    assert a.train_idx.equals(b.train_idx)
    assert a.val_idx.equals(b.val_idx)
    assert a.test_idx.equals(b.test_idx)


def test_no_shuffling_occurs(transactions):
    """Every train timestamp precedes every test timestamp -- no random mixing."""
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
    )
    train, _, test = split.apply(transactions)
    assert train[S.TIMESTAMP].max() < test[S.TIMESTAMP].min()


# --------------------------------------------------------------------------
# Label isolation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("forbidden", sorted(S.FORBIDDEN_IN_FEATURES))
def test_extractor_rejects_forbidden_column(transactions, forbidden):
    """No extractor may observe an evaluation-only column."""
    tx_view = S.feature_view(transactions)
    tx_view[forbidden] = transactions[forbidden]

    with pytest.raises(LabelLeakageError, match=forbidden):
        _Echo().run(tx_view)


def test_extractor_accepts_clean_view(transactions):
    out = _Echo().run(S.feature_view(transactions))
    assert list(out.columns) == ["probe_amount_log"]
    assert len(out) == len(transactions)


def test_feature_view_strips_every_forbidden_column(transactions):
    view = S.feature_view(transactions)
    assert not S.FORBIDDEN_IN_FEATURES & set(view.columns)
    S.assert_label_blind(view)


def test_edge_payload_carries_no_label():
    """Graph edges must not carry ground truth (plan v3 section 6.3)."""
    assert not S.FORBIDDEN_IN_FEATURES & set(S.EDGE_PAYLOAD)


def test_label_view_is_joinable(transactions):
    labels = S.label_view(transactions)
    assert S.TRANSACTION_ID in labels.columns
    assert labels[S.TRANSACTION_ID].is_unique
