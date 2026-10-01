"""Synthetic fixtures.

These are deliberately dataset-agnostic: the split and leakage logic must be
correct before the real corpus lands, and must stay correct independently of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S

BASE_TS = pd.Timestamp("2026-01-01T00:00:00Z")


def make_transactions(
    n: int = 300,
    *,
    n_accounts: int = 40,
    base_rate: float = 0.05,
    n_patterns: int = 6,
    pattern_span_minutes: int = 45,
    freq_minutes: int = 10,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a canonical transaction frame with injected laundering patterns.

    Each pattern is a contiguous chain of transfers, so some patterns will
    straddle a split boundary -- which is the case the boundary policies exist
    to handle.
    """
    rng = np.random.default_rng(seed)

    timestamps = BASE_TS + pd.to_timedelta(
        np.arange(n) * freq_minutes, unit="m"
    )
    accounts = np.array([f"ACC_{i:06d}" for i in range(n_accounts)])

    df = pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:08d}" for i in range(n)],
            S.TIMESTAMP: timestamps,
            S.SOURCE_ACCOUNT: rng.choice(accounts, n),
            S.DESTINATION_ACCOUNT: rng.choice(accounts, n),
            S.AMOUNT: np.round(rng.lognormal(7.0, 1.1, n), 2),
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: rng.choice(["WIRE", "ACH", "CHEQUE"], n),
            S.IS_LAUNDERING: 0,
            S.SCENARIO_ID: pd.NA,
            S.PATTERN_TYPE: pd.NA,
            S.AMOUNT_RECEIVED: np.round(rng.lognormal(7.0, 1.1, n), 2),
            S.CURRENCY_RECEIVED: "USD",
            S.IS_SELF_TRANSFER: 0,
        }
    )
    # No self-transfers.
    same = df[S.SOURCE_ACCOUNT] == df[S.DESTINATION_ACCOUNT]
    df.loc[same, S.DESTINATION_ACCOUNT] = accounts[
        (np.searchsorted(accounts, df.loc[same, S.SOURCE_ACCOUNT]) + 1) % n_accounts
    ]

    # Inject patterns as contiguous runs, spread across the whole time span.
    chain_len = max(2, pattern_span_minutes // freq_minutes)
    n_positives = int(n * base_rate)
    per_pattern = max(chain_len, n_positives // max(1, n_patterns))
    starts = np.linspace(0, n - per_pattern - 1, n_patterns).astype(int)

    typologies = ["layering", "round_trip", "fan_in", "fan_out"]
    for p, start in enumerate(starts):
        rows = slice(start, start + per_pattern)
        df.loc[df.index[rows], S.IS_LAUNDERING] = 1
        df.loc[df.index[rows], S.SCENARIO_ID] = f"SC_{p:03d}"
        df.loc[df.index[rows], S.PATTERN_TYPE] = typologies[p % len(typologies)]

    df[S.IS_SELF_TRANSFER] = (
        df[S.SOURCE_ACCOUNT] == df[S.DESTINATION_ACCOUNT]
    ).astype("int8")
    df = df.astype({S.IS_LAUNDERING: "int8"})
    for col, dtype in S.CANONICAL_DTYPES.items():
        if dtype == "string" and col in df.columns:
            df[col] = df[col].astype("string")
    return df


@pytest.fixture
def transactions() -> pd.DataFrame:
    return make_transactions()


@pytest.fixture
def unlabelled_patterns() -> pd.DataFrame:
    """A corpus with no pattern annotations, to exercise the fallback paths."""
    df = make_transactions()
    return df.drop(columns=[S.SCENARIO_ID, S.PATTERN_TYPE])
