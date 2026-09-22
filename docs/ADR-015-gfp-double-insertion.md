# ADR-015 — Every edge was inserted into the graph twice

**Status:** Accepted — defect found, fixed, and every affected result listed
**Date:** 2026-09-22
**Decision:** Insert each edge exactly once, through `transform()`. Treat every result
computed with the old extractor as unverified until it is re-run, and say so wherever it
is quoted. **Supersedes** [ADR-008](ADR-008-reconstruction-rejected.md).

---

## What was wrong

IBM's Snap ML documentation for `GraphFeaturePreprocessor.transform` says:

> This function inserts the edges from the input edge list into the in-memory graph of
> this preprocessor and computes the graph-based features using the updated graph.

`features/gfp.py` believed `transform` was read-only. For every batch it called
`transform(batch)` for the features and then `partial_fit(batch)` to "insert" the batch —
so every edge entered the graph **twice**. The module docstring even described the wrong
convention as "the whole correctness story".

## How it was found

While reproducing the GFP paper's benchmark (WINNING_PLAN S1) the docs were read closely
for the first time. A four-edge test settled it — A, B, C, D each pay HUB, then the
fourth edge is scored:

| | Target in-degree | Target amount sum |
|---|---:|---:|
| Each edge inserted once (correct) | **4** | **400** |
| `transform` + `partial_fit` (our extractor) | **7** | **700** |

`transform` alone and `partial_fit` alone produced identical graphs; together they doubled
every earlier edge. Histogram counts also moved to the wrong bins.

## Why nothing caught it

- It is **not leakage**. Train, validation and test were distorted identically, so the
  leakage tests (future-edge invariance, label blindness) all passed — correctly.
- The one test aimed at insertion order,
  `test_transaction_does_not_inflate_its_own_features`, rested on the same false premise:
  it compared our extractor with "insert everything, then transform", which inflates even
  more, so it passed.
- The distortion is roughly monotone (counts about double), so the model still learned
  something and the numbers looked plausible.

## The fix

- `run_streaming` calls `transform` once per batch and nothing else. Self-transfers are
  never sent to GFP; their graph features are NaN (XGBoost routes NaN natively).
- `test_each_edge_enters_the_graph_once` compares streamed output with an
  insert-exactly-once reference; it replaces the test with the false premise.
- Extraction metadata now records `insertion_convention: "transform inserts once"`, so a
  feature cache made before the fix can be told apart from one made after.

## ADR-008 was wrong for the same reason

ADR-008 rejected periodic reconstruction because rebuilt features differed from
continuously-fed ones, and concluded GFP "retains state beyond the windowed edge set".
The difference was ours: the rebuild replayed each edge once, while the continuous graph
held each edge twice. With the fix, all four reconstruction tests pass — rebuilt features
are **identical** at every cadence tested. Reconstruction is sound again; whether it is
*worth it* is a throughput question, answered in STATUS.

## Results affected

Everything whose graph features came from the old extractor. The old figure stays visible
so the change is auditable; corrected figures are in [STATUS.md](STATUS.md).

| Result | Where quoted | Old figure | Re-run |
|---|---|---|---|
| A4 shipped model: PR-AUC, "21× over tabular" | README, STATUS, PENDING, model card | 0.1400 ± 0.0030 | superseded by v2 |
| E2 and the `payment_type` ablation lifts | README, ADR-007 | 0.2048 (E2) | not re-run — research arm only |
| Ethereum transfer, account-level Δ PR-AUC | README, ADR-012 | +0.0504 [0.0187, 0.1231] | **+0.0497 [0.0186, 0.1079]** — holds |
| Extraction throughput; "cost is intrinsic" | README, ADR-006, ADR-013, ADR-014 | ~450 tx/s synthetic, ~139 tx/s real | 532 tx/s HI-Small full corpus (batch 1); 135 tx/s ETH — **holds**: degree skew, not the defect, drives cost |
| Reconstruction rejected | ADR-008 | "unsound" | **wrong** — identical over 2M rows after the fix; but only +1% throughput, so still not adopted |
| Adaptive features rejected | ADR-011 | relative to E2/A4 | not re-run — direction likely holds |
| Cascade cannot pre-filter | ADR-014 | ~half the detections lost | not re-run — direction likely holds |
| 2.1× false positives on legitimate complexity | README, ERROR_ANALYSIS_A2 | 2.34% vs 1.11% | not re-run |
| P2 evidence case, P3 cascade, P4 typology, P6 unsupervised | TRACK_P_PLAN | various | not re-run |

**Unaffected:** E0 and E1 (no graph features); the `payment_type` data finding in ADR-007
(2,553 of 2,554 patterns on ACH is a count over the data, not a model output); ADR-002,
-003, -004, -005, -009, -010; the correctness of fund tracing and evidence bundles.

## What this cost

Every graph result from 2026-09-18 to 2026-09-21. What it bought: the corrected extractor
plus tuning took the benchmark-protocol F1 from 0.280 to 0.521 (WINNING_PLAN S1b → S2),
and a method the GFP authors would recognise as theirs.

## Lesson

Read the library's documented semantics for every call that mutates state, and test the
**absolute** value of a feature on a hand-built graph — not only its relative behaviour.
Every leakage test here compared two runs of the same extractor, so none could see a
defect both runs shared.
