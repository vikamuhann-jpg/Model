"""Parse ``*_Patterns.txt`` and attach typology labels to transactions.

The patterns file annotates which transactions belong to which injected
laundering pattern. It is the only source of ``scenario_id`` and
``pattern_type``, which the unseen-pattern split (plan v3 section 11 B) and the
splitter's purge-buffer derivation both depend on.

Format::

    BEGIN LAUNDERING ATTEMPT - STACK
    2022/08/09 05:14,00952,8139F54E0,0111632,8062C56E0,5331.44,US Dollar,...,1
    ...
    END LAUNDERING ATTEMPT - STACK

    BEGIN LAUNDERING ATTEMPT - CYCLE:  Max 12 hops
    ...

Two properties make this harder than a merge:

1. **The rows carry no transaction id**, and neither does the transaction file.
   Attachment is therefore a composite-key join on the full natural key
   (timestamp, both endpoints, amount, currency, payment format).
2. **Timestamps are minute-resolution** with thousands of transactions per
   stamp, so natural keys are not guaranteed unique. Genuine collisions are
   counted and reported rather than silently resolved -- an ambiguous match is
   a data-quality fact the report needs, not something to paper over.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

import pandas as pd

from flowguard.data import schema as S
from flowguard.data.loader import RAW_TIMESTAMP_FORMAT, make_account_id

BEGIN_RE: Final = re.compile(r"^BEGIN LAUNDERING ATTEMPT\s*-\s*(?P<typology>[^:\n]+)")
END_RE: Final = re.compile(r"^END LAUNDERING ATTEMPT")

#: Natural key used to attach a pattern row to a transaction row.
JOIN_KEY: Final[tuple[str, ...]] = (
    S.TIMESTAMP,
    S.SOURCE_ACCOUNT,
    S.DESTINATION_ACCOUNT,
    S.AMOUNT,
    S.CURRENCY,
    S.PAYMENT_TYPE,
)


class PatternParseError(ValueError):
    """Raised when the patterns file does not match the expected structure."""


@dataclass(frozen=True)
class PatternAttachReport:
    """Outcome of attaching patterns, for the provenance record."""

    patterns: int
    pattern_rows: int
    matched_transactions: int
    unmatched_pattern_rows: int
    ambiguous_keys: int
    typology_counts: dict[str, int]
    labelled_positives: int
    total_positives: int

    def to_metadata(self) -> dict:
        return {
            "patterns": self.patterns,
            "pattern_rows": self.pattern_rows,
            "matched_transactions": self.matched_transactions,
            "unmatched_pattern_rows": self.unmatched_pattern_rows,
            "ambiguous_keys": self.ambiguous_keys,
            "typology_counts": dict(sorted(self.typology_counts.items())),
            "labelled_positives": self.labelled_positives,
            "total_positives": self.total_positives,
            "positive_coverage": (
                self.labelled_positives / self.total_positives
                if self.total_positives
                else 0.0
            ),
        }


def _iter_blocks(path: Path) -> Iterator[tuple[str, list[str]]]:
    """Yield ``(typology, csv_lines)`` for each BEGIN/END block."""
    typology: str | None = None
    rows: list[str] = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue

            begin = BEGIN_RE.match(line)
            if begin:
                if typology is not None:
                    raise PatternParseError(
                        f"nested BEGIN before END in {path.name}: {line!r}"
                    )
                typology = begin.group("typology").strip()
                rows = []
                continue

            if END_RE.match(line):
                if typology is None:
                    raise PatternParseError(f"END without BEGIN in {path.name}")
                yield typology, rows
                typology, rows = None, []
                continue

            if typology is not None:
                rows.append(line)

    if typology is not None:
        raise PatternParseError(f"unterminated block in {path.name}: {typology}")


def parse_patterns(path: str | Path) -> pd.DataFrame:
    """Parse the patterns file into one row per annotated transaction.

    Returns a frame carrying the natural join key plus ``scenario_id`` and
    ``pattern_type``. ``scenario_id`` identifies the pattern *instance*;
    ``pattern_type`` identifies its typology.
    """
    path = Path(path)
    records: list[dict] = []

    for index, (typology, lines) in enumerate(_iter_blocks(path)):
        scenario_id = f"SC{index:06d}"
        normalised = typology.upper().replace(" ", "_")
        for line in lines:
            fields = line.split(",")
            if len(fields) != 11:
                raise PatternParseError(
                    f"{path.name}: expected 11 fields in pattern row, got "
                    f"{len(fields)}: {line!r}"
                )
            records.append(
                {
                    "timestamp_raw": fields[0],
                    "from_bank_raw": fields[1],
                    "from_account_raw": fields[2],
                    "to_bank_raw": fields[3],
                    "to_account_raw": fields[4],
                    # Columns 5/6 are the received leg, 7/8 the paid leg --
                    # matching the transaction file's ordering.
                    "amount_paid_raw": fields[7],
                    "currency_paid_raw": fields[8],
                    "payment_format_raw": fields[9],
                    S.SCENARIO_ID: scenario_id,
                    S.PATTERN_TYPE: normalised,
                }
            )

    if not records:
        raise PatternParseError(f"{path.name}: no laundering blocks found")

    raw = pd.DataFrame.from_records(records)
    return pd.DataFrame(
        {
            S.TIMESTAMP: pd.to_datetime(
                raw["timestamp_raw"], format=RAW_TIMESTAMP_FORMAT, utc=True
            ),
            S.SOURCE_ACCOUNT: make_account_id(
                raw["from_bank_raw"], raw["from_account_raw"]
            ),
            S.DESTINATION_ACCOUNT: make_account_id(
                raw["to_bank_raw"], raw["to_account_raw"]
            ),
            S.AMOUNT: raw["amount_paid_raw"].astype("float64"),
            S.CURRENCY: raw["currency_paid_raw"].astype("string"),
            S.PAYMENT_TYPE: raw["payment_format_raw"].astype("string"),
            S.SCENARIO_ID: raw[S.SCENARIO_ID].astype("string"),
            S.PATTERN_TYPE: raw[S.PATTERN_TYPE].astype("string"),
        }
    )


def attach_patterns(
    transactions: pd.DataFrame, patterns: pd.DataFrame
) -> tuple[pd.DataFrame, PatternAttachReport]:
    """Populate ``scenario_id`` / ``pattern_type`` on ``transactions``.

    Matching is on the natural key. Where a key is ambiguous -- more than one
    distinct pattern instance sharing it -- the transaction is left unlabelled
    and counted, because guessing would corrupt the unseen-pattern split.
    """
    tx = transactions.copy()

    def key_frame(df: pd.DataFrame) -> pd.Series:
        return (
            df[S.TIMESTAMP].astype("int64").astype("string")
            + "|" + df[S.SOURCE_ACCOUNT].astype("string")
            + "|" + df[S.DESTINATION_ACCOUNT].astype("string")
            + "|" + df[S.AMOUNT].round(2).astype("string")
            + "|" + df[S.CURRENCY].astype("string")
            + "|" + df[S.PAYMENT_TYPE].astype("string")
        )

    pattern_keys = key_frame(patterns)

    # A key is usable only if every pattern row sharing it belongs to the same
    # pattern instance.
    by_key: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for key, scenario, typology in zip(
        pattern_keys, patterns[S.SCENARIO_ID], patterns[S.PATTERN_TYPE]
    ):
        by_key[key].add((scenario, typology))

    unambiguous = {k: next(iter(v)) for k, v in by_key.items() if len(v) == 1}
    ambiguous_keys = len(by_key) - len(unambiguous)

    tx_keys = key_frame(tx)
    mapped = tx_keys.map(unambiguous)
    matched = mapped.notna()

    tx[S.SCENARIO_ID] = pd.Series(
        [m[0] if isinstance(m, tuple) else pd.NA for m in mapped], index=tx.index
    ).astype("string")
    tx[S.PATTERN_TYPE] = pd.Series(
        [m[1] if isinstance(m, tuple) else pd.NA for m in mapped], index=tx.index
    ).astype("string")

    matched_keys = set(tx_keys[matched])
    unmatched_pattern_rows = int((~pattern_keys.isin(matched_keys)).sum())

    report = PatternAttachReport(
        patterns=int(patterns[S.SCENARIO_ID].nunique()),
        pattern_rows=len(patterns),
        matched_transactions=int(matched.sum()),
        unmatched_pattern_rows=unmatched_pattern_rows,
        ambiguous_keys=ambiguous_keys,
        typology_counts=(
            tx[S.PATTERN_TYPE].value_counts().to_dict()  # type: ignore[assignment]
        ),
        labelled_positives=int((matched & (tx[S.IS_LAUNDERING] == 1)).sum()),
        total_positives=int((tx[S.IS_LAUNDERING] == 1).sum()),
    )
    return tx, report
