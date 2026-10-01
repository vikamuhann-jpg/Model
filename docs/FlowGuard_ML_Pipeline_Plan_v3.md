# FlowGuard — ML Research Pipeline Plan

### Raw Data → Validated Model

**Version:** 3.0 (scoped)
**Supersedes:** `start.txt` v1, Unified Plan v2
**Scope:** data ingestion through validated final model. Nothing downstream of that.

---

## 0. Scope Definition

This plan covers one thing: building a defensible machine-learning pipeline for graph-based AML detection, from raw files to a model that has passed explicit validation gates.

### In scope

```text
Raw data acquisition
    ↓
Schema canonicalisation and quality validation
    ↓
Leakage-safe temporal splitting
    ↓
Streaming transaction-graph construction
    ↓
Feature extraction (tabular + graph + novel families)
    ↓
Model training with a fixed protocol
    ↓
Evaluation, error analysis, interpretation
    ↓
Ablation studies
    ↓
Cross-dataset validation
    ↓
Final model selection
    ↓
VALIDATION GATES  ← terminus
```

### Out of scope

Not built, not designed, not estimated:

| Excluded | Why it is excluded |
|---|---|
| FastAPI backend / REST endpoints | Serving concern |
| Streamlit or React dashboard | Presentation concern |
| Investigator workflow, case management | Product concern |
| Evidence packages, STR narrative generation | Product concern |
| LLM narrative layer | Product concern |
| Docker / deployment / CI-CD | Operations concern |
| Synthetic bank-context data generation | Only needed for typologies the research data cannot express |
| Dormant-activation and profile-mismatch typologies | Require customer context the dataset does not carry (§3.4) |
| Homomorphic encryption, cross-institution federation | Research horizon, not a deliverable |
| IBM product positioning | Not a modelling concern |

SHAP stays in scope — but as a **model-interpretation and leakage-detection tool**, not as a compliance explanation feature. Its job here is to tell you whether the model learned something real.

### The boundary artifact

The terminus is a **validated model package** (§26) that a future serving track could pick up without re-deriving anything. Producing that package cleanly is part of this scope; consuming it is not.

---

## 1. Objective

### Research question

> **Do graph-structural, temporal and value-flow features measurably improve transaction-level AML detection over a tabular baseline — and at what cost in feature-extraction throughput and memory?**

Both halves are the deliverable. A result that reports only detection quality has answered half the question.

### Target

Per-transaction binary classification: is this transaction part of a laundering pattern?

### Method

```text
REPRODUCE a graph-feature baseline
    ↓
MEASURE where it fails, and why
    ↓
DESIGN features that target those specific failures
    ↓
ABLATE one change at a time
    ↓
VALIDATE against gates fixed in advance
```

The third step is conditional on the second. Features designed before the error analysis exists are guesses, and the plan treats them as such.

### Success criteria

The project succeeds if it produces a trustworthy answer — including "graph features did not help on this dataset", which is a publishable result if the pipeline is sound. It fails if it produces an impressive number nobody can reproduce or defend.

---

## 2. Dataset Strategy

### 2.1 Candidate corpora

| Dataset | Nodes | Edges | Illicit rate | Span |
|---|---:|---:|---:|---:|
| AML HI Small | 0.5 M | 5 M | 0.102% | 10 days |
| AML HI Medium | 2.1 M | 32 M | 0.110% | 16 days |
| AML HI Large | 2.1 M | 180 M | 0.124% | 97 days |
| AML LI Small | 0.7 M | 7 M | 0.051% | 10 days |
| ETH Phishing (real) | 2.9 M | 13 M | 0.278% | 1261 days |

**[Figures inherited from the source analysis. Re-derive every one of them from the files you actually download and record your own counts. Do not cite the table above in a report.]**

### 2.2 Roles

| Role | Dataset | Used for | Never used for |
|---|---|---|---|
| **Primary** | AML HI Small | All model development, ablation, selection | — |
| **Scale test** | AML HI Medium | Throughput and memory scaling only | Model selection |
| **Rate contrast** | AML LI Small | Sensitivity to a ~2× lower illicit rate | Model selection |
| **Cross-dataset** | ETH Phishing | Generalisation test, run once at the end | Anything before §25 |

AML HI Small is the primary because it iterates fast and its illicit rate keeps minority-class metrics from becoming pure noise. Ten days of span is short — note in the limitations that long-horizon layering is structurally undetectable in it.

ETH Phishing is the honest generalisation test precisely because it is a different domain with a real (not generated) topology. Passing it cannot be explained by having memorised a simulator's signature.

### 2.3 Verification before any code

* [ ] Files downloaded, SHA-256 recorded
* [ ] Licence permits your intended use and redistribution method
* [ ] Column names and dtypes enumerated
* [ ] Label semantics confirmed — per transaction, per pattern, or per account?
* [ ] Timestamp format, timezone, resolution, and monotonicity confirmed
* [ ] Account identifiers confirmed globally unique (or a namespacing rule defined)
* [ ] Row count and illicit rate computed and recorded
* [ ] Memory footprint when loaded, measured against your RAM budget
* [ ] Graph Feature Preprocessor availability confirmed for your platform, version recorded

---

## 3. Source Reconciliation and Claim Discipline

### 3.1 What each source actually gives you

| Source | Provides | Does not provide |
|---|---|---|
| IBM synthetic AML data / AMLSim | Transaction ledgers with injected typologies and ground-truth labels | Customer profiles, dormancy, branch/channel context |
| GFP literature | A described method for incremental subgraph-pattern and vertex-statistical features | A guarantee its datasets match your download |
| PS9 blueprint | Product framing and typology vocabulary | Any measured result |

### 3.2 Three rules

1. **Do not assume your download equals the datasets in the GFP literature.** Verify schema, labels and scale yourself.
2. **Do not call the first implementation an exact reproduction.** Until version and configuration are confirmed, it is *a GFP-inspired graph-feature baseline*.
3. **Do not claim graph analytics for AML is novel.** It is not, and the claim will be challenged.

### 3.3 What can be claimed

> **A controlled, leakage-audited measurement of what graph, temporal and value-flow features contribute to transaction-level AML detection, with the computational cost of each contribution reported alongside it.**

That is a defensible contribution. It is also a more useful one than an unreproducible accuracy number.

### 3.4 Capability gap — what this dataset cannot support

| Feature family | Requires | Supported? |
|---|---|---|
| Fan-in, fan-out, cycles, scatter-gather | transactions | Yes |
| Temporal flow motifs | timestamps | Yes |
| Value-flow / retention | amounts | Yes |
| Behavioural novelty | account history | Yes |
| Degree / neighbourhood | graph | Yes |
| Dormant activation | account-open and inactivity history | **No** |
| Profile mismatch | KYC attributes | **No** |
| Channel / branch typologies | operational context | **No** |
| Heterogeneous entity graph | entity-type metadata | **No** |

The four unsupported rows are **dropped from this plan entirely**, not deferred. Under the narrowed scope there is no synthetic augmentation layer to carry them, so listing them would be planning work that cannot be executed.

---

## 4. Phase 0 — Freeze the Experimental Rules

Freeze before the first model runs. Record in `configs/experiment.yaml` and echo into every registry entry.

| Item | Frozen value |
|---|---|
| Primary dataset | AML HI Small, specific file set, SHA-256 recorded |
| Prediction target | Per-transaction `is_laundering` ∈ {0, 1} |
| Split | Chronological 70 / 15 / 15 on transaction time |
| Split boundaries | Actual timestamps, printed and recorded |
| Random seeds | `[42, 1337, 2718]` — three seeds per configuration |
| Hardware | CPU model, cores, RAM, GPU if any |
| Python | Exact interpreter version |
| Libraries | XGBoost, Snap ML, NetworkX, pandas/Polars, scikit-learn, SHAP — pinned |
| Headline metric | PR-AUC on the temporal test split |
| Supporting metrics | Minority F1, precision, recall, recall@budget, FP/1k |
| Cost metrics | Feature-extraction tx/s, inference p50/p95/p99, peak RSS |
| Threshold policy | Selected on validation only, at a fixed alert budget |
| Feature naming | `snake_case`, family-prefixed: `tx_`, `gfp_`, `tflow_`, `vflow_`, `nov_` |
| Experiment IDs | `E0` … `E7` only |
| Storage | Parquet for tables, JSON for metadata and metrics |

### The governing rule

> **Every model uses the same dataset, target, split, threshold-selection procedure and evaluation code.**

If one of those changes, the run gets a new ID and is not comparable to prior runs. Record that explicitly rather than quietly re-running everything.

---

## 5. Repository Structure

Scoped to the ML pipeline. No `api/`, no `frontend/`, no `evidence/`.

