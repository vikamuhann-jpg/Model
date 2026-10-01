"""Loader behaviour against the real IBM AML file layout.

Every case here corresponds to a property verified on HI-Small; the fixtures
reproduce the raw layout exactly, including the duplicated ``Account`` header.
"""

from __future__ import annotations

import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.data.loader import (
    LoaderError,
    load_accounts,
    load_transactions,
    make_account_id,
)

RAW_HEADER = (
    "Timestamp,From Bank,Account,To Bank,Account,Amount Received,"
    "Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
)
RAW_ROWS = [
    # self-transfer ("Reinvestment"), the ~12% case on HI-Small
    "2022/09/01 00:20,010,8000EBD30,010,8000EBD30,3697.34,US Dollar,3697.34,US Dollar,Reinvestment,0",
    # ordinary transfer between banks
    "2022/09/01 00:20,03208,8000F4580,001,8000F5340,0.01,US Dollar,0.01,US Dollar,Cheque,0",
    # cross-currency: paid and received legs differ
    "2022/09/01 00:05,0134266,814167590,0036925,810E343A0,132713.46,Yuan,18264.20,Euro,ACH,1",
]


@pytest.fixture
def trans_csv(tmp_path):
    path = tmp_path / "TEST-Small_Trans.csv"
    path.write_text("\n".join([RAW_HEADER, *RAW_ROWS]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def accounts_csv(tmp_path):
    path = tmp_path / "TEST-Small_accounts.csv"
    path.write_text(
        "Bank Name,Bank ID,Account Number,Entity ID,Entity Name\n"
        "Bank A,10,8000EBD30,800062E24,Corporation #1\n"
        "Bank B,3208,8000F4580,800062E25,Partnership #2\n"
        "Bank C,1,8000F5340,800062E26,Corporation #3\n"
        "Bank D,134266,814167590,800062E27,Sole Proprietorship #4\n"
        "Bank E,36925,810E343A0,800062E28,Corporation #5\n",
        encoding="utf-8",
    )
    return path


def test_duplicate_account_header_is_resolved_positionally(trans_csv):
    """The raw header contains 'Account' twice; names cannot disambiguate it."""
    df, _ = load_transactions(trans_csv)
    assert df.loc[1, S.SOURCE_ACCOUNT] == "3208:8000F4580"
    assert df.loc[1, S.DESTINATION_ACCOUNT] == "1:8000F5340"


def test_bank_ids_are_normalised_numerically():
    """Zero-padded transaction bank ids must match unpadded account-file ids.

    Verified on HI-Small: normalising numerically joins all 30,470 banks with
    zero orphans; string comparison matches none.
    """
    padded = make_account_id(pd.Series(["010"]), pd.Series(["ACC"]))
    unpadded = make_account_id(pd.Series(["10"]), pd.Series(["ACC"]))
    assert padded.iloc[0] == unpadded.iloc[0] == "10:ACC"


def test_account_identity_is_bank_scoped():
    """The bare account number is not globally unique -- 8 collisions on HI-Small."""
    a = make_account_id(pd.Series(["10"]), pd.Series(["SHARED"]))
    b = make_account_id(pd.Series(["11"]), pd.Series(["SHARED"]))
    assert a.iloc[0] != b.iloc[0]


def test_self_transfers_are_flagged_not_rejected(trans_csv):
    """~12% of HI-Small is same-account 'Reinvestment'; rejecting it loses real data."""
    df, report = load_transactions(trans_csv)
    assert df.loc[0, S.IS_SELF_TRANSFER] == 1
    assert df.loc[1, S.IS_SELF_TRANSFER] == 0
    assert report.self_transfers == 1


def test_amount_side_paid_is_canonical_and_received_is_retained(trans_csv):
    df, report = load_transactions(trans_csv, amount_side="paid")
    assert df.loc[2, S.AMOUNT] == pytest.approx(18264.20)
    assert df.loc[2, S.CURRENCY] == "Euro"
    assert df.loc[2, S.AMOUNT_RECEIVED] == pytest.approx(132713.46)
    assert df.loc[2, S.CURRENCY_RECEIVED] == "Yuan"
    assert report.cross_currency == 1


def test_amount_side_received_swaps_the_legs(trans_csv):
    df, _ = load_transactions(trans_csv, amount_side="received")
    assert df.loc[2, S.AMOUNT] == pytest.approx(132713.46)
    assert df.loc[2, S.CURRENCY] == "Yuan"
    assert df.loc[2, S.AMOUNT_RECEIVED] == pytest.approx(18264.20)


def test_transaction_ids_are_synthesised_and_unique(trans_csv):
    """The source carries no id, so row position becomes identity."""
    df, report = load_transactions(trans_csv)
    assert df[S.TRANSACTION_ID].is_unique
    assert df.loc[0, S.TRANSACTION_ID] == "TX0000000000"
    assert "row position" in report.to_metadata()["transaction_id_convention"]


def test_timestamps_parse_to_utc(trans_csv):
    df, _ = load_transactions(trans_csv)
    assert df[S.TIMESTAMP].dt.tz is not None
    assert df.loc[0, S.TIMESTAMP] == pd.Timestamp("2022-09-01T00:20:00Z")


def test_output_satisfies_the_canonical_contract(trans_csv):
    df, _ = load_transactions(trans_csv)
    S.validate_schema(df)


def test_wrong_column_count_is_rejected(tmp_path):
    path = tmp_path / "bad_Trans.csv"
    path.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="expected 11 columns"):
        load_transactions(path)


def test_accounts_key_matches_transaction_endpoints(trans_csv, accounts_csv):
    """Zero orphan endpoints is the check that proves the composite key correct."""
    df, _ = load_transactions(trans_csv)
    accounts = load_accounts(accounts_csv)

    endpoints = set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT])
    assert endpoints - set(accounts["account_id"]) == set()


def test_accounts_missing_column_is_rejected(tmp_path):
    path = tmp_path / "bad_accounts.csv"
    path.write_text("Bank Name,Bank ID\nA,1\n", encoding="utf-8")
    with pytest.raises(LoaderError, match="missing column"):
        load_accounts(path)
