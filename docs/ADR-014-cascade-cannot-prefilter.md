# ADR-014 — A cheap tier cannot pre-filter for an expensive one here

> **Note 2026-09-22:** figures in this record were computed with the extractor that inserted every edge twice. See [ADR-015](ADR-015-gfp-double-insertion.md) for what was re-run and the corrected values.

**Status:** Accepted — negative result
**Date:** 2026-09-21
**Decision:** Do **not** use two-tier cascading to meet the extraction throughput gate.
It meets the gate and costs about half the detections.

---

## What it was meant to fix

Gate P8 requires 1,000 tx/s of feature extraction. The graph extractor sustains ~450 tx/s
on HI-Small and ~139 tx/s on a real network, the library is closed, and
[ADR-013](ADR-013-degree-skew-dominates-cost.md) established the cost tracks the tail of
the degree distribution. The gate cannot be met by running the same thing faster.

The standard production answer is to stop running it on everything: score cheaply first,
spend the expensive model only on what survives.

```text
all transactions -> tier 0: row-local features     (~90k tx/s)
                        |
                        +- top K% -> graph features -> final score
```

## Result

Seven hundred sixty-one thousand test rows, 906 positives, three seeds per arm.

| Arm | PR-AUC | Recall @1% |
|---|---:|---:|
| tier 0 — row-local only | 0.0069 | 11.9% |
| tier 1 — + graph | 0.1362 | 56.0% |

| K | Recall @1% | Share of full | End-to-end | Throughput gate | Recall gate |
|---:|---:|---:|---:|:--|:--|
| 1% | 11.9% | 20.9% | 29,947 tx/s | PASS | **FAIL** |
| 2% | 16.9% | 29.9% | 17,981 tx/s | PASS | **FAIL** |
| 5% | 29.3% | 51.6% | 8,178 tx/s | PASS | **FAIL** |
| 10% | 39.2% | 69.2% | 4,285 tx/s | PASS | **FAIL** |

The throughput gate passes by more than an order of magnitude at every routing share. The
recall gate — keep ≥ 95% of full-extraction recall — **fails at every routing share**, and
at the planned K = 5% it does not miss narrowly: it keeps barely half.

## Why, and why tuning will not save it

Tier 0 reaches 11.9% recall where tier 1 reaches 56.0%. A filter can only forward what it
can see, and **the positives graph features detect are largely invisible to row-local
features**. That is not incidental — it is the same fact that makes graph features worth a
21× lift over the tabular baseline. Everything that makes them valuable makes them
un-prefilterable by a tabular score.

Raising K does not resolve it. Routing ten percent of the corpus still recovers only 69% of
the recall, and the curve is flattening: extrapolating, the routing share that would clear
95% is close to routing everything, at which point there is no cascade.

A better tier 0 would have to predict which transactions the graph model will like —
which is to say, it would have to already contain the graph signal.

## The second corpus adds throughput, not recall

On the ETH slice the cascade sustains 1,351–10,781 tx/s across the same routing shares, so
the throughput claim holds on a real network too. Its **recall column is not reported**:
ETH carries no transaction-level truth, and evaluating there would mean scoring the weak
proxy at transaction level, which [ADR-012](ADR-012-account-disjoint-proxy.md) forbids. The
run reports retention of 143.5% at K = 1% — a filter cannot beat the model it filters for,
and the figure is noise around a PR-AUC of 0.002. It is recorded here only so nobody
rediscovers it and mistakes it for a result.

## Decision

* `features/cascade.py` and its twelve tests stay in the tree. The implementation is
  correct and the property it guarantees — that a rejected transaction can never outrank an
  accepted one — holds. It is the *approach* that failed.
* It is **not** wired into any reported model.
* **Gate P8 stands as FAILED.** It is not rescued by this, and it should not be reported as
  conditionally met.

## What this establishes

Extraction cost on this method is **intrinsic, not an engineering oversight**. Two
independent attempts have now failed to reduce it: periodic graph reconstruction, rejected
for failing its identity test ([ADR-008](ADR-008-reconstruction-rejected.md)), and
cascading, rejected here for costing half the detections. Combined with ADR-013's finding
that the cost is driven by degree skew that real networks have and this generator does not,
the honest position is that **this method is expensive, the expense is a property of the
method, and no amount of routing changes that.**

## Revisit if

A cheap tier becomes available that carries some graph signal — incrementally maintained
degree counters, for example, which are far cheaper than full subgraph enumeration. The
experiment to run then is the same one, with the same gate.
