# ADR-002 — Boundary policy for the temporal split

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Use **`HARD_CUT`** for the HI-Small chronological split, not `PURGE`.
This deviates from plan v3 §11's stated order of preference, on measured grounds.

---

## Context

Plan v3 §11 lists three policies for laundering patterns that straddle a split
boundary, in order of preference:

1. **Purge** — drop a buffer around each boundary. "Cleanest; costs data."
2. **Assign by pattern start** — preserves patterns, blurs the boundary.
3. **Hard cut** — split purely on time, accepting truncated patterns.

The plan requires choosing once, documenting it, and reporting the count of affected
patterns. The choice was deferred until the real pattern-duration distribution was
known, because the ranking above is only valid if the buffer is small relative to the
corpus.

## Measurements (HI-Small, 5,078,345 transactions, 5,177 positives, 370 patterns)

### Pattern durations

| Statistic | Value |
|---|---|
| Median | 3 days 02:44 |
| 95th percentile | 6 days 17:16 |
| **Maximum** | **8 days 10:16** |

Against an effective corpus span of ~10 days: days 1–10 hold 5,077,237 transactions
(99.98%), while days 11–18 hold just 1,108. The nominal 17-day span is a thin tail.

### Policy outcomes

| Policy | Train | Val | Test | Dropped | Test positives |
|---|---:|---:|---:|---:|---:|
| Purge (auto buffer = 8d10h) | 0 | 0 | 18 | **5,078,327 (100%)** | 13 |
| Purge (12h buffer) | 3,320,814 | 241,199 | 441,676 | 1,074,656 (21%) | 1,292 |
| Pattern start | 3,555,531 | 761,711 | 761,103 | 0 | 1,025 |
| **Hard cut** | **3,554,957** | **761,749** | **761,639** | **0** | **1,561** |

### Temporal violations

| Policy | Train rows after `train_end` | Train rows after `val_end` | Strict ordering |
|---|---:|---:|---|
| Hard cut | 0 | 0 | **holds** |
| Pattern start | 574 | **238** | fails |

## Decision

**`HARD_CUT`.**

**Purge is infeasible on this corpus.** The longest pattern spans 84% of the effective
data window, so an honestly-sized buffer erases the dataset. A 12-hour buffer discards
21% of the data and still fails to contain the median 3-day pattern — it pays the cost
of purging without buying the guarantee.

**Pattern start leaks.** It places 238 test-period transactions into the training set.
In absolute terms that is 0.0067% of training rows, which sounds negligible — but they
are *pattern* rows, and only 5,177 positives exist in the entire corpus. Those 238
represent ~4.6% of all positives, concentrated in exactly the minority class the model
is being asked to learn. Leakage into a rare class is worth more than its row count
suggests.

**Hard cut has zero temporal violations** and yields the largest test-positive count
(1,561), which stabilises minority-class metrics.

## Consequences

* **140 of 370 patterns straddle a boundary** and are truncated. This is reported with
  every experiment, per v3 §11.
* Of the 181 patterns appearing in test, **81 are fully intact** and 100 are truncated,
  retaining a median 50% of their transactions.
* Truncation is a **detectability** cost, not a correctness one. A fan-in truncated
  half-way is still a fan-in; the model simply observes fewer of its edges. Measured
  recall on truncated patterns is therefore a floor, not an unbiased estimate, and the
  report must say so rather than presenting it as a clean number.
* `SplitSpec.boundary_policy` now defaults to `HARD_CUT`. The other two policies remain
  implemented and tested — this decision is dataset-specific, and a corpus with short
  patterns relative to its span should revisit it.

## Revisit if

The primary dataset changes, or pattern durations become short relative to the corpus
span — in which case purge regains its advantage and v3's original ranking applies.