```text
flowguard/
│
├── README.md
├── pyproject.toml
├── requirements.lock
├── Makefile
│
├── configs/
│   ├── dataset.yaml
│   ├── features.yaml
│   ├── model.yaml
│   └── experiment.yaml
│
├── data/
│   ├── raw/                  # immutable after ingestion
│   ├── interim/
│   ├── processed/
│   └── splits/
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_quality.ipynb
│   ├── 03_graph_analysis.ipynb
│   ├── 04_baseline_analysis.ipynb
│   └── 05_error_analysis.ipynb
│
├── src/
│   └── flowguard/
│       ├── data/
│       │   ├── loader.py
│       │   ├── schema.py
│       │   ├── validator.py
│       │   └── profiling.py
│       │
│       ├── splits/
│       │   ├── temporal.py
│       │   ├── unseen_pattern.py
│       │   ├── hard_negative.py
│       │   └── leakage_checks.py
│       │
│       ├── graph/
│       │   ├── temporal_graph.py     # CTDG: window, insert, tombstone, sweep
│       │   ├── adjacency.py
│       │   └── motifs.py
│       │
│       ├── features/
│       │   ├── base.py               # FeatureExtractor interface
│       │   ├── transaction.py
│       │   ├── gfp.py
│       │   ├── temporal_flow.py
│       │   ├── value_flow.py
│       │   ├── novelty.py
│       │   └── adaptive.py
│       │
│       ├── models/
│       │   ├── rules.py
│       │   ├── xgb.py
│       │   ├── tuning.py             # rolling-origin search
│       │   └── calibration.py
│       │
│       ├── evaluation/
│       │   ├── metrics.py
│       │   ├── thresholds.py
│       │   ├── stability.py
│       │   ├── sanity.py             # null baselines, shuffle test
│       │   ├── error_analysis.py
│       │   ├── interpretation.py     # SHAP
│       │   └── profiling.py          # latency, throughput, memory
│       │
│       ├── registry/
│       │   └── experiments.py
│       │
│       └── pipeline/
│           ├── run_baseline.py
│           ├── run_experiment.py
│           └── run_ablation.py
│
├── experiments/
│   ├── E0/ … E7/
│   └── results.csv
│
├── models/                   # frozen artifacts + model cards
│
├── reports/
│   ├── data_quality/
│   ├── metrics/
│   ├── error_analysis/
│   └── figures/
│
└── tests/
    ├── unit/
    ├── leakage/              # treated as a first-class test category
    └── integration/
```

---

## 6. Canonical Schema and Data Contract

Single source of truth for field names. This resolves the `label` / `is_laundering` collision present in the original draft.

### 6.1 Canonical record

| Field | Type | Required | Purpose |
|---|---|---|---|
| `transaction_id` | string | yes | Unique key; join key for feature tables |
| `timestamp` | datetime (UTC) | yes | Ordering, splitting, windowing |
| `source_account` | string | yes | Graph source node |
| `destination_account` | string | yes | Graph destination node |
| `amount` | float | yes | Value-flow feature basis |
| `currency` | string | yes | Cross-border signal |
| `payment_type` | string | no | Transfer mechanism |
| `is_laundering` | int {0,1} | yes | Ground truth |
| `scenario_id` | string | no | Injected-scenario identifier, if present |
| `pattern_type` | string | no | Typology annotation, if present |

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

### 6.2 The label-isolation rule

`is_laundering`, `scenario_id` and `pattern_type` are **evaluation-only columns**.

Enforce this structurally, not by convention:

```python
class FeatureExtractor:
    """Feature extractors receive a label-free view. Enforced, not documented."""

    FORBIDDEN = {"is_laundering", "scenario_id", "pattern_type"}

    def extract(self, tx_view, graph_view):
        assert not (self.FORBIDDEN & set(tx_view.columns))
        ...
```

Every feature module inherits this. A test asserts that no extractor can see a forbidden column (§27). This single constraint prevents the most common and most embarrassing failure mode in this class of project.

### 6.3 Graph edge payload

```text
transaction_id, timestamp, amount, currency, payment_type
```

Labels are **not** stored on edges. They live in a separate table joined on `transaction_id` at evaluation time only. This is stricter than the previous draft, which stored the label on the edge "for evaluation" — an unnecessary temptation.

---

## 7. Phase 1 — Ingestion and Immutable Raw Layer

```text
Download / generate
       ↓
SHA-256 per file
       ↓
Write to data/raw/ (read-only thereafter)
       ↓
Dataset metadata record
       ↓
Load → canonical schema → data/interim/
```

```json
{
  "dataset_name": "IBM AML HI Small",
  "dataset_version": "v1",
  "download_date": "YYYY-MM-DD",
  "files": [
    {"file_name": "transactions.csv", "sha256": "…", "bytes": 0, "row_count": 0}
  ],
  "source_url": "…",
  "licence": "…",
  "row_count_total": 0,
  "illicit_count": 0,
  "illicit_rate": 0.0,
  "time_min": "…",
  "time_max": "…",
  "ingested_at": "…",
  "ingested_by_commit": "…"
}
```

### Rules

* `data/raw/` is never written after ingestion. Set it read-only if your OS permits.
* Every transformation writes a new artifact to `interim/` or `processed/`.
* Row counts at ingestion are asserted against row counts after loading. Mismatch is a hard failure.
* The illicit rate recorded here is the reference value. If it changes after cleaning, §9 requires an explanation.

---

## 8. Phase 2 — Profiling and Exploratory Analysis

Several downstream decisions depend on what you find here: window length `δ`, expansion depth, alert budget, and which typologies are even present.

### Critical constraint

> Compute any statistic that will inform a design decision on the **training window only**.

Profiling the full timeline and then choosing `δ` from it is leakage into your design choices. It will not show up in any metric, and it will not survive scrutiny if someone asks how you picked the window.

### Transaction level

Counts, distinct accounts, amount percentiles (1/5/25/50/75/95/99), payment-type and currency cardinality, time range and coverage gaps, missing values per column, duplicate IDs, illicit rate overall and per day.

### Account level

In-degree and out-degree **distributions** (report the distribution — these are heavy-tailed, and the mean is misleading), total inflow and outflow, distinct counterparty counts, activity frequency, inactivity gaps, hub identification, accounts in labelled patterns.

### Temporal

Transactions per minute / hour / day, burst detection and duration, inter-transaction gaps per account, observed traversal time for multi-hop labelled scenarios. **This last one directly determines a sensible `δ`.**

### Graph level

Node and edge counts, degree distributions, connected and strongly connected components, cycle statistics on a sample, density, approximate path-length distribution.

### Label structure

Not in the original draft, and it matters:

* How many distinct laundering patterns exist?
* How many transactions per pattern?
* Are patterns contiguous in time, or spread across the split boundary?
* Does any pattern span the train/test boundary? **If so, decide and document how to handle it** — a pattern split across the boundary leaks training signal into test.

### Deliverables

```text
reports/data_quality/data_quality_report.html
reports/data_quality/dataset_summary.json
reports/data_quality/label_structure.json
reports/figures/amount_distribution.png
reports/figures/degree_distribution.png
reports/figures/temporal_activity.png
```

---

## 9. Phase 3 — Validation and Quality Policy

### Required fields

Fail fast if absent: `transaction_id`, `timestamp`, `source_account`, `destination_account`, `amount`, `is_laundering`.

### Checks

| Check | Action |
|---|---|
| Missing source or destination | Reject, log |
| Missing or non-numeric amount | Reject, log |
| Negative amount | Reject, log |
| Zero amount | Flag and count; retain only if legitimate in this dataset |
| Unparseable timestamp | Reject, log |
| Timestamp outside declared span | Reject, log |
| Duplicate `transaction_id` | Keep first, log collision count |
| Self-transaction | Flag; exclude from graph edges, retain in ledger |
| Unsupported currency | Flag, normalise via mapping if one exists |
| `is_laundering` ∉ {0,1} | Reject, log |
| Out of chronological order | Sort; log that sorting occurred |

### Policy

**Never silently drop a record.** The quality report states records read, retained, rejected by reason, corrected by type, and the resulting change in illicit rate.

> **A shift in illicit rate after cleaning is a warning sign.** It suggests the cleaning rule correlates with the label — which means cleaning is doing classification. Investigate before proceeding.

---

## 10. Phase 4 — Target Definition

Transaction-level binary classification.

```text
is_laundering = 1 → transaction is part of a laundering pattern
is_laundering = 0 → benign
```

### Prediction record

```text
transaction_id
risk_score          # continuous [0,1], the primary output
predicted_label     # thresholded
threshold_used
experiment_id
model_version
seed
```

### Design notes

* **The score is the model output; the label is a policy decision.** Rank-based metrics (PR-AUC) evaluate the score. Precision, recall and F1 evaluate the threshold. Report both and never conflate them.
* Account-level and path-level prediction are **out of scope**. They require their own labels, splits and evaluation; bolting them on without those produces numbers that mean nothing.

---

## 11. Phase 5 — Leakage-Safe Temporal Splitting

The part most likely to silently invalidate everything downstream. Build it, and its tests, before any model.

### The invariant

> Scoring a transaction at time `T` may use only information that existed at or before `T`.

Random shuffling grants access to future network structure. It inflates offline metrics and produces a model that collapses in a live stream — and the failure is invisible unless you specifically test for it.

### Primary split

```text
Earliest 70%  →  Train
Next    15%   →  Validation
Latest  15%   →  Test
```

