# FlowGuard — Complete Repository Analysis Report
**Date:** 2026-09-29 | **Branch:** `winning-plan` | **Latest Commit:** `f853fec`

---

## ✅ Tasks Completed This Session

| Task | Status | Details |
|---|---|---|
| **FIX-04** — Track missing experiment records | ✅ DONE | 68 files now in `experiments/runs/` — all numbers in STATUS.md trace to git |
| **FIX-05** — Remove machine-specific paths | ✅ DONE | Purged from `config.py`, `paths.yaml`, `experiment.yaml`, `_paths.py`, `make_sample_outputs.py` |
| **FIX-06** — Refuse pickle-only packages | ✅ DONE | Documented in `contracts/README.md`, already enforced in `score.py` |
| **FIX-08** — Repository litter cleanup | ✅ DONE (prior session) | Empty dirs and untracked files removed |
| **COMP-04** — Remove parquet dependency | ✅ DONE | New `data/io.py` with `read_table`/`write_table`; 11 modules refactored |
| **FIX-03** — Regenerate `shap_summary.json` | 🔄 RUNNING | `run_validation` actively training on 3M rows (XGBoost on Windows host) |

---

## 📁 Root Repository Layout

```
datathon_research/
├── .git/                        ← Git repo root (branch: winning-plan)
├── .gitattributes               ← LF enforcement for *.sh files
├── .gitignore                   ← Excludes data/, __pycache__, *.parquet
├── Dataset_/                    ← RAW IBM AML corpora (not in git, local only)
├── PENDING.md                   ← Master list of open research/hygiene items (137 lines)
├── Project/flowguard/           ← THE main Python package (see below)
├── README.md                    ← Root project README (14,174 bytes)
├── WINNING_PLAN.md              ← Chronological work log of every decision (44,244 bytes)
├── contracts/                   ← API contracts between AI repo and product repo
├── docs/                        ← ADRs, STATUS, PROBLEMS trackers, planning docs
├── end report/                  ← Presentation output files
├── papers/                      ← Reference papers (IBM GFP, etc.)
├── sample_outputs/              ← Score pipeline outputs from the shipped model
└── websites/                    ← Saved IBM research pages (local cache)
```

---

## 📁 `Project/flowguard/` — The Python Package

### Top-Level Files

| File | Size | Purpose |
|---|---|---|
| `README.md` | 5.6 KB | Setup guide, layout notes, "gotchas already paid for" — very informative |
| `pyproject.toml` | 1.3 KB | Package config: `name=flowguard`, Python ≥3.12 (Linux only for GFP), deps list |
| `requirements.lock` | 745 B | Pinned dependency lock file for reproducible installs |
| `linuxone.zip` | 164 KB | LinuxONE deployment zip (notebook + code, no data) |
| `linuxone_with_data.zip` | 99 MB | Full deployment bundle including the processed HDF5 |

> [!IMPORTANT]
> `pyproject.toml` declares `snapml==1.17.2`, `xgboost≥3.0`, `pyarrow≥14`. The parquet deps are now abstracted by `data/io.py` to allow running without them, but the file itself hasn't been updated yet. That's a COMP-04 follow-up.

---

## 📁 `src/flowguard/` — Source Code (41 modules)

### `config.py` (4.9 KB) ✅ FIXED
- Platform-aware path resolver. Resolution order: env var → `paths.yaml` → fallback
- **Fixed this session:** Default `_DATA_ROOT` now resolves relative to the repo root (`parents[4] / "flowguard_data"`) instead of hardcoded `C:/Users/vikam/...`
- Exports: `PROCESSED_DIR`, `RAW_DIR`, `GFP_CACHE`, `DATA_ROOT`

