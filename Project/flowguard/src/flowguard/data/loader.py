"""Load the IBM AML corpora into the canonical schema (plan v3 Phase 1).

Everything here is driven by the *actual* file layout, which differs from the
plan documents' assumptions in several ways that matter. Each is handled
explicitly and noted, because every one of them fails silently otherwise.

Raw transaction header::

    Timestamp,From Bank,Account,To Bank,Account,Amount Received,
    Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering

Verified against HI-Small (5,078,345 transactions, 518,581 accounts):

* ``Account`` appears **twice**. Columns are therefore resolved positionally.
* There is **no transaction id**. One is synthesised from row position.
* ``From Bank``/``To Bank`` are zero-padded (``010``); ``accounts.csv`` stores
  the same ids unpadded (``210``). Normalising both to int makes all 30,470
  banks join with zero orphans; comparing them as strings matches nothing.
* ``Account Number`` alone is *nearly* unique -- 8 of 518,581 appear under more
  than one bank -- so account identity is the ``(bank, account)`` composite.
  Keying on the account column alone would merge distinct accounts into one
  graph node and corrupt every structural feature computed from it.
* Timestamps are minute-resolution with thousands of transactions per stamp.
* ~60% of rows are same-account "Reinvestment" transfers. They are legitimate
  and are retained, flagged via ``is_self_transfer``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import pandas as pd

from flowguard.data import schema as S

#: Positional layout of the raw transaction CSV. Used instead of names because
#: the header contains "Account" twice.
RAW_TRANSACTION_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp_raw",
    "from_bank_raw",
    "from_account_raw",
    "to_bank_raw",
    "to_account_raw",
    "amount_received_raw",
    "currency_received_raw",
    "amount_paid_raw",
    "currency_paid_raw",
    "payment_format_raw",
    "is_laundering_raw",
)

RAW_TIMESTAMP_FORMAT: Final = "%Y/%m/%d %H:%M"

#: Which side of a transfer becomes the canonical ``amount``.
AmountSide = Literal["paid", "received"]

DEFAULT_AMOUNT_SIDE: Final[AmountSide] = "paid"


class LoaderError(ValueError):
    """Raised when a raw file does not match the expected layout."""


def make_account_id(bank: pd.Series, account: pd.Series) -> pd.Series:
    """Build the composite account identifier.

    Bank ids are normalised numerically so that the zero-padded form in the
    transaction file (``010``) matches the unpadded form in the accounts file
    (``10``). Accounts are then namespaced by bank, because the bare account
    number is not globally unique.
    """
    bank_norm = pd.to_numeric(bank, errors="raise").astype("int64").astype("string")
    return bank_norm.str.cat(account.astype("string"), sep=":")


@dataclass(frozen=True)
class LoadReport:
    """What the loader did, for the provenance record."""

    path: str
    rows: int
    amount_side: AmountSide
    self_transfers: int
    cross_currency: int
    ts_min: pd.Timestamp
    ts_max: pd.Timestamp

    def to_metadata(self) -> dict:
        return {
            "path": self.path,
            "rows": self.rows,
            "amount_side": self.amount_side,
            "self_transfers": self.self_transfers,
            "self_transfer_rate": (
                self.self_transfers / self.rows if self.rows else 0.0
            ),
            "cross_currency": self.cross_currency,
            "ts_min": self.ts_min.isoformat(),
            "ts_max": self.ts_max.isoformat(),
            "transaction_id_convention": (
                "TX{n:010d}, n = 0-based row position in the raw file as "
                "downloaded; stable only for an unmodified source file"
            ),
        }


def load_transactions(
    path: str | Path,
    *,
    amount_side: AmountSide = DEFAULT_AMOUNT_SIDE,
    nrows: int | None = None,
) -> tuple[pd.DataFrame, LoadReport]:
    """Read a ``*_Trans.csv`` file into the canonical schema.

    Parameters
    ----------
    amount_side
        Which leg becomes canonical ``amount``/``currency``. ``"paid"`` is the
        value that left the source account. The other leg is always retained in
        ``amount_received``/``currency_received``, so the choice is recoverable.
    nrows
        Read only the first *n* data rows. For tests and smoke runs.
    """
    path = Path(path)

    header = pd.read_csv(path, nrows=0)
    if len(header.columns) != len(RAW_TRANSACTION_COLUMNS):
        raise LoaderError(
            f"{path.name}: expected {len(RAW_TRANSACTION_COLUMNS)} columns, "
            f"found {len(header.columns)}: {list(header.columns)}"
        )

    raw = pd.read_csv(
        path,
        skiprows=1,
        header=None,
        names=list(RAW_TRANSACTION_COLUMNS),
        nrows=nrows,
        dtype={
            "from_bank_raw": "string",
            "from_account_raw": "string",
            "to_bank_raw": "string",
            "to_account_raw": "string",
            "currency_received_raw": "string",
            "currency_paid_raw": "string",
            "payment_format_raw": "string",
        },
    )

    timestamp = pd.to_datetime(
        raw["timestamp_raw"], format=RAW_TIMESTAMP_FORMAT, utc=True
    )
    source = make_account_id(raw["from_bank_raw"], raw["from_account_raw"])
    destination = make_account_id(raw["to_bank_raw"], raw["to_account_raw"])

    if amount_side == "paid":
        amount, currency = raw["amount_paid_raw"], raw["currency_paid_raw"]
        other_amount, other_currency = (
            raw["amount_received_raw"],
            raw["currency_received_raw"],
        )
    else:
        amount, currency = raw["amount_received_raw"], raw["currency_received_raw"]
        other_amount, other_currency = raw["amount_paid_raw"], raw["currency_paid_raw"]

    df = pd.DataFrame(
        {
            # No id exists in the source, so position becomes identity. This is
            # recorded in the load report because re-ingesting a modified file
            # would silently renumber every row and break every join.
            S.TRANSACTION_ID: pd.Series(
                [f"TX{i:010d}" for i in range(len(raw))], dtype="string"
            ),
            S.TIMESTAMP: timestamp,
            S.SOURCE_ACCOUNT: source,
            S.DESTINATION_ACCOUNT: destination,
            S.AMOUNT: raw[amount.name].astype("float64"),
            S.CURRENCY: currency,
            S.PAYMENT_TYPE: raw["payment_format_raw"],
            S.IS_LAUNDERING: raw["is_laundering_raw"].astype("int8"),
            S.SCENARIO_ID: pd.Series(pd.NA, index=raw.index, dtype="string"),
            S.PATTERN_TYPE: pd.Series(pd.NA, index=raw.index, dtype="string"),
            S.AMOUNT_RECEIVED: raw[other_amount.name].astype("float64"),
            S.CURRENCY_RECEIVED: other_currency,
            S.IS_SELF_TRANSFER: (source == destination).astype("int8"),
        }
    )

    report = LoadReport(
        path=str(path),
        rows=len(df),
        amount_side=amount_side,
        self_transfers=int(df[S.IS_SELF_TRANSFER].sum()),
        cross_currency=int((df[S.CURRENCY] != df[S.CURRENCY_RECEIVED]).sum()),
        ts_min=df[S.TIMESTAMP].min(),
        ts_max=df[S.TIMESTAMP].max(),
    )

    S.validate_schema(df)
    return df, report


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

ACCOUNT_ID: Final = "account_id"
BANK_ID: Final = "bank_id"
BANK_NAME: Final = "bank_name"
ENTITY_ID: Final = "entity_id"
ENTITY_NAME: Final = "entity_name"

RAW_ACCOUNT_COLUMNS: Final[tuple[str, ...]] = (
    "Bank Name",
    "Bank ID",
    "Account Number",
    "Entity ID",
    "Entity Name",
)


def load_accounts(path: str | Path) -> pd.DataFrame:
    """Read an ``*_accounts.csv`` file, keyed to match transaction endpoints.

    Deliberately kept as a separate table rather than denormalised onto
    transactions: it is reference data, and joining it in at load time would
    put entity attributes inside the canonical transaction contract where the
    label-isolation rule cannot see them.

    ``entity_id`` groups accounts under a common owner -- one entity may hold
    several accounts across several banks, which is the customer-to-account
    hierarchy the graph work will need.
    """
    path = Path(path)
    raw = pd.read_csv(path, dtype="string")

    missing = [c for c in RAW_ACCOUNT_COLUMNS if c not in raw.columns]
    if missing:
        raise LoaderError(f"{path.name}: missing column(s) {missing}")

    return pd.DataFrame(
        {
            ACCOUNT_ID: make_account_id(raw["Bank ID"], raw["Account Number"]),
            BANK_ID: pd.to_numeric(raw["Bank ID"]).astype("int64"),
            BANK_NAME: raw["Bank Name"],
            ENTITY_ID: raw["Entity ID"],
            ENTITY_NAME: raw["Entity Name"],
        }
    )
