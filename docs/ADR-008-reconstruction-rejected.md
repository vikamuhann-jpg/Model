# ADR-008 — Periodic preprocessor reconstruction: tried, measured, rejected

> **SUPERSEDED 2026-09-22 by [ADR-015](ADR-015-gfp-double-insertion.md). The conclusion
> below is wrong.** The feature difference it measured came from our own extractor, which
> inserted every edge twice (`transform` + `partial_fit`); the rebuild replayed each edge
> once. With the extractor fixed, rebuilt features are identical at every cadence and the
> four reconstruction tests pass. GFP does not retain hidden state. Kept unedited below as
> the record of what was believed and why.

**Status:** ~~Rejected~~ **Superseded by ADR-015**
**Date:** 2026-09-18
**Decision:** Do **not** rebuild the Graph Feature Preprocessor from the windowed edge
set. It changes the extracted features, so it is unsound regardless of how much time it
saves.

---

## The problem it was meant to solve

[ADR-006](ADR-006-gfp-time-window.md) established that bounding `time_window` helps
37–53% and is **not sufficient**: a 2-day run still decayed 11×, from 12,539 to 468 tx/s
across the corpus, because GFP evicts edges but retains **every vertex it has ever
seen** — 515,078 of them.

The proposed fix (Tier S1 in [COMPLETION_PLAN.md](COMPLETION_PLAN.md)): periodically
discard the preprocessor and replay only the edges still inside the window into a fresh
one, bounding the vertex set to accounts *active* in that window.

The reasoning looked sound. Edges outside the window are evicted and cannot affect any
future feature, so the windowed edge set should be the entire state that matters. Replay
runs against a near-empty graph — the fast regime — and measured at **0.00 s**, so the
overhead was negligible.

## Why it was tested before being trusted

The plan committed in advance:

> If they differ, GFP's state carries something beyond the windowed edge set, the
> optimisation is unsound, and it is abandoned rather than tuned. **The test decides, not
> the throughput number.**

`tests/leakage/test_gfp_reconstruction.py` extracts features for the same stream twice —
once continuously, once with rebuilds inserted mid-stream — and asserts the outputs are
byte-identical.

## Result: it fails

```
FAILED test_reconstruction_is_feature_identical
FAILED test_identical_at_several_rebuild_cadences[50]
FAILED test_identical_at_several_rebuild_cadences[137]
FAILED test_identical_at_several_rebuild_cadences[250]
4 failed, 3 passed
```

Rebuilt features differ from continuously-fed ones, at every cadence tried. The two
control tests passed — rebuilds genuinely occurred (so the failure is not vacuous), and
rebuilding is correctly inert when no window is configured.

**Conclusion: GFP retains state that is not reconstructible from the windowed edges
alone.** The likely mechanism is that vertex statistics carry running aggregates
accumulated since the vertex was first seen, rather than being recomputed from the live
window — in which case an "evicted" edge still influences the statistics of vertices it
touched. That would also explain ADR-006's residual decay: the vertex table is the thing
that grows without bound, and it grows *because* it is stateful, not merely because it is
retained.

## Decision

* `rebuild_every` stays in the code but defaults to `0` and **warns loudly** if enabled.
  It exists only so the regression test can keep asserting the defect.
* The identity tests are marked `xfail(strict=True)`. They currently document a measured
  defect; if a future snapml release makes reconstruction sound, they flip to XPASS and
  say so rather than passing silently.
* **No reported result may use it.**

## Consequences

* **The throughput problem is unsolved.** Extraction on HI-Small costs ~2.5 hours and
  gate P8 fails at steady state (468 tx/s against a 1,000 tx/s target). That is now a
  property of the method as implemented, not a configuration mistake to be tuned away.
* **Tier S2 becomes the load-bearing fix.** It does not make extraction faster, but it
  makes it survivable and resumable — which, after an OOM kill at 98.5% of a 2.5-hour
  run, is the more urgent property.
* Scaling to ETH Phishing (13M edges) or HI-Medium (32M) is now clearly bounded by
  extraction cost rather than by memory alone. The honest move is to **measure and publish
  the envelope** (Tier S5) rather than claim the method scales.
* Remaining avenues, none attempted: sharding the graph by account subset and extracting
  in parallel; a time-sliced extraction with explicitly documented boundary effects; or
  re-implementing the feature families directly, which forfeits the "real GFP" claim that
  [ADR-001](ADR-001-gfp-platform.md) went to some trouble to secure.

## What this cost, and what it bought

Two hours of build and test time for a negative result. That is the correct price: the
alternative was a 10× speed-up silently changing every graph feature in the experiment
the whole project exists to run. The test caught it before any result depended on it,
which is the same reason gate C8 was worth its cost.

## Revisit if

A snapml release changes vertex-statistic handling — the strict-xfail tests will announce
it — or if the extraction cost becomes the binding constraint on a deadline, in which case
sharding is the next thing to try, with the same identity test as its gate.
