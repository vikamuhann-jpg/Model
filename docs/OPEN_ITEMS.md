# FlowGuard — Open Items, Solutions and Timings

**Date:** 2026-09-18
**Purpose:** Everything outstanding, what I propose to do about it, and how long each
takes — separated into *compute time* (machine) and *build time* (writing the code).

Committing is deliberately excluded; it stays on hold.

---

## 0. Where the project actually stands

*Updated after the autonomous build session.*

| | |
|---|---|
| Code | 5,777 lines / 37 modules |
| Tests | 1,593 lines / 12 files, **117 passing** |
| Leakage tests | **All 7 required by v3 §11 implemented** |
| ADRs | 7 |
| Experiments logged | E0, E1, ABLATION |
| Uncommitted | yes — nothing committed yet |

### The result that reframed the project

A five-seed ablation on the tabular baseline:

| Arm | Features | PR-AUC | Recall @1% |
|---|---:|---:|---:|
| A1 — `payment_type` included | 13 | 0.0416 ± 0.0030 | 41.0% |
| A2 — `payment_type` **removed** | 12 | **0.0066 ± 0.0003** | **12.1%** |

**84% of the tabular baseline's performance was a simulator artifact.** 2,553 of 2,554
annotated pattern transactions are ACH, so "is ACH" nearly identifies an injected
pattern ([ADR-007](ADR-007-payment-type-artifact.md)). The honest baseline is 0.0066, a
5.5× lift — not the 35.7× first reported.

This was surfaced by gate C8 (no feature above 50% of mean |SHAP|) firing at 56.8%, and
it is the strongest argument in the project for the gate discipline actually earning its
cost.

### Now done

* Ingestion, canonical schema, validation, chronological split — all gated
* Complete leakage suite, including `test_future_edge_invariance`
* Rolling-origin hyperparameter search (`models/tuning.py`)
* Thresholds with recorded provenance, SHAP interpretation, temporal stability, PSI/KS
  drift, cost profiling
* Hard-negative and unseen-pattern splits
* Validation-gate framework C1–C8 / P1–P9 and the model-package writer
* Ablation runner with per-arm seed repeats
* Published visual report

### Still open

1. **E2 extraction is running** — the 2-day window, ~35% through. The 10-day window was
   abandoned after 47 minutes ([ADR-006](ADR-006-gfp-time-window.md)).
2. **E2 vs A2 is the comparison that matters** — against the artifact-free baseline of
   0.0066, not the inflated 0.0416.
3. **P4 recall gate** — 41.1% with the artifact, 12.1% without, against a 45% target.
   The target needs restating against the artifact-free baseline.
4. **No cross-dataset validation.** ADR-007 makes this the most important gap: a real
   network is the only way to show the result is not simulator-specific.
5. **E3–E7 feature families** — still gated on the error analysis, by design.

## 1. Blocking — must be resolved before any further result is trustworthy

### 1.1 E2 is still extracting, and the cause is a parameter I chose badly

**Problem.** I set GFP's `time_window` to 10 days — the entire corpus. The internal graph
therefore **never evicts**: every one of 4.49M `transform` calls searches a structure
that keeps growing, and cycle detection degrades superlinearly. My 17,500 tx/s benchmark
was taken on a near-empty graph and overestimated the full run by roughly an order of
magnitude. 39 minutes in and still going.

**Solution.** Let the current run finish so a 10-day number exists, then re-extract at
2-day and 5-day windows. A tighter window is not a compromise — it is *more* defensible
operationally, because no real-time system holds ten days of full graph to score one
payment. This doubles as the window-sensitivity study v3 §26.3 requires anyway.

| | |
|---|---|
| Compute | 10–30 min to finish, then ~15 min per additional window (est.) |
| Build | none — a config change |
| Risk | the 10-day run may still be an hour out; cap it and move on if so |

### 1.2 E1 and E2 will have been trained on different devices

**Problem.** E1 in the registry was trained on CPU with `early_stopping_rounds=30`; the
in-flight E2 uses the same stale settings. Current defaults are GPU with patience 100.
Comparing across that boundary mixes a configuration change into the very delta being
measured.

**Solution.** Once the GFP cache lands, re-run E0/E1/E2 in one pass off the cache, all on
GPU with patience 100. Re-runs are cheap because extraction is cached.

| | |
|---|---|
| Compute | ~3 min total |
| Build | none |

### 1.3 Three required leakage tests do not exist

