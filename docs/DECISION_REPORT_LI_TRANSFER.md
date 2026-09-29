# Decision report — does the approach survive fresh data?

**2026-09-29.** Written to answer one question: *keep the graph-feature approach, or change
it?* Evidence: `runs/G1_zero_shot_LI-Small-2M.json`, `runs/G1_diagnosis_LI-Small-2M.json`,
`runs/G1_diagnosis_HI-Small.json`. Everything below is measured; nothing is projected.

## Bottom line

**Keep the approach, narrow the claim, and add one thing.**

- **The graph method works where there is graph structure to find.** It catches 95% of
  patterned laundering on HI-Small, and on fresh data it still ranks patterned laundering at
  the 98.7th percentile — near misses, not blindness.
- **It is weak on laundering with no structure, on both corpora** — 28% recall on HI-Small,
  9.5% on LI-Small, and 1–3% for unstructured laundering off ACH on either. That is a limit
  of the method, not a failure to transfer, and no graph method will remove it.
- **The headline failed on LI-Small mainly because LI-Small is mostly unstructured** (88% of
  its laundering, against 25% on HI-Small). Composition explains about two-thirds of the
  drop; a genuine per-group drop explains the rest.

Changing the method would throw away the part that works in order to chase the part no graph
method covers. The right move is to say precisely what the model detects, and — if time
allows — add a detector aimed at the unstructured part.

## The evidence

Recall at a 1% alert budget, shipped model, no retraining. Brackets are 95% Wilson intervals.

| | HI-Small | LI-Small prefix |
|---|---:|---:|
| All laundering | **78.1%** | **13.3%** [8.7–19.8] |
| Share that is **patterned** (an injected typology) | 75% | **12%** |
| Patterned | **95.3%** [94.0–96.3] | 41.2% [21.6–64.0] · 7 of 17 |
| Share that is **untagged** (no typology) | 25% | **88%** |
| Untagged | 27.9% [24.0–32.2] | 9.5% [5.5–15.9] |
| Untagged, off ACH | **1.4%** [0.4–5.0] | **3.1%** [0.8–10.5] |
| Median rank of patterned positives | 99.9th pct | 98.7th pct |

**Splitting the drop from 78% to 13%:**

| Cause | Points | How measured |
|---|---:|---|
| LI-Small is mostly unstructured | **~42** | HI-Small's per-group recall applied to LI-Small's mix gives 36% |
| The model does worse on each group | **~23** | 36% expected, 13% observed; both group intervals sit clear of HI-Small's |

The first cause is the method's scope. The second is ordinary distribution shift — a model
trained on one corpus meeting a different base rate (0.036% against 0.177% in test) and
different traffic — and its standard remedy is training on the target data.

## The options, with what each costs

| | Option | Time | What it buys | Risk |
|---|---|---:|---|---|
| **A** | **Narrow the claim**: "detects structured laundering — 95% of patterned cases on HI-Small; unstructured laundering is a known limit on every corpus" | **1 h** | An honest, defensible headline. Judges who probe transfer find it already stated | None |
| **B** | **Retrain on full LI-Small** (the G2 run the prefix was too small for) | **3–4 h** | Tests whether per-corpus training closes the ~23-point per-group drop. That is how banks deploy AML models anyway | `run_benchmark` needs the per-partition read first (~30 min), or 6.9M rows will not fit in memory |
| **C** | **Add a detector for unstructured laundering** — account-level behaviour and velocity scoring, combined with the graph score | **1–2 days** | The only option that moves the 88% | Uncertain payoff; the earlier unsupervised arm (P6) did not combine usefully and was never re-run after ADR-015 |
| **D** | **Replace the method** (e.g. a graph neural network) | Not feasible | — | Not on the package list, not buildable on the s390x VM, and it would face the same unstructured-laundering problem |

## Recommendation, given the time you have

1. **Do A now.** One hour, and it turns the failure into a finding: the project can say
   exactly what its model catches and where the published benchmark's number comes from.
2. **Run B if you have one more afternoon.** It is the cheapest way to learn whether the
   per-group drop is a training-data problem, which is the likely answer.
3. **Do not start C or D before the deadline.** C is the right long-term direction and is
   worth naming in the presentation as future work; it is not a same-week task.

## Caveats that belong beside any of these numbers

- **Small counts on LI-Small.** 17 patterned positives; the 41.2% interval runs from 22% to
  64%. It supports "still detected, less well", not a precise figure.
- **A prefix, not the whole corpus.** The first 1.5 days, and the sparsest stretch of
  LI-Small (base rate 0.023% against 0.050% overall).
- **One generator.** Both corpora come from IBM's AMLSim, so this is a base-rate and
  composition contrast, not external validation. The Ethereum result (graph features add
  +0.050 account PR-AUC on a real network) remains the only independent evidence.
- **"Patterned" means injected by the simulator.** Real laundering does not arrive labelled
  with its typology; the split is a property of this benchmark, which is why the claim in
  option A is phrased in terms of structure rather than labels.
