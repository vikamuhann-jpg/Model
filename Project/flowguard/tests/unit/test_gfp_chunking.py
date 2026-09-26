"""Chunked feature persistence (Tier S2).

The first full extraction was OOM-killed at 98.5% after 2.5 hours: the whole
5M x 215 float32 block was held in RAM, and the final `DataFrame(...)` plus
`reindex()` copied it twice more. Chunking writes each part to disk as it is
produced, so peak memory is one part and the features survive a crash in the
assembly step.

It is a memory fix, not a resume fix. GFP's Python wrapper exposes no way to
serialise the graph, so a crash *during* extraction still means starting over
(docs/ADR-009).

The invariant that matters: chunking must be a persistence detail and change no
feature value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.features.gfp import DAY, DEFAULT_GFP_PARAMS, GFPFeatures, read_chunks

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(n: int = 120, accounts: int = 20, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    src = rng.integers(0, accounts, n)
    dst = (src + rng.integers(1, accounts, n)) % accounts
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:06d}" for i in range(n)],
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=30 * i) for i in range(n)],
            S.SOURCE_ACCOUNT: [f"A{v}" for v in src],
            S.DESTINATION_ACCOUNT: [f"A{v}" for v in dst],
            S.AMOUNT: np.round(rng.lognormal(6, 1, n), 2),
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: "ACH",
        }
    )


def _params() -> dict:
    params = dict(DEFAULT_GFP_PARAMS)
    params["num_threads"] = 1  # see test_gfp_reconstruction for why
    window = int(2 * DAY)
    params["time_window"] = window
    for key in ("vertex_stats_tw", "scatter-gather_tw", "temp-cycle_tw", "lc-cycle_tw"):
        params[key] = min(params[key], window)
    return params


def test_chunked_output_matches_in_memory(tmp_path):
    """The decisive test: persistence must not change any value."""
    frame = _frame()
    params = _params()

    in_memory = GFPFeatures(params=params, progress_every=0).run_streaming(frame)
    chunked = GFPFeatures(
        params=params, progress_every=0, chunk_dir=tmp_path / "parts", chunk_rows=37
    ).run_streaming(frame)

    assert list(chunked.columns) == list(in_memory.columns)
    np.testing.assert_array_equal(
        chunked.to_numpy(),
        in_memory.to_numpy(),
        err_msg="chunking changed feature values; it must be persistence only",
    )


def test_row_order_is_preserved(tmp_path):
    """Rows are sorted internally; the result must return in input order."""
    frame = _frame().sample(frac=1.0, random_state=1)
    chunked = GFPFeatures(
        params=_params(), progress_every=0,
        chunk_dir=tmp_path / "parts", chunk_rows=40,
    ).run_streaming(frame)

    assert chunked.index.equals(frame.index)


@pytest.mark.parametrize("chunk_rows", [17, 50, 500])
def test_result_is_independent_of_chunk_size(tmp_path, chunk_rows):
    """A chunk larger than the corpus must behave like no chunking at all."""
    frame = _frame()
    params = _params()
    reference = GFPFeatures(params=params, progress_every=0).run_streaming(frame)

    chunked = GFPFeatures(
        params=params, progress_every=0,
        chunk_dir=tmp_path / f"parts_{chunk_rows}", chunk_rows=chunk_rows,
    ).run_streaming(frame)

    np.testing.assert_array_equal(chunked.to_numpy(), reference.to_numpy())


def test_parts_are_written_and_readable(tmp_path):
    """Parts on disk are the artifact that survives an assembly-step crash."""
    out = tmp_path / "parts"
    extractor = GFPFeatures(
        params=_params(), progress_every=0, chunk_dir=out, chunk_rows=40
    )
    result = extractor.run_streaming(_frame(n=120))

    parts = sorted(out.glob("part_*.parquet"))
    assert len(parts) == 3
    assert extractor.n_parts_written_ == 3

    # Recoverable without re-running extraction.
    recovered = read_chunks(out)
    assert len(recovered) == len(result)
    np.testing.assert_array_equal(
        recovered.loc[result.index].to_numpy(), result.to_numpy()
    )


def test_stale_parts_are_cleared(tmp_path):
    """A previous run's parts must never be mixed into a new one."""
    out = tmp_path / "parts"
    out.mkdir(parents=True)
    (out / "part_00000.parquet").write_bytes(b"not a parquet file")

    GFPFeatures(
        params=_params(), progress_every=0, chunk_dir=out, chunk_rows=60
    ).run_streaming(_frame(n=120))

    assert read_chunks(out).shape[0] == 120


def test_read_chunks_rejects_an_empty_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="no part files"):
        read_chunks(tmp_path)


def test_chunking_is_off_by_default():
    assert GFPFeatures().chunk_dir is None


@pytest.mark.filterwarnings("ignore:GFPFeatures\\(batch_size")
def test_batches_never_straddle_part_files(tmp_path):
    """chunk_rows=37 is not a multiple of 8; a batch used to overflow the part
    buffer (ValueError: could not broadcast) on the first boundary it crossed."""
    extractor = GFPFeatures(
        params=_params(), progress_every=0, batch_size=8,
        chunk_dir=tmp_path / "parts", chunk_rows=37,
    )
    assert extractor.chunk_rows % 8 == 0
    assert extractor.run_streaming(_frame(n=120)).shape[0] == 120


def test_a_half_written_cache_is_not_reused_as_if_it_were_complete(tmp_path):
    """A killed extraction leaves valid parts covering a prefix of the corpus.

    They are indistinguishable from a finished cache by existence alone, and
    `read_varying_chunks(order=...)` reindexes to the full frame -- so the rows
    that were never extracted come back as NaN features instead of as an error.
    A real run hit this: 8 parts of ~28 were accepted, and the next step would
    have trained on NaN for 70% of the corpus.
    """
    from flowguard.pipeline.run_benchmark import _rows_in_cache, gfp_block

    rows = 40
    frame = pd.DataFrame({
        S.TRANSACTION_ID: [f"TX{i:04d}" for i in range(rows)],
        S.TIMESTAMP: pd.date_range("2022-09-01", periods=rows, freq="min", tz="UTC"),
        S.SOURCE_ACCOUNT: [f"A{i % 7}" for i in range(rows)],
        S.DESTINATION_ACCOUNT: [f"B{i % 5}" for i in range(rows)],
        S.AMOUNT: np.linspace(10.0, 500.0, rows),
        S.IS_SELF_TRANSFER: np.zeros(rows, dtype="int8"),
        S.IS_LAUNDERING: np.zeros(rows, dtype="int8"),
    })
    cache = tmp_path / "parts"

    full, _ = gfp_block(frame, cache, batch_size=1, window_days=None)
    assert _rows_in_cache(cache) == rows
    assert not full.isna().all(axis=1).any(), "a complete cache should cover every row"

    # Simulate the interrupted run. The real one left 8 whole parts of ~28; at
    # this size everything fits one part, so truncate that part's rows instead --
    # what matters to the check is rows covered, not files present.
    part = sorted(cache.glob("part_*.parquet"))[0]
    pd.read_parquet(part).iloc[: rows // 4].to_parquet(part, index=False)
    truncated = _rows_in_cache(cache)
    assert 0 < truncated < rows, "the fixture needs a genuinely partial cache"

    again, _ = gfp_block(frame, cache, batch_size=1, window_days=None)

    assert _rows_in_cache(cache) == rows, "the partial cache must be re-extracted"
    assert not again.isna().all(axis=1).any(), "no row may come back all-NaN"
    pd.testing.assert_frame_equal(full, again)
