"""Sparse-tail trimming (docs/ADR-003)."""

from __future__ import annotations

import pandas as pd

from flowguard.data import schema as S
from flowguard.data.windowing import daily_profile, trim_sparse_tail
from tests.conftest import make_transactions


def _with_tail(dense_days: int = 6, tail_days: int = 4) -> pd.DataFrame:
    """Dense corpus followed by a sparse, laundering-heavy tail.

    Reproduces the HI-Small shape: background traffic stops while injected
    patterns keep running.
    """
    dense = make_transactions(n=dense_days * 500, freq_minutes=1)
    base = dense[S.TIMESTAMP].max()

    tail = make_transactions(n=tail_days * 5, freq_minutes=1, seed=7)
    tail[S.TIMESTAMP] = [
        base + pd.Timedelta(days=1 + i // 5) for i in range(len(tail))
    ]
    tail[S.IS_LAUNDERING] = 1
    tail[S.TRANSACTION_ID] = [f"TAIL{i:06d}" for i in range(len(tail))]

    return pd.concat([dense, tail], ignore_index=True)


def test_trailing_sparse_days_are_dropped():
    df = _with_tail()
    trimmed, report = trim_sparse_tail(df)

    assert report.applied
    assert report.rows_dropped == 20
    assert len(trimmed) == len(df) - 20
    assert trimmed[S.TIMESTAMP].max() < pd.Timestamp(report.cutoff)


def test_dropped_positives_are_counted():
    """The trim discards real positives; that must be visible, not silent."""
    df = _with_tail()
    _, report = trim_sparse_tail(df)

    assert report.positives_dropped == 20
    meta = report.to_metadata()
    assert meta["positives_dropped"] == 20
    assert len(meta["days_dropped"]) == 4


def test_dense_corpus_is_untouched():
    df = make_transactions(n=3000, freq_minutes=1)
    trimmed, report = trim_sparse_tail(df)

    assert not report.applied
    assert len(trimmed) == len(df)
    assert report.cutoff is None


def test_only_a_trailing_run_is_removed():
    """A quiet day mid-corpus is real variation and must survive."""
    df = make_transactions(n=3000, freq_minutes=1)
    start = df[S.TIMESTAMP].min().normalize()

    # Make one interior day sparse by deleting most of its rows.
    day2 = (df[S.TIMESTAMP] >= start + pd.Timedelta(days=1)) & (
        df[S.TIMESTAMP] < start + pd.Timedelta(days=2)
    )
    keep = df[~day2 | (df.groupby(day2).cumcount() < 3)]

    trimmed, report = trim_sparse_tail(keep)
    assert not report.applied or pd.Timestamp(report.cutoff) > start + pd.Timedelta(days=2)


def test_daily_profile_reports_rate():
    df = _with_tail()
    profile = daily_profile(df)

    assert {"rows", "positives", "rate"} <= set(profile.columns)
    assert profile["rate"].iloc[-1] == 1.0  # the tail is pure laundering


def test_single_day_corpus_is_a_noop():
    df = make_transactions(n=100, freq_minutes=1)
    trimmed, report = trim_sparse_tail(df)
    assert len(trimmed) == len(df)
    assert not report.applied
