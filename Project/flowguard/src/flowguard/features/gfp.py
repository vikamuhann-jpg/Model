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

import gc
import time
import warnings
from pathlib import Path
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


def windowed_params(window_days: float = 2.0) -> dict[str, Any]:
    """The graph parameters every shipped model was trained with.

    Training and scoring must build graph features identically -- a model scored
    on features computed with a different window receives inputs it never saw,
    and nothing downstream would notice. One definition, used by both.

    The window bounds the internal graph (ADR-006); sub-windows larger than it
    are capped, since the graph holds nothing older to search.
    """
    params = dict(DEFAULT_GFP_PARAMS)
    window = int(window_days * DAY)
    params["time_window"] = window
    for key in ("vertex_stats_tw", "scatter-gather_tw", "temp-cycle_tw", "lc-cycle_tw"):
        params[key] = min(params[key], window)
    return params


def varying_columns(parts: list[Path]) -> tuple[list[str], int]:
    """Columns that are not constant across the whole corpus.

    Accumulates per-column min/max one part at a time so peak memory is a
    single part rather than the whole block.
    """
    lo: dict[str, float] = {}
    hi: dict[str, float] = {}
    for path in parts:
        frame = pd.read_parquet(path)
        for col in frame.columns:
            if col == "_row":
                continue
            values = frame[col].to_numpy()
            cmin, cmax = float(np.nanmin(values)), float(np.nanmax(values))
            lo[col] = min(lo.get(col, cmin), cmin)
            hi[col] = max(hi.get(col, cmax), cmax)
        del frame
        gc.collect()
    return [c for c in lo if hi[c] > lo[c]], len(lo)