Split on transaction **time**, not row index. Print and record the actual boundary timestamps. Adjust percentages only after inspecting the temporal distribution, and only before any model comparison begins.

### Handling patterns that span a boundary

Decide once, document, apply everywhere. Options, in order of preference:

1. **Purge** — drop transactions within a buffer around each boundary, sized to the longest observed pattern duration. Cleanest; costs data.
2. **Assign by pattern start** — the whole pattern goes to whichever split contains its first transaction. Preserves patterns; slightly blurs the boundary.
3. **Hard cut** — split purely on transaction time, accepting truncated patterns in test. Simplest; makes some test positives undetectable by construction.

Whichever you choose, report the count of affected patterns.

### Hard rules

* No shuffling across time.
* No historical feature computed from future transactions.
* No global graph statistic over the full dataset.
* No feature derived from any label.
* Scalers and encoders fitted on training rows only.
* Class balancing applied to the training partition only.
* Thresholds selected on validation only.
* **The test set is touched once.** If you look at test results and then change the model, say so in the report.

### Additional evaluation splits

**A. Standard temporal** — the headline. Measures future-like performance.

**B. Unseen-pattern** — train on a subset of `pattern_type` values, test on held-out ones. Distinguishes generalisation to novel structure from memorisation of the generator's templates. Requires `pattern_type` to exist; if it does not, say so and drop this split.

**C. Hard-negative** — select structurally complex but benign behaviour from the data: high-fan-out accounts with regular cadence, high-volume hubs, dense but legitimate cycles. Measures whether the model separates suspicious topology from legitimate complexity. **This split predicts real-world false-positive pain better than anything else in the framework.**

### Leakage test suite

These run in CI and are treated as first-class tests, not assertions buried in a notebook.

| Test | Passes when |
|---|---|
| `test_split_boundaries_ordered` | max(train.ts) < min(val.ts) < max(val.ts) < min(test.ts) |
| `test_extractor_label_blind` | No extractor can access a forbidden column |
| `test_future_edge_invariance` | Extractor output for tx at `T` is byte-identical whether or not edges after `T` exist in the graph |
| `test_encoder_fit_scope` | Encoders and scalers record training-only fit indices |
| `test_threshold_source` | Threshold provenance metadata says `validation` |
| `test_label_shuffle_collapse` | Training on shuffled labels yields PR-AUC ≈ base rate |
| `test_deterministic_split` | Same config and data produce identical split boundaries |

The `test_future_edge_invariance` test is the strongest one available. Construct a graph containing future edges, extract features for an earlier transaction, and assert equality against extraction from a truncated graph. If they differ, you have leakage — and you have found it in seconds rather than in review.

### The deliberate leaky control

Run one intentionally-leaky configuration: random shuffle split, global graph statistics, encoders fitted on everything. Record its PR-AUC in the registry as `E_LEAK`.

Its purpose is evidentiary. A report that shows `E_LEAK` at, say, 0.94 and the honest `E2` at 0.61 demonstrates that the pipeline is doing the right thing far more convincingly than a paragraph asserting it does.

---

## 12. Phase 6 — Streaming Transaction Graph

### Graph model

```text
Account     = Node
Transaction = Directed edge
```

```text
A ──₹10,00,000──▶ B ──₹9,80,000──▶ C ──₹9,50,000──▶ D
```

Three ordinary-looking edges. One layering path with 95% value retention.

### Processing order — fix this explicitly

```text
Transaction arrives at time T
       ↓
Tombstone edges older than (T − δ)
       ↓
Extract features from the active window      ← new edge NOT yet present
       ↓
Emit feature row
       ↓
Insert the new edge
       ↓
Next transaction
```

**The new edge is inserted after its own features are extracted.** The alternative — insert first — means every transaction contributes to its own fan-out count, degree and vertex statistics. That is not leakage in the temporal sense, but it is a self-reference that inflates structural features on exactly the transactions you care about.

Whichever convention you adopt, apply it identically across E0–E7 and state it in the report. Inconsistency here silently invalidates every ablation comparison.

### Sliding window

For edge `e_uv` at `t_uv` with look-back `δ`, the active edge set is:

```text
TW = [ t_uv − δ , t_uv )
```

Half-open at the right end, consistent with the insertion order above.

`δ` is a frozen hyperparameter chosen from the §8 traversal-time analysis, not guessed. Multi-resolution windows are a distinct experiment (§17.E), not a silent default.

### Memory management: tombstoned eviction

Deleting expired edges eagerly on every insertion triggers cascading reallocation and stalls the extraction thread.

```text
Insert:   mark expired edges as tombstoned (O(1) flag write)
Read:     extraction skips tombstoned entries
Sweep:    background pass compacts adjacency lists, reclaims memory
```

Measure and report:

* Tombstone ratio over time (tombstoned / total edges)
* Sweep frequency and pause duration distribution
* Peak RSS vs steady-state RSS
* Whether sweep pauses appear in the inference-latency p99

An unmeasured memory optimisation is not an optimisation. If sweep pauses show up in p99 latency, that is the finding.

### Representation

Start: Python dicts and adjacency lists; NetworkX for validation and figures only; pandas/Polars for tabular work; Parquet for intermediates.

Scale up only if profiling demands it: CSR-style compressed adjacency, incremental adjacency maps with tombstones, memory-mapped storage, chunked streaming.

**Do not start with the optimised version.** Build the simple one, profile it, then optimise the part that is actually slow.

---

## 13. Phase 7 — Feature Extraction

### 13.1 Transaction features (`tx_`)

| Feature | Description |
|---|---|
| `tx_amount` | Raw amount |
| `tx_amount_log` | log1p(amount) |
| `tx_hour` | Hour of day |
| `tx_day_of_week` | Day of week |
| `tx_payment_type` | Encoded mechanism |
| `tx_currency` | Encoded currency |
| `tx_src_count` | Source's prior transaction count |
| `tx_dst_count` | Destination's prior transaction count |
| `tx_src_inflow` | Source's cumulative prior inflow |
| `tx_src_outflow` | Source's cumulative prior outflow |
| `tx_dst_inflow` | Destination's cumulative prior inflow |
| `tx_counterparty_count` | Distinct prior counterparties |
| `tx_amount_deviation` | z-score vs the account's own prior amount distribution |
| `tx_velocity_1h` | Transactions by this account in the prior hour |
| `tx_velocity_24h` | Transactions in the prior 24 hours |

Every one computed from **prior** transactions only.

**Encoding note:** categorical encoders are fitted on training rows only. Unseen categories at validation or test time map to a reserved `UNKNOWN` bucket — not to a silently-added new code, and not to NaN.

### 13.2 Graph structural features (`gfp_`)

**Fan-in**
```text
gfp_in_account_count, gfp_in_tx_count,
gfp_in_amount_sum, gfp_in_amount_mean, gfp_in_amount_var
```

**Fan-out**
```text
gfp_out_account_count, gfp_out_tx_count,
gfp_out_amount_sum, gfp_out_amount_mean, gfp_out_amount_var
```

**Cycles** — `A → B → C → A`
```text
gfp_cycle_detected, gfp_cycle_length, gfp_cycle_count,
gfp_tx_in_cycle, gfp_shortest_cycle_length
```

**Scatter-gather**
```text
Source ─┬──▶ B ──┐
        ├──▶ C ──┼──▶ Target
        └──▶ D ──┘
```
```text
gfp_scatter_gather_detected, gfp_scatter_width,
gfp_gather_width, gfp_sg_path_count
```

**Vertex statistics** — incrementally maintained per account, inflow and outflow: mean, variance, skewness, min, max, median. Incremental maintenance is what makes this streaming rather than batch; recomputing full history per transaction is the difference between seconds and hours.

```text
gfp_src_inflow_mean,  gfp_src_inflow_var,  gfp_src_inflow_skew
gfp_src_outflow_mean, gfp_src_outflow_var, gfp_src_outflow_skew
gfp_dst_inflow_mean,  gfp_dst_inflow_var,  gfp_dst_inflow_skew
gfp_dst_outflow_mean, gfp_dst_outflow_var, gfp_dst_outflow_skew
```

**Degree and neighbourhood**
```text
gfp_src_in_degree, gfp_src_out_degree,
gfp_dst_in_degree, gfp_dst_out_degree,
gfp_src_neighbour_count, gfp_dst_neighbour_count,
gfp_shared_neighbour_count
```

### 13.3 Feature table contract

One row per transaction, joined on `transaction_id`. Column names, order and dtypes are frozen and asserted at both training and inference.

```python
FEATURE_SCHEMA = {
    "tx_amount": "float64",
    "tx_amount_log": "float64",
    ...
}

def assert_schema(df):
    assert list(df.columns) == list(FEATURE_SCHEMA), "feature drift"
    assert df.dtypes.to_dict() == FEATURE_SCHEMA, "dtype drift"
```

A silent column reorder between training and inference is one of the most expensive bugs in this class of system, and it produces plausible-looking wrong answers rather than a crash.

### 13.4 Missing-value policy

XGBoost handles NaN natively, but "handles" is not "should receive". Decide per feature and document:

