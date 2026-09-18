# ADR-003 — Trimming the generator's sparse tail

**Status:** Accepted
**Date:** 2026-09-18
**Decision:** Drop the trailing low-volume days from every IBM AML variant before
splitting, and exclude absolute-calendar features from the model.

---

## Context

The single-feature sanity baseline (plan v3 §14.1) flagged something wrong immediately:

```
single_feature:tx_day_of_week   PR-AUC = 0.0926
[E1 full model]                 PR-AUC = 0.0829
```

One raw calendar feature, used alone, beat the entire trained model. Plan v3 §14.1
describes this check as an early warning; here it fired on the first run.

## Investigation

HI-Small's daily profile explains it. Background transaction generation stops after
2022-09-10, but the injected laundering patterns keep running to 2022-09-18:

| Date | Rows | Positives | Laundering rate |
|---|---:|---:|---:|
| 2022-09-09 | 552,206 | 464 | 0.084% |
| 2022-09-10 | 208,325 | 442 | 0.212% |
| 2022-09-11 | 396 | 232 | **58.6%** |
| 2022-09-12 | 281 | 170 | **60.5%** |
| … | … | … | … |
| 2022-09-18 | 11 | 8 | **72.7%** |

The trailing 1,108 transactions are ~59% laundering against a 0.10% corpus base rate —
a **~290× enrichment** — and they held 655 of the corpus's 5,177 positives.

Under a chronological split the test window covered 2022-09-09 onward, so those days
landed in test and contributed 42% of all test positives from 0.15% of test rows. Any
feature that merely identifies "this row is in the tail" therefore behaves like a
near-perfect classifier. `day_of_week` did exactly that: within the test window,
`dow ∈ {0,1,2,3,6}` occurred *only* in the tail, giving those values a ~290× enrichment.

This is an artifact of how the data was generated, not a detection problem.

## Decision

**Two changes.**

1. **Trim the trailing sparse days** (`flowguard.data.windowing.trim_sparse_tail`).
   A trailing run of days holding under 5% of the median daily volume is dropped. The
   real cliff is ~500× (208,325 → 396), so the threshold is not delicate. Only a
   *trailing* run is removed — a quiet day mid-corpus is real variation and is kept.

2. **Remove absolute-calendar features.** `day_of_week` and `is_weekend` are gone from
   `TransactionFeatures`. Over a ~10-day corpus they are near-collinear with the
   calendar date, so under a chronological split they encode *when in the test window*
   a row sits rather than anything about its behaviour. `hour` and `minute_of_day`
   remain: within-day position repeats across every day and is genuinely behavioural.

## Consequences

* HI-Small becomes 5,077,237 rows (−1,108), 4,522 positives (−655), base rate 0.0891%.
* **The span becomes 9 days 23:59 — which is the "10 days" the source material
  describes.** The nominal 17-day span was always this artifact.
* Measured effect on E1, before → after:

  | | Before trim | After trim |
  |---|---:|---:|
  | Best single feature | 0.0926 (`day_of_week`) | 0.0019 (`amount`) |
  | Full model PR-AUC | 0.0829 | 0.0424 |
  | Ratio, model ÷ best single feature | **0.9× (inverted)** | **22×** |

  The headline PR-AUC halves. That is the point: the earlier number was measuring the
  generator's tail, not laundering.
* Trimming discards 655 real positives. This is a deliberate trade: they sit in a region
  where laundering is the *majority* class, which is neither representative of the
  detection problem nor useful for training a model meant to find rare events.
* The trim is recorded in `dataset_summary.json` (`window_trim`), including the exact
  cutoff, rows and positives dropped, and the full daily profile.

## Revisit if

A variant is used whose background traffic and pattern injection end together, in which
case no tail exists and `trim_sparse_tail` is a no-op by construction.
