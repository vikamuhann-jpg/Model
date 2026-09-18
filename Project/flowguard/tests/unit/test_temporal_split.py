"""Behaviour of the chronological splitter beyond the leakage invariants."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.splits.temporal import (
    BoundaryPolicy,
    SplitError,
    SplitSpec,
    chronological_split,
)


def test_default_proportions_are_roughly_70_15_15(transactions):
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
    )
    n = len(transactions)
    assert split.sizes["train"] / n == pytest.approx(0.70, abs=0.02)
    assert split.sizes["val"] / n == pytest.approx(0.15, abs=0.02)
    assert split.sizes["test"] / n == pytest.approx(0.15, abs=0.02)


def test_spanning_patterns_are_counted(transactions):
    """The plan requires reporting affected patterns whatever the policy."""
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
    )
    assert split.patterns_spanning_boundary >= 0
    assert any("hard cut" in note for note in split.notes)


def test_purge_drops_rows_around_boundaries(transactions):
    split = chronological_split(
        transactions,
        SplitSpec(
            boundary_policy=BoundaryPolicy.PURGE,
            purge_buffer=pd.Timedelta(minutes=30),
        ),
    )
    assert split.purged_rows > 0
    assert len(split.train_idx) + len(split.val_idx) + len(split.test_idx) == (
        len(transactions) - split.purged_rows
    )


def test_purge_buffer_is_derived_from_longest_pattern(transactions):
    """With no explicit buffer, purge sizes itself from observed pattern spans."""
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.PURGE)
    )
    assert split.purged_rows > 0
    assert any("purge buffer" in note for note in split.notes)


def test_purge_without_pattern_columns_fails_loudly(unlabelled_patterns):
    """Cannot silently guess a buffer when no pattern annotation exists."""
    with pytest.raises(SplitError, match="purge_buffer could not be derived"):
        chronological_split(
            unlabelled_patterns, SplitSpec(boundary_policy=BoundaryPolicy.PURGE)
        )


def test_hard_cut_works_without_pattern_columns(unlabelled_patterns):
    split = chronological_split(
        unlabelled_patterns, SplitSpec(boundary_policy=BoundaryPolicy.HARD_CUT)
    )
    assert split.patterns_spanning_boundary == 0
    assert any("could not be counted" in note for note in split.notes)


def test_pattern_start_keeps_each_pattern_whole(transactions):
    """Under PATTERN_START no pattern instance may be split across partitions."""
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.PATTERN_START)
    )
    train, val, test = split.apply(transactions)

    for name, part in (("train", train), ("val", val), ("test", test)):
        part_patterns = set(part[S.SCENARIO_ID].dropna())
        others = set()
        for other_name, other in (("train", train), ("val", val), ("test", test)):
            if other_name != name:
                others |= set(other[S.SCENARIO_ID].dropna())
        assert not (part_patterns & others), (
            f"pattern(s) {part_patterns & others} appear in {name} and elsewhere"
        )


def test_pattern_start_documents_its_blurred_boundary(transactions):
    split = chronological_split(
        transactions, SplitSpec(boundary_policy=BoundaryPolicy.PATTERN_START)
    )
    assert any("NOT guaranteed" in note for note in split.notes)


def test_metadata_is_registry_ready(transactions):
    split = chronological_split(transactions, SplitSpec())
    meta = split.to_metadata()

    assert meta["spec"]["boundary_policy"] == "purge"
    assert meta["spec"]["seed"] == 42
    assert set(meta["sizes"]) == {"train", "val", "test"}
    pd.Timestamp(meta["boundaries"]["train_end"])  # parses
    pd.Timestamp(meta["boundaries"]["val_end"])


def test_rejects_impossible_fractions():
    with pytest.raises(SplitError, match="leave room for test"):
        SplitSpec(train_frac=0.9, val_frac=0.2)


def test_rejects_tiny_frame(transactions):
    with pytest.raises(SplitError, match="at least 3 rows"):
        chronological_split(transactions.head(2), SplitSpec())


def test_rejects_frame_with_too_coarse_timestamps(transactions):
    """If every row shares one instant, no honest boundary exists."""
    df = transactions.copy()
    df[S.TIMESTAMP] = pd.Timestamp("2026-01-01T00:00:00Z")
    with pytest.raises(SplitError, match="boundaries collapsed"):
        chronological_split(df, SplitSpec())
