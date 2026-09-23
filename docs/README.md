# FlowGuard documentation — what to read, in order

| Read | For |
|---|---|
| 1. [`../README.md`](../README.md) | What the project is and its headline results |
| 2. [`STATUS.md`](STATUS.md) | Every current number, with the protocol it was measured under |
| 3. [`../WINNING_PLAN.md`](../WINNING_PLAN.md) | The dated log of the latest work — including what went wrong |
| 4. [`../PENDING.md`](../PENDING.md) | What is still open |

## Decision records (ADRs)

One decision each, with the evidence. Superseded ones stay, marked, so the reasoning is
auditable.

| ADR | Decision | Status |
|---|---|---|
| [001](ADR-001-gfp-platform.md) | GFP runs on Linux only; extraction in WSL | accepted |
| [002](ADR-002-boundary-policy.md) | Split boundary policy: hard cut | accepted |
| [003](ADR-003-sparse-tail-trim.md) | Trim the generator's sparse tail (A4 protocol) | accepted — not used by the benchmark protocol |
| [004](ADR-004-gfp-batch-leakage.md) | Batches let an edge see later batch-mates | accepted |
| [005](ADR-005-gpu-training.md) | GPU training, device recorded | accepted |
| [006](ADR-006-gfp-time-window.md) | Bound the GFP time window | accepted — figures pre-ADR-015 |
| [007](ADR-007-payment-type-artifact.md) | `payment_type` is a generator artifact | accepted |
| [008](ADR-008-reconstruction-rejected.md) | Reconstruction rejected | **superseded by ADR-015** |
| [009](ADR-009-chunked-extraction.md) | Chunked extraction | accepted |
| [010](ADR-010-contaminated-pre-registration.md) | A contaminated pre-registration is reported, not moved | accepted |
| [011](ADR-011-adaptive-features-rejected.md) | Adaptive features rejected | accepted — figures pre-ADR-015 |
| [012](ADR-012-account-disjoint-proxy.md) | Account-disjoint proxy labels on ETH | accepted — figures re-run, see STATUS |
| [013](ADR-013-degree-skew-dominates-cost.md) | Degree skew dominates extraction cost | accepted — figures pre-ADR-015 |
| [014](ADR-014-cascade-cannot-prefilter.md) | A cheap tier cannot pre-filter | accepted — figures pre-ADR-015 |
| [015](ADR-015-gfp-double-insertion.md) | **Every edge was inserted twice; fixed** — lists every affected result | accepted |

## Findings and plans

| Document | What it is |
|---|---|
| [`FlowGuard_ML_Pipeline_Plan_v3.md`](FlowGuard_ML_Pipeline_Plan_v3.md) | The modelling specification; code docstrings cite its sections ("v3 §12") |
| [`CORPUS_COMPARISON.md`](CORPUS_COMPARISON.md) | HI-Small vs LI-Small |
| [`ERROR_ANALYSIS_A2.md`](ERROR_ANALYSIS_A2.md) | Where the artifact-free baseline fails (pre-ADR-015) |
| [`TRACK_P_PLAN.md`](TRACK_P_PLAN.md) | The completed plan for tracing, evidence, cascade and typology |
| [`COMPLETION_PLAN.md`](COMPLETION_PLAN.md) | The completed Tier A/B/C plan |
| [`OPEN_ITEMS.md`](OPEN_ITEMS.md) | Longer-form discussion of the open research findings |

## Archive

[`archive/planning/`](archive/planning/) holds the superseded planning generations — the
PS9 blueprint, Unified Plan v2, the Track R execution plan, the quick brief, the Track B
brief and an external analysis PDF. [`archive/`](archive/) holds v1. Nothing in the
archive governs current work.
