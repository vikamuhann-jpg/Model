# ADR-009 — Chunked feature persistence, and why extraction still cannot resume

**Status:** Accepted
**Date:** 2026-09-19
**Decision:** Stream GFP features to disk as numbered part files during extraction, and
treat those parts as the cache. Extraction is **not** resumable, and this ADR records why
that is a property of the library rather than a gap in the implementation.

---

## What went wrong

The first full extraction ran for **2 hours 30 minutes**, reached **98.5%**, and was
killed by the kernel:

```
Out of memory: Killed process 25386 (python)
total-vm:21481180kB, anon-rss:11743332kB
```

Nothing was recovered. The cache was written *after* extraction completed, so a failure
in the final assembly discarded the entire run.

The arithmetic, against a 12 GB WSL ceiling:

| Live object at the moment of death | Size |
|---|---:|
| Preallocated feature block, 5,077,237 × 215 float32 | 4.4 GB |
| GFP internal graph, fully populated | ~3 GB |
| `pd.DataFrame(engineered, …)` copy | 4.4 GB |
| `.reindex()` copy | 4.4 GB |

## The fix

`GFPFeatures.chunk_dir` writes each block of `chunk_rows` (default 250,000) to
`part_00042.parquet` as it is produced. Each part carries its own row index, so ordering
survives independently of the file order.

Measured effect during extraction: **3.43 GB at 24.6%**, against ~5.0 GB at the same
point on the previous run.

### The second half of the bug, found while reviewing the fix

Chunking bounded the *extraction* phase but not the *assembly* phase. Reading the parts
back still concatenated 4.4 GB and reordered it while **the graph was still referenced** —
and `run_graph` then wrote a monolithic 4.4 GB parquet on top of that. The same ~12 GB
peak, merely deferred to the end.

Both halves are now closed:

* the graph, edge array and working buffers are released **before** assembly begins;
* reordering happens in the same pass as the concatenation rather than as a second copy;
* **the part files are the cache.** No monolithic parquet is written; it would double the
  disk and reintroduce the peak that chunking exists to remove.

## What this does and does not buy

| Failure point | Recoverable? |
|---|---|
| **Assembly step** — where the first run actually died | **Yes.** Parts are already on disk and `read_chunks()` reconstructs the frame without re-extracting |
| Crash *during* extraction | **No.** Start over |

## Why resume is impossible, not merely unimplemented

The obvious next step is to restart at part *N* and skip the earlier ones. That is
**wrong**, and wrong in the same way [ADR-008](ADR-008-reconstruction-rejected.md)
already caught: the preprocessor's graph state was built by streaming parts 0…N−1 through
it. Skipping them produces a different graph and therefore different features.

Genuine resume would need the graph itself serialised. The native library exports the
symbols — `gf_export_graph` and `gf_import_graph` are both present in
`libsnapmllocal3.so` — but the Python wrapper exposes neither. Its public surface is:

```
fit, fit_transform, partial_fit, transform, get_params, set_params
```

There is no supported path to the graph state. Reaching the symbols directly via `ctypes`
would mean depending on an undocumented ABI for a correctness-critical component, and
after ADR-008 it would also need its own byte-identity test before it could be trusted —
the same test reconstruction already failed.

So resume is deferred, not attempted.

## Consequences

* Peak memory during extraction is one part (~215 MB) plus the graph, instead of the whole
  corpus plus the graph.
* A crash in assembly, or in anything downstream, costs seconds rather than hours.
* Extraction still takes ~2.5 hours and gate **P8 still fails** at steady state. ADR-008
  left throughput unsolved and this does not address it.
* Downstream consumers take a **directory**, not a file. `--gfp-cache` now points at
  `HI-Small_gfp_w2_parts/`.
* Parts are cleared at the start of each run, so a previous run's output can never be
  mixed into a new one — asserted by `test_stale_parts_are_cleared`.

## The invariant that makes this safe

`tests/unit/test_gfp_chunking.py` asserts chunked output is **byte-identical** to the
in-memory path at three chunk sizes, under shuffled input order, plus recovery through
`read_chunks()` without re-extraction. Chunking is a persistence detail; if it ever
changes a feature value, it is a defect, not a trade-off.

## An operational note worth keeping

The first relaunch after this fix appeared to succeed and did not. A `pkill` issued
through `cmd → wsl → bash -c` had its quoting mangled, so the old process survived while
the new one failed to open its log. The old process then ran for ten minutes writing into
a deleted directory, looking healthy by every indirect signal.

**Kill long-running jobs by PID and confirm the kill, rather than trusting a pattern
match through three layers of shell quoting.** Verify with the process table, not with the
absence of an error.

## Revisit if

The snapml wrapper exposes graph serialisation, at which point resume becomes possible —
gated on a byte-identity test before it is trusted.
