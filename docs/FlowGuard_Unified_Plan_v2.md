# FlowGuard — Unified Research and Implementation Plan

**Version:** 2.0 (consolidated)
**Supersedes:** `start.txt` v1
**Sources merged:** `start.txt`, *Refined FlowGuard AML Project Analysis*, *FlowGuard AI Master Project Blueprint (PS9)*

---

## 0. How to Read This Document

This plan describes **one system with two delivery tracks** that share a single codebase, a single canonical schema, and a single evidence model.

| Track | Purpose | Primary audience | Success measure |
|---|---|---|---|
| **Track R — Research** | Reproduce a graph-feature AML baseline, then measure whether new temporal, value-flow and adaptive features improve on it | Technical report / paper | PR-AUC, minority-class F1, throughput, peak RAM |
| **Track P — Product (PS9)** | Turn the research pipeline into an investigator-facing fund-flow tracking and evidence-generation application | Demo judges, compliance users | Case clarity, explanation coverage, investigation time |

**Rule:** Track P must never be built on numbers Track R has not measured. Every claim shown in the product must trace back to a logged experiment.

### Conventions used throughout

* `is_laundering` is the **only** label field name. It is never called `label`, `target`, `y`, or `fraud`.
* Experiment IDs follow one scheme only: `E1` … `E7` (see §24). The older `EXP001_*` scheme from the previous draft is retired.
* Diagrams are illustrative pseudocode, not literal APIs.
* Anything marked **[unverified]** must be confirmed against a primary source before it appears in a report or a slide.

---

## 1. Project Identity

> ### FlowGuard
> **A Graph-Based, Temporal and Resource-Efficient Anti-Money-Laundering Detection System**

### One-line research framing (Track R)

> FlowGuard models financial transactions as a continuous-time dynamic graph, extracts graph and temporal behavioural features, and uses gradient-boosted models to detect laundering topologies under explicit latency and memory budgets.

### One-line product framing (Track P)

> FlowGuard reconstructs the journey of money as a temporal graph, scores the path rather than the isolated transaction, explains why the path is risky, and produces an investigator-ready evidence package.

### Research method

```text
REPRODUCE
    ↓
ANALYSE LIMITATIONS
    ↓
DESIGN AND EVALUATE IMPROVEMENTS
    ↓
REPORT BOTH GAINS AND COSTS
```

The fourth step is not optional. A feature that improves recall while tripling feature-extraction latency is a finding, not a failure — but it must be reported as a trade-off, not as an unqualified win.

---

## 2. Problem Statement

### 2.1 What legacy monitoring does

Traditional AML transaction monitoring relies on:

* fixed transaction-amount thresholds
* static, hand-configured rule alerts
* evaluation of each transaction in isolation
* manually enumerated suspicious patterns

### 2.2 Why that fails

Laundering is distributed across a *sequence* of transactions spread over several accounts. Each hop can be individually unremarkable.

```text
Account A
   │ ₹10,00,000
   ▼
Account B
   │ ₹9,80,000
   ▼
Account C
   │ ₹9,50,000
   ▼
Account D
```

Every edge above may pass a per-transaction rule. The *path* — three hops, 95% value retention, short inter-hop intervals — is the signal. Structurally this is a layering / pass-through topology; individually it is invisible.

### 2.3 Research question

> **How can graph-based, temporal and value-flow information improve AML detection, while keeping processing time, memory usage and false-positive rates within acceptable operating limits?**

Note that the question has two halves. A plan that only answers the first half is incomplete.

---

## 3. Objectives

### 3.1 Primary objective

Develop a reproducible, leakage-safe, graph-based AML detection pipeline on a frozen dataset, and evaluate whether additional temporal, value-flow, behavioural-novelty and adaptive-expansion features improve on a Graph-Feature-Preprocessor-style baseline.

### 3.2 Secondary objectives

1. Build a clean, reproducible AML data pipeline with an immutable raw layer.
2. Normalise heterogeneous transaction data into one canonical schema.
3. Construct a directed, continuous-time dynamic transaction graph.
4. Reproduce or faithfully re-implement the graph-feature extraction approach.
5. Train and log a rule-based control (M0).
6. Train and log a transaction-only gradient-boosted baseline (M1).
7. Train and log a graph-feature baseline (M2).
8. Perform structured false-positive and false-negative analysis.
9. Design new feature families from the observed failures — not from intuition.
10. Measure detection quality **and** computational cost for every variant.
11. Run controlled ablations with one change at a time.
12. Produce SHAP-based, evidence-linked explanations.
13. Assemble an investigator case view and evidence package.
14. Demonstrate the whole system through an API and dashboard.
15. Document limitations, failure modes and threats to validity.

---

## 4. Regulatory and Operational Context

This section grounds the project in the environment it claims to serve. It is required for the product track and useful framing for the research track.

### 4.1 Indian regulatory setting

RBI KYC/AML Master Direction obligations require regulated entities to perform ongoing due diligence and monitor for activity inconsistent with a customer's declared profile, business, risk profile and source of funds. Supervisory guidance draws particular attention to large, complex or unusual transactions, turnover inconsistent with balances, and money-mule behaviour. Under the PMLA framework, the compliance function files Suspicious Transaction Reports with FIU-IND.

**Implication for FlowGuard:** explainability is a functional requirement, not a nice-to-have. A risk score that cannot be defended in an audit cannot support an STR narrative.

### 4.2 Reporting volume context **[unverified — confirm against the current FIU-IND annual report before citing]**

| Metric | FY2023–24 | FY2024–25 |
|---|---:|---:|
| Suspicious Transaction Reports (STRs) | 3,68,592 | 4,34,668 |
| Cross-Border Wire Transfer Reports | 90,87,189 | 1,02,73,512 |
| Priority STRs disseminated to LEAs | 2,750 | 6,908 |

Source to verify: FIU-IND Publications — <https://fiuindia.gov.in/files/Publication/Publication.html>

### 4.3 Why network-level analysis matters

