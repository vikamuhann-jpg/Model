# FlowGuard

**Graph-structural features for anti-money-laundering detection — measured, not assumed.**

> Do graph-structural features measurably improve transaction-level AML detection over a
> tabular baseline — and at what cost in throughput and memory?

Built for **Datathon problem statement PS9 — *Tracking of Funds within Bank for Fraud
Detection*.** This repository answers one falsifiable question from inside PS9 on two
independent corpora, and adds the investigator-facing layer — fund tracing, evidence
bundles — on top.

> **This is the AI repository.** It holds the model, the code that trains and scores it, and
> the evidence behind every number. The frontend, backend and database live in a **separate
> product repository**, which consumes exactly two things from here:
> **[`contracts/`](contracts/)** (what the outputs look like) and
> **[`sample_outputs/`](sample_outputs/)** (real outputs to build against).
> Product developers start at [`contracts/README.md`](contracts/README.md).

Remaining work is tracked in **[`PENDING.md`](PENDING.md)**.

---

## Status at a glance

| | |
|---|---|
| **Research question** | Answered on two corpora. Graph features work, and transfer to a real network. |
| **Shipped model** | `flowguard_A4_v1` — PR-AUC **0.1400 ± 0.0030**, all 8 correctness gates pass, no simulator artifact |
| **Scoring** | `python -m flowguard.pipeline.score` — batch, Linux; 50,000 transactions in ~11 s on a cold graph |
| **Functional requirements (PS9)** | 6 built · 6 partial · 0 absent, of 12 |
| **Tests** | **261 passing**, including contract tests on every sample output |
| **Decision records** | 14 ADRs — six document defects caught, four document work rejected on evidence |
| **Production-ready?** | **No.** See [Where this stands](#where-this-stands) |

---

## Headline results

**Synthetic corpus — IBM AML HI-Small** (5,077,237 transactions, 4,522 positives, 0.089%)

| Arm | Features | PR-AUC | Recall @1% |
|---|---:|---:|---:|
| Tabular, simulator artifact removed | 12 | 0.0065 ± 0.0001 | 11.6% |
| **+ graph features, artifact removed — shipped as A4** | 167 | **0.1400 ± 0.0030** | 56.2% |
| + graph features, artifact present (E2 — research only, not shipped) | 168 | 0.2048 ± 0.0065 | 66.2% |

E2 scores higher because it leans on `payment_type`, a simulator artifact that nearly
identifies an injected pattern ([ADR-007](docs/ADR-007-payment-type-artifact.md)). That lift
would not survive real data, so the model this repository ships is A4.

Graph structure lifts PR-AUC **21×** over the honest tabular baseline and carries 69.8% of
the model's attribution mass.

**Real network — XBlock Ethereum phishing graph** (account-level, account-disjoint protocol)

| Arm | Account PR-AUC | 95% CI (paired bootstrap) |
|---|---:|---:|
| Tabular only | 0.0032 | [0.0016, 0.0071] |
| + graph features | 0.0536 | [0.0216, 0.1263] |
| **Delta** | **+0.0504** | **[0.0187, 0.1231]** |

2,000 of 2,000 bootstrap resamples favour the graph arm. The direction is settled; the
magnitude is not — the scored set holds only 20 illicit accounts.

---

## Where this stands

**Presentable as research: yes.** **Deployable for real AML decisions: no.**

| Blocker | Why it matters |
|---|---|
| Catches **1 of 100** laundering transactions outside ACH | 2,553 of 2,554 injected patterns in the training corpus use one payment rail ([ADR-007](docs/ADR-007-payment-type-artifact.md)). Removing the artifact from the model does not add the missing training examples. |
| Most of each case's reasons are unnamed graph features | The graph library exposes no feature names, so its features are positions, not concepts |
| Extraction ~450 tx/s synthetic, ~139 tx/s real | Cost is intrinsic to the method ([ADR-013](docs/ADR-013-degree-skew-dominates-cost.md), [ADR-014](docs/ADR-014-cascade-cannot-prefilter.md)) |
| 2.1× false positives on legitimate complexity | Merchant hubs, payroll fan-out, treasury sweeps (A4; E2 was 2.3×) |
| Trained only on synthetic data | Real-network evidence rests on 20 positive accounts |

**Usable today, with no model risk:** fund tracing ([`graph/trace.py`](Project/flowguard/src/flowguard/graph/trace.py))
and the evidence bundle ([`evidence/bundle.py`](Project/flowguard/src/flowguard/evidence/bundle.py)).
Both are correct or incorrect independently of detector quality.

---

## Repository map

```text
flowguard/  (this repository — AI only)
├── README.md                  this file — the master guide
├── PENDING.md                 everything still to do, prioritised
├── .gitignore
│
├── contracts/                 THE HANDOFF — four JSON schemas the product repo builds against
├── sample_outputs/            real scored output from the shipped model, 12 MB
│
├── Project/flowguard/         THE CODE — the Python package, tests, configs, model
│   ├── src/flowguard/         the library: 9 packages, 39 modules
│   ├── tests/                 261 tests: unit / leakage / integration
│   ├── models/
│   │   └── flowguard_A4_v1/   THE SHIPPED MODEL, 2 MB
│   ├── scripts/               environment setup, sample regeneration, measure/ scripts
│   ├── configs/               frozen experimental rules and platform paths
│   ├── experiments/           experiment registry (results.csv tracked)
│   ├── reports/               exported cases                  [local only]
│   ├── notebooks/             empty — reserved
│   └── data  ──►              junction to the external data folder  [local only]
│
├── docs/                      THE REASONING — plans, 14 ADRs, status, analyses
│   └── archive/               superseded v1 planning
│
├── papers/                    three reference papers (PDF)
├── websites/                  five saved reference pages (HTML only)
└── end report/                pointer to the published reports

Kept on the build machine, not in the repository:
  Dataset_/   raw corpora, 4.4 GB      models/flowguard_E2_v1/   the research model
```

`[local only]` means excluded by `.gitignore`.

---

## Directory guide

### `/` — repository root

| File | Purpose |
|---|---|
| `README.md` | This master guide: what the project is, what every directory holds, where it stands. |
| `PENDING.md` | Every outstanding task, grouped by what it blocks. |
| `.gitignore` | Keeps corpora, research models and reports out of git; lets the shipped model and the sample outputs in. |

---

### `contracts/` — the handoff to the product repository

Four JSON Schemas, and the only agreement between this repository and the product one.
[`contracts/README.md`](contracts/README.md) explains how the outputs flow into a database
and the eight rules a UI must follow — show the coverage warning on the case, order by rank,
never call per-hop amounts "funds traced", and so on.

| File | Describes |
|---|---|
| `transaction.schema.json` | One input transaction |
| `score.schema.json` | One row of `scores.csv` |
| `evidence_bundle.schema.json` | One investigation case |
| `run.schema.json` | One scoring run's summary |

### `sample_outputs/` — real output to build against, 12 MB

50,000 test-period transactions scored by the shipped model through the real entry point,
plus ten evidence bundles and the run summary. Every file is validated against `contracts/`
by a test. They are format examples, not accuracy figures — see
[`sample_outputs/README.md`](sample_outputs/README.md). Regenerate with
`python scripts/make_sample_outputs.py`.

---

### `Project/flowguard/` — the code

The entire implementation. An installable Python package (`pyproject.toml`), its tests, its
configuration and its outputs. Linux-only: the graph library's native backend ships only in
manylinux wheels ([ADR-001](docs/ADR-001-gfp-platform.md)), so everything runs under WSL2
Ubuntu 24.04, CPython 3.12.

| File | Purpose |
|---|---|
| `pyproject.toml` | Package metadata and dependencies; installs `flowguard` in editable mode. |
| `requirements.lock` | Exact pinned versions — `snapml 1.17.2`, `xgboost 3.4.1` among them. |
| `README.md` | Setup instructions specific to the package. |

#### `src/flowguard/` — the library

Nine packages. Each owns a stage of the pipeline; data flows top to bottom.

##### `data/` — 7 modules, 1,351 lines
Everything between a raw file and a clean, canonical frame.

| Module | Purpose |
|---|---|
| `schema.py` | The canonical column contract, and the **label-blindness guard**: `feature_view()` strips the target and raises `LabelLeakageError` if a feature ever sees it. |
| `loader.py` | Reads the IBM CSVs. Resolves the duplicated `Account` header positionally and builds a composite `bank:account` identity. |
| `patterns.py` | Parses `*_Patterns.txt` and attaches typology labels by natural key. Ambiguous keys are left unlabelled rather than guessed. |
| `validator.py` | Integrity checks. Reports self-transfers instead of silently dropping them. |
| `windowing.py` | Trims the generator's sparse, laundering-saturated tail ([ADR-003](docs/ADR-003-sparse-tail-trim.md)). |
| `capabilities.py` | Declares what each corpus actually provides — derived from the data, not from column presence — so experiments a corpus cannot support are disabled rather than faked. |
| `eth.py` | Converts the Ethereum phishing graph (a pickled NetworkX graph) to the canonical schema. |

##### `splits/` — 3 modules, 652 lines
How data is divided so nothing from the future reaches training.

| Module | Purpose |
|---|---|
| `temporal.py` | Chronological split with explicit boundary policies. `HARD_CUT` is the default because the plan's preferred purge policy erases the corpus ([ADR-002](docs/ADR-002-boundary-policy.md)). |
| `hard_negative.py` | Slices out structurally complex but *benign* traffic — the control that measures false-positive cost. |
| `unseen_pattern.py` | Holds out whole laundering patterns to test generalisation to unseen instances. |

##### `features/` — 5 modules, 975 lines
Turning transactions into model inputs.

| Module | Purpose |
|---|---|
| `base.py` | Shared extractor interface, with fit-scope recorded so a feature cannot be fitted on test data. |
| `transaction.py` | Row-local tabular features. `payment_type` is optional because it is a simulator artifact ([ADR-007](docs/ADR-007-payment-type-artifact.md)). |
| `gfp.py` | Streaming graph extraction via IBM Snap ML's Graph Feature Preprocessor. One transaction at a time (batching leaks the future — [ADR-004](docs/ADR-004-gfp-batch-leakage.md)), a bounded time window, and chunked persistence so a crash costs one part rather than the run ([ADR-009](docs/ADR-009-chunked-extraction.md)). |
| `adaptive.py` | Degree-normalised neighbourhood features. **Built, measured, rejected** — cost 0.0326 PR-AUC ([ADR-011](docs/ADR-011-adaptive-features-rejected.md)). Kept, not wired in. |
| `cascade.py` | Two-tier scoring to meet the throughput gate. **Built, measured, rejected** — meets the gate and loses half the recall ([ADR-014](docs/ADR-014-cascade-cannot-prefilter.md)). Kept, not wired in. |

##### `graph/` — 1 module, 445 lines
Traversal: following the money.

| Module | Purpose |
|---|---|
| `trace.py` | **Fund tracing (FR-05).** Forward and backward traces from an account, strictly time-ordered so no path runs backwards, bounded by a per-vertex degree cap and a total edge budget. Reports truncation instead of hiding it. p95 168 ms at horizon 4 on 5M rows. |

##### `evidence/` — 1 module, 481 lines
The case object an investigator reads.

| Module | Purpose |
|---|---|
| `bundle.py` | **Evidence bundles (FR-09, FR-11).** A self-validating case: trace, transactions, per-case reasons, threshold provenance, model version, and a coverage warning for rails the model cannot see. `check_internal_consistency()` enforces that no field states a fact its own path does not. Round-trips byte-identically. |

##### `models/` — 4 modules, 695 lines

| Module | Purpose |
|---|---|
| `rules.py` | The E0 rule-based baseline — fixed thresholds, the thing the project had to beat. |
| `xgb.py` | XGBoost wrapper: fit, calibrate, predict, device resolution. Early-stopping patience is 100 because GPU training undertrained silently at 30 ([ADR-005](docs/ADR-005-gpu-training.md)). |
| `tuning.py` | Rolling-origin hyperparameter search — never tunes against the test period. |
| `typology.py` | Typology hinting (FR-06). **Built, measured, did not clear its bar** — macro-F1 margin 0.1265 against a required 0.1405. Kept, not wired in. |

##### `evaluation/` — 9 modules, 1,660 lines
Everything that decides whether a number is real.

| Module | Purpose |
|---|---|
| `metrics.py` | PR-AUC, ROC-AUC, lift, and recall/precision at fixed alert budgets. |
| `thresholds.py` | Operating thresholds with recorded provenance — which data picked them, and how. |
| `sanity.py` | Shuffled-label and random-score baselines; a model must beat both. |
| `interpretation.py` | Global SHAP attribution with gate C8 (no feature above 50% of mean attribution), and per-case local contributions for evidence bundles. |
| `stability.py` | Performance across time windows, plus PSI/KS drift. |
| `profiling.py` | Throughput and peak-memory measurement at steady state, not startup ([ADR-006](docs/ADR-006-gfp-time-window.md)). |
| `account_level.py` | Rolls transaction scores up to accounts. Used for the real-network evaluation, where labels exist only per account. |
| `error_analysis.py` | Where a model fails — by amount band, rail, typology and chain position. |
| `gates.py` | The pre-registered validation gates C1–C8 (correctness) and P1–P9 (performance). |

##### `pipeline/` — 7 modules
Command-line runners that compose the library into experiments, and the one that scores.

| Module | Purpose |
|---|---|
| `score.py` | **Batch scoring with a shipped model package — the entry point the product relies on.** Reads transactions, builds graph and tabular features exactly as training did, scores, and writes `scores.csv`, evidence bundles and `run.json`. Refuses input missing a feature rather than zero-filling it. |
| `ingest.py` | Raw CSV → validated canonical parquet, with a dataset summary. |
| `run_baseline.py` | E0 rules and E1 tabular model, plus sanity baselines. |
| `run_graph.py` | E2: graph feature extraction and the graph model. |
| `run_ablation.py` | The seven-arm controlled ablation, three seeds per arm. |
| `run_validation.py` | Runs every gate and writes the model package, including its model card. `--artifact-free` drops the `payment_type` artifact; the shipped package was built with it. |
| `run_transfer.py` | The real-network transfer test, with the account-disjoint label partition ([ADR-012](docs/ADR-012-account-disjoint-proxy.md)). |

##### `registry/` — 1 module, 141 lines
`experiments.py` appends each run to `experiments/results.csv` with its full configuration.

##### Top level
`config.py` resolves platform-aware paths from `configs/paths.yaml`.

#### `tests/` — 261 tests

| Directory | Files | Purpose |
|---|---:|---|
| `leakage/` | 4 | **Merge-blocking.** All seven leakage checks plan v3 §11 requires, including future-edge invariance — no feature may change when later transactions are appended. |
| `unit/` | 16 | Per-module behaviour: schema, loader, splits, metrics, features, tracing, evidence, cascade, transfer partition — and `test_contracts.py`, which validates every sample output against `contracts/`, runs the real scorer on a slice, and fails if a model using the simulator artifact is ever committed. |
| `integration/` | 1 | Verifies the graph library's native backend actually works on this platform — the check that caught the Windows problem on day one. |

Seven slow tests (full reconstruction runs) are marked `slow` and deselected by default.

#### `configs/`

| File | Purpose |
|---|---|
| `experiment.yaml` | **Frozen experimental rules.** Changing any of them invalidates prior results, which then need a new experiment id rather than a quiet re-run. |
| `paths.yaml` | Where raw data, processed data and outputs live on each platform. |

#### `scripts/`

| File | Purpose |
|---|---|
| `setup_wsl.sh` | Builds the WSL virtualenv and verifies the graph backend loads. |
| `refresh_wheelhouse.ps1` | Downloads wheels on the Windows side, because WSL on the build machine has no outbound network. |
| `make_sample_outputs.py` | Regenerates `sample_outputs/` from the shipped model. |
| `measure/` | The nine scripts that produced the numbers the reports and ADRs quote — tracing latency, the cascade, typology, the bootstrap, the degree comparison, the scaling envelope. Indexed in [`measure/README.md`](Project/flowguard/scripts/measure/README.md). Set `FLOWGUARD_DATA` to point them at the data. |

#### `experiments/`
`results.csv` is tracked — one row per logged experiment. The per-experiment subdirectories
(`E0/`, `E1/`, `E2/`, `ABLATION/`) hold `record.json` files and are local only.

#### `models/`
**`flowguard_A4_v1/` is the shipped model, and the only one in git** (2 MB): the XGBoost
model, isotonic calibrator, categorical encoder, feature schema with hash, operating
thresholds, SHAP summary, metrics, `PROVENANCE.json` (git commit, platform, device, split
boundaries), a model card and a validation report. 167 features — 12 row-local, 155 graph —
with the `payment_type` artifact excluded. PR-AUC 0.1400 ± 0.0030 across three seeds; all
eight correctness gates pass.

`flowguard_E2_v1/` — the higher-scoring research model that uses the artifact — stays on the
build machine and out of git.

#### `reports/` — local only
`cases/` holds exported evidence bundles; one real case, `FG-18aedbed.json`, exists.
`data_quality/`, `error_analysis/`, `figures/` and `metrics/` are empty placeholders.

#### `notebooks/`
Empty. Every result in this project comes from a versioned runner, not a notebook.

#### `data` — local only
A junction to `C:\Users\vikam\flowguard_data`, kept outside OneDrive because processed data
and graph-feature parts run to several gigabytes.

| Subdirectory | Purpose |
|---|---|
| `processed/` (1.7 GB) | Canonical parquet for HI-Small, LI-Small and ETH; cached graph-feature parts for HI-Small and ETH. |
| `raw/` (1.5 GB) | The extracted Ethereum graph pickle. |
| `wheelhouse/` (333 MB) | Offline Python wheels. |
| `s5_parts/` (225 MB) | Graph-feature parts from the scaling-envelope run. |
| Loose files | 13 JSON result files and 18 run logs — the raw record of every measurement since Tier C. |

---

### `docs/` — the reasoning

Twenty-nine files explaining *why* the code is the way it is.
[`docs/README.md`](docs/README.md) indexes them and says which of the overlapping plans
governs what.

**Status — start here**

| File | Purpose |
|---|---|
| `STATUS.md` | Current results, gate outcomes, where the model fails, honest assessment. |
| `OPEN_ITEMS.md` | Unresolved findings and known weaknesses in the evidence. |
| `README.md` | Index of every document, and which plan governs what. |

**Plans — three generations, deliberately narrowing**

| File | Purpose |
|---|---|
| `FlowGuard_AI_Master_Project_Blueprint.md` | PS9 framing: regulatory context, pain points, the twelve functional requirements. |
| `FlowGuard_AI_PS9_Quick_Brief.md` | The pitch and demo narrative. |
| `FlowGuard_Unified_Plan_v2.md` | Splits the work into Track R (research) and Track P (product). §§29–33 hold the only product designs. |
| `FlowGuard_ML_Pipeline_Plan_v3.md` | **Governing plan for the research.** Deletes Track P and spends the time on measurement rigour — a higher version number with a *narrower* scope. |
| `Execution_Plan_TrackR.md` | Milestones M1–M6 with pre-registered gates. |
| `COMPLETION_PLAN.md` | Tiers A/B/C and the Tier S fixes, with an outcome banner. |
| `TRACK_P_PLAN.md` | Phases P1–P6, closing seven open requirements, with every gate result recorded. |
| `archive/implementation_plan.md` | A superseded Tier A command sequence. Historical. |
| `NEED_TO_RESEARCH.txt` | A brief for an unstaffed second research track. |
| `archive/start.txt` | The v1 plan. Superseded — do not build from it. |

**Analyses**

| File | Purpose |
|---|---|
| `ERROR_ANALYSIS_A2.md` | Where the artifact-free baseline fails: blind below $2,671. |
| `CORPUS_COMPARISON.md` | HI-Small vs LI-Small — why a second corpus from the same generator tests robustness, not transfer. |
| `Refined FlowGuard AML Project Analysis (1).pdf` | An external analysis document. |

**Decision records — fourteen**

| ADR | Decision | Kind |
|---|---|---|
| [001](docs/ADR-001-gfp-platform.md) | The graph library does not work on Windows; the project runs on WSL2 | constraint |
| [002](docs/ADR-002-boundary-policy.md) | The preferred split policy erases the corpus; use a hard cut | defect caught |
| [003](docs/ADR-003-sparse-tail-trim.md) | The corpus tail is 59% laundering; trim it and drop calendar features | defect caught |
| [004](docs/ADR-004-gfp-batch-leakage.md) | Batched graph extraction leaks future edges; extract one at a time | defect caught |
| [005](docs/ADR-005-gpu-training.md) | GPU training undertrained silently; raise early-stopping patience | defect caught |
| [006](docs/ADR-006-gfp-time-window.md) | Throughput collapses as the graph fills; bound the time window | constraint |
| [007](docs/ADR-007-payment-type-artifact.md) | 84% of the baseline was a simulator artifact | defect caught |
| [008](docs/ADR-008-reconstruction-rejected.md) | Periodic graph reconstruction failed its identity test | rejected |
| [009](docs/ADR-009-chunked-extraction.md) | Chunked feature persistence, after an OOM at 98.5% | fix |
| [010](docs/ADR-010-contaminated-pre-registration.md) | A gate pre-registered on contaminated numbers stays as written | constraint |
| [011](docs/ADR-011-adaptive-features-rejected.md) | Adaptive neighbourhood features made the model worse | rejected |
| [012](docs/ADR-012-account-disjoint-proxy.md) | A weak proxy label needs an account-disjoint partition | defect caught |
| [013](docs/ADR-013-degree-skew-dominates-cost.md) | Extraction cost tracks degree skew; throughput figures are generator-specific | finding |
| [014](docs/ADR-014-cascade-cannot-prefilter.md) | A cheap tier cannot pre-filter for the graph model | rejected |

---

### `Dataset_/` — raw corpora, 4.4 GB — kept local, not in the repository

| Item | Size | Purpose |
|---|---:|---|
| `IBM_Dataset/HI-Small_*` | 486 MB | **Primary corpus.** 5.08M transactions, plus patterns and accounts files. |
| `IBM_Dataset/HI-Medium_*` | 3.0 GB | Used only for the scaling-envelope measurement. |
| `IBM_Dataset/LI-Small_*` | 665 MB | A second corpus from the same generator, for robustness. |
| `IBM_Synthetic_AML-Data.pdf` | — | The generator's documentation. |
| `QmdMVccE2y…` (RAR) | 310 MB | The XBlock Ethereum phishing graph, as downloaded. |

The whole folder is git-ignored. The IBM corpora are on Kaggle as *IBM Transactions for
Anti-Money Laundering*; the Ethereum graph is from XBlock. **The Ethereum archive and the PDF
were committed once, in `d230c50`** — they must be removed from that commit before the first
push, because the archive exceeds GitHub's 100 MB file limit. See `PENDING.md` item A1.

### `papers/` — reference literature, 7.1 MB
Three PDFs that informed the approach: the **FraudGT** graph-transformer paper, a
**disk-based graph algorithms** survey, and a general research paper. Third-party and
copyrighted — tracked because the repository is private.

### `websites/` — saved reference pages, 56 MB
Five saved pages kept because the build machine had no outbound network: the **Snap ML Graph
Feature Preprocessor** documentation, its **literature review**, and IBM's pages on AI fraud
detection and on Snap ML on IBM Z. Only the HTML is tracked; the `*_files/` asset folders are
ignored. Third-party and copyrighted — tracked because the repository is private.

### `end report/`
`claude_validated_data_website.txt` — a pointer to the published report. It lists one of the
four reports; see `PENDING.md`.

---

## Published reports

Four hosted reports accompany the repository. They are private to the owner until shared from
each page's Share menu.

| Report | What it covers |
|---|---|
| [Validation Report](https://claude.ai/artifact/Y9qSGamEhR5nbeyacw6yzy) | The model result: ablation, transfer test, gates, charts |
| [Project Ledger](https://claude.ai/artifact/83KjAnxMtm2xEAk7nRdsVQ) | The whole repository assessed against PS9's twelve requirements |
| [Six Phases, Sixteen Gates](https://claude.ai/artifact/Mrrx53zCPmCuBndyiy4Ejo) | The P1–P6 build phases and every gate outcome |
| [Case Desk](https://claude.ai/artifact/UpGYYThbJiNrnsV5U9hkNC) | An investigator's view of the one exported case |

---

## Quick start

Linux only ([ADR-001](docs/ADR-001-gfp-platform.md)).

```bash
# Windows: stage the offline wheelhouse (WSL on the build machine has no network)
powershell -File Project/flowguard/scripts/refresh_wheelhouse.ps1

# WSL: build the environment and verify the graph backend loads
cd Project/flowguard && bash scripts/setup_wsl.sh

# run the pipeline
python -m flowguard.pipeline.ingest         --variant HI-Small
python -m flowguard.pipeline.run_baseline   --variant HI-Small   # E0, E1, sanity baselines
python -m flowguard.pipeline.run_ablation   --variant HI-Small   # seven-arm ablation
python -m flowguard.pipeline.run_graph      --variant HI-Small   # E2, graph features
python -m flowguard.pipeline.run_validation --model-id A4 --artifact-free   # the shipped package

# score transactions with the shipped model — what the product repo consumes
python -m flowguard.pipeline.score \
    --package models/flowguard_A4_v1 --transactions <file.csv|parquet> --out <dir> --cases 25

# tests (the leakage suite is merge-blocking)
python -m pytest -m "not slow"
```

---

## Where to start reading

1. **This file** for the map.
2. **[`docs/STATUS.md`](docs/STATUS.md)** for the results, and what they do and do not show.
3. **[ADR-007](docs/ADR-007-payment-type-artifact.md)** — the finding that reframed the project.
4. **[ADR-013](docs/ADR-013-degree-skew-dominates-cost.md)** — why the performance figures do not transfer.
5. **[`PENDING.md`](PENDING.md)** for what is left.

A negative result is a success condition here. Four of the fourteen decision records
document work that was built, measured and thrown away, because a rule fixed before the
result existed said so.
