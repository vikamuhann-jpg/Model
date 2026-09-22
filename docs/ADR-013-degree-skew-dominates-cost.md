# ADR-013 — Extraction cost is driven by degree skew, not corpus size

> **Note 2026-09-22:** figures in this record were computed with the extractor that inserted every edge twice. See [ADR-015](ADR-015-gfp-double-insertion.md) for what was re-run and the corrected values.

**Status:** Accepted
**Date:** 2026-09-20
**Decision:** Treat the P8 throughput gate and the S5 scaling envelope as
**generator-specific**. Neither transfers to a real network, because AMLSim does not
produce the degree distribution real networks have.

---

## What happened

Tier C extraction on a 2M-row ETH slice was abandoned after the cost per 250k-row block
roughly doubled at every checkpoint:

| Rows | Cumulative rate | This block took |
|---|---:|---:|
| 250k | 1,629 tx/s | 2.5 min |
| 500k | 1,174 tx/s | 4.5 min |
| 750k | 497 tx/s | 18 min |
| 1.00M | 238 tx/s | 45 min |
| 1.25M | 139 tx/s | 80 min |

Full extraction projected past **fifteen hours**. The run was stopped and the experiment
completed on the contiguous 1.25M-row prefix that chunked persistence had already saved
([ADR-009](ADR-009-chunked-extraction.md)).

## The explanation I gave first, and why it was wrong

I attributed the collapse to vertex count, citing ADR-008's finding that vertex count
dominates extraction cost.

S5 then ran the same code, same 2-day window, on an HI-Medium prefix and reached
**11,418 tx/s at 1.25M rows** — where ETH had fallen to 139. That is an **80× gap**, and
HI-Medium has *more* vertices, not fewer (1.01M against 331k at equal edge count). More
vertices, far more speed. The explanation was falsified by its own prediction.

## What actually drives it

Degree distribution, measured at equal edge count (1.25M edges each):

| | ETH slice | HI-Medium |
|---|---:|---:|
| vertices | 330,849 | 1,013,373 |
| mean degree | 7.56 | 2.47 |
| median degree | 1 | 2 |
| p99.9 degree | **1,034** | **11** |
| p99.99 degree | **9,962** | **16** |
| max degree | 11,152 | 9,179 |
| share of endpoints on the top 0.01% of vertices | **13.3%** | **1.0%** |

The maxima are comparable, which is what makes the naive comparison misleading.
HI-Medium's 9,179-degree vertex is a **lone outlier in an otherwise near-regular graph** —
its 99.9th percentile is 11. ETH has *thousands* of genuine hubs, and 13% of all edge
endpoints sit on 0.01% of its vertices.

GFP's pattern searches — scatter-gather, fan-in/out, cycles — enumerate over a vertex's
neighbourhood. That work grows super-linearly in degree, so a corpus with a heavy tail of
1,000+ degree vertices costs far more per edge than one with none, at identical size.
**Cost tracks the tail of the degree distribution, not the number of rows or vertices.**

## Consequences

* **P8 (≥1,000 tx/s) is not a transferable gate.** It was pre-registered and measured on
  AMLSim output. On a real network at the same scale the method runs an order of
  magnitude slower, and P8 would fail by a far wider margin than the ~450 tx/s recorded
  on HI-Small.
* **The S5 envelope describes AMLSim, not "this method".** It is still worth publishing,
  but only labelled as such. Extrapolating it to a real deployment would be wrong.
* **This is a cost finding, not a signal finding.** Tier C shows the graph *features*
  transfer and carry real signal on ETH. What does not transfer is the *throughput*.
* **Real networks are scale-free; this generator is not.** That is a property worth
  stating about the corpus generally, since it may affect more than extraction cost — any
  conclusion that depends on neighbourhood size is suspect on AMLSim output.

## What this does not claim

The mechanism is inferred from the degree distributions and the throughput gap, not from
profiling GFP's internals — the library is closed. A direct measurement would time
extraction against synthetically varied degree tails at fixed edge count. That is the
experiment that would turn this from a well-supported explanation into a demonstrated
one, and it has not been run.

## Revisit if

GFP exposes per-pattern timing, or a degree-capped extraction mode becomes available, in
which case capping the neighbourhood searched would trade a known amount of signal for a
bounded cost and could be measured directly.