| Situation | Policy |
|---|---|
| Account has no prior history | NaN — genuinely unknown, let the model learn the split |
| No cycle exists | `gfp_cycle_length = 0`, `gfp_cycle_detected = 0` — a real zero, not missing |
| Window contains no edges | Structural zeros, not NaN |
| Division by zero in a ratio | NaN with a companion `_defined` boolean flag |

Conflating "no history" with "zero activity" is a subtle modelling error: the first is unknown, the second is information.

---

## 14. Phase 8 — Baseline Models

### E0 — Rule-based control

Legacy monitoring simulation:

```python
if tx_velocity_1h(source) > V:
    flag
if tx_amount_deviation > K:
    flag
if outflow_1h(source) / inflow_1h(source) > R:
    flag
if gfp_out_account_count > F:
    flag
```

**Tune the thresholds on validation**, exactly as you would a model. A deliberately badly-tuned rule baseline is not a control, it is a straw man — and reviewers notice.

Record: alert count, precision, recall, F1, FP/1k, processing time.

E0 is expected to be interpretable and to alert at an unsustainable rate. That tension is the argument for everything that follows.

### E1 — Transaction-only XGBoost

`tx_` features only. Answers: how far does tabular learning go with zero network topology?

### E2 — Graph-feature XGBoost

`tx_` + `gfp_` features. The primary research baseline.

```text
Transactions → CTDG → GFP extraction → join with tx_ features → XGBoost
```

Record the exact extractor configuration — window `δ`, pattern set, maximum pattern size — in the registry. If you re-implement rather than integrate, say so plainly and validate against hand-computed small graphs (§27).

### 14.1 Sanity baselines — run these before trusting anything

Not in the original plan, and they catch more problems than any single other check.

| Baseline | Expected result | Interpretation if violated |
|---|---|---|
| Random scores | PR-AUC ≈ base rate (≈0.001) | Metric implementation is wrong |
| Constant score | PR-AUC = base rate | Metric implementation is wrong |
| Shuffled training labels | PR-AUC ≈ base rate | **Leakage** — the model found signal in shuffled labels |
| `tx_amount` alone | Some lift above base rate | If this matches E2, graph features add nothing |
| E0 rules | Above base rate, poor precision | If E1 loses to E0, the ML pipeline is broken |

The shuffled-label test is the single highest-value check in this document. If a model trained on randomly permuted labels achieves meaningful PR-AUC, something in your pipeline is leaking, and every downstream result is void.

### 14.2 Why gradient boosting rather than a GNN

Reported comparisons place standard GIN architectures far below GFP + XGBoost on AML-HI Small, with graph transformers scoring higher still at a throughput cost that undermines streaming. **[Verify against the primary papers before citing; do not present these as your measurements.]**

The reasoning stands independently:

* Extreme minority-class imbalance favours boosted trees on dense engineered features.
* Continuous-time dynamic GNNs need memory modules that add latency on the critical path.
* Tree ensembles integrate cleanly with SHAP for the interpretation work in §19.

Treat these as hypotheses. If a GNN wins on your data, report that — it is a more interesting result than confirmation.

---

## 15. Phase 9 — Training Protocol

Fixed for every experiment. Deviations get a new experiment ID.

### 15.1 Class imbalance

At ~0.1% positives, a naive fit predicts the majority class everywhere.

**Use:** `scale_pos_weight = n_negative / n_positive` in XGBoost. It is principled, costs nothing, and does not fabricate data.

**Do not use SMOTE or any synthetic oversampling.** Two independent reasons:

1. Interpolating between graph-derived feature vectors produces feature combinations corresponding to *no transaction that ever existed in the graph* — a synthetic point with a fan-out of 7.3 and a cycle length of 2.6 is meaningless.
2. Synthetic points ignore temporal ordering, reintroducing exactly the leakage §11 works to eliminate.

**Optional comparison:** random undersampling of the majority class, as a documented alternative run. Report both if you try it. Never apply either to validation or test.

### 15.2 Hyperparameter search

**Do not use k-fold cross-validation.** Standard k-fold shuffles across time and reintroduces leakage.

Use **rolling-origin (expanding-window) validation inside the training period only**:

```text
Training period ───────────────────────────────────▶

Fold 1:  [====train====][val]
Fold 2:  [======train======][val]
Fold 3:  [========train========][val]
Fold 4:  [==========train==========][val]

                                          │
   held-out validation block (§11) ────────┘  ← untouched by the search
                                             test split ← untouched entirely
```

The dedicated validation block is reserved for threshold selection and model comparison. Using it for hyperparameter search too would make it a second training set.

**Search space** (Bayesian or randomised, fixed budget, recorded):

```text
max_depth            4 – 10
learning_rate        0.01 – 0.3   (log scale)
n_estimators         100 – 2000   (with early stopping)
subsample            0.6 – 1.0
colsample_bytree     0.6 – 1.0
min_child_weight     1 – 20
gamma                0 – 5
reg_lambda           0.1 – 10     (log scale)
scale_pos_weight     fixed by the imbalance ratio
```

Selection objective: **PR-AUC on the rolling-origin folds**, averaged. Not accuracy, not ROC-AUC, not log-loss.

**Fairness rule:** every experiment E1–E7 gets the same search budget. Tuning E7 for 200 trials and E2 for 20 makes the ablation meaningless — you would be measuring search effort, not features.

### 15.3 Probability calibration

PR-AUC is rank-based and indifferent to calibration. Thresholds are not.

After training, fit isotonic regression (or Platt scaling for small positive counts) on the **validation** split. Report reliability curves and Brier score before and after.

This matters because an uncalibrated score of 0.9 does not mean a 90% chance of laundering, and any threshold policy expressed in probability terms is meaningless without it.

### 15.4 Threshold selection

Select on validation, using a fixed alert budget rather than an arbitrary cutoff:

```text
θ = the score at the (100 − b)th percentile of validation scores,
    where b = alert budget as a percentage of transactions
```

Report at **b ∈ {0.1%, 0.5%, 1.0%}**. Budget-based thresholds are how detection systems are actually operated: an investigations team has fixed capacity, and the honest question is "how much laundering do we catch at the volume we can review".

Record the threshold, the budget, and the provenance (`validation`) in every registry entry.

### 15.5 Seeds and repetition

Three seeds per configuration: `[42, 1337, 2718]`. Report mean and standard deviation for every metric.

With a few thousand positives in the test set, seed-to-seed variance can exceed the effect size you are trying to measure. Single-seed results are not evidence.

---

## 16. Phase 10 — Evaluation Framework

At 0.1% positives, **accuracy is meaningless** — predicting "benign" always scores 99.9%. It never appears as a headline.

### 16.1 Ranking metrics

* **PR-AUC** — the headline. Robust under extreme imbalance.
* **Average Precision** — report alongside; interpolation differences between implementations are a known source of confusion.
* **ROC-AUC** — report for literature comparability only, with an explicit note that it is optimistic here.

### 16.2 Threshold metrics

At each alert budget b ∈ {0.1%, 0.5%, 1.0%}:

* Precision, recall, minority F1
* Confusion matrix
* Alerts generated
* False positives per 1,000 transactions

### 16.3 Detection-structure metrics

Beyond per-transaction scoring:

* **Per-typology recall** — fan-in, fan-out, cycle, scatter-gather separately. An aggregate F1 hides that the model catches cycles and misses scatter-gather entirely.
* **Pattern-level detection** — fraction of labelled patterns where ≥1 constituent transaction is flagged. This is closer to what matters operationally than per-transaction recall.
* **Pattern coverage** — of detected patterns, what fraction of constituent hops were recovered?

### 16.4 Stability metrics

Not in the original plan, and essential for the validation gates in §26:

* **Seed stability** — standard deviation of PR-AUC across the three seeds
* **Temporal stability** — split the test period into 5 sub-windows, report PR-AUC per window. A monotone decline indicates drift and means the model has a shelf life.
* **Feature-distribution drift** — PSI or KS statistic per feature between train and test. Large drift on a high-importance feature is a red flag for the model's durability.
* **Bootstrap confidence intervals** — 1000 resamples of the test set, 95% CI on PR-AUC.

### 16.5 Cost metrics

Measured per component. A single end-to-end number hides where the cost actually sits.

| Component | Measurement |
|---|---|
| Data loading | seconds |
| Validation | seconds |
| Graph construction | seconds, edges/s |
| Feature extraction | ms/transaction, transactions/s |
| Inference | ms/transaction, transactions/s |
| End-to-end | wall-clock seconds |
| Memory | peak RSS, steady-state RSS |
| Intermediates | on-disk bytes |

**Report latency as a distribution — p50, p95, p99 — not a mean.** In any streaming design, the tail is what breaks.

---

## 17. Phase 11 — Error Analysis and Feature Design

**This phase gates everything in §18.** Features designed before it are guesses.

### 17.1 Categorise every test-set error

