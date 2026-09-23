"""The interface to the product repository, held to its published contracts.

contracts/ is the only agreement between this repository and the product one.
If a scoring output drifts from it, the product breaks in a way this repository
would never see -- so the drift must fail here instead.

The validator is a small subset of JSON Schema (type, required, properties,
additionalProperties, items, enum, minimum, maximum): exactly what the four
contracts use. The product side can validate the same files with any full
JSON Schema implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from flowguard.evidence import EvidenceBundle

REPO = Path(__file__).resolve().parents[4]
CONTRACTS = REPO / "contracts"
SAMPLES = REPO / "sample_outputs"
PACKAGE = REPO / "Project" / "flowguard" / "models" / "flowguard_V2_v1"


def _is(value, kind: str) -> bool:
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return {
        "string": isinstance(value, str),
        "number": number,
        "integer": number and float(value).is_integer(),
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "null": value is None,
    }[kind]


def validate(value, schema: dict, where: str = "$") -> None:
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        assert any(_is(value, k) for k in kinds), f"{where}: {value!r} is not {kinds}"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} not in {schema['enum']}"
    if _is(value, "number"):
        if "minimum" in schema:
            assert value >= schema["minimum"], f"{where}: {value} < {schema['minimum']}"
        if "maximum" in schema:
            assert value <= schema["maximum"], f"{where}: {value} > {schema['maximum']}"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            assert key in value, f"{where}: missing required {key!r}"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            assert not extra, f"{where}: unexpected fields {sorted(extra)}"
        for key, item in value.items():
            if key in props:
                validate(item, props[key], f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{where}[{i}]")


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict]:
    return pd.read_csv(path).to_dict("records")


# ---------------------------------------------------------------- the validator


def test_the_validator_rejects_what_it_should():
    """A validator that passes everything would make every test below vacuous."""
    schema = contract("score")
    good = {
        "transaction_id": "TX1",
        "timestamp": "2022-09-09T00:00:00Z",
        "source_account": "a",
        "destination_account": "b",
        "amount": 1.0,
        "score": 0.5,
        "raw_score": 0.4,
        "rank": 1,
        "alert": True,
    }
    validate(good, schema)
    for bad in (
        {k: v for k, v in good.items() if k != "rank"},  # missing required
        {**good, "score": 1.5},  # above maximum
        {**good, "rank": 0},  # below minimum
        {**good, "alert": "yes"},  # wrong type
    ):
        with pytest.raises(AssertionError):
            validate(bad, schema)


# ---------------------------------------------------------------- the samples


def test_sample_input_matches_the_transaction_contract():
    schema = contract("transaction")
    for i, row in enumerate(rows(SAMPLES / "transactions_sample.csv")):
        validate(row, schema, f"row {i}")


def test_sample_scores_match_the_score_contract():
    schema = contract("score")
    records = rows(SAMPLES / "scores.csv")
    for i, row in enumerate(records):
        validate(row, schema, f"row {i}")
    ranks = sorted(r["rank"] for r in records)
    assert ranks == list(range(1, len(records) + 1)), "rank must be a 1..n permutation"


def test_sample_cases_match_the_bundle_contract_and_their_own_evidence():
    schema = contract("evidence_bundle")
    files = sorted((SAMPLES / "cases").glob("*.json"))
    assert files
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate(payload, schema, path.name)
        EvidenceBundle.from_dict(payload).check_internal_consistency()


def test_run_summary_matches_its_contract_and_the_files_beside_it():
    run = json.loads((SAMPLES / "run.json").read_text(encoding="utf-8"))
    validate(run, contract("run"))
    scores = pd.read_csv(SAMPLES / "scores.csv")
    assert run["n_transactions"] == len(scores)
    assert run["n_alerts"] == int(scores["alert"].sum())
    on_disk = {p.stem for p in (SAMPLES / "cases").glob("*.json")}
    assert set(run["case_ids"]) == on_disk


# ---------------------------------------------------------------- the model


def test_the_shipped_model_does_not_use_the_simulator_artifact():
    """payment_type nearly identifies an injected pattern (ADR-007). The model in
    git must not see it, or the cases it explains lead with 'it is ACH'."""
    columns = json.loads((PACKAGE / "feature_schema.json").read_text())["columns"]
    assert not [c for c in columns if "payment_type" in c]
    run = json.loads((SAMPLES / "run.json").read_text(encoding="utf-8"))
    assert run["uses_payment_type"] is False


def test_the_shipped_package_records_how_its_graph_features_were_built():
    """score.py rebuilds graph features from graph.json; without it training and
    scoring could silently use different GFP settings (ADR-015 era packages did)."""
    graph = json.loads((PACKAGE / "graph.json").read_text(encoding="utf-8"))
    assert graph["insertion_convention"] == "transform inserts once"
    assert {"params", "batch_size", "behaviour"} <= set(graph)


def test_every_feature_of_the_shipped_model_has_a_plain_language_label():
    """An investigator never sees a bare column name as a reason."""
    from flowguard.features.behaviour import LABELS as BH
    from flowguard.features.gfp import feature_label
    from flowguard.features.transaction import LABELS as TX

    params = json.loads((PACKAGE / "graph.json").read_text(encoding="utf-8"))["params"]
    columns = json.loads((PACKAGE / "feature_schema.json").read_text())["columns"]
    unnamed = [c for c in columns if not (feature_label(c, params) or BH.get(c) or TX.get(c))]
    assert not unnamed, unnamed


def test_sample_cases_name_their_graph_reasons():
    """Graph reasons carry a plain-language label and are not flagged opaque."""
    reasons = [
        r
        for path in (SAMPLES / "cases").glob("*.json")
        for r in json.loads(path.read_text(encoding="utf-8"))["reasons"]
        if r["feature"].startswith("gfp_f")
    ]
    assert reasons, "expected graph reasons in the sample cases"
    assert all(r["label"] and not r["opaque"] for r in reasons)


def test_history_rows_build_features_but_are_not_scored(tmp_path):
    """Scored cold, a window alerts far above budget (every counterparty looks
    new). Rows before emit_from are history: used for features, never emitted."""
    pytest.importorskip("snapml")
    from flowguard.pipeline import score

    source = pd.read_csv(SAMPLES / "transactions_sample.csv").head(2_000)
    source.to_csv(tmp_path / "tx.csv", index=False)
    cutoff = pd.Timestamp(sorted(source["timestamp"])[1_500], tz="UTC")
    summary = score.run(PACKAGE, tmp_path / "tx.csv", tmp_path / "out", n_cases=0,
                        emit_from=cutoff)
    emitted = pd.read_csv(tmp_path / "out" / "scores.csv")
    assert summary["n_transactions"] == len(emitted) == int(
        (pd.to_datetime(source["timestamp"], utc=True) >= cutoff).sum())
    assert summary["history_transactions"] == 2_000 - len(emitted)
    assert (pd.to_datetime(emitted["timestamp"], utc=True) >= cutoff).all()


def test_live_scoring_writes_outputs_that_match_every_contract(tmp_path):
    """The real entry point, graph extraction included, on a small slice."""
    pytest.importorskip("snapml")
    from flowguard.pipeline import score

    source = pd.read_csv(SAMPLES / "transactions_sample.csv").head(2_000)
    source.to_csv(tmp_path / "tx.csv", index=False)
    summary = score.run(PACKAGE, tmp_path / "tx.csv", tmp_path / "out", n_cases=3)

    validate(summary, contract("run"))
    for row in rows(tmp_path / "out" / "scores.csv"):
        validate(row, contract("score"))
    for path in (tmp_path / "out" / "cases").glob("*.json"):
        validate(json.loads(path.read_text(encoding="utf-8")), contract("evidence_bundle"))
    assert summary["n_transactions"] == 2_000


def test_scoring_refuses_input_missing_a_feature_the_model_needs(tmp_path):
    """Never zero-fill a missing input: the model would answer confidently and wrongly."""
    pytest.importorskip("snapml")
    from flowguard.pipeline import score

    source = pd.read_csv(SAMPLES / "transactions_sample.csv").head(200)
    source.drop(columns=["amount_received"]).to_csv(tmp_path / "tx.csv", index=False)
    with pytest.raises(score.ScoringError, match="absent"):
        score.run(PACKAGE, tmp_path / "tx.csv", tmp_path / "out", n_cases=0)
