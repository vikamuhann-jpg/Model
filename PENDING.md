# FlowGuard — Pending Work

**As of:** 2026-09-22 · **Repository:** private, AI only (the product repo consumes
[`contracts/`](contracts/) and [`sample_outputs/`](sample_outputs/)).
**Companions:** [`README.md`](README.md) (what exists) · [`docs/STATUS.md`](docs/STATUS.md)
(every current number) · [`WINNING_PLAN.md`](WINNING_PLAN.md) (the dated work log).

| Section | Open |
|---|---:|
| [A. Research findings still open](#a-research-findings-still-open) | 8 |
| [B. Reproducibility and hygiene](#b-reproducibility-and-hygiene) | 3 |
| [C. Functional requirements](#c-functional-requirements-ps9) | 5 partial |
| [D. Toward production](#d-toward-production) | 3 stages |
| [E. From the LinuxONE handoff (2026-09-24)](#e-from-the-linuxone-handoff-2026-09-24) | 3 |

**Sorted by who can act:** [`docs/PROBLEMS_1_FIXABLE.md`](docs/PROBLEMS_1_FIXABLE.md) (ours),
[`docs/PROBLEMS_2_BLOCKED.md`](docs/PROBLEMS_2_BLOCKED.md) (blocked on someone else),
[`docs/PROBLEMS_3_LIMITS.md`](docs/PROBLEMS_3_LIMITS.md) (cannot be fixed, only stated).
This page stays the record of the findings themselves.

Closed since 2026-09-21: the push to GitHub; the GFP double-insertion defect
([ADR-015](docs/ADR-015-gfp-double-insertion.md)); tuning (F1 0.280 → 0.521); the benchmark
comparison; named reasons for every feature (FR-09); the v2 package; history-aware scoring
(cold start); the Ethereum re-run (holds); timestamp statistics dropped as a time proxy;
the experiment registry and run records — never in git before — now tracked.

---

## A. Research findings still open

- [ ] **A1. Blind off ACH.** — *most serious.* v2 recall at 1%: ACH 84.9%; cheque 4.2%;
  cash, credit card, Bitcoin 0%. The corpus puts 2,553 of 2,554 patterns on ACH.
  **Needs:** a corpus whose laundering spans rails.
- [ ] **A2. Behaviour features: partly validated off the generator.** On the Ethereum graph
  they add +0.0098 account PR-AUC over graph features (2σ 0.0085, 20 positives) — a first
  sign, not proof. **Next:** repeat S4b on LI-Small.
- [ ] **A3. The remaining gap to the paper** is ~2 F1 points (0.614 vs 63.2 — the paper with
  the artifact and lookahead). Candidates: tuning *artifact-free* (S2 tuned with
  `payment_type` present); a larger budget (the paper used successive halving).
- [ ] **A4. Throughput (P8).** 532 tx/s strictly one at a time; 2,785 tx/s at batch 128 with
  no measured accuracy cost. Reconstruction is sound but does not help. **Decide:** adopt
  micro-batching (≤ ~23 s alert latency) with an ADR, or keep P8 as a reported failure.
- [x] **A5. Memory (P9) — closed 2026-09-28.** 10.99 GB → **9.71 GB**, inside the 10 GB
  budget. The peak was the full-corpus graph-feature frame held beside the matrices built
  from it, not the training matrices; partitions now read only their own rows from the part
  files. Model unchanged to four decimals. *Still not enough for the 6 GB VM — that needs
  the notebook's HDF5 streaming path.*
- [ ] **A6. Tail-inflated headline.** Dense-window PR-AUC 0.406 vs 0.595 overall. Both are
  reported in STATUS; consider a variance gate (P7 spread 0.593).
- [ ] **A7. Low-value laundering.** Recall at 1%: 4% below $139, 34% for $139–599.
- [ ] **A8. Pre-fix results not re-run:** typology hinting (P4), unsupervised arm (P6),
  cascade (ADR-014), adaptive features (ADR-011). Directions likely hold; magnitudes unknown.

## B. Reproducibility and hygiene

- [ ] **B1.** Tier C, P3, P4 and P6 records still live only in the data folder. (The
  benchmark runs are now tracked in `Project/flowguard/experiments/runs/`.)
- [ ] **B2.** Machine-specific paths remain in `configs/` and `_throughput_from_log`.
- [ ] **B3.** Build only from the provided package list: parquet (no pyarrow), `shap`, and
  numpy-2 pickles in the package must be replaced. 261 of 271 tests already pass there.

## C. Functional requirements (PS9)

| FR | Requirement | State | What is missing |
|---:|---|---|---|
| 03 | Entity representation | partial | Customers, branches, products — no corpus has them (open by choice) |
| 06 | Typology detection | partial | Hinting missed its bar (pre-fix); not re-run |
| 07 | ML anomaly detection | partial | Unsupervised arm not usefully combined; not re-run |
| 08 | Risk scoring | partial | Customer/branch/product risk — depends on FR-03 |
| 12 | Near-real-time | partial | See A4 |

FR-09 (explainability) closed 2026-09-22: graph reasons are named from GFP's documented layout.

## D. Toward production

**Presentable as research; not deployable for AML decisions.**

1. **Investigation aid (2–4 weeks).** *Product repo:* load `scores.csv`, `cases/`, `run.json`
   into a database; build the case view against `contracts/`. *AI repo:* schedule `score.py`
   with `--emit-from` and ≥ 2 days of history.
2. **Shadow mode (2–3 months).** Retrain on the bank's own data; capture analyst dispositions
   back into bundles; measure the false-positive cost on real cases.
3. **Production candidate (6+ months).** Multi-rail laundering data (A1); throughput at real
   volume (A4); model governance — validation on real data, drift monitoring, retraining.

Stage 3 is blocked on data, not code.

---

## E. From the LinuxONE handoff (2026-09-24)

Shivraj ran the deployment notebooks on the datathon VM and sent
`HANDOFF_VIKA_2026-09-24.md`. The code items are done (see
[`WINNING_PLAN.md`](WINNING_PLAN.md)); these four are decisions, not patches.

- [x] **E1. Keras ships.** Decided 2026-09-26. `02_keras_model.ipynb` is restored as the
  neural notebook and carries the protobuf import order, the corpus setting, the raised
  epoch cap and the P5 report. The PyTorch port (`02_neural_model.ipynb`) is removed; it
  stays in git history at `136c07a^` and needs no protobuf handling, should TensorFlow
  become unusable here again.
- [ ] **E2. BIPARTITE at zero recall fails our own gate P5.** Measured on the Keras DNN
  across all four seeds; the tree models do catch it. **State it either way** — the
  notebook now names the failing typology instead of averaging it away.

  **Note (2026-09-30):** In the 2-day LinuxONE window (170,585 rows, 127 positives) there
  is exactly **1 BIPARTITE positive**, ranked at the **92.4th percentile**. A gate decided
  by a single transaction is not evidence either way; neither a pass nor a fail on that one
  case should be read as a claim about BIPARTITE detection in general. State this clearly
  next to the gate result in the notebook.

  What can fix it, cheapest first:
  1. **Diagnose before treating** (in the notebook, section 7b, no training): if the missed
     positives' *best percentile* is near 100 the pattern is visible and the 1% budget is
     the binding constraint; a median near 50 means the network cannot see it at all. The
     two cases need different fixes, and we have never checked which one this is.
  2. **Blend with E2 by rank** (section 7b, no retraining, minutes): a rank-average of the
     two models keeps the extra alerts the network finds while restoring a typology the
     trees already catch. The blend table reports which weights leave no typology at zero.
     This is the fix to reach for if the diagnosis says "near miss".
  3. **Scale the heavy tails** (~20 lines, one retrain): GFP counts and amounts are
     extremely skewed, and `StandardScaler` compresses exactly the large values that make a
     fan-in or bipartite pattern visible. `log1p` before scaling, or a quantile transform,
     is the standard remedy and the likeliest cause if the diagnosis says "invisible".
     Trees are scale-invariant, which would explain why only the network misses it.
  4. **Weight the rare typologies in training** — effective but easy to do wrongly: the
     weights must come from training-partition typologies only, and only 62% of positives
     carry one, so it optimises for a labelled subset.
- [ ] **E3. Is the neural arm worth shipping at all?** Over seeds 42/1/2/3 its PR-AUC is
  0.0407 / 0.0462 / 0.0231 / 0.0297 against XGBoost's 0.0325 — two of four seeds below the
  tree model. It does catch 4–9 more of 127 laundering transactions at a 1% review budget
  in every seed. "The DNN beats XGBoost" is not a claim the numbers support. Options:
  1. **Report the narrow claim** (free): not better on PR-AUC; consistently finds a few
     alerts the trees miss at a fixed budget. This is what the numbers support and it is
     what the comparison table should say.
  2. **Ship the blend rather than the network** (free, section 7b): if rank-averaging beats
     both arms, the honest headline is the ensemble, and E2 is likely solved with it.
  3. **Average several seeds** (~15 minutes of VM time): score 3–5 seeds and average the
     ranks. A 0.0231 seed next to a 0.0462 one is variance, and averaging is the standard
     way to stop reporting whichever seed we happened to run.
  4. **Only then tune the architecture.** Depth, width and dropout are the least promising
     lever here and the most time-consuming.

  **Note (2026-09-30):** Cell 22 scores five blend weights **on the test set**. Using this
  as a diagnostic is fine, but do **not** report the best row (PR-AUC 0.0556) as a result
  unless the weight was chosen on the **validation** set first. Until then the best-row
  number is an optimistic oracle figure, not a deployable claim.

- [ ] **E4. Does `Vika/` belong in git?** It sits untracked in the other team's repository.
  It is this repository's work, so it belongs on a branch here rather than there.
- [ ] **E5. LinuxONE 2-day window numbers (2026-09-30 clean run).** Both notebooks ran
  clean on the VM (no reused caches): `01` in 6 min 14 s at 2.10 GB peak RAM, `02` in
  4 min 29 s. All self-checks pass. Results on HI-Small, 2-day window, 170,585 rows,
  127 positives:

  | Model | PR-AUC | recall@1% |
  |---|---:|---:|
  | E2 GFP + XGBoost | 0.0325 | 36.2% |
  | Keras DNN (seed 42, 150-epoch cap, early stopping) | 0.0389 | 36.2% |

  The DNN catches exactly as many cases as E2 at 1% (46 of 127); it does not beat the tree
  model on PR-AUC. These are window-level demonstration numbers, not the shipped model.