BIS Project Aurora reports that AML monitoring performed in siloed, rules-based ways struggles with interconnected fund flows, and that its simulated collaborative approach combining machine learning, network analysis and privacy-enhancing technology detected substantially more complex laundering networks with materially fewer false positives than the siloed approach it tested. **[Verify the exact figures in the BIS report before quoting them; do not paraphrase them as FlowGuard's own expected results.]**

Source to verify: <https://www.bis.org/publ/othp66.pdf>

### 4.4 The operational goal

The objective is not more alerts.

> **Fewer alerts, better prioritised, each carrying a reconstructed fund-flow story.**

---

## 5. Source-Material Reconciliation and Claim Discipline

The three source documents behind this plan do not describe the same thing, and conflating them is the single largest correctness risk in the project.

| Source | What it actually provides | What it does **not** provide |
|---|---|---|
| IBM synthetic AML material / AMLSim | Synthetic transaction ledgers with injected laundering typologies (fan-in, fan-out, cycles, scatter-gather, gather-scatter) and ground-truth labels | Customer KYC profiles, dormancy history, branch/channel/product context |
| Graph Feature Preprocessor (GFP) literature | A described method for incremental subgraph-pattern and vertex-statistical features feeding gradient-boosted models | A guarantee that its reported datasets are identical to whatever you download |
| PS9 Master Blueprint | Product framing, typology catalogue, investigator workflow, evidence model, IBM positioning | Measured results of any kind |

### 5.1 Three rules that must not be broken

1. **Do not assume AMLSim output and the exact datasets in the GFP literature are identical.** Verify schema, label semantics and scale yourself.
2. **Do not describe the first implementation as an exact reproduction.** Until you have confirmed the implementation, version and configuration, describe it as:
   > *a GFP-based / GFP-inspired graph-feature AML baseline*
3. **Do not claim that graph analytics plus machine learning for AML is novel.** Commercial AML platforms already combine rules, ML, entity resolution, network analytics and case management. That claim is not defensible and will be challenged.

### 5.2 What may be claimed

> **FlowGuard's contribution is a temporal, path-centric, resource-budgeted workflow in which the fund path is the primary analytical object, every risk score is linked to the specific evidence that produced it, and every accuracy gain is reported alongside its throughput and memory cost.**

### 5.3 Pre-implementation verification checklist

Before writing pipeline code, confirm and record:

* [ ] Dataset identity, version, and exact download or generation configuration
* [ ] Available columns and their types
* [ ] Label semantics — is `is_laundering` per transaction, per pattern, or per account?
* [ ] Timestamp format, timezone, and monotonicity
* [ ] Whether accounts are globally unique or bank-scoped
* [ ] Whether a public GFP implementation is available and which version (a Graph Feature Preprocessor is documented as part of Snap ML — confirm availability, licence, and API for your platform)
* [ ] Licence terms for redistribution inside your repository
* [ ] Whether the data can be processed within your hardware budget

### 5.4 Capability gap: what the research dataset cannot support

This is a correction to the previous draft, which listed research directions the chosen dataset cannot express.

| Feature family / typology | Needs | Available in IBM-style AML transaction data? |
|---|---|---|
| Fan-in, fan-out, cycles, scatter-gather | transactions only | Yes |
| Temporal flow motifs | timestamps | Yes |
| Value-flow / retention ratios | amounts | Yes |
| Behavioural novelty | account history | Yes |
| Dormant-account activation | account open date + inactivity history | **No — requires augmentation** |
| Profile mismatch | KYC / declared-profile attributes | **No — requires augmentation** |
| Channel / branch / product typologies | operational banking context | **No — requires augmentation** |
| Heterogeneous entity graph | entity-type metadata | **No — requires augmentation** |

**Resolution.** Track R runs on the public dataset and reports only the typologies that dataset supports. Track P adds an explicitly-labelled **synthetic bank-context layer** (§29.3) supplying customer profiles, account-open dates, dormancy, branch, channel and product. Results from the synthetic layer are reported separately and are never mixed into the research comparison table. Any slide showing profile-mismatch or dormant-activation detection must state that it runs on synthetic augmented data.

---

## 6. Datasets

### 6.1 Candidate corpora

| Dataset variant | Nodes (accounts) | Edges (transactions) | Illicit rate | Temporal span |
|---|---:|---:|---:|---:|
| AML HI Small | 0.5 M | 5 M | 0.102% | 10 days |
| AML HI Medium | 2.1 M | 32 M | 0.110% | 16 days |
| AML HI Large | 2.1 M | 180 M | 0.124% | 97 days |
| AML LI Small | 0.7 M | 7 M | 0.051% | 10 days |
| ETH Phishing (real) | 2.9 M | 13 M | 0.278% | 1261 days |

**[These figures come from the source analysis and must be re-derived from the files you actually download. Record your own counts in `dataset_summary.json` and use those in the report.]**

### 6.2 Selection decision

* **Primary experimental dataset:** AML HI Small — small enough for fast iteration, high enough illicit rate to make minority-class metrics stable.
* **Scale-test dataset:** AML HI Medium — used only for throughput and memory scaling, not for model selection.
* **Cross-dataset validation:** ETH Phishing — a *real* network with a different domain, schema and temporal span. This is the honest generalisation test, because passing it cannot be explained by having memorised one synthetic generator's quirks.
* **Optional contrast:** AML LI Small — tests behaviour at roughly half the illicit rate.

Freeze the primary dataset before any model is trained. Changing it later invalidates every prior experiment.

### 6.3 Dataset selection checklist

* Does every transaction carry a usable timestamp?
* Are source and destination accounts present and resolvable?
* Is there a per-transaction ground-truth label?
* Are laundering pattern annotations available (pattern type / scenario ID)?
* Are amounts present, non-negative, and in a stated currency?
* Is the dataset large enough for the temporal split to leave a meaningful test period?
* Can it be processed within your RAM and time budget?
* Can it be redistributed, or must it be fetched by script at setup time?

---

## 7. Phase 0 — Freeze the Research Rules

Freeze these before the first model runs. Record them in `configs/experiment.yaml` and in the registry entry of every experiment.

| Item | What to freeze |
|---|---|
| Primary dataset | AML HI Small, specific file set |
| Dataset version | SHA-256 checksums of every raw file |
| Prediction target | Per-transaction `is_laundering` classification |
| Data split | Chronological 70 / 15 / 15 by transaction time |
| Random seed | `42` (and record it per run) |
| Hardware | CPU model, core count, RAM, GPU if used |
| Python version | Exact interpreter version |
| Library versions | XGBoost, Snap ML, NetworkX, pandas/Polars, SHAP, scikit-learn |
| Evaluation metrics | PR-AUC (headline), minority F1, precision, recall, latency, throughput, peak RAM |
| Feature naming | `snake_case`, family-prefixed (`gfp_`, `tflow_`, `vflow_`, `nov_`) |
| Experiment naming | `E1` … `E7` only |
| Threshold policy | Selected on validation only, never on test |
| Output formats | Parquet for tables, JSON for metadata and metrics |

### The governing rule

> **Every model must use the same dataset, prediction target, temporal split, threshold-selection procedure and evaluation code.**

If any of those change, the experiment gets a new ID and the old results are not comparable. Say so explicitly in the report rather than quietly re-running.

---

## 8. Canonical Schema and Data Contract

This is the single source of truth for field names. It resolves the `label` / `is_laundering` inconsistency in the previous draft — the earlier document used both names in different sections, which would have produced a silent `KeyError` or, worse, a silently mismatched join.

### 8.1 Canonical transaction record

| Field | Type | Required | Purpose |
|---|---|---|---|
| `transaction_id` | string | yes | Unique identifier; prevents duplicate processing |
| `timestamp` | datetime (UTC) | yes | Chronological marker for splits and sliding windows |
| `source_account` | string | yes | Originating node identifier |
| `destination_account` | string | yes | Receiving node identifier |
| `amount` | float | yes | Value transferred; basis of all value-flow features |
| `currency` | string | yes | Exchange medium; cross-border risk signal |
| `payment_type` | string | no | Transfer mechanism (ACH, wire, cash, cheque, …) |
| `is_laundering` | int (0/1) | yes | Ground-truth label: 0 = benign, 1 = suspicious |
| `scenario_id` | string | no | Injected-scenario identifier, where the dataset provides one |
| `pattern_type` | string | no | Typology annotation (fan_in, cycle, scatter_gather, …) |

### 8.2 Canonical representation

```python
{
    "transaction_id": "TX00000001",
    "timestamp": "2026-01-01T10:00:00Z",
    "source_account": "ACC_000123",
    "destination_account": "ACC_009876",
    "amount": 1000.0,
    "currency": "USD",
    "payment_type": "WIRE",
    "is_laundering": 0,
    "scenario_id": None,
    "pattern_type": None,
}
```

### 8.3 Graph edge attributes

Every directed edge carries exactly the canonical fields:

```text
transaction_id
timestamp
amount
currency
payment_type
is_laundering     # stored for evaluation only — NEVER read by a feature extractor
```

> **Critical:** `is_laundering` is present on the edge for evaluation and error analysis. Any code path where a feature function can read it is a leakage bug. Enforce this with a test (§32).

### 8.4 Optional bank-context extension (Track P only)

Used only with the synthetic augmentation layer, and always flagged as such:

```text
customer_id, account_open_date, last_activity_date, account_status,
declared_segment, declared_turnover_band, branch_id, channel, product
```

---

## 9. Repository Structure

One repository, both tracks. Research modules stay importable by the product layer, never the reverse.

```text
flowguard/
│
├── README.md
├── pyproject.toml
├── requirements.txt
├── requirements.lock
├── .gitignore
│
├── configs/
│   ├── dataset.yaml
│   ├── features.yaml
│   ├── model.yaml
│   ├── experiment.yaml
│   └── thresholds.yaml
│
├── data/
│   ├── raw/                  # immutable, never written after ingestion
│   ├── interim/
│   ├── processed/
│   ├── splits/
│   └── synthetic_context/    # Track P augmentation layer only
│
├── docs/
│   ├── problem-statement.md
│   ├── architecture.md
│   ├── research-log.md
│   ├── model-card.md
│   ├── limitations.md
│   └── demo-script.md
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_quality.ipynb
│   ├── 03_graph_analysis.ipynb
│   └── 04_baseline_analysis.ipynb
│
├── src/
│   └── flowguard/
│       ├── data/
│       │   ├── loader.py
│       │   ├── schema.py
│       │   ├── validator.py
│       │   └── cleaner.py
│       │
│       ├── graph/
│       │   ├── builder.py
│       │   ├── temporal_graph.py     # CTDG, sliding window, tombstone GC
│       │   ├── traversal.py
│       │   ├── graph_statistics.py
│       │   └── motif_extractor.py
│       │
│       ├── features/
│       │   ├── transaction_features.py
│       │   ├── gfp_features.py
│       │   ├── temporal_features.py
│       │   ├── value_flow_features.py
│       │   ├── novelty_features.py
│       │   └── adaptive_features.py
│       │
│       ├── models/
│       │   ├── rules.py
│       │   ├── xgboost_model.py
│       │   └── anomaly_models.py
│       │
│       ├── risk/
│       │   ├── typologies.py
│       │   ├── correlation.py
│       │   └── thresholds.py
│       │
│       ├── evaluation/
│       │   ├── metrics.py
│       │   ├── splits.py
│       │   ├── error_analysis.py
│       │   ├── profiling.py
│       │   └── registry.py
│       │
│       ├── explainability/
│       │   ├── shap_explainer.py
│       │   ├── graph_explainer.py
│       │   └── narrative.py
│       │
│       ├── evidence/
│       │   ├── case_builder.py
│       │   └── export.py
│       │
│       ├── pipeline/
│       │   └── run_baseline.py
│       │
│       └── api/
│           └── app.py
│
├── frontend/
│   └── dashboard/
│
├── experiments/
│   ├── E1/ … E7/
│   └── results.csv
│
├── models/
│
├── reports/
│   ├── data_quality/
│   ├── metrics/
│   ├── graphs/
│   └── error_analysis/
│
└── tests/
    ├── unit/
    ├── integration/
    └── scenario/
```

---

## 10. Phase 1 — Data Ingestion and the Immutable Raw Layer

### Workflow

```text
Dataset download or generation
          ↓
SHA-256 checksum calculation
          ↓
Raw file preservation (read-only)
          ↓
Dataset metadata record
          ↓
Loading into the canonical schema
```

### Metadata record

Written once per dataset, stored beside the raw files:

```json
{
  "dataset_name": "IBM AML HI Small",
  "dataset_version": "v1",
  "download_date": "YYYY-MM-DD",
  "files": [
    { "file_name": "transactions.csv", "sha256": "…", "row_count": 0 }
  ],
  "source_url": "…",
  "generation_config": "config_reference_or_null",
  "licence": "…",
  "ingested_by": "git_commit_hash"
}
```

### Rules

* The raw directory is never written to after ingestion. Mount it read-only in development if your OS allows it.
* Every cleaning or transformation step writes a **new** artifact into `interim/` or `processed/`.
* Row counts recorded at ingestion are compared against row counts after loading. A mismatch is a hard failure, not a warning.

---

## 11. Phase 2 — Exploratory Data Analysis and Quality Profiling

Run this before building any graph. Several downstream design decisions — window length, expansion depth, alert budget — depend on the distributions found here.

### Transaction-level

* Total transactions and total distinct accounts
* Amount minimum, maximum, mean, and the 1/5/25/50/75/95/99th percentiles
* Payment-type and currency cardinality
* Full time range and gaps in coverage
* Missing-value counts per field
* Duplicate `transaction_id` count
* Suspicious-to-benign ratio, overall and per time bucket

### Account-level

* In-degree and out-degree distributions (report as distributions, not just means — these are heavy-tailed)
* Total inflow and outflow per account
* Distinct counterparty counts
* Activity frequency and inactivity gaps
* High-degree hub accounts
* Accounts participating in labelled laundering patterns

### Temporal

* Transactions per minute / hour / day
* Burst detection and burst duration
* Inter-transaction time gaps per account
* Observed time for funds to traverse multi-hop paths in labelled scenarios

### Graph-level

* Node and edge counts
* Average degree; in- and out-degree distributions
* Connected and strongly connected components
* Cycle statistics on a sampled subgraph
* Graph density
* Approximate path-length distribution

> **Caution:** compute these profiling statistics on the **training window only** when they will inform feature design or thresholds. Global statistics computed over the full timeline are a subtle form of leakage into your design choices.

### Deliverables

```text
reports/data_quality/data_quality_report.html
reports/data_quality/dataset_summary.json
reports/graphs/graph_statistics.json
reports/data_quality/transaction_distribution.png
reports/data_quality/account_activity.png
reports/data_quality/temporal_activity.png
```

---

## 12. Phase 3 — Validation and Quality Policy

### Required-field validation

Fail fast if any of these are absent:

```text
transaction_id
timestamp
source_account
destination_account
amount
is_laundering
```

### Quality checks

| Check | Action on violation |
|---|---|
| Missing source or destination account | Reject, log reason |
| Missing or non-numeric amount | Reject, log reason |
| Negative amount | Reject, log reason |
| Zero amount | Flag and count; keep only if the dataset legitimately contains them |
| Invalid or unparseable timestamp | Reject, log reason |
| Timestamp outside the declared dataset span | Reject, log reason |
| Duplicate `transaction_id` | Keep first, log the collision |
| Self-transaction (`source == destination`) | Flag, exclude from graph edges, keep in the ledger |
| Unresolvable account reference | Reject, log reason |
| Unsupported currency code | Flag, normalise if a mapping exists |
| `is_laundering` not in {0, 1} | Reject, log reason |
| Records out of chronological order | Sort; log that sorting occurred |

### Quality policy

**Never silently drop a record.** Every rejection is counted and explained. The quality report states:

* records read
* records retained
* records rejected, broken down by rejection reason
* records corrected, broken down by correction type
* the resulting change in illicit rate

A change in illicit rate after cleaning is a red flag worth investigating: it can mean the cleaning rule is correlated with the label.

---

## 13. Phase 4 — Prediction Unit

The first complete implementation predicts at the **transaction** level.

```text
is_laundering = 0 → not suspicious
is_laundering = 1 → suspicious
```

### Model output record

```text
transaction_id
risk_score          # continuous, 0.0–1.0
predicted_label     # thresholded
is_laundering       # ground truth, for evaluation only
threshold_used
prediction_timestamp
model_version
experiment_id
```

### Later escalation (do not build these simultaneously)

```text
Transaction risk
      ↓
Account risk
      ↓
Path risk
      ↓
Investigation case
```

Each level needs its own labels, its own evaluation and its own error analysis. Adding a level without those is how a project ends up with four unvalidated scores averaged into one meaningless number.

---

## 14. Phase 5 — Leakage-Safe Temporal Splitting

This is the part of the project most likely to silently invalidate every result.

### The invariant

> When scoring a transaction at time `T`, the model may use only information and graph structure that existed at or before `T`.

```text
Prediction time = T
       ↓
Use only information known ≤ T
```

Random shuffling grants the model access to future network structure. It inflates offline accuracy and produces a model that is useless in a live stream — and the failure is invisible unless you look for it.

### Primary split

```text
Earliest 70%  →  Training
Next    15%   →  Validation
Latest  15%   →  Test
```

Split on transaction time, not row order. Percentages may be adjusted after inspecting the temporal distribution, but must be fixed before any model comparison.

### Hard rules

* Do not shuffle across time.
* Do not compute historical features from future transactions.
* Do not compute global graph statistics over the full dataset.
* Do not use labels — anyone's, at any time — to construct features.
* Fit scalers and encoders on training data only.
* Apply class balancing to the training partition only.
* Select thresholds on validation only.
* Touch the test set once, at the end. If you look at test results and then change the model, say so in the report.

### Additional evaluation splits

**A. Standard temporal split** — measures future-like performance. This is the headline.

**B. Unseen-pattern split** — train on a subset of laundering typologies, test on held-out or composite typologies. Measures generalisation to novel structure rather than memorisation of the generator's templates.

**C. Hard-negative split** — inject or select structurally complex but legitimate behaviour:

* payroll distribution (legitimate high fan-out)
* corporate treasury sweeps
* merchant settlement batches
* supply-chain payment chains
* regular high-volume business flows

Measures whether the model distinguishes suspicious topology from legitimate complexity. This is the split that predicts real-world false-positive pain.

### Leakage control checklist

Run before every experiment is logged:

* [ ] Split boundaries are timestamps, printed in the run log
* [ ] Maximum training timestamp < minimum validation timestamp
* [ ] Maximum validation timestamp < minimum test timestamp
* [ ] Feature extraction for a transaction at `T` reads no edge with timestamp > `T`
* [ ] No feature function has access to `is_laundering`
* [ ] Encoders and scalers fitted on training rows only
* [ ] Threshold chosen on validation only
* [ ] An intentionally-leaky control run exists, showing the inflated score, so the gap is documented

That last item is worth the effort: an explicit leaky baseline showing, say, a much higher PR-AUC is the clearest possible evidence that your non-leaky pipeline is doing the right thing.

---

## 15. Phase 6 — Baseline Models

Build in increasing complexity so that the value added by each layer is measurable.

### Model M0 — Rule-Based Control

Simulates legacy monitoring. Rules such as:

* transaction velocity above a threshold
* amount far above the account's own historical distribution
* counterparty count above a threshold
* rapid inflow followed by outflow within a short window (pass-through)
* fan-in or fan-out above a threshold
* multi-hop movement completed within a short window

```text
if velocity_1h(source) > V_THRESHOLD:
    flag

if amount > mean(source_history) + K * std(source_history):
    flag

if outflow_within(source, 1h) / inflow_within(source, 1h) > R_THRESHOLD:
    flag
```

Thresholds are tuned on **validation**, exactly like a model. A deliberately badly-tuned rule baseline is not a fair control.

Record: alert count, precision, recall, F1, false-positive rate, processing time.

M0 is the control group. It is expected to be interpretable and to generate an unsustainable alert volume — that tension is the whole argument for the rest of the project.

### Model M1 — Transaction-Only Gradient Boosting

Tabular XGBoost with no graph information.

| Feature | Description |
|---|---|
| `amount` | Transaction amount |
| `amount_log` | Log1p-transformed amount |
| `hour` | Hour of day |
| `day_of_week` | Day of week |
| `payment_type_encoded` | Encoded transfer mechanism |
| `currency_encoded` | Encoded currency |
| `source_tx_count` | Source's prior transaction count |
| `destination_tx_count` | Destination's prior transaction count |
| `source_inflow` | Source's cumulative prior inflow |
| `source_outflow` | Source's cumulative prior outflow |
| `destination_inflow` | Destination's cumulative prior inflow |
| `counterparty_count` | Distinct prior counterparties |
| `amount_deviation` | Deviation from the account's own prior amount distribution |
| `velocity_1h` | Transactions by this account in the prior hour |
| `velocity_24h` | Transactions by this account in the prior 24 hours |

Every one of these is computed from **prior** transactions only.

```text
Transaction features
       ↓
XGBoost
       ↓
Risk score
```

M1 answers: *how far can tabular learning go with no network topology at all?*

### Model M2 — Graph-Feature Baseline

The primary research baseline.

```text
Transactions
      ↓
Directed continuous-time dynamic graph
      ↓
GFP or verified GFP-inspired extractor
      ↓
Graph feature table
      ↓
Concatenate with M1 features
      ↓
XGBoost
      ↓
Transaction risk score
```

Feature families: fan-in, fan-out, scatter-gather, cycles, temporal graph patterns, vertex-level statistics, degree and neighbourhood aggregates.

Implement against the verified paper, source and version. Record the exact configuration — window length, pattern set, maximum pattern size — in the experiment registry. If you re-implement rather than integrate, state that plainly and validate your implementation against small graphs with hand-computed expected outputs.

### Why gradient boosting rather than a GNN

The source analysis reports that on AML-HI Small, a standard GIN architecture reaches roughly 28.7% F1 while a GFP + XGBoost pipeline reaches roughly 64.8%, and that graph transformers score higher still (around 76.4%) at a computational cost that undermines real-time streaming. **[Verify these numbers against the primary papers before citing them; do not present them as your own measurements.]**

The architectural reasoning stands independently of the exact figures:

* Highly imbalanced minority-class problems favour boosted trees on dense engineered features.
* Continuous-time dynamic GNNs need memory modules that add latency on the critical path.
* Tree ensembles integrate cleanly with SHAP, which the regulatory requirement demands.

Treat these as hypotheses your own experiments will confirm or refute on your data. If a GNN wins on your setup, report that.

---

## 16. Phase 7 — Streaming Graph Construction

### Graph model

```text
Account     = Node
Transaction = Directed edge
```

```text
A ──₹10,00,000──▶ B
B ──₹9,80,000───▶ C
C ──₹9,50,000───▶ D
```

### Temporal evolution

The graph must evolve with transaction time. Never build the full graph and then extract features for an earlier transaction.

```text
Transaction arrives at time T
       ↓
Evict / tombstone edges older than T − δ
       ↓
Extract features from the active window
       ↓
Score the transaction
       ↓
Insert the new edge
       ↓
Next transaction
```

Note the ordering: features are extracted **before** the new edge is inserted, or the transaction contributes to its own features. Whichever convention you choose, document it and apply it identically across every model.

### Sliding temporal window

For an edge `e_uv` at time `t_uv` with look-back `δ`, the active edge set is:

```text
TW = [ t_uv − δ , t_uv ]
```

This keeps long-dormant historical ties from inflating an account's current risk profile, which matters for detecting short, rapid smurfing campaigns.

`δ` is a frozen hyperparameter. Multi-resolution windows are a separate research direction (§24.E), not a silent default.

### Memory management: tombstoned eviction

Naively deleting expired edges on every insertion triggers cascading reallocation and stalls the feature-extraction thread.

Instead:

1. On insertion, mark expired edges as logically deleted (tombstoned) rather than physically removing them.
2. A background sweeper periodically compacts adjacency lists and reclaims tombstoned entries.
3. Feature extraction skips tombstoned edges on read.

This keeps the critical path unblocked and inference latency stable. Measure and report: tombstone ratio over time, sweep frequency, sweep pause duration, and peak versus steady-state RAM. A memory optimisation whose pauses are unmeasured is not an optimisation, it is a hope.

### Representation choices

Prototype scale:

* Python dictionaries and adjacency lists
* NetworkX for small-scale validation and visualisation only
* pandas or Polars for tabular work
* Parquet / PyArrow for intermediate storage

Larger scale:

* CSR-style compressed adjacency
* Incremental adjacency maps with tombstones
* Disk-backed or memory-mapped storage
* Streaming, chunked processing

Start simple. Optimise only after the baseline is correct and profiled.

---

## 17. Phase 8 — Graph Feature Families

Implement the established families before inventing anything.

### A. Fan-in

Multiple accounts funnelling into one.

```text
gfp_in_account_count
gfp_in_tx_count
gfp_in_amount_sum
gfp_in_amount_mean
gfp_in_amount_var
```

### B. Fan-out

One account distributing to many.

```text
gfp_out_account_count
gfp_out_tx_count
gfp_out_amount_sum
gfp_out_amount_mean
gfp_out_amount_var
```

### C. Cycles

Funds returning toward the originator: `A → B → C → A`

```text
gfp_cycle_detected
gfp_cycle_length
gfp_cycle_count
gfp_tx_in_cycle
gfp_shortest_cycle_length
```

### D. Scatter-gather

Funds disperse through intermediaries and re-aggregate.

```text
Source
 ├──▶ B ──┐
 ├──▶ C ──┼──▶ Target
 └──▶ D ──┘
```

```text
gfp_scatter_gather_detected
gfp_scatter_width
gfp_gather_width
gfp_sg_path_count
```

### E. Vertex statistics

Incrementally maintained per-account profiles of inflow and outflow: sum, mean, min, max, median, variance, skewness, kurtosis. Maintaining these incrementally avoids recomputing full history on every transaction — which is the difference between a streaming system and a batch one.

```text
gfp_src_inflow_mean,  gfp_src_inflow_var,  gfp_src_inflow_skew
gfp_src_outflow_mean, gfp_src_outflow_var, gfp_src_outflow_skew
gfp_dst_inflow_mean,  gfp_dst_inflow_var,  gfp_dst_inflow_skew
gfp_dst_outflow_mean, gfp_dst_outflow_var, gfp_dst_outflow_skew
```

### F. Degree and neighbourhood

```text
gfp_src_in_degree,  gfp_src_out_degree
gfp_dst_in_degree,  gfp_dst_out_degree
gfp_src_neighbour_count
gfp_dst_neighbour_count
gfp_shared_neighbour_count
```

### Output contract

Exactly one feature row per transaction, joined on `transaction_id`:

```text
transaction_id
<transaction features>
<fan-in features>
<fan-out features>
<cycle features>
<scatter-gather features>
<vertex statistics>
<degree / neighbourhood features>
```

Feature column order and dtypes are frozen and asserted at both training and inference. A silent column reorder between the two is one of the most common and most expensive bugs in this class of system.

---

## 18. Phase 9 — Train the First Complete System

### Full M2 pipeline

```text
Raw AML data
      ↓
Validation and quality report
      ↓
Canonical schema
      ↓
Temporal split
      ↓
Streaming graph construction
      ↓
Graph feature extraction
      ↓
Feature table (joined with transaction features)
      ↓
XGBoost training
      ↓
Validation and threshold selection
      ↓
Test evaluation (once)
      ↓
Risk scores, SHAP explanations, registry entry
```

### M2 completion criteria

M2 is complete only when all of the following exist and are reproducible from a clean checkout:

* Deterministic data loading with checksum verification
* Documented, tested graph construction
* Verified feature extraction with unit tests on hand-computed graphs
* A trained XGBoost model with saved weights and saved hyperparameters
* Saved test predictions with scores and thresholds
* Full evaluation metrics, including timing and memory
* Feature-importance output
* Error-analysis report
* A registry entry containing the git commit hash

---

## 19. Phase 10 — Evaluation Framework

Because roughly 0.1% of transactions are illicit, **accuracy is meaningless** here — a model predicting "benign" for everything scores 99.9%. Never report accuracy as a headline.

### Machine-learning metrics

* **PR-AUC** — the headline metric for imbalanced detection
* Minority-class F1
* Precision and recall at the operating threshold
* ROC-AUC — report for comparability with literature, but never as the headline; it is optimistic under extreme imbalance
* Confusion matrix at the operating threshold

### AML-operational metrics

* Recall at a fixed alert budget (e.g. top 0.1% / 0.5% / 1% of scored transactions)
* Precision@K and Recall@K
* Total alerts generated
* False positives per 1,000 transactions
* Per-typology detection rate (fan-in, fan-out, cycle, scatter-gather)
* Path-level detection rate: proportion of labelled multi-hop scenarios where at least one hop is flagged
* Path reconstruction completeness: proportion of the true suspicious hops recovered

The alert-budget metrics matter more than raw F1 for anyone who has to staff an investigations team. A model that finds 90% of laundering by alerting on 5% of all transactions is operationally useless.

### System-performance metrics

Measured separately per component — a single end-to-end number hides where the cost actually is.

| Component | Measurement |
|---|---|
| Data loading | seconds |
| Validation | seconds |
| Graph construction | seconds, and edges/second |
| Feature extraction | milliseconds per transaction, and transactions/second |
| Model inference | milliseconds per transaction, and transactions/second |
| End-to-end pipeline | total wall-clock seconds |
| Throughput | sustained transactions/second |
| CPU | mean and peak utilisation |
| Memory | peak RSS and steady-state RSS |
| Storage | intermediate artifact size on disk |

Report latency as a distribution — p50, p95, p99 — not a mean. In a streaming system the tail is the thing that breaks.

### Explanation metrics

* Explanation coverage: proportion of high-risk outputs carrying evidence-linked reason codes
* Evidence traceability: proportion of reasons that resolve to specific transaction IDs

---

## 20. Phase 11 — Error Analysis

Baseline numbers are the input to this phase, not the output of the project. **This is the stage that determines what you build next.** New features should come from observed failures, not from a brainstorm.

### False-positive categories

* Legitimate payroll fan-out
* Merchant settlement batching
* Corporate treasury movement
* Supply-chain payment chains
* High-volume but legitimate hub accounts
* Shared service and nostro-style accounts
* Structurally complex but benign business cycles

### False-negative categories

* Slow layering spread beyond the window `δ`
* Long-distance, many-hop movement
* Low-value dispersed transfers below velocity thresholds
* Typologies absent from training
* Activity split across the split boundary
* Patterns where each hop is individually within normal account behaviour

### Error-analysis record

| Transaction ID | Actual | Predicted | Typology | Error cause | Candidate remedy |
|---|---:|---:|---|---|---|
| TX001 | 0 | 1 | Payroll fan-out | Legitimate high-degree hub | Behavioural-novelty features (§24.C) |
| TX002 | 1 | 0 | Slow layering | Window `δ` too short | Multi-resolution windows (§24.E) |
| TX003 | 0 | 1 | Merchant settlement | High fan-in, regular cadence | Periodicity feature |
| TX004 | 1 | 0 | Pass-through mule | Structure present, timing missed | Temporal flow motifs (§24.A) |

Categorise every misclassification in the test set, count the categories, and rank them by volume. Attack the largest bucket first.

---

## 21. Phase 12 — Explainability

SHAP on XGBoost, plus graph-path evidence. Regulatory defensibility is a functional requirement, not decoration: a Principal Officer filing an STR must be able to state *why* an alert fired.

### Per-alert output

```text
Transaction ID : TX1001
Risk score     : 0.94
Threshold      : 0.72
Category       : HIGH
Model version  : flowguard_v1 (E7)
```

### Top contributing features

```text
1. gfp_cycle_detected                 +0.21
2. tflow_mean_inter_hop_seconds       +0.17
3. gfp_out_account_count              +0.14
4. vflow_retention_ratio              +0.11
5. nov_new_counterparty_rate          +0.08
```

### Graph evidence

* Source and destination accounts
* Relevant neighbouring accounts within the extracted subgraph
* The detected typology
* The specific transaction path, with IDs
* Time intervals between hops
* Amount at each hop and the retention ratio
* The contributing features, each linked to the evidence that produced it

### From score to narrative

Not:

> "This transaction is suspicious."

But:

> "Flagged because the account participated in a three-hop flow completed within 21 minutes, retaining 94% of received value, with a fan-out count 6× its own 30-day baseline and participation in a detected cycle."

**Constraint:** if a large language model generates the narrative, it summarises the structured evidence object and nothing else. It must not introduce facts, infer intent, or assert criminality. Every sentence must be reconstructible from the evidence JSON. An ungrounded narrative generator is a liability, not a feature.

---

## 22. Phase 13 — Computational Baseline

Record the cost of every stage, on the frozen hardware, before optimising anything.

```text
Data loading            = ____ s
Validation              = ____ s
Graph construction      = ____ s
Feature extraction      = ____ s      ( ____ tx/s )
Model inference         = ____ s      ( ____ tx/s )
Total                   = ____ s
Peak RAM                = ____ MB
Steady-state RAM        = ____ MB
Latency p50 / p95 / p99 = ____ / ____ / ____ ms
```

Your contribution may improve detection quality, runtime, memory, explainability, or some combination. Without this baseline you cannot demonstrate any of the last four.

**Do not report model quality alone.** That is the single most common way a systems-flavoured research claim fails review.

---

## 23. Phase 14 — Experiment Registry

Every run writes a machine-readable record. No exceptions, including failed runs — negative results are data.

```json
{
  "experiment_id": "E3",
  "run_id": "E3_20260101_142233",
  "dataset": "AML_HI_Small",
  "dataset_sha256": "…",
  "split": "temporal_70_15_15",
  "split_boundaries": { "train_end": "…", "val_end": "…" },
  "feature_set": ["transaction", "gfp", "temporal_flow"],
  "feature_count": 0,
  "model": "XGBoost",
  "model_params": {},
  "random_seed": 42,
  "threshold": 0.0,
  "threshold_selected_on": "validation",
  "pr_auc": 0.0,
  "roc_auc": 0.0,
  "precision": 0.0,
  "recall": 0.0,
  "f1_minority": 0.0,
  "recall_at_1pct_budget": 0.0,
  "false_positives_per_1k": 0.0,
  "feature_extraction_tx_per_sec": 0.0,
  "inference_latency_p95_ms": 0.0,
  "peak_memory_mb": 0.0,
  "python_version": "…",
  "library_versions": {},
  "hardware": "…",
  "git_commit": "…",
  "notes": ""
}
```

### Experiment identifiers

One scheme, used everywhere — in the registry, the ablation matrix, the results table and the report.

| ID | Feature combination | Model |
|---|---|---|
| `E1` | Transaction features only | XGBoost |
| `E2` | Transaction + GFP structural features | XGBoost |
| `E3` | E2 + temporal flow motifs | XGBoost |
| `E4` | E2 + value-flow features | XGBoost |
| `E5` | E2 + behavioural novelty | XGBoost |
| `E6` | E2 + risk-adaptive graph expansion | XGBoost |
| `E7` | Selected final combination | XGBoost |

`M0` (rules) and `M1` (= `E1`) are named separately because M0 is not a learned model. Record M0 under `E0` in the registry for a uniform results table.

### Tooling

* JSON per run plus an aggregate `experiments/results.csv` to start
* MLflow once the run count exceeds roughly twenty
* Git for code; record the commit hash in every run
* DVC for dataset versioning if raw files cannot live in Git
* SQLite if you want to query runs rather than grep them

---

## 24. Phase 15 — Research Innovation Directions

Investigate **one at a time**. Each becomes one ablation row. Each must be motivated by a specific error category from §20.

### A. Temporal flow motifs → targets slow/fast layering false negatives

Structure tells you a path exists; timing tells you how the money moved.

* Elapsed time between consecutive hops
* Total source-to-final-destination duration
* Transaction burst duration and burst count
* Mean and variance of inter-intermediary intervals
* Time-decayed path activity
* Temporal ordering of graph motifs (did the fan-out precede the fan-in?)
* Multi-scale time-window statistics

```text
A → B at 10:00
B → C at 10:02
C → D at 10:04
```

```text
tflow_mean_inter_hop_seconds = 120
tflow_three_hop_within_10min = 1
tflow_path_duration_seconds  = 240
```

Community context is an extension here: bottom-up random-walk methods (PageRank variants) can define local overlapping communities, and weighted temporal metrics computed inside those communities surface coordinated bursts characteristic of automated mule networks. Treat this as a sub-experiment with its own cost measurement — community detection is not free.

### B. Value-flow features → targets pass-through and mule typologies

Topology confirms a path exists; laundering is about the movement of value along it.

* `vflow_retention_ratio` — fraction of received value forwarded onward
* `vflow_inflow_outflow_ratio`
* `vflow_dissipation` — value lost across intermediate hops
* `vflow_split_score` — degree of amount fragmentation
* `vflow_aggregation_score` — degree of amount recombination
* `vflow_conservation_deviation`
* `vflow_source_to_final_ratio`

```text
A sends ₹10,00,000 to B
B sends  ₹9,80,000 to C
C sends  ₹9,50,000 to D
```

```text
vflow_retention_ratio = 950000 / 1000000 = 0.95
vflow_dissipation     = 0.05
```

An account forwarding 98% of an inflow within minutes is behaving very differently from one drawing funds down gradually, even though the graph topology is identical. That distinction is exactly what pure structural features miss.

### C. Behavioural novelty → targets legitimate-hub false positives

Not "does this pattern exist" but "is this unusual *for this account*".

* `nov_new_counterparty_rate`
* `nov_new_payment_type`
* `nov_amount_distribution_shift`
* `nov_degree_jump`
* `nov_activity_burst_vs_baseline`
* `nov_rare_pattern_score`

> An account that normally pays two known suppliers and suddenly pays 25 new accounts is anomalous. A payroll account that pays 400 accounts every month is not — even though its fan-out is far higher.

This is the primary defence against the payroll and merchant-settlement false positives identified in §20.

### D. Risk-adaptive graph expansion → targets throughput

Extracting deep multi-hop features for every benign transaction is wasteful.

```text
Incoming transaction
        ↓
One-hop neighbourhood analysis
        ↓
   risk < θ₁ ?
   ┌────┴────┐
  Yes        No
   │         │
  Stop    Expand to 2-hop
             ↓
        risk < θ₂ ?
        ┌────┴────┐
       Yes        No
        │         │
       Stop   Expand to 3-hop
```

Expected benefit: lower average extraction cost with preserved context where it matters.

**Evaluate carefully.** Adaptive exploration introduces selection bias: a suspicious transaction whose one-hop neighbourhood looks benign is never expanded, and the deep evidence is never gathered. Measure recall on exactly that population — transactions that were *not* expanded but were labelled illicit. Report average cost saving **and** the recall lost. If the recall loss is non-trivial, the honest conclusion is that adaptive expansion is a deployment-time cost lever, not an accuracy improvement.

### E. Multi-resolution temporal features → targets both fast and slow layering

Compute features at several window lengths simultaneously:

```text
5 minutes
1 hour
6 hours
1 day
7 days
```

Per resolution: transaction count, amount sum, counterparty count, fan-in, fan-out, cycle participation, flow velocity.

This directly addresses the tension where a single `δ` cannot capture both rapid smurfing and slow layering. Cost scales roughly linearly with the number of resolutions — measure it.

### F. Heterogeneous entity features → requires dataset support

Distinguish node types rather than treating every node as an identical account:

```text
Person | Company | Merchant | Supplier | Bank account
```

with typed relationships (ownership, employment, supply, account-holding).

**Attempt only if the selected dataset carries entity metadata.** On the public AML corpora it does not (§5.4), so this direction belongs to the Track P synthetic-context layer and must be reported separately.

### G. Fuzzy multi-stage pattern mining → targets evasion and throughput

Exact subgraph matching is brittle. Launderers introduce **structural fuzziness** (varying the hop count) and **temporal fuzziness** (delaying integration). Enumerating every permutation of a fuzzy pattern triggers combinatorial blow-up.

The alternative: decompose a laundering scheme into independent logical stages connected by set operations over active neighbourhoods, rather than searching for one rigid subgraph. Published work in this direction compiles such stage logic into optimised native kernels with power-law-aware memory access and degree-based workload balancing, reporting comparable or better F1 at substantially higher throughput. **[Verify the source and its claims before citing; the compiled-kernel implementation is almost certainly out of scope for a ten-week project.]**

**Realistic scope here:** implement the *decomposition idea* in Python — stage-wise neighbourhood set operations instead of exact motif enumeration — and measure whether it recovers fuzzy patterns that exact matching misses. Do not promise CUDA kernels.

---

## 25. Phase 16 — Controlled Ablation Studies

```text
E1  Baseline (transaction only)
E2  + GFP structural
E3  E2 + temporal flow
E4  E2 + value-flow
E5  E2 + behavioural novelty
E6  E2 + adaptive expansion
E7  Selected combination
```

### Rules

* Dataset fixed.
* Split fixed.
* Model family fixed.
* Threshold-selection procedure fixed.
* One feature group added at a time.
* Every run logged, including runs that made things worse.
* Report benefit **and** cost for every group.

A feature group earns a place in E7 only if it produces a measurable improvement that survives its own computational cost. "It felt like it should help" is not a result.

### Statistical honesty

With illicit rates near 0.1%, the test set may contain only a few thousand positives. Differences of a point or two in PR-AUC can be noise.

* Run each configuration with at least three seeds; report mean and spread.
* Report bootstrap confidence intervals on PR-AUC.
* Do not declare a winner on a difference smaller than the seed-to-seed variance.

---

## 26. Phase 17 — Main Comparison Table

| Model | PR-AUC | Precision | Recall | F1 | FP/1k | Recall@1% | Feat. tx/s | p95 latency | Peak RAM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E0 — Rule-based | — | — | — | — | — | — | — | — | — |
| E1 — Transaction XGB | — | — | — | — | — | — | — | — | — |
| E2 — GFP + XGB | — | — | — | — | — | — | — | — | — |
| E3 — + temporal flow | — | — | — | — | — | — | — | — | — |
| E4 — + value-flow | — | — | — | — | — | — | — | — | — |
| E5 — + novelty | — | — | — | — | — | — | — | — | — |
| E6 — + adaptive expansion | — | — | — | — | — | — | — | — | — |
| E7 — Final FlowGuard | — | — | — | — | — | — | — | — | — |

**Do not fill any cell until the experiment has actually run.** Placeholder numbers have a way of surviving into final reports.

---

## 27. Phase 18 — Cross-Dataset Validation

```text
                 FlowGuard (E7, frozen)
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    AML HI Small      AML LI Small       ETH Phishing
     (primary)        (lower rate)      (real network)
```

The question this answers: has the model learned general laundering behaviour, or has it memorised one synthetic generator's signature?

Compare and report:

* Feature availability differences and how gaps were handled
* Schema mapping required
* Performance change per metric
* Typology-transfer performance
* Runtime and memory differences at different scales
* Robustness to a different transaction-amount distribution

Expect degradation — especially on ETH Phishing, which is a different domain entirely. **Report the degradation.** A cross-dataset result that shows no drop usually indicates a bug in the evaluation, not a triumph.

---

## 28. Phase 19 — Final Model Selection

The final architecture might be:

```text
GFP structural features
        +
Temporal flow motifs
        +
Value-flow features
        +
Behavioural novelty
        +
Risk-adaptive expansion (deployment-time toggle)
        +
XGBoost
```

**Select this combination only if the ablations demonstrate it.** The final architecture is an output of the experiments, not an assumption written at the start of the project.

Record in the model card:

* Which feature groups were included and which were dropped, with the measured reason
* Operating threshold and how it was chosen
* Known failure modes from the error analysis
* Performance envelope: throughput and memory at the tested scale
* Datasets the model has *not* been validated on

---

## 29. Phase 20 — Typology Layer and Risk-Scoring Architecture (Track P)

Everything above scores an individual transaction. The product track adds the typology and case layers that an investigator actually works with.

### 29.1 Typology catalogue

| Typology | Definition | Detectable on public AML data? |
|---|---|---|
| **Layering** | Rapid movement through multiple intermediary accounts | Yes |
| **Round-tripping** | Funds return to a prior node via a cycle | Yes |
| **Fan-in / fan-out** | Many-to-one or one-to-many distribution | Yes |
| **Scatter-gather** | Disperse through intermediaries, re-aggregate | Yes |
| **Structuring** | Fragmented transfers with compressed timing and near-repeated amounts | Partially — see note |
| **Pass-through / mule** | High inflow, rapid high outflow, little retained | Yes (via value-flow features) |
| **Dormant activation** | Long inactivity followed by abnormal high-value flow | Requires synthetic context layer |
| **Profile mismatch** | Observed behaviour materially deviates from declared customer profile | Requires synthetic context layer |

**Note on structuring:** do not hard-code a statutory reporting threshold. Detect the *behaviour* — fragmentation, near-repeated amounts, compressed timing, aggregate volume inconsistent with the account baseline. The system surfaces suspicious fragmentation; a compliance officer makes the determination. Encoding a legal threshold into a model is both brittle and, depending on jurisdiction, inadvisable.

### 29.2 Layered risk architecture

```text
                      TRANSACTION
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 Tabular + graph        Anomaly         Deterministic
  XGBoost score        detector        typology rules
  (supervised)      (unsupervised)      (graph logic)
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                Correlation / Risk Layer
                           ▼
                    Case-level risk
```

Each layer answers a different question:

* **XGBoost** — does this look like known labelled laundering?
* **Anomaly detector** (e.g. Isolation Forest) — is this unusual regardless of labels? Catches typologies absent from training.
* **Deterministic typology rules** — is this a named pattern a regulator would recognise? Provides an auditable, non-statistical reason code.

### 29.3 Synthetic bank-context layer (Track P only)

Because the public research data lacks customer context (§5.4), Track P generates an explicitly-labelled augmentation layer:

```text
Entities:      10,000–50,000 customers
               50,000–200,000 accounts
               1,000–5,000 merchants
               10–100 branches
               3–8 channels

Transaction mix:  98–99% normal
                  0.2–1% suspicious
```

Do **not** rebalance toward a convenient illicit rate. An artificially balanced dataset produces a model whose precision collapses on contact with reality.

Injected ground-truth scenarios: layering, round-tripping, dormant activation, structuring, profile mismatch, fan-in/fan-out, and one **mixed-typology** case combining dormant activation + layering + cycle + profile mismatch. The mixed case is the demo centrepiece, because it is the case where single-typology rule systems most visibly fail.

Every result produced on this layer is labelled *synthetic augmented data* in the report and on every slide.

### 29.4 Combining the layers

Do not average scores without validation. Either:

* **Learn the combination** — train a small calibrated model on the layer outputs, using the same temporal split; or
* **State the weights explicitly** and justify each one, treating it as a documented policy decision rather than a model output.

An unvalidated weighted average presented as a risk score is the kind of thing that does not survive a governance review.

### 29.5 Decision thresholds

```text
0–39    LOW       → monitor
40–69   MEDIUM    → review
70–100  HIGH      → investigator case
```

These are **demonstration thresholds**. State plainly in the report:

> Production thresholds require calibration against the institution's risk appetite, historical case outcomes, investigator capacity and regulatory controls.

---

## 30. Phase 21 — Evidence Model and Case Output

### 30.1 One source of truth

```text
Raw transaction
    ↓
Normalised transaction
    ↓
Feature record
    ↓
Graph event
    ↓
Model outputs
    ↓
Evidence object
    ↓
Case
```

Every explanation, dashboard element, narrative sentence and exported report reads from the evidence object. Nothing generates its own facts.

### 30.2 Evidence object

```json
{
  "case_id": "FG-1042",
  "created_at": "2026-01-01T10:21:00Z",
  "transaction_ids": ["TX-1", "TX-2", "TX-3"],
  "accounts": ["ACC_000123", "ACC_004410", "ACC_009876"],
  "risk_score": 94,
  "risk_category": "HIGH",
  "primary_typology": "rapid_layering",
  "secondary_typologies": ["cycle", "pass_through"],
  "supporting_features": {
    "vflow_retention_ratio": 0.94,
    "hop_count": 3,
    "tflow_median_inter_hop_seconds": 143,
    "gfp_out_account_count": 18
  },
  "shap_top_features": [
    {"feature": "gfp_cycle_detected", "contribution": 0.21},
    {"feature": "tflow_mean_inter_hop_seconds", "contribution": 0.17}
  ],
  "path": [
    {"from": "ACC_000123", "to": "ACC_004410", "amount": 1800000, "at": "2026-01-01T10:00:00Z"},
    {"from": "ACC_004410", "to": "ACC_009876", "amount": 1690000, "at": "2026-01-01T10:21:00Z"}
  ],
  "model_version": "flowguard-xgb-1.0.0",
  "experiment_id": "E7",
  "threshold": 0.72,
  "data_snapshot": "AML_HI_Small@sha256:…",
  "investigator_notes": [],
  "disposition": null
}
```

### 30.3 Case export

Exported as JSON and PDF, containing: case ID, creation timestamp, risk score and category, primary and secondary typologies, masked account identifiers, the chronological transaction trail, the fund-flow graph, supporting features, model explanations, graph reasons, investigator notes, model version, data snapshot and audit metadata.

**Boundary:** the export is an internal investigation package. Do not present it as an FIU filing, and do not label it as an STR, unless an authorised integration exists. Say this explicitly in the demo.

### 30.4 Narrative discipline

> "Account ACC_004410 received ₹18.0 lakh after 11 months of inactivity and transferred ₹16.9 lakh onward within 21 minutes through three counterparties. The account is connected to a previously anomalous cluster, and observed velocity deviates materially from its historical baseline."

Every number in that sentence appears in the evidence object. If a number cannot be traced there, it does not go in the narrative.

---

## 31. Phase 22 — Demonstration Application

### Backend

FastAPI · Python · XGBoost · pandas/Polars · graph module · SHAP · evidence builder

### Frontend

Streamlit for the research demo; React if a more polished investigator UI is needed and time allows. Do not start with React.

### Dashboard screens

**1 — Risk overview.** Alert volume over time, risk distribution, model version in use, current threshold.

**2 — Case queue.** Ranked cases with score, primary typology, accounts involved, age, status. Sortable by score and by alert budget.

**3 — Transaction scoring.** Upload a CSV or enter a transaction; returns risk score, category, predicted label, detected typologies, top contributing features.

**4 — Fund trace.** Interactive graph: account nodes, transaction edges, the highlighted suspicious path, amounts, timestamps, detected motifs. Controls for hop depth, time window, direction (forward/backward) and amount filter.

**5 — Why flagged.** SHAP contributions beside the graph evidence and the typology reason codes, each linked to the specific transactions that produced them.

**6 — Timeline.** Chronological view of the case's transactions with inter-hop intervals and retention ratios.

**7 — Model performance.** PR-AUC, F1, precision, recall, FP/1k, latency distribution, throughput, memory — read directly from the experiment registry, never hard-coded.

**8 — Model comparison.** E0 through E7 side by side, from `experiments/results.csv`.

**Usability target:** a reader unfamiliar with the project should understand why a high-risk case is high-risk within about 30 seconds of opening it.

---

## 32. Phase 23 — API Design

```http
GET  /health
```

```http
POST /score
```

Request:

```json
{
  "transaction_id": "TX1001",
  "timestamp": "2026-01-01T10:00:00Z",
  "source_account": "ACC_000123",
  "destination_account": "ACC_009876",
  "amount": 10000.0,
  "currency": "INR",
  "payment_type": "WIRE"
}
```

Response:

```json
{
  "transaction_id": "TX1001",
  "risk_score": 0.91,
  "risk_category": "HIGH",
  "predicted_label": 1,
  "threshold": 0.72,
  "detected_typologies": ["fan_out", "rapid_layering"],
  "top_features": [
    {"feature": "tflow_mean_inter_hop_seconds", "contribution": 0.19},
    {"feature": "gfp_out_account_count", "contribution": 0.15},
    {"feature": "vflow_retention_ratio", "contribution": 0.12}
  ],
  "model_version": "flowguard-xgb-1.0.0",
  "experiment_id": "E7",
  "scored_at": "2026-01-01T10:00:00.412Z"
}
```

Note that the request carries no label field. The scoring endpoint must not accept `is_laundering` — accepting it invites accidental leakage in evaluation harnesses.

```http
GET  /transactions/{transaction_id}/explanation
GET  /transactions/{transaction_id}/graph?hops=2&window=24h
GET  /cases
GET  /cases/{case_id}
GET  /cases/{case_id}/evidence          # JSON evidence object
GET  /cases/{case_id}/export?format=pdf
POST /cases/{case_id}/notes
POST /cases/{case_id}/disposition
GET  /evaluation/summary                # reads the experiment registry
```

---

## 33. Phase 24 — Testing and Reproducibility

### Data tests

* Required columns exist with correct dtypes
* Timestamps parse and are timezone-consistent
* Amounts are numeric and non-negative
* `transaction_id` is unique
* `is_laundering` ∈ {0, 1}

### Graph tests

* Each transaction produces exactly one edge
* Edge direction matches source → destination
* Temporal ordering is preserved under insertion
* Self-loops are excluded from the graph but retained in the ledger
* Tombstoned edges are invisible to feature extraction
* Sweep compaction preserves all non-tombstoned edges

### Feature tests

Hand-computed expectations on tiny graphs:

```text
A → B
A → C
A → D
```

```text
gfp_src_out_degree(A)      == 3
gfp_out_account_count(A)   == 3
gfp_cycle_detected(A)      == 0
```

```text
A → B → C → A
```

```text
gfp_cycle_detected    == 1
gfp_shortest_cycle_length == 3
```

### Leakage tests (the most important ones)

* A feature extractor given a graph containing future edges produces identical output to one given only past edges
* No feature function can reach `is_laundering` — assert via the feature-module interface, not by convention
* Training-split maximum timestamp < validation-split minimum timestamp
* Shuffling the test set does not change aggregate metrics

### Model tests

* Feature column names and order are identical at training and inference
* A saved model reloaded from disk reproduces the same predictions
* Missing features raise an error rather than silently imputing
* A fixed seed reproduces identical metrics across runs

### Integration and scenario tests

```text
transaction → graph → features → model → risk → case → evidence
```

Scenario coverage: normal, layering, cycle, scatter-gather, fan-in, fan-out, pass-through, and the mixed-typology case.

### Reproducibility checklist

* [ ] Dependencies pinned in a lock file
* [ ] Configs committed
* [ ] Seeds recorded per run
* [ ] Dataset checksums recorded
* [ ] Model hyperparameters saved with the model
* [ ] Experiment metadata written for every run
* [ ] Git commit hash in every registry entry
* [ ] A clean checkout reproduces the headline number with one command

---

## 34. Governance, Responsible AI, Privacy and Security

### 34.1 Model governance

Track for every model version:

```text
Model name and version
Training data version and checksum
Feature set version
Training date and evaluation date
Operating threshold and how it was selected
Measured performance envelope
Known limitations and failure modes
```

Every scored output records the model version, threshold and inference timestamp. That triple is what makes a decision auditable months later.

### 34.2 Responsible AI boundaries

The system outputs:

> **"Potential suspicious pattern detected."**

Never:

> ~~"This customer is laundering money."~~

FlowGuard is decision support. A human investigator makes every determination. This is both an ethical position and a legal one.

Additional commitments:

* Evaluate whether performance differs materially across customer segments, where such attributes are used at all.
* Prefer not to use attributes that act as proxies for protected characteristics; if any are used, justify them explicitly.
* Log investigator dispositions so that model error can be measured against human judgement over time.

### 34.3 Privacy

* Synthetic and public research data only. No real customer information at any point.
* Pseudonymised identifiers in every artifact: `Customer_001`, `Account_78421`, `TXN_103829`.
* Separate identifying attributes from analytic attributes; models consume the minimum field set needed.
* Never imply the demonstration is connected to a live banking system.

### 34.4 Security

```text
Authentication → Authorization → API gateway → Validated input
    → Analytics → Risk engine → Audit log
```

Protect API credentials, database credentials, any cloud service tokens, model artifacts and any sensitive fields. Secrets live in environment configuration, never in the repository. Audit-log every case access and every export.

### 34.5 Non-functional targets (prototype, not production guarantees)

| Property | Prototype target |
|---|---|
| Transaction scoring | < 2 s end-to-end |
| Common graph trace | < 3 s |
| Dashboard refresh | < 2 s |
| Case export | < 10 s |
| Scale handled smoothly | ≥ 100k synthetic transactions |
| Deterministic outputs | Identical input → identical risk score |
| Malformed input | Handled gracefully, logged, never crashes the stream |

---

## 35. Technology Stack

| Component | Tool |
|---|---|
| Language | Python |
| Data processing | pandas or Polars |
| Storage format | Parquet |
| Graph prototyping | NetworkX (validation and visualisation only) |
| Graph runtime | Custom incremental adjacency with tombstoned eviction |
| Graph features | Snap ML Graph Feature Preprocessor, if available for the platform; otherwise a verified re-implementation |
| Supervised model | XGBoost |
| Anomaly model | Isolation Forest (Track P) |
| Explainability | SHAP |
| Validation | Pandera or explicit validators |
| Experiment tracking | JSON registry, then MLflow |
| Version control | Git |
| Dataset versioning | DVC, if raw data cannot be committed |
| API | FastAPI |
| Dashboard | Streamlit (React only if time allows) |
| Visualisation | Matplotlib, Plotly, PyVis |
| Profiling | `time.perf_counter`, `tracemalloc`, `memory_profiler`, `psutil` |
| Testing | Pytest |
| Environment | `venv` or Conda with a lock file |
| Packaging | Docker |

Start simple. Distributed processing, GPU kernels and graph databases come after the single-machine baseline works and has been profiled.

---

## 36. Scope Control

### Must have

Transaction ingestion · canonical schema · leakage-safe temporal split · streaming graph construction · GFP-style graph features · M0 rule baseline · M1 transaction XGBoost · M2 graph XGBoost · evaluation framework with cost metrics · error analysis · SHAP explanations · experiment registry · reproducible single-command run

### Should have

Temporal flow features · value-flow features · behavioural novelty · ablation suite · fund-trace dashboard · evidence package · FastAPI backend · cross-dataset validation

### Nice to have

Risk-adaptive expansion · multi-resolution windows · fuzzy multi-stage mining (Python-level) · Isolation Forest layer · synthetic bank-context layer · case management · LLM narrative generation over the evidence object

### Do not build unless everything above is done

Graph neural networks · compiled CUDA kernels · graph embeddings · homomorphic encryption · production IAM · real FIU filing integration · cross-institution deployment · blockchain anything

The failure mode this section exists to prevent: an impressive-sounding component half-built while the baseline remains unmeasured.

---

## 37. Ten-Week Timeline

| Week | Focus | Deliverable |
|---|---|---|
| 1 | Dataset verification, licence check, project structure, immutable raw layer, dataset metadata, generic loader | Raw data layer + loader + dataset report |
| 2 | Canonical schema, validation, EDA, quality report, graph and temporal distributions | Data-quality report + EDA notebooks |
| 3 | Temporal split module + leakage tests, M0 rules, M1 transaction XGBoost, evaluation framework | E0 and E1 logged + metric framework |
| 4 | CTDG construction, sliding window, tombstoned GC, degree/neighbourhood features, memory benchmarks | Streaming graph module + memory profile |
| 5 | GFP verification and integration, exact pattern mining, M2 | E2 logged + first F1 and throughput numbers |
| 6 | Error analysis, SHAP, latency profiling, computational baseline | False-positive breakdown + explainability module |
| 7 | Temporal flow motifs, value-flow features, behavioural novelty | E3, E4, E5 logged |
| 8 | Adaptive expansion, multi-resolution windows, fuzzy-mining prototype, accuracy-vs-throughput analysis | E6 logged + efficiency report |
| 9 | Final selection, seeds and confidence intervals, cross-dataset validation, model card, limitations | E7 frozen + cross-dataset report |
| 10 | FastAPI backend, dashboard, fund trace, evidence package, final report | End-to-end demonstration + technical report |

**Ordering note:** the temporal split and its leakage tests are built in week 3, **before** the first learned model is evaluated — not after. Building a model and retrofitting the split is how leaked results end up in a report.

**Buffer reality:** weeks 7 and 8 contain five research directions. If week 6's error analysis shows two dominant failure categories, drop the directions that do not address them. A plan that is executed on three directions beats a plan that is half-executed on five.

---

## 38. Final Deliverables

### Technical

Clean AML data pipeline · canonical schema module · leakage-safe split module with tests · streaming CTDG with tombstoned GC · graph feature extractors · novel feature modules · M0/M1/M2 and E3–E7 models · evaluation framework with cost profiling · experiment registry · SHAP explanation module · graph visualisation · evidence builder and exporter · FastAPI backend · dashboard · Docker configuration · test suite

### Research

Dataset analysis report · GFP implementation and verification report · baseline comparison report · error-analysis report · ablation-study report · accuracy-versus-efficiency trade-off analysis · cross-dataset validation report · model card · limitations and threats-to-validity section · final technical report or paper

---

## 39. Master Research Flow

```text
                  ┌────────────────────┐
                  │ Dataset selection  │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Immutable raw data │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Validation + EDA   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Canonical schema   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Temporal split     │
                  │ + leakage tests    │
                  └─────────┬──────────┘
                            ▼
            ┌───────────────┴───────────────┐
            ▼                               ▼
  ┌────────────────────┐          ┌────────────────────┐
  │ Transaction        │          │ Streaming temporal │
  │ features           │          │ graph (CTDG)       │
  └─────────┬──────────┘          └─────────┬──────────┘
            ▼                               ▼
  ┌────────────────────┐          ┌────────────────────┐
  │ E1: XGBoost        │          │ Graph feature      │
  │ baseline           │          │ extraction (GFP)   │
  └─────────┬──────────┘          └─────────┬──────────┘
            │                               ▼
            │                     ┌────────────────────┐
            │                     │ E2: GFP + XGBoost  │
            │                     └─────────┬──────────┘
            └───────────────┬───────────────┘
                            ▼
                  ┌────────────────────┐
                  │ Baseline evaluation│
                  │ + cost profiling   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Error analysis     │
                  └─────────┬──────────┘
                            ▼
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   E3 temporal        E4 value-flow        E5 novelty
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                  ┌────────────────────┐
                  │ E6 adaptive /      │
                  │ efficiency study   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Controlled         │
                  │ ablation studies   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Cross-dataset test │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ E7: Final model    │
                  │ + model card       │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Evidence layer     │
                  │ API + dashboard    │
                  └────────────────────┘
```

---

## 40. First Practical Milestone — M0

Do not begin by implementing the whole system. The first milestone is a **reproducible baseline**, not a feature.

M0 is complete when all of these are true:

```text
✓ Dataset selected, licence checked, schema verified
✓ Raw data preserved immutably with checksums
✓ Dataset metadata recorded
✓ Data-quality report generated
✓ Canonical schema implemented and tested
✓ Leakage-safe temporal split implemented WITH passing leakage tests
✓ Rule-based baseline (E0) implemented and logged
✓ Transaction-only XGBoost (E1) trained and logged
✓ Streaming temporal graph constructed and unit-tested
✓ GFP integration or verified re-implementation complete
✓ Graph-feature XGBoost (E2) trained and logged
✓ PR-AUC, minority F1, precision, recall recorded
✓ Latency distribution and peak memory recorded
✓ SHAP explanations produced for sample alerts
✓ Error analysis categorised and counted
✓ Experiment registry populated for E0, E1, E2
✓ One command reproduces the headline result from a clean checkout
```

Only after this should new graph algorithms, adaptive expansion, fuzzy mining or agentic workflows begin.

### First executable workflow

```bash
python -m flowguard.pipeline.run_baseline --config configs/experiment.yaml
```

### Immediate next actions

1. Download the candidate dataset and verify its schema against §8 — column names, label semantics, timestamp format.
2. Confirm whether the Graph Feature Preprocessor is installable on your platform, and record its version.
3. Create the repository structure from §9.
4. Implement `data/loader.py`, `data/schema.py` and `data/validator.py`.
5. Implement `evaluation/splits.py` **together with its leakage tests**, before any model code.

---

## 41. Risks, Limitations and Threats to Validity

State these in the report. A limitations section that is honest is a strength; one that is absent is an invitation.

| Risk | Impact | Mitigation |
|---|---|---|
| Synthetic data does not reflect real laundering | Results may not transfer | Cross-dataset validation on ETH Phishing; explicit statement in limitations |
| Subtle temporal leakage | Inflated metrics throughout | Automated leakage tests; deliberate leaky control run for contrast |
| Extreme class imbalance | Unstable metrics, noisy comparisons | Multi-seed runs, bootstrap CIs, alert-budget metrics |
| GFP implementation mismatch | Baseline is not what the literature reports | Verify version; describe as GFP-inspired until confirmed; validate on hand-computed graphs |
| Window `δ` mis-set | Systematic blindness to slow layering | Multi-resolution study (§24.E); report sensitivity to `δ` |
| Adaptive expansion selection bias | Hidden recall loss | Measure recall specifically on non-expanded illicit transactions |
| Hardware variance | Incomparable timing results | Freeze hardware; report specs; re-run baselines if hardware changes |
| Scope creep into GNNs / kernels | Baseline never finished | §36 scope control; M0 gate |
| Over-claiming novelty | Credibility loss under questioning | §5.2 claim discipline |
| Dashboard numbers drifting from measured results | Misleading demo | Dashboard reads the registry; nothing hard-coded |

### Explicit non-claims

* FlowGuard does not determine that money laundering has occurred.
* FlowGuard does not replace an institution's AML platform.
* FlowGuard has not been validated on real banking data.
* Reported thresholds are demonstration values, not production settings.
* Performance figures apply to the tested hardware and dataset scale only.

---

## 42. Future Work

### 42.1 Collaborative AML across institutions

Launderers deliberately fragment networks across multiple banks so that no single institution sees the full topology. Intra-institutional detection — everything in this plan — is structurally blind to that fragmentation.

A future direction is privacy-preserving collaborative analysis using fully homomorphic encryption: participating institutions encrypt local transaction edges under a shared public key; a central processor performs feature extraction and inference on ciphertexts without decrypting identities or amounts; encrypted risk scores are returned and decrypted locally. This would give cross-institution visibility while preserving confidentiality and data-localisation compliance.

**Scope reality:** FHE inference is orders of magnitude slower than plaintext inference, and graph feature extraction over ciphertext is substantially harder than tree inference alone. Treat this as a research horizon and a report section, not a deliverable. If demonstrated at all, demonstrate it on a toy graph with measured latency stated honestly.

### 42.2 Other directions

* Account-level and path-level prediction with their own labels and evaluation
* Closed-loop learning from investigator dispositions
* Graph neural networks, if and only if they beat the boosted baseline on your data
* Streaming deployment with real event infrastructure and sustained-load benchmarks

---

## 43. References

Every reference below must be opened and verified before it appears in a report. Several were inherited from the source analysis and have not been independently confirmed.

**Graph features and AML modelling**

1. Graph Feature Preprocessor: real-time subgraph-based feature extraction — <https://arxiv.org/abs/2402.08593>
2. Graph Feature Preprocessor — Snap ML documentation — <https://snapml.readthedocs.io/>
3. Realistic synthetic financial transactions for anti-money laundering models — <https://arxiv.org/abs/2306.16424>
4. BlazingAML: high-throughput AML graph mining — **[verify arXiv ID and publication status]**
5. Extracting money-laundering transactions from quasi-temporal graphs (ExSTraQt) — **[verify arXiv ID and publication status]**

**Temporal graph systems**

6. TGLite: a lightweight framework for continuous-time dynamic graphs — <https://charithmendis.com/assets/pdf/24-asplos-tglite.pdf>
7. UTG: toward a unified view of snapshot and event-based models — <https://arxiv.org/abs/2407.12269>
8. Mark-and-sweep garbage collection — standard compiler/runtime literature

**Regulatory and operational**

9. RBI Master Direction on KYC / AML — <https://www.rbi.org.in/>
10. FIU-IND publications and annual reports — <https://fiuindia.gov.in/files/Publication/Publication.html>
11. FATF — <https://www.fatf-gafi.org/>
12. BIS Innovation Hub, Project Aurora — <https://www.bis.org/project/aurora>
13. BIS Project Aurora report — <https://www.bis.org/publ/othp66.pdf>

**Privacy-preserving inference**

14. Privacy-preserving graph-based machine learning with fully homomorphic encryption — **[verify]**
15. Concrete ML / TFHE documentation — **[verify current version]**

---

## 44. Change Log — What Was Corrected

Recorded so that anyone comparing this document to the original `start.txt` can see what moved and why.

### Correctness fixes

1. **Label field unified.** The original used `label` in the validation rules, canonical representation and edge attributes, but `is_laundering` in the expected schema table. Now `is_laundering` everywhere, with an explicit note that feature code must never read it.
2. **Experiment IDs unified.** The original had two incompatible schemes (`EXP001_RULE_BASELINE` in §22 and `E1`–`E7` in §24). Now `E0`–`E7` only.
3. **Feature-extraction ordering specified.** The original did not state whether a transaction's own edge is inserted before or after its features are extracted — a silent source of label-adjacent leakage. Now explicit.
4. **Dataset selection made concrete.** The original said "AMLSim or verified IBM AML dataset" and drew a cross-dataset diagram of "AMLSim / IBM AML / Other AML". Now a named primary, scale-test, contrast and cross-dataset corpus with a stated rationale.
5. **Capability gap documented.** The original listed heterogeneous-entity features as a research direction without noting that the chosen dataset carries no entity metadata. §5.4 now maps every feature family to whether the data supports it, and routes the rest to an explicitly-labelled synthetic layer.
6. **Timeline reordered.** The original week 3 listed training XGBoost before building the temporal split. Split and leakage tests now precede every learned model.
7. **ASCII diagrams rebuilt.** Several box diagrams in the original had mismatched widths and misaligned arrows.
8. **Heading levels normalised.** The original mixed `##` and `#` for sibling sections.
9. **`scenario_id` and `pattern_type` reconciled.** Listed in the original's schema table but missing from its canonical representation example.
10. **ROC-AUC demoted.** Listed alongside PR-AUC without comment in the original; now explicitly not the headline under extreme imbalance.

### Material added from the refined analysis

Continuous-time dynamic graph framing · sliding temporal window with explicit `δ` · tombstoned mark-and-sweep eviction and its measurement · the dataset comparison table · GNN-versus-boosting rationale · fuzzy multi-stage mining (scoped realistically) · community-context temporal metrics · FIU-IND / PMLA explainability requirement · FHE future work.

### Material added from the PS9 blueprint

Regulatory and operational context · typology catalogue including structuring, dormant activation and profile mismatch · layered risk-scoring architecture · anomaly-detection layer · evidence object as single source of truth · case export and narrative discipline · investigator dashboard screens · model governance · responsible-AI boundaries · privacy and security requirements · non-functional targets · scope control tiers.

### Material added that was in neither source

Leakage-control checklist and automated leakage tests · deliberate leaky-control run · statistical-honesty rules (multi-seed, bootstrap CIs) · alert-budget metrics · error-driven feature design as an explicit gate · adaptive-expansion selection-bias measurement · risks and threats-to-validity table · explicit non-claims · verification flags on every unconfirmed citation · this change log.