**Problem.** v3 §11 lists seven; four exist. Missing: `test_encoder_fit_scope`,
`test_threshold_source`, `test_label_shuffle_collapse`. The shuffled-label check *runs*
in the baseline pipeline but is not a merge-blocking test.

**Solution.** Write all three. Encoder fit scope and threshold provenance both need the
objects to record where they were fitted — `CategoricalEncoder` already does, thresholds
do not yet (see 2.2).

| | |
|---|---|
| Compute | seconds |
| Build | 30–45 min |

### 1.4 `E_LEAK` — the deliberate leaky control — has not been run

**Problem.** v3 §11 asks for one intentionally-leaky configuration (random split, global
graph statistics, encoders fitted on everything) logged as `E_LEAK`. Its purpose is
evidentiary: a report showing E_LEAK at, say, 0.35 against an honest E2 at 0.05 proves
the pipeline is sound far better than a paragraph claiming it.

**Solution.** Add it to the ablation runner and log it like any other experiment.

| | |
|---|---|
| Compute | ~3 min |
| Build | 30 min |

---

## 2. Required before E2 vs E1 counts as a fair comparison

### 2.1 No hyperparameter search exists (`models/tuning.py`)

**Problem.** Every experiment uses one fixed parameter set. v3 §15.2 requires
**rolling-origin** search — never k-fold, which shuffles across time and reintroduces the
leakage the splitter exists to prevent — and an **equal search budget** per experiment.
Without that, an ablation measures tuning effort rather than features.

**Solution.** Implement rolling-origin search over the training partition with a fixed
trial budget recorded per experiment. GPU makes this affordable: ~5 s per fit means a
40-trial search is ~4 minutes.

| | |
|---|---|
| Compute | ~4 min per experiment |
| Build | 1.5–2 h |
| Priority | **high** — it gates the validity of every comparison |

### 2.2 Threshold selection is implicit (`evaluation/thresholds.py`)

**Problem.** Alert-budget points are computed inside the metrics module, but no threshold
object records *where* it was chosen. Gate C-series requires provenance saying
`validation`, never `test`.

**Solution.** A small `Thresholds` class carrying value, budget and provenance, written
into the model package and asserted by `test_threshold_source`.

| | |
|---|---|
| Compute | none |
| Build | 45 min |

### 2.3 Error analysis is written but has never been run

**Problem.** `evaluation/error_analysis.py` exists (slices by typology, amount band, hour,
payment type, position-within-pattern). It has not been executed, and **v3 §17.2 makes it
a hard gate on all feature work** — features designed before it are guesses.

**Solution.** Run it against E1 and E2, write the findings into
`reports/error_analysis/`, and let it choose which feature families get built.

| | |
|---|---|
| Compute | ~2 min |
| Build | 30 min (runner + report) |
| Priority | **highest after E2** — it decides what §3 contains |

---

## 3. Required by the validation gates

| Module | Gate | What it does | Build |
|---|---|---|---|
| `evaluation/interpretation.py` | **C8** | SHAP as a leakage detector — no single feature above 50% of mean abs SHAP; stability across seeds | 1–1.5 h |
| `evaluation/profiling.py` | **P8, P9** | extraction throughput, inference latency, peak RSS, per-family cost | 1 h |
| `evaluation/stability.py` | **P7** | PR-AUC across five test sub-windows; PSI/KS feature drift | 1–1.5 h |

Compute for all three: ~15 min combined.

---

## 4. Required for the research contribution

### 4.1 Two evaluation splits are missing

`splits/unseen_pattern.py` (v3 §11 B) and `splits/hard_negative.py` (v3 §11 C).

The hard-negative split is the one that matters most — v3 says it *"predicts real-world
false-positive pain better than anything else in the framework"*. It selects structurally
complex but benign behaviour: high-fan-out accounts with regular cadence, high-volume
hubs, dense legitimate cycles.

**Caveat on unseen-pattern:** only **62%** of positives carry a `pattern_type`
(3,209 of 5,177 before tail-trimming). The other 38% are labelled laundering with no
pattern annotation, so the held-out-typology split covers roughly two-thirds of the
positive class. That limitation must be stated in the report rather than glossed.

| | |
|---|---|
| Compute | ~5 min |
| Build | 2–2.5 h |

### 4.2 Feature families E3–E7 (`temporal_flow`, `value_flow`, `novelty`, `adaptive`)

**Do not build these yet.** Which ones get built is an output of §2.3, not an input. If
the error analysis says recall collapses on late-stage chain hops, that is a temporal
finding; if it says false positives cluster on high-degree hubs, that is a hard-negative
finding. Building all four regardless is exactly what v3 §17.2 forbids.

