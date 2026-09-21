"""XBlock ETH phishing graph -> canonical parquet.

The corpus ships as a pickled NetworkX MultiDiGraph: nodes carry an ``isp`` flag
marking known phishers, edges carry ``amount`` and ``timestamp``. There is no
transaction-level label, which is the fact that shapes every downstream choice --
see :mod:`flowguard.pipeline.run_transfer` and ADR-012.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S


def load_graph(path: Path):
    with Path(path).open("rb") as fh:
        return pickle.load(fh)


def to_frames(graph) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the graph into a canonical transaction frame and an account-label frame.

    Returns ``(transactions, labels)``. ``labels`` has columns ``account_id`` and
    ``is_illicit`` and is the *only* ground truth this corpus provides.
    """
    labels = pd.DataFrame(
        [(n, d.get("isp", 0)) for n, d in graph.nodes(data=True)],
        columns=["account_id", "is_illicit"],
    )

    source, destination, amount, stamp = [], [], [], []
    for s, d, attr in graph.edges(data=True):
        source.append(s)
        destination.append(d)
        amount.append(attr.get("amount", 0.0))
        stamp.append(attr.get("timestamp", 0.0))

    tx = pd.DataFrame(
        {
            S.TRANSACTION_ID: pd.Series(
                [f"E{i:09d}" for i in range(len(source))], dtype="string"
            ),
            S.TIMESTAMP: pd.to_datetime(
                np.asarray(stamp, dtype="float64"), unit="s", utc=True
            ),
            S.SOURCE_ACCOUNT: pd.Series(source, dtype="string"),
            S.DESTINATION_ACCOUNT: pd.Series(destination, dtype="string"),
            S.AMOUNT: np.asarray(amount, dtype="float64"),
            S.CURRENCY: pd.Series("ETH", index=range(len(source)), dtype="string"),
            # The transaction-level label does not exist for this corpus. It is
            # held at 0 so the canonical schema still validates; every reported
            # metric is account-level. Never report is_laundering for ETH.
            S.IS_LAUNDERING: np.int8(0),
        }
    )
    tx = tx.sort_values(S.TIMESTAMP, kind="stable").reset_index(drop=True)
    tx["is_self_transfer"] = (
        tx[S.SOURCE_ACCOUNT] == tx[S.DESTINATION_ACCOUNT]
    ).astype("int8")
    return tx, labels


def convert(raw_pickle: Path, out_dir: Path) -> tuple[Path, Path]:
    """One pass: pickle in, two parquet files out."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tx, labels = to_frames(load_graph(raw_pickle))
    tx_path = out_dir / "ETH_transactions.parquet"
    lb_path = out_dir / "ETH_labels.parquet"
    tx.to_parquet(tx_path, index=False)
    labels.to_parquet(lb_path, index=False)
    return tx_path, lb_path
