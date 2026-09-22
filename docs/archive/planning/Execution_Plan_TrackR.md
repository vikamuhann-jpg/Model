# FlowGuard — Track R Execution Plan

**Version:** 1.0
**Date:** 2026-09-18
**Governing plan:** [`FlowGuard_ML_Pipeline_Plan_v3.md`](FlowGuard_ML_Pipeline_Plan_v3.md)
**Scope:** Track R only. Terminus is the validated model package of v3 §26.4.

This document is the *execution* layer: what to build next, in what order, with which
gate closing each step. It does not restate v3's reasoning — it points at it. Where a
number has to be fixed in advance, it is fixed here and marked for sign-off.

---

## 1. Status snapshot

*Updated 2026-09-18 after the M1-M4 build.*

| v3 Phase | Component | State |
|---|---|---|
| Phase 0 | Environment, GFP availability | **Done** ([ADR-001](ADR-001-gfp-platform.md)) |
| Phase 1 | Ingestion, checksums, `dataset_summary.json` | **Done** |
| Phase 2 | Profiling (daily profile, typology counts) | **Done** |
| Phase 3 | Validation and quality policy | **Done** |
| Phase 5 | Canonical schema, label isolation | **Done** |
| Phase 5 | Chronological splitter, 3 boundary policies | **Done** ([ADR-002](ADR-002-boundary-policy.md)) |
| Phase 5 | Leakage suite | **Done** — incl. `test_future_edge_invariance` |
| Phase 6 | Streaming transaction graph | **Done** — via GFP's internal CTDG |
| Phase 7 | Transaction features, GFP features | **Done** ([ADR-004](ADR-004-gfp-batch-leakage.md)) |
| Phase 8 | E0 rules, E1 tabular, sanity baselines | **Done** |
| Phase 9 | Training protocol, calibration | **Done** — `scale_pos_weight`, isotonic on validation |
| Phase 10 | Evaluation framework, alert budgets | **Done** |
| Phase 17 | Experiment registry | **Done** |
| Phase 7-8 | E2 graph baseline | **In progress** |
| Phase 11 | Error analysis | Not started — **gates the feature work** |
| Phase 12 | Research feature families (E3-E7) | Not started |
| Phase 13-16 | Interpretation, profiling, ablation, results | Not started |
| Phase 20 | Validation gates | Not started |

### Measured results so far (HI-Small, 5,077,237 transactions)

| Experiment | PR-AUC | Lift | Recall @1% | Precision @1% |
|---|---:|---:|---:|---:|
| E0 — rules | 0.0011 | 1.0x | 1.0% | 0.12% |
| E1 — transaction-only XGBoost | **0.0424** | **35.7x** | **41.1%** | 4.89% |
| E2 — + GFP graph features | *running* | | | |

Sanity baselines all pass: random 0.0011, constant 0.0011, shuffled-label 0.0011
against a test base rate of 0.00119. Gate **P2 (E1 beats E0) passes**: +0.0413.

### Four findings that changed the plan

1. **GFP is Linux-only** — the Windows wheel ships the wrapper with no native
   backend ([ADR-001](ADR-001-gfp-platform.md)).
2. **Purge is infeasible here** — pattern durations reach 8d10h against a 10-day
   corpus, so the plan's preferred boundary policy erases the dataset
   ([ADR-002](ADR-002-boundary-policy.md)).
3. **The corpus has a laundering-saturated tail** — the last 1,108 transactions are
   ~59% positive, a 290x enrichment that made `day_of_week` alone outscore the whole
   model ([ADR-003](ADR-003-sparse-tail-trim.md)).
4. **GFP batching leaks the future** — an edge transformed alongside later edges in
   the same batch counts them, so extraction must run one transaction at a time
   ([ADR-004](ADR-004-gfp-batch-leakage.md)).

Findings 3 and 4 would each have produced a large, clean, entirely artificial result.

## 2. Dataset roles

The download is ~8 GB and contains every variant. Assign roles **before** ingesting, and
do not revisit — v3 §4 makes changing the primary dataset an invalidation event.

