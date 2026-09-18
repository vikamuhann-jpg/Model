"""Pattern parsing and composite-key attachment."""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.loader import load_transactions
from flowguard.data.patterns import (
    PatternParseError,
    attach_patterns,
    parse_patterns,
)

RAW_HEADER = (
    "Timestamp,From Bank,Account,To Bank,Account,Amount Received,"
    "Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
)
TX_A = "2022/09/01 00:20,010,8000EBD30,020,8000EBD31,100.00,US Dollar,100.00,US Dollar,ACH,1"
TX_B = "2022/09/01 00:25,020,8000EBD31,030,8000EBD32,95.00,US Dollar,95.00,US Dollar,ACH,1"
TX_C = "2022/09/01 00:30,040,8000EBD40,050,8000EBD41,10.00,US Dollar,10.00,US Dollar,Cheque,0"

PATTERNS_TXT = f"""BEGIN LAUNDERING ATTEMPT - STACK
{TX_A}
{TX_B}
END LAUNDERING ATTEMPT - STACK

BEGIN LAUNDERING ATTEMPT - CYCLE:  Max 12 hops
{TX_B}
END LAUNDERING ATTEMPT - CYCLE
"""


@pytest.fixture
def trans_csv(tmp_path):
    path = tmp_path / "T_Trans.csv"
    path.write_text("\n".join([RAW_HEADER, TX_A, TX_B, TX_C]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def patterns_txt(tmp_path):
    path = tmp_path / "T_Patterns.txt"
    path.write_text(PATTERNS_TXT, encoding="utf-8")
    return path


def test_blocks_are_parsed_with_typology(patterns_txt):
    patterns = parse_patterns(patterns_txt)
    assert set(patterns[S.PATTERN_TYPE]) == {"STACK", "CYCLE"}
    assert patterns[S.SCENARIO_ID].nunique() == 2


def test_typology_suffix_after_colon_is_stripped(patterns_txt):
    """Headers look like 'CYCLE:  Max 12 hops'; the qualifier is not the typology."""
    patterns = parse_patterns(patterns_txt)
    assert "CYCLE" in set(patterns[S.PATTERN_TYPE])
    assert not any(":" in t for t in patterns[S.PATTERN_TYPE])


def test_attachment_populates_scenario_and_typology(trans_csv, patterns_txt):
    tx, _ = load_transactions(trans_csv)
    patterns = parse_patterns(patterns_txt)
    labelled, report = attach_patterns(tx, patterns)

    assert labelled.loc[0, S.PATTERN_TYPE] == "STACK"
    assert labelled.loc[0, S.SCENARIO_ID] == "SC000000"
    assert pd.isna(labelled.loc[2, S.PATTERN_TYPE])
    assert report.matched_transactions == 1


def test_ambiguous_key_is_left_unlabelled_not_guessed(trans_csv, patterns_txt):
    """TX_B belongs to two pattern instances; guessing would corrupt the split.

    Minute-resolution timestamps mean natural keys are not guaranteed unique, so
    this case is real rather than theoretical.
    """
    tx, _ = load_transactions(trans_csv)
    patterns = parse_patterns(patterns_txt)
    labelled, report = attach_patterns(tx, patterns)

    assert report.ambiguous_keys == 1
    assert pd.isna(labelled.loc[1, S.SCENARIO_ID])


def test_attachment_preserves_row_count_and_schema(trans_csv, patterns_txt):
    tx, _ = load_transactions(trans_csv)
    labelled, _ = attach_patterns(tx, parse_patterns(patterns_txt))
    assert len(labelled) == len(tx)
    S.validate_schema(labelled)


def test_report_tracks_positive_coverage(trans_csv, patterns_txt):
    tx, _ = load_transactions(trans_csv)
    _, report = attach_patterns(tx, parse_patterns(patterns_txt))
    meta = report.to_metadata()
    assert meta["total_positives"] == 2
    assert 0.0 <= meta["positive_coverage"] <= 1.0


def test_unterminated_block_is_rejected(tmp_path):
    path = tmp_path / "bad_Patterns.txt"
    path.write_text(f"BEGIN LAUNDERING ATTEMPT - STACK\n{TX_A}\n", encoding="utf-8")
    with pytest.raises(PatternParseError, match="unterminated"):
        parse_patterns(path)


def test_malformed_row_is_rejected(tmp_path):
    path = tmp_path / "bad2_Patterns.txt"
    path.write_text(
        "BEGIN LAUNDERING ATTEMPT - STACK\n1,2,3\nEND LAUNDERING ATTEMPT - STACK\n",
        encoding="utf-8",
    )
    with pytest.raises(PatternParseError, match="expected 11 fields"):
        parse_patterns(path)


def test_empty_file_is_rejected(tmp_path):
    path = tmp_path / "empty_Patterns.txt"
    path.write_text("", encoding="utf-8")
    with pytest.raises(PatternParseError, match="no laundering blocks"):
        parse_patterns(path)
