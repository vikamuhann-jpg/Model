"""GFP insertion-order and future-edge leakage tests (plan v3 sections 11, 12).

``test_future_edge_invariance`` is the strongest leakage test the plan offers:
extract features for a transaction at time T against a graph that also contains
edges after T, and assert the result is identical to extraction against a graph
truncated at T. Any difference is future information reaching the present.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.features.gfp import GFPFeatures

pytestmark = pytest.mark.leakage

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(rows: list[tuple[str, str, int, float]]) -> pd.DataFrame:
    """Build a label-free transaction view from (src, dst, minute, amount)."""
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:06d}" for i in range(len(rows))],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=m) for _, _, m, _ in rows],
            S.SOURCE_ACCOUNT: [s for s, _, _, _ in rows],
            S.DESTINATION_ACCOUNT: [d for _, d, _, _ in rows],
            S.AMOUNT: [a for _, _, _, a in rows],
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: "ACH",
        }
    )


#: A fan-in onto HUB, then later activity. The early rows must not be able to
#: see the later ones.
ROWS = [
    ("A", "HUB", 0, 100.0),
    ("B", "HUB", 5, 110.0),
    ("C", "HUB", 10, 120.0),
    ("D", "HUB", 15, 130.0),
    ("HUB", "E", 20, 400.0),
    ("E", "A", 25, 380.0),
]


def test_future_edge_invariance():
    """Features for early transactions must not change when later ones exist."""
    full = _frame(ROWS)
    truncated = _frame(ROWS[:3])

    features_full = GFPFeatures(batch_size=1).run_streaming(full)
    features_truncated = GFPFeatures(batch_size=1).run_streaming(truncated)

    overlap = features_truncated.index
    np.testing.assert_array_equal(
        features_full.loc[overlap].to_numpy(),
        features_truncated.to_numpy(),
        err_msg=(
            "features for early transactions changed when later edges were "
            "added -- future information is reaching the present"
        ),
    )


def test_batching_leaks_future_edges_so_batch_size_must_be_one():
    """GFP's transform lets an edge see later edges in its OWN batch.

    This is not an implementation detail -- it is a leakage vector. Measured on
    a 4-edge fan-in: edge 0's fan feature reads 1.0 transformed alone and 4.0
    transformed alongside the three later edges, i.e. it counts transactions
    that have not happened yet.

    The test pins the behaviour so that raising ``batch_size`` for speed cannot
    silently reintroduce it.
    """
    frame = _frame(ROWS)

    alone = GFPFeatures(batch_size=1).run_streaming(frame)
    with pytest.warns(UserWarning, match="leaks future edges"):
        batched = GFPFeatures(batch_size=len(frame)).run_streaming(frame)

    first_alone = alone.iloc[0].to_numpy()
    first_batched = batched.iloc[0].to_numpy()

    assert not np.array_equal(first_alone, first_batched)
    assert first_batched.sum() > first_alone.sum(), (
        "batching did not inflate the first row; the leakage this guard exists "
        "for may have changed behaviour in a new snapml version"
    )


def test_default_batch_size_is_leakage_safe():
    assert GFPFeatures().batch_size == 1


def test_each_edge_enters_the_graph_once():
    """transform() inserts its batch (Snap ML docs). A following partial_fit
    inserted every edge a second time: on this fan-in the last edge's target
    in-degree read 7 instead of 4. Streamed features must equal a reference in
    which each earlier edge was inserted exactly once."""
    frame = _frame(ROWS[:4])
    streamed = GFPFeatures(batch_size=1).run_streaming(frame).iloc[-1].to_numpy()

    from flowguard.features.gfp import VertexIndex

    index = VertexIndex()
    src = index.encode(frame[S.SOURCE_ACCOUNT]).astype("float64")
    dst = index.encode(frame[S.DESTINATION_ACCOUNT]).astype("float64")
    ts = (frame[S.TIMESTAMP].astype("int64").to_numpy() // 1_000_000_000).astype(
        "float64"
    )
    edges = np.column_stack(
        [np.arange(len(frame), dtype="float64"), src, dst, ts,
         frame[S.AMOUNT].to_numpy(dtype="float64")]
    )
    preproc = GFPFeatures()._new_preprocessor()
    preproc.partial_fit(edges[:3])
    reference = preproc.transform(edges[3:])[0, edges.shape[1]:]

    np.testing.assert_array_equal(streamed, reference.astype("float32"))


def test_self_transfers_are_kept_out_of_the_graph():
    """Same-account edges add no inter-account topology (~12% of HI-Small)."""
    rows = [("A", "A", 0, 100.0), ("A", "A", 5, 100.0), ("A", "B", 10, 100.0)]
    frame = _frame(rows)

    extractor = GFPFeatures(batch_size=1, exclude_self_transfers=True)
    extractor.run_streaming(frame)
    assert extractor.n_edges_inserted_ == 1

    keeping = GFPFeatures(batch_size=1, exclude_self_transfers=False)
    keeping.run_streaming(frame)
    assert keeping.n_edges_inserted_ == 3


def test_output_is_row_aligned_to_input():
    """Rows are sorted internally; the result must come back in input order."""
    frame = _frame(ROWS).sample(frac=1.0, random_state=0)
    features = GFPFeatures(batch_size=2).run_streaming(frame)
    assert features.index.equals(frame.index)


def test_labels_are_rejected():
    frame = _frame(ROWS)
    frame[S.IS_LAUNDERING] = 0
    with pytest.raises(Exception, match="is_laundering"):
        GFPFeatures().run_streaming(frame)