def read_varying_chunks(
    chunk_dir: Path, order: pd.Index | None = None
) -> pd.DataFrame:
    """Load only the columns that carry information.

    The naive path -- concatenate every part, then drop constant columns --
    peaks at the full 5M x 215 float32 block plus a copy. That is what OOM'd
    assembly and took WSL down with it. GFP emits a fixed feature block
    regardless of which patterns occur, so a large share of its columns are
    structurally constant here; selecting them out *during* the read rather
    than after is the difference between fitting in memory and not.
    """
    parts = sorted(Path(chunk_dir).glob("part_*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no part files in {chunk_dir}")

    keep, total = varying_columns(parts)
    print(f"  {len(keep)} of {total} GFP features vary; reading only those",
          flush=True)

    frames = [pd.read_parquet(p, columns=["_row"] + keep) for p in parts]
    frame = pd.concat(frames, ignore_index=True).set_index("_row")
    del frames
    gc.collect()
    return frame.reindex(order) if order is not None else frame


def read_chunks(chunk_dir: Path, order: pd.Index | None = None) -> pd.DataFrame:
    """Read part files back as one frame, restoring the original row index.

    ``order`` reorders to the caller's row order in the same pass, rather than
    materialising the concatenation and then copying it again to reindex.
    """
    parts = sorted(Path(chunk_dir).glob("part_*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no part files in {chunk_dir}")
    frame = pd.concat(
        [pd.read_parquet(p) for p in parts], ignore_index=True
    ).set_index("_row")
    if order is not None:
        frame = frame.reindex(order)
    return frame


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
    #: REJECTED OPTIMISATION -- do not enable for any reported result.
    #: The idea was to periodically rebuild the preprocessor from the windowed
    #: edges alone, bounding the vertex set. It is measurably UNSOUND: rebuilt
    #: features differ from continuously-fed ones, so GFP retains state beyond
    #: the windowed edge set. Kept only so the regression test can keep
    #: asserting the defect. See docs/ADR-008-reconstruction-rejected.md.
    rebuild_every: int = 0
    n_rebuilds_: int = 0
    rebuild_seconds_: float = 0.0
    #: Write feature chunks to this directory as they are produced instead of
    #: holding the whole block in RAM. Peak memory becomes one chunk rather
    #: than the full corpus, and -- crucially -- the features survive a crash
    #: in the *assembly* step afterwards, which is what killed the first full
    #: run at 98.5%. It does NOT make extraction resumable: GFP's Python
    #: wrapper exposes no way to serialise the graph, so a crash *during*
    #: extraction still means starting over. See docs/ADR-009.
    chunk_dir: Path | None = None
    #: Rows per part file. 250k x 215 float32 is ~215 MB per part.
    chunk_rows: int = 250_000
    n_parts_written_: int = 0

    n_engineered_: int | None = None
    n_vertices_: int | None = None
    n_edges_inserted_: int = 0
    extract_seconds_: float | None = None

    def __post_init__(self) -> None:
        super().__init__()
        if self.rebuild_every:
            warnings.warn(
                "GFPFeatures(rebuild_every>0) is UNSOUND: rebuilt features do "
                "not match continuously-fed ones (docs/ADR-008). Never use it "
                "for a reported result.",
                stacklevel=2,
            )
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
        window_seconds = float(self.params.get("time_window", 0) or 0)
        last_rebuild = 0

        # The output buffer is preallocated rather than accumulated. At
        # batch_size=1 a list of per-row arrays would hold ~5M tiny ndarrays,
        # each carrying its own object overhead -- several GB of bookkeeping
        # before vstack even runs, on top of the data itself.
        # float32 also halves the payload: 5M x 215 is 9.3 GB in float64, 4.7 GB
        # here, which is what makes the full corpus fit in the memory budget.
        engineered: np.ndarray | None = None

        # Chunked mode: accumulate one part at a time and flush to disk.
        chunk_buffer: np.ndarray | None = None
        chunk_start = 0
        if self.chunk_dir is not None:
            self.chunk_dir.mkdir(parents=True, exist_ok=True)
            for stale in self.chunk_dir.glob("part_*.parquet"):
                stale.unlink()

        for start in range(0, total, self.batch_size):
            stop = min(start + self.batch_size, total)
            batch = edges[start:stop]

            # 1. Features from history only -- BEFORE this batch is inserted.
            transformed = preproc.transform(batch)[:, n_raw:]

            if self.chunk_dir is not None:
                if chunk_buffer is None:
                    chunk_buffer = np.empty(
                        (min(self.chunk_rows, total), transformed.shape[1]),
                        dtype="float32",
                    )
                offset = start - chunk_start
                chunk_buffer[offset : offset + (stop - start)] = transformed
                if offset + (stop - start) >= len(chunk_buffer) or stop == total:
                    filled = offset + (stop - start)
                    self._flush_chunk(
                        chunk_buffer[:filled], ordered.index[chunk_start:stop]
                    )
                    chunk_start = stop
                    remaining = total - chunk_start
                    chunk_buffer = (
                        None
                        if remaining <= 0
                        else np.empty(
                            (min(self.chunk_rows, remaining), transformed.shape[1]),
                            dtype="float32",
                        )
                    )
            else:
                if engineered is None:
                    engineered = np.empty(
                        (total, transformed.shape[1]), dtype="float32"
                    )
                engineered[start:stop] = transformed

            # 2. Now insert, so later batches can see these edges.
            insertable = batch[in_graph[start:stop]]
            if len(insertable):
                preproc.partial_fit(insertable)
                self.n_edges_inserted_ += len(insertable)

            # Rebuild on a bounded vertex set. Replay runs against a near-empty
            # graph -- the fast regime -- so the cost is small relative to the
            # decay it avoids.
            if (
                self.rebuild_every
                and window_seconds > 0
                and start - last_rebuild >= self.rebuild_every
                and start > 0
            ):
                rebuild_started = time.perf_counter()
                cutoff = timestamps[stop - 1] - window_seconds
                # Edges are in chronological order, so the live window is a
                # contiguous tail of everything inserted so far.
                first_live = int(np.searchsorted(timestamps[:stop], cutoff, "left"))
                live = edges[first_live:stop][in_graph[first_live:stop]]
                preproc = self._new_preprocessor()
                if len(live):
                    preproc.partial_fit(live)
                last_rebuild = start
                self.n_rebuilds_ += 1
                self.rebuild_seconds_ += time.perf_counter() - rebuild_started

            if self.progress_every and start and start % self.progress_every == 0:
                rate = start / (time.perf_counter() - started)
                remaining = (total - start) / rate / 60 if rate else float("nan")
                print(
                    f"    {start:>9,}/{total:,} ({start / total:5.1%})  "
                    f"{rate:>8,.0f} tx/s  ~{remaining:.1f} min left",
                    flush=True,
                )

        if self.chunk_dir is not None:
            self.n_vertices_ = len(index)
            self.extract_seconds_ = time.perf_counter() - started
            print(
                f"  wrote {self.n_parts_written_} parts to {self.chunk_dir}",
                flush=True,
            )
            # Release everything extraction needed BEFORE assembling. The graph
            # alone is several GB by the end, and holding it while concatenating
            # the parts and reordering them is what put the first run over the
            # ceiling at 98.5%. Chunked writes bound the extraction phase; this
            # bounds the assembly phase.
            del preproc, edges, ordered, source, destination, timestamps, amounts
            del in_graph, chunk_buffer
            gc.collect()
            return read_chunks(self.chunk_dir, order=tx_view.index)

        if engineered is None:
            raise ValueError("no transactions to extract features from")
        self.n_engineered_ = engineered.shape[1]
        self.n_vertices_ = len(index)
        self.extract_seconds_ = time.perf_counter() - started

        columns = [f"{self.family}_f{i:03d}" for i in range(engineered.shape[1])]
        out = pd.DataFrame(engineered, index=ordered.index, columns=columns)
        return out.reindex(tx_view.index)

    def _flush_chunk(self, block: np.ndarray, index: pd.Index) -> None:
        """Write one part file. Carries its own row index so order survives."""
        if self.n_engineered_ is None:
            self.n_engineered_ = block.shape[1]
        frame = pd.DataFrame(
            block,
            index=index,
            columns=[f"{self.family}_f{i:03d}" for i in range(block.shape[1])],
        )
        frame.index.name = "_row"
        path = self.chunk_dir / f"part_{self.n_parts_written_:05d}.parquet"
        frame.reset_index().to_parquet(path, index=False)
        self.n_parts_written_ += 1

    def to_metadata(self) -> dict:
        return {
            "family": self.family,
            "params": self.params,
            "chunk_dir": str(self.chunk_dir) if self.chunk_dir else None,
            "chunk_rows": self.chunk_rows if self.chunk_dir else None,
            "n_parts_written": self.n_parts_written_,
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
            "rebuild_every": self.rebuild_every,
            "n_rebuilds": self.n_rebuilds_,
            "rebuild_seconds": round(self.rebuild_seconds_, 1),
        }
