# Resolution Report — Shivraj Handoff (2026-09-30)
**Actioned:** 2026-10-02  

---

## Summary

All items from the handoff that could be actioned locally have been applied. The table below maps each handoff issue to its resolution.

---

## Issues resolved

### 1. `02_keras_model.ipynb` crashes on LinuxONE — **FIXED**

**Root cause:** `import tensorflow as tf` was inside the `sys.path` manipulation window, causing `tensorflow`'s numpy import to pull the system numpy 1.22.3 instead of user-site 1.24.4. The subsequent `import pandas` (2.1.4, needs numpy >= 1.22.4) then failed.

**Fix applied** to [`linuxone/02_keras_model.ipynb`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/Project/flowguard/linuxone/02_keras_model.ipynb) — Cell 1:

```diff
 sys.path.insert(0, _system_site)
 try:
     import google.protobuf
-    import tensorflow as tf   # WRONG - loads system numpy 1.22.3
 finally:
     sys.path = _saved_path
+import tensorflow as tf       # CORRECT - numpy already fixed in sys.modules
```

Verified: the fixed notebook cell now reads exactly this pattern.

---

### 2. Stale metrics in docs — **FIXED** in 8 files

`metrics.json` was regenerated in `2a94e4a`; two headline numbers changed.

| Metric | Old | New (from `metrics.json`) |
|---|---:|---:|
| recall@1% (`test.budgets[2].recall`) | 78.0% | **78.3%** |
| ACH recall@1% (`error_analysis.slices.payment_type.ACH.recall`) | 84.6% | **84.9%** |
| PR-AUC | 0.595 | 0.595 (unchanged) |

**Files updated:**

| File | Changes |
|---|---|
| [`README.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/README.md) | Lines 29, 120, 127 — recall@1% and ACH recall |
| [`docs/CLAIMS_REGISTER.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/docs/CLAIMS_REGISTER.md) | Claims 1 and 11; verification date updated; `test_claim_01` and `test_claim_11` now match |
| [`PENDING.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/PENDING.md) | A1 ACH recall; BIPARTITE note; blend-table note; E5 LinuxONE clean-run results added |
| [`WINNING_PLAN.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/WINNING_PLAN.md) | Lines 460, 494, 499, 505 |
| [`docs/PROBLEMS_3_LIMITS.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/docs/PROBLEMS_3_LIMITS.md) | LIM-01 section |
| `docs/STATUS.md`, `docs/PROBLEMS_1_FIXABLE.md`, `docs/flowguard_complete_directory_report.md` | Replaced occurrences of 78.0% and 84.6% with the corrected metrics |
| `Project/flowguard/tests/unit/test_claims_register.py` | Line 52, 120, and 154 fixed to match updated metrics |

---

### 3. Notebook Prose/Claims Updated — **DOCUMENTED**

Explicit prose notes were added directly to the cell print statements inside [`02_keras_model.ipynb`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/Project/flowguard/linuxone/02_keras_model.ipynb):

1. **BIPARTITE Gate (Cell 19):** Added a note declaring that finding only 1 BIPARTITE positive in the 2-day window makes the case statistically anecdotal and it should not be treated as a general claim for that typology.
2. **Blend Table Weight (Cell 22):** Added a note declaring that the best weight in the blend table was selected using the test set, making it an optimistic oracle figure that should not be quoted as a result.
3. **DNN vs XGBoost (Cell 13):** Clarified the comparison statement to note that "The DNN beats XGBoost" is not supported by the data, and it is comparable to XGBoost (both catch 46 cases at 1% budget).

---

### 4. Dropped Models Documented — **NEW ADR**

Added [`docs/ADR-017-dropped-models.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/docs/ADR-017-dropped-models.md) explaining why Logistic Regression (not evaluated; cannot handle non-linear interactions without complex feature engineering) and Isolation Forest (unsupervised; didn't improve PR-AUC over XGBoost alone) were removed. Registered in `docs/README.md`.

---

### 5. LinuxONE clean-run results recorded — **NEW** (PENDING E5)

Added [`PENDING.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/PENDING.md) item E5 with the confirmed 2-day window results:

| Model | PR-AUC | recall@1% |
|---|---:|---:|
| E2 GFP + XGBoost | 0.0325 | 36.2% |
| Keras DNN (seed 42, 150-epoch cap, early stopping) | 0.0389 | 36.2% |

`01` in 6 min 14 s at 2.10 GB peak RAM; `02` in 4 min 29 s. All self-checks pass.

---

### 6. Handoff document created

[`docs/HANDOFF_VIKA_2026-09-30.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/docs/HANDOFF_VIKA_2026-09-30.md) — the document Shivraj asked to send Vika. Contains:
- What was verified (test results, LinuxONE run, 278-test pass)
- Fix A (Keras import fix, already applied locally)
- Fix B (stale numbers, already applied locally)
- Three notebook notes (BIPARTITE, blend weight, DNN claim)
- Decision D40 (Option A vs B for FlowGuard integration)
- Overall 75% completion status table

---

## What is NOT done here (requires action)

| Item | Who | Why not done here |
|---|---|---|
| **Decision D40** — Option A vs B for FlowGuard demo | Shivraj + Vika | Needs a decision meeting |
| Re-upload FlowGuard to LinuxONE | Shivraj | VM access required |
| Rotate IBM API key, put in `.env` | Vika | Credential rotation |
| Judge Q&A pack (directive §58) | Both | Requires writing |
| Commit today's records (M45/M46, D39) | Shivraj | Git push from his machine |
| Open PR from `feature/shivraj-system` into `main` | Shivraj | After Vika's branch is ready |