| Variant | Role | Used for |
|---|---|---|
| **HI-Small** | **Primary** | Every experiment E0–E7, all model selection, all headline numbers |
| HI-Medium | Scale test only | Throughput and peak-memory measurement (P8, P9). **Never** for model selection |
| LI-Small | Optional contrast | Behaviour at roughly half the illicit rate, if time allows |
| HI-Large | **Not used** | ~180 M transactions will not fit the 12 GB WSL ceiling |
| `*_Patterns.txt` | Required | Source of `scenario_id` / `pattern_type` |

If the patterns file is absent, two things are lost and must be declared in the report:
the unseen-pattern split (v3 §11 B), and the splitter's ability to derive its purge
buffer — a boundary policy would then have to be chosen by hand.

**Cross-dataset validation (v3 §24):** v2 §6.2 nominates the ETH Phishing network as the
honest generalisation test, because passing it cannot be explained by having memorised
one generator's quirks. It is a separate download with a different schema. Treat it as
stretch scope, after the gates pass.

---

## 3. Milestones

Each milestone ends with a gate. A milestone is not complete until its gate is green and
its results are in the registry.

### M1 — Ingestion and data contract *(blocked on download)*

**Build**

* `data/loader.py` — HI-Small → canonical schema. The real work is account identity:
  HI-Small keys an account as a *(bank, account)* pair. Collapsing that to the bare
  account column would merge distinct accounts into one graph node and silently corrupt
  every structural feature downstream. Resolve to a composite ID and test it.
* `data/validator.py` — v3 §9 quality policy: non-negative amounts, no self-transfers,
  resolvable endpoints, parseable timestamps, duplicate detection, null policy per field.
* `pipeline/ingest.py` — SHA-256 every raw file, write the immutable raw layer, emit
  `dataset_summary.json`.
* `data/profiling.py` + `notebooks/01_data_exploration.ipynb` — v3 §8 profiling.

**Derive, do not copy.** v2 §6.1's statistics are flagged unverified in the plan itself.
Row count, account count, illicit rate and temporal span all get re-derived from the
files actually downloaded, and those are the numbers the report uses.

**Gate M1**
- [ ] Checksums recorded; raw layer never written to again
- [ ] `validate_schema()` passes on the full canonical frame
- [ ] Every raw column is either mapped or explicitly dropped — no silent passthrough
- [ ] `dataset_summary.json` exists with self-derived counts
- [ ] Amount/currency semantics confirmed (HI-Small carries both a paid and a received
      amount; which one `amount` means is a decision, and it gets recorded)

---

### M2 — Splits on real data

**Build**

* `splits/unseen_pattern.py` — hold out whole `pattern_type` values (v3 §11 B)
* `splits/hard_negative.py` — structurally complex but benign behaviour: high-fan-out
  accounts with regular cadence, high-volume hubs, dense legitimate cycles (v3 §11 C)
* `splits/leakage_checks.py` — shared assertions for the suite

**Decide** the boundary policy against the real pattern-duration distribution. The
splitter defaults to `PURGE` with a buffer derived from the longest observed pattern; on
a ~10-day corpus that may purge an unacceptable fraction. The splitter warns above 25%.
Record the choice and the count of affected patterns either way.

**Gate M2**
- [ ] Boundary timestamps printed and recorded in the registry
- [ ] Affected-pattern count reported
- [ ] Leakage suite green on real data
- [ ] Every partition contains positives — a test set with none is not a test set

> v3 §11 C is worth the effort: the hard-negative split predicts real-world
> false-positive pain better than anything else in the framework.

---

### M3 — Baselines: E0, E1, and the sanity floor

**Build**

* `evaluation/sanity.py` — random, constant, shuffled-label, single-feature baselines
* `models/rules.py` — E0, threshold/velocity rules
* `features/transaction.py` — tabular features, no graph
* `models/xgb.py`, `models/tuning.py` (rolling-origin), `models/calibration.py`
* `evaluation/metrics.py`, `evaluation/thresholds.py`
* `registry/experiments.py` — v3 §23

**Run the sanity baselines first.** Shuffled-label is the highest-value leak detector
available and costs one training run. If it scores meaningfully above base rate, stop —
something upstream is leaking and every later number would be fiction.

