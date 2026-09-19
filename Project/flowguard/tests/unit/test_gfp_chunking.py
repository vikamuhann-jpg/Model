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
