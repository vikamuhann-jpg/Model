"""Data-quality policy (plan v3 Phase 3).

Each check returns a finding rather than raising, so a full profile is produced
in one pass and the caller decides what is fatal. Severity separates "this
corpus is unusable" from "this is a property worth recording in the report".

One rule from the original plan is deliberately **absent**: "no self-transfers".
Roughly 60% of IBM AML rows are same-account "Reinvestment" transfers. They are
legitimate, and rejecting them would discard most of the corpus. They are
reported as an observation instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from flowguard.data import schema as S


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    count: int
    message: str

    def to_metadata(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "count": self.count,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(
        self, check: str, severity: Severity, count: int, message: str
    ) -> None:
        self.findings.append(Finding(check, severity, count, message))

    def to_metadata(self) -> dict:
        return {
            "ok": self.ok,
            "error_count": len(self.errors),
            "findings": [f.to_metadata() for f in self.findings],
        }

    def summary(self) -> str:
        lines = [f"validation: {'PASS' if self.ok else 'FAIL'}"]
        for f in self.findings:
            marker = {
                Severity.ERROR: "ERROR",
                Severity.WARNING: "warn ",
                Severity.INFO: "info ",
            }[f.severity]
            lines.append(f"  [{marker}] {f.check}: {f.message}")
        return "\n".join(lines)


def validate_transactions(df: pd.DataFrame) -> ValidationReport:
    """Run the quality policy over a canonical transaction frame."""
    report = ValidationReport()
    n = len(df)

    if n == 0:
        report.add("non_empty", Severity.ERROR, 0, "frame is empty")
        return report

    # --- fatal -----------------------------------------------------------
    dup_ids = int(df[S.TRANSACTION_ID].duplicated().sum())
    report.add(
        "unique_transaction_id",
        Severity.ERROR if dup_ids else Severity.INFO,
        dup_ids,
        f"{dup_ids} duplicate transaction ids" if dup_ids else "all ids unique",
    )

    null_ts = int(df[S.TIMESTAMP].isna().sum())
    report.add(
        "timestamp_parseable",
        Severity.ERROR if null_ts else Severity.INFO,
        null_ts,
        f"{null_ts} unparseable timestamps" if null_ts else "all timestamps parsed",
    )

    negative = int((df[S.AMOUNT] < 0).sum())
    report.add(
        "non_negative_amount",
        Severity.ERROR if negative else Severity.INFO,
        negative,
        f"{negative} negative amounts" if negative else "no negative amounts",
    )

    null_endpoints = int(
        df[S.SOURCE_ACCOUNT].isna().sum() + df[S.DESTINATION_ACCOUNT].isna().sum()
    )
    report.add(
        "endpoints_present",
        Severity.ERROR if null_endpoints else Severity.INFO,
        null_endpoints,
        f"{null_endpoints} null endpoints" if null_endpoints else "all endpoints present",
    )

    positives = int(df[S.IS_LAUNDERING].sum())
    report.add(
        "positives_present",
        Severity.ERROR if positives == 0 else Severity.INFO,
        positives,
        f"{positives} positives ({positives / n:.4%})",
    )

    # --- worth knowing ---------------------------------------------------
    zero_amount = int((df[S.AMOUNT] == 0).sum())
    report.add(
        "zero_amount",
        Severity.WARNING if zero_amount else Severity.INFO,
        zero_amount,
        f"{zero_amount} zero-value transfers ({zero_amount / n:.4%})",
    )

    exact_dupes = int(
        df.duplicated(
            subset=[
                S.TIMESTAMP,
                S.SOURCE_ACCOUNT,
                S.DESTINATION_ACCOUNT,
                S.AMOUNT,
                S.PAYMENT_TYPE,
            ]
        ).sum()
    )
    report.add(
        "duplicate_natural_key",
        Severity.WARNING if exact_dupes else Severity.INFO,
        exact_dupes,
        f"{exact_dupes} rows share a natural key ({exact_dupes / n:.4%}); "
        "pattern attachment cannot disambiguate these",
    )

    if S.IS_SELF_TRANSFER in df.columns:
        self_tx = int(df[S.IS_SELF_TRANSFER].sum())
        report.add(
            "self_transfers",
            Severity.INFO,
            self_tx,
            f"{self_tx} same-account transfers ({self_tx / n:.2%}); legitimate, "
            "excluded from the graph by policy",
        )

    if S.CURRENCY_RECEIVED in df.columns:
        cross = int((df[S.CURRENCY] != df[S.CURRENCY_RECEIVED]).sum())
        report.add(
            "cross_currency",
            Severity.INFO,
            cross,
            f"{cross} cross-currency transfers ({cross / n:.4%})",
        )

    # --- temporal --------------------------------------------------------
    span = df[S.TIMESTAMP].max() - df[S.TIMESTAMP].min()
    distinct_ts = int(df[S.TIMESTAMP].nunique())
    report.add(
        "temporal_resolution",
        Severity.WARNING if distinct_ts < n / 100 else Severity.INFO,
        distinct_ts,
        f"span {span}, {distinct_ts} distinct timestamps "
        f"({n / distinct_ts:.0f} tx per stamp); within-stamp order is undefined",
    )

    return report
