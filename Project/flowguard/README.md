# FlowGuard — the Python package

The implementation behind the [root README](../../README.md): ingestion, leakage-safe
splits, GFP graph features and account-behaviour features, XGBoost, the validation gates,
fund tracing, evidence bundles and batch scoring. The modelling specification is
[`docs/FlowGuard_ML_Pipeline_Plan_v3.md`](../../docs/FlowGuard_ML_Pipeline_Plan_v3.md);
current results are in [`docs/STATUS.md`](../../docs/STATUS.md).

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
* **`transform` inserts.** Snap ML's `transform(batch)` adds the batch to the graph
  *and* computes its features. Never follow it with `partial_fit` on the same batch —
  that inserted every edge twice until 2026-09-22
  ([ADR-015](../../docs/ADR-015-gfp-double-insertion.md)). `partial_fit` is only for
  loading history you do not need features for.
* **Editing `.sh` files from Windows Python** — `Path.write_text` silently writes
  CRLF and bash then fails with `set: pipefail: invalid option name`. `.gitattributes`
  pins `*.sh` to LF; use `write_bytes` when scripting edits.

## Running the pipeline

```bash
# 1. Ingest: raw CSV -> canonical Parquet + dataset_summary.json
python -m flowguard.pipeline.ingest --variant HI-Small

#    (the benchmark protocol uses the full corpus: add --min-density 0 --out-dir <data>/processed/benchmark)

# 2. Baselines: sanity checks, E0 rules, E1 transaction-only XGBoost
python -m flowguard.pipeline.run_baseline --variant HI-Small

# 3. Benchmark runs: GFP extraction, optional tuning, five seeds (see WINNING_PLAN.md)
python -m flowguard.pipeline.run_benchmark --processed-dir <benchmark dir> \
    --cache <benchmark dir>/gfp_paper_b1 --batch-size 1 --paper-params \
    --no-payment-type --behaviour --drop-timestamp-stats --n-estimators 3000 \
    --params-from <tuned run>.json --out run.json

# 4. The shipped package: every gate, then models/flowguard_V2_v1/
python -m flowguard.pipeline.run_validation --processed-dir <benchmark dir> \
    --gfp-cache <benchmark dir>/gfp_paper_b1 --model-id V2 --artifact-free --behaviour \
    --drop-timestamp-stats --from-run run.json --n-estimators 3000

# 5. Score a window with its history
python -m flowguard.pipeline.score --package models/flowguard_V2_v1 \
    --transactions <file> --emit-from <timestamp> --out <dir>
```

Frozen experimental rules live in [`configs/experiment.yaml`](configs/experiment.yaml);
results land in `experiments/<id>/record.json` with a flat index in
`experiments/results.csv` (tracked).

## Gotchas already paid for

* **GFP parameter keys are hyphenated**: `scatter-gather`, `temp-cycle`, `lc-cycle`.
  The plan documents' prose uses underscores, which `set_params` rejects with
  `KeyError`. Canonical values live in `tests/integration/test_gfp_environment.py`.
* **Batching lets an edge see its batch-mates.** A fan feature reading 1.0 alone
  reads 4.0 batched with three later edges ([ADR-004](../../docs/ADR-004-gfp-batch-leakage.md)).
  The shipped model uses `batch_size=1`. Measured on HI-Small, batch 128 changes F1 by
  less than noise (WINNING_PLAN S1c vs S1e) — a throughput option, not a free pass.
* **Score with history.** Behaviour features count first-time counterparties and
  dormancy; a window scored cold alerts on ~30% of rows. Use `score.py --emit-from`.
* **Graph experiments cannot be smoke-tested on a stride-sample.** Taking every
  *n*-th transaction destroys the fan-ins and cycles the features detect, so a
  sampled run understates graph value instead of approximating it.
* **Do not add `day_of_week`-style calendar features.** Over a 10-day corpus they
  are collinear with the date and, under a chronological split, identify the test
  window rather than describe behaviour ([ADR-003](../../docs/ADR-003-sparse-tail-trim.md)).
* **Editing `.sh` files from Windows Python** — `Path.write_text` silently writes
  CRLF and bash then fails with `set: pipefail: invalid option name`. `.gitattributes`
  pins `*.sh` to LF; use `write_bytes` when scripting edits.
