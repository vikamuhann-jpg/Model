"""Dataset capability matrix (Tier S3).

The pipeline was built against IBM AML HI-Small, which carries a payment rail, a
currency, typology annotations and transaction-level labels. ETH Phishing
carries none of those. Without an explicit contract, a component meeting a
corpus that lacks what it needs fails in one of two bad ways: an exception
halfway through a long run, or -- worse -- a silent zero that looks like a
measurement.

This module makes the mismatch a declaration checked at load time. Each dataset
states what it provides, each consumer states what it requires, and the
reconciliation is printed and written into the experiment record. A capability
that is absent is then visibly absent, and can never be mistaken for a measured
zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from flowguard.data import schema as S


class Capability(str, Enum):
    """Something a corpus may or may not provide."""

    PAYMENT_TYPE = "payment_type"
    CURRENCY = "currency"
    CROSS_CURRENCY = "cross_currency"
    TYPOLOGY = "typology_annotations"
    TRANSACTION_LABELS = "transaction_level_labels"
    ACCOUNT_LABELS = "account_level_labels"
    SELF_TRANSFERS = "self_transfers"
    ACCOUNT_REFERENCE = "account_reference_table"


#: What each consumer needs. A consumer whose requirements are unmet is skipped,
#: and the skip is reported rather than silently producing an empty result.
CONSUMERS: dict[str, set[Capability]] = {
    "E0_rule_baseline": {Capability.PAYMENT_TYPE},
    "tx_payment_type_feature": {Capability.PAYMENT_TYPE},
    "tx_currency_feature": {Capability.CURRENCY},
    "tx_cross_currency_feature": {Capability.CROSS_CURRENCY},
    "tx_self_transfer_feature": {Capability.SELF_TRANSFERS},
    "unseen_pattern_split": {Capability.TYPOLOGY},
    "per_typology_recall": {Capability.TYPOLOGY},
    "purge_boundary_policy": {Capability.TYPOLOGY},
    "transaction_level_metrics": {Capability.TRANSACTION_LABELS},
    "account_level_metrics": {Capability.ACCOUNT_LABELS},
    "entity_features": {Capability.ACCOUNT_REFERENCE},
}


@dataclass
class DatasetCapabilities:
    """What one corpus provides, and what that costs downstream."""

    name: str
    provides: set[Capability] = field(default_factory=set)
    notes: dict[str, str] = field(default_factory=dict)

    def has(self, capability: Capability) -> bool:
        return capability in self.provides

    def unmet(self, consumer: str) -> set[Capability]:
        return CONSUMERS.get(consumer, set()) - self.provides

    def supports(self, consumer: str) -> bool:
        return not self.unmet(consumer)

    def skipped_consumers(self) -> dict[str, list[str]]:
        """Consumers that cannot run here, and what each is missing."""
        return {
            name: sorted(c.value for c in self.unmet(name))
            for name in CONSUMERS
            if not self.supports(name)
        }

    def to_metadata(self) -> dict:
        return {
            "dataset": self.name,
            "provides": sorted(c.value for c in self.provides),
            "missing": sorted(
                c.value for c in set(Capability) - self.provides
            ),
            "skipped_consumers": self.skipped_consumers(),
            "notes": self.notes,
        }

    def summary(self) -> str:
        lines = [f"capabilities — {self.name}"]
        for capability in sorted(Capability, key=lambda c: c.value):
            mark = "yes" if self.has(capability) else "NO "
            note = self.notes.get(capability.value, "")
            lines.append(
                f"  [{mark}] {capability.value:26s} {note}".rstrip()
            )
        skipped = self.skipped_consumers()
        if skipped:
            lines.append("  disabled here:")
            for consumer, missing in sorted(skipped.items()):
                lines.append(f"    {consumer:28s} needs {', '.join(missing)}")
        else:
            lines.append("  all consumers supported")
        return "\n".join(lines)


def detect(df: pd.DataFrame, name: str, *, accounts: pd.DataFrame | None = None,
           account_labels: pd.DataFrame | None = None) -> DatasetCapabilities:
    """Derive capabilities from the data itself rather than from a hand-written list.

    Presence of a column is not enough -- an all-null ``pattern_type`` provides
    no typology, and a constant ``currency`` cannot support a cross-currency
    feature. The check is what the corpus can actually support.
    """
    caps = DatasetCapabilities(name=name)
    notes: dict[str, str] = {}

    if S.PAYMENT_TYPE in df.columns and df[S.PAYMENT_TYPE].notna().any():
        caps.provides.add(Capability.PAYMENT_TYPE)
        notes[Capability.PAYMENT_TYPE.value] = (
            f"{df[S.PAYMENT_TYPE].nunique()} distinct rails"
        )

    if S.CURRENCY in df.columns and df[S.CURRENCY].notna().any():
        caps.provides.add(Capability.CURRENCY)
        n_currencies = df[S.CURRENCY].nunique()
        notes[Capability.CURRENCY.value] = f"{n_currencies} distinct"
        if S.CURRENCY_RECEIVED in df.columns and n_currencies > 1:
            caps.provides.add(Capability.CROSS_CURRENCY)

    if S.PATTERN_TYPE in df.columns and df[S.PATTERN_TYPE].notna().any():
        caps.provides.add(Capability.TYPOLOGY)
        positives = df[df[S.IS_LAUNDERING] == 1]
        coverage = (
            float(positives[S.PATTERN_TYPE].notna().mean()) if len(positives) else 0.0
        )
        notes[Capability.TYPOLOGY.value] = (
            f"{df[S.PATTERN_TYPE].nunique()} typologies, "
            f"{coverage:.0%} of positives annotated"
        )

    if S.IS_LAUNDERING in df.columns and df[S.IS_LAUNDERING].notna().all():
        caps.provides.add(Capability.TRANSACTION_LABELS)
        rate = float(df[S.IS_LAUNDERING].mean())
        notes[Capability.TRANSACTION_LABELS.value] = f"base rate {rate:.4%}"

    if account_labels is not None and len(account_labels):
        caps.provides.add(Capability.ACCOUNT_LABELS)
        notes[Capability.ACCOUNT_LABELS.value] = (
            f"{len(account_labels):,} labelled accounts"
        )

    if S.IS_SELF_TRANSFER in df.columns:
        caps.provides.add(Capability.SELF_TRANSFERS)
        notes[Capability.SELF_TRANSFERS.value] = (
            f"{df[S.IS_SELF_TRANSFER].mean():.1%} of rows"
        )

    if accounts is not None and len(accounts):
        caps.provides.add(Capability.ACCOUNT_REFERENCE)
        notes[Capability.ACCOUNT_REFERENCE.value] = f"{len(accounts):,} accounts"

    caps.notes = notes
    return caps


#: Declared expectations, used to catch a corpus that silently changed shape.
#: Checked against `detect()` rather than trusted -- see `reconcile`.
EXPECTED: dict[str, set[Capability]] = {
    "HI-Small": {
        Capability.PAYMENT_TYPE,
        Capability.CURRENCY,
        Capability.CROSS_CURRENCY,
        Capability.TYPOLOGY,
        Capability.TRANSACTION_LABELS,
        Capability.SELF_TRANSFERS,
        Capability.ACCOUNT_REFERENCE,
    },
    "ETH-Phishing": {
        Capability.ACCOUNT_LABELS,
        Capability.SELF_TRANSFERS,
    },
}


def reconcile(detected: DatasetCapabilities) -> list[str]:
    """Compare detected capabilities against what was declared for this corpus.

    Returns a list of discrepancies. An empty list means the corpus is the shape
    the pipeline was configured for; anything else means either the data or the
    expectation is wrong, and finding out which is cheaper now than mid-run.
    """
    expected = EXPECTED.get(detected.name)
    if expected is None:
        return [f"no declared expectation for {detected.name!r}"]

    problems = []
    for missing in sorted(expected - detected.provides, key=lambda c: c.value):
        problems.append(
            f"expected {missing.value} but the data does not provide it"
        )
    for extra in sorted(detected.provides - expected, key=lambda c: c.value):
        problems.append(
            f"data provides {extra.value}, which was not declared"
        )
    return problems