| Transaction | Actual | Pred | Typology | Cause | Candidate remedy |
|---|---:|---:|---|---|---|
| TX001 | 0 | 1 | High fan-out hub | Legitimate high-degree account | Behavioural novelty (§18.C) |
| TX002 | 1 | 0 | Layering | Pattern duration > δ | Multi-resolution windows (§18.E) |
| TX003 | 0 | 1 | Regular fan-in | Periodic settlement cadence | Periodicity feature |
| TX004 | 1 | 0 | Pass-through | Structure seen, timing missed | Temporal flow motifs (§18.A) |
| TX005 | 1 | 0 | Scatter-gather | Intermediaries outside window | Adaptive expansion (§18.D) |

Count every category. Rank by volume. **Attack the largest bucket first.**

### 17.2 The gate

Before implementing any feature family in §18, write down:

1. Which error category it targets
2. How many test errors fall in that category
3. The mechanism by which the feature would fix them
4. What the ablation will show if it works

If you cannot fill in all four, do not build the feature. This single rule prevents the most common failure of research plans — building the interesting thing rather than the needed thing.

### 17.3 Slice analysis

Report PR-AUC separately by:

* Amount decile
* Time of day and day of week
* Source-account degree quartile
* Path position (first hop, middle hop, final hop of a labelled pattern)
* Pattern type

Aggregate metrics conceal systematic blind spots. If the model is strong on first hops and blind on middle hops, that is the finding, and it is invisible in a single PR-AUC number.

---

## 18. Phase 12 — Feature Research Directions

One at a time. Each becomes one ablation row. Each must pass the §17.2 gate.

### A. Temporal flow motifs (`tflow_`)

Targets: timing-dependent false negatives.

```text
tflow_mean_inter_hop_seconds
tflow_median_inter_hop_seconds
tflow_path_duration_seconds
tflow_burst_count_1h
tflow_burst_duration_mean
tflow_time_decayed_path_activity
tflow_motif_order_score        # did fan-out precede fan-in?
```

```text
A → B at 10:00
B → C at 10:02
C → D at 10:04
```
```text
tflow_mean_inter_hop_seconds = 120
tflow_path_duration_seconds  = 240
tflow_three_hop_within_10min = 1
```

Structure says a path exists; timing says how the money moved. Two topologically identical paths — one completed in four minutes, one over four weeks — are very different risks.

### B. Value-flow features (`vflow_`)

Targets: pass-through and mule typologies.

```text
vflow_retention_ratio           # forwarded / received
vflow_inflow_outflow_ratio
vflow_dissipation               # value lost across hops
vflow_split_score               # amount fragmentation
vflow_aggregation_score         # amount recombination
vflow_conservation_deviation
vflow_source_to_final_ratio
```

```text
A → B: ₹10,00,000
B → C:  ₹9,80,000
C → D:  ₹9,50,000

vflow_retention_ratio = 0.95
vflow_dissipation     = 0.05
```

An account forwarding 98% of an inflow within minutes behaves nothing like one drawing funds down gradually — despite identical topology. Pure structural features cannot see this distinction at all.

### C. Behavioural novelty (`nov_`)

Targets: legitimate-hub false positives, the usual largest error bucket.

```text
nov_new_counterparty_rate
nov_new_payment_type
nov_amount_distribution_shift   # KS vs the account's own baseline
nov_degree_jump                 # vs the account's own rolling degree
nov_activity_burst_vs_baseline
nov_rare_pattern_score
```

> An account that normally pays two suppliers and suddenly pays 25 new accounts is anomalous. A payroll account paying 400 accounts every month is not — even though its raw fan-out is 16× higher.

This reframes the question from "does this pattern exist" to "is this unusual *for this account*", which is the core defence against high-degree-hub false positives.

### D. Risk-adaptive graph expansion

Targets: throughput, not accuracy.

```text
Incoming transaction
        ↓
One-hop analysis
        ↓
    risk < θ₁ ?
    ┌────┴────┐
   Yes        No
    │         │
   Stop   Expand to 2-hop
              ↓
          risk < θ₂ ?
          ┌───┴───┐
         Yes      No
          │       │
         Stop  Expand to 3-hop
```

**Measure the selection bias explicitly.** A suspicious transaction whose one-hop neighbourhood looks benign is never expanded, and its deep evidence is never gathered.

Required measurement: **recall on illicit transactions that were never expanded**. Report average cost saving *and* recall lost. If recall loss is non-trivial, the honest conclusion is that adaptive expansion is a throughput lever, not an accuracy improvement — and it belongs in a deployment discussion, not in E7.

### E. Multi-resolution temporal windows

Targets: the tension where one `δ` cannot capture both rapid smurfing and slow layering.

```text
5 min · 1 hour · 6 hours · 1 day · 7 days
```

Per resolution: transaction count, amount sum, counterparty count, fan-in, fan-out, cycle participation, flow velocity.

Cost scales roughly linearly with the number of resolutions. Measure it, and consider whether three well-chosen windows beat five.

### F. Fuzzy multi-stage pattern decomposition

Targets: evasion via structural fuzziness (varying hop counts) and temporal fuzziness (delayed integration).

Exact subgraph matching is brittle, and enumerating every permutation of a fuzzy pattern blows up combinatorially. The alternative is decomposing a scheme into independent logical stages connected by set operations over active neighbourhoods, rather than searching for one rigid subgraph.

**Realistic scope:** implement the decomposition idea in Python and measure whether it recovers fuzzy patterns that exact matching misses. Published work in this direction compiles stage logic into optimised native kernels — that is not a deliverable here, and the plan does not pretend otherwise. **[Verify the source before citing it.]**

### Dropped from the previous plan

Heterogeneous entity features required entity-type metadata the dataset does not carry (§3.4). Removed rather than deferred.

---

## 19. Phase 13 — Model Interpretation

SHAP on XGBoost. In this scope its purpose is diagnostic, not presentational.

### 19.1 Global interpretation

* Mean absolute SHAP per feature, by family (`tx_`, `gfp_`, `tflow_`, `vflow_`, `nov_`)
* Family-level contribution — does the graph family actually carry weight, or is E2's gain coming from one incidentally-correlated feature?
* Interaction values for the top features
* Comparison of SHAP importance against gain-based importance; large disagreement warrants investigation

### 19.2 Leakage detection through interpretation

**A single feature with implausibly dominant importance is a leakage signal.** If one feature carries 70% of the model's explanatory weight, ask how it could be correlated with the label by construction before celebrating.

Concrete checks:

* Does any feature have near-perfect rank correlation with `is_laundering` on its own?
* Does removing the top feature collapse PR-AUC to the base rate?
* Is any feature's value derivable from a pattern annotation?

### 19.3 Local interpretation for error analysis

For a sample of false positives and false negatives from each §17.1 category, record the SHAP breakdown. This tells you *why* the model made each error, which is what turns an error count into a feature design.

```text
TX001 — false positive, high-fan-out hub
  gfp_out_account_count      +0.31
  gfp_out_amount_sum         +0.19
  tx_velocity_24h            +0.11
  nov_new_counterparty_rate  −0.04   ← present but outweighed
```

That last line is actionable: the novelty feature is pointing the right way but is too weak. Read: needs a stronger baseline window, not a new feature.

### 19.4 Stability of interpretation

Compare SHAP rankings across the three seeds. If the top-10 features differ substantially between seeds, the model is not learning a stable structure, and any narrative built on feature importance is unreliable.

---

## 20. Phase 14 — Computational Profiling

Measure on frozen hardware, before optimising anything.

```text
Data loading            = ____ s
Validation              = ____ s
Graph construction      = ____ s      ( ____ edges/s )
Feature extraction      = ____ s      ( ____ tx/s )
  ├─ tx_   family       = ____ %
  ├─ gfp_  family       = ____ %
  ├─ tflow_ family      = ____ %
  └─ vflow_ family      = ____ %
Model training          = ____ s
Model inference         = ____ s      ( ____ tx/s )
Total                   = ____ s
Peak RSS                = ____ MB
Steady-state RSS        = ____ MB
Tombstone ratio (mean)  = ____
Sweep pause p99         = ____ ms
Latency p50/p95/p99     = ____ / ____ / ____ ms
```

The per-family breakdown of extraction cost is what makes the accuracy-versus-cost trade-off in §21 quantitative rather than rhetorical. Without it, "value-flow features improved PR-AUC by 0.03" has no denominator.

---

## 21. Phase 15 — Ablation Studies

```text
E0   Rule baseline
E1   tx_ only
E2   tx_ + gfp_                          ← primary baseline
E3   E2 + tflow_
E4   E2 + vflow_
E5   E2 + nov_
E6   E2 + adaptive expansion
E7   Selected combination
```

Plus `E_LEAK` (deliberate leaky control, §11) and the §14.1 sanity baselines.

### Rules

* Dataset, split, model family, search budget and threshold procedure all fixed.
* One feature family added per run.
* Three seeds per configuration.
* Every run logged, **including runs that made things worse** — negative results are the point of an ablation.
* Benefit and cost reported for every family.

### The inclusion criterion

A family enters E7 only if:

```text
ΔPR-AUC > 2 × (seed-to-seed standard deviation)
        AND
the 95% bootstrap CI excludes zero
        AND
the extraction cost is justified and stated
```

"It felt like it should help" is not a criterion. Neither is a 0.004 improvement on a single seed.

