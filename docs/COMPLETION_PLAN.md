# FlowGuard — End-to-End Completion Plan (A + B + C)

**Version:** 1.0
**Date:** 2026-09-18
**Target:** Track R complete, feature research done, cross-dataset validation passed.
**Estimate:** **≈ 11 hours** — 7h build, 4h compute, overlapping where noted.

Committing is autonomous for this session. Everything below is sequenced so each phase
ends in something reportable, and so an early stop still leaves a defensible deliverable.

---

## Current position

| | |
|---|---|
| Committed | 5 commits · 117 tests · 37 modules · 7 ADRs |
| Measured | E0, E1, A1/A2 ablation, error analysis on the artifact-free baseline |
| Running | E2 GFP extraction — 78.8%, ~30 min out |
| Published | Validation report artifact |

**The number that governs everything below:** seed sd ≈ 0.0017, so the inclusion bar is
**2σ ≈ 0.0034 PR-AUC**. Nothing counts as an improvement under that.

**The honest baseline is A2: PR-AUC 0.0066, recall@1% 11.8%** — not the artifact-inflated
0.0416 ([ADR-007](ADR-007-payment-type-artifact.md)).

---

# Tier A — Close the Track R terminus

**≈ 1 hour · 50 min compute · 15 min build**

### A1. E2 extraction completes *(30 min, automatic)*

Watcher is armed inside WSL. Two outcomes:

* **Cache written** → proceed to A2.
* **OOM before the write** → fall back to a *contiguous* 3-day slice (≈2.3M rows), running
  A2 and E2 on that same slice so they stay mutually comparable. Contiguous preserves
  graph topology; stride-sampling does not, and would understate graph value.

### A2. Run the completion script *(10 min, already written)*

Three arms × three seeds:

| Arm | Features | Purpose |
|---|---|---|
| A2 | tabular, artifact-free | honest baseline |
| **E2** | **tabular + GFP, artifact-free** | **answers the research question** |
| E2x | tabular + GFP, artifact present | continuity with earlier figures |

**The pre-registered test**, decided mechanically, not narrated:

> Mean recall gain in the three lowest amount bands (currently **zero** recall) must
> exceed the gain in the two highest. A uniform lift means the graph features are another
> magnitude proxy.

Plus the hard-negative enrichment against its **1.02×** control — recall bought by
alerting on legitimately complex accounts is a cost, not a win.

### A3. Validation gates and model package *(10 min)*

`run_validation --model-id E2` → `models/flowguard_E2_v1/` per v3 §26.4: booster,
calibrator, feature schema + hash, encoders, thresholds, metrics, `validation_report.md`,
`model_card.md`, `shap_summary.json`, `PROVENANCE.json`.

### A4. Update the report and commit *(15 min)*

**Gate A — the fork.** Record `delta = E2 − A2` against 2σ:

| Outcome | What it means | Next |
|---|---|---|
| Δ > +0.0034 **and** low-band concentrated | Graph structure adds real information | Tier B is justified |
| Δ > +0.0034, uniform across bands | Another magnitude proxy | Tier B narrows to one targeted family |
| \|Δ\| ≤ 0.0034 | Graph features do not help here | **Skip Tier B.** Go straight to Tier C |

That last row is a legitimate ending. Plan v3 §1 is explicit that a trustworthy negative
is a result. Five hours spent hunting a feature family that beats a baseline the graph
features could not beat is how a project talks itself into noise.

---

# Tier B — Feature research (E3–E7)

**≈ 4–7 hours · 1h compute · 3–6h build · conditional on Gate A**

Scope is already **cut by evidence**: the error analysis found recall flat across chain
position (early 21.6%, middle 15.1%, late 17.2%), so **temporal-velocity features are not
supported** and are not being built. That removes two of the four families v3 anticipated.

### B1. Value-flow features *(2 h)* — `features/value_flow.py`

Targets the measured failure directly: zero recall below $2,671.

* amount relative to the account's own history (z-score against its rolling distribution)
* pass-through ratio — fraction of inflow forwarded on, and how fast
* value preservation along a path: a laundering chain sheds a small percentage per hop
* round-number and just-under-threshold structuring signals, per account rather than global

**Hypothesis:** a $500 transfer is unremarkable globally but extraordinary for an account
whose median is $30. Magnitude *relative to baseline* should recover low-value positives
where absolute magnitude cannot.

### B2. Adaptive / neighbourhood features *(2 h)* — `features/adaptive.py`

Only if B1's ablation shows graph context still under-used.

* risk-weighted neighbourhood: are counterparties themselves anomalous?
* degree-normalised structural scores, so hubs are not penalised for being hubs — directly
  targeting the hard-negative enrichment metric
* depth-limited path aggregates around the transaction

### B3. Ablation and inclusion decision *(1 h + 30 min compute)*

`run_ablation` with every family, 5 seeds, equal search budget via rolling-origin.

