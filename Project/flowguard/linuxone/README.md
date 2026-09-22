# FlowGuard on IBM LinuxONE

Everything needed to train, test and validate the AML models on the datathon
VM. **Nothing here installs anything** — it uses only packages already present
in that environment's `pip list`.

Target: IBM LinuxONE (s390x, big-endian), Ubuntu 22.04.1 LTS, 2 vCPUs, 6 GB
RAM, 50 GB disk, no GPU.

---

## Contents

| File | Purpose |
|---|---|
| `01_prepare_and_baseline.ipynb` | Raw CSV → features → XGBoost baselines (E0/E1/E2) → **exports `*_features.h5`** |
| `02_keras_model.ipynb` | Loads that HDF5 → trains a Keras/TensorFlow DNN → compares against the trees |
| `data/` | Where the generated `*_features.h5` can live (outputs default to `~/flowguard_outputs/`) |

Run them in order. `01` is the expensive one (feature extraction dominates);
`02` reuses its output, so model iteration costs minutes rather than a full
re-extraction.

---

## Setup

### 1. Get the code onto the VM

    scp flowguard_vm_bundle.zip linux1@148.100.112.165:~/
    ssh linux1@148.100.112.165
    unzip flowguard_vm_bundle.zip -d ~

### 2. Get the dataset onto the VM

Three files, ~510 MB total, from the IBM AML-World corpus:

    HI-Small_Trans.csv      ~476 MB
    HI-Small_accounts.csv    ~34 MB
    HI-Small_Patterns.txt   ~0.3 MB

Put them anywhere under `$HOME` — the notebooks find them. `~/data/IBM_Dataset/`
is checked first, so that is the fastest location.

### 3. Run

    cd ~/flowguard/linuxone
    jupyter lab --no-browser --port 8888

Open `01_prepare_and_baseline.ipynb` and Run All, then `02_keras_model.ipynb`.

---

## Do NOT `pip install -e .`

This repo's `pyproject.toml` requires Python 3.12, pyarrow, shap, numpy≥2,
snapml 1.17.2 and xgboost≥3 — it targets the x86 development machine, not this
one. Installing it would try to change the provided environment, and on s390x
most of those packages have no wheel at all, so a failed install can leave you
worse off than before.

The notebooks never need it: they put `src/` on `sys.path`, and `01` asserts at
import time that the source tree is the copy actually in use.

---

## First run

Set `SAMPLE_ROWS = 300_000` in the paths cell of `01` for a fast end-to-end
proof before committing to the full ~5.08M-row run. Peak RSS is printed at
every stage against the 6 GB budget.

Afterwards, check `results["E2"]["feature_source"]`:

- `"gfp"` — snapml's Graph Feature Preprocessor worked
- `"graph_lite_fallback"` — it did not, and E2 used weaker pandas-only
  substitute features. The run is still valid, but it is **not** the
  pre-registered GFP feature set, so say so in any write-up.

---

## The HDF5 export

`01` writes `HI-Small_features.h5`. Rows are stored **train, then val, then
test**, contiguously, so a data generator can slice a whole partition as one
range.

| Dataset | Type | Notes |
|---|---|---|
| `X` | float32 `(n, d)` | the feature matrix |
| `y` | int8 `(n,)` | 1 = laundering |
| `split` | int8 `(n,)` | 0 train, 1 val, 2 test |
| `timestamp` | int64 `(n,)` | epoch seconds |
| `amount` | float64 `(n,)` | |
| `transaction_id`, `pattern_type`, `scenario_id`, `source_account`, `destination_account` | vlen str | evaluation metadata |
| `feature_names` | vlen str `(d,)` | column order of `X` |

Attributes carry `n_train` / `n_val` / `n_test`, `n_features`,
`gfp_feature_source`, `base_rate`, the split boundaries and the creation time.

**NaNs are preserved on purpose.** XGBoost handles them natively and uses them
as signal — GFP leaves self-transfer rows NaN by design. `02` imputes them
(after scaling) because Keras cannot: a single NaN gives a NaN loss and a dead
model on epoch 1.

HDF5 rather than `.npy` or pickle: one self-describing file, streams in bounded
RAM via h5py, and is endian-safe on s390x. Nothing in this directory writes a
pickle — a pickle is tied to the exact numpy/sklearn build that wrote it, which
on a big-endian machine is a portability problem waiting to happen.

---

## Outputs

Both notebooks write to `~/flowguard_outputs/` (override with
`FLOWGUARD_OUTPUT_DIR`).

**Models:** `e1_model.json`, `e2_model.json` (XGBoost native JSON),
`dnn_model.h5` (Keras 2.9 predates the `.keras` format), plus
`dnn_scaler_mean.npy` / `dnn_scaler_scale.npy`.

**Metrics:** `results.json`, `dnn_results.json`, `comparison.csv`,
`dnn_comparison.csv`, `e2_test_predictions.csv`.

**Charts (14):** `daily_profile`, `pr_curves`, `roc_curves`,
`score_distribution`, `budget_recall_precision`, `confusion_matrices`,
`e2_feature_importance`, `typology_recall`, `caught_patterns_graph`,
`dnn_training_history`, `dnn_pr_curve`, `dnn_confusion_matrices`,
`dnn_score_distribution`, `dnn_typology_recall`.

---

## A note on the metrics

Accuracy is deliberately absent everywhere. At a ~0.089% base rate a model that
never fires scores 99.9%. The headline is **PR-AUC**, with recall and precision
reported at alert budgets (0.1% / 0.5% / 1% / 5%) — the fraction of
transactions an investigation team could actually review.

Both notebooks score through the same `flowguard.evaluation.metrics.evaluate()`
so the DNN and the tree models are directly comparable. Keras' own
`AUC(curve="PR")` is used only for early stopping: it approximates over ~200
histogram buckets, which at this base rate is too coarse to report.

Disk budget: ~510 MB dataset + ~4.6 GB transient GFP cache + ~2 GB HDF5 +
~50 MB outputs ≈ 7 GB of the 50 GB available.
