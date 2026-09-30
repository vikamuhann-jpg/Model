# Model card — FlowGuard V2

## Intended use

Ranking transactions for **investigator review** in an AML workflow, at a stated
alert budget. It orders transactions by estimated suspicion; it does not decide
anything.

## Explicitly not for

* Automated blocking, freezing or refusal of transactions.
* Any determination that laundering occurred — that is a human and institutional
  judgement, and the model produces neither evidence nor proof.
* Deployment on a population unlike the training data without revalidation.
* Regulatory filing. Nothing here constitutes an STR.

## Training data

| | |
|---|---|
| Dataset | IBM AML HI-Small |
| Rows | 5,078,345 |
| Positives | 5,177 (0.102%) |
| Span | 2022-09-01 to 2022-09-18 |
| Split | chronological 60%/20%/20%, `hard_cut` boundary policy (ADR-002) |

## Features and model

| | |
|---|---|
| Features | 206 |
| Graph | GFP `time_window` 24 h, scatter-gather 6 h, vertex statistics on columns [3, 4] (timestamp statistics dropped); batch size 1; transform inserts once; behaviour features on. Stored in `graph.json`; `score.py` rebuilds features from it. |
| XGBoost | {'max_depth': 8, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.75, 'min_child_weight': 1, 'reg_lambda': 0.01, 'scale_pos_weight': 2}; up to 1000 rounds, best 740 |

## Performance

| Metric | Value |
|---|---:|
| PR-AUC | 0.5949 |
| Lift | 336.2x |
| Recall @1% budget | 78.3% |
| Precision @1% budget | 13.85% |
| Inference latency | 15.56 ms median (batch=1) |

### Per typology, recall at 1% budget

| Typology | Recall | Caught |
|---|---:|---|
| BIPARTITE | 91.9% | 68/74 |
| CYCLE | 95.4% | 104/109 |
| FAN-IN | 93.4% | 128/137 |
| FAN-OUT | 97.9% | 137/140 |
| GATHER-SCATTER | 96.3% | 386/401 |
| RANDOM | 93.0% | 80/86 |
| SCATTER-GATHER | 97.6% | 246/252 |
| STACK | 90.0% | 126/140 |

### Structured vs unstructured laundering, recall at 1% budget

The per-typology table above covers only laundering that belongs to an injected
pattern. What the model detects is *structure*, so this split is what the headline
number actually means. It ranks by the raw score, which has no ties; the headline and
the typology table use calibrated scores, which tie at the 1% cut-off, so totals can
differ by a handful of cases:

| | Share of test positives | Recall | Caught |
|---|---:|---:|---|
| Structured | 75% | 95.3% | 1276/1339 |
| Unstructured | 25% | 27.9% | 128/458 |

## Known failure modes

* **Unstructured laundering is largely missed.** A transfer with no fan-in, cycle or
  chain around it leaves no graph shape to find. See the split above; this is a
  limit of the method on every corpus measured, not of this one (LIM-08).
* **Truncated patterns.** 140 of 370 patterns straddle a split boundary; recall
  on those is a floor, not an unbiased estimate (ADR-002).
* **Structurally complex benign activity** — see the hard-negative slice in
  `metrics.json` for the measured false-positive enrichment.

## Fresh data

**LI-Small (2M-row prefix), applied unchanged: recall at 1% 13.3%, against the
pre-registered bar of 50% — failed.** 88% of that corpus's laundering is
unstructured, against 25% here, which explains about two-thirds of the drop;
structured laundering is still ranked at the 98.7th percentile. The alert threshold
transfers (1.34% alert rate). See `docs/DECISION_REPORT_LI_TRANSFER.md`.

**Not validated on:** HI-Medium, HI-Large, the full LI-Small, or any real-world
transaction data. Both corpora come from one generator, so generalisation beyond it
is **unmeasured** apart from the Ethereum graph (ADR-012).

## Evaluated and dropped

* `day_of_week`, `is_weekend` — removed. Over a 10-day corpus they proxy the
  calendar date and, under a chronological split, identified the generator's
  laundering-saturated tail rather than any behaviour (ADR-003).
* `payment_type` — removed. 2,553 of 2,554 pattern rows are ACH, so the feature
  encodes a generator convention rather than behaviour. It was worth 84% of the
  tabular baseline's PR-AUC (ADR-007).
* **Adaptive neighbourhood family** (11 features, `features/adaptive.py`) — built
  to attack the hard-negative enrichment by normalising structure against
  same-degree peers. Measured **A6 − A4 = −0.0326 PR-AUC** against a 2σ inclusion
  bar of 0.0059: a real regression at more than five times the noise threshold,
  costing 23% of the graph model's PR-AUC. Alone (A5) it scores 0.0041, below the
  12-feature tabular baseline. The code stays in the tree and is not wired into any
  reported model (ADR-011). These figures predate the extractor fix (ADR-015).
* **Value-flow family** — never built. Gate A falsified the low-band concentration
  prediction the hypothesis depended on, so it was ruled out before implementation.

## Performance envelope

Device: cuda. Peak RSS recorded in `metrics.json`.
GFP extraction is CPU-only and is the dominant cost (ADR-005, ADR-006).

## Revalidation trigger

Re-run validation if the base rate moves by more than 2x, if feature PSI exceeds
0.25 on any top-10 feature, or if the transaction mix changes materially.
