ts# FlowGuard — Project Status

**Date:** 2026-09-20
**Final model:** `E2` — transaction + GFP graph features, 168 features
**Package:** [`Project/flowguard/models/flowguard_E2_v1/`](../Project/flowguard/models/flowguard_E2_v1/)

---

## 1. What exists

| | |
|---|---|
| Source | 6,912 lines / 41 modules |
| Tests | 2,204 lines / 16 files, **160 passing** (7 marked `slow`, deselected by default) |
| ADRs | 11 |
| Experiments logged | E0, E1, E2, ABLATION (7 arms), Tier C transfer |
| Leakage suite | all 7 checks required by plan v3 §11 |

The pipeline runs end to end: ingest → validate → chronological split → features →
train → calibrate → evaluate → gate → package.

---

## 2. The headline result

Seven-arm ablation on HI-Small (5,077,237 rows, 4,522 positives, base rate 0.089%),
three seeds per arm, one change per arm. Pooled seed sd **0.0030**, so the
pre-registered inclusion bar is **2σ = 0.0059**.

| Arm | Features | PR-AUC | Recall @1% |
|---|---:|---:|---:|
| A1 — tabular, artifact present | 13 | 0.0411 ± 0.0038 | 40.8% |
| A2 — tabular, artifact removed | 12 | 0.0065 ± 0.0001 | 11.6% |
| A3 — + graph, artifact present | 168 | 0.2048 ± 0.0065 | 66.2% |
| **A4 — + graph, artifact removed** | 167 | **0.1400 ± 0.0030** | 56.2% |
| A5 — adaptive alone | 21 | 0.0041 ± 0.0001 | 7.4% |
| A6 — graph + adaptive | 176 | 0.1073 ± 0.0071 | 52.8% |
| `E_LEAK` — deliberate leak control | 12 | 0.0052 ± 0.0001 | 11.4% |

**Graph structure is the finding.** Artifact-free, it lifts PR-AUC from 0.0065 to
0.1400 — a 21× improvement, far outside noise. Graph features carry 69.8% of SHAP mass.

**The leaky control found nothing.** `E_LEAK` uses a random split and fits encoders on
everything, and scores *below* the honest A2. A random split manufactures no signal on
this corpus, which is direct evidence the chronological split conceals no leakage.

---

## 3. What the gates caught

Four of eleven ADRs record defects that would have produced impressive false results.

* **ADR-007 — the payment-type artifact.** 2,553 of 2,554 annotated pattern rows are
  ACH. `payment_type` was worth **84% of the tabular baseline**. Surfaced by gate C8
  (no feature above 50% of mean |SHAP|) firing at 56.8%.
* **ADR-003 — the sparse tail.** `day_of_week` alone outscored the full model, because
  over a 10-day corpus it proxies the calendar date and the generator's tail is 59%
  laundering. Tail trimmed, calendar features removed.
* **ADR-004 — GFP batch leakage.** `transform` lets an edge see later edges in the same
  batch. `batch_size=1` is now enforced for every reported result, with a test.
* **ADR-002 — the purge policy erased the corpus.** An automatically derived 8d10h
  buffer against a 10-day corpus drops 100% of rows. Replaced with `HARD_CUT`.

---

## 4. Where it fails

**The validated model is blind to every rail except ACH.** Recall at the 1% budget:

| Rail | Recall | Caught |
|---|---:|---:|
| ACH | 75.3% | 599 / 796 |
| Bitcoin | 10.0% | 1 / 10 |
| Cheque | 0.0% | 0 / 53 |
| Credit Card | 0.0% | 0 / 30 |
| Cash | 0.0% | 0 / 17 |

**100 laundering transactions on non-ACH rails; one caught.** Gate P4 passed at 66.2%
against a 45% target — arithmetically correct and substantively hollow, earned almost
entirely on one rail. This is ADR-007 reappearing in the final model's behaviour.

**False positives on legitimate complexity more than doubled.** The hard-negative
control moved from 1.02× (tabular) to 2.3× (graph): across 172,158 structurally complex
but benign transactions, E2 alerts at 2.49% against 1.09% for ordinary benign traffic.
Some recall is bought by flagging merchant hubs, payroll fan-out and treasury sweeps.

**The headline number is less stable across time than it looks.** Evaluated on five
consecutive ~9-hour windows, the same model scores 0.153, 0.298, 0.106, 0.238 and 0.172
— a spread of 0.192 against a mean of 0.193, so the best window is nearly 3× the worst.
Gate P7 passes, but only because it tests for *monotone decline*; it does not test
variance, and a gate that would have caught this was never written.

Much of the movement tracks the base rate, which itself varies 3.5× across those windows
(0.077% to 0.272%), and PR-AUC is base-rate sensitive. That is an explanation, not a
defence: the single headline figure of 0.2048 is a point estimate on one split, and the
honest summary is 0.19 ± 0.08 across time.

