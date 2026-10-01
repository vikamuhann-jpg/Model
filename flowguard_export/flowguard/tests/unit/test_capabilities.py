"""Dataset capability matrix (Tier S3)."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.capabilities import (
    Capability,
    DatasetCapabilities,
    detect,
    reconcile,
)


def test_hi_small_shaped_data_provides_what_the_pipeline_expects(transactions):
    caps = detect(transactions, "HI-Small")

    for expected in (
        Capability.PAYMENT_TYPE,
        Capability.CURRENCY,
        Capability.TYPOLOGY,
        Capability.TRANSACTION_LABELS,
        Capability.SELF_TRANSFERS,
    ):
        assert caps.has(expected), f"{expected.value} should be detected"


def test_capabilities_are_derived_from_data_not_column_presence(transactions):
    """An all-null annotation column provides no typology.

    Checking for the column alone would report a capability the corpus cannot
    actually support, which is the failure this module exists to prevent.
    """
    blanked = transactions.copy()
    blanked[S.PATTERN_TYPE] = pd.NA

    assert not detect(blanked, "HI-Small").has(Capability.TYPOLOGY)


def test_constant_currency_does_not_provide_cross_currency(transactions):
    """One currency cannot support a cross-currency feature."""
    single = transactions.copy()
    single[S.CURRENCY] = "USD"
    single[S.CURRENCY_RECEIVED] = "USD"

    caps = detect(single, "HI-Small")
    assert caps.has(Capability.CURRENCY)
    assert not caps.has(Capability.CROSS_CURRENCY)


def test_eth_shaped_data_disables_the_right_consumers(transactions):
    """A corpus with no rail, currency or typology must skip those consumers."""
    eth_like = transactions.drop(
        columns=[S.PAYMENT_TYPE, S.CURRENCY, S.CURRENCY_RECEIVED,
                 S.PATTERN_TYPE, S.SCENARIO_ID]
    )
    caps = detect(eth_like, "ETH-Phishing")
    skipped = caps.skipped_consumers()

    assert "E0_rule_baseline" in skipped
    assert "unseen_pattern_split" in skipped
    assert "per_typology_recall" in skipped
    assert "purge_boundary_policy" in skipped
    # Transaction labels are still present in this fixture, so metrics survive.
    assert "transaction_level_metrics" not in skipped


def test_account_labels_enable_account_level_metrics(transactions):
    labels = pd.DataFrame({"account_id": ["A", "B"], "is_illicit": [1, 0]})
    caps = detect(transactions, "ETH-Phishing", account_labels=labels)

    assert caps.has(Capability.ACCOUNT_LABELS)
    assert caps.supports("account_level_metrics")


def test_missing_capability_is_reported_not_silent(transactions):
    """The whole point: an absent capability must be visible."""
    eth_like = transactions.drop(columns=[S.PAYMENT_TYPE])
    caps = detect(eth_like, "ETH-Phishing")

    assert caps.unmet("E0_rule_baseline") == {Capability.PAYMENT_TYPE}
    assert "payment_type" in caps.summary()
    assert "payment_type" in caps.to_metadata()["missing"]


def test_reconcile_flags_a_corpus_that_changed_shape(transactions):
    """A dataset quietly losing a column must not pass unnoticed."""
    degraded = transactions.drop(columns=[S.PATTERN_TYPE])
    problems = reconcile(detect(degraded, "HI-Small"))

    assert any("typology_annotations" in p for p in problems)


def test_reconcile_is_clean_on_the_expected_shape(transactions):
    """The shared fixture is not HI-Small-shaped, so make it one here.

    Real HI-Small has multiple currencies (1.42% of rows are cross-currency)
    and a 518,581-row accounts table. Asserting against a fixture that lacks
    both would either fail or force the expectation to be weakened to fit the
    fixture -- which would stop it catching a real corpus that changed shape.
    """
    faithful = transactions.copy()
    faithful.loc[faithful.index[:5], S.CURRENCY] = "Euro"
    accounts = pd.DataFrame({"account_id": ["ACC_000001"], "bank_id": [1]})

    problems = reconcile(detect(faithful, "HI-Small", accounts=accounts))
    assert problems == [], f"unexpected discrepancies: {problems}"


def test_reconcile_flags_an_undeclared_dataset(transactions):
    problems = reconcile(detect(transactions, "Some-New-Corpus"))
    assert any("no declared expectation" in p for p in problems)


def test_metadata_is_registry_ready(transactions):
    meta = detect(transactions, "HI-Small").to_metadata()

    assert meta["dataset"] == "HI-Small"
    assert isinstance(meta["provides"], list)
    assert isinstance(meta["skipped_consumers"], dict)


def test_summary_states_what_is_disabled(transactions):
    eth_like = transactions.drop(columns=[S.PAYMENT_TYPE, S.PATTERN_TYPE])
    summary = detect(eth_like, "ETH-Phishing").summary()

    assert "disabled here" in summary
    assert "E0_rule_baseline" in summary


def test_empty_capability_set_supports_nothing():
    caps = DatasetCapabilities(name="empty")
    assert not caps.supports("E0_rule_baseline")
    assert len(caps.skipped_consumers()) > 0
