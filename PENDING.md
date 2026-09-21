# FlowGuard — Pending Work

**As of:** 2026-09-21
**Repository:** private, **AI only**. The frontend, backend and database live in a separate
product repository that consumes [`contracts/`](contracts/) and [`sample_outputs/`](sample_outputs/).
**Companion to:** [`README.md`](README.md) (what exists) and [`docs/OPEN_ITEMS.md`](docs/OPEN_ITEMS.md) (research findings in depth)

| Section | Open | Done | Blocks |
|---|---:|---:|---|
| [A. Before pushing to GitHub](#a-before-pushing-to-github) | 2 | 3 | The push itself |
| [B. Reproducibility and hygiene](#b-reproducibility-and-hygiene) | 4 | 6 | Anyone else re-running the results |
| [C. Open research findings](#c-open-research-findings) | 9 | — | Stronger claims |
| [D. Functional requirements still open](#d-functional-requirements-still-open) | 6 | — | Full PS9 coverage |
| [E. Toward production](#e-toward-production) | 3 stages | — | Real deployment |

---

## A. Before pushing to GitHub

- [ ] **A1. Remove the 310 MB archive from git.** — *hard blocker*
  `Dataset_/QmdMVccE2ymMyiRmyxVQSVm3JUNh18k7XKSbwQ6JsiPSBx` (the Ethereum phishing graph) was
  committed in `d230c50`, the latest commit. GitHub rejects any file over 100 MB, so the push
  fails until it is gone. It sits only in the latest commit and nothing has been pushed, so
  removing it rewrites one local commit nobody else has. `.gitignore` now excludes all of
  `Dataset_/`, so it cannot recur. The 352 KB generator PDF beside it stays tracked.

- [x] ~~**Untrack the reference material.**~~ *Decided: keep it.* `papers/`, `websites/` (HTML
  only) and `docs/*.pdf` stay tracked — the repository is private, and they total about 11 MB.

- [ ] **A3. Commit, create the remote, push.**
  No remote is configured. The local branch is `master`; GitHub defaults to `main`, so rename
  with `git branch -M main` before the first push.

- [x] ~~**Rescue nine measurement scripts from temporary storage.**~~ *Done 2026-09-21* — in
  `Project/flowguard/scripts/measure/`, hard-coded paths replaced by `_paths.py`
  (`FLOWGUARD_DATA` overrides), indexed in its README against the results each produced.

- [x] ~~**Decide public or private.**~~ *Done* — private, AI only.

---

## B. Reproducibility and hygiene

- [ ] **B1. Log P3, P4, P6 and Tier C in the experiment registry.**
  Their results live as JSON in the external data folder, not in `experiments/results.csv`.
  A4 is logged (validation logs automatically); these four are not.

- [ ] **B2. Update `Project/flowguard/README.md`.**
  It describes a Track-R-only package and predates `graph/`, `evidence/`, the cascade, the
  transfer runner and `score.py`. The root README is current; this one is not.

- [ ] **B3. Reconcile the account count.**
  `configs/experiment.yaml` records **515,088** accounts; the trace index and every document
  report **515,078**. One of them is wrong by ten.

- [ ] **B4. Remove the remaining machine-specific paths.**
  `configs/experiment.yaml` and the pipeline runners still assume `/mnt/c/Users/vikam/…`. The
  measure scripts and `score.py` are already parameterised; the rest should follow before
  anyone else trains a model.

- [x] ~~**Package the artifact-free model.**~~ *Done* — `models/flowguard_A4_v1/`: 167
  features, no `payment_type`, PR-AUC 0.1400 ± 0.0030, all eight correctness gates pass. It is
  the only model in git, and a test fails if one using the artifact is ever committed.

- [x] ~~**Batch scoring entry point.**~~ *Done* — `pipeline/score.py`, with four contracts in
  `contracts/` and real samples in `sample_outputs/`, all validated by `test_contracts.py`.

- [x] ~~**Regenerate the shipped model card.**~~ *No longer needed* — E2 is not shipped; A4's
  card was generated from the fixed template.

- [x] ~~**Update `end report/`.**~~ *Done* — lists all four reports.

- [x] ~~**Archive `docs/implementation_plan.md`.**~~ *Done* — moved to `docs/archive/`.

### Correction to published material

- [x] ~~**Republish two hosted reports with corrected P2 numbers.**~~ *Done 2026-09-21.*
  The first P2 evidence case reported its top reason as `payment_type` at **+8.599**, "more than
  three times the strongest graph feature". A bug — trace edges renumbered their index, so
  SHAP values were joined to the wrong rows — overstated it about threefold. Regenerated, the
  figure is **+2.926**, about 1.5× the strongest graph feature; the direction holds. Fixed at
  the root and pinned by two regression tests. Corrected in `docs/TRACK_P_PLAN.md` and in
  *Six Phases, Sixteen Gates* (with a correction note); *Case Desk* now shows the shipped
  model's ten sample cases instead.

---

## C. Open research findings

Not code tasks. Each needs data, a decision, or a new experiment.

- [ ] **C1. The model is blind to every payment rail except ACH.** — *most serious*
  599 of 796 ACH laundering transactions caught; 1 of 100 on every other rail. The training
  corpus puts 2,553 of 2,554 injected patterns on ACH. Removing the artifact from the model
  (A4) stops it *relying* on the rail; it cannot teach it the patterns the corpus never shows.
  **Needs:** a corpus whose laundering spans payment rails.

- [ ] **C2. False positives on legitimate complexity: 2.1×.**
  A4 alerts on merchant hubs and payroll fan-out at 2.34% against 1.11% for ordinary traffic
  (E2 was 2.3×). The family built to fix it made things worse
  ([ADR-011](docs/ADR-011-adaptive-features-rejected.md)).
  **Needs:** analyst dispositions written back into evidence bundles.

- [ ] **C3. Extraction throughput fails its gate, and the cause is intrinsic.**
  ~450 tx/s synthetic, ~139 tx/s on a real network, against 1,000. Two reduction attempts have
  been rejected ([ADR-008](docs/ADR-008-reconstruction-rejected.md),
  [ADR-014](docs/ADR-014-cascade-cannot-prefilter.md)).
  **Worth trying:** a tier 0 carrying cheap graph signal — incrementally maintained degree
  counters — rather than none.

- [ ] **C4. The stability gate does not test variance.**
  Across five time windows A4 scores 0.061 to 0.210. Gate P7 passes because it checks only for
  a *monotone decline*. Add a variance gate.

- [ ] **C5. Calibrated scores saturate.**
  Isotonic calibration pins its top bin, so many top alerts share one score. `score.py` now
  emits `raw_score` and a tie-breaking `rank`, which works around it; the calibration itself is
  unchanged. Try Platt scaling.

- [ ] **C6. Alert rate depends on how much history the graph has.**
  The threshold was set for a 1% alert budget; on a 50,000-row window it alerts on **5.0%**,
  because a short window starts the graph cold. Production scoring should run over windows
  long enough to warm the graph (at least the 2-day graph window), or re-derive the threshold
  per window.

- [ ] **C7. The real-network result rests on 20 positive accounts.**
  The direction is settled (2,000/2,000 bootstrap resamples); the magnitude is not (95% CI
  0.019–0.123). **Needs:** more labelled accounts, or the full 2.02M-edge slice.

- [ ] **C8. Typology hinting missed its bar by 0.014.**
  Macro-F1 margin 0.1265 against a required 0.1405, and CYCLE scores F1 0.079 — awkward, since
  round-tripping is one of the three patterns PS9 names. **Needs:** more annotated patterns.
  The bar is not to be moved.

- [ ] **C9. The unsupervised arm finds something real and cannot be combined naively.**
  The isolation forest catches ~20 positives per seed the supervised model misses, but a rank
  average collapses PR-AUC from 0.140 to 0.040. **Worth trying:** stacking instead of an average.

---

## D. Functional requirements still open

PS9 lists twelve. Six are built, six are partial, none is absent.

| FR | Requirement | State | What is missing | Blocked by |
|---:|---|---|---|---|
| 03 | Entity representation | partial | Customers, branches, products, channels | No corpus contains them — left open by choice |
| 06 | Typology detection | partial | A classifier that clears its bar | Too few annotated patterns (C8) |
| 07 | ML anomaly detection | partial | A usable unsupervised arm | Combination method (C9) |
| 08 | Risk scoring | partial | Customer, branch and product risk | Depends on FR-03 |
| 09 | Explainability | partial | Semantic reasons for graph features | The graph library exposes no feature names |
| 12 | Near-real-time scoring | partial | Extraction at production volume | Intrinsic cost (C3) |

**FR-03 and FR-08 are open deliberately.** Closing them means generating synthetic customers
and branches and then reporting that the detector found patterns in them.

---

## E. Toward production

**Presentable as research; not deployable for AML decisions.** With the repositories now
split, each stage says which side owns it.

### Stage 1 — investigation aid · 2–4 weeks
- [ ] *Product repo:* load `scores.csv`, `cases/` and `run.json` into a database; build the
  case view against `contracts/`
- [ ] *AI repo:* schedule `score.py` over windows long enough to warm the graph (C6)
- [ ] *Both:* account identity resolution for the real data's schema

### Stage 2 — shadow mode · 2–3 months
- [ ] *AI repo:* retrain on the bank's own data — the current model does not transfer
- [ ] *Product repo:* capture analyst dispositions and write them back into bundles
- [ ] *Both:* measure the false-positive cost (C2) on real cases

### Stage 3 — production candidate · 6+ months
- [ ] Resolve C1 — needs multi-rail laundering data
- [ ] Throughput engineering for actual volume (C3)
- [ ] Model governance: validation on real data, drift monitoring, retraining cadence

**Stage 3 is blocked on data, not code.**
