# ADR-011 — Adaptive neighbourhood features: built, measured, rejected

> **Note 2026-09-22:** figures in this record were computed with the extractor that inserted every edge twice. See [ADR-015](ADR-015-gfp-double-insertion.md) for what was re-run and the corrected values.

**Status:** Rejected — negative result
**Date:** 2026-09-20
**Decision:** Do **not** include the degree-normalised neighbourhood family in the model.
It measurably degrades performance.

---

## What it was meant to fix

Gate A confirmed graph features work — PR-AUC 0.0065 → 0.1400 artifact-free — but it also
surfaced a cost. The hard-negative control moved from **1.02× to 2.3×**: the graph model
alerts on structurally complex but *benign* accounts at more than twice the rate it alerts
on ordinary benign traffic. Some of its recall is bought by flagging merchant hubs,
payroll fan-out and treasury sweeps.

Gate A also **falsified** the prediction that graph gains would concentrate in low amount
bands, which ruled out the value-flow family. So Tier B narrowed to one hypothesis:

> Raw structural counts punish hubs for being hubs. Normalising each signal against what
> is typical **for an account of that degree** should let the model keep the structural
> signal while dropping the false positives that come from size alone.

Eleven features: degree asymmetry, amount versus the account's own median, amount versus
same-degree peers (ratio and z-score), value per counterparty, and unseen-endpoint flags.
Fitted on training rows only; 11 tests, including one asserting that a hub transacting
like other hubs scores near zero.

## Result

Seven arms, three seeds, one change per arm, pooled seed sd 0.0030 → **2σ = 0.0059**.

| Arm | Features | PR-AUC | Recall @1% |
|---|---:|---:|---:|
| A2 — tabular, artifact-free | 12 | 0.0065 ± 0.0001 | 11.6% |
| A4 — + graph, artifact-free | 167 | **0.1400 ± 0.0030** | 56.2% |
| A5 — adaptive alone | 21 | 0.0041 ± 0.0001 | 7.4% |
| **A6 — graph + adaptive** | 176 | **0.1073 ± 0.0071** | 52.8% |

**A6 − A4 = −0.0326.** Against a 2σ bar of 0.0059, that is a real regression at more than
five times the noise threshold — not an inconclusive result, a measurably worse one. The
family costs **23% of the graph model's PR-AUC**.

A5 is the second signal: adaptive features alone score **0.0041**, *below* the 12-feature
tabular baseline at 0.0065, and within noise of nothing.

## Why it failed

The mechanism that was supposed to remove false positives removes the signal with them.

Degree-normalisation tells the model *"this hub is normal for a hub"*. But on this corpus
raw degree and fan counts **are** the discriminative signal — they carry the 69.8% of
SHAP mass that graph features hold in the validated model. Suppressing size-driven
structure to protect hubs suppresses the very anomalies that were doing the detecting.

The trade was real and it went the wrong way: a false-positive property was bought at a
larger cost in detection.

A5's result sharpens this. Neighbourhood context **without** the raw structural counts is
worth less than twelve row-local features. Whatever these features encode, it is not
independently informative here.

## Decision

* `features/adaptive.py` and its tests stay in the tree. The code is correct and tested;
  it is the *hypothesis* that failed, and deleting it would invite someone to rebuild it.
* It is **not** wired into any reported model.
* `model_card.md` lists it under evaluated-and-dropped with the measured delta.
* The inclusion rule was fixed before the result existed — a family enters only on
  a > 2σ improvement — so this verdict is arithmetic, not judgement.

## What this closes

Tier B is **complete with a negative result**. Both candidate families are now eliminated
*on evidence* rather than on preference:

* **Value-flow** — ruled out before being built, because Gate A falsified the low-band
  prediction it depended on.
* **Adaptive neighbourhood** — built, measured, rejected here.

Per [COMPLETION_PLAN.md](COMPLETION_PLAN.md) Gate B: *"if nothing clears the bar, E2 is
the final model and that is stated plainly rather than softened."*

**E2 is the final model.**

## What this does not close

The 2.3× hard-negative enrichment is **still unaddressed**. This family was the attempt at
it and it failed. The honest position is that the validated model buys part of its recall
by alerting on legitimate complexity, and nothing in this project fixes that.

Whether the problem is even solvable on a corpus whose laundering sits almost entirely on
one payment rail is doubtful — ADR-007 suggests the model has limited structural
understanding to refine in the first place. That question belongs to cross-dataset
validation, not to another feature family here.

## Revisit if

A corpus is used where the model's structural signal does not collapse onto a single
payment rail, making it meaningful to ask whether degree-normalisation helps — or if the
hard-negative enrichment becomes the binding operational constraint, in which case the
cost in PR-AUC may be worth paying deliberately rather than avoided.