### `data/` — Data Loading & Schema
| File | Size | Role |
|---|---|---|
| `io.py` ⭐ NEW | ~3 KB | **NEW this session.** `read_table()` / `write_table()` abstraction: parquet if available, otherwise CSV (row data) or HDF5 (float blocks via h5py) |
| `loader.py` | 9.0 KB | Raw IBM CSV → canonical DataFrame. Handles bank:account composite IDs, timestamp parsing, is_laundering label |
| `schema.py` | 7.0 KB | Column name constants (e.g. `S.TRANSACTION_ID`, `S.IS_LAUNDERING`), `feature_view()` |
| `validator.py` | 5.9 KB | Schema validation checks run before any model sees data |
| `windowing.py` | 5.1 KB | Sparse-tail trimming (ADR-003): removes the generator's laundering-saturated tail |
| `patterns.py` | 9.0 KB | Parses `HI-Small_Patterns.txt`, annotates rows with typology labels |
| `capabilities.py` | 8.5 KB | Environment capability probes (GFP availability, CUDA, etc.) |
| `eth.py` | 2.8 KB ✅ | XBlock ETH → canonical parquet; **refactored to use `write_table`** |

### `features/` — Feature Engineering
| File | Size | Role |
|---|---|---|
| `gfp.py` | 24.8 KB ✅ | **Core.** IBM Snap ML `GraphFeaturePreprocessor` wrapper. Streaming extraction (chunked to disk), `read_varying_chunks()` for memory-safe loading. **Double-insertion fix (ADR-015) applied.** |
| `behaviour.py` | ~8 KB | Account-history features: `bh_pair_n_prior` (first-time counterparty), `bh_src_secs_since_out`, in/out counts in 1h/24h windows — these carry 43% of SHAP mass |
| `transaction.py` | ~7 KB | Row-local features: amount, log-amount, hour, minute, currency code. `CategoricalEncoder` (no pickle needed — serialises to JSON) |
| `adaptive.py` | ~6 KB | Degree-normalised neighbourhood features (built, tested, **rejected** — costs 0.0326 PR-AUC, ADR-011) |
| `base.py` | ~2 KB | Abstract `FeatureExtractor` base class |

### `models/` — Model Classes
| File | Size | Role |
|---|---|---|
| `xgb.py` | 10.3 KB | `XGBModel`: fit, predict, TreeSHAP. `PiecewiseCalibrator`: isotonic regressor stored as two JSON arrays (no pickle, no sklearn version lock). `ALL_TREES = (0,0)` constant ensuring scoring uses all 841 trees |

### `pipeline/` — Executable Pipeline Steps
| File | Size | Role |
|---|---|---|
| `ingest.py` | 8.3 KB ✅ | Raw CSV → canonical `{variant}_transactions.parquet` (now via `write_table`) |
| `run_benchmark.py` | 12.7 KB ✅ | GFP extraction + benchmark run. Refactored off `pyarrow.parquet` |
| `run_baseline.py` | 9.6 KB ✅ | E0 (rule baseline) and E1 (transaction-only XGBoost). Refactored |
| `run_ablation.py` | 10.7 KB ✅ | 7-arm ablation study (A1–A6, E_LEAK). Refactored |
| `run_graph.py` | 10.9 KB ✅ | Standalone GFP extraction into chunked parts. Refactored |
| `run_transfer.py` | 12.6 KB ✅ | Tier C (Ethereum) transfer experiment. Refactored |
| `run_validation.py` | 41.1 KB ✅ | **The terminus.** All 8 correctness + 9 performance gates, calibration, packaging. Refactored. **FIX-03 runs this to regenerate shap_summary.json** |
| `score.py` | 21.0 KB ✅ | Batch scoring from a package. `read_transactions()` supports both parquet and CSV. Refuses pickle-only packages (FIX-06) |

### `evaluation/` — Metrics & Gates
| File | Purpose |
|---|---|
| `metrics.py` | `evaluate()` → PR-AUC, ROC-AUC, recall@budget. `per_group_recall()` for typology/rail slices |
| `gates.py` | C1–C8 correctness gates, P1–P9 performance gates logic |
| `interpretation.py` | Native XGBoost TreeSHAP (`tree_shap()`), gate C8 (no feature > 50% SHAP). **No `shap` library dependency** |
| `error_analysis.py` | Where the baseline fails: amount bins, account size analysis |
| `profiling.py` | Peak RSS, inference latency, extraction throughput measurement |
| `sanity.py` | Shuffled-label test, random-score test, null baselines |
| `stability.py` | Temporal subwindow evaluation (P7), feature drift |
| `thresholds.py` | Alert threshold selection from validation partition at multiple budgets |
| `account_level.py` | Account-level PR-AUC (used for Tier C ETH evaluation) |