### Statistical honesty

With ~0.1% positives, the test set may hold only a few thousand positives. A one-point PR-AUC difference is frequently noise.

* Bootstrap CIs on every headline number.
* Report seed spread alongside every mean.
* **Do not declare a winner on a difference smaller than the seed variance.** Report it as inconclusive — which is a legitimate finding.

---

## 22. Phase 16 — Results Table

| Exp | Features | PR-AUC (mean ± sd) | 95% CI | P@0.5% | R@0.5% | F1 | FP/1k | Extract tx/s | p95 ms | Peak MB |
|---|---|---|---|---|---|---|---|---|---|---|
| E0 | rules | — | — | — | — | — | — | — | — | — |
| E1 | tx_ | — | — | — | — | — | — | — | — | — |
| E2 | tx_+gfp_ | — | — | — | — | — | — | — | — | — |
| E3 | +tflow_ | — | — | — | — | — | — | — | — | — |
| E4 | +vflow_ | — | — | — | — | — | — | — | — | — |
| E5 | +nov_ | — | — | — | — | — | — | — | — | — |
| E6 | +adaptive | — | — | — | — | — | — | — | — | — |
| E7 | final | — | — | — | — | — | — | — | — | — |

Reference rows, reported separately so nobody mistakes them for results:

| Reference | PR-AUC | Purpose |
|---|---|---|
| Random scores | — | Metric sanity |
| Shuffled labels | — | Leakage check |
| `tx_amount` alone | — | Trivial-feature floor |
| E_LEAK | — | Demonstrates what leakage would have produced |

**Do not fill any cell until the run exists.** Placeholder numbers survive into final reports with alarming regularity.

---

## 23. Phase 17 — Experiment Registry

Every run writes a record. Failed and worse-performing runs included.

```json
{
  "experiment_id": "E3",
  "run_id": "E3_seed42_20260101_142233",
  "seed": 42,

  "dataset": "AML_HI_Small",
  "dataset_sha256": "…",
  "split": "temporal_70_15_15",
  "split_boundaries": {"train_end": "…", "val_end": "…"},
  "boundary_policy": "purge_24h",

  "feature_families": ["tx", "gfp", "tflow"],
  "feature_count": 0,
  "feature_schema_hash": "…",
  "window_delta": "6h",
  "insertion_order": "extract_then_insert",

  "model": "XGBoost",
  "model_params": {},
  "search_budget_trials": 0,
  "search_protocol": "rolling_origin_4fold",
  "calibration": "isotonic",

  "threshold": 0.0,
  "threshold_budget_pct": 0.5,
  "threshold_source": "validation",

  "pr_auc": 0.0,
  "pr_auc_ci95": [0.0, 0.0],
  "average_precision": 0.0,
  "roc_auc": 0.0,
  "precision": 0.0,
  "recall": 0.0,
  "f1_minority": 0.0,
  "fp_per_1k": 0.0,
  "recall_by_typology": {},
  "pattern_level_recall": 0.0,
  "temporal_stability": [],

  "extraction_tx_per_sec": 0.0,
  "extraction_cost_by_family": {},
  "inference_p50_ms": 0.0,
  "inference_p95_ms": 0.0,
  "inference_p99_ms": 0.0,
  "peak_memory_mb": 0.0,

  "python_version": "…",
  "library_versions": {},
  "hardware": "…",
  "git_commit": "…",
  "leakage_tests_passed": true,
  "notes": ""
}
```

`leakage_tests_passed` is mandatory. A run whose leakage suite did not pass is not a result, and recording it as `false` rather than omitting it keeps the record honest.

Tooling: JSON per run plus an aggregate `experiments/results.csv`. Move to MLflow past roughly twenty runs. Git commit hash in every entry. DVC only if raw data cannot be committed.

---

## 24. Phase 18 — Cross-Dataset Validation

Run **once**, after E7 is frozen. This is not a tuning opportunity.

```text
              E7, frozen
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
  AML LI Small  AML HI Med   ETH Phishing
  (lower rate)  (scale)      (real, other domain)
```

### Protocol per dataset

1. Map the source schema to the canonical schema (§6). Record the mapping.
2. Rebuild features with the **same code and same `δ`**.
3. Handle absent features explicitly — reserved-missing, never silently zero.
4. Score with the frozen model. No retraining, no re-tuning, no threshold adjustment.
5. Report every metric from §16, alongside the primary-dataset values.
6. Report feature-distribution drift (PSI) between primary and target.

### What to expect

| Target | Expectation |
|---|---|
| AML LI Small | Moderate degradation — lower base rate compresses precision |
| AML HI Medium | Similar quality; the finding here is throughput and memory scaling |
| ETH Phishing | **Substantial degradation.** Different domain, different topology, different economics |

**Report the degradation plainly.** A cross-dataset result showing no drop almost always indicates an evaluation bug — most often a target-leak through a schema-mapping shortcut — not a triumph. Investigate it as a defect before writing it up as a success.

---

## 25. Phase 19 — Final Model Selection

The final architecture is an **output** of the ablations, not an assumption written at the start.

### Selection procedure

1. Rank E3–E6 by ΔPR-AUC over E2, with CIs.
2. Retain only families passing the §21 inclusion criterion.
3. Build candidate E7 configurations from the retained families.
4. Tune each candidate with the same search budget used everywhere else.
5. Select on **validation**, not test.
6. Evaluate the single selected E7 on test, once.
7. Calibrate on validation, report reliability before and after.
8. Freeze.

### If nothing passes

If no feature family passes the inclusion criterion, **E2 is your final model**, and the finding is:

> On this dataset, at this scale, additional temporal/value-flow/novelty features did not measurably improve on the graph-feature baseline.

That is a legitimate, publishable result — and considerably more useful to the field than a marginal improvement obtained by relaxing the criterion after seeing the numbers. Do not move the goalposts to manufacture a positive.

---

## 26. Phase 20 — Model Validation Gates

The terminus of this plan. **Define these before running E7.** A gate chosen after seeing results is not a gate.

### 26.1 Correctness gates — all must pass

| # | Gate | Pass condition |
|---|---|---|
| C1 | Leakage suite | All §11 tests pass |
| C2 | Shuffled-label sanity | PR-AUC within 2× base rate |
| C3 | Random-score sanity | PR-AUC ≈ base rate |
| C4 | Split integrity | Boundary timestamps strictly ordered; recorded |
| C5 | Schema integrity | Training and inference feature schema hashes identical |
| C6 | Reproducibility | Clean checkout + one command reproduces headline PR-AUC to 3 decimals |
| C7 | Determinism | Same seed, same data, identical predictions |
| C8 | Interpretation sanity | No single feature carries >50% of mean absolute SHAP |

**A failure on any correctness gate voids the result.** These are not negotiable, and no amount of good performance compensates for failing one.

### 26.2 Performance gates — targets, set in advance

| # | Gate | Target | Rationale |
|---|---|---|---|
| P1 | E2 beats E1 | ΔPR-AUC > 2σ | Graph features contribute at all |
| P2 | E1 beats E0 | ΔPR-AUC > 2σ | ML beats rules |
| P3 | E7 beats E2 | ΔPR-AUC > 2σ, or documented as inconclusive | Research contribution is real |
| P4 | Recall @ 1% budget | Stated in advance, e.g. > 0.60 | Operationally meaningful |
| P5 | Per-typology recall | No typology at zero recall | No total blind spots |
| P6 | Seed stability | PR-AUC sd < 0.02 | Result is stable |
| P7 | Temporal stability | No monotone decline across test sub-windows | No unmanaged drift |
| P8 | Extraction throughput | Stated in advance, e.g. > 1000 tx/s | Streaming remains plausible |
| P9 | Peak memory | Within the frozen hardware budget | Fits the stated envelope |

A missed performance gate is a **finding to report**, not a failure to hide. P3 in particular may legitimately come out inconclusive.

### 26.3 Robustness checks

Run on the frozen E7:

* **Feature-ablation sensitivity** — drop each top-10 feature individually, measure PR-AUC change. A model collapsing on one feature is fragile.
* **Window sensitivity** — re-run with `δ/2` and `2δ`. Report the curve. A model that only works at one exact window is overfitted to it.
* **Threshold sensitivity** — precision and recall across the budget range, not just at the chosen point.
* **Noise injection** — perturb amounts by ±1%, ±5%. Predictions should not swing wildly.
* **Temporal sub-window performance** — PR-AUC across the five test sub-windows, reported individually.

### 26.4 The validated model package

The deliverable that closes this scope:

```text
models/flowguard_E7_v1/
├── model.json                  # serialised booster
├── calibrator.pkl              # isotonic calibrator fitted on validation
├── feature_schema.json         # names, order, dtypes, schema hash
├── encoders/                   # categorical encoders, training-fit only
├── config.yaml                 # full frozen experiment config, δ included
├── thresholds.json             # θ per alert budget, with provenance
├── metrics.json                # all §16 metrics with CIs
├── validation_report.md        # every gate in §26, pass/fail, with evidence
├── model_card.md               # §26.5
├── shap_summary.json           # global interpretation
└── PROVENANCE.json             # dataset hash, git commit, library versions, hardware
```

