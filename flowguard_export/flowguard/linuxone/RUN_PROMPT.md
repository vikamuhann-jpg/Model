# Run prompt

Paste everything below the line into a fresh session (Claude Code, another
assistant, or hand it to an engineer) on the machine that should run this.
It is self-contained: it assumes no knowledge of the project.

---

You are setting up and running **FlowGuard**, an anti-money-laundering
detection pipeline, on this machine. Work through it in order and stop at the
first thing that does not hold.

## What this directory is

```
linuxone/
    01_prepare_and_baseline.ipynb   raw CSV -> graph + behaviour features ->
                                    XGBoost E0/E1/E2 -> 9 charts -> HDF5 export
    02_keras_model.ipynb            that HDF5 -> Keras DNN -> compared to the trees
    README.md                       runbook
    STATUS.md                       measured results and known limits
    data/IBM_Dataset/               the corpus (may be absent; see below)
../src/flowguard/                   the package the notebooks import
../configs/experiment.yaml          the frozen experimental rules
```

`01` must run before `02`. `01` is the expensive one; `02` reads its output, so
model iteration costs minutes rather than a full re-extraction.

## 1. Check the platform first

**Linux is strongly preferred.** The graph features come from
`snapml.GraphFeaturePreprocessor`, and the Windows wheel ships the Python
wrapper with **no native backend** — its binaries export zero `gf_*` symbols.
On Windows the notebook detects this, falls back to a weaker pandas-only
feature set, and records `feature_source: "graph_lite_fallback"`. That run is
still valid but is **not** the real result, so say so in anything you report.

Verified working: Linux x86_64, and Linux s390x (IBM Z, big-endian).

## 2. Dependencies

Needed: `python 3.9–3.12`, `numpy<2`, `pandas>=2`, `scikit-learn>=1.3`,
`xgboost>=2.0`, `snapml`, `h5py`, `matplotlib`, `seaborn`, `networkx`,
`pyyaml`. `tensorflow` (2.9.x, already on the VM) is needed only for `02`.

**Not needed, deliberately:** `pyarrow` and `shap`. The pipeline uses no
Parquet and takes feature attribution from XGBoost itself.

**Do not run `pip install -e .` on the repo.** Its `pyproject.toml` pins
Python 3.12, pyarrow, shap, numpy≥2, snapml 1.17.2 and xgboost≥3 — that
targets one specific development machine and will fight whatever is installed
here. The notebooks put `src/` on `sys.path` instead and assert at import time
that this is the copy in use.

## 3. The dataset

Three files from IBM's AML-World **HI-Small** corpus (public, on Kaggle):

```
HI-Small_Trans.csv        475.7 MB   (or .csv.gz, 89.8 MB — read transparently)
HI-Small_accounts.csv      34.1 MB   (or .csv.gz)
HI-Small_Patterns.txt       0.3 MB   must stay UNCOMPRESSED
```

`Patterns.txt` cannot be gzipped: `parse_patterns` opens it with a plain
`open()`, not through pandas.

Put them in `linuxone/data/IBM_Dataset/` or `~/data/IBM_Dataset/`. Paths are
auto-detected — walking up from the notebook, then globbing `$HOME` — so no
edits are normally needed. If detection fails it prints every location it
checked; set `RAW_DIR_OVERRIDE` in the paths cell or export
`FLOWGUARD_RAW_DIR`.

## 4. Run

```bash
cd linuxone
jupyter lab --no-browser --port 8888
```

Open `01_prepare_and_baseline.ipynb` → Run All. Then `02_keras_model.ipynb`.

## 5. The one knob that matters: `WINDOW_DAYS`

In the paths cell of `01`. It selects whole days from the corpus and governs
memory. The default is `("2022/09/08", "2022/09/09")`.

