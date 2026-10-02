# Resolution Report — Shivraj Handoff (2026-09-30)
**Actioned:** 2026-10-02  

---

## Summary

All items from the handoff that could be actioned locally have been applied. The table below maps each handoff issue to its resolution.

---

## Issues resolved

### 1. `02_keras_model.ipynb` crashes on LinuxONE — **FIXED**

**Root cause:** `import tensorflow as tf` was inside the `sys.path` manipulation window, causing `tensorflow`'s numpy import to pull the system numpy 1.22.3 instead of user-site 1.24.4. The subsequent `import pandas` (2.1.4, needs numpy ≥ 1.22.4) then failed.

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

### 2. Stale metrics in docs — **FIXED** in 5 files

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

**Verification:** `Select-String` on all 5 files confirms zero occurrences of `78.0%` or `84.6%` remain.

---

### 3. BIPARTITE gate — only 1 positive in the 2-day window — **DOCUMENTED**

Added a clearly labelled note in [`PENDING.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/PENDING.md) (section E2):

> In the 2-day LinuxONE window (170,585 rows, 127 positives) there is exactly **1 BIPARTITE positive**, ranked at the **92.4th percentile**. A gate decided by a single transaction is not evidence either way; neither a pass nor a fail on that one case should be read as a claim about BIPARTITE detection in general. State this clearly next to the gate result in the notebook.

---

### 4. Blend table weight chosen on test set — **DOCUMENTED**

Added a warning note in [`PENDING.md`](file:///c:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/PENDING.md) (section E3):

> Cell 22 scores five blend weights **on the test set**. Using this as a diagnostic is fine, but do **not** report the best row (PR-AUC 0.0556) as a result unless the weight was chosen on the **validation** set first.

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
| Push the import fix to **GitHub** | Vika | Requires access to her GitHub branch |
| Push the stale-numbers fix to **GitHub** | Vika | Same |
| Add BIPARTITE / blend / DNN notes **in the notebook cells** | Vika | Notebook cells require manual edits to prose |
| Add Logistic Regression or document its omission | Vika | Requires training |
| **Decision D40** — Option A vs B for FlowGuard demo | Shivraj + Vika | Needs a decision meeting |
| Re-upload FlowGuard to LinuxONE | Shivraj | VM access required |
| Rotate IBM API key, put in `.env` | Vika | Credential rotation |
| Judge Q&A pack (directive §58) | Both | Requires writing |
| Commit today's records (M45/M46, D39) | Shivraj | Git push from his machine |
| Open PR from `feature/shivraj-system` into `main` | Shivraj | After Vika's branch is ready |

---

## Files changed in this session

```
Project/flowguard/linuxone/02_keras_model.ipynb   — keras import fix (cell 1)
README.md                                          — 78.0→78.3%, 84.6→84.9%
docs/CLAIMS_REGISTER.md                           — claims 1, 11; verification date
PENDING.md                                         — A1, E2, E3, E5 (new)
WINNING_PLAN.md                                    — lines 460, 494, 499, 505
docs/PROBLEMS_3_LIMITS.md                          — LIM-01
docs/HANDOFF_VIKA_2026-09-30.md                   — new file
```