Anything downstream of this — serving, dashboards, case management — consumes this directory and re-derives nothing. That clean boundary is what makes the narrowed scope safe.

### 26.5 Model card contents

* Intended use, and explicitly stated non-uses
* Training data: dataset, version, hash, date range, illicit rate
* Feature families included, and which were **evaluated and dropped**, with the measured reason
* Training protocol: search, imbalance handling, calibration
* Performance: all metrics with CIs, per typology, per slice
* Operating thresholds and their alert budgets
* Known failure modes, taken from §17.1
* Datasets **not** validated on
* Performance envelope: throughput and memory at tested scale
* Drift indicators to monitor, and a recommended revalidation trigger

The "evaluated and dropped" line is the one most often omitted and most often useful. A future reader needs to know that value-flow features were tried and did not help, so they do not spend three weeks retrying them.

---

## 27. Testing Strategy

### Unit — data

Required columns present with correct dtypes; timestamps parse with consistent timezone; amounts numeric and non-negative; `transaction_id` unique; `is_laundering` ∈ {0,1}.

### Unit — graph

One edge per transaction; direction matches source → destination; temporal ordering preserved under insertion; self-loops excluded from edges, retained in ledger; tombstoned edges invisible to extraction; sweep preserves all non-tombstoned edges; window boundary is half-open as specified.

### Unit — features, on hand-computed graphs

```text
A → B, A → C, A → D
```
```text
gfp_src_out_degree(A)    == 3
gfp_out_account_count(A) == 3
gfp_cycle_detected(A)    == 0
```

```text
A → B → C → A
```
```text
gfp_cycle_detected        == 1
gfp_shortest_cycle_length == 3
```

```text
A →(1000)→ B →(980)→ C
```
```text
vflow_retention_ratio(B) == 0.98
```

Small graphs with hand-derived expected values are the only way to know a re-implementation is correct. Write these before the extractor.

### Leakage — first-class category

The seven tests in §11, run in CI on every commit. A failing leakage test blocks the merge.

### Unit — model

Feature schema identical at train and inference; reloaded model reproduces predictions exactly; missing features raise rather than silently impute; fixed seed reproduces identical metrics; calibrator is fitted on validation indices only.

### Integration

```text
raw → validate → canonical → split → graph → features → train → evaluate → registry
```

Run end-to-end on a 10,000-row sample in CI. It should complete in under a minute and catch schema and wiring breaks before they reach a full run.

### Reproducibility checklist

* [ ] Dependencies pinned in a lock file
* [ ] Configs committed
* [ ] Seeds recorded per run
* [ ] Dataset checksums recorded and verified at load
* [ ] Hyperparameters saved with the model
* [ ] Registry entry per run, with commit hash
* [ ] `make reproduce` regenerates the headline number from a clean checkout

---

## 28. Technology Stack

| Component | Tool |
|---|---|
| Language | Python |
| Data processing | pandas, or Polars if memory-bound |
| Storage | Parquet |
| Graph validation / figures | NetworkX |
| Graph runtime | Custom incremental adjacency with tombstones |
| Graph features | Snap ML Graph Feature Preprocessor if available; otherwise verified re-implementation |
| Model | XGBoost |
| Hyperparameter search | Optuna |
| Calibration | scikit-learn `IsotonicRegression` / `CalibratedClassifierCV` |
| Interpretation | SHAP (`TreeExplainer`) |
| Validation | Pandera or explicit validators |
| Registry | JSON + CSV, then MLflow |
| Profiling | `time.perf_counter`, `tracemalloc`, `memory_profiler`, `psutil` |
| Testing | Pytest |
| Environment | `venv` or Conda with lock file |
| Version control | Git; DVC only if raw data cannot be committed |

Deliberately absent: FastAPI, Streamlit, Docker, any serving framework. Out of scope.

---

## 29. Eight-Week Timeline

Two weeks shorter than the full-system plan, because the API and dashboard weeks are gone.

| Week | Focus | Deliverable |
|---|---|---|
| **1** | Dataset verification, licence, repo structure, immutable raw layer, metadata, loader, canonical schema | Raw layer + loader + dataset report |
| **2** | Validation, quality policy, EDA, label-structure analysis, δ selection from traversal times | Data-quality report + profiling notebooks |
| **3** | **Split module + full leakage test suite first**, then E0 rules, E1 tabular XGBoost, sanity baselines, E_LEAK | Leakage suite green; E0, E1, sanity baselines logged |
| **4** | CTDG: window, insertion order, tombstoned GC; degree/neighbourhood features; memory profiling | Graph module + memory profile + graph unit tests |
| **5** | GFP verification and integration, E2, training protocol (rolling-origin search, calibration, budget thresholds) | **E2 logged — the primary baseline** |
| **6** | Error analysis, slice analysis, SHAP interpretation, leakage-via-interpretation checks, full cost profiling | Error taxonomy + interpretation report + cost baseline |
| **7** | Feature families gated by week 6: E3, E4, E5, and E6 if time permits | E3–E6 logged with three seeds each |
| **8** | Ablation synthesis, E7 selection, cross-dataset validation, robustness checks, validation gates, model card | **Validated model package + final report** |

### Ordering constraints — not negotiable

* **Week 3 before week 5.** The split and its leakage tests exist before any graph model is evaluated. Retrofitting a split onto an evaluated model is how leaked results reach reports.
* **Week 6 before week 7.** Feature families are designed from measured errors, not from this document's list. The §17.2 gate enforces this.
* **Week 8 cross-dataset runs once.** After E7 is frozen.

### Buffer reality

Week 7 nominally holds four feature families with three seeds each. It will not all fit.

When week 6's error analysis names the two dominant failure categories, **build only the families that target them.** Two families executed properly — three seeds, full ablation, honest CIs — beat four families executed on one seed each. The second version produces no usable evidence.

---

## 30. Deliverables

### Code

Data loader and validator · canonical schema module · temporal split module with leakage suite · streaming CTDG with tombstoned GC · feature extractors per family · E0 rule baseline · XGBoost training with rolling-origin search and calibration · evaluation framework with stability and cost metrics · SHAP interpretation module · error-analysis tooling · experiment registry · test suite including the leakage category

### Artifacts

Validated model package (§26.4) · experiment registry with every run · frozen configs · dataset metadata with checksums

### Reports

Dataset analysis · data-quality report · GFP verification and implementation report · baseline comparison (E0–E2) · error taxonomy with counts · slice analysis · interpretation report · ablation study with CIs · accuracy-versus-cost analysis · cross-dataset validation · robustness checks · validation-gate report · model card · limitations and threats to validity · final technical report

---

## 31. Pipeline Flow

```text
                  ┌────────────────────┐
                  │ Dataset verified   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Immutable raw      │
                  │ + checksums        │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Canonical schema   │
                  │ + quality report   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Temporal split     │
                  │ + LEAKAGE SUITE    │
                  └─────────┬──────────┘
                            ▼
            ┌───────────────┴───────────────┐
            ▼                               ▼
  ┌────────────────────┐          ┌────────────────────┐
  │ tx_ features       │          │ Streaming CTDG     │
  └─────────┬──────────┘          └─────────┬──────────┘
            ▼                               ▼
  ┌────────────────────┐          ┌────────────────────┐
  │ E1: tabular XGB    │          │ gfp_ extraction    │
  └─────────┬──────────┘          └─────────┬──────────┘
            │                               ▼
            │                     ┌────────────────────┐
            │                     │ E2: graph XGB      │
            │                     └─────────┬──────────┘
            └───────────────┬───────────────┘
                            ▼
                  ┌────────────────────┐
                  │ Evaluation + cost  │
                  │ + sanity baselines │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ ERROR ANALYSIS     │
                  │ (feature gate)     │
                  └─────────┬──────────┘
                            ▼
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
    E3 tflow_           E4 vflow_            E5 nov_
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                  ┌────────────────────┐
                  │ E6 adaptive /      │
                  │ cost study         │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Ablation synthesis │
                  │ (CIs, 3 seeds)     │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ E7 selected        │
                  │ + calibrated       │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Cross-dataset      │
                  │ + robustness       │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ VALIDATION GATES   │
                  └─────────┬──────────┘
                            ▼
                  ┌────────────────────┐
                  │ Validated model    │
                  │ package  ── END    │
                  └────────────────────┘
```

---

## 32. First Milestone — M0

Not a feature. A reproducible baseline.

```text
✓ Dataset selected, licence checked, schema verified against §6
✓ Raw data immutable, checksums recorded
✓ Dataset metadata written
✓ Data-quality report generated, illicit-rate stability confirmed
✓ Canonical schema implemented and unit-tested
✓ Temporal split implemented WITH the full leakage suite passing
✓ E_LEAK control run recorded
✓ Sanity baselines recorded (random, shuffled-label, amount-only)
✓ E0 rules implemented, thresholds tuned on validation
✓ E1 tabular XGBoost trained, three seeds, logged
✓ Streaming CTDG built and unit-tested on hand-computed graphs
✓ GFP integrated or re-implementation validated
✓ E2 trained, three seeds, logged
✓ PR-AUC with CIs, precision/recall at three budgets, per-typology recall
✓ Cost profile: extraction tx/s, latency p50/p95/p99, peak RSS
✓ SHAP global interpretation, no single feature >50% importance
✓ Error taxonomy with counts per category
✓ Registry populated for E0, E1, E2, E_LEAK, sanity baselines
✓ `make reproduce` regenerates the headline PR-AUC from a clean checkout
```

