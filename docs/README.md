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

## Conventions that are enforced, not suggested

* The label field is `is_laundering`. Never `label`, `target`, `y`, or `fraud`.
* Experiment IDs are `E0`…`E7`. The `EXP001_*` scheme in `archive/start.txt` is retired.
* Claims marked **[unverified]** must be confirmed against a primary source before
  they appear in a report or slide. Several dataset statistics in v2 §6.1 and
  several references in v3 §35 carry this flag.

## Open items blocking progress

1. **Which dataset?** — *blocks v3 Phase 1.* The plans waffle between IBM **AMLSim**
   (a generator) and the **AML HI/LI** corpora whose statistics appear in v2 §6.1.
   These are different artifacts with different schemas; `archive/start.txt` §4
   warns explicitly against assuming they are interchangeable. Nothing can be
   ingested until this is fixed and its checksums recorded.
2. **Track R only, or R + P?** — v3 terminates at a validated model package with no
   UI; the PS9 demo needs the dashboard, fund tracing and evidence package from
   v2 §§29–33. This changes the timeline materially.
3. **Is the Track B researcher real?** `NEED_TO_RESEARCH.txt` is addressed to a second
   person. If that person does not exist, it is aspirational and must leave the
   critical path.
4. **WSL memory ceiling.** The 16 GB host gives WSL 7.6 GiB by default. AML HI Small
   is ~5 M edges; raise it via `%USERPROFILE%\.wslconfig` (`memory=12GB`) before
   ingestion. Requires a `wsl --shutdown`.
5. **WSL has no outbound network.** `apt` and PyPI are both unreachable — the gateway
   itself does not answer (campus network, `saveetha.in` search domain). Worked
   around with an offline wheelhouse. The real fix is likely
   `networkingMode=mirrored` in `.wslconfig`, but that is machine-wide and may
   affect Docker Desktop, so it needs a deliberate decision.
