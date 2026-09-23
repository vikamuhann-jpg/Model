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
| `02_neural_model.ipynb` | Loads that HDF5 → trains a **PyTorch** DNN → compares against the trees |
| `data/IBM_Dataset/` | The corpus, gzipped. **Gitignored** — present on disk, never committed |
| `STATUS.md` | **Current deployment state** — what is on the VM, what has been measured there, what does not work |

Run them in order. `01` is the expensive one (feature extraction dominates);
`02` reuses its output, so model iteration costs minutes rather than a full
re-extraction.

---

## Setup

### 1. Get the code onto the VM

    scp flowguard_vm_bundle.zip linux1@148.100.112.165:~/
    ssh linux1@148.100.112.165
    unzip flowguard_vm_bundle.zip -d ~

### 2. The dataset

This folder already carries it, gzipped, at `data/IBM_Dataset/`:

    HI-Small_Trans.csv.gz     89.8 MB   (475.7 MB raw, 5.3x)
    HI-Small_accounts.csv.gz   9.8 MB
    HI-Small_Patterns.txt      0.3 MB   must stay uncompressed

pandas reads `.csv.gz` transparently, so the 475 MB plain file never needs to
exist. `Patterns.txt` stays raw because `parse_patterns` opens it with a plain
`open()`, not through pandas.

`data/` is **gitignored**: `HI-Small_Trans.csv.gz` is 89.8 MB, git history is
permanent, and the IBM AML-World corpus carries its own licence. Anyone
redistributing this should point at the Kaggle source rather than ship the
data. The notebooks also find the corpus at `~/data/IBM_Dataset/` or anywhere
under `$HOME`, so a fresh checkout without `data/` still works once the files
are fetched.

### 3. Run

    cd ~/flowguard/linuxone
    jupyter lab --no-browser --port 8888

Open `01_prepare_and_baseline.ipynb` and Run All, then `02_neural_model.ipynb`.

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

## Validated on the VM, 2026-09-23

`01` was run end to end on the target machine with its shipped defaults:

```
s390x big-endian · Ubuntu 22.04 userspace on el9_6 kernel · Python 3.10.12
2 vCPUs · 5.62 GB RAM (3.90 GB available) · no swap
654,467 rows · 2.5 min · 2.55 GB peak
```

| | PR-AUC | lift | recall@1% |
|---|---|---|---|
| E0 rules | 0.0008 | 1.0x | 1.6% |
| E1 transaction-only | 0.0095 | 13.7x | — |
| **E2 GFP + behaviour** | **0.0218** | **31.4x** | **39.7%** |

All three leakage checks pass. **snapml 1.16.0's GraphFeaturePreprocessor
works on s390x** — 215 engineered features, 153 of which vary on this window,
at ~8,000 tx/s. ADR-001 only ever showed the *Windows* wheel lacks the
backend; s390x had never been tested.

After a run, check `results["E2"]["feature_source"]`. It should say `"gfp"`.
`"graph_lite_fallback"` means snapml stopped being available and E2 used
weaker substitute features — still a valid run, but not the pre-registered
feature set, so say so in any write-up.

## Do not widen WINDOW_DAYS without measuring

`09/08-09/09` (1,137,240 rows) was **OOM-killed** during the E2 assembly.
There is no swap on this box, so the kernel dies outright. The assembly
briefly holds the graph block, all three feature matrices and a concat copy
at once — about 4,000 B/row, because 153 of GFP's 215 columns survive the
constant-prune rather than the ~80 first assumed. The real ceiling is near
**790k rows** for this design.

Going bigger needs the streaming rework: write features to HDF5 chunk-wise
and train through `xgb.QuantileDMatrix` over a `DataIter`. That lifts the
ceiling to roughly 30M rows, because RAM stops scaling with the corpus.

## The neural model is PyTorch, not Keras

`tensorflow 2.9.3` **cannot run on this image**, and it is an environment
problem rather than a defect. TF 2.9 requires `protobuf < 3.20`; the image
carries `7.35.1`. Setting `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` gets
the import through, but constructing any Keras layer then fails with
*"RepeatedCompositeFieldContainer object does not support item assignment"*,
and nothing installable fixes it on s390x. The datathon's own
`Fraud_LSTM_Keras_TF.ipynb` and `Digit_Class_TensorFlow.ipynb` carry no saved
outputs, consistent with TF never having worked here.

`torch 2.1.0a0` — built from source for s390x — does work, so
`02_neural_model.ipynb` uses PyTorch. It needs the same environment variable
set before importing torch, which the notebook does for you.

It mirrors the Keras design it replaces: `StandardScaler` fitted on train only,
NaNs imputed after scaling (GFP leaves self-transfer rows NaN by design, and a
network would propagate that into a NaN loss), `pos_weight` in
`BCEWithLogitsLoss` as the analogue of `scale_pos_weight`, isotonic calibration
on validation, and scoring through the project's own `evaluate()` so the DNN
and the tree models stay comparable.

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
