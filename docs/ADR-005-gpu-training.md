# ADR-005 — GPU training, and the early-stopping trap that comes with it

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Train XGBoost on the GPU (`device="auto"` → `cuda`), with
`early_stopping_rounds=100`. Record the device in every experiment record, and never
compare experiments trained on different devices.

---

## Context

Hardware available: **NVIDIA GeForce RTX 5060 Laptop, 8 GB, compute capability 12.0**,
visible inside WSL2 through `/usr/lib/wsl/lib/libcuda.so.1`. The installed
`xgboost==3.4.1` reports `USE_CUDA: True` on CUDA 13.3, which covers Blackwell.

A synthetic 400k × 60 fit ran 69.5 s on CPU and 1.80 s on GPU, so the speedup is real.

## What went wrong first

Switching E1 to GPU moved PR-AUC from **0.0424 to 0.0357** — a 16% drop. Two things had
been changed at once (`DMatrix` → `QuantileDMatrix`, and CPU → GPU), so the cause was
unattributed. Varying one at a time:

| device | matrix | PR-AUC | best_iteration | secs |
|---|---|---:|---:|---:|
| cpu | DMatrix | 0.0461 | 119 | 101.1 |
| cpu | QuantileDMatrix | 0.0461 | 119 | 102.5 |
| cuda | DMatrix | 0.0371 | 80 | 3.6 |
| cuda | QuantileDMatrix | 0.0362 | 54 | 3.7 |

The matrix type is irrelevant. The **device** cost ~22% PR-AUC.

## Root cause

Not the GPU's arithmetic — **early stopping**. Raising `max_bin` (256 → 512 → 1024)
changed nothing (0.0371 / 0.0359 / 0.0368), ruling out histogram resolution. Disabling
early stopping recovered almost everything:

| device | `early_stopping_rounds` | PR-AUC | best_iteration | secs |
|---|---|---:|---:|---:|
| cpu | 30 | 0.0461 | 119 | 59.9 |
| cuda | 30 | 0.0371 | 80 | 2.8 |
| **cuda** | **100** | **0.0452** | 220 | **5.5** |
| cuda | 200 | 0.0452 | 220 | 5.4 |
| cuda | none | 0.0452 | 299 | 5.4 |
| cpu | none | 0.0460 | 299 | 114.8 |

GPU hist yields a flatter early validation curve on this imbalance — **2,856 positives
in 3,554,066 training rows** — so 30 rounds of patience trips a stop around iteration 80
while the model is still improving through ~220. The CPU curve improves steadily enough
that 30 rounds never trips early.

The failure is silent: training completes, metrics look plausible, and the model is
simply undertrained.

## Decision

* `device` defaults to `"auto"` — GPU when usable, CPU otherwise, with the resolved
  device recorded as `device_used`.
* `early_stopping_rounds` defaults to **100**.
* `QuantileDMatrix` is retained — not for accuracy, which it does not affect, but
  because it bins up front rather than materialising the dense matrix, which is what
  keeps 5M × ~230 float32 inside 8 GB of VRAM.
* Prediction sets the booster device to CPU, avoiding XGBoost's device-mismatch
  fallback warning on every call.

## Is the residual gap real? No.

The single-seed comparison above (CPU 0.0461 vs GPU 0.0452 at seed 42) suggested a
persistent ~2% CPU advantage. **It does not survive repetition.** Five seeds per device,
`early_stopping_rounds=100` throughout:

| device | mean PR-AUC | sd | min | max |
|---|---:|---:|---:|---:|
| GPU | **0.0452** | 0.0021 | 0.0433 | 0.0485 |
| CPU | 0.0449 | 0.0014 | 0.0435 | 0.0465 |

Device gap (CPU − GPU means): **−0.0003**, against a pooled seed sd of **0.0017**. The
gap is inside the noise, and points the *opposite* way from the single-seed result — GPU
is fractionally ahead on average. There is no accuracy reason to prefer CPU.

The lesson generalises past this decision: on this dataset a single run is worth
±0.002 PR-AUC of nothing, so no comparison between configurations means anything until
it is repeated across seeds.

### The number this fixes for the rest of the project

Seed sd ≈ **0.0017**, so the 2σ inclusion criterion gates P1/P3 depend on is
**≈ 0.0034 PR-AUC**. A feature family — graph features included — must beat its
baseline by more than that to count as a real improvement rather than a lucky seed.
Against an E1 of ~0.045 that is an ~8% relative improvement, which is a demanding but
honest bar.

## Consequences

* E1 training: **~60 s → ~5 s**, an 11× speedup, with no measurable accuracy cost.
* **Inference device is irrelevant.** Training fixes the tree structure; prediction just
  walks it. Verified on a GPU-trained model: GPU and CPU inference give PR-AUC
  identical to six decimal places (max prediction difference 1.19e-07, float32
  rounding). Training on GPU and serving on CPU is therefore free — and gains nothing.
* **Gate P6 passes on both devices** (sd 0.0021 GPU, 0.0014 CPU, threshold 0.02).
* Keep the device constant within a comparison anyway. The bias is not measurable here,
  but `device_used` is recorded per experiment so a future mixed comparison is at least
  detectable.
* **GFP feature extraction cannot use the GPU.** `snapml`'s
  `GraphFeaturePreprocessor` is a CPU C++ implementation; the `gf_*` symbols live in
  `libsnapmllocal3.so` and have no CUDA path. Extraction is the slower half of E2 and
  stays CPU-bound, so the end-to-end speedup is far smaller than 11×.
* `QuantileDMatrix` is retained — not for accuracy, which it demonstrably does not
  affect, but because it bins up front rather than materialising the dense matrix,
  which keeps 5M × ~230 float32 inside 8 GB of VRAM.
* The 8 GB VRAM ceiling is the binding constraint for larger variants. HI-Medium
  (32M transactions) will not fit and must train on CPU or in batches.

## Revisit if

A variant exceeds 8 GB of VRAM, or a future XGBoost release changes the GPU hist
algorithm — in which case the seed study should be repeated rather than assumed.
