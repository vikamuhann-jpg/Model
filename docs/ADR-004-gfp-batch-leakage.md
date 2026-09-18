# ADR-004 — GFP extraction must use `batch_size=1`

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Extract Graph Feature Preprocessor features one transaction at a time.
Any batch size above 1 leaks future graph structure into the present.

---

## Context

Plan v3 §12 fixes the insertion-order convention: features for an edge must be computed
against the graph as it stood *before* that edge was inserted, or a transaction inflates
its own structural features. The implementation followed that —

```python
transformed = preproc.transform(batch)   # features from history
preproc.partial_fit(batch)               # then insert
```

— with `batch_size=50_000`, chosen purely for throughput. That is correct with respect
to *inserted* history, and still wrong.

## Investigation

A batch-size test produced an unexpected result, so the behaviour was isolated on four
edges forming a fan-in onto one vertex, all within an hour:

```python
alone    = preproc().transform(edges[:1])   # edge 0 by itself
together = preproc().transform(edges)       # edge 0 alongside 3 later edges
```

Neither call inserts anything; both run against an empty graph. The feature vectors for
edge 0 nonetheless differ:

| Feature | Alone | Batched with 3 later edges |
|---|---:|---:|
| `f000` | 0.00 | 1.00 |
| `f001` | 0.00 | 1.00 |
| `f058` | 0.00 | 1.00 |
| `f207` | 1.00 | **4.00** |

`f207` is a degree/fan count. Transformed alone it reads 1; transformed alongside three
transactions that **had not yet happened**, it reads 4.

`GraphFeaturePreprocessor.transform` evaluates the edges in a call *against each other*,
not only against inserted history. The batch is itself a graph.

## Why this matters more than it looks

At `batch_size=50_000` every transaction could see up to 50,000 future transactions —
and precisely through the fan, degree, scatter-gather and cycle features that E2 exists
to evaluate. It would have inflated E2 and nothing else, producing a large, clean,
entirely artificial E1 → E2 improvement: the exact result the project is trying to
establish, arrived at by measurement error.

It is silent. There is no error, no warning, and the resulting numbers look plausible.

## Decision

`GFPFeatures.batch_size` defaults to **1**, and the constructor warns on any other
value. `tests/leakage/test_gfp_insertion_order.py::`
`test_batching_leaks_future_edges_so_batch_size_must_be_one` pins the behaviour, so
raising the batch size for speed cannot silently reintroduce it.

The cost is nil. Measured throughput:

| Batch size | Throughput | Full corpus | Leakage-safe |
|---:|---:|---:|---|
| **1** | **17,566 tx/s** | **~4.8 min** | **yes** |
| 100 | 70,610 tx/s | 1.2 min | no |
| 1,000 | 97,381 tx/s | 0.9 min | no |
| 10,000 | 85,586 tx/s | 1.0 min | no |

Batching is ~5× faster and saves four minutes on a run that already takes longer than
that to train. There is no trade-off worth making here.

`batch_size=1` also clears gate P8 (>1,000 tx/s extraction throughput) by ~17×.

## Consequences

* Every reported GFP result uses `batch_size=1`.
* `test_future_edge_invariance` — plan v3's strongest leakage test — passes: features
  for early transactions are byte-identical whether or not later edges exist.
* Graph experiments **cannot be smoke-tested on a stride-sample**. Taking every *n*-th
  transaction destroys the fan-ins, cycles and scatter-gather structures the features
  detect, so a sampled run understates graph value rather than approximating it. Smoke
  runs validate wiring only; any reported number comes from the full corpus.

## Revisit if

A future snapml release changes `transform` to evaluate edges independently. The pinned
test fails loudly in that case rather than passing quietly, which is the intent.
