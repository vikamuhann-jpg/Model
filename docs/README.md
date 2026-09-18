# FlowGuard documentation — what to read, and in what order

Five planning documents accumulated here with overlapping content and colliding
phase numbers. This file states which one governs what, so nobody builds against
a superseded scope.

## Document lineage

| Document | Role | Status |
|---|---|---|
| [`FlowGuard_ML_Pipeline_Plan_v3.md`](FlowGuard_ML_Pipeline_Plan_v3.md) | **Track R** — the ML pipeline, raw data → validated model package | **Governing** for all modelling work |
| [`FlowGuard_Unified_Plan_v2.md`](FlowGuard_Unified_Plan_v2.md) | Track R + **Track P** (product). §§29–33 are the only source for the product layer | **Governing** for Track P only |
| [`FlowGuard_AI_Master_Project_Blueprint.md`](FlowGuard_AI_Master_Project_Blueprint.md) | PS9 problem framing, functional requirements, regulatory context | Reference |
| [`FlowGuard_AI_PS9_Quick_Brief.md`](FlowGuard_AI_PS9_Quick_Brief.md) | Pitch, demo script, judging narrative | Reference |
| [`Execution_Plan_TrackR.md`](Execution_Plan_TrackR.md) | **Execution plan** — milestones M1–M6, gates, pre-registered targets | **Active working plan** |
| [`OPEN_ITEMS.md`](OPEN_ITEMS.md) | **Open items** — every outstanding problem, proposed fix, build/compute timing | **Review this first** |
| [`ERROR_ANALYSIS_A2.md`](ERROR_ANALYSIS_A2.md) | Where the artifact-free baseline fails — **gates all feature work** (v3 §17.2) | Active finding |
| [`NEED_TO_RESEARCH.txt`](NEED_TO_RESEARCH.txt) | Research Track B brief for a *second* researcher | Unassigned — see open items |
| [`archive/start.txt`](archive/start.txt) | v1 of everything | **Superseded** — do not build from it |

### v3 does not supersede v2

This is the trap the filenames set. v3 **narrows** v2 deliberately: it deletes the
API, dashboard, evidence packages, typology layer, Isolation Forest and IBM
positioning as out of scope, and spends the room on modelling rigour (sanity
baselines, rolling-origin search, calibration, pre-registered gates C1–C8/P1–P9).
Everything v3 removed still lives only in v2 §§29–33.

**So:** modelling question → v3. Product question → v2. Never assume the higher
version number covers more.

### Colliding phase numbers

Both documents number phases from 0, at different section numbers (v2 §7 = Phase 0;
v3 §4 = Phase 0). Cite phases as `v3 Phase 6` or `v2 §16`, never a bare "Phase 6".

## Decision records

| ADR | Subject |
|---|---|
| [ADR-001](ADR-001-gfp-platform.md) | Execution platform for the GFP baseline — **Linux/WSL only** |
| [ADR-002](ADR-002-boundary-policy.md) | Boundary policy is `HARD_CUT`; purge is infeasible on this corpus |
| [ADR-003](ADR-003-sparse-tail-trim.md) | Trim the generator's sparse tail; drop absolute-calendar features |
| [ADR-004](ADR-004-gfp-batch-leakage.md) | GFP extraction must use `batch_size=1` |
| [ADR-005](ADR-005-gpu-training.md) | GPU training + `early_stopping_rounds=100`; results are device-dependent |
| [ADR-006](ADR-006-gfp-time-window.md) | GFP `time_window` must bound the graph (provisional) |
| [ADR-007](ADR-007-payment-type-artifact.md) | `payment_type` is a generator artifact — ablate every headline result |

## Conventions that are enforced, not suggested

* The label field is `is_laundering`. Never `label`, `target`, `y`, or `fraud`.
* Experiment IDs are `E0`…`E7`. The `EXP001_*` scheme in `archive/start.txt` is retired.
* Claims marked **[unverified]** must be confirmed against a primary source before
  they appear in a report or slide. Several dataset statistics in v2 §6.1 and
  several references in v3 §35 carry this flag.

## Decisions taken

| Decision | Choice | Date |
|---|---|---|
| Execution platform | WSL2 Ubuntu 24.04 / CPython 3.12 (see [ADR-001](ADR-001-gfp-platform.md)) | 2026-09-18 |
| Primary dataset | **IBM AML HI-Small** (the Kaggle "IBM Transactions for Anti-Money Laundering" corpus) | 2026-09-18 |
| Scope | **Track R only** -- terminus is the validated model package of v3 §26.4. No API, dashboard or evidence layer. | 2026-09-18 |
| Track B (`NEED_TO_RESEARCH.txt`) | Off the critical path. Not staffed. | 2026-09-18 |

Because scope is Track R only, **`FlowGuard_ML_Pipeline_Plan_v3.md` is the governing
document for all work.** v2 §§29–33 are retained for reference but are not being built.

## Open items

1. **Kaggle credentials** — *blocks v3 Phase 1.* The HI-Small corpus needs a
   `kaggle.json` API token at `%USERPROFILE%\.kaggle\kaggle.json` (Kaggle → Account →
   Create New API Token), or a manual browser download. Nothing can be ingested until
   the files are local and checksummed.
2. **Verify HI-Small's real schema against the contract.** v2 §6.1's statistics are
   flagged unverified in the plan itself and must be re-derived from the downloaded
   files into `dataset_summary.json`. The raw columns (`Timestamp`, `From Bank`,
   `Account`, `Amount Received`, `Receiving Currency`, `Payment Format`,
   `Is Laundering`) need mapping to the canonical schema, and account identity there is
   a *(bank, account)* pair rather than a single column — the loader must resolve that.
3. **Boundary policy for the real corpus.** The splitter defaults to `PURGE` with a
   buffer derived from the longest observed pattern. On a 10-day corpus that may purge
   too much; decide against the real pattern-duration distribution and record it.
4. **WSL memory ceiling.** The 16 GB host gives WSL 7.6 GiB by default. HI-Small is
   ~5 M transactions; raise it via `%USERPROFILE%\.wslconfig` (`memory=12GB`) before
   ingestion. Requires `wsl --shutdown`.
5. **WSL has no outbound network.** `apt` and PyPI are both unreachable — the gateway
   itself does not answer (campus network, `saveetha.in` search domain). Worked around
   with an offline wheelhouse (`scripts/refresh_wheelhouse.ps1`). The real fix is
   likely `networkingMode=mirrored` in `.wslconfig`, but that is machine-wide and may
   affect Docker Desktop, so it needs a deliberate decision.
