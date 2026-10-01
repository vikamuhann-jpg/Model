# Measurement scripts

These produced numbers that the reports, `docs/STATUS.md`, `docs/TRACK_P_PLAN.md` and the ADRs
quote. They are kept so every one of those numbers can be regenerated, not because anyone
needs them to use the model.

They read from the external data folder. Set `FLOWGUARD_DATA` if it is not at the build
machine's default (`_paths.py`). Run them from `Project/flowguard/` under WSL, with this folder
on `PYTHONPATH` so the shared helpers import:

```bash
cd Project/flowguard
PYTHONPATH=scripts/measure python -u scripts/measure/p1_bench.py
```

| Script | Produces | Cited in |
|---|---|---|
| `p1_bench.py` | Fund-tracing latency by horizon — p95 168.53 ms at horizon 4 | `TRACK_P_PLAN.md` P1 |
| `p2_case.py` | The exported evidence case `FG-18aedbed` | `TRACK_P_PLAN.md` P2 |
| `p3_cascade.py` | Cascade recall and throughput by routing share; `python p3_cascade.py ETH` runs one corpus | [ADR-014](../../../../docs/ADR-014-cascade-cannot-prefilter.md) |
| `p4p6.py` | Typology hinting (P4) and the unsupervised arm (P6) | `TRACK_P_PLAN.md` P4, P6 |
| `tier_c_bootstrap.py` | The paired bootstrap interval on the Ethereum transfer result | `STATUS.md` §5 |
| `degree_skew.py` | The degree-distribution comparison, ETH against HI-Medium | [ADR-013](../../../../docs/ADR-013-degree-skew-dominates-cost.md) |
| `s5_envelope.py`, `s5_parse.py` | The scaling envelope on an HI-Medium prefix, under a 20-minute budget | [ADR-013](../../../../docs/ADR-013-degree-skew-dominates-cost.md) |
| `gslice.py` | Shared helper: reads graph-feature rows for one split, one part file at a time | — |
| `_paths.py` | Shared helper: where the data and the repository are | — |

`gslice.py` exists because reading the whole graph-feature block before slicing it was
OOM-killed at 5.6 GB. Keep using it for anything that touches the graph features of a full
corpus.
