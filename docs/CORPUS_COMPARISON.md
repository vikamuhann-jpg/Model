# Corpus comparison — HI-Small vs LI-Small

**Date:** 2026-09-19
**Purpose:** What a second corpus from the same generator does and does not establish.

LI-Small was ingested through the unmodified pipeline. Every component — loader, pattern
attachment, tail trimming, validator, capability matrix — generalised without a change.

---

## Measured side by side

| | HI-Small | LI-Small |
|---|---:|---:|
| Transactions *(after tail trim)* | 5,077,237 | 6,923,826 |
| Accounts | 515,078 | 705,905 |
| Positives | 4,522 | 3,431 |
| **Base rate** | **0.0891%** | **0.0496%** |
| Injected patterns | 370 | 117 |
| **Typology coverage of positives** | **62.0%** | **28.7%** |
| Self-transfer rate | 11.64% | 11.62% |
| Cross-currency rate | 1.42% | 1.43% |
| Orphan endpoints | 0 | 0 |
| Ambiguous pattern keys | 0 | 0 |

---

## Three generator properties confirmed across both corpora

### 1. The ACH convention ([ADR-007](ADR-007-payment-type-artifact.md))

| Corpus | Pattern transactions | On ACH |
|---|---:|---:|
| HI-Small | 2,554 | 2,553 — **99.96%** |
| LI-Small | 1,023 | 1,022 — **99.90%** |

Not a quirk of one generation run. AMLSim injects laundering over a single rail.

### 2. The laundering-saturated tail ([ADR-003](ADR-003-corpus-tail.md))

| Corpus | Tail rows | Tail positives | Tail laundering rate |
|---|---:|---:|---:|
| HI-Small | 1,108 | 655 | **59%** |
| LI-Small | 223 | 134 | **60%** |

Background traffic stops before injected pattern chains finish, in both. The trimming
step was written for HI-Small and fired correctly on LI-Small without adjustment.

### 3. Structural rates are near-identical

Self-transfers 11.64% vs 11.62%, cross-currency 1.42% vs 1.43%. The generator produces
the same background behaviour at different laundering densities, which is what makes
LI-Small a clean **base-rate contrast**.

---

## What LI-Small can and cannot be used for

### It CAN test

* **Base-rate robustness.** 0.0496% against 0.0891% — nearly half. Whether the method
  degrades when positives are rarer is a real question this answers.
* **Whether findings replicate.** The amount-magnitude failure, the hard-negative
  enrichment control, and the graph contribution can all be re-measured independently.
* **Whether the pipeline generalises.** Already answered: it does, unchanged.

### It CANNOT test

* **Simulator independence.** It shares the generator, and therefore the ACH convention
  under suspicion. A model exploiting that artifact will exploit it here identically.
  Any result on LI-Small presented as external validation would be **wrong**.

Only a corpus from a different generator — or a real network such as ETH Phishing — can
answer whether the method learned laundering or learned AMLSim.

---

## A new limitation LI-Small introduces

**Typology coverage is 28.7%, against 62.0% on HI-Small.** Only 117 patterns are injected
across 6.9M transactions, so most positives carry no typology annotation.

Consequences, which must be stated wherever LI-Small results appear:

* The **unseen-pattern split** would cover barely a quarter of the positive class —
  materially weaker than on HI-Small, and arguably too weak to support a generalisation
  claim.
* **Per-typology recall** describes under a third of positives.
* The capability matrix reports the coverage figure in the experiment record, so this is
  visible rather than assumed.

This is the reverse of the usual trade: LI-Small is larger and has a more realistic
(lower) base rate, but is **less annotated**, so the very splits that test generalisation
are weaker on it.

---

## Recommendation

Use LI-Small as a **base-rate contrast**, labelled as such — never as external validation.
Report the ACH concentration and the 28.7% coverage alongside any result from it.

The value it adds is real but bounded: it tells us whether the finding survives a halved
base rate. It tells us nothing about whether the finding survives leaving the simulator.