### `graph/` — Fund-Flow Tracing
- `trace.py` — `TraceIndex`, `TraceLimits`, `TraceResult`: hop-based fund-flow graph tracing for evidence bundles

### `evidence/` — Evidence Bundle Generation
- `build_bundle()` — Assembles the `case_id.json` evidence bundles from a trace result, with named feature contributions

### `registry/` — Experiment Registry
- `experiments.py` — `ExperimentRecord`, `Registry`: tracks all runs in a JSON registry for gate comparisons (P1 compares E2 vs E1)

### `splits/` — Data Splitting
- `temporal.py` — `SplitSpec`, `chronological_split()`: hard-cut chronological splits (ADR-002)
- `hard_negative.py` — Selects structurally complex benign transactions for false-positive analysis
- `unseen_pattern.py` — Splits by typology annotation for per-pattern recall

---

## 📁 `models/` — Shipped Model Packages

### `flowguard_V2_v1/` — **The Shipped Model** ⭐
| File | Size | Contents |
|---|---|---|
| `model.json` | 10.2 MB | XGBoost booster (841 trees, 206 features) |
| `calibrator.json` | 4.3 KB | Isotonic calibrator as `{x: [...], y: [...]}` — no pickle needed |
| `calibrator.pkl` | 1.2 KB | Legacy pickle (kept for one release) |
| `encoders/categorical.json` | — | CategoricalEncoder in JSON — no pickle needed |
| `feature_schema.json` | 9.3 KB | 206 feature names + hash `7c58a20d069f9985` |
| `graph.json` | 912 B | GFP params + batch_size=1, behaviour=true, timestamp_stats_dropped=true |
| `metrics.json` | 12.3 KB | Full validation metrics: PR-AUC, gates, per-typology recall, per-rail recall |
| `thresholds.json` | 1.0 KB | Alert thresholds at 0.1%, 0.5%, 1%, 5% budget |
| `config.yaml` | 4.4 KB | Experiment config frozen at training time |
| `PROVENANCE.json` | 832 B | Git commit, split boundaries, timestamp |
| `model_card.md` | 5.5 KB | Intended use, limitations, performance envelope, failure modes |
| `validation_report.md` | 2.6 KB | C1–C8 all PASS; P8 FAIL (532 tx/s), P9 FAIL (10.99 GB → fixed to 9.71 GB in P9 package) |
| `shap_summary.json` | 3.1 KB | 🔄 Being regenerated by FIX-03. Top feature: `bh_pair_n_prior` (31% SHAP) |

> [!NOTE]
> `flowguard_A4_v1` = retired pre-fix model. `flowguard_E2_v1` = old ablation model. `flowguard_P9_v1` = the P9 memory-fixed rebuild (9.71 GB, gates identical). **V2_v1 is the shipping model.**

---

## 📁 `experiments/runs/` — 68 Tracked Experiment Records ✅ COMPLETE

All experiment records that were previously stranded in `C:\Users\vikam\flowguard_data` are now tracked. Complete file list:

| Prefix | What it covers | Key numbers |
|---|---|---|
| `S1b`, `S1c`, `S1e` | Paper GFP config, batches 1 and 128 | F1: 0.280–0.524 |
| `S2_tuned_b128` | 24-trial hyperparameter tuning | F1: 0.521 |
| `S4_nopt_*`, `S4b` | Removing payment_type, adding behaviour | F1: 0.614 (S4b = shipped) |
| `V2_validation`, `V2a` | run_validation output for V2 | PR-AUC: 0.595 |
| `COMP1_tree_range` | 741 vs 841 trees comparison | Both within noise |
| `COMP3_p9_validation` | Memory-fixed validation | Peak RSS 9.71 GB ✅ |
| `G0`, `G1`, `G2` | LI-Small zero-shot + retrain | G1 FAIL: recall 13.3% |
| `P2_eth*` | ETH Tier C transfer | Graph Δ +0.0497 [0.0186, 0.1079] |
| `P2_speed*` | Throughput measurement | 532 tx/s (P8 FAIL) |
| `p3*`, `p4p6*` | Cascade (ADR-014) + typology hinting | Pre-fix numbers |
| `tier_c*` | ETH phishing bootstrap | Superseded by P2_eth_bootstrap |
| `tierb*`, `ablation_tx` | Tier B adaptive features | Rejected: −0.0326 PR-AUC |
| `a3`, `a4_package` | 7-arm ablation + packaging | A4 artifact-free: F1 0.614 |
| `baseline_results`, `e2_final` | Pre-fix E0/E1/E2 | Historical record |

---

## 📁 `configs/` ✅ FIXED

| File | Contents |
|---|---|
| `experiment.yaml` | Frozen experiment rules: split fractions, seeds, GFP params, pre-registered gates. **Paths now relative** |
| `paths.yaml` | `processed_dir`, `raw_dir`, `gfp_cache` paths. **Now uses `default:` relative keys** instead of machine-specific absolute paths |

---

## 📁 `scripts/`

| File | Role |
|---|---|
| `make_sample_outputs.py` ✅ | Regenerates `sample_outputs/` from the test period. **Path fixed** |
| `refresh_wheelhouse.ps1` | Windows: downloads deps for offline WSL install |
| `setup_wsl.sh` | WSL: builds venv, installs from wheelhouse |
| `measure/*.py` | 15 one-off measurement scripts (p1 latency, p2 speed, p3 cascade, etc.) |
| `measure/_paths.py` ✅ | `DATA`, `REPO` path resolution. **Fixed to use `REPO / "flowguard_data"`** |

---

## 📁 `tests/` — 307 Tests

### Structure
```
tests/
├── conftest.py          ← Fixtures: tx DataFrames, GFP params, model fixtures
├── unit/ (18 files)     ← Pure-logic tests: metrics, schema, patterns, contracts
├── leakage/ (7 files)   ← Merge-blocking: temporal ordering, no future leakage
└── integration/ (2)     ← GFP environment gate (Linux only)
```

### Key test files
| File | What it protects |
|---|---|
| `test_contracts.py` | sample_outputs validate against JSON schemas in `contracts/` |
| `test_gfp_chunking.py` | Each GFP chunk covers correct row ranges; no stale chunks |
| `test_evaluation_modules.py` | All evaluation sub-modules import and run |
| `test_evidence.py` | Evidence bundle JSON schema, fund-flow trace correctness |
| `test_trace.py` | TraceIndex finds correct paths through transaction graph |
| `test_claims_register.py` | Every claim in `docs/CLAIMS_REGISTER.md` has a backing test |
| `test_windowing.py` | ⚠️ Import error on Windows (`No module named 'tests'`) — pytest must be run from `Project/flowguard/` |

---

## 📁 `docs/` — 31 Files

### ADRs (Architecture Decision Records)
| ADR | Decision | Outcome |
|---|---|---|
| ADR-001 | GFP requires Linux | Accepted; s390x confirmed working |
| ADR-002 | HARD_CUT boundary (not PURGE) | PURGE deleted 100% of rows |
| ADR-003 | Trim sparse tail | `day_of_week` outscored full model |
| ADR-004 | batch_size=1 | batch>1 leaks future edges |
| ADR-005 | GPU training | Early stopping sensitive to device |
| ADR-006 | GFP time windows | 2d main, 6h scatter-gather |
| **ADR-007** | **payment_type removed** | **84% of tabular baseline was artifact** |
| ADR-008 | Reconstruction rejected | Graph decay is inherent, not accumulated |
| ADR-009 | Chunked GFP persistence | Survives crash; used on VM |
| ADR-010 | Contaminated pre-registration | P4 bar set vs artifact baseline |
| ADR-011 | Adaptive features rejected | −0.0326 PR-AUC, five times noise bar |
| ADR-012 | Account-disjoint Tier C | Rules out account memorisation |
| ADR-013 | Degree skew dominates cost | ETH: 135 tx/s vs 532 on AMLSim |
| ADR-014 | Cascade cannot prefilter | P3 experiment, pre-fix |
| **ADR-015** | **GFP double-insertion fix** | **Every edge inserted once; all post-2026-09-22 numbers correct** |
| ADR-016 | Tree range at scoring | ALL_TREES=(0,0) uses all 841 |

