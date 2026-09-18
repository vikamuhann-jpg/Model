# ADR-007 — `payment_type` is a generator artifact, and must be ablated

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Report every headline comparison **twice** — with and without
`payment_type`. The version without it is the honest measure of whether the model
learned laundering structure or learned the simulator.

---

## How this surfaced

Gate C8 (no single feature above 50% of mean |SHAP|) **failed** on E1:

```
[FAIL] C8  top feature tx_payment_type_code holds 56.8% of mean |SHAP|
```

Plan v3 §19.2 frames exactly this situation: a feature carrying most of the
importance is *"a warning, not a triumph"*. The gate did its job.

## Investigation

Laundering rate by payment rail across the full corpus:

| Payment type | Rows | Positives | Rate | Share of positives | Enrichment |
|---|---:|---:|---:|---:|---:|
| **ACH** | 599,689 | **3,828** | 0.638% | **84.7%** | **7.2×** |
| Cheque | 1,864,331 | 324 | 0.017% | 7.2% | 0.20× |
| Credit Card | 1,323,324 | 206 | 0.016% | 4.6% | 0.17× |
| Cash | 490,891 | 108 | 0.022% | 2.4% | 0.25× |
| Bitcoin | 146,091 | 56 | 0.038% | 1.2% | 0.43× |
| Reinvestment | 481,056 | **0** | 0% | 0% | 0× |
| Wire | 171,855 | **0** | 0% | 0% | 0× |

Corpus base rate: 0.089%.

Restricting to transactions that carry a typology annotation — i.e. those the
generator explicitly injected as part of a laundering pattern:

| Payment type | Annotated pattern rows |
|---|---:|
| ACH | **2,553** |
| Bitcoin | 1 |

**99.96% of injected pattern transactions are ACH**, and the cross-tab by typology
shows it holds for all eight — BIPARTITE, CYCLE, FAN-IN, FAN-OUT, GATHER-SCATTER,
RANDOM, SCATTER-GATHER and STACK are essentially pure ACH.

## What this is, and is not

**It is not leakage.** `payment_type` is a legitimate attribute observable at scoring
time, carries no future information, and no label was involved in producing it. The
leakage suite is right to pass.

**It is a spurious correlation baked into the simulator.** AMLSim injects laundering
over a single rail. In real banking data, laundering is not 99.96% ACH — money mules use
cards, cash, wires and crypto precisely to vary the rail. A model leaning on
`is_ACH` has learned the generator's implementation, not money laundering.

This distinction matters for how it is handled: leakage must be *eliminated*, whereas a
dataset artifact must be *measured and disclosed*.

## Why it distorts the central research question

The project exists to answer whether graph-structural features improve detection over a
tabular baseline. A tabular model with `payment_type` can shortcut most of the way to
the answer without any structural understanding, which:

1. **inflates E1**, raising the bar E2 must clear;
2. **understates the value of graph features**, because the structural signal they add
   is partly redundant with an artifact E1 already exploits;
3. **produces a headline number that will not survive contact with real data.**

An E1-vs-E2 comparison conducted only with `payment_type` present risks concluding
"graph features add little" when the true finding is "the simulator leaks its rail
choice".

## Decision

* `TransactionFeatures(include_payment_type=...)` makes it switchable, defaulting to
  `True` so the artifact-inclusive number remains reproducible.
* **Every headline comparison is run both ways.** The ablation is not optional garnish;
  it is the control that makes the graph-feature result interpretable.
* The **artifact-free** variant is the one the conclusion should rest on. The
  artifact-inclusive variant is reported alongside so the gap is visible.
* `model_card.md` lists `payment_type` under evaluated-and-disclosed with this
  reasoning, so a future reader does not rediscover it.

## Measured cost of the artifact

Five seeds per arm, one change between them, everything else identical:

| Arm | Features | PR-AUC | Recall @1% budget |
|---|---:|---:|---:|
| A1 — `payment_type` included | 13 | 0.0416 ± 0.0030 | 41.0% |
| A2 — `payment_type` **removed** | 12 | **0.0066 ± 0.0003** | **12.1%** |

Delta 0.0350 against a 2σ bar of 0.0032 — an order of magnitude past noise.

**Roughly 84% of the tabular baseline's apparent performance was the artifact.**
Removing one column collapses PR-AUC 6.3× and cuts recall at the 1% budget from 41% to
12%. The honest transaction-only baseline is **0.0066**, a lift of ~5.5× over the base
rate rather than the 35.7× first reported.

This reframes the project's central question rather than merely qualifying it. The
earlier E1 number left graph features almost no headroom to demonstrate value; against
the artifact-free baseline there is a large, genuine gap for structural information to
fill. **The E2-versus-A2 comparison is the one that answers the research question**;
E2-versus-A1 mostly measures how much of the simulator's giveaway the graph features
happen to reproduce.

## Consequences

* Absolute PR-AUC falls hard in the artifact-free variant. That is the point — the
  earlier number was mostly measuring the simulator.
* C8 may pass once `payment_type` is removed, since the dominant feature is gone. A C8
  pass achieved that way should be reported as *"passes after removing a disclosed
  artifact"*, never as an unqualified pass.
* This strengthens the case for cross-dataset validation (v3 §24). A real network such
  as ETH Phishing has no injected-rail convention, so it is the only way to show the
  result is not simulator-specific.

## Revisit if

A corpus is used whose laundering is distributed across payment rails in proportion to
legitimate traffic, in which case `payment_type` becomes an ordinary feature and the
ablation becomes informative rather than corrective.
