"""Every number we publish must be the number its evidence record holds.

`docs/CLAIMS_REGISTER.md` lists each claim a reader can see and the file that
proves it. This module is that register made executable: it opens each record,
reads the value out, and checks it against what the documents state, rounded the
way they state it. A record that changes, or a document edited by hand to a number
no record supports, fails here instead of in front of a judge.

The one claim not checked is the published benchmark (F1 63.2), which comes from
a paper rather than a run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
RUNS = REPO / "Project" / "flowguard" / "experiments" / "runs"
PACKAGE = REPO / "Project" / "flowguard" / "models" / "flowguard_V2_v1"


def record(name: str) -> dict:
    return json.loads((RUNS / name).read_text(encoding="utf-8"))


def summary(name: str, key: str) -> tuple[float, float]:
    s = record(name)["summary"][key]
    return s["mean"], s["sd"]


def metrics() -> dict:
    return json.loads((PACKAGE / "metrics.json").read_text(encoding="utf-8"))


def at_budget(test: dict, budget: float = 0.01) -> dict:
    return next(b for b in test["budgets"] if b["budget"] == budget)


def shown(value: float, places: int) -> float:
    """The value as a document displays it: rounded half-up, not banker's."""
    return float(f"{value + 1e-12:.{places}f}")


# --------------------------------------------------------------- the claims

def test_claim_01_shipped_model():
    test = metrics()["test"]
    assert shown(test["pr_auc"], 3) == 0.595
    assert shown(at_budget(test)["recall"] * 100, 1) == 78.3


def test_claim_02_benchmark_protocol_five_seeds():
    f1, f1_sd = summary("S4b_no_ts_stats.json", "f1_val_threshold")
    pr, _ = summary("S4b_no_ts_stats.json", "pr_auc")
    # The spread is 0.002475. It was published as 0.003 -- the 4-place display
    # (0.0025) rounded up a second time -- until this test compared it.
    assert (shown(f1, 3), shown(f1_sd, 3)) == (0.614, 0.002)
    assert shown(pr, 3) == 0.608


def test_claim_04_lookahead_is_worth_nothing():
    b1, b1_sd = summary("S1c_paper_b1.json", "f1_val_threshold")
    b128, b128_sd = summary("S1e_paper_b128.json", "f1_val_threshold")
    assert (shown(b1, 3), shown(b1_sd, 3)) == (0.518, 0.027)
    assert (shown(b128, 3), shown(b128_sd, 3)) == (0.524, 0.021)
    # The claim itself: the gap is inside either run's spread.
    assert abs(b128 - b1) < min(b1_sd, b128_sd)


def test_claim_05_payment_type_is_half_the_score():
    with_field, _ = summary("S1c_paper_b1.json", "f1_val_threshold")
    without, _ = summary("S4_nopt_3000.json", "f1_val_threshold")
    assert shown(without, 3) == 0.249
    assert without < with_field / 2 + 0.01


def test_claim_06_timestamp_statistics_were_a_time_proxy():
    kept, _ = summary("S4_nopt_3000_bh.json", "f1_val_threshold")
    dropped, _ = summary("S4b_no_ts_stats.json", "f1_val_threshold")
    assert (shown(kept, 3), shown(dropped, 3)) == (0.544, 0.614)


def test_claim_07_what_the_model_detects():
    d = record("G1_diagnosis_HI-Small.json")
    assert shown(d["patterned"]["recall"] * 100, 1) == 95.3
    assert shown(d["untagged"]["recall"] * 100, 1) == 27.9
    assert (d["patterned"]["caught"], d["patterned"]["positives"]) == (1276, 1339)
    assert (d["untagged"]["caught"], d["untagged"]["positives"]) == (128, 458)
    share = d["patterned"]["positives"] / d["positives"]
    assert shown(share * 100, 0) == 75


def test_claim_08_the_headline_includes_the_tail():
    dense = metrics()["temporal_stability"]["windows"][0]
    assert shown(dense["pr_auc"], 3) == 0.406
    assert (dense["n"], dense["positives"]) == (952348, 1003)


def test_claim_09_graph_features_help_on_a_real_network():
    delta = record("P2_eth_bootstrap_ETH_gfp_parts_v2.json")["delta"]
    assert shown(delta["point"], 3) == 0.050
    assert [shown(v, 3) for v in delta["ci95"]] == [0.019, 0.108]
    assert delta["ci95"][0] > 0, "the interval must exclude zero"


def test_claim_10_fresh_data_fails_its_bar():
    g1 = record("G1_zero_shot_LI-Small-2M.json")["test"]
    d = record("G1_diagnosis_LI-Small-2M.json")
    assert shown(g1["recall_at_1pct"] * 100, 1) == 13.3
    assert g1["recall_at_1pct"] < 0.50, "the pre-registered bar was 50%"
    assert shown(d["untagged"]["positives"] / d["positives"] * 100, 0) == 88
    assert shown(d["patterned"]["recall"] * 100, 1) == 41.2


def test_claim_11_blind_off_ach():
    rails = metrics()["error_analysis"]["slices"]["payment_type"]
    assert shown(rails["ACH"]["recall"] * 100, 1) == 84.9
    assert shown(rails["Cheque"]["recall"] * 100, 1) == 4.2
    for rail in ("Cash", "Credit Card", "Bitcoin"):
        assert rails[rail]["recall"] == 0.0, rail


def test_claim_12_every_correctness_gate_passes():
    log = (RUNS / "V2_validation.log").read_text(encoding="utf-8")
    for gate in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"):
        assert f"[PASS  ] {gate} " in log, gate


def test_claim_13_memory_gate_passes():
    log = (RUNS / "COMP3_p9_validation.log").read_text(encoding="utf-8")
    assert "P9: 9.71 GB vs <= 10 GB allowed" in log
    assert "[PASS  ] P9" in log


def test_claim_14_throughput_gate_fails_and_says_why():
    one = record("S1c_paper_b1.json")["extraction"]["tx_per_s"]
    batched = record("S1e_paper_b128.json")["extraction"]["tx_per_s"]
    assert round(one) == 532 and one < 1000, "P8 wants 1,000 tx/s"
    assert round(batched) == 2785


def test_claim_16_scoring_uses_every_tree_deliberately():
    arms = record("COMP1_tree_range.json")["arms"]
    assert shown(arms["all_trees"]["best_f1"], 4) == 0.6142
    assert shown(arms["best_iteration"]["best_f1"], 4) == 0.6140


# ------------------------------------------------ the documents say the same

@pytest.mark.parametrize("text", [
    "0.595", "78.3%", "0.614 ± 0.002", "63.2", "0.249",
    "95.3%", "27.9%", "13.3%", "0.050", "0.019",
])
def test_the_readme_states_the_registered_numbers(text):
    """The headline numbers above must be the ones the README shows."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert text in readme, f"README no longer shows {text}"