**Protocol, non-negotiable** (v3 §15): rolling-origin search, never k-fold — k-fold
shuffles across time and reintroduces the leakage the splitter exists to prevent. No
SMOTE: interpolating graph features produces impossible transactions. Thresholds from
validation only. Equal search budget across experiments, or the ablation measures tuning
effort rather than features.

**Gate M3**
- [ ] Shuffled-label PR-AUC within 2× base rate (**C2**)
- [ ] Random-score PR-AUC ≈ base rate (**C3**)
- [ ] E0 and E1 logged with full provenance
- [ ] E1 beats E0 by > 2σ (**P2**) — or the finding is reported as-is

---

### M4 — Graph and the GFP baseline: E2

**Build**

* `graph/temporal_graph.py` — CTDG: window, insert, tombstone, sweep
* `graph/adjacency.py`
* `features/gfp.py` — wraps `snapml.GraphFeaturePreprocessor`

**The insertion-order convention is the whole game** (v3 §12). Features for an edge must
be computed against the graph as it stood *before* that edge was inserted, or a
transaction inflates its own structural features. That means `partial_fit` on history,
then `transform` on the new edge — already proven working in
`tests/integration/test_gfp_environment.py`.

**Two facts already paid for:**
- GFP parameter keys are hyphenated: `scatter-gather`, `temp-cycle`, `lc-cycle`. The
  plan documents' prose uses underscores, which `set_params` rejects with `KeyError`.
- The default config in the gate test yields 215 engineered features per edge.

**Then implement the remaining leakage tests**, which only become possible now:
`test_future_edge_invariance` (the strongest one available — extract for a transaction
at *T* against a graph containing future edges, assert byte-identical output against a
truncated graph), `test_extractor_label_blind` end-to-end, `test_encoder_fit_scope`,
`test_threshold_source`.

**Also run `E_LEAK`** (v3 §11): one deliberately leaky configuration — random split,
global graph statistics, encoders fitted on everything. Its purpose is evidentiary. A
report showing `E_LEAK` at 0.94 against an honest E2 at 0.61 demonstrates the pipeline is
sound far more convincingly than a paragraph claiming it is.

**Gate M4**
- [ ] `test_future_edge_invariance` passes
- [ ] Full leakage suite green (**C1**)
- [ ] E2 logged; window δ recorded
- [ ] E2 beats E1 by > 2σ (**P1**) — or reported as a negative result, which is publishable

---

### M5 — Error analysis, then features that target it

**The ordering here is the point** (v3 §17.2). Features designed before the error
analysis exists are guesses. The gate exists to stop the project inventing features it
finds interesting rather than features the model measurably needs.

**Build**

* `evaluation/error_analysis.py` — FP/FN categorisation, slice analysis by amount, time,
  degree, path position
* `evaluation/interpretation.py` — SHAP, used as a **leakage detector**: a feature
  carrying >50% of mean absolute SHAP is a warning, not a triumph (**C8**)
* `evaluation/profiling.py` — latency, throughput, peak memory, per-family cost

**Then, and only then**, the research families (v3 §18) — each targeting a *measured*
failure: `features/temporal_flow.py`, `features/value_flow.py`, `features/novelty.py`,
`features/adaptive.py`.

**Inclusion rule, fixed now:** a family enters the final model only if it improves PR-AUC
by > 2σ with a confidence interval excluding zero, measured at equal search budget.
Anything else is reported as evaluated-and-dropped, with the measured reason — the line
most often omitted and most often useful to whoever reads this next.

**Gate M5**
- [ ] Error analysis complete and categorised **before** any new feature is written
- [ ] Each proposed family names the specific failure it targets
- [ ] Per-family extraction cost measured, giving the accuracy/cost trade-off a denominator
- [ ] No single feature carries >50% of mean absolute SHAP (**C8**)

---

### M6 — Ablations, final selection, validation gates

**Build**

* `pipeline/run_ablation.py` — one change at a time
* `evaluation/stability.py` — seed stability, temporal sub-windows, PSI/KS drift
* `pipeline/run_baseline.py` / `run_experiment.py` — the single reproduction command

