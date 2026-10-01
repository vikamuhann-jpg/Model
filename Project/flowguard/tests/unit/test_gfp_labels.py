"""GFP column labels match what the library actually emits (WINNING_PLAN S7)."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.features.gfp import (
    DEFAULT_GFP_PARAMS,
    GFPFeatures,
    feature_label,
    feature_labels,
    windowed_params,
)

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _fan_in() -> pd.DataFrame:
    """A, B, C, D each pay HUB, a minute apart."""
    src = ["A", "B", "C", "D"]
    return pd.DataFrame({
        S.TRANSACTION_ID: [f"TX{i}" for i in range(4)],
        S.TIMESTAMP: [BASE + pd.Timedelta(minutes=i) for i in range(4)],
        S.SOURCE_ACCOUNT: src,
        S.DESTINATION_ACCOUNT: ["HUB"] * 4,
        S.AMOUNT: [100.0] * 4,
        S.CURRENCY: "USD",
        S.PAYMENT_TYPE: "ACH",
    })


@pytest.mark.parametrize("params", [DEFAULT_GFP_PARAMS, windowed_params(2.0)])
def test_one_unique_label_per_emitted_column(params):
    features = GFPFeatures(params=dict(params), progress_every=0).run_streaming(_fan_in())
    labels = feature_labels(params)
    assert len(labels) == features.shape[1]
    assert len(set(labels)) == len(labels)


def test_labels_mean_what_they_say():
    """The fourth edge closes a 4-edge fan-in onto HUB."""
    last = GFPFeatures(progress_every=0).run_streaming(_fan_in()).iloc[-1]
    by_label = dict(zip(feature_labels(), last.to_numpy()))
    assert by_label["count of fan-in patterns of size 4 containing this transaction "
                    "(24h window)"] == 1
    assert by_label["receiver's incoming transfers (48h window): transaction count"] == 4
    assert by_label["receiver's incoming transfers (48h window): total amount"] == 400


def test_non_gfp_columns_have_no_label():
    assert feature_label("amount_log") is None
    assert feature_label("gfp_f000").startswith("count of fan-in patterns of size 2")