Nothing from §18 begins until every line is ticked.

```bash
make reproduce
# → python -m flowguard.pipeline.run_baseline --config configs/experiment.yaml
```

### Immediate next actions

1. Download the candidate dataset; verify schema against §6 — column names, label semantics, timestamp format.
2. Confirm Graph Feature Preprocessor availability for your platform; record the version, or decide to re-implement.
3. Create the §5 repository structure.
4. Implement `data/schema.py`, `data/loader.py`, `data/validator.py`.
5. Implement `splits/temporal.py` **together with `splits/leakage_checks.py`**, before any model code exists.

Step 5 is the one that pays for itself. Every hour spent on the leakage suite before the first model is an hour that does not have to be spent re-running everything after discovering a leak in week 7.

---

## 33. Risks and Threats to Validity

| Risk | Impact | Mitigation |
|---|---|---|
| Subtle temporal leakage | Every result void | §11 leakage suite in CI; future-edge invariance test; shuffled-label check; E_LEAK contrast |
| Synthetic data unrepresentative | Results do not transfer | ETH Phishing cross-dataset; stated in limitations |
| Extreme imbalance → noisy comparisons | False conclusions from noise | Three seeds, bootstrap CIs, 2σ inclusion criterion |
| Patterns spanning split boundaries | Train signal in test | Explicit boundary policy (§11), affected-pattern count reported |
| GFP implementation mismatch | Baseline is not the literature's | Version recorded; described as GFP-inspired until confirmed; hand-computed validation |
| `δ` mis-set | Systematic blindness to slow layering | δ chosen from traversal-time analysis; sensitivity curve in §26.3 |
| Search budget asymmetry across experiments | Ablation measures tuning effort, not features | Fixed budget for every experiment |
| Adaptive-expansion selection bias | Hidden recall loss | Recall measured specifically on non-expanded illicit transactions |
| Ten-day dataset span | Long-horizon typologies undetectable | Stated as a hard limitation, not a model failing |
| Hardware variance | Incomparable timing | Frozen hardware; specs recorded; baselines re-run if hardware changes |
| Moving the goalposts after seeing results | Unsound conclusion | Gates defined before E7 runs (§26) |

### Explicit non-claims

* This pipeline does not determine that laundering occurred; it scores transactions.
* It has not been validated on real banking data.
* Thresholds are research values derived from alert budgets, not production settings.
* Cost figures apply to the tested hardware and scale only.
* No claim of novelty for graph analytics in AML.
* Typologies requiring customer context — dormant activation, profile mismatch — are out of scope and undetectable here by construction.

---

## 34. Handoff Contract

For whoever picks this up later. This section exists so the narrowed scope stays clean rather than becoming a gap.

### What a serving track receives

The §26.4 model package, plus the extraction code needed to reproduce features online:

| Consumer needs | Provided by |
|---|---|
| Model weights | `model.json` |
| Calibrator | `calibrator.pkl` |
| Exact feature schema | `feature_schema.json` + hash |
| Categorical encoders | `encoders/` |
| Window and insertion convention | `config.yaml` |
| Operating thresholds | `thresholds.json` |
| Expected performance | `metrics.json`, `model_card.md` |
| Known failure modes | `model_card.md` |
| Cost envelope | `metrics.json` cost block |
| Revalidation trigger | `model_card.md` |

### What is explicitly not provided

Serving code, latency guarantees under production load, case management, explanation UI, evidence packaging, monitoring infrastructure, drift alerting.

### The contract

> The feature extraction used at serving time must be **the same code path** used at training time. A reimplementation in another language or framework invalidates the validation in §26 and requires re-running the gates.

This is the most common way validated models degrade silently in production — a reimplemented feature pipeline that differs in some small edge case the model was never tested against.

---

## 35. References

Verify every entry before it appears in a report. Several are inherited unconfirmed.

**Graph features and AML modelling**

1. Graph Feature Preprocessor: real-time subgraph-based feature extraction — <https://arxiv.org/abs/2402.08593>
2. Graph Feature Preprocessor — Snap ML documentation — <https://snapml.readthedocs.io/>
3. Realistic synthetic financial transactions for anti-money laundering models — <https://arxiv.org/abs/2306.16424>
4. BlazingAML: high-throughput AML graph mining — **[verify arXiv ID and status]**
5. Extracting money-laundering transactions from quasi-temporal graphs (ExSTraQt) — **[verify arXiv ID and status]**

**Temporal graph systems**

6. TGLite: lightweight framework for continuous-time dynamic graphs — <https://charithmendis.com/assets/pdf/24-asplos-tglite.pdf>
7. UTG: toward a unified view of snapshot and event-based models — <https://arxiv.org/abs/2407.12269>

**Evaluation methodology**

8. Davis & Goadrich, *The relationship between Precision-Recall and ROC curves* — the standard justification for PR-AUC under imbalance
9. Standard references on probability calibration (Platt scaling, isotonic regression)
10. Rolling-origin / time-series cross-validation literature

**Regulatory background** (context only — no compliance deliverable in this scope)

11. RBI Master Direction on KYC / AML — <https://www.rbi.org.in/>
12. FIU-IND publications — <https://fiuindia.gov.in/files/Publication/Publication.html>
13. BIS Innovation Hub, Project Aurora — <https://www.bis.org/publ/othp66.pdf>

---

## 36. Change Log vs the Full-System Plan

### Removed — out of scope

FastAPI backend and endpoint design · Streamlit/React dashboard and all eight screens · investigator workflow · evidence object and case export · STR narrative generation · LLM narrative layer · typology/risk-scoring product layer · Isolation Forest ensemble layer · synthetic bank-context data generation · dormant-activation and profile-mismatch typologies · heterogeneous entity features · security and privacy architecture · non-functional serving targets · IBM integration · demo script · scope-control tiers · FHE future work · Docker and deployment · the two application weeks in the timeline

### Added — depth the narrowed scope makes room for

| Addition | Why it matters |
|---|---|
| Sanity baselines: random, constant, shuffled-label, single-feature (§14.1) | Shuffled-label is the highest-value leakage check available, and was absent |
| Rolling-origin hyperparameter search (§15.2) | k-fold CV shuffles across time and reintroduces leakage; the previous plan never specified a search protocol |
| Explicit prohibition on SMOTE, with reasoning (§15.1) | Synthetic interpolation of graph features produces impossible transactions and breaks temporal ordering |
| Probability calibration (§15.3) | Thresholds expressed in probability terms are meaningless uncalibrated |
| Alert-budget threshold selection (§15.4) | How detection systems are actually operated; arbitrary cutoffs are not |
| Equal search budget across experiments (§15.2) | Otherwise the ablation measures tuning effort, not features |
| Boundary-spanning pattern policy (§11) | A pattern straddling train/test leaks signal; previously unaddressed |
| Explicit insertion-order convention (§12) | Inserting before extraction lets a transaction inflate its own structural features |
| Missing-value policy per feature (§13.4) | "No history" and "zero activity" are different facts |
| Temporal stability across test sub-windows (§16.4) | Reveals drift and gives the model a stated shelf life |
| Feature-distribution drift, PSI/KS (§16.4) | Durability signal |
| Slice analysis by amount, time, degree, path position (§17.3) | Aggregate metrics hide systematic blind spots |
| Error-analysis gate before feature work (§17.2) | Forces features to target measured failures rather than intuition |
| SHAP as leakage detection (§19.2) | A feature carrying 70% of importance is a warning, not a triumph |
| SHAP stability across seeds (§19.4) | Unstable importance makes any feature narrative unreliable |
| Per-family extraction cost breakdown (§20) | Gives the accuracy-versus-cost trade-off a denominator |
| Quantitative inclusion criterion, 2σ + CI (§21) | Replaces "measurable improvement" with a testable rule |
| Explicit "if nothing passes, E2 is final" (§25) | Prevents goalpost-moving |
| Validation gates C1–C8 and P1–P9, set before E7 (§26) | The terminus of the scope, made concrete |
| Robustness checks: feature, window, threshold, noise sensitivity (§26.3) | Distinguishes a stable model from a lucky one |
| Validated model package specification (§26.4) | Clean scope boundary |
| Leakage tests as a first-class CI category (§27) | Merge-blocking, not advisory |
| Handoff contract (§34) | Keeps the narrowed scope a boundary rather than a gap |

### Carried forward from the correctness fixes in v2

Unified `is_laundering` naming with structural enforcement · single `E0`–`E7` experiment ID scheme · dataset roles made concrete · capability-gap analysis (now used to delete features rather than defer them) · split-before-model timeline ordering · corrected ASCII diagrams · verification flags on unconfirmed citations