**Ablation matrix:** E2 → +temporal → +value-flow → +novelty → +adaptive (E3…E7), equal
search budget throughout.

**If nothing passes the inclusion rule, E2 is the final model.** This is stated in
advance precisely so the goalposts cannot move later.

**Gate M6 — all of v3 §26.1 (C1–C8) and §26.2 (P1–P9).** Correctness gates are
non-negotiable: a failure voids the result regardless of performance. A missed
*performance* gate is a finding to report, not a failure to hide — P3 in particular may
legitimately come out inconclusive.

**Deliverable:** `models/flowguard_E7_v1/` exactly as specified in v3 §26.4, including
`validation_report.md`, `model_card.md` and `PROVENANCE.json`.

---

## 4. Pre-registered targets — needs sign-off

v3 §26.2 requires these fixed **before** E7 runs. A gate chosen after seeing results is
not a gate. Proposed values, to confirm or amend now:

| Gate | Proposed target | Note |
|---|---|---|
| P4 | Recall > 0.60 at a 1% alert budget | The operationally meaningful number; 1% is the budget the report will quote |
| P5 | No typology at zero recall | Guards against a total blind spot hidden by a good aggregate |
| P6 | PR-AUC standard deviation < 0.02 across 5 seeds | Distinguishes a stable result from a lucky one |
| P8 | Feature extraction > 1,000 tx/s | Keeps the streaming claim plausible |
| P9 | Peak RSS < 10 GB | Inside the 12 GB WSL ceiling, measured on HI-Small |

P1/P2/P3 are the 2σ comparisons and need no numeric target.

---

## 5. Sequencing and dependencies

```text
        [ 8 GB download ]
                 |
                 v
   M1 Ingestion ──> M2 Splits ──> M3 Baselines (E0,E1)
                                        |
                                        v
                                  M4 Graph + GFP (E2) + E_LEAK
                                        |
                                        v
                        M5 Error analysis ──> features (E3..E7)
                                        |
                                        v
                                  M6 Ablation + Gates
                                        |
                                        v
                          models/flowguard_E7_v1/
```

Nothing may be pulled forward past M5's gate: the feature work is *conditional* on the
error analysis, not parallel to it.

**Parallelisable while the download runs:** M1's loader and validator can be written now
against the published HI-Small column layout and tested on a synthetic fixture of the
same shape, so ingestion becomes a single command once the files land.

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Patterns file missing from the download | Lose unseen-pattern split and auto-derived purge buffer | Choose a boundary policy by hand; declare the limitation in the report |
| Purge drops too much of a ~10-day corpus | Weak test partition | Splitter warns above 25%; fall back to `PATTERN_START` and document the blurred boundary |
| Graph features don't beat tabular | P1 missed | This is a legitimate, publishable result. v3 §1 says so explicitly — the project succeeds by producing a trustworthy answer, not a flattering one |
| GFP extraction too slow at 5 M edges | P8 missed | Measure early in M4, not at M6; tune window δ before tuning the model |
| WSL 12 GB ceiling exceeded | M4/M6 stall | HI-Medium is throughput-only by design; HI-Large is excluded |
| Test set consulted more than once | Silent invalidation | v3 §11: the test set is touched once. If it is looked at and the model then changes, the report says so |

---

## 7. Definition of done

1. `models/flowguard_E7_v1/` complete per v3 §26.4
2. All correctness gates C1–C8 green, with evidence in `validation_report.md`
3. All performance gates P1–P9 measured and reported, pass or fail
4. One command reproduces the headline PR-AUC to 3 decimals from a clean checkout (**C6**)
5. Every number in the write-up traces to a logged experiment ID
6. `model_card.md` states the non-uses, the known failure modes, and the families that
   were evaluated and dropped

---

## 8. Open questions

1. **What is the deadline?** M1–M4 is the defensible core; M5–M6 is the research
   contribution. If time is short, a fully-gated E2 beats a rushed E7.
2. **Confirm the §4 pre-registered targets** before E7 runs.
3. **Is ETH Phishing cross-dataset validation in scope**, or stretch?
