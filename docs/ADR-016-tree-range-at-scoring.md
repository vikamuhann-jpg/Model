# ADR-016 — Score with every tree, and say so

**Date:** 2026-09-26 · **Status:** accepted · **Supersedes:** nothing ·
**Measured by:** `Project/flowguard/scripts/measure/tree_range.py` →
`runs/COMP1_tree_range.json`

## Context

`flowguard_V2_v1` was trained with early stopping. It stopped improving on
validation at iteration **740**, and training ran on to **841 trees** before the
patience window expired.

Which of those two numbers gets used at prediction time is a library default, and
XGBoost's entry points do not agree on it:

| Path | Trees used |
|---|---:|
| `Booster.inplace_predict` — what `predict_raw` calls | 841 |
| `shap.TreeExplainer` — what explanations used until 2026-09-26 | 741 |

Nobody chose either. The disagreement surfaced while replacing `shap` with
XGBoost's native TreeSHAP: the two produced different numbers for the same model,
and the cause was the tree range rather than the algorithm. Until then **every
evidence bundle we shipped explained a 741-tree model whose scores came from
841 trees.**

The explanation side is now fixed. This record settles the remaining question:
*which range is correct?* The trees past the best iteration are the ones
validation said had stopped helping, so they are either mild overfitting or
harmless — and every number we publish was measured with all 841.

## Decision

**Score with every tree, and pass the range explicitly everywhere.**

`flowguard.models.xgb.ALL_TREES = (0, 0)` is now the single statement of it.
`XGBModel.predict_raw` passes it to `inplace_predict`; `tree_shap` passes the same
constant to `pred_contribs`. Neither inherits a default any more.

## Why

Measured on the full test partition — 1,015,564 rows, 1,797 positives:

| Arm | Trees | PR-AUC | best F1 | recall @1% |
|---|---:|---:|---:|---:|
| All trees | 841 | 0.6034 | 0.6142 | 78.13% |
| Truncated at `best_iteration` | 741 | 0.6036 | 0.6140 | 78.30% |
| **Difference** | −100 | −0.0003 | **+0.0002** | −0.17 pp |

The F1 difference is **0.0002** against a five-seed spread of **0.0025** for this
configuration (S4b). The extra hundred trees neither help nor hurt: there is no
measurable overfitting to remove, and no accuracy to be gained by removing it.

Given that, the deciding argument is not accuracy but consistency:

1. **Every published number was measured with all 841 trees.** Truncating would
   change the shipped model for no measured benefit, and would invalidate figures
   that are correct as they stand.
2. **A silent default caused the original defect.** Two code paths inherited
   different defaults and nothing failed — the numbers simply disagreed, somewhere
   nobody looked. Stating the range removes the class of bug, not just this
   instance of it.
3. **The alternative was never wrong, only unmeasured.** Had truncation been
   better, this record would say so. It is within noise, so the tie goes to the
   option that keeps the published record intact.

## Consequences

- Scoring and explanation are guaranteed to describe the same model, which is
  what the bundles claim and what they previously did not do.
- `predict_raw` and `tree_shap` now break loudly rather than silently if a future
  XGBoost changes its default, because the range is an argument, not an
  assumption.
- The 100 trees past the best iteration stay in the package. They cost roughly 12%
  of inference time for no accuracy — worth revisiting only if latency becomes the
  binding constraint, which at a 30 ms median per transaction it is not.
- Any future model trained with early stopping inherits this decision. One where
  the gap is *not* inside the seed spread would need its own record.
