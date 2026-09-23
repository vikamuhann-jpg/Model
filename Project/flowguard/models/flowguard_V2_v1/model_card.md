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
| XGBoost | {'max_depth': 8, 'learning_rate': 0.03, 'subsample': 0.8, 'colsample_bytree': 0.75, 'min_child_weight': 1, 'reg_lambda': 0.01, 'scale_pos_weight': 2}; up to 3000 rounds, best 740 |

## Performance

| Metric | Value |
|---|---:|
| PR-AUC | 0.5949 |
| Lift | 336.2x |
| Recall @1% budget | 78.0% |
| Precision @1% budget | 13.80% |
| Inference latency | 30.12 ms median (batch=1) |

### Per typology, recall at 1% budget

| Typology | Recall | Caught |
|---|---:|---|
| BIPARTITE | 91.9% | 68/74 |
| CYCLE | 95.4% | 104/109 |
| FAN-IN | 93.4% | 128/137 |
| FAN-OUT | 97.9% | 137/140 |
| GATHER-SCATTER | 95.5% | 383/401 |
| RANDOM | 91.9% | 79/86 |
| SCATTER-GATHER | 97.6% | 246/252 |
| STACK | 89.3% | 125/140 |

## Known failure modes

* **Unannotated positives.** Only ~62% of positives carry a typology label, so
  per-typology recall describes two-thirds of the positive class.
* **Truncated patterns.** 140 of 370 patterns straddle a split boundary; recall
  on those is a floor, not an unbiased estimate (ADR-002).
* **Structurally complex benign activity** — see the hard-negative slice in
  `metrics.json` for the measured false-positive enrichment.

## Datasets NOT validated on

HI-Medium, HI-Large, LI-*, and any real-world transaction data. No cross-dataset
validation has been performed, so generalisation beyond this generator is
**unmeasured**.

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
