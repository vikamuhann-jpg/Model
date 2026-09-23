# FlowGuard — Open Items

**Date:** 2026-09-20
**Scope:** what is genuinely still open. Everything resolved during the build has been
removed rather than annotated; the record of *how* it was resolved lives in the ADRs.

Current results are in [`STATUS.md`](STATUS.md). This file is only the remainder.

---

## 1. Unresolved findings

### 1.1 The model is blind to every payment rail except ACH

**Status:** open, and the most serious limitation in the project.

E2 catches 599 of 796 ACH laundering transactions at the 1% budget and **1 of 100** on
every other rail combined — 0.0% on cheque, credit card and cash. The cause is
[ADR-007](ADR-007-payment-type-artifact.md): 2,553 of 2,554 annotated pattern rows are
ACH, so the corpus contains almost no non-ACH laundering to learn from.

**Why it is not fixed here.** It is a property of the generator, not of the model. No
feature family can teach a model about behaviour the corpus does not contain. It would
need a corpus whose laundering is distributed across rails.

### 1.2 False positives on legitimate complexity: 2.3×

**Status:** open. Tier B was the attempt and it failed.

The graph model alerts on structurally complex but benign accounts at 2.49% against
1.09% for ordinary benign traffic. The adaptive neighbourhood family was built
specifically to attack this and cost 0.0326 PR-AUC — five times the noise bar
([ADR-011](ADR-011-adaptive-features-rejected.md)). Degree-normalisation removes the
raw structural counts that were doing the detecting.

**What would be needed.** Something that separates *anomalous* structure from *large*
structure without discarding size. Nothing in this project achieves that, and ADR-011
argues the question may not even be well-posed on a corpus whose laundering sits on one
rail.

### 1.3 The performance envelope is generator-specific

**Status:** open, and newly understood.

AMLSim produces a near-regular graph — HI-Medium's 99.9th-percentile degree is 11. Real
networks do not: the ETH slice's is 1,034, with 13.3% of edge endpoints on 0.01% of
vertices. GFP's neighbourhood searches grow super-linearly in degree, so every throughput
and memory figure in this project describes the generator rather than the method
([ADR-013](ADR-013-degree-skew-dominates-cost.md)).

**Why it is not fixed here.** It is a property of the library, which is closed, and of
the corpus. A degree-capped extraction mode would trade signal for bounded cost, but GFP
exposes no such control.

**What it does not undermine.** The *signal* result. Tier C measured graph features
carrying real signal on ETH; what fails to transfer is the cost model, not the finding.

### 1.4 Two performance gates fail

> **Correction 2026-09-22:** every figure in this section was measured with an extractor
> that inserted each edge twice, and the ADR-008 conclusion cited below is wrong — see
> [ADR-015](ADR-015-gfp-double-insertion.md). Corrected throughput is in
> [STATUS.md](STATUS.md). Note also that GFP does expose `max_no_edges`, a cap on graph
> size (not on degree).

* **P8 — extraction ≥ 1,000 tx/s.** Measured ~450 tx/s on HI-Small. Throughput decays
  as the graph fills; [ADR-008](ADR-008-reconstruction-rejected.md) established this is
  a property of the method after periodic reconstruction was tried and failed its
  identity test. **The gate does not transfer**
  ([ADR-013](ADR-013-degree-skew-dominates-cost.md)): cost tracks the tail of the degree
  distribution, and on a real scale-free network the method is an order of magnitude
  slower again — ~139 tx/s at 1.25M ETH edges against ~11,400 tx/s on an HI-Medium prefix
  of identical size.
* **P9 — peak RSS ≤ 10 GB.** Measured 10.88 GB. Chunked persistence
  ([ADR-009](ADR-009-chunked-extraction.md)) bounded both the extraction and assembly
  phases but did not bring the peak under the gate.

Both are reported as failures rather than rescoped.

---

## 2. Known weaknesses in the evidence

| | |
|---|---|
| **Typology coverage** | ~62% of positives carry a typology annotation; per-typology recall describes two-thirds of the positive class. |
| **Truncated patterns** | 140 of 370 patterns straddle a split boundary under `HARD_CUT`; their recall is a floor, not an unbiased estimate ([ADR-002](ADR-002-boundary-policy.md)). |
| **Device dependence** | Results are device-dependent through early stopping ([ADR-005](ADR-005-gpu-training.md)); the package records the resolved device. |
| **One generator for the headline** | HI-Small and LI-Small share a generator, so the second corpus tests robustness, not transfer ([`CORPUS_COMPARISON.md`](CORPUS_COMPARISON.md)). Tier C adds a genuinely independent corpus, but answers a different question. |
| **Tier C rests on 20 positives** | The direction is decisive (2,000/2,000 bootstrap resamples), the magnitude is not: the 95% CI on the delta spans 0.019–0.123. |
| **Tier C used 62% of its slice** | Extraction was stopped at 1.25M of 2.02M rows; the experiment ran on the contiguous prefix ([ADR-013](ADR-013-degree-skew-dominates-cost.md)). |
| **Contaminated pre-registration** | P4's 45% target was set against a baseline later found to be 84% artifact. The gate was left as written and reported as a miss ([ADR-010](ADR-010-contaminated-pre-registration.md)). |

---

## 3. Not built, deliberately

* **Track P** — API, dashboard, evidence packages, typology layer. Out of scope by the
  Track R decision recorded in [`README.md`](README.md); v2 §§29–33 retain the design.
* **Research Track B** ([`NEED_TO_RESEARCH.txt`](archive/planning/NEED_TO_RESEARCH.txt)) — briefed for a
  second researcher, never staffed, off the critical path.
* **Extraction resume** — a mid-extraction crash still costs the run. Chunked parts
  survive, but the graph state does not, and rebuilding it is the cost being avoided
  ([ADR-009](ADR-009-chunked-extraction.md)).
* **E3–E7** — the experiment ladder ends at E2 because Tier B produced no family that
  cleared the 2σ bar. Numbering is preserved rather than reused.

---

## 4. What would most improve the project

Not another feature family, and not a better number on HI-Small.

1. **A corpus with laundering across multiple payment rails.** It would turn §1.1 from
   a disclaimer into a measurement.
2. **Real transaction data.** Every claim here is bounded by synthetic or public-chain
   provenance, and the model card says so.
3. **Transaction-level truth on a real network**, which would remove the weak proxy
   Tier C depends on ([ADR-012](ADR-012-account-disjoint-proxy.md)) and let the two
   corpora be evaluated on the same question.
4. **More labelled accounts on a real network.** Twenty positives fixes a direction and
   cannot fix a magnitude; the Tier C interval would tighten with nothing else changed.