| | |
|---|---|
| Compute | ~30 min (extraction cached) |
| Build | 1.5–2 h per family, 2–3 families realistic |

### 4.3 `pipeline/run_ablation.py`

One change at a time, equal search budget, 5 seeds each, judged against Δ > 0.0034.

| | |
|---|---|
| Compute | ~30 min |
| Build | 1–1.5 h |

---

## 5. The deliverable

`models/flowguard_E7_v1/` per v3 §26.4 — booster, calibrator, feature schema + hash,
encoders, config, thresholds, metrics, `validation_report.md`, `model_card.md`,
`shap_summary.json`, `PROVENANCE.json`.

The model card must include the families that were **evaluated and dropped**, with the
measured reason. It is the most commonly omitted section and the most useful to whoever
picks this up next.

| | |
|---|---|
| Compute | ~5 min |
| Build | 2–3 h |

---

## 6. Decisions only you can make

### 6.1 Gate P4 — currently unachievable as written

`P4: recall > 0.60 at a 1% alert budget`. E1 measures **41.1%**. It must be fixed before
E7 runs or it is not a gate.

| Option | Consequence |
|---|---|
| Keep 0.60 @ 1% | Honest, but likely reported as a miss |
| Lower to ~0.45 @ 1% | Achievable; must be justified as an operational bar, not fitted to the result |
| Quote 5% budget instead | E1 already reaches **77%** there; 5% of 5M transactions is a large alert volume, so justify the budget |

**My recommendation:** keep 1% as the headline budget and lower P4 to 0.45, while
*also* reporting the full budget curve. Moving the budget to make the number look good is
the worse failure.

### 6.2 Scope under time pressure

If the deadline is tight, the defensible core is **E0 → E1 → E2 with gates**, which is
§1 + §2 + §3 only. The research contribution (§4) is what gets cut first. A fully-gated
E2 beats a rushed E7.

### 6.3 GFP window

Confirm the 2-day / 5-day / 10-day sensitivity study is worth ~45 minutes of compute.
I think it is: it converts my parameter mistake into a required v3 §26.3 result.

---

## 7. Known risks, accepted rather than fixed

| Risk | Status |
|---|---|
| WSL has no outbound network | Worked around with an offline wheelhouse; adding a package means refreshing it from Windows first |
| 8 GB VRAM | Caps GPU training at HI-Small; HI-Medium must train on CPU or in batches |
| 39 GB of raw data inside OneDrive | Gitignored, but still syncing; moving it outside OneDrive is ~10 min and removes the risk |
| Pattern coverage 62% | Limits the unseen-pattern split; must be declared |
| 9 duplicate natural keys | 0.0002% of rows, left unlabelled rather than guessed |
| Test set touched once | So far honoured — E1's numbers came from a single scoring pass |

---

## 8. Proposed order, with a running clock

Assumes continuous work; compute overlaps where noted.

| # | Item | Build | Compute | Cumulative |
|---|---|---|---|---|
| 1 | E2 finishes; same-device re-run of E0/E1/E2 | — | 30 min | 0:30 |
| 2 | **Error analysis run** — gates everything after | 30 m | 2 min | 1:05 |
| 3 | Three missing leakage tests + `E_LEAK` | 1.5 h | 3 min | 2:35 |
| 4 | Rolling-origin search + thresholds | 2.5 h | 10 min | 5:15 |
| 5 | GFP window sensitivity (2/5/10 day) | — | 45 min | 6:00 |
| 6 | Interpretation, profiling, stability | 3.5 h | 15 min | 9:45 |
| 7 | Unseen-pattern + hard-negative splits | 2.5 h | 5 min | 12:20 |
| 8 | 2–3 feature families the error analysis picked | 4 h | 30 min | 16:50 |
| 9 | Ablation runner, 5 seeds, 2σ judgement | 1.5 h | 30 min | 18:50 |
| 10 | Model package, validation report, model card | 2.5 h | 5 min | 21:25 |

**≈ 21 hours of work to a fully-gated, publishable result.**

Milestones if that is too long:

* **After #3 (~2.5 h)** — E0/E1/E2 measured on one device with a complete leakage
  suite and a leaky control. Defensible, reportable, honest.
* **After #6 (~10 h)** — all correctness gates and most performance gates green. This is
  the point where the result is genuinely solid.
* **After #10 (~21 h)** — the full v3 terminus.

---

## 9. What I would do next, in one line

Wait for E2, run the error analysis, and let it decide what gets built — everything in
§4 is downstream of that answer, and building it sooner would just be guessing.
