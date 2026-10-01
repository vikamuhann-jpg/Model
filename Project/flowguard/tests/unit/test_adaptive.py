"""Degree-normalised neighbourhood features (Tier B).

The family exists to attack the hard-negative enrichment Gate A exposed
(1.02x tabular -> 2.10x with GFP), so the tests check the property that
matters: a hub behaving like other hubs must not look anomalous merely for
being large.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.schema import LabelLeakageError
from flowguard.features.adaptive import AdaptiveFeatures

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:05d}" for i in range(len(rows))],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=i) for i in range(len(rows))],
            S.SOURCE_ACCOUNT: [s for s, _, _ in rows],
            S.DESTINATION_ACCOUNT: [d for _, d, _ in rows],
            S.AMOUNT: [a for _, _, a in rows],
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: "ACH",
        }
    )


@pytest.fixture
def mixed() -> pd.DataFrame:
    """A hub with many counterparties, and a small account with few."""
    rows = []
    for i in range(40):                      # HUB pays 40 distinct parties
        rows.append(("HUB", f"P{i}", 1000.0))
    for i in range(3):                       # SMALL pays 3, tiny amounts
        rows.append(("SMALL", f"Q{i}", 30.0))
    return _frame(rows)


def test_hub_is_not_flagged_for_being_large(mixed):
    """The central property: size alone must not read as anomalous.

    A hub transacting like other hubs should score near zero on the
    peer-normalised features, however high its raw degree.
    """
    extractor = AdaptiveFeatures().fit(mixed)
    features = extractor.run(mixed)

    hub = features[mixed[S.SOURCE_ACCOUNT] == "HUB"]
    assert abs(hub["adp_amount_peer_z"].mean()) < 1.0, (
        "a hub behaving typically for its degree scored as anomalous"
    )


def test_unusual_amount_for_a_small_account_stands_out(mixed):
    """The complement: the same absolute amount is anomalous for a small account."""
    extractor = AdaptiveFeatures().fit(mixed)

    probe = _frame([("SMALL", "NEW", 5000.0), ("HUB", "NEW", 5000.0)])
    features = extractor.run(probe)

    # Identical amount; SMALL's own history makes it far more unusual.
    assert (
        features.loc[probe.index[0], "adp_amount_vs_own_median"]
        > features.loc[probe.index[1], "adp_amount_vs_own_median"]
    )


def test_raw_degree_is_retained_alongside_the_normalised_view(mixed):
    """Normalising must ADD a view, not hide size where size is informative."""
    features = AdaptiveFeatures().fit(mixed).run(mixed)
    assert "adp_out_degree_log" in features.columns
    assert "adp_amount_vs_peer_median" in features.columns


def test_degree_asymmetry_separates_payers_from_receivers(mixed):
    features = AdaptiveFeatures().fit(mixed).run(mixed)
    hub_rows = features[mixed[S.SOURCE_ACCOUNT] == "HUB"]
    # HUB only ever sends, so asymmetry should sit at the positive end.
    assert hub_rows["adp_degree_asymmetry"].mean() > 0


def test_unseen_accounts_are_flagged_not_treated_as_quiet(mixed):
    """"No history" and "no activity" are different facts."""
    extractor = AdaptiveFeatures().fit(mixed)
    probe = _frame([("BRAND_NEW", "ALSO_NEW", 100.0)])
    features = extractor.run(probe)

    assert features["adp_source_unseen"].iloc[0] == 1
    assert features["adp_dest_unseen"].iloc[0] == 1


def test_unseen_account_falls_back_to_global_median_not_zero(mixed):
    """A zero fallback would make every new account look extraordinary."""
    extractor = AdaptiveFeatures().fit(mixed)
    probe = _frame([("BRAND_NEW", "X", float(extractor.global_median_))])
    features = extractor.run(probe)

    # An amount equal to the global median should look ordinary.
    assert features["adp_amount_vs_own_median"].iloc[0] == pytest.approx(
        np.log1p(1.0), abs=0.01
    )


def test_features_are_finite(mixed):
    """Ratios and z-scores must not emit inf or nan into the model."""
    features = AdaptiveFeatures().fit(mixed).run(mixed)
    values = features.to_numpy(dtype="float64")
    assert np.isfinite(values).all()


def test_rejects_labelled_input(mixed):
    labelled = mixed.copy()
    labelled[S.IS_LAUNDERING] = 0
    with pytest.raises(LabelLeakageError):
        AdaptiveFeatures().fit(labelled)


def test_rejects_use_before_fit(mixed):
    with pytest.raises(RuntimeError, match="before fit"):
        AdaptiveFeatures().run(mixed)


def test_metadata_records_fit_scope(mixed):
    meta = AdaptiveFeatures().fit(mixed).to_metadata()
    assert meta["fit_scope"] == "train"
    assert meta["fit_rows"] == len(mixed)
    assert "hard-negative" in meta["targets"]


def test_row_alignment_is_preserved(mixed):
    shuffled = mixed.sample(frac=1.0, random_state=0)
    features = AdaptiveFeatures().fit(mixed).run(shuffled)
    assert features.index.equals(shuffled.index)