| window | rows | peak RAM | notes |
|---|---|---|---|
| `("2022/09/09","2022/09/09")` | 654k | 2.5 GB | smallest useful |
| `("2022/09/08","2022/09/09")` | 1.14M | 2.5 GB | **default, validated** |
| `None` (whole corpus) | 5.08M | 3.8 GB extraction | training needs more — see below |

Per-day row counts, if you want a different window:

```
09/01 1,114,921   09/04   207,430   09/07   482,751   09/10   208,325
09/02   754,449   09/05   482,650   09/08   482,773
09/03   207,382   09/06   482,089   09/09   654,467
```

**Do not pick a window by row count alone.** Day 09/01 is 1.11M rows but only
322 positives (0.029%), so a naive row prefix spends the whole memory budget on
the most positive-poor stretch. Days differ ~6x in base rate.

With ~4 GB usable, feature extraction handles the full corpus but the final
XGBoost fit does not — `QuantileDMatrix` over 3.55M × 189 exceeds it. If this
machine has **8 GB+ free**, try `WINDOW_DAYS = None` for the full corpus; watch
the peak-RSS line printed at every stage. If it has less, keep the default.

## 6. What success looks like

`01` prints a per-stage peak-RSS line and ends with a self-check. On the
reference run (1.14M rows, 6.3 minutes):

| | PR-AUC | lift | recall@1% |
|---|---|---:|---:|
| E0 rule baseline | 0.0007 | 1.0x | 1.6% |
| E1 transaction-only | 0.0198 | 26.6x | 33.1% |
| **E2 graph + behaviour** | **0.0311** | — | — |

Outputs land in `~/flowguard_outputs/` (override with `FLOWGUARD_OUTPUT_DIR`):
9 PNGs, `e1_model.json`, `e2_model.json`, `results.json`, `comparison.csv`,
`e2_test_predictions.csv`, and `*_features.h5` for `02`.

**Two things to check before trusting any number:**

1. All three sanity baselines must print `PASS` (random, constant,
   shuffled-label). A failure means label information is leaking and every
   metric after it is fiction.
2. `results["E2"]["feature_source"]` must be `"gfp"`. If it says
   `"graph_lite_fallback"`, snapml's graph engine was unavailable and E2 used
   substitute features.

Accuracy is deliberately absent everywhere: at a ~0.09% base rate a model that
never fires scores 99.9%. PR-AUC is the headline, with recall and precision at
alert budgets (0.1 / 0.5 / 1 / 5%) — the fraction of transactions an
investigation team could actually review.

## 7. Failure modes

| symptom | meaning |
|---|---|
| Kernel dies with no traceback | out of memory. Narrow `WINDOW_DAYS`. If the machine has no swap it will thrash first and may stop responding. |
| `feature_source: graph_lite_fallback` | snapml could not provide GFP here. Expected on Windows; on Linux check `from snapml import GraphFeaturePreprocessor; GraphFeaturePreprocessor()`. |
| `FileNotFoundError` naming every checked path | dataset or `src/` not found. Use the override shown in the message. |
| `'flowguard' imported from ...` RuntimeError | a pip-installed copy is shadowing the source tree. `pip uninstall flowguard`, restart the kernel. |
| `02` raises about protobuf, or cannot build a layer | the wrong protobuf won. Cell 1 prints which one is loaded and from where: it must be < 3.20, from the system `site-packages`, not `~/.local`. |
| `02` raises `Intra op parallelism cannot be modified after initialization` | TensorFlow was imported before cell 1 ran. Restart the kernel and run cell 1 first. |
| GFP extraction seems stuck | it is single-threaded per edge, ~4,000–11,000 tx/s. 5M rows takes ~18 minutes. Progress prints every 500k. |

## 8. Rules

- Never `pip install -e .` for this repo.
- Never widen `WINDOW_DAYS` without watching the peak-RSS output.
- Never report a number without checking the two conditions in §6.
- If something fails, read the error — the notebooks are written to fail with
  an explanation and the fix, not a bare traceback. Prefer fixing the cause
  over working around it.
