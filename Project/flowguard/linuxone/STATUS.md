# LinuxONE deployment — status as of 2026-09-23

State of the FlowGuard AML pipeline on the datathon's IBM LinuxONE VM: what is
deployed, what has actually been run there, what does not work, and what is
left. Every number below was measured on the machine, not estimated.

---

## 1. The machine

```
IBM LinuxONE · s390x · big-endian
Linux 5.14.0-570.42.2.el9_6.s390x  (Ubuntu 22.04 userspace on an el9_6 kernel)
Python 3.10.12 · 2 vCPUs · 5.62 GB RAM (3.90 GB available) · NO SWAP
52.7 GB disk · no GPU
Jupyter at http://148.100.112.165:38888/lab
```

The cloud console labels the image "RHEL9.6" and `/etc/os-release` says Ubuntu
22.04.1. Both are true: an Ubuntu userspace on a RHEL host kernel. glibc 2.35
confirms the userspace.

**No swap is the detail that matters.** Under memory pressure this box does not
slow down and recover — it thrashes on page reclaim and can take the Jupyter
server down with it.

---

## 2. ⚠ Current VM state: needs a restart

As of the last check the VM is **unresponsive**. Port 38888 still accepts TCP
connections, so `jupyter-lab` is alive, but it has not answered an HTTP request
in ~40 minutes.

**Cause:** an attempt to train XGBoost on the full 5.08M-row corpus. The
`QuantileDMatrix` build exhausted the remaining RAM and, with no swap, the box
entered reclaim thrashing.

**Fix:** restart the VM (or the Jupyter service) from the LinuxONE console.
Nothing on disk is at risk — every artifact was written and closed before this
happened.

---

## 3. What is deployed on the VM

```
~/data/IBM_Dataset/            100 MB   the corpus, gzipped
    HI-Small_Trans.csv.gz       89.8 MB  (475.7 MB uncompressed, 5.3x)
    HI-Small_accounts.csv.gz     9.8 MB
    HI-Small_Patterns.txt        0.3 MB  must stay uncompressed
~/flowguard_linuxone/         0.45 MB   code
    src/flowguard/                       51 .py files
    linuxone/                            the two notebooks + README
    configs/experiment.yaml
~/flowguard_outputs/          ~8.8 GB   generated
    HI-Small_features.h5        4.05 GB  full-corpus feature matrix
    HI-Small_gfp_npy_cache/     ~4.5 GB  26 GFP chunk parts
    HI-Small_Trans_*.csv        ~167 MB  cached day windows
    *.png, *.json, *.csv, *.npy  ~50 MB  charts, models, metrics
```

pandas reads `.csv.gz` transparently, so the 475 MB plain CSV never has to
exist on this disk. `Patterns.txt` stays uncompressed because `parse_patterns`
opens it with a plain `open()`, not through pandas.

The code is at `~/flowguard_linuxone/`, deliberately **not** `~/flowguard/` —
that directory holds a different, older FlowGuard project (one with
`generator.py` / `scenarios.py` and synthetic data). Merging them would have
tangled two codebases.

### Nothing pre-existing was modified

Created three new directories (`data/`, `flowguard_linuxone/`,
`flowguard_outputs/`). No file that was already on the VM was edited or
deleted. Untouched: `~/flowguard/`, the four demo notebooks, `clients.csv`,
`transactions.csv`, `transactions_history.csv`, the 1.5 GB granite GGUF,
`loan_demo/`, `sample_data/`, `shared/`, `thinc-bigendian-ops/`,
`flowguard.tar.gz`.

**One exception worth stating plainly:** four Jupyter *kernels* were shut down
to reclaim RAM — three that had been idle for 1–2 days, plus one of ours. That
destroys live variables in those sessions. Notebook *files* are untouched, but
any unsaved in-memory state from those sessions is gone.

Disk added is roughly 8.9 GB of the 52.7 GB. The GFP cache and the windowed
CSVs are both reproducible and safe to delete; the HDF5 is what `02` trains
from.

*These file-state claims are from our own record of actions — they could not be
re-verified because the VM went unresponsive.*

---

## 4. What has been validated on the machine

`01_prepare_and_baseline.ipynb`, run end to end with its shipped defaults:

```
1,137,240 rows (2022/09/08–09) · 6.3 min · 2.50 GB peak
```

| | PR-AUC | lift | recall@1% |
|---|---|---:|---:|
| E0 rule baseline | 0.0007 | 1.0x | 1.6% |
| E1 transaction-only | 0.0198 | 26.6x | 33.1% |
| **E2 GFP + behaviour** | **0.0311** | — | — |

All three leakage checks pass (random, constant, shuffled-label). Nine charts,
both XGBoost models, `results.json` and the HDF5 are written.

Scale clearly helps: E2 was 0.0218 at 654k rows and 0.0311 at 1.14M.

### snapml's Graph Feature Preprocessor works on s390x

The project's biggest open question, now settled. `snapml 1.16.0` constructs
`GraphFeaturePreprocessor`, accepts the hyphenated params and emits **215
engineered features** at **4,000–8,000 tx/s**. ADR-001 only ever established
that the *Windows* wheel lacks the backend; s390x had never been tested. The
graph-lite fallback remains but is not needed here.

### Full-corpus feature extraction completes

On the complete 5,077,237-row corpus (515,078 accounts, 4,522 positives,
0.0891% base rate — matching `configs/experiment.yaml` exactly):

