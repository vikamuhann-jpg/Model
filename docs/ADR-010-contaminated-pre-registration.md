# ADR-010 — Gate P4 stays as written, and is reported as a miss

**Status:** Accepted
**Date:** 2026-09-19
**Decision:** Leave gate **P4** at *recall ≥ 45% at a 1% alert budget*. It will fail. Do
not move it.

---

## What happened

P4 was pre-registered in `configs/experiment.yaml` before any result existed — which is
the correct discipline. The target was set against the then-current baseline, E1 at
**41.1%** recall, so 45% looked like a modest, achievable stretch.

E1's 41.1% was later shown to be **84% simulator artifact**
([ADR-007](ADR-007-payment-type-artifact.md)). The artifact-free baseline reaches
**11.8%**.

So the gate was calibrated against a number that was mostly measuring the generator's
payment-rail convention. It is now roughly four times out of reach, and it was never a
meaningful target — it just looked like one.

## Decision

**The target does not change.**

Moving a pre-registered gate after seeing results is precisely the failure gates exist to
prevent. A gate that gets adjusted whenever it is inconvenient provides no discipline at
all; it only produces a record of having passed. Plan v3 §26 is explicit that a gate
chosen after seeing results is not a gate, and that a missed performance gate is **a
finding to report, not a failure to hide**.

P4 is therefore reported as **FAILED**, with the measured value and this explanation
alongside it.

## The generalisable lesson

This is the part worth carrying forward, because the mistake was not in the target — it
was in the ordering.

> **Pre-registration inherits whatever contaminates the numbers it was set against.**

Fixing a threshold in advance protects against choosing it to flatter a result. It does
**not** protect against the baseline itself being wrong. If the preliminary number is
contaminated, the pre-registered gate is contaminated too, and the discipline gives a
false sense of rigour — the gate feels principled precisely because it was set early.

The correct sequence is:

1. Build the pipeline
2. **Run the artifact audit** — SHAP dominance, single-feature baselines, ablation of any
   suspiciously strong feature
3. *Then* pre-register the gates, against numbers that have survived that audit
4. Run the experiments

This project did 1 → 3 → 4 → 2. The audit happened, and caught something large, but it
happened after the gates were already fixed against the unaudited baseline.

Notably, the same audit machinery that invalidated the gate is what makes the failure
interpretable: gate **C8** fired on `payment_type` at 56.8% of mean |SHAP|, and the
five-seed ablation quantified the cost. Without that, P4 would simply have been missed
with no explanation, and the natural reading would have been "the model underperforms"
rather than "the target was set against a contaminated baseline".

## Consequences

* `validation_report.md` records P4 as FAILED with the measured recall and a pointer here.
* `model_card.md` states the operating point honestly: at a 1% alert budget the
  artifact-free model recovers ~12% of laundering transactions. That is a weak result and
  is presented as one.
* Any future gate on this project is set **after** the artifact audit, not before.
* P4 remains a reasonable *aspiration* for an AML screening model. Nothing here argues
  that 45% is the wrong thing to want — only that this corpus, this feature set and this
  honest baseline do not reach it.

## What would make P4 achievable

Not a lower target. Either graph-structural features that recover the low-value
transactions where recall is currently zero (the Tier B hypothesis), or a corpus whose
laundering is not concentrated in a single payment rail — which is the argument for
cross-dataset validation in Tier C.

## Revisit if

The primary dataset changes, at which point every pre-registered target is re-derived
from an audited baseline on the new corpus, and this ADR becomes the reason that ordering
is enforced.
