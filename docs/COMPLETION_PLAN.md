# FlowGuard — End-to-End Completion Plan (A + B + C)

**Version:** 1.0
**Date:** 2026-09-18
**Target:** Track R complete, feature research done, cross-dataset validation passed.
**Estimate:** **≈ 19 hours** with the Tier S fixes (13h if Tier B is skipped, ~11h if
Tier C is dropped). The original 11h figure assumed the pipeline transfers cleanly; it
does not yet, and Tier S is what makes it.

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

# Tier S — Fixing the flaws, before they bite

**≈ 6 hours · 2h compute · 4h build**

Tiers A–C above are written as if the pipeline transfers cleanly. It does not yet. Six
known flaws would each degrade or invalidate part of the work, and four of them are
*engineering problems with engineering answers* rather than limitations to disclaim.
This tier fixes those four and puts a measurement behind the other two.

**Sequencing matters:** S1 and S2 run **before** Tier C, because ETH Phishing is 2.6× the
current corpus and would hit both problems harder. S3 and S4 run before Tier C for the
same reason.

---

## S1. Throughput decays even with a bounded window *(2 h build · 30 min compute)*

**The flaw.** [ADR-006](ADR-006-gfp-time-window.md) confirmed that bounding `time_window`
helps 37–53%, and confirmed it is *not sufficient*: the 2-day run still decayed 11×, from
12,539 to ~557 tx/s. GFP evicts edges but **retains every vertex it has ever seen** —
515,078 of them — so lookup and cycle-search cost climb regardless. At 13M ETH edges this
gets materially worse, and gate P8 is already failing.

**The fix — periodic preprocessor reconstruction.**

Every *N* transactions, discard the preprocessor and build a fresh one, replaying into it
only the edges still inside the current time window. Those edges are the only ones that
can affect any future feature, so the reconstructed state is semantically identical — but
its vertex set is bounded to accounts *active in the window* rather than accumulated since
the beginning.

```text
for each chunk of N transactions:
    if preprocessor is stale:
        fresh = GraphFeaturePreprocessor(params)
        fresh.partial_fit(edges within [t - window, t])   # replay: near-empty start, fast
        preprocessor = fresh
    transform(edge) -> features      # convention unchanged
    partial_fit(edge)
```

**Why it should pay for itself.** Replay runs against a near-empty graph, which is the
fast regime (~12,000 tx/s). A 2-day window holds roughly 1M edges, so one reconstruction
costs ~80 s. Ten reconstructions across the corpus is ~13 min of overhead to hold
throughput near the fast end instead of decaying to 557 tx/s — which currently costs
**over two hours**.

**The correctness test this needs, and it is not optional.** Reconstruction is only valid
if it changes nothing observable:

> `test_reconstruction_is_feature_identical` — extract features for a run of transactions
> with and without a reconstruction inserted mid-stream, and assert the outputs are
> byte-identical.

If they differ, GFP's state carries something beyond the windowed edge set, the
optimisation is unsound, and it is abandoned rather than tuned. **The test decides, not
the throughput number.**

---

## S2. Peak memory is the binding constraint *(1 h build)*

**The flaw.** The current design materialises the whole feature block in RAM — 5M × 215
float32 = 4.4 GB — and the run sits at 7.6 GB of an 11 GB ceiling with 16% still to go.
The cache writes *last*, so a late OOM discards hours of extraction. ETH at 13M rows would
need ~11 GB for the buffer alone: **guaranteed failure**.

**The fix — stream features to disk in chunks.**

Write each chunk of *N* rows to `…/gfp_parts/part_00042.parquet` as it is produced, then
read the parts back as one pyarrow dataset at training time. Peak memory becomes a single
chunk instead of the whole corpus, and a crash costs one chunk rather than everything.

This also makes extraction **resumable** — on restart, skip the chunks already on disk.
Given a two-hour extraction, that alone justifies the hour.

---

## S3. The pipeline assumes columns ETH does not have *(1 h build)*

**The flaw.** ETH Phishing has no `payment_type`, no `currency`, no typology annotations.
Today several components would fail or silently degrade: the categorical encoder expects
both columns, `split_by_typology` raises, the rule baseline reads `payment_type`.

**The fix — an explicit capability matrix, checked at load.**

Each dataset declares what it carries; each component states what it requires; the loader
reconciles the two and **prints what is unavailable and why**, rather than discovering it
mid-run.

| Capability | HI-Small | ETH Phishing | Consumers |
|---|---|---|---|
| `payment_type` | yes | **no** | E0 rules, categorical encoder |
| `currency` | yes | **no** | cross-currency feature |
| typology annotations | 62% of positives | **none** | unseen-pattern split, per-typology recall |
| transaction-level labels | yes | **no — node-level** | every metric (see S4) |

Components degrade explicitly and the degradation is written into the experiment record,
so a missing capability can never be mistaken for a measured zero.

Much of this is already true — `TransactionFeatures` guards each optional column and
`split_by_typology` raises a clear error. S3 makes it **declared up front and logged**
instead of discovered by exception.

---

## S4. ETH labels are node-level; every metric assumes transaction-level *(1.5 h build)*

