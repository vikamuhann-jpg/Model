"""Graph Feature Preprocessor features -- the E2 baseline (plan v3 Phase 7).

Wraps IBM's ``snapml.GraphFeaturePreprocessor``, which maintains a
continuous-time dynamic graph internally and emits fan-in/fan-out, degree,
scatter-gather, cycle and vertex-statistics features per edge.

**The insertion-order convention is the whole correctness story** (plan v3
section 12). Features for an edge must be computed against the graph as it stood
*before* that edge was inserted. The sequence per batch is therefore:

    transform(batch)      -> features from history only
    partial_fit(batch)    -> now insert the batch

Doing it the other way round lets a transaction contribute to its own degree,
fan and cycle counts, which inflates exactly the structural signals the
experiment is trying to measure. ``tests/leakage/test_gfp_no_self_inflation.py``
asserts the difference is real rather than theoretical.

Requires Linux -- the Windows snapml wheel has no native GFP backend. See
docs/ADR-001-gfp-platform.md.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.features.base import FeatureExtractor

DAY = 86_400

#: GFP parameter keys are HYPHENATED. The planning documents' prose uses
#: underscores, which set_params rejects with KeyError.
DEFAULT_GFP_PARAMS: dict[str, Any] = {
    "num_threads": 8,
    "time_window": 10 * DAY,
    "vertex_stats": True,
    "vertex_stats_tw": 2 * DAY,
    # Column 4 of the edge array is the amount.
    "vertex_stats_cols": [4],
    "vertex_stats_feats": [0, 1, 2, 3, 4, 8, 9, 10],
    "fan": True,
    "fan_tw": DAY,
    "degree": True,
    "degree_tw": DAY,
    "scatter-gather": True,
    "scatter-gather_tw": 2 * DAY,
    "temp-cycle": True,
    "temp-cycle_tw": 3 * DAY,
    "lc-cycle": True,
    "lc-cycle_tw": 3 * DAY,
    "lc-cycle_len": 10,
}


class VertexIndex:
    """Map account identifiers to the dense integer ids GFP expects."""

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}

    def encode(self, accounts: pd.Series) -> np.ndarray:
        out = np.empty(len(accounts), dtype="int64")
        ids = self._ids
        for i, account in enumerate(accounts.to_numpy()):
            vertex = ids.get(account)
            if vertex is None:
                vertex = len(ids)
                ids[account] = vertex
            out[i] = vertex
        return out

    def __len__(self) -> int:
        return len(self._ids)


@dataclass
class GFPFeatures(FeatureExtractor):
    """Streaming GFP extraction over a chronologically ordered transaction set."""

    family: str = "gfp"
    params: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_GFP_PARAMS))
    #: MUST be 1. Measured: an edge transformed alongside later edges in the
    #: same batch SEES them -- a fan feature reading 1.0 alone reads 4.0 when
    #: batched with three subsequent edges. Anything above 1 therefore leaks
    #: future structure into the present and inflates exactly the graph signals
    #: E2 is meant to measure. At batch_size=1 throughput is ~17,500 tx/s, so
    #: the whole corpus extracts in ~5 minutes; there is no reason to trade
    #: correctness for it.
    batch_size: int = 1
    #: Same-account transfers cannot contribute to inter-account topology and
    #: make up ~12% of HI-Small, so they are kept out of the graph. Their rows
    #: still receive features -- computed against the graph they did not enter.
    exclude_self_transfers: bool = True
    #: Emit a progress line every N transactions; 0 disables. GFP slows as
    #: the graph fills, so a rate measured on an empty graph badly
    #: overestimates the full run.
    progress_every: int = 250_000

    n_engineered_: int | None = None
    n_vertices_: int | None = None
    n_edges_inserted_: int = 0
    extract_seconds_: float | None = None

    def __post_init__(self) -> None:
        super().__init__()
        if self.batch_size != 1:
            warnings.warn(
                f"GFPFeatures(batch_size={self.batch_size}) leaks future edges: "
                "GFP's transform lets an edge see later edges in the same batch. "
                "Use batch_size=1 for any reported result.",
                stacklevel=2,
            )

    def _new_preprocessor(self):
        from snapml import GraphFeaturePreprocessor

        preproc = GraphFeaturePreprocessor()
        preproc.set_params(self.params)
        return preproc

    def _extract(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        """Not used -- GFP is stateful and streams, see :meth:`run_streaming`."""
        raise NotImplementedError(
            "GFPFeatures streams over the whole corpus; call run_streaming()"
        )

    def run_streaming(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        """Extract features for every row, in chronological order.

        ``tx_view`` must be label-free and is sorted internally; the returned
        frame is reindexed to match the input order.
        """
        S.assert_label_blind(tx_view)
        started = time.perf_counter()

        order = tx_view[S.TIMESTAMP].sort_values(kind="stable").index
        ordered = tx_view.loc[order]

        index = VertexIndex()
        source = index.encode(ordered[S.SOURCE_ACCOUNT])
        destination = index.encode(ordered[S.DESTINATION_ACCOUNT])
        timestamps = (
            ordered[S.TIMESTAMP].astype("int64").to_numpy() // 1_000_000_000
        ).astype("float64")
        amounts = ordered[S.AMOUNT].to_numpy(dtype="float64")

        edges = np.column_stack(
            [
                np.arange(len(ordered), dtype="float64"),
                source.astype("float64"),
                destination.astype("float64"),
                timestamps,
                amounts,
            ]
        )

        in_graph = (
            (source != destination)
            if self.exclude_self_transfers
            else np.ones(len(ordered), dtype=bool)
        )

        preproc = self._new_preprocessor()
        n_raw = edges.shape[1]
        total = len(edges)

        # The output buffer is preallocated rather than accumulated. At
        # batch_size=1 a list of per-row arrays would hold ~5M tiny ndarrays,
        # each carrying its own object overhead -- several GB of bookkeeping
        # before vstack even runs, on top of the data itself.
        # float32 also halves the payload: 5M x 215 is 9.3 GB in float64, 4.7 GB
        # here, which is what makes the full corpus fit in the memory budget.
        engineered: np.ndarray | None = None

        for start in range(0, total, self.batch_size):
            stop = min(start + self.batch_size, total)
            batch = edges[start:stop]

            # 1. Features from history only -- BEFORE this batch is inserted.
            transformed = preproc.transform(batch)[:, n_raw:]

            if engineered is None:
                engineered = np.empty((total, transformed.shape[1]), dtype="float32")
            engineered[start:stop] = transformed

            # 2. Now insert, so later batches can see these edges.
            insertable = batch[in_graph[start:stop]]
            if len(insertable):
                preproc.partial_fit(insertable)
                self.n_edges_inserted_ += len(insertable)

            if self.progress_every and start and start % self.progress_every == 0:
                rate = start / (time.perf_counter() - started)
                remaining = (total - start) / rate / 60 if rate else float("nan")
                print(
                    f"    {start:>9,}/{total:,} ({start / total:5.1%})  "
                    f"{rate:>8,.0f} tx/s  ~{remaining:.1f} min left",
                    flush=True,
                )

        if engineered is None:
            raise ValueError("no transactions to extract features from")
        self.n_engineered_ = engineered.shape[1]
        self.n_vertices_ = len(index)
        self.extract_seconds_ = time.perf_counter() - started

        columns = [f"{self.family}_f{i:03d}" for i in range(engineered.shape[1])]
        out = pd.DataFrame(engineered, index=ordered.index, columns=columns)
        return out.reindex(tx_view.index)

    def to_metadata(self) -> dict:
        return {
            "family": self.family,
            "params": self.params,
            "batch_size": self.batch_size,
            "exclude_self_transfers": self.exclude_self_transfers,
            "n_engineered": self.n_engineered_,
            "n_vertices": self.n_vertices_,
            "n_edges_inserted": self.n_edges_inserted_,
            "extract_seconds": self.extract_seconds_,
            "throughput_tx_per_s": (
                None
                if not self.extract_seconds_
                else round(self.n_edges_inserted_ / self.extract_seconds_, 1)
            ),
            "insertion_convention": "transform before partial_fit (v3 s12)",
        }
