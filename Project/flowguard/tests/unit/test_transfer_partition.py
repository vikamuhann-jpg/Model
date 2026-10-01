"""The account-disjoint partition that makes the Tier C proxy trustworthy.

The proxy label ("an endpoint is a known phisher") is derived from the same
account truth that defines the test metric. Without a partition, an account
would contribute its label to training and then be scored from it -- and because
graph features describe structural position, a persistent hub could be
memorised through them. See ADR-012.

These tests check the property the protocol depends on: the two sides never
share an account, and the assignment does not move between runs.
"""

from __future__ import annotations

import pandas as pd

from flowguard.pipeline.run_transfer import partition_accounts


def _labels(n: int = 400) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account_id": [f"0x{i:040x}" for i in range(n)],
            "is_illicit": [1 if i % 10 == 0 else 0 for i in range(n)],
        }
    )


def test_sides_are_disjoint():
    """The whole point: no account may appear on both sides."""
    parts = partition_accounts(_labels())
    train = set(parts.loc[parts.side == "train", "account_id"])
    held = set(parts.loc[parts.side == "eval", "account_id"])
    assert train & held == set()
    assert train | held == set(parts.account_id)


def test_assignment_is_stable_across_calls():
    """Hashed, not shuffled -- so the three seed repeats differ only in the model."""
    first = partition_accounts(_labels())
    second = partition_accounts(_labels())
    assert first.side.equals(second.side)


def test_eval_fraction_is_approximately_honoured():
    parts = partition_accounts(_labels(2000), eval_fraction=0.30)
    share = (parts.side == "eval").mean()
    assert 0.25 < share < 0.35, f"eval side took {share:.1%}, expected ~30%"


def test_both_sides_receive_illicit_accounts():
    """A partition that starved either side would make the experiment meaningless."""
    parts = partition_accounts(_labels())
    illicit = parts[parts.is_illicit == 1]
    assert (illicit.side == "train").sum() > 0
    assert (illicit.side == "eval").sum() > 0


def test_input_frame_is_not_mutated():
    labels = _labels(50)
    partition_accounts(labels)
    assert "side" not in labels.columns