**Nothing in this project fixes that.** Tier B was the attempt, and it failed
(ADR-011): the adaptive neighbourhood family cost 0.0326 PR-AUC, five times the noise
bar. Degree-normalisation protects hubs by suppressing the raw structural counts that
were doing the detecting.

---

## 5. Tier C — does the result transfer to a real network?

**Corpus:** XBlock ETH phishing graph, a contiguous 1.25M-edge prefix of 2018-03..2018-04.
**Question:** *is this account a phisher?* — not HI-Small's *is this transaction part of
laundering?* Different question, different unit, different base rate. The two are
reported side by side and never merged.

| Arm | Features | Account PR-AUC (3 seeds) |
|---|---:|---:|
| T1 — tabular only | 9 | 0.0031 ± 0.0002 |
| **T2 — + GFP graph** | 170 | **0.0490 ± 0.0052** |

Seed test: **+0.0460 against a 2σ bar of 0.0054** — clears it eightfold.

**But the seed bar is the wrong uncertainty here.** Only 20 illicit accounts fall in the
scored test set, and seed spread measures "would another initialisation change this",
not "would another sample of 20 accounts". A paired bootstrap over the 16,527 scored
accounts gives the honest interval:

| | Point | 95% CI |
|---|---:|---:|
| T1 | 0.0032 | [0.0016, 0.0071] |
| T2 | 0.0536 | [0.0216, 0.1263] |
| **Delta** | **+0.0504** | **[0.0187, 0.1231]** |

**2,000 of 2,000 resamples favour the graph arm.** The direction is not in doubt. The
magnitude spans a 6.6× range and is not pinned down — which is what 20 positives buys.

**The claim this supports:** graph-structural features carry real signal on a real
network, under a protocol ([ADR-012](ADR-012-account-disjoint-proxy.md)) that rules out
memorising accounts through their structure. **The claim it does not support:** any
specific effect size, or that 0.0490 means anything next to HI-Small's 0.2048.

### What Tier C cost, and what that revealed

Extraction was abandoned at 1.25M of 2.02M rows after the cost per 250k block doubled at
every checkpoint, projecting past fifteen hours. Chunked persistence
([ADR-009](ADR-009-chunked-extraction.md)) meant the completed prefix survived and the
experiment ran on it.

Investigating why produced the sharper finding:
**[ADR-013](ADR-013-degree-skew-dominates-cost.md) — extraction cost tracks degree skew,
not corpus size.** At equal edge count ETH's 99.9th-percentile degree is 1,034 against
HI-Medium's 11, and 13.3% of ETH's edge endpoints sit on 0.01% of its vertices against
1.0% for HI-Medium. Real networks are scale-free; this generator is not.

**So the P8 throughput gate and the S5 envelope describe AMLSim, not the method.** The
signal transfers. The performance envelope does not.

---

## 6. Gate results

Eight of eight **correctness** gates pass, including the conditional C8. Two
**performance** gates fail and are reported as failures:

* **P8 — extraction ≥ 1,000 tx/s.** Measured ~450 tx/s steady state on HI-Small. **FAIL** — and per [ADR-013](ADR-013-degree-skew-dominates-cost.md) the gate is not transferable: on a real scale-free network the method runs an order of magnitude slower still.
* **P9 — peak RSS ≤ 10 GB.** Measured 10.88 GB. **FAIL.**
* **P3 — a Tier B family beats E2 by 2σ.** −0.0326. **FAIL**, recorded not hidden.
* **P4 — recall ≥ 45% @1%.** 66.2%, but ACH-only, so reported as a conditional pass
  against a target that was itself pre-registered on contaminated numbers (ADR-010).

---

## 7. Honest assessment

**What is strong.** The gate discipline earned its cost — four defects caught before
anything depended on them, and the artifact finding turned a flattering number into a
real research question. The graph result is large, replicated across seeds, and
survives the removal of the artifact that inflated its predecessor.

**What is weak.** One synthetic generator. A model whose recall collapses off one
payment rail. An extraction step that misses its own throughput and memory gates. A
2.3× false-positive enrichment on legitimate complexity that remains unaddressed.

**What Tier C changed.** External validity is no longer entirely unmeasured. Graph
features carry signal on a real blockchain, in the right direction, decisively — while
the throughput envelope turned out to be a property of the generator rather than of the
method ([ADR-013](ADR-013-degree-skew-dominates-cost.md)).

**What would most improve it.** A corpus with laundering spread across payment rails, to
turn the ACH blindness in §4 from a disclaimer into a measurement. Failing that, more
labelled accounts on a real network: 20 positives establishes a direction and cannot
establish a magnitude.
