# ADR-001 — Execution platform for the Graph Feature Preprocessor baseline

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Run the FlowGuard pipeline on **Linux (WSL2 Ubuntu 24.04) with CPython 3.12
and `snapml==1.17.2`**. Windows is not a supported execution target for Track R.

---

## Context

Every plan in `docs/` builds its M2/E2 baseline on IBM's **Graph Feature Preprocessor
(GFP)**, shipped in the `snapml` package. `start.txt` §4 explicitly instructs verifying
that GFP is installable and recording its version before claiming reproduction. That
verification had never been run. The development machine is Windows 11.

## Investigation

Performed before any pipeline code was written, because every downstream phase depends
on the answer.

| Step | Finding |
|---|---|
| `pip install snapml` on CPython 3.14 | Fails — no matching distribution |
| snapml wheels for Windows | Only `1.15.6`, and only `cp311` |
| snapml wheels for Linux | `1.17.2`, `manylinux_2_28_x86_64`, cp39–cp312 |
| snapml wheels for macOS | `1.17.2`, `macosx_10_13_x86_64` |
| Latest snapml version | **1.17.2** (not 1.15.6, which is Windows-only and stale) |

Installing `snapml==1.15.6` on Windows/cp311 succeeded, and
`snapml/GraphFeaturePreprocessor.py` was present — but constructing it failed:

```
AttributeError: module 'snapml.libsnapmllocal3_avx2' has no attribute 'gf_allocate'
```

Scanning every native binary in both wheels for `gf_*` symbols:

| Wheel | `gf_*` symbols |
|---|---:|
| `snapml-1.15.6-cp311-win_amd64` (all 6 `.pyd`) | **0** |
| `snapml-1.17.2-cp312-manylinux_2_28_x86_64` → `libsnapmllocal3.so` | **8** |

The Linux binary exports the full API: `gf_allocate`, `gf_set_params`, `gf_partial_fit`,
`gf_transform`, `gf_get_num_engineered_features`, `gf_get_output_array_dims`,
`gf_import_graph`, `gf_export_graph`.

**Conclusion:** the Windows wheel ships the Python wrapper without its C++ backend. GFP
is not merely awkward on Windows — it is absent. No amount of version pinning fixes it.

## Decision

Run on WSL2 Ubuntu 24.04 / CPython 3.12 / `snapml==1.17.2`.

This was chosen over the alternative — re-implementing the GFP feature families in
NetworkX and labelling the baseline "GFP-inspired" per `start.txt` §4 — because the real
GFP is available at no accuracy or fidelity cost, and a genuine reproduction is a
materially stronger research claim than an approximation of one.

## Consequences

* **Verified working.** 6 toy edges → 215 engineered features per edge. The
  cycle-closing edge of a 1→2→3→1 round-trip carries 24 non-zero engineered features;
  a fan-in edge carries 16. The streaming `partial_fit` → `transform` path returns the
  same feature width as `fit_transform`, which is what the insertion-order convention
  in plan v3 §12 requires.
* **GFP parameter keys are hyphenated**, not underscored: `scatter-gather`, `temp-cycle`,
  `lc-cycle` (and `lc-cycle_len`, `scatter-gather_tw`, …). `set_params` raises
  `KeyError` on unknown keys, so this is fail-fast rather than silent. Any config or
  code written from the plan documents' prose will use the wrong names.
* **`libgomp.so.1` is required** and is not present in this WSL image. It is satisfied
  from the copy vendored in the scikit-learn wheel, installed to
  `/usr/lib/x86_64-linux-gnu/`. Note that `ldconfig` indexes by SONAME — which in the
  vendored copy is `libgomp-<hash>.so.1.0.0` — so installing it to `/usr/local/lib` does
  **not** work; it must sit in a default search path under the exact filename.
* **xgboost on Linux declares `nvidia-nccl-cu13`**, needed only for multi-GPU. This
  project is CPU-bound, so xgboost is installed with `--no-deps`.
* **Track P is unaffected.** A FastAPI/Streamlit layer can run on either platform; only
  the GFP feature-extraction step is Linux-bound.
* **The 16 GB host gives WSL 7.6 GiB by default.** This needs raising via `.wslconfig`
  before touching AML HI Small (5 M edges). See the open item in `docs/README.md`.

## Revisit if

IBM ships a Windows wheel containing the `gf_*` symbols, or the project abandons GFP as
its baseline.
