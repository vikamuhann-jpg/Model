"""Two-tier scoring (FR-12).

The property the recall gate turns on: below the routing share K, the cascade's
alerts are exactly tier 1's alerts. If a transaction tier 0 rejected could climb
back above one it accepted, the cascade would be a score blend rather than a
filter, and the recall measurement would not mean what it says.
"""

from __future__ import annotations

import numpy as np
import pytest

from flowguard.features.cascade import CascadeError, cascade, combine, select

RNG = np.random.default_rng(0)


def test_select_takes_the_top_share():
    scores = np.arange(100, dtype=float)
    mask = select(scores, k=0.05)
    assert mask.sum() == 5
    assert set(np.flatnonzero(mask)) == {95, 96, 97, 98, 99}


def test_select_always_keeps_at_least_one():
    assert select(np.arange(10, dtype=float), k=0.001).sum() == 1


@pytest.mark.parametrize("k", [-0.1, 0.0, 1.5])
def test_invalid_k_is_rejected(k):
    with pytest.raises(CascadeError, match="k must be"):
        select(np.arange(10, dtype=float), k=k)


def test_rejected_rows_never_outrank_accepted_rows():
    """The central property: tier 0 is a filter, not a competing opinion."""
    tier0 = RNG.random(1000)
    tier1 = RNG.random(1000)
    result = cascade(tier0, tier1, k=0.05)
    assert result.scores[result.selected].min() >= result.scores[~result.selected].max()


def test_alerts_below_k_come_only_from_tier_one():
    tier0 = RNG.random(10_000)
    tier1 = RNG.random(10_000)
    result = cascade(tier0, tier1, k=0.05)
    budget = int(0.01 * len(tier0))
    alerts = np.argsort(-result.scores)[:budget]
    assert result.selected[alerts].all()


def test_selected_rows_are_ordered_by_tier_one():
    tier0 = np.arange(100, dtype=float)
    tier1 = np.arange(100, dtype=float)[::-1].copy()
    result = cascade(tier0, tier1, k=0.1)
    chosen = np.flatnonzero(result.selected)
    best_by_tier1 = chosen[np.argmax(tier1[chosen])]
    assert result.scores[best_by_tier1] == result.scores[result.selected].max()


def test_tier1_values_outside_the_mask_are_ignored():
    """A caller that never computed tier 1 for rejected rows may pass anything."""
    tier0 = np.arange(100, dtype=float)
    mask = select(tier0, k=0.1)
    clean = np.where(mask, 5.0, 0.0)
    junk = np.where(mask, 5.0, np.nan)
    assert np.array_equal(
        combine(tier0, clean, mask).scores, combine(tier0, junk, mask).scores
    )


def test_length_mismatch_is_rejected():
    with pytest.raises(CascadeError, match="same length"):
        combine(np.zeros(5), np.zeros(4), np.zeros(5, dtype=bool))


def test_throughput_is_the_sequential_cost_of_both_tiers():
    result = cascade(
        RNG.random(100), RNG.random(100), k=0.05, tier0_rate=50_000, tier1_rate=450
    )
    # 1 / (1/50000 + 0.05/450) = 7,627 tx/s -- comfortably past the 1,000 gate
    assert result.end_to_end_rate == pytest.approx(7627, rel=0.01)
    assert result.end_to_end_rate >= 1000


def test_throughput_is_none_without_measured_rates():
    assert cascade(RNG.random(10), RNG.random(10)).end_to_end_rate is None


def test_a_full_cascade_is_just_tier_one():
    """K=1 routes everything, so the ranking must be tier 1's ranking."""
    tier0 = RNG.random(200)
    tier1 = RNG.random(200)
    result = cascade(tier0, tier1, k=1.0)
    assert result.selected.all()
    assert np.array_equal(np.argsort(result.scores), np.argsort(tier1))


def test_perfect_tier0_filter_loses_no_positives():
    """Sanity: when tier 0 ranks positives first, the cascade keeps them all."""
    y = np.zeros(1000, dtype=int)
    y[:20] = 1
    tier0 = np.where(y == 1, 0.99, RNG.random(1000) * 0.5)
    tier1 = RNG.random(1000)
    result = cascade(tier0, tier1, k=0.05)
    assert result.selected[y == 1].all()
