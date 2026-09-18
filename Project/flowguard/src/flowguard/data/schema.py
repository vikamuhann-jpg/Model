"""Canonical transaction schema and the label-isolation rule.

Single source of truth for field names, per plan v3 §6. Every loader adapts a
raw corpus *to* this contract; nothing downstream sees raw column names.

The label-isolation rule (v3 §6.2) is enforced structurally here rather than by
convention, because "remember not to pass the label into the features" is the
most common way this class of project quietly invalidates itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd

# --------------------------------------------------------------------------
# Canonical fields
# --------------------------------------------------------------------------

TRANSACTION_ID: Final = "transaction_id"
TIMESTAMP: Final = "timestamp"
SOURCE_ACCOUNT: Final = "source_account"
DESTINATION_ACCOUNT: Final = "destination_account"
AMOUNT: Final = "amount"
CURRENCY: Final = "currency"
PAYMENT_TYPE: Final = "payment_type"
IS_LAUNDERING: Final = "is_laundering"
SCENARIO_ID: Final = "scenario_id"
PATTERN_TYPE: Final = "pattern_type"

# The IBM AML corpora record both sides of a transfer. They agree for ~99.4% of
# rows; the remainder are genuine cross-currency transfers where the sent and
# received values legitimately differ. `amount`/`currency` carry the PAID side
# (what left the source); these carry the received side so the difference stays
# recoverable instead of being silently discarded at load time.
AMOUNT_RECEIVED: Final = "amount_received"
CURRENCY_RECEIVED: Final = "currency_received"

#: Derived at load time. Roughly 60% of IBM AML rows are same-account transfers
#: (payment format "Reinvestment"). They are legitimate account activity but
#: contribute nothing to inter-account topology, so the graph builder needs to
#: discriminate them without re-deriving the comparison.
IS_SELF_TRANSFER: Final = "is_self_transfer"

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    TRANSACTION_ID,
    TIMESTAMP,
    SOURCE_ACCOUNT,
    DESTINATION_ACCOUNT,
    AMOUNT,
    CURRENCY,
    IS_LAUNDERING,
)

OPTIONAL_COLUMNS: Final[tuple[str, ...]] = (
    PAYMENT_TYPE,
    SCENARIO_ID,
    PATTERN_TYPE,
    AMOUNT_RECEIVED,
    CURRENCY_RECEIVED,
    IS_SELF_TRANSFER,
)

ALL_COLUMNS: Final[tuple[str, ...]] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

#: Evaluation-only columns. No feature extractor may observe these (v3 §6.2).
FORBIDDEN_IN_FEATURES: Final[frozenset[str]] = frozenset(
    {IS_LAUNDERING, SCENARIO_ID, PATTERN_TYPE}
)

#: Columns carried on a graph edge. Labels are deliberately absent (v3 §6.3):
#: they live in a separate table joined on transaction_id at evaluation time.
EDGE_PAYLOAD: Final[tuple[str, ...]] = (
    TRANSACTION_ID,
    TIMESTAMP,
    AMOUNT,
    CURRENCY,
    PAYMENT_TYPE,
)

CANONICAL_DTYPES: Final[dict[str, str]] = {
    TRANSACTION_ID: "string",
    SOURCE_ACCOUNT: "string",
    DESTINATION_ACCOUNT: "string",
    AMOUNT: "float64",
    CURRENCY: "string",
    PAYMENT_TYPE: "string",
    IS_LAUNDERING: "int8",
    SCENARIO_ID: "string",
    PATTERN_TYPE: "string",
    AMOUNT_RECEIVED: "float64",
    CURRENCY_RECEIVED: "string",
    IS_SELF_TRANSFER: "int8",
}


class SchemaError(ValueError):
    """Raised when a frame does not satisfy the canonical contract."""


class LabelLeakageError(AssertionError):
    """Raised when an evaluation-only column reaches a feature extractor."""


# --------------------------------------------------------------------------
# Contract checks
# --------------------------------------------------------------------------


def validate_schema(df: pd.DataFrame, *, require_optional: bool = False) -> None:
    """Assert that ``df`` satisfies the canonical contract.

    Raises
    ------
    SchemaError
        If a required column is missing, a timestamp is not datetime-typed, or
        ``is_laundering`` holds anything other than 0/1.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing required column(s): {missing}")

    if require_optional:
        missing_opt = [c for c in OPTIONAL_COLUMNS if c not in df.columns]
        if missing_opt:
            raise SchemaError(f"missing optional column(s): {missing_opt}")

    if not pd.api.types.is_datetime64_any_dtype(df[TIMESTAMP]):
        raise SchemaError(
            f"{TIMESTAMP!r} must be datetime64; got {df[TIMESTAMP].dtype}. "
            "Parse it in the loader, not downstream."
        )

    labels = pd.unique(df[IS_LAUNDERING].dropna())
    unexpected = set(labels) - {0, 1}
    if unexpected:
        raise SchemaError(f"{IS_LAUNDERING!r} must be 0/1; found {sorted(unexpected)}")

    if df[IS_LAUNDERING].isna().any():
        raise SchemaError(f"{IS_LAUNDERING!r} contains nulls; ground truth must be complete")

    unknown = set(df.columns) - set(ALL_COLUMNS)
    if unknown:
        raise SchemaError(
            f"non-canonical column(s) present: {sorted(unknown)}. "
            "Map them in the loader or drop them."
        )


def feature_view(df: pd.DataFrame) -> pd.DataFrame:
    """Return a label-free view of ``df``, safe to hand to a feature extractor.

    This is the only sanctioned way to produce extractor input.
    """
    return df.drop(columns=[c for c in FORBIDDEN_IN_FEATURES if c in df.columns])


def label_view(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the join key and the evaluation-only columns."""
    cols = [TRANSACTION_ID] + [c for c in FORBIDDEN_IN_FEATURES if c in df.columns]
    return df[cols]


def assert_label_blind(df: pd.DataFrame) -> None:
    """Fail if an evaluation-only column is present.

    Raises
    ------
    LabelLeakageError
    """
    leaked = FORBIDDEN_IN_FEATURES & set(df.columns)
    if leaked:
        raise LabelLeakageError(
            f"evaluation-only column(s) reached a feature extractor: {sorted(leaked)}"
        )


@dataclass(frozen=True)
class SchemaSummary:
    """Counts recorded alongside every experiment for provenance."""

    rows: int
    accounts: int
    positives: int
    base_rate: float
    ts_min: pd.Timestamp
    ts_max: pd.Timestamp

    def to_metadata(self) -> dict:
        return {
            "rows": self.rows,
            "accounts": self.accounts,
            "positives": self.positives,
            "base_rate": self.base_rate,
            "ts_min": self.ts_min.isoformat(),
            "ts_max": self.ts_max.isoformat(),
        }


def summarise(df: pd.DataFrame) -> SchemaSummary:
    """Derive the counts the plan insists on re-deriving rather than citing."""
    validate_schema(df)
    accounts = pd.unique(
        pd.concat([df[SOURCE_ACCOUNT], df[DESTINATION_ACCOUNT]], ignore_index=True)
    )
    positives = int(df[IS_LAUNDERING].sum())
    return SchemaSummary(
        rows=len(df),
        accounts=int(len(accounts)),
        positives=positives,
        base_rate=positives / len(df) if len(df) else 0.0,
        ts_min=df[TIMESTAMP].min(),
        ts_max=df[TIMESTAMP].max(),
    )