**Inclusion rule, fixed now:** a family enters the final model only if it improves PR-AUC
by **> 2σ** with a CI excluding zero. Everything else is reported as
*evaluated-and-dropped with the measured reason* — the model-card line most often omitted
and most useful to whoever reads this next.

**Gate B:** if nothing clears the bar, **E2 is the final model** and that is stated
plainly rather than softened.

---

# Tier C — Cross-dataset validation

**≈ 3–4 hours · 1h compute · 2–3h build**

**The highest-value work in this plan, and it runs regardless of Gate A.**

ADR-007 is the argument for it: a simulator that injects laundering over a single payment
rail may have other conventions a model quietly learns. Everything measured so far comes
from one generator. A real network is the only evidence the result is not
simulator-specific.

### C1. Acquire and canonicalise ETH Phishing *(1.5 h)*

* ~2.9M accounts, ~13M transactions, 0.278% illicit, 1,261-day span — a different domain,
  schema and time scale.
* New loader mapping onto the existing canonical contract. The contract was built for
  exactly this: adapt at the edge, change nothing downstream.
* **Expect friction.** No `payment_type`, no typology annotations, node-level rather than
  transaction-level labels. Each gap gets declared, not patched over.

### C2. Run the frozen pipeline *(1 h, mostly compute)*

Same split logic, same features where they exist, same evaluation code, same gates. The
model is **not retuned** — this measures transfer, and retuning would measure something
else.

### C3. Report transfer *(1 h)*

| Question | Why it matters |
|---|---|
| Does the graph contribution survive? | The core external-validity question |
| Does the amount-magnitude failure recur? | Is it a property of the method or of AMLSim? |
| Does hard-negative enrichment hold near 1.0×? | Real networks have real hubs |
| What is the throughput at 13M edges? | 2.6× the current corpus, and P8 already strains |

**Gate C:** if the graph contribution vanishes on a real network, that is the single most
important finding the project can produce — and it must headline, not sit in an appendix.

### C4. Intermediate scale check *(optional, 30 min compute)*

HI-Medium (32M transactions) for throughput and memory only, never model selection. Given
extraction throughput decays to ~350 tx/s on 5M rows, **32M is likely infeasible on this
hardware** — which is itself a reportable finding about the method's scaling envelope.

---

# Final assembly

**≈ 1 hour, inside the totals above**

1. `models/flowguard_<final>_v1/` regenerated against the selected model
2. `model_card.md` complete — intended use, non-uses, **evaluated-and-dropped**, failure
   modes, datasets *not* validated on, revalidation trigger
3. Published report updated: results, the prediction test, gates, cross-dataset transfer
4. `docs/README.md` and `OPEN_ITEMS.md` reconciled to final state
5. Final commit

---

## Schedule

| Phase | Build | Compute | Cumulative |
|---|---:|---:|---:|
| A1 — E2 extraction | — | 0:30 | 0:30 |
| A2 — completion script | — | 0:10 | 0:40 |
| A3 — gates + package | — | 0:10 | 0:50 |
| A4 — report + commit + **Gate A** | 0:15 | — | **1:05** |
| B1 — value-flow features | 2:00 | 0:20 | 3:25 |
| B2 — adaptive features | 2:00 | 0:20 | 5:45 |
| B3 — ablation + **Gate B** | 1:00 | 0:30 | 7:15 |
| C1 — ETH loader | 1:30 | — | 8:45 |
| C2 — run pipeline | 0:30 | 1:00 | 10:15 |
| C3 — transfer report + **Gate C** | 1:00 | — | 11:15 |
| Final assembly | 0:45 | 0:10 | **12:10** |

**≈ 11–12 hours.** Tier B is the variable: it shrinks to ~2h if Gate A points at one
family, and to zero if Gate A comes back inconclusive — in which case the total is **≈ 6
hours**.

### Checkpoints where stopping still leaves something complete

* **1:05 — Tier A done.** Validated model package, seven ADRs, gate report. Defensible
  and publishable as-is.
* **7:15 — Tier B done.** Feature research with an evidence-gated inclusion rule.
* **12:10 — everything.** The only version that can claim the result is not
  simulator-specific.

---

## Risks

| Risk | Handling |
|---|---|
| E2 OOMs at 95% | Contiguous 3-day slice, both arms on it, labelled as sub-corpus |
| Gate A inconclusive | Skip Tier B — that is the plan working, not failing |
| ETH labels are node-level, not transaction-level | Declare the mismatch; evaluate at account level and state that the comparison is indicative |
| ETH is 13M edges vs 5M | Throughput already decays badly; may need a time slice, reported as such |
| WSL memory ceiling | 12 GB cap already binding at 7.5 GB; raising it needs a `wsl --shutdown` between runs |
| Scope creep into Track P | Out of scope. v2 §§29–33 only, and only if judged on a live demo |

## What this plan will still not deliver

Real transaction data. Both corpora are synthetic or public-chain; neither is bank data
with genuine KYC context. Every claim remains bounded by that, and the model card says so.
