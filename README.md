# FlowGuard

**Graph-structural AML detection on IBM Snap ML's Graph Feature Preprocessor — measured
against IBM's own benchmark, without lookahead and without the simulator's artifact.**

Built for **Datathon problem statement PS9 — *Tracking of Funds within Bank for Fraud
Detection*.** FlowGuard scores transactions for money-laundering risk, traces where funds
went, and packages each alert as a self-validating evidence bundle an investigator can read.

> **This is the AI repository**: the model, the code that trains and scores it, and the
> evidence behind every number. The frontend, backend and database live in a separate
> product repository, which consumes exactly two folders from here —
> **[`contracts/`](contracts/)** and **[`sample_outputs/`](sample_outputs/)**.
> Product developers start at [`contracts/README.md`](contracts/README.md).

---

## Status at a glance

| | |
|---|---|
| **Shipped model** | `flowguard_V2_v1` — PR-AUC **0.595** (seeds 0.597 ± 0.002), best F1 **0.613**, recall **78.0%** at a 1% alert budget; all 8 correctness gates pass |
| **Against IBM's benchmark** | F1 **0.614** vs the published GFP+XGBoost **63.2** — using **neither** the payment-rail artifact **nor** within-batch lookahead, both of which the published protocol includes |
| **Real network** | On the Ethereum phishing graph, graph features lift account PR-AUC by **+0.050** (95% CI 0.019–0.108), and survived the extractor fix unchanged |
| **Explainability** | Every reason in every evidence bundle is named in plain language — graph, behaviour and row-local features alike; a test enforces it |
| **Scoring** | `python -m flowguard.pipeline.score` — batch, Linux, history-aware |
| **Tests** | 275 passing (plus 7 slow reconstruction tests), including contract tests on every sample output |
| **Decision records** | 15 ADRs — including [ADR-015](docs/ADR-015-gfp-double-insertion.md), a defect we found in our own extractor and every result it touched |
| **Production-ready?** | **No** — see [Where this stands](#where-this-stands) |

---

## Headline results — IBM AML HI-Small

**Protocol** (the GFP paper's, verified in [`papers/`](papers/)): the full corpus, a 60/20/20
chronological split, minority-class F1 at a threshold chosen on validation, five seeds.
Full per-run detail in [`WINNING_PLAN.md`](WINNING_PLAN.md).

| Model | `payment_type` | Lookahead | F1 | PR-AUC |
|---|:-:|:-:|---:|---:|
| IBM GFP paper, GFP + XGBoost ([Blanuša et al.](papers/), Table 4) | yes | batch 128 | 63.2 ± 0.2 | — |
| Ours, the paper's GFP configuration, tuned | yes | batch 128 | 0.524 ± 0.021 | 0.516 ± 0.020 |
| Same, **strictly one transaction at a time** | yes | **none** | 0.518 ± 0.027 | 0.504 ± 0.020 |
| Same, **`payment_type` removed** | **no** | none | 0.249 ± 0.044 | 0.203 ± 0.046 |
| + account-behaviour features | no | none | 0.544 ± 0.036 | 0.570 ± 0.012 |
| **v2 — same, timestamp statistics dropped (shipped)** | **no** | **none** | **0.614 ± 0.003** | **0.608 ± 0.004** |

Five things this table says, each measured rather than assumed:

1. **Lookahead is worth nothing measurable.** The paper feeds GFP 128 transactions at a time,
   so a transaction can see later ones in its batch ([ADR-004](docs/ADR-004-gfp-batch-leakage.md)).
   Scoring strictly one at a time gives the same F1 within noise.
2. **Half the benchmark score is a simulator artifact.** 2,553 of 2,554 injected patterns are
   on one payment rail (ACH) ([ADR-007](docs/ADR-007-payment-type-artifact.md)). Remove the
   field and F1 halves. The published figure uses it too.
3. **Behaviour features recover it honestly.** Ten strictly-causal account-history features —
   first-time counterparty, dormant account suddenly sending, funds passed straight through —
   more than double artifact-free F1. They are standard AML red flags GFP does not compute.
   *Caveat:* a synthetic generator can exaggerate exactly these traits; they are not yet
   validated on another corpus.
4. **Timestamp statistics were a time proxy.** The paper's GFP configuration adds vertex
   statistics on the timestamp. They topped the attributions ("average timestamp of the
   sender's transfers"), helped on validation (next to training time) and **hurt on test**
   (further out). Dropping them — decided on explainability grounds before measuring —
   raised test F1 from 0.544 to 0.614 and cut its seed spread twelvefold.
5. **The test period includes the generator's tail**, where laundering is 20–68% of rows
   ([ADR-003](docs/ADR-003-sparse-tail-trim.md)). On the dense first window alone — 952k rows,
   1,003 positives — v2's PR-AUC is **0.41**. The published protocol includes the same tail.

**The biggest single fix was one parameter.** Every model before 2026-09-21 weighted positives
by the negative/positive ratio (~980). Tuning chose **2**. F1 went from 0.280 to 0.521.

### Real network — XBlock Ethereum phishing graph

Account-level, account-disjoint protocol ([ADR-012](docs/ADR-012-account-disjoint-proxy.md)),
re-run with the corrected extractor on the same 1.25M-edge prefix as before.

| Arm | Account PR-AUC (3 seeds) |
|---|---:|
| Row-local features only | 0.0031 |
| + GFP graph features | **0.0533 ± 0.0015** |
| + behaviour features | 0.0631 ± 0.0070 |

Graph Δ **+0.0497**, paired-bootstrap 95% CI **[0.0186, 0.1079]**, 2,000 of 2,000 resamples
favour the graph arm — unchanged by the fix. The behaviour features add +0.0098 (2σ bar
0.0085): a first sign they are not only a trait of the synthetic generator. The direction is
settled; the magnitude is not — the scored set holds only 20 illicit accounts.

---

## What an investigator gets

| Capability | Where | State |
|---|---|---|
| Risk score per transaction, ranked, with an alert flag at a stated budget | `pipeline/score.py` → `scores.csv` | built |
| **Fund tracing** — forward and backward, strictly time-ordered, truncation reported | [`graph/trace.py`](Project/flowguard/src/flowguard/graph/trace.py) | built (FR-05) |
| **Evidence bundle** per alert — the traced path, the transactions, the reasons, threshold provenance, model version, a coverage warning | [`evidence/bundle.py`](Project/flowguard/src/flowguard/evidence/bundle.py) | built (FR-09, FR-11) |
| **Named reasons** — e.g. *"count of fan-in patterns of size 4 containing this transaction (24h window)"* | [`features/gfp.py: feature_labels`](Project/flowguard/src/flowguard/features/gfp.py) | built — names all GFP columns from IBM's documented layout, verified against real output |

A bundle validates itself: `check_internal_consistency()` fails if any field states a fact its
own path does not.

---

## Where this stands

**Presentable as research: yes. Deployable for real AML decisions: no.**

| Limitation | Evidence |
|---|---|
| **Blind off ACH.** Recall at 1%: ACH 84.6%; cheque 4.2%, cash, credit card and Bitcoin 0% | The corpus puts almost no laundering on other rails (144 of 1,797 test positives); removing the artifact cannot add examples |
| **Extraction throughput** 532 tx/s strictly one-at-a-time (gate P8 wants 1,000) | Batches of 128 reach 2,785 tx/s at no measured accuracy cost — ≤ ~23 s of alert latency on this corpus. A deployment choice, not a pass |
| **Peak memory** 10.99 GB (gate P9 wants ≤ 10 GB) | Training over the full 5M-row feature table |
| **False positives on legitimate complexity** 1.5× ordinary traffic | Merchant hubs, payroll fan-out (hard-negative slice; A4 was 2.1×) |
| **Low-value laundering is missed.** Recall at 1%: 4% below $139, 34% for $139–599 | Small transfers carry little structural signal |
| **Synthetic data only**, one generator for the headline | Behaviour features in particular need a second corpus |
| **Cold start** — a window scored without history alerts far above budget | `score.py --emit-from` scores a window using earlier rows as history; use ≥ 2 days |

---

## Repository map

```text
flowguard/  (this repository — AI only)
├── README.md            this file
├── WINNING_PLAN.md      the dated work log — every result, including what went wrong
├── PENDING.md           what is still open
├── contracts/           THE HANDOFF — four JSON schemas the product builds against
├── sample_outputs/      50,000 test-period transactions scored by v2, ten evidence bundles
├── Project/flowguard/   THE CODE
│   ├── src/flowguard/   data · splits · features · graph · evidence · models · evaluation · pipeline · registry
│   ├── tests/           unit / leakage (merge-blocking) / integration
│   ├── models/flowguard_V2_v1/   THE SHIPPED MODEL (8.7 MB) — model, calibrator, schema,
│   │                             thresholds, graph.json, SHAP summary, model card, validation report
│   ├── experiments/results.csv   the experiment registry
│   ├── configs/ · scripts/ (incl. measure/, the scripts behind every quoted number)
├── docs/                THE REASONING — STATUS, 15 ADRs, analyses; index in docs/README.md
│   └── archive/         superseded plans
├── papers/ · websites/  reference material (IBM's GFP paper and Snap ML docs among them)
└── end report/          pointers to the hosted reports
```

`Dataset_/` (raw corpora, 4.4 GB) and the data folder stay local.

---

## Quick start

Linux only — the graph library's native backend ships in manylinux wheels
([ADR-001](docs/ADR-001-gfp-platform.md)).

```bash
cd Project/flowguard && bash scripts/setup_wsl.sh      # environment + GFP backend check

# data: the full corpus, as the benchmark protocol uses it
python -m flowguard.pipeline.ingest --variant HI-Small --min-density 0 --out-dir <data>/processed/benchmark

# benchmark runs (WINNING_PLAN S1–S4): extraction, optional tuning, five seeds
python -m flowguard.pipeline.run_benchmark --processed-dir <data>/processed/benchmark \
    --cache <data>/processed/benchmark/gfp_paper_b1 --batch-size 1 --paper-params \
    --no-payment-type --behaviour --drop-timestamp-stats --n-estimators 3000 \
    --params-from <tuned run>.json --out run.json

# the shipped package: every gate, then models/flowguard_V2_v1/
python -m flowguard.pipeline.run_validation --processed-dir <data>/processed/benchmark \
    --gfp-cache <data>/processed/benchmark/gfp_paper_b1 --model-id V2 --artifact-free \
    --behaviour --drop-timestamp-stats --from-run run.json --n-estimators 3000

# score a window, using everything before it as history
python -m flowguard.pipeline.score --package models/flowguard_V2_v1 \
    --transactions <file.csv|parquet> --emit-from 2022-09-08T16:13:00 --out <dir> --cases 25

python -m pytest -m "not slow"                           # the leakage suite is merge-blocking
```

---

## Where to start reading

1. **[`docs/STATUS.md`](docs/STATUS.md)** — every current number and the protocol behind it.
2. **[ADR-015](docs/ADR-015-gfp-double-insertion.md)** — the extractor defect, found and fixed,
   and the table of every result it affected.
3. **[ADR-007](docs/ADR-007-payment-type-artifact.md)** — the artifact that halves the benchmark.
4. **[`WINNING_PLAN.md`](WINNING_PLAN.md)** — how the numbers moved, step by step.
5. **[`docs/README.md`](docs/README.md)** — the index of all decision records.

A negative result is a success condition here: several decision records document work that
was built, measured and discarded because a rule fixed before the run said so.

### Hosted reports

Four reports were published on 2026-09-21: [Validation Report](https://claude.ai/artifact/Y9qSGamEhR5nbeyacw6yzy),
[Project Ledger](https://claude.ai/artifact/83KjAnxMtm2xEAk7nRdsVQ),
[Six Phases, Sixteen Gates](https://claude.ai/artifact/Mrrx53zCPmCuBndyiy4Ejo) and
[Case Desk](https://claude.ai/artifact/UpGYYThbJiNrnsV5U9hkNC). **They predate ADR-015 and quote
A4-era figures; this README and STATUS supersede them.**
