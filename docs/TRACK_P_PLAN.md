# FlowGuard — Plan to close the open functional requirements

**Version:** 2.0 *(supersedes the 40-hour v1.0)*
**Date:** 2026-09-20
**Scope:** seven of the nine open requirements — FR-05, FR-06, FR-07, FR-09, FR-10, FR-11,
FR-12. **FR-03 and FR-08 are deliberately left open**; see §3.
**Estimate:** **≈ 16 hours**, ordered by value per hour.

This plan inherits the discipline of [`COMPLETION_PLAN.md`](COMPLETION_PLAN.md): every
phase ends in something reportable, anything claiming an improvement clears a gate **fixed
before the result exists**, and a phase that fails its gate is written up as a negative
result rather than quietly softened.

---

## 0. Why this is 16 hours and not 40

v1.0 estimated each item as if it were greenfield. It is not. The pipeline already ships,
tested, the parts this plan composes:

| Already built | Used by |
|---|---|
| `models/xgb.py` — fit, calibrate, device resolution | typology head, unsupervised arm |
| `splits/temporal.py` — chronological split, boundary policies | every measured phase |
| `features/transaction.py`, `features/gfp.py` | cascade tiers |
| `evaluation/interpretation.py` — SHAP attribution | local reasons |
| `evaluation/metrics.py`, `evaluation/gates.py` | every gate below |
| `evaluation/account_level.py` — endpoint aggregation | tracing, case queue |
| `models/flowguard_E2_v1/PROVENANCE.json` | evidence bundle schema |

**Most of what follows is composition, not construction.** Two further corrections to v1.0:

* **Tracing does not depend on the cascade.** They share a degree cap — about fifteen lines
  — not an architecture. v1.0 sequenced six hours of cascade work in front of the one
  capability PS9 leads with, for no reason.
* **Local explanations and the evidence bundle are one phase.** Reasons with nowhere to go
  are not a deliverable, and the bundle needs reasons to be worth exporting.

---

## 1. The standing constraint

The validated model catches **599 of 796 ACH laundering transactions and 1 of 100 on every
other rail** ([ADR-007](ADR-007-payment-type-artifact.md)), and alerts on structurally
complex but benign accounts at 2.3× the ordinary rate
([ADR-011](ADR-011-adaptive-features-rejected.md)).

Building a product on that detector is legitimate. **Building one that conceals it is not.**

> Every case carries the model's known blind spots *in the case*, not in a manual. A case
> built on a non-ACH transaction is labelled as sitting outside the regime where the model
> has demonstrated recall.

Enforced by test in P2. It costs almost nothing and is the difference between decision
support and a confident-looking liability.

---

## 2. The work

### P1 — Fund tracing *(FR-05)* · 3h

PS9's headline capability, and the only item here **independent of detector quality** —
traversal is correct or incorrect regardless of how good the model is. No dependency, so it
goes first.

```text
trace(account | transaction, direction, horizon)
  → time-ordered subgraph
  → per-hop amount retained / dispersed
  → terminal endpoints
```

Two constraints fall straight out of existing findings:

* **Funds only flow forward in time.** Traversal must be timestamp-ordered, or it happily
  builds backwards paths and produces fiction.
* **Degree-capped.** An uncapped walk through a vertex with 11,152 neighbours does not
  terminate usefully ([ADR-013](ADR-013-degree-skew-dominates-cost.md)). Take the most
  recent *d* edges. This cap is reused by P3.

| Gate | Threshold |
|---|---|
| **P1-a** | On a fixture with a known injected chain, trace recovers it and admits no out-of-order edge |
| **P1-b** | Every traversal terminates under the cap — a property test, not an example test |
| **P1-c** | p95 latency < 2 s at horizon 4 on HI-Small |

**Deliverable:** `graph/trace.py` + tests.