**The flaw, and it is the serious one.** ETH Phishing labels *accounts*, not transactions.
The tempting fix — mark every transaction touching a flagged account as positive — is
**wrong, and must be rejected explicitly**: a phishing account also receives legitimate
funds, so propagation manufactures false positives, inflates the base rate, and makes
precision meaningless. It would produce a number that looks like a result and is not one.

**The fix — evaluate at the account level instead.**

Score transactions as usual, then aggregate to the account and compare against the label
the dataset actually provides:

```text
account_score = max(scores of that account's transactions)      # primary
                mean, top-k mean                                # reported alongside
```

`max` is primary because detection is a screening problem: one clearly suspicious
transaction should surface the account. Mean and top-k are reported so the choice is
visible rather than buried.

This needs a parallel evaluation path — `evaluation/account_level.py` — with its own
PR-AUC, alert budgets and gates. The cross-dataset comparison is then **indicative, not
like-for-like**, and must be labelled that way everywhere it appears: HI-Small answers
*"is this transaction part of laundering?"*, ETH answers *"is this account a phisher?"*.
Those are different questions. The transfer claim is about whether **graph structure
carries signal in both**, never about a shared number.

---

## S5. HI-Medium at 32M is probably infeasible *(30 min compute — measure, don't assume)*

**The flaw.** Gates P8/P9 are stated against HI-Small only. Whether the method scales is
currently an assumption in both directions.

**The fix — measure the envelope and publish it.** With S1 and S2 in place, run extraction
on HI-Medium for a **fixed 20-minute budget** and record how far it gets, the steady-state
throughput, and peak memory. Extrapolate honestly from that.

A scaling envelope stating *"this method sustains X tx/s at Y edges and becomes
impractical beyond Z on 12 GB"* is a genuine contribution. Silence is not, and neither is
an untested claim that it scales.

---

## S6. P4 was pre-registered against a contaminated number *(15 min — documentation)*

**The flaw.** P4's 45% recall target was set against a baseline later found to be 84%
simulator artifact. The artifact-free baseline reaches 11.8%.

**The fix — leave the gate alone, and report the mechanism.** The target stays at 45% and
is reported as a **miss**. Moving a pre-registered gate after seeing results is precisely
what gates exist to prevent, and the honest record is worth more than a passing mark.

What gets added is the lesson, in the model card and the report: **pre-registration
inherits whatever contaminates the numbers it was set against.** The correct protocol is
to pre-register gates *after* the artifact audit — which means the artifact audit has to
come first, and in this project it did not.

---

## Revised schedule with Tier S

| Phase | Build | Compute | Cumulative |
|---|---:|---:|---:|
| **Tier A** — close Track R | 0:15 | 0:50 | **1:05** |
| S1 — periodic reconstruction + invariance test | 2:00 | 0:30 | 3:35 |
| S2 — chunked, resumable feature persistence | 1:00 | — | 4:35 |
| **Tier B** — value-flow, adaptive, ablation | 5:00 | 1:10 | 10:45 |
| S3 — capability matrix | 1:00 | — | 11:45 |
| S4 — account-level evaluation path | 1:30 | — | 13:15 |
| **Tier C** — ETH loader, run, transfer report | 3:00 | 1:00 | 17:15 |
| S5 — scaling envelope | — | 0:30 | 17:45 |
| S6 + final assembly | 1:00 | 0:10 | **18:55** |

**≈ 19 hours**, against the 11 in the original plan. **The fixes are not free, and
pretending otherwise would repeat exactly the error they correct.**

If Gate A comes back inconclusive and Tier B is skipped: **≈ 13 hours**.

### Which of these are actually optional

| | Verdict |
|---|---|
| **S2, S4** | **Mandatory for Tier C.** Without them ETH either OOMs or produces a meaningless number |
| S1 | Strongly advised — it likely *saves* net time, and the invariance test decides it |
| S3 | Cheap, and prevents mid-run surprises |
| S5, S6 | Reporting quality, not correctness |

**If Tier C is dropped, S2 and S4 drop with it** and the total returns to roughly the
original 11–12 hours. That is the real trade: cross-dataset validation costs ~2.5 hours of
enabling work on top of its own 4 — and it remains the only route to a claim that is not
simulator-specific.

---

## Risks

| Risk | Handling |
|---|---|
| E2 OOMs at 95% | Contiguous 3-day slice, both arms on it, labelled as sub-corpus. S2 prevents a recurrence |
| Gate A inconclusive | Skip Tier B — that is the plan working, not failing |
| ETH labels are node-level, not transaction-level | **Fixed by S4** — account-level evaluation path; label propagation explicitly rejected |
| ETH is 13M edges vs 5M | **Fixed by S1 + S2** — periodic reconstruction and chunked persistence |
| WSL memory ceiling | **Fixed by S2** — peak becomes one chunk, and extraction becomes resumable |
| Scope creep into Track P | Out of scope. v2 §§29–33 only, and only if judged on a live demo |

## What this plan will still not deliver

Real transaction data. Both corpora are synthetic or public-chain; neither is bank data
with genuine KYC context. Every claim remains bounded by that, and the model card says so.
