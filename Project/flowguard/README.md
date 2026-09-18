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

## Status

Phase 0 (environment) complete and gated. Phase 2 (dataset acquisition) is blocked
on the dataset decision recorded in [`docs/README.md`](../../docs/README.md).
