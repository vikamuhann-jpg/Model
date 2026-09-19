# FlowGuard — Project Status

**Date:** 2026-09-19
**Scope:** Track R (ML research pipeline) per `FlowGuard_ML_Pipeline_Plan_v3.md`
**One-line summary:** The pipeline is built and validated; the single experiment that
answers the research question is running now.

---

## 1. Where the project stands

| | |
|---|---|
| Source | 6,328 lines / 39 modules |
| Tests | 2,019 lines / 15 files — **137 passing** |
| Decision records | 9 ADRs |
| Commits | 7 (**18 files uncommitted**) |
| Experiments logged | E0, E1, ABLATION |
| In flight | **E2** — GFP extraction, 29.5%, ~25 min remaining |
| Published | [Validation report](https://claude.ai/artifact/Y9qSGamEhR5nbeyacw6yzy) |

**Plan v3 phases complete:** 0–14, 17, 20 (framework). Outstanding: the E2 result itself,
feature research (conditional), and cross-dataset validation.

---

## 2. What has been done

### The pipeline

Raw CSV → canonical schema → leakage-safe chronological split → features → baselines →
evaluation → validation gates → model package. Every stage tested; the leakage suite is
merge-blocking.

Built: ingestion with checksums, canonical schema with structurally-enforced label
isolation, chronological splitter with three boundary policies, streaming GFP extraction,
transaction features, rule baseline, XGBoost with calibration, rolling-origin
hyperparameter search, thresholds with provenance, SHAP interpretation, temporal
stability, PSI/KS drift, cost profiling, hard-negative and unseen-pattern splits,
account-level evaluation, the C1–C8/P1–P9 gate framework, experiment registry, ablation
runner, and the model-package writer.

### The results measured so far

Corpus: **IBM AML HI-Small** — 5,077,237 transactions, 515,078 accounts, 4,522 positives,
base rate **0.089%**. Every figure re-derived from the files, not copied from the planning
documents.

| Experiment | PR-AUC | Lift | Recall @1% |
|---|---:|---:|---:|
| E0 — threshold rules | 0.0011 | 1.0× | 1.0% |
| E1 — transaction-only *(with artifact)* | 0.0424 | 35.7× | 41.1% |
| **A2 — transaction-only *(artifact removed)*** | **0.0066** | **5.6×** | **11.8%** |
| E2 — + GFP graph features | *running* | | |

### The finding that reframed the project

Gate C8 fired on `payment_type` at 56.8% of mean |SHAP|. Investigation showed **2,553 of
2,554** annotated pattern transactions are ACH — the simulator injects laundering over a
single payment rail, so "is ACH" nearly identifies an injected pattern.

A five-seed ablation measured the cost: **84% of the tabular baseline's apparent
performance was that artifact.** The honest baseline is 0.0066, not 0.0424.

This matters beyond the number. The inflated baseline left graph features almost no
headroom to demonstrate value; against 0.0066 there is a real gap. **E2 versus A2 is the
comparison that answers the research question** — not E2 versus E1.

### Where the honest baseline fails

Error analysis on A2 (the gate on all feature work, v3 §17.2):

| Amount band | Positives | Recall |
|---|---:|---:|
| ≤ $2,671 | 220 | **0.0%** |
| $2,671 – $17,158 | 442 | 14.7% |
| > $17,158 | 244 | 17.2% |

It has learned "large transfer" — the legacy threshold behaviour this project set out to
beat, and precisely what structuring defeats. Caught positives have a median amount of
$15,711 against $6,793 for missed ones.

**Pre-registered prediction:** graph gains must concentrate in the bottom three bands. A
uniform lift means the graph features are another magnitude proxy. Decided mechanically
when E2 lands.

**Control:** hard-negative enrichment is **1.02×** — the tabular model does not mistake
structural complexity for crime, because it cannot see structure. If E2 pushes this well
above 1.0, it is buying recall by alerting on legitimately complex accounts.

---

## 3. The nine decision records

Four of these caught defects that would each have produced a clean, impressive, false
result.

| ADR | Finding |
|---|---|
| **001** | GFP's native backend is **absent from the Windows snapml wheel** — wrapper present, zero `gf_*` symbols. Import succeeds, construction raises. Project moved to WSL2 on day one |
| **002** | Plan v3's *preferred* purge split policy **erases 100% of rows** on this corpus; pattern-start leaks 238 test-period transactions (4.6% of positives). Hard cut adopted |
| **003** | The corpus tail is ~59% laundering vs a 0.089% base rate — a 290× enrichment that made `day_of_week` alone outscore the entire model. Trimmed |
| **004** | GFP's `transform` lets an edge **see later edges in its own batch**. `batch_size=50,000` would have inflated E2 and nothing else — manufacturing the exact result under test |
| **005** | GPU `hist` stops ~80 iterations early on this imbalance, **silently undertraining** and costing 22% PR-AUC until patience was raised to 100 |
| **006** | Bounding the GFP window helps 37–53% but is **not sufficient** — the vertex map grows regardless |
| **007** | **`payment_type` is a generator artifact** — the 84% finding above |
| **008** | Periodic graph reconstruction **rejected**: it changes features, so GFP holds state beyond the windowed edges. Negative result, recorded |
| **009** | Chunked extraction — the first full run was **OOM-killed at 98.5% after 2.5 hours**. Resume is impossible, not unimplemented |

---

## 4. Remaining time to completion

### Immediate — Tier A *(≈ 1 hour, mostly waiting)*

| Step | Time |
|---|---|
| E2 extraction finishes | ~25 min |
| Completion script — 3 arms × 3 seeds, prediction test | 10 min |
| Validation gates + model package | 10 min |
| Report update + commit | 15 min |

**Gate A forks the rest of the project:**

| Outcome | Next |
|---|---|
| Δ > +0.0034 and low-band concentrated | Tier B justified |
| Δ > +0.0034 but uniform | Tier B narrowed to adaptive/neighbourhood features only |
| \|Δ\| ≤ 0.0034 | **Skip Tier B.** A trustworthy negative is a result (v3 §1) |

### Full completion

| Target | From now | What you get |
|---|---:|---|
| **Tier A only** | **~1 h** | Validated model package, 9 ADRs, complete gate report. Defensible as-is |
| A + C (recommended) | ~5 h | Adds cross-dataset validation — the only evidence the result is not simulator-specific |
| A + B + C | ~11 h | Adds feature research |
| **With the Tier S fixes** | **~19 h** | Two already done (S2, S4); S1 rejected; S3/S5/S6 outstanding |

**Realistic estimate to a complete, defensible deliverable: 1 hour.
To one that can claim external validity: ~5 hours.**

---

## 5. What the project still needs to address

### Blocking

1. **E2 must complete.** Two prior attempts died — one OOM at 98.5%, one killed by a
   failed `pkill` that left the old process writing to deleted files. The current run is
   on fixed code with chunked persistence.
2. **`run_validation` needs `--gfp-cache`.** Without it the command validates a
   *tabular* model and files it under E2's name, with every gate passing. A wrong number
   that looks right.

### Correctness gaps

3. **Gate P4 will fail and should.** Target 45% recall @1%; A2 measures 11.8%. The target
   was pre-registered against the artifact-inflated 41%. It stays unchanged and is
   reported as a miss — moving a gate after seeing results is what gates prevent. The
   lesson is recorded: **pre-registration inherits whatever contaminates the numbers it
   was set against.**
4. **Gate P8 fails.** Extraction decays to ~470 tx/s against a 1,000 tx/s target. After
   ADR-008 this is a property of the method, not a tuning mistake.
5. **Gate C8 passes only conditionally** — after removing a disclosed artifact. It must
   never be reported as an unqualified pass.
6. **`E_LEAK` has not been run.** The deliberate leaky control exists in the ablation
   runner but has not executed. Its value is evidentiary.

### External validity — the largest gap

7. **No cross-dataset validation.** Everything rests on one synthetic generator, and
   ADR-007 is the reason that is dangerous: a simulator that leaks its payment rail may
   leak other conventions. A real network is the only way to know.
8. **Typology recall covers ~62% of positives.** The rest carry no annotation.
9. **140 of 370 patterns are truncated** at a split boundary; their recall is a floor,
   not an unbiased estimate.
10. **No real transaction data.** Both candidate corpora are synthetic or public-chain.
    Every claim is bounded by that, and the model card says so.

### Engineering

11. **Extraction cannot resume** — ADR-009. A mid-extraction crash costs the full run.
12. **Scaling is unmeasured.** HI-Medium (32M) is likely infeasible; that should be
    measured and published as an envelope rather than assumed either way.
13. **18 files uncommitted**, including the Windows-native path and ADRs 008–009.
14. **Tier S3/S5/S6 outstanding** — capability matrix, scaling envelope, P4 documentation.

---

## 6. Honest assessment

**What is strong.** The pipeline is rigorous and the gates earned their cost — four of
nine ADRs record defects that would have produced impressive false results, each caught
before anything depended on it. The artifact finding in particular turned a flattering
number into a real research question.

**What is weak.** A single synthetic corpus, a headline PR-AUC of 0.0066 that is honest
but operationally far from useful, and an extraction step too slow to meet its own
throughput gate.

**What would most improve it.** Cross-dataset validation, by a wide margin. Not another
feature family, and not a better number on HI-Small.
