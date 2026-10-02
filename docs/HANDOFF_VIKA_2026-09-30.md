# Handoff to Vika - 2026-09-30

**From:** Shivraj  
**To:** Vika  
**Repository checked:** ef882c7 (github.com/vikamuhann-jpg/Model)  
**Date:** 2026-09-30  

---

## What was verified

I read the code, ran the tests locally, recomputed the sample window, and ran both
LinuxONE notebooks from a clean output folder on the VM.

### LinuxONE clean run - confirmed

Both notebooks ran successfully with no reused caches:

| Notebook | Time | Peak RAM |
|---|---:|---:|
| `01_prepare_and_baseline.ipynb` | 6 min 14 s | 2.10 GB |
| `02_keras_model.ipynb` | 4 min 29 s | - |

All self-checks pass in both.

**Results - HI-Small, 2-day window, test = 170,585 rows, 127 positives:**

| Model | PR-AUC | recall@1% |
|---|---:|---:|
| E2 GFP + XGBoost | 0.0325 | 36.2% |
| Keras DNN (seed 42, 150-epoch cap, early stopping) | 0.0389 | 36.2% |

With the longer training cap (150 epochs), the DNN catches exactly as many cases at
1% as E2 (46 of 127). It does not beat the tree model on PR-AUC.

### Confirmed working

- The empty-string typology group is gone (`metrics.py`), and the new test covers it.
- `calibrator.json` + `np.interp` reproduces `scores.csv` to 3e-14.
- `encoders/categorical.json` is present.
- `sample_outputs/`: `window_metrics.json` recomputes exactly from `scores.csv` + `labels.csv`
  (PR-AUC 0.5684 on raw_score, ROC 0.9887, recall@1% 73.7%, 631 alerts, 58 caught).
  Ranks are unique, ties are broken by `raw_score`, and every alert has `top_features`.
- No secrets in the repo.
- Tests run locally on Windows with Python 3.10: **278 passed**.
  Of the 28 failures and 4 errors: 27 need snapml (expected, ADR-001), 1 needs pyarrow and
  1 needs numpy 2 to unpickle (both absent by design). The remaining 2 were the claim tests
  in item 1 below - **now fixed in this commit**.

---

## Two things that are yours to fix

### Fix A - One-line Keras import fix in `02_keras_model.ipynb` (5 minutes)

**The bug.** Cell 1 imports `tensorflow` inside the `sys.path` manipulation window.
TensorFlow imports numpy during that import, so the system numpy 1.22.3 gets loaded
instead of the user-site 1.24.4. The next `import pandas` (2.1.4, which needs numpy >= 1.22.4)
then fails:

```
ImportError: this version of pandas is incompatible with numpy < 1.22.4
```

**The fix** (one line moved - tensorflow must come AFTER the `finally`):

```python
# CORRECT - only google.protobuf inside the window
sys.path.insert(0, _system_site)
try:
    import google.protobuf
finally:
    sys.path = _saved_path
import tensorflow as tf   # tensorflow after, numpy already in sys.modules correctly
```

This fix has already been applied in this local copy. Apply the same change on GitHub.

---

### Fix B - Stale numbers in your docs (10 minutes)

`metrics.json` was regenerated in `2a94e4a`. Two numbers changed:

| Metric | Old (stale) | New (correct) | Files to change |
|---|---:|---:|---|
| recall@1% | 78.0% | **78.3%** | README, CLAIMS_REGISTER, PENDING, WINNING_PLAN, PROBLEMS_3 |
| ACH recall@1% | 84.6% | **84.9%** | README, CLAIMS_REGISTER, PENDING, WINNING_PLAN, PROBLEMS_3 |

These mismatches cause `test_claim_01` and `test_claim_11` to fail. PR-AUC 0.595 is unchanged.

**These fixes have already been applied in this local copy.** Apply the same changes on GitHub.

---

## Three things to note in the notebook (no training needed)

### Note 1 - BIPARTITE gate rests on one case

In this 2-day window there is exactly **1 BIPARTITE positive**, ranked at the **92.4th
percentile**. A gate decided by a single transaction is not evidence either way. State this
clearly next to the P5 gate result - neither a pass nor a fail on that one case should be
read as a general claim about BIPARTITE detection.

### Note 2 - Blend table weight was chosen on the test set

Cell 22 scores five blend weights **on the test set**. Using this as a diagnostic is fine.
Do **not** report the best row (PR-AUC 0.0556) as a result unless the weight was chosen on
the **validation** set first. Until then it is an optimistic oracle figure, not a result.

### Note 3 - DNN vs XGBoost claim

"The DNN beats XGBoost" is not what the numbers support. Over seeds 42/1/2/3 the DNN's
PR-AUC is 0.0407 / 0.0462 / 0.0231 / 0.0297 against XGBoost's 0.0325 - two of four seeds
below the tree model. The honest claim is: **not better on PR-AUC; consistently finds a
few alerts the trees miss at a fixed budget.** The comparison table should say that.

---

## Recommended order of remaining work

**Quick (today):**
1. Apply the Keras import fix on GitHub (Fix A).
2. Correct the stale numbers in your docs (Fix B).
3. Add the three notebook notes above (BIPARTITE, blend weight, DNN claim).

**Important for judging:**
4. Decide how your model enters the FlowGuard demo (Decision D40 - see below).
5. Add Logistic Regression and re-run Isolation Forest, or document why they were dropped
   (the directive's model order lists both).

---

## Decision D40 - How does your model enter the FlowGuard demo?

Your model was trained on IBM's AML data, which has no customer, branch, product or channel
fields, so it cannot score our synthetic bank data as it stands. Two options:

**Option A - Run the investigation side on IBM data.**
Our graph tracing, typologies, risk engine and evidence package run on IBM's data, with your
model's scores feeding the risk engine. All ML numbers are already measured on that data.

**Option B - You retrain on our synthetic schema.**
Fits the hero demo (dormant account -> layering -> round-trip -> profile mismatch), but
needs your time and a new round of measurements.

**My recommendation is A**, with our synthetic hero case kept as the scripted walkthrough.
I will write up both options formally (D40) before you decide.

---

## Overall project status - ~75% complete

| Area | Done | What's left |
|---|---|---|
| **System core** | ~95% | Nothing major |
| **Validation** | ~90% | Combined system + ML baseline table |
| **ML (Vika)** | ~80% | Logistic Regression missing; Isolation Forest old |
| **ML integrated into FlowGuard** | ~10% | **The biggest gap** - two halves still run separately |
| **IBM integration** (watsonx.ai) | ~75% | Authenticated call from LinuxONE |
| **LinuxONE** | ~70% | FlowGuard system was deleted; must be re-uploaded |
| **Judging material** | ~50% | Q&A pack, claims C1-C9, final demo storyline |

---

*Generated 2026-09-30. All documentation fixes in this handoff have been applied to the local copy.*
