# Model card — FlowGuard A4

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
| Rows | 5,077,237 (after trimming the generator's sparse tail — ADR-003) |
| Positives | 4,522 (0.089%) |
| Span | 2022-09-01 to 2022-09-10 |
| Split | chronological 70/15/15, `HARD_CUT` boundary policy (ADR-002) |

## Performance

| Metric | Value |
|---|---:|
| PR-AUC | 0.1369 |
| Lift | 115.0x |
| Recall @1% budget | 53.5% |
| Precision @1% budget | 6.37% |
| Inference latency | 13.10 ms median (batch=1) |

### Per typology, recall at 1% budget

| Typology | Recall | Caught |
|---|---:|---|
| BIPARTITE | 55.0% | 22/40 |
| CYCLE | 44.2% | 23/52 |
| FAN-IN | 75.0% | 42/56 |
| FAN-OUT | 71.4% | 45/63 |
| GATHER-SCATTER | 69.6% | 87/125 |
| RANDOM | 56.1% | 23/41 |
| SCATTER-GATHER | 81.1% | 86/106 |
| STACK | 58.0% | 47/81 |

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
  reported model (ADR-011).
* **Value-flow family** — never built. Gate A falsified the low-band concentration
  prediction the hypothesis depended on, so it was ruled out before implementation.

## Performance envelope

Device: cuda. Peak RSS recorded in `metrics.json`.
GFP extraction is CPU-only and is the dominant cost (ADR-005, ADR-006).

## Revalidation trigger

Re-run validation if the base rate moves by more than 2x, if feature PSI exceeds
0.25 on any top-10 feature, or if the transaction mix changes materially.