> ### P1 — COMPLETE, 2026-09-20
>
> `graph/trace.py`, `tests/unit/test_trace.py` (50 tests). Suite: **215 passing**.
>
> | Gate | Result |
> |---|---|
> | **P1-a** | **PASS** — chain recovered exactly; decoy edges that precede the funds' arrival are excluded in both directions |
> | **P1-b** | **PASS** — 27 parametrised cases across fan ∈ {5,40,200} × cap ∈ {1,8,64} × horizon ∈ {1,3,5}; bounds also asserted on every one of 1,200 real-corpus traces |
> | **P1-c** | **PASS** — p95 **168.53 ms** at horizon 4 against a 2,000 ms gate, 12× inside it |
>
> Latency on HI-Small (5,077,237 rows, 515,078 accounts; index built once in 12.3 s):
>
> | Horizon | p50 | p95 | max | mean edges | truncated |
> |---|---:|---:|---:|---:|---:|
> | 2 | 118 ms | 146 ms | 1,272 ms | 162 | 33.0% |
> | 3 | 118 ms | 144 ms | 186 ms | 311 | 34.2% |
> | 4 | 137 ms | 169 ms | 191 ms | 491 | 34.2% |
>
> **Two findings that change how P2 must consume a trace.**
>
> **A third of traces are truncated.** At the default cap of 64, 34% of sampled traces hit
> it. That is the cap working — but it means a trace is often a *sample* of the
> neighbourhood, not the neighbourhood. `TraceResult.is_complete` reports this, and P2 must
> carry it into the evidence bundle rather than presenting a truncated subgraph as a
> complete picture.
>
> **Per-hop amounts grow with depth, and must never be read as attribution.** The busiest
> account traces to 86.0M at depth 1, 210.3M at depth 2, 837.5M at depth 3 — because depth 3
> sums *all* transactions of 186 accounts, not the traced funds. Once money enters an account
> it is commingled with the balance already there, and transaction data alone cannot say what
> moved on. `per_hop()` documents this; the case view must not present it as "funds traced".
>
> **One defect found and fixed during the phase.** Reading epoch integers straight off a
> datetime column yields whatever *resolution* pandas 2 assigned it — microseconds on one
> frame, nanoseconds on another — while a scalar anchor is always nanoseconds. That mismatch
> scaled every time comparison by a thousand and let a 40-day hop clear a 7-day gap limit,
> silently, still returning plausible edges. All conversions now route through one helper,
> pinned by a regression test parametrised over four resolutions.

---

### P2 — Evidence bundle with reasons *(FR-09, FR-11)* · 3h

The schema is already designed in Unified Plan v2 §30.2 and the project already writes a
model package with provenance, so this is assembly over an existing pattern.

The bundle carries: case ID, the traced subgraph from P1, the transaction set, local SHAP
reasons mapped to reason codes, the threshold and its provenance, model version and corpus
hash, and the §1 coverage caveat.

| Gate | Threshold |
|---|---|
| **P2-a** | v2 §30.1 holds — every field reads from the evidence object; nothing generates its own facts |
| **P2-b** | Every reason code resolves to transactions present in the bundle |
| **P2-c** | Round-trips: export, re-import, byte-identical |
| **P2-d** | Every non-ACH bundle carries the coverage warning |

**Deliverable:** `evidence/bundle.py` + tests + one exported sample case.

