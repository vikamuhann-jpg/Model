"""Canonical schema contract (plan v3 section 6)."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.schema import SchemaError


def test_fixture_satisfies_the_contract(transactions):
    S.validate_schema(transactions, require_optional=True)


def test_missing_required_column_is_rejected(transactions):
    with pytest.raises(SchemaError, match="missing required column"):
        S.validate_schema(transactions.drop(columns=[S.AMOUNT]))


def test_string_timestamp_is_rejected(transactions):
    """Parsing belongs in the loader; downstream code must not guess a format."""
    df = transactions.copy()
    df[S.TIMESTAMP] = df[S.TIMESTAMP].astype(str)
    with pytest.raises(SchemaError, match="must be datetime64"):
        S.validate_schema(df)


def test_non_binary_label_is_rejected(transactions):
    df = transactions.copy()
    df.loc[df.index[0], S.IS_LAUNDERING] = 2
    with pytest.raises(SchemaError, match="must be 0/1"):
        S.validate_schema(df)


def test_null_label_is_rejected(transactions):
    df = transactions.copy()
    df[S.IS_LAUNDERING] = df[S.IS_LAUNDERING].astype("Int8")
    df.loc[df.index[0], S.IS_LAUNDERING] = pd.NA
    with pytest.raises(SchemaError, match="complete"):
        S.validate_schema(df)


def test_unmapped_raw_column_is_rejected(transactions):
    """Catches a loader that forgot to map or drop a source column."""
    df = transactions.copy()
    df["Receiving Currency"] = "USD"
    with pytest.raises(SchemaError, match="non-canonical column"):
        S.validate_schema(df)


def test_label_is_never_named_anything_else():
    """Guards the naming collision the plans were explicitly written to fix."""
    assert S.IS_LAUNDERING == "is_laundering"
    for alias in ("label", "target", "y", "fraud"):
        assert alias not in S.ALL_COLUMNS


def test_summary_rederives_counts(transactions):
    summary = S.summarise(transactions)

    assert summary.rows == len(transactions)
    assert summary.positives == int(transactions[S.IS_LAUNDERING].sum())
    assert summary.base_rate == pytest.approx(summary.positives / summary.rows)
    assert summary.ts_min <= summary.ts_max

    meta = summary.to_metadata()
    assert meta["rows"] == summary.rows
    pd.Timestamp(meta["ts_min"])  # parses


def test_summary_counts_accounts_from_both_endpoints(transactions):
    summary = S.summarise(transactions)
    expected = len(
        set(transactions[S.SOURCE_ACCOUNT]) | set(transactions[S.DESTINATION_ACCOUNT])
    )
    assert summary.accounts == expected
