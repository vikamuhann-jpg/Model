"""Evidence bundles (FR-09, FR-11), against the gates in TRACK_P_PLAN.md.

P2-a  v2 section 30.1 holds -- every field reads from the evidence object
P2-b  every reason code resolves to transactions present in the bundle
P2-c  round-trips: export, re-import, byte-identical
P2-d  every non-ACH bundle carries the coverage warning

P2-a and P2-b are the ones with teeth. A case object whose summary figures are
recomputed somewhere else drifts from its own evidence the first time either
side changes, and a reason citing a transaction the bundle does not contain is
an assertion the investigator cannot check.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.evidence import (
    COVERAGE_WARNING,
    UNKNOWN_RAIL_WARNING,
    EvidenceBundle,
    EvidenceError,
    Reason,
    build_bundle,
    reason_code,
)
from flowguard.graph.trace import TraceLimits, trace

BASE = pd.Timestamp("2026-01-01T00:00:00Z")
FIXED_TIME = datetime(2026, 1, 2, 10, 21, tzinfo=timezone.utc)

MODEL = {
    "model_id": "flowguard_E2_v1",
    "git_commit": "d230c50ef73e93e3d48cf20e5d30f1d8fcbdc1f4",
    "device_used": "cuda",
}


def _frame(rows, rails=None) -> pd.DataFrame:
    """rows: (source, destination, amount, minutes_after_base)."""
    df = pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:05d}" for i in range(len(rows))],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=m) for _, _, _, m in rows],
            S.SOURCE_ACCOUNT: [s for s, _, _, _ in rows],
            S.DESTINATION_ACCOUNT: [d for _, d, _, _ in rows],
            S.AMOUNT: [a for _, _, a, _ in rows],
            S.CURRENCY: "USD",
        }
    )
    if rails is not None:
        df[S.PAYMENT_TYPE] = rails
    return df


@pytest.fixture
def chain() -> pd.DataFrame:
    return _frame(
        [("A", "B", 1000.0, 10), ("B", "C", 900.0, 20), ("C", "D", 800.0, 30)],
        rails=["ACH", "ACH", "ACH"],
    )


@pytest.fixture
def contributions(chain) -> pd.DataFrame:
    """Stand-in for local SHAP, shaped exactly as the real matrix is."""
    return pd.DataFrame(
        {
            "amount_log": [0.30, 0.10, -0.05],
            "gfp_f042": [0.20, 0.25, 0.15],
            "hour": [-0.02, -0.01, -0.03],
        },
        index=chain.index,
    )


def _bundle(chain, contributions=None, **kw):
    result = trace(chain, "A", horizon=3)
    return build_bundle(
        result,
        score=0.83,
        threshold=0.72,
        threshold_source="max_f1_on_validation",
        model=MODEL,
        contributions=contributions,
        transactions=chain,
        created_at=FIXED_TIME,
        **kw,
    )


# ---------------------------------------------------------------- P2-a


def test_bundle_is_internally_consistent(chain, contributions):
    _bundle(chain, contributions).check_internal_consistency()


def test_accounts_are_derived_from_the_path_not_asserted(chain, contributions):
    bundle = _bundle(chain, contributions)
    assert bundle.accounts == ["A", "B", "C", "D"]
    bundle.accounts = ["A", "B", "C", "D", "GHOST"]
    with pytest.raises(EvidenceError, match="accounts do not match"):
        bundle.check_internal_consistency()


def test_transaction_ids_must_match_the_path(chain, contributions):
    bundle = _bundle(chain, contributions)
    bundle.transaction_ids.append("TX99999")
    with pytest.raises(EvidenceError, match="transaction_ids do not match"):
        bundle.check_internal_consistency()


def test_per_hop_amounts_must_reconcile_to_the_path(chain, contributions):
    bundle = _bundle(chain, contributions)
    bundle.trace["per_hop"][0]["amount"] = 999999.0
    with pytest.raises(EvidenceError, match="per_hop depth 1 claims"):
        bundle.check_internal_consistency()


def test_per_hop_counts_must_reconcile_to_the_path(chain, contributions):
    bundle = _bundle(chain, contributions)
    bundle.trace["per_hop"][0]["n_transactions"] = 7
    with pytest.raises(EvidenceError, match="claims 7 transactions"):
        bundle.check_internal_consistency()


def test_rail_counts_must_reconcile_to_the_path(chain, contributions):
    bundle = _bundle(chain, contributions)
    bundle.coverage["rails"] = {"ACH": 99}
    with pytest.raises(EvidenceError, match="coverage rail counts"):
        bundle.check_internal_consistency()


def test_no_typology_or_risk_band_is_invented(chain, contributions):
    """Fields describing unbuilt work must be absent, not guessed."""
    payload = _bundle(chain, contributions).to_dict()
    for absent in ("primary_typology", "secondary_typologies", "risk_category"):
        assert absent not in payload
    assert "risk_category" not in payload["risk"]


# ---------------------------------------------------------------- P2-b


def test_every_reason_cites_only_transactions_in_the_bundle(chain, contributions):
    bundle = _bundle(chain, contributions)
    present = set(bundle.transaction_ids)
    assert bundle.reasons
    for reason in bundle.reasons:
        assert reason.transaction_ids
        assert set(reason.transaction_ids) <= present


def test_a_reason_citing_an_absent_transaction_is_rejected(chain, contributions):
    bundle = _bundle(chain, contributions)
    bundle.reasons.append(
        Reason(
            code="MADE_UP", feature="x", contribution=1.0, transaction_ids=["TX99999"]
        )
    )
    with pytest.raises(EvidenceError, match="cites transactions absent"):
        bundle.check_internal_consistency()


def test_reason_codes_are_mechanical_not_hand_written():
    assert reason_code("amount_log", 0.4) == "AMOUNT_LOG_RAISED"
    assert reason_code("amount_log", -0.4) == "AMOUNT_LOG_LOWERED"


def test_reasons_are_ranked_by_absolute_contribution(chain, contributions):
    bundle = _bundle(chain, contributions)
    magnitudes = [abs(r.contribution) for r in bundle.reasons]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_graph_features_are_opaque_without_extraction_params(chain, contributions):
    """Without the GFP params a gfp_* column is a position, not a concept."""
    by_feature = {r.feature: r for r in _bundle(chain, contributions).reasons}
    assert by_feature["gfp_f042"].opaque is True
    assert by_feature["gfp_f042"].label is None
    assert by_feature["amount_log"].opaque is False


def test_graph_features_are_named_from_extraction_params(chain, contributions):
    """With them, the documented GFP layout names every column (WINNING_PLAN S7)."""
    from flowguard.features.gfp import DEFAULT_GFP_PARAMS, feature_labels

    bundle = _bundle(chain, contributions, gfp_params=DEFAULT_GFP_PARAMS)
    reason = {r.feature: r for r in bundle.reasons}["gfp_f042"]
    assert reason.opaque is False
    assert reason.label == feature_labels(DEFAULT_GFP_PARAMS)[42]
    assert EvidenceBundle.from_json(bundle.to_json()).reasons[0].label == bundle.reasons[0].label


def test_without_contributions_there_are_no_reasons(chain):
    """No SHAP means no reasons -- never invented ones."""
    assert _bundle(chain).reasons == []


# ---------------------------------------------------------------- P2-c


def test_bundle_round_trips_byte_identically(chain, contributions):
    first = _bundle(chain, contributions).to_json()
    second = EvidenceBundle.from_json(first).to_json()
    assert first == second


def test_bundle_round_trips_through_a_file(tmp_path, chain, contributions):
    original = _bundle(chain, contributions)
    path = original.write(tmp_path / "cases" / "case.json")
    reloaded = EvidenceBundle.read(path)
    assert reloaded.to_json() == original.to_json()
    reloaded.check_internal_consistency()


def test_floats_survive_the_round_trip(chain, contributions):
    original = _bundle(chain, contributions)
    reloaded = EvidenceBundle.from_json(original.to_json())
    assert reloaded.risk["score"] == original.risk["score"]
    assert [r.contribution for r in reloaded.reasons] == [
        r.contribution for r in original.reasons
    ]


def test_unknown_fields_are_rejected_on_import(chain, contributions):
    payload = _bundle(chain, contributions).to_dict()
    payload["smuggled_in"] = 1
    with pytest.raises(EvidenceError, match="unrecognised fields"):
        EvidenceBundle.from_dict(payload)


def test_case_id_is_stable_for_the_same_evidence(chain, contributions):
    assert _bundle(chain, contributions).case_id == _bundle(chain, contributions).case_id


# ---------------------------------------------------------------- P2-d


def test_an_ach_only_case_carries_no_warning(chain, contributions):
    assert _bundle(chain, contributions).coverage["warning"] is None


def test_a_non_ach_case_carries_the_coverage_warning():
    mixed = _frame(
        [("A", "B", 1000.0, 10), ("B", "C", 900.0, 20)], rails=["ACH", "Cheque"]
    )
    bundle = build_bundle(
        trace(mixed, "A", horizon=2),
        score=0.9,
        threshold=0.72,
        threshold_source="max_f1_on_validation",
        model=MODEL,
        transactions=mixed,
        created_at=FIXED_TIME,
    )
    assert bundle.coverage["warning"] == COVERAGE_WARNING
    assert bundle.coverage["rails"] == {"ACH": 1, "Cheque": 1}
    assert "COVERAGE" in bundle.summary()


def test_a_corpus_without_rails_says_so_rather_than_staying_silent():
    """ETH records no payment type; silence would read as 'ACH, fine'."""
    bare = _frame([("A", "B", 100.0, 1)])
    bundle = build_bundle(
        trace(bare, "A", horizon=1),
        score=0.5,
        threshold=0.72,
        threshold_source="max_f1_on_validation",
        model=MODEL,
        transactions=bare,
        created_at=FIXED_TIME,
    )
    assert bundle.coverage["warning"] == UNKNOWN_RAIL_WARNING
    assert bundle.coverage["unknown_rail_transactions"] == 1


def test_reasons_come_from_the_traced_rows_not_the_first_rows():
    """Regression for a published defect.

    The case's rows sit after unrelated ones. The unrelated rows carry a huge
    contribution on a feature the case's rows never touch; if the join goes by
    position instead of by index, that feature leaks into the case's reasons.
    """
    rows = [("X", "Y", 1.0, 1), ("P", "Q", 2.0, 2), ("R", "S", 3.0, 3)]
    rows += [("A", "B", 1000.0, 10), ("B", "C", 900.0, 20)]
    df = _frame(rows, rails=["ACH"] * 5)
    contrib = pd.DataFrame(
        {
            "decoy_feature": [9.0, 9.0, 9.0, 0.0, 0.0],
            "case_feature": [0.0, 0.0, 0.0, 0.4, 0.2],
        },
        index=df.index,
    )
    bundle = build_bundle(
        trace(df, "A", horizon=2),
        score=0.9,
        threshold=0.5,
        threshold_source="test",
        model=MODEL,
        contributions=contrib,
        transactions=df,
        created_at=FIXED_TIME,
    )
    features = {r.feature for r in bundle.reasons}
    assert features == {"case_feature"}
    assert bundle.reasons[0].contribution == pytest.approx(0.6)


# ---------------------------------------------------------------- truncation


def test_a_truncated_trace_is_marked_in_the_bundle():
    """P1 found a third of real traces truncate; that must reach the case."""
    rows = [("HUB", f"P{i}", 10.0, i) for i in range(100)]
    result = trace(_frame(rows), "HUB", horizon=1, limits=TraceLimits(degree_cap=10))
    bundle = build_bundle(
        result,
        score=0.8,
        threshold=0.72,
        threshold_source="max_f1_on_validation",
        model=MODEL,
        created_at=FIXED_TIME,
    )
    assert bundle.trace["is_complete"] is False
    assert bundle.trace["truncation"]["capped_vertices"] == 1
    assert "TRUNCATED" in bundle.summary()
    bundle.check_internal_consistency()
