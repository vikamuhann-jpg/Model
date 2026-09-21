"""Fund tracing (FR-05), against the gates pre-registered in TRACK_P_PLAN.md.

P1-a  a known injected chain is recovered, and no out-of-order edge is admitted
P1-b  every traversal terminates under its bounds -- a property, not an example
P1-c  latency, exercised separately against the real corpus

The out-of-order property is the one worth stating plainly: a neighbour walk
that ignores timestamps builds paths where funds arrive after they left, and
presents them as a chain. Several tests below exist only to pin that down.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.graph.trace import (
    BACKWARD,
    FORWARD,
    TraceError,
    TraceIndex,
    TraceLimits,
    trace,
)

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(rows: list[tuple[str, str, float, int]]) -> pd.DataFrame:
    """rows: (source, destination, amount, minutes_after_base)."""
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:05d}" for i in range(len(rows))],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=m) for _, _, _, m in rows],
            S.SOURCE_ACCOUNT: [s for s, _, _, _ in rows],
            S.DESTINATION_ACCOUNT: [d for _, d, _, _ in rows],
            S.AMOUNT: [a for _, _, a, _ in rows],
            S.CURRENCY: "USD",
        }
    )


@pytest.fixture
def chain() -> pd.DataFrame:
    """A known layering chain A->B->C->D, buried in unrelated traffic.

    The decoys matter: NOISE1->B happens *before* the chain reaches B, and
    D->NOISE2 happens *before* the chain reaches D. A traversal that ignores
    time will pick both up and report a longer chain than exists.
    """
    return _frame(
        [
            ("A", "B", 1000.0, 10),
            ("B", "C", 900.0, 20),
            ("C", "D", 800.0, 30),
            ("NOISE1", "B", 55.0, 5),     # arrives before the chain does
            ("D", "NOISE2", 44.0, 15),    # leaves before the chain arrives
            ("X", "Y", 12.0, 12),         # unrelated entirely
        ]
    )


# ---------------------------------------------------------------- P1-a


def test_forward_trace_recovers_the_full_chain(chain):
    result = trace(chain, "A", direction=FORWARD, horizon=3)
    assert list(result.edges[S.TRANSACTION_ID]) == ["TX00000", "TX00001", "TX00002"]
    assert list(result.edges["depth"]) == [1, 2, 3]


def test_forward_trace_admits_no_out_of_order_edge(chain):
    """The core correctness property: time never runs backwards along a path."""
    result = trace(chain, "A", direction=FORWARD, horizon=3)
    times = pd.DatetimeIndex(result.edges[S.TIMESTAMP]).asi8
    assert (np.diff(times) >= 0).all()
    # D->NOISE2 precedes the chain's arrival at D, so it must not appear.
    assert "TX00004" not in set(result.edges[S.TRANSACTION_ID])


def test_backward_trace_recovers_the_chain_in_reverse(chain):
    result = trace(chain, "D", direction=BACKWARD, horizon=3)
    found = set(result.edges[S.TRANSACTION_ID])
    assert {"TX00000", "TX00001", "TX00002"} <= found
    # D->NOISE2 is downstream of D; walking back from D it is never upstream.
    assert "TX00004" not in found


def test_horizon_limits_depth(chain):
    result = trace(chain, "A", direction=FORWARD, horizon=2)
    assert list(result.edges[S.TRANSACTION_ID]) == ["TX00000", "TX00001"]
    assert result.edges["depth"].max() == 2


def test_terminals_are_where_the_money_stopped(chain):
    result = trace(chain, "A", direction=FORWARD, horizon=3)
    assert result.terminals == ["D"]


def test_anchor_time_excludes_earlier_movement(chain):
    """Anchoring after the chain starts must not pick up the earlier hop."""
    result = trace(
        chain, "A", direction=FORWARD, horizon=3, at=BASE + pd.Timedelta(minutes=15)
    )
    assert result.n_edges == 0


def test_per_hop_reports_observed_amounts(chain):
    hops = trace(chain, "A", direction=FORWARD, horizon=3).per_hop()
    assert list(hops["depth"]) == [1, 2, 3]
    assert list(hops["amount"]) == [1000.0, 900.0, 800.0]
    assert list(hops["n_transactions"]) == [1, 1, 1]


def test_a_cycle_is_traced_rather_than_looping_forever():
    """Round-tripping is a typology we want to see, not a bug to suppress."""
    cycle = _frame([("A", "B", 100.0, 1), ("B", "C", 100.0, 2), ("C", "A", 100.0, 3)])
    result = trace(cycle, "A", direction=FORWARD, horizon=5)
    assert result.n_edges == 3
    assert "A" in set(result.edges[S.DESTINATION_ACCOUNT])


# ---------------------------------------------------------------- P1-b


@pytest.mark.parametrize("fan", [5, 40, 200])
@pytest.mark.parametrize("cap", [1, 8, 64])
@pytest.mark.parametrize("horizon", [1, 3, 5])
def test_traversal_always_terminates_within_its_bounds(fan, cap, horizon):
    """P1-b as a property: over a hub, for any cap and horizon, bounds hold."""
    rows = [("HUB", f"P{i}", 10.0, i) for i in range(fan)]
    rows += [(f"P{i}", "SINK", 5.0, fan + i) for i in range(fan)]
    limits = TraceLimits(degree_cap=cap, edge_budget=500)
    result = trace(
        _frame(rows), "HUB", direction=FORWARD, horizon=horizon, limits=limits
    )

    assert result.n_edges <= limits.edge_budget
    # No vertex may contribute more than the cap at any one depth.
    per_vertex = result.edges.groupby(["depth", S.SOURCE_ACCOUNT]).size()
    assert per_vertex.max() <= cap
    assert result.edges["depth"].max() <= horizon


def test_degree_cap_is_reported_not_silent():
    rows = [("HUB", f"P{i}", 10.0, i) for i in range(100)]
    result = trace(_frame(rows), "HUB", horizon=1, limits=TraceLimits(degree_cap=10))
    assert result.n_edges == 10
    assert result.capped_vertices == ["HUB"]
    assert not result.is_complete
    assert "TRUNCATED" in result.summary()


def test_edge_budget_is_reported_not_silent():
    rows = [("HUB", f"P{i}", 10.0, i) for i in range(100)]
    result = trace(
        _frame(rows),
        "HUB",
        horizon=1,
        limits=TraceLimits(degree_cap=100, edge_budget=25),
    )
    assert result.n_edges == 25
    assert result.budget_exhausted
    assert not result.is_complete


def test_an_untruncated_trace_reports_itself_complete(chain):
    assert trace(chain, "A", horizon=3).is_complete


def test_max_gap_stops_the_walk_at_a_stale_hop():
    rows = [("A", "B", 100.0, 1), ("B", "C", 100.0, 60 * 24 * 40)]  # 40 days later
    result = trace(
        _frame(rows), "A", horizon=3, limits=TraceLimits(max_gap=pd.Timedelta(days=7))
    )
    assert list(result.edges[S.TRANSACTION_ID]) == ["TX00000"]


@pytest.mark.parametrize("unit", ["ns", "us", "ms", "s"])
def test_time_comparisons_survive_the_column_resolution(unit):
    """Regression: pandas 2 carries a resolution, and it broke max_gap.

    Reading epoch integers straight off the column yields microseconds on a
    ``datetime64[us]`` frame and nanoseconds on a ``datetime64[ns]`` one, while
    a scalar anchor is always nanoseconds. That mismatch scaled every gap
    comparison by a thousand and let a forty-day hop pass a seven-day limit --
    silently, with the traversal still returning plausible edges.
    """
    rows = [("A", "B", 100.0, 1), ("B", "C", 100.0, 60 * 24 * 40)]
    df = _frame(rows)
    df[S.TIMESTAMP] = df[S.TIMESTAMP].astype(f"datetime64[{unit}, UTC]")

    result = trace(
        df, "A", horizon=3, limits=TraceLimits(max_gap=pd.Timedelta(days=7))
    )
    assert list(result.edges[S.TRANSACTION_ID]) == ["TX00000"], (
        f"a 40-day hop cleared a 7-day gap limit at resolution {unit!r}"
    )


def test_a_naive_and_an_aware_corpus_trace_identically():
    """Timezone is converted, never discarded."""
    rows = [("A", "B", 100.0, 10), ("B", "C", 100.0, 20)]
    aware = _frame(rows)
    naive = aware.copy()
    naive[S.TIMESTAMP] = naive[S.TIMESTAMP].dt.tz_convert(None)

    assert list(trace(aware, "A", horizon=2).edges[S.TRANSACTION_ID]) == list(
        trace(naive, "A", horizon=2).edges[S.TRANSACTION_ID]
    )


def test_edges_keep_the_source_frame_index():
    """Regression: edges were renumbered 0..n-1, breaking joins back to features.

    Evidence bundles attach per-row SHAP values by this index. With the chain
    sitting after unrelated rows, a renumbered index points at the unrelated
    rows -- which is exactly how a published case carried the wrong reasons.
    """
    rows = [("X", "Y", 1.0, 1), ("P", "Q", 2.0, 2), ("R", "S", 3.0, 3)]  # decoys first
    rows += [("A", "B", 100.0, 10), ("B", "C", 90.0, 20)]
    df = _frame(rows)
    df.index = df.index + 1000  # a non-positional index, like a split slice

    result = trace(df, "A", horizon=2)
    assert list(result.edges.index) == [1003, 1004]
    assert (
        df.loc[result.edges.index, S.TRANSACTION_ID].tolist()
        == result.edges[S.TRANSACTION_ID].tolist()
    )


# ---------------------------------------------------------------- contracts


def test_unknown_account_is_rejected(chain):
    with pytest.raises(TraceError, match="does not appear"):
        trace(chain, "NOT_AN_ACCOUNT")


def test_bad_direction_is_rejected(chain):
    with pytest.raises(TraceError, match="direction"):
        trace(chain, "A", direction="sideways")


def test_zero_horizon_is_rejected(chain):
    with pytest.raises(TraceError, match="horizon"):
        trace(chain, "A", horizon=0)


def test_missing_columns_are_named(chain):
    with pytest.raises(TraceError, match="missing required columns"):
        TraceIndex(chain.drop(columns=[S.AMOUNT]))


def test_index_is_reusable_across_traces(chain):
    index = TraceIndex(chain)
    first = index.trace("A", horizon=3)
    second = index.trace("A", horizon=3)
    assert first.n_edges == second.n_edges == 3
    # A, B, C, D, NOISE1, NOISE2, X, Y
    assert index.n_accounts == 8


def test_empty_result_still_has_the_expected_shape(chain):
    result = trace(chain, "NOISE2", direction=FORWARD, horizon=2)
    assert result.n_edges == 0
    assert list(result.edges.columns) == [
        S.TRANSACTION_ID,
        S.TIMESTAMP,
        S.SOURCE_ACCOUNT,
        S.DESTINATION_ACCOUNT,
        S.AMOUNT,
        "depth",
    ]
    assert result.per_hop().empty
