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

Closed since 2026-09-21: the push to GitHub; the GFP double-insertion defect
([ADR-015](docs/ADR-015-gfp-double-insertion.md)); tuning (F1 0.280 → 0.521); the benchmark
comparison; named reasons for every feature (FR-09); the v2 package; history-aware scoring
(cold start); the Ethereum re-run (holds); timestamp statistics dropped as a time proxy;
the experiment registry and run records — never in git before — now tracked.

---

## A. Research findings still open

- [ ] **A1. Blind off ACH.** — *most serious.* v2 recall at 1%: ACH 84.6%; cheque 4.2%;
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
- [ ] **A5. Memory (P9).** 10.99 GB peak against 10 GB, from training over the full table.
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