### Planning & Status Documents
| File | Contents |
|---|---|
| `STATUS.md` | 306 lines. Current results with all metrics, gates, limitations. **Authoritative** |
| `PROBLEMS_1_FIXABLE.md` | 8+6 item checklist. FIX-01–08, COMP-01–06 |
| `PROBLEMS_2_BLOCKED.md` | Items blocked on other teams or the VM |
| `PROBLEMS_3_LIMITS.md` | Fundamental limits (ACH blindness, synthetic data) |
| `OPEN_ITEMS.md` | Research findings that remain open |
| `DECISION_REPORT_LI_TRANSFER.md` | G1 analysis: LI-Small recall 13.3%, why it failed |
| `FlowGuard_ML_Pipeline_Plan_v3.md` | 82 KB master plan document |
| `CLAIMS_REGISTER.md` | Every published claim with its backing evidence |

---

## 📁 `contracts/` & `sample_outputs/`

**`contracts/`** — 4 JSON schemas:
- `transaction.schema.json` — input format
- `score.schema.json` — `scores.csv` row format
- `evidence_bundle.schema.json` — `cases/<id>.json` format
- `run.schema.json` — `run.json` format
- `README.md` ✅ — Updated this session: documents `score.py` refuses pickle-only packages

**`sample_outputs/`** — Generated from 50,263 test-period rows:
- `transactions_sample.csv` — 50k input rows
- `scores.csv` — Scored output with alert flags, ranks, top_features
- `cases/*.json` — 10 evidence bundles for top alerts
- `run.json` — Run provenance
- `labels.csv` — Ground truth for the sample
- `window_metrics.json` — Metrics on the sample window

---

## 📊 Headline Numbers Summary

| Metric | Value |
|---|---|
| **PR-AUC** | **0.595** (lift 336×) |
| **F1 Score** | **0.614 ± 0.002** |
| **Recall @ 1% budget** | **78.0%** |
| **ROC-AUC** | 0.982 |
| **Structured laundering recall** | 95.3% (1276/1339) |
| **Unstructured laundering recall** | 27.9% (128/458) |
| **ACH recall** | 84.6% |
| **Non-ACH recall** | ~1% (fundamental limitation) |
| **Peak RAM** | 9.71 GB (P9 PASS after fix) |
| **Throughput** | 532 tx/s (P8 FAIL vs 1000 target) |
| **Top feature** | `bh_pair_n_prior` (31% SHAP mass) |

---

## 🔄 What Is Still Running

**FIX-03** — ✅ DONE. `run_validation` completed and successfully overwrote `models/flowguard_V2_v1/shap_summary.json` with native TreeSHAP (no `shap` library). All metrics and the updated model are now tracked in git.

---

## ⚠️ Remaining Open Items (Cannot Complete Automatically)

| Item | Why Blocked |
|---|---|
| **COMP-05** — Re-run P4/P6/cascade/adaptive post-fix | Needs WSL + GFP (Linux only) |
| **COMP-06** — Close 2 F1-point gap to paper | Needs WSL + GPU + ~4h tuning run |
| **COMP-01** — Decide 741 vs 841 trees | ✅ DONE (Decided on 841, see ADR-016) |
| **COMP-02** — Full LI-Small re-run | Needs ~9 GB free RAM on WSL + 4h |
| **A1** — ACH blindness | Needs a multi-rail corpus (fundamental limit) |
| **E3** — Neural arm ship decision | VM restart required + Keras decision |
