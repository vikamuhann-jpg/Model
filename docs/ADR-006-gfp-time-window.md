# ADR-006 — GFP `time_window` must bound the graph

**Status:** Provisional — hypothesis under test
**Date:** 2026-09-18
**Decision:** Set GFP's `time_window` to **2 days**, not the 10-day corpus span. A window
equal to the corpus disables eviction and makes extraction fail to terminate in useful
time.

---

## Context

`DEFAULT_GFP_PARAMS` initially set `time_window` to 10 days — the full span of HI-Small.
The intent was "let the model see everything". The effect was the opposite of intended.

GFP maintains a continuous-time dynamic graph and evicts edges older than
`time_window`. Setting the window to the corpus span means **nothing is ever evicted**:
the graph grows monotonically to all 4.49M inter-account edges, and every one of the
5,077,237 `transform` calls searches a structure that is larger than the last. Cycle
detection over a growing graph degrades superlinearly.

## Evidence

Instrumented progress from the 10-day run:

| Progress | Throughput | Projected remaining |
|---:|---:|---:|
| 4.9% | 13,596 tx/s | 5.9 min |
| 9.8% | 12,735 tx/s | 6.0 min |
| 14.8% | 8,395 tx/s | 8.6 min |
| 19.7% | 5,383 tx/s | 12.6 min |
| 24.6% | 3,440 tx/s | 18.5 min |
| 29.5% | 1,664 tx/s | 35.8 min |
| 34.5% | 1,161 tx/s | 47.8 min |
| 39.4% | 870 tx/s | 59.0 min |
| 44.3% | **822 tx/s** | 57.3 min |

Throughput fell **16.5×**, from 13,596 tx/s to 822 tx/s. The run reached 44.3% in 47
minutes with roughly another hour outstanding, and was terminated.

Two things follow directly:

1. **The early benchmark was worthless.** Measuring 17,500 tx/s over the first 20,000
   transactions sampled an almost-empty graph and overestimated the full run by an order
   of magnitude. Any throughput claim for a stateful streaming component must be
   measured at steady state, not at startup.
2. **The 10-day window fails gate P8** (>1,000 tx/s extraction throughput), and was
   already failing it by 34.5% of the way through.

## Verification in progress

The causal claim above is **not yet confirmed**. A 2-day run tracks the 10-day run
almost exactly through the first fifth of the corpus:

| Progress | 10-day | 2-day |
|---:|---:|---:|
| 4.9% | 13,596 tx/s | 12,539 tx/s |
| 9.8% | 12,735 tx/s | 12,484 tx/s |
| 14.8% | 8,395 tx/s | 8,118 tx/s |
| 19.7% | 5,383 tx/s | 5,155 tx/s |

That is consistent with the hypothesis rather than against it: 19.7% of 5,077,237 rows
is ~1M transactions, and day 1 alone holds 1,114,921. Neither configuration has reached
its eviction horizon yet, so both are still accumulating. **The windows cannot diverge
until roughly 37%** (the end of day 2).

If the 2-day curve is still tracking the 10-day curve past 44%, the window is not the
cause and the real driver is something that grows regardless of edge eviction — most
likely the vertex map, which retains all 515,088 accounts however old their edges are.
This ADR is to be corrected rather than defended if that is what the data shows.

## Decision

`time_window = 2 days`, with the dependent windows clamped to not exceed it
(`vertex_stats_tw`, `scatter-gather_tw`, `temp-cycle_tw`, `lc-cycle_tw`). Exposed as
`--window-days` on `run_graph` so the sensitivity study is a flag, not an edit.

## Why this is the right setting, not merely the fast one

A bounded window is **more** defensible than an unbounded one:

* **Operationally.** No real-time AML system holds ten days of complete transaction graph
  in memory to score a single payment. A bounded lookback is what production actually
  does, so measuring with one measures the deployable system.
* **Statistically.** Median pattern duration is 3 days and the 95th percentile is 6d17h
  ([ADR-002](ADR-002-boundary-policy.md)), so a 2-day window still spans most of a
  typical laundering chain while excluding structure far too old to be causally related.
* **Scientifically.** Window size is a parameter the result depends on, so v3 §26.3
  requires reporting sensitivity to it. Making it configurable converts a mistake into a
  required experiment.

## Consequences

* Extraction throughput should stay roughly flat instead of collapsing, because the
  graph reaches a steady-state size and stops growing.
* **A window-sensitivity study is now required**, not optional: 1, 2 and 3 days, with
  PR-AUC and throughput reported for each. A model that only works at one exact window
  is overfitted to that window.
* The 10-day configuration is retained as a documented data point — it is the evidence
  for this decision, and its P8 failure is a genuine finding about unbounded graph
  retention rather than an implementation defect.
* Comparisons must hold the window fixed. Window size changes both feature semantics and
  cost, so an E2 at 2 days and an E5 at 3 days are not comparable.

## Revisit if

A variant's pattern durations are materially longer than HI-Small's, or the sensitivity
study shows PR-AUC still climbing at 3 days — in which case the accuracy/throughput
trade-off should be re-chosen on the measured curve rather than on this reasoning.