- GFP ran over **every edge** at 4,058 tx/s (18.4 min)
- 166 of 215 features vary
- a **4.05 GB, 189-feature HDF5** was written
- peak 3.79 GB

On 2 vCPUs and 6 GB. This is the efficiency claim, and it is real.

---

## 5. What does not work

### Full-corpus XGBoost training

Feature extraction scales; the final fit does not. `QuantileDMatrix` over
3.55M × 189 exceeds what remains after the pipeline, even at `max_bin=128`
with 50k batches. With no swap it thrashes rather than failing cleanly — this
is what took the VM down.

**Unattempted fix:** external-memory XGBoost — `DMatrix` with `cache_prefix`,
spilling to the ~24 GB of free disk. xgboost 2.0.3 supports it. This is the
single remaining piece for a genuine full-corpus result.

### TensorFlow / Keras — environment-level, not our code

`02_keras_model.ipynb` **cannot run on this image.** `tensorflow 2.9.3`
requires `protobuf < 3.20`; the image ships `7.35.1`. Setting
`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` gets the import through, but
constructing any Keras layer then raises *"RepeatedCompositeFieldContainer
object does not support item assignment"*. Nothing installable fixes it on
s390x.

Corroboration: the datathon's own `Fraud_LSTM_Keras_TF.ipynb` and
`Digit_Class_TensorFlow.ipynb` carry **zero saved outputs**, consistent with TF
never having run on this image.

`02` now fails on its first cell with that explanation rather than a protobuf
traceback thirty cells deep.

**`torch 2.1.0a0` does work** (source-built for s390x, 2 threads) with the same
env var set before import. A neural model is viable — `02` needs porting from
Keras to PyTorch.

---

## 6. Memory: the governing constraint

Usable RAM is ~3.90 GB of 5.62 GB after the OS, Jupyter and this kernel's
imports.

The original design cost ~3,150 B/row, i.e. 16.7 GB for the full corpus. Two
changes brought it to ~720 B/row:

**Streaming.** The feature matrix is never materialised. Each GFP chunk is read
from disk, joined to its transaction and behaviour features, written to HDF5
and dropped; XGBoost trains through `QuantileDMatrix` over a `DataIter` reading
that file back. Rows go in chronological order, which — because the split is a
hard chronological cut — makes train/val/test three contiguous ranges, so a
partition is one slice.

**Dtype slimming.** pandas has no pyarrow here, so every string is a Python
object: one account id costs **61 bytes**, not 4. int32 account codes plus
categoricals took the frame from **2,799 MB to 223 MB** at full scale (551 → 44
B/row, 12.5x, measured).

| | before | after |
|---|---|---|
| 654k rows | 2.55 GB | — |
| 1.14M rows | **OOM-killed** | **2.50 GB** |
| 5.08M feature extraction | impossible | **3.79 GB, works** |
| 5.08M training | impossible | still does not fit |

---

## 7. Defects found by running it

Five, none of which static review would have caught. All fixed and committed.

1. **Path auto-detection missed the deployed directory** — it guessed names and
   never guessed `flowguard_linuxone`. Now globs `$HOME/*/src`, which matters
   because a bare kernel starts in `$HOME`, not the notebook's directory.
2. **`attach_report.positive_coverage` does not exist** — it is a key in
   `to_metadata()`, not an attribute.
3. **Stale GFP chunks leaked.** `GFPFeatures.run_streaming` clears old parts
   with `glob("part_*.parquet")`, which never matches the `.npy` parts the
   subclass writes, so a shorter second run read the previous longer run's
   chunks too.
4. **A real bug masquerading as "snapml unavailable".** That stale-chunk
   mismatch was swallowed by a broad `try/except` around the whole GFP block
   and reported as snapml being missing — silently substituting weaker fallback
   features while still printing a plausible PR-AUC. The first apparently
   successful full run said `feature_source: graph_lite_fallback` and was very
   nearly reported as a win. The `try` now covers only the availability probe;
   anything downstream raises, and two asserts check alignment.
5. **`CategoricalEncoder.transform` broke on categorical input** —
   `.map(mapping)` on a categorical returns a categorical, and `.fillna(-1)`
   then raises because -1 is not a category. Fixed in
   `src/flowguard/features/transaction.py`; string and object input unaffected.

Number 4 is the one worth remembering: a fallback that catches real defects
does not degrade gracefully, it lies.

---

## 8. Next

1. **Restart the VM.** Nothing else can proceed until Jupyter answers again.
2. **External-memory XGBoost** for genuine full-corpus training — the one
   remaining gap in the scale story.
3. **Port `02` to PyTorch**, since TensorFlow is unusable here.
4. Optional: an ADR recording GFP-on-s390x, which is a real finding and fits
   this repo's existing practice of documenting platform decisions.

## 9. Reproducing

```bash
cd ~/flowguard_linuxone/linuxone
jupyter lab --no-browser --port 8888
```

Open `01_prepare_and_baseline.ipynb` → Run All. Both paths auto-detect; no
edits needed. `WINDOW_DAYS` defaults to `("2022/09/08", "2022/09/09")`, the
largest window validated end to end.

Widen it freely for feature extraction — re-measure before training.

**Never run `pip install -e .` on this VM.** `pyproject.toml` targets the x86
dev machine (Python 3.12, pyarrow, shap, numpy≥2, snapml 1.17.2, xgboost≥3),
and on s390x most of those have no wheel at all.
