# Error analysis — artifact-free tabular baseline (A2)

**Date:** 2026-09-18
**Model:** transaction-only XGBoost, `payment_type` removed ([ADR-007](ADR-007-payment-type-artifact.md))
**Budget:** 1% alert budget, 761,422 test transactions, 906 positives

This is the gate plan v3 §17.2 places in front of all feature work: *features designed
before the error analysis exists are guesses*. It is run against **A2** rather than A1
because A1's performance is mostly the simulator artifact, so its error profile describes
the artifact rather than the problem.

---

## Headline

| Metric | Value |
|---|---:|
| PR-AUC | 0.0066 |
| Lift over base rate | 5.6× |
| ROC-AUC | 0.7945 |
| Recall @1% budget | 11.8% |
| Recall @5% budget | 32.5% |

**Gate C8 now passes.** With the artifact removed the top feature is `tx_amount` at
**35.8%** of mean |SHAP|, under the 50% ceiling — where `payment_type` had held 56.8%.
This must be reported as *"passes after removing a disclosed artifact"*, never as an
unqualified pass.

Remaining SHAP mass: `amount` 35.8%, `amount_received_log` 16.7%, `is_self_transfer`
14.1%, `currency` 13.4%, `minute_of_day` 9.6%. **Over half of the model's attention is on
transaction magnitude.**

---

## The dominant failure: it can only see big transactions

Recall by amount band, at the 1% budget:

| Amount band | Positives | Recall |
|---|---:|---:|
| ≤ $144 | 42 | **0.0%** |
| $144 – $614 | 35 | **0.0%** |
| $614 – $2,671 | 143 | **0.0%** |
| $2,671 – $17,158 | 442 | 14.7% |
| > $17,158 | 244 | 17.2% |

**Zero recall on every laundering transaction below $2,671** — 220 positives, 24% of the
test positive class, entirely invisible.

The missed-versus-caught contrast says the same thing:

| | Count | Median amount |
|---|---:|---:|
| Missed positives | 799 | $6,793 |
| Caught positives | 107 | **$15,711** |

Caught transactions are 2.3× larger than missed ones. The model has learned "large
transfer" as its main proxy for suspicion, which is precisely the legacy
threshold-monitoring behaviour the project set out to improve on — and precisely what
structuring defeats.

## Position within the pattern is *not* the constraint

| Position in chain | Positives | Recall |
|---|---:|---:|
| Early | 264 | 21.6% |
| Middle | 172 | 15.1% |
| Late | 128 | 17.2% |

Nearly flat. This rules out the obvious temporal hypothesis — the model is not failing
because early hops lack accumulated history. It fails roughly evenly along the chain,
which is consistent with it never modelling the chain at all.

## By typology

| Typology | Recall |
|---|---:|
| CYCLE | 25.0% |
| *(unannotated)* | 0.6% |

Only CYCLE clears 20%. The unannotated positives — 38% of the class, with no typology
label — are effectively undetected at 0.6%.

## Hard negatives: a clean control

| | Value |
|---|---:|
| Structurally complex benign transactions | 172,158 (22.6% of benign) |
| False-positive rate on that slice | 1.396% |
| False-positive rate on ordinary benign | 1.367% |
| **Enrichment** | **1.02×** |

The tabular model does **not** confuse structural complexity with crime — unsurprisingly,
since it has no structural features to confuse itself with. That 1.02× is the control
value: **if E2's graph features push this materially above 1.0, they are buying recall by
alerting on legitimately complex accounts**, which is the false-positive pain v3 §11 C
warns about. This number is the one to watch when the graph result lands.

---

## What this licenses building

The analysis supports one specific, falsifiable hypothesis:

> **The artifact-free baseline detects laundering only by transaction magnitude, and is
> blind to every laundering transaction under ~$2,671. Graph-structural features should
> recover low-value positives specifically, because a small transaction inside a fan-in,
> cycle or chain is identifiable by its *position in the topology* rather than its size.**

The prediction is sharp enough to be wrong: if graph features help, **the gain must show
up disproportionately in the bottom three amount bands**, which currently sit at exactly
zero recall. A uniform lift across all bands would suggest the graph features are acting
as another magnitude proxy rather than contributing structural information.

Two secondary checks come with it:

* Hard-negative enrichment must stay near 1.0×. Recall bought by alerting on complex
  benign accounts is not a real improvement.
* The unannotated positives (0.6% recall) are the hardest slice. Movement there would be
  the strongest evidence of genuine generalisation, since those transactions carry no
  typology template to memorise.

## What this does *not* license

Temporal-velocity features are **not** supported by this analysis. The flat
early/middle/late recall profile gives no evidence that accumulated history is the
binding constraint. Building them now would be exactly the guess v3 §17.2 prohibits —
revisit only if the graph result shows a position-dependent gain.
