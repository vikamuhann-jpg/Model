"""Behaviour features see only strictly earlier transactions (WINNING_PLAN S4)."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.features.behaviour import behaviour_features

pytestmark = pytest.mark.leakage

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(rows):
    """rows: (src, dst, minutes after BASE, amount)."""
    return pd.DataFrame({
        S.TRANSACTION_ID: [f"TX{i}" for i in range(len(rows))],
        S.TIMESTAMP: [BASE + pd.Timedelta(minutes=m) for _, _, m, _ in rows],
        S.SOURCE_ACCOUNT: [r[0] for r in rows],
        S.DESTINATION_ACCOUNT: [r[1] for r in rows],
        S.AMOUNT: [r[3] for r in rows],
    })


ROWS = [
    ("A", "B", 0, 100.0),
    ("A", "C", 10, 50.0),
    ("B", "A", 20, 80.0),
    ("A", "B", 120, 40.0),
]


def test_values_by_hand():
    last = behaviour_features(_frame(ROWS)).iloc[-1]
    assert last["bh_src_out_n_1h"] == 0          # A's sends were 110+ min ago
    assert last["bh_src_out_n_24h"] == 2
    assert last["bh_src_out_amt_24h"] == 150
    assert last["bh_src_in_n_24h"] == 1          # B -> A at minute 20
    assert last["bh_src_passthrough_24h"] == pytest.approx(40 / 80)
    assert last["bh_src_secs_since_out"] == 110 * 60
    assert last["bh_pair_n_prior"] == 1          # A -> B at minute 0
    assert last["bh_reverse_pair_n_prior"] == 1  # B -> A at minute 20


def test_future_rows_change_nothing():
    later = ROWS + [("A", "B", 121, 999.0), ("B", "A", 125, 5.0)]
    early = behaviour_features(_frame(ROWS))
    full = behaviour_features(_frame(later)).iloc[: len(ROWS)]
    pd.testing.assert_frame_equal(early, full)


def test_same_minute_rows_are_blind_to_each_other():
    """Within-minute order is undefined, so neither row may count the other."""
    out = behaviour_features(_frame([("A", "B", 5, 10.0), ("A", "B", 5, 20.0)]))
    assert (out["bh_pair_n_prior"] == 0).all()
    assert (out["bh_src_out_n_1h"] == 0).all()
    assert out["bh_src_secs_since_out"].isna().all()


def test_labels_are_rejected():
    frame = _frame(ROWS)
    frame[S.IS_LAUNDERING] = 0
    with pytest.raises(Exception, match="is_laundering"):
        behaviour_features(frame)