> ### P2 — COMPLETE, 2026-09-21
>
> `evidence/bundle.py`, `evaluation/interpretation.local_contributions`,
> `tests/unit/test_evidence.py` (22 tests). Suite: **237 passing**.
> Sample case: `reports/cases/FG-18aedbed.json` (4,490 bytes).
>
> | Gate | Result |
> |---|---|
> | **P2-a** | **PASS** — `check_internal_consistency()` recomputes `accounts`, `transaction_ids`, `per_hop` counts and amounts, and the rail tally from the path; six tests corrupt each in turn and assert it is caught |
> | **P2-b** | **PASS** — every reason cites only transactions in the bundle, enforced on build and on import |
> | **P2-c** | **PASS** — export → import → export byte-identical, verified on the fixture *and* on the real exported case |
> | **P2-d** | **PASS** — fired on the real case, which reached a Cheque transaction at depth 2 |
>
> **What the real case exposed.** Built from the shipped E2 package against the test period
> (761,422 rows after the package's own split boundary), the highest-scoring true positive
> traced to three transactions across three accounts. Its reasons, ranked by absolute
> contribution:
>
> | Reason | Contribution | |
> |---|---:|---|
> | `TX_IS_CROSS_CURRENCY_LOWERED` | −2.960 | |
> | `TX_PAYMENT_TYPE_CODE_RAISED` | **+2.926** | |
> | `GFP_F185_RAISED` | +1.998 | opaque |
> | `GFP_F183_LOWERED` | −1.997 | opaque |
> | `TX_IS_SELF_TRANSFER_LOWERED` | −1.617 | |
>
> **The largest factor raising this case's score is the ACH artifact** — about 1.5× the
> strongest graph feature. [ADR-007](ADR-007-payment-type-artifact.md) has been a number in
> a table until now; this is what it looks like as an explanation handed to a person.
>
> > **Correction, 2026-09-21.** This section first reported `TX_PAYMENT_TYPE_CODE_RAISED`
> > at **+8.599**, *"more than three times the strongest graph feature"*. That was wrong.
> > `TraceResult.edges` renumbered its index 0..n-1, so the case's SHAP values were taken
> > from test-set rows 0–2 instead of the case's own three transactions. The reasons cited
> > the right transaction ids with contributions from unrelated rows. The fixture test did
> > not catch it because there the traced rows *were* rows 0–2. Fixed at the root —
> > `edges` now keeps the source frame's index — and pinned by two regression tests that
> > place the traced rows after decoys. The table above is the regenerated case. The
> > direction of the finding survives; its magnitude was overstated about threefold.
>
> **The shipped package was the artifact-inclusive model.** E2 (168 features) is what
> `models/flowguard_E2_v1/` contains. A first attempt to build the case artifact-free
> failed on a schema mismatch, which is how this surfaced. **Resolved:** the artifact-free
> arm is now packaged as `models/flowguard_A4_v1/` (167 features, PR-AUC 0.1400 ± 0.0030,
> all eight correctness gates passing) and is the model this repository ships.
>
> **Half the reasons are unreadable.** Four of eight cite `gfp_f*` features. The graph
> library exposes no feature names — no `get_feature_names` on the preprocessor — so those
> are positions, not concepts, and they carry 69.8% of the model's attribution mass. The
> bundle marks them `opaque: true` rather than inventing labels. **This is the ceiling on
> FR-09**: per-case explainability is quantitative for the dominant signal and semantic only
> for the row-local minority.
>
> **Calibrated scores saturate.** The top true positive scores exactly `1.000000` against a
> threshold of `0.009975`. Isotonic calibration pins its top bin, so the score cannot rank
> the most severe cases against one another — which P5's queue ordering has to account for.
>
> **What the bundle refuses to carry.** `primary_typology`, `secondary_typologies`,
> `risk_category` and the `vflow_*`/`tflow_*` features from v2 §30.2 are all absent. They
> describe work that does not exist — typology classification is P4, the value-flow family
> was never built, the adaptive family was rejected — and a test asserts they stay absent
> rather than being filled with guesses.

---

### P3 — Cascade *(FR-12)* · 3.5h

P8 fails at ~450 tx/s against 1,000, and per ADR-013 that number describes AMLSim — on real
data it was ~139 tx/s. The library is closed, so the gate cannot be met by running the same
thing faster. It can be met by **not running it on everything**:

```text
all transactions ─► tier 0: row-local features, calibrated score   (~50k tx/s)
                       │
                       └─ top 5% ─► GFP graph features ─► final score
```

At K = 5% the extractor sees one transaction in twenty, so 1,000 tx/s end-to-end needs only
~50 tx/s from GFP — inside what it sustains even on ETH. Plus P1's degree cap.

| Gate | Threshold | On failure |
|---|---|---|
| **P3-a** | End-to-end ≥ **1,000 tx/s** on HI-Small | Report P8 still failing, with the cascade figure |
| **P3-b** | Recall @1% ≥ **95%** of full extraction (≥ 53.4% vs A4's 56.2%) | Raise K and re-measure, or publish the trade as the cost |
| **P3-c** | Holds ≥ 1,000 tx/s on the **ETH** slice | Headline becomes "meets the gate on synthetic data only" |

**P3-c is the one that matters.** Passing on AMLSim and failing on ETH repeats exactly the
mistake ADR-013 documents.

> ### P3 — COMPLETE, 2026-09-21 · **throughput solved, recall not**
>
> `features/cascade.py`, `tests/unit/test_cascade.py` (12 tests).
>
> | Arm | PR-AUC | Recall @1% | Throughput |
> |---|---:|---:|---:|
> | tier 0 — row-local only | 0.0069 | 11.9% | 89,524 tx/s |
> | tier 1 — + graph | 0.1362 | 56.0% | 450 tx/s (extraction) |
>
> | K | Recall @1% | Share of full | End-to-end | P3-a | P3-b |
> |---:|---:|---:|---:|:--|:--|
> | 1% | 11.9% | 20.9% | 29,947 tx/s | PASS | **FAIL** |
> | 2% | 16.9% | 29.9% | 17,981 tx/s | PASS | **FAIL** |
> | 5% | 29.3% | 51.6% | 8,178 tx/s | PASS | **FAIL** |
> | 10% | 39.2% | 69.2% | 4,285 tx/s | PASS | **FAIL** |
>
> **P3-a passes everywhere by a wide margin. P3-b fails everywhere.** At the planned K = 5%
> the cascade keeps 51.6% of full-extraction recall against a 95% bar — it does not miss the
> gate, it misses it by half.
>
> **Why, and it is not a tuning problem.** Tier 0 reaches 11.9% recall where tier 1 reaches
> 56.0%. The cheap filter cannot identify which transactions the expensive model would flag,
> because the positives graph features find are invisible to row-local features — that is the
> entire reason graph features are worth 21× in the first place. **The independence that makes
> them valuable is what makes them un-prefilterable by a tabular score.** Raising K does not
> fix it: even routing 10% of the corpus recovers only 69% of the recall, and the curve is
> flattening, so the K that would clear 95% is close to routing everything.
>
> **P3-c, on ETH: throughput PASSES, and its recall must not be quoted.** End-to-end rates on
> the 1.25M-edge slice are 10,781 / 6,072 / 2,628 / 1,351 tx/s at K = 1/2/5/10%, all clear of
> the gate. The recall column from that run is *not* reported: ETH has no transaction-level
> truth, so evaluating there means scoring the weak proxy at transaction level, which
> [ADR-012](ADR-012-account-disjoint-proxy.md) forbids. The give-away is retention of 143.5%
> at K = 1% — a cascade cannot beat the model it is filtering for; the numbers are noise
> around a PR-AUC of 0.002.
>
> **Consequence for FR-12.** The cascade is not the answer to P8. Meeting the throughput gate
> this way costs about half the detections, and a detector that finds half as much laundering
> at twenty times the speed is not a better detector. **P8 stands as failed**, and the honest
> statement is that this method's cost is intrinsic (ADR-013), not an engineering oversight.
> The code stays in the tree, measured and rejected, as the adaptive family did.

---

### P4 — Typology hinting *(FR-06)* · 2.5h

PS9 asks for layering, round-tripping and structuring **by name**. Today per-typology recall
is *measured* but nothing *classifies*.

`HI-Small_Patterns.txt` annotates 370 patterns across eight typologies. **Stated before
building:** that is 2,554 transactions, ~62% of positives are unannotated, and 140 of 370
patterns are truncated at a boundary ([ADR-002](ADR-002-boundary-policy.md)). Enough for a
**hint with calibrated confidence**; not enough for a classifier anyone should trust
unsupervised. The deliverable is named accordingly.

A multi-class head over existing graph features, annotated rows only, same split. Emits a
ranked typology above a confidence floor, `"unclassified"` below it.

| Gate | Threshold | On failure |
|---|---|---|
| **P4-a** | Macro-F1 beats a stratified-random baseline by **> 2σ**, 3 seeds | Ship as "not supported by this corpus" — a documented negative result |
| **P4-b** | Calibrated, ECE < **0.10** | Show a rank with no probability attached |

> ### P4 — COMPLETE, 2026-09-21 · **not supported by this corpus**
>
> `models/typology.py`. Fitted on 1,529 annotated training rows, evaluated on 564 annotated
> test rows.
>
> | | |
> |---|---:|
> | macro-F1, 3 seeds | **0.2523** |
> | stratified-random baseline | 0.1258 |
> | delta | **+0.1265** |
> | 2σ bar | **0.1405** |
> | ECE | **0.1678** |
>
> **P4-a FAILS and P4-b FAILS.** The hinter doubles the random baseline, and still misses the
> pre-registered bar — by 0.014. That is close enough to be tempting and the rule was fixed
> before the number existed, so it is recorded as a miss and the bar is not moved. Confidence
> is also badly calibrated at 0.168 against a 0.10 ceiling, so the probabilities would have
> been decoration.
>
> Per-class F1 shows where the little signal there is lives:
>
> | Typology | F1 | | Typology | F1 |
> |---|---:|---|---|---:|
> | GATHER-SCATTER | 0.558 | | FAN-IN | 0.257 |
> | SCATTER-GATHER | 0.342 | | BIPARTITE | 0.091 |
> | STACK | 0.340 | | CYCLE | 0.079 |
> | FAN-OUT | 0.338 | | RANDOM | 0.013 |
>
> Fan-shaped typologies are distinguishable; **CYCLE at 0.079 is not**, which is awkward
> given round-tripping is one of the three PS9 names by name. The constraint stated before
> building held: 2,554 annotated transactions across eight classes is not enough.
>
> **FR-06 therefore remains partial.** The module ships, is tested, and is wired into nothing
> — the same disposition as the adaptive family.

---

### P5 — Case view *(FR-10)* · 3h

One page that reads exported bundles and renders the queue, the case, the traced subgraph
and the reasons. **No backend, no state machine, no database** — the bundles are the state,
and a queue ordered by calibrated score is a sort.

Disposition capture (open / escalated / closed-false-positive / closed-reported) writes back
to the bundle. That is the part with lasting value: analyst outcomes are the only route this
project has to real labels, and the 2.3× enrichment is exactly what they would measure.

| Gate | Threshold |
|---|---|
| **P5-a** | Every figure shown traces to a bundle field; the page computes no metric of its own |
| **P5-b** | The coverage caveat is visible on the case, not behind a link |

> ### P5 — COMPLETE, 2026-09-21
>
> **[FlowGuard Case Desk](https://claude.ai/artifact/UpGYYThbJiNrnsV5U9hkNC)** — queue rail, case
> header, fund flow, reasons, provenance and disposition. No backend, no state machine, no
> database: the bundles are the state and the queue is a sort, exactly as scoped.
>
> | Gate | Result |
> |---|---|
> | **P5-a** | **PASS** — every figure carries a visible grey label naming the bundle field it came from (`risk.score`, `trace.per_hop`, `reasons`…). The page derives nothing; it has no arithmetic beyond formatting |
> | **P5-b** | **PASS** — the coverage limit renders as a bordered block on the case itself, with each rail chipped *demonstrated* or *not demonstrated*, and every non-ACH hop striped in the flow |
>
> **The queue holds one case, and says so.** One bundle has been exported, so the rail shows one
> row and states that it shows what exists rather than a sample. Padding it with invented cases
> would have been the easy demo and the wrong one.
>
> **Disposition writes back to the bundle**, not to a database — the page copies an updated JSON
> with `disposition` and the note filled in. That keeps the bundle the single source of truth
> (v2 §30.1) and means analyst outcomes accumulate as files rather than in a system nobody built.
> It is also the only mechanism in the project that could eventually measure the 2.3%
> false-positive enrichment against human judgement rather than a proxy.

---

### P6 — Unsupervised spike *(FR-07)* · 1h

An Isolation Forest over the same feature view, training rows only, as **a measured arm, not
a feature**. One hour, because the answer is what matters and the harness already exists.

| Gate | Threshold | On failure |
|---|---|---|
| **P6-a** | Catches ≥ **5** positives at the 1% budget the supervised model misses | "Adds no independent coverage" |
| **P6-b** | Ensemble beats supervised alone by **> 2σ** | Rejected and written up, as in [ADR-011](ADR-011-adaptive-features-rejected.md) |

**Expect rejection.** On a corpus whose laundering sits on one payment rail there may be no
unknown-pattern structure left to find. P6-a is the more interesting test — a detector that
merely agrees with the supervised one has added nothing, however the ensemble score moves.

> ### P6 — COMPLETE, 2026-09-21 · **P6-a PASS, P6-b FAIL**
>
> | | PR-AUC |
> |---|---:|
> | supervised | **0.1400** |
> | isolation forest | 0.0093 |
> | rank-average ensemble | 0.0395 |
>
> **P6-a PASSES.** The isolation forest catches **20 positives on average (18 / 20 / 22 across
> seeds)** at the 1% budget that the supervised model misses — far past the bar of 5. It is
> genuinely looking at something else.
>
> **P6-b FAILS, and badly.** The naive rank-average ensemble scores 0.0395 against the
> supervised model's 0.1400 — a delta of **−0.1004** against a 2σ bar of 0.1101. Averaging a
> 0.0093 detector with a 0.1400 one destroys the good one.
>
> **The honest reading is not "rejected".** The expectation going in was that an unsupervised
> arm would find nothing independent; it found ~20 positives per seed that the supervised
> model does not. What failed is the *combination*, and a rank average was always the crudest
> possible one. The result is "adds independent coverage, cannot be naively ensembled" —
> which is a more interesting finding than either gate was written to capture, and the
> pre-registered rule still governs: **it is not wired into any reported model.**

---

## 3. What is cut, and why

**FR-03 (entity representation) and FR-08 (full risk scoring) stay open.** They need
customers, branches, products and channels. No available corpus has them, so the only route
is the synthetic augmentation layer in v2 §29.3 — six hours to generate entities the
detector then "discovers".

This project's asset is that its numbers are trustworthy. Manufacturing the data that makes
two requirements look closed is the fastest way to spend that, for the weakest two items on
the list. **Leaving them open and saying why is worth more than closing them with invented
data.**

If a demo later needs bank context, build it then, behind an automated test asserting no
metrics table ever mixes real-corpus and synthetic figures — a CI firewall, not discipline.

---

## 4. Schedule

| Phase | Hours | Cumulative | Leaves behind |
|---|---:|---:|---|
| **P1** — fund tracing | 3:00 | **3:00** | PS9's headline capability |
| **P2** — evidence bundle | 3:00 | 6:00 | A complete detect → trace → explain → export path |
| **P3** — cascade | 3:30 | 9:30 | A P8 verdict on both corpora |
| **P4** — typology hinting | 2:30 | 12:00 | A named-typology result, or a negative one |
| **P5** — case view | 3:00 | 15:00 | Something an analyst can open |
| **P6** — unsupervised spike | 1:00 | **16:00** | A measured arm, likely rejected |

**Stop points that still deliver.** After P2 there is a working detect-trace-explain-export
path — the demo exists at six hours. After P3 the failing throughput gate has a verdict.
P4–P6 are additive and independently droppable.

---

## 5. What 16 hours does not fix

**The ACH blindness.** Nothing here touches it, because no feature family can teach a model
behaviour the corpus does not contain. It needs a corpus whose laundering spreads across
rails. Until then every case inherits the limitation — which is why §1 makes surfacing it a
build requirement rather than a documentation task.

**The 2.3× false-positive enrichment.** Tier B attacked it directly and failed. P5's
disposition capture is the first mechanism that could *measure* it against analyst judgement
rather than a proxy, but measuring is not fixing.

**Twenty positives.** The cross-dataset result establishes a direction and cannot establish a
magnitude. Nothing here produces more labelled accounts on a real network.

Two requirements stay open by choice and three stay qualified by evidence. The final report
should say so in the same place it reports the successes.
