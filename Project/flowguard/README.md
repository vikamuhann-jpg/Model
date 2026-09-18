# FlowGuard — Track R (ML research pipeline)

Implements [`docs/FlowGuard_ML_Pipeline_Plan_v3.md`](../../docs/FlowGuard_ML_Pipeline_Plan_v3.md).
Repository layout follows that plan's §5 exactly.

> **Platform: Linux only.** The Graph Feature Preprocessor's native backend ships
> only in `snapml`'s manylinux wheels. On Windows the Python wrapper installs but
> `GraphFeaturePreprocessor()` raises `AttributeError: ... no attribute
> 'gf_allocate'`. See [ADR-001](../../docs/ADR-001-gfp-platform.md).

## Setup

WSL2 Ubuntu 24.04 + CPython 3.12. WSL on this machine has **no outbound network**,
so dependencies install offline from a wheelhouse fetched on the Windows side.

```powershell
# Windows: populate the wheelhouse (once, and whenever deps change)
powershell -File scripts\refresh_wheelhouse.ps1
```

```bash
# WSL: build the venv and verify the GFP gate
wsl -d Ubuntu
cd /mnt/c/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/Project/flowguard
bash scripts/setup_wsl.sh
source ~/flowguard/.venv/bin/activate
```

## Verify the environment

```bash
pytest tests/integration/test_gfp_environment.py -q   # 5 passed
```

This gate is not ceremonial — it is the check that the GFP baseline the whole
research plan rests on can actually run here.

## Layout notes

* `data/` is a **directory junction** to `C:\Users\vikam\flowguard_data`, kept
  outside OneDrive so multi-GB datasets and Parquet artifacts don't sync-thrash.
  It is gitignored.
* `tests/leakage/` is a first-class, merge-blocking test category (plan v3 §27),
  not a subfolder of unit tests.

## Gotchas already paid for

* **GFP parameter keys are hyphenated**: `scatter-gather`, `temp-cycle`, `lc-cycle`.
  The plan documents' prose uses underscores, which `set_params` rejects with
  `KeyError`. Canonical values live in `tests/integration/test_gfp_environment.py`.
* **Feature extraction must precede insertion.** Use `partial_fit` on history then
  `transform` on the new edge; a transaction inserted first inflates its own
  structural features (plan v3 §12).
* **Editing `.sh` files from Windows Python** — `Path.write_text` silently writes
  CRLF and bash then fails with `set: pipefail: invalid option name`. `.gitattributes`
  pins `*.sh` to LF; use `write_bytes` when scripting edits.

## Running the pipeline

```bash
# 1. Ingest: raw CSV -> canonical Parquet + dataset_summary.json
python -m flowguard.pipeline.ingest --variant HI-Small

# 2. Baselines: sanity checks, E0 rules, E1 transaction-only XGBoost
python -m flowguard.pipeline.run_baseline --variant HI-Small

# 3. Graph: E2 = GFP features + XGBoost
python -m flowguard.pipeline.run_graph --variant HI-Small     --cache ~/flowguard_data/processed/HI-Small_gfp.parquet
```

Frozen experimental rules live in [`configs/experiment.yaml`](configs/experiment.yaml);
results land in `experiments/<id>/record.json` with a flat index in
`experiments/results.csv`.

## Status

| Phase (plan v3) | State |
|---|---|
| Phase 0 — environment | Done, gated by `tests/integration/` |
| Phases 1-3 — ingestion, profiling, validation | Done |
| Phase 5 — canonical schema, leakage-safe split | Done |
| Phases 6-7 — streaming graph, feature extraction | Done |
| Phases 8-10 — E0/E1 baselines, training, evaluation | Done |
| Phase 17 — experiment registry | Done |
| E2 — graph baseline | Running |
| Phase 11 — error analysis | Next; **gates** the E3-E7 feature work |

### Measured (HI-Small, 5,077,237 transactions, 4,522 positives)

| Experiment | PR-AUC | Lift | Recall @1% budget |
|---|---:|---:|---:|
| E0 — rules | 0.0011 | 1.0x | 1.0% |
| E1 — transaction-only XGBoost | 0.0424 | 35.7x | 41.1% |

Sanity baselines (random, constant, shuffled-label) all sit at the base rate.

## Gotchas already paid for

* **GFP parameter keys are hyphenated**: `scatter-gather`, `temp-cycle`, `lc-cycle`.
  The plan documents' prose uses underscores, which `set_params` rejects with
  `KeyError`. Canonical values live in `tests/integration/test_gfp_environment.py`.
* **GFP extraction must use `batch_size=1`.** An edge transformed alongside later
  edges in the same batch *sees* them — a fan feature reading 1.0 alone reads 4.0
  when batched with three later edges ([ADR-004](../../docs/ADR-004-gfp-batch-leakage.md)).
* **Graph experiments cannot be smoke-tested on a stride-sample.** Taking every
  *n*-th transaction destroys the fan-ins and cycles the features detect, so a
  sampled run understates graph value instead of approximating it.
* **Do not add `day_of_week`-style calendar features.** Over a 10-day corpus they
  are collinear with the date and, under a chronological split, identify the test
  window rather than describe behaviour ([ADR-003](../../docs/ADR-003-sparse-tail-trim.md)).
* **Editing `.sh` files from Windows Python** — `Path.write_text` silently writes
  CRLF and bash then fails with `set: pipefail: invalid option name`. `.gitattributes`
  pins `*.sh` to LF; use `write_bytes` when scripting edits.
