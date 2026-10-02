# Problems we can fix ourselves

**As of 2026-09-26.** Everything here is inside our control: no VM access, no other team,
no data we do not have. If it is on this page and still open, the only thing in the way is
our own time.

Companion pages: **[PROBLEMS_2_BLOCKED.md](PROBLEMS_2_BLOCKED.md)** (waiting on someone
else) · **[PROBLEMS_3_LIMITS.md](PROBLEMS_3_LIMITS.md)** (cannot be fixed, only stated).
The findings themselves stay in [`../PENDING.md`](../PENDING.md) and
[`OPEN_ITEMS.md`](OPEN_ITEMS.md); this page is about *work*, and sorts it by who can do it.

Each entry says what is wrong, why it matters, the fix, what it costs, and how we will know
it is done. IDs are stable, so they can be quoted in commits and messages.

| | Part A — no compute needed | Part B — needs a run |
|---|---:|---:|
| Items | 8 | 6 |
| Effort | about one working day | about three working days |

---

# Part A — fixable now, no compute

## FIX-01 · This session's work is uncommitted
**What is wrong.** 38 files sit in the working tree on branch `winning-plan`: the metrics
fix, the JSON package exports, native TreeSHAP, the memory-bounded scoring path, both
notebooks, the regenerated samples and the reply to the handoff.

**Why it matters.** None of it survives a lost machine, none of it is visible to anyone
else, and the other team cannot take our fixes at source while they exist only here.

**Fix.** One commit of the whole set on `winning-plan`, grouped in the message as: handoff
fixes (R3, R8), the TreeSHAP defect, the scoring memory fix, and the Keras decision.
Pushing, or merging to `main`, is a separate decision.

**Effort.** Minutes. **Done when** `git status` is clean and 279 tests still pass.

## FIX-02 · The shipped validation report quotes a stale number — **DONE 2026-09-28**
**What is wrong.** `STATUS.md:60` records it: gate P1's line in
`models/flowguard_V2_v1/validation_report.md` reads **0.5587**, the *previous* v2 build's
registry entry, read before the current build overwrote it. The model's real PR-AUC is
0.595.

**Why it matters.** It is the one number inside the shipped package that contradicts every
other number we publish, and the package is where a careful evaluator looks first.

**Fix, and the cause was not what this entry assumed.** Rebuilding would not have helped:
the number comes back on every build. Gate P1 reads `registry.load(model_id)`, and the
current run's record is written at the *end* of validation — so each build compares itself
against its predecessor wearing the same name. The V2 build read the superseded
214-feature entry (0.5587) for a model scoring 0.5949. P1 now uses the metrics the run has
just measured, and only falls back to the registry for the *other* side of the comparison
(E1, E0), which is what it was always for.

**Effort.** 40 minutes, most of it finding the cause. **Done:** the next build's report
quotes the model it validated. The verdict never changed — P1 passed either way, by +0.52
over E1 — but it was quoting another model's number to do it.

## FIX-03 · `shap_summary.json` describes a model that never scores
**What is wrong.** It was produced with `shap.TreeExplainer`, which truncates an
early-stopped booster at `best_iteration` — 741 of the model's 841 trees — while scoring
uses all 841. The global importances therefore describe a different model from the one
that produces the scores.

**Why it matters.** It is the same defect we fixed for per-case explanations on 2026-09-26
(`WINNING_PLAN.md`), left behind in the package's global summary.

**Fix.** Regenerate through `flowguard.evaluation.interpretation.explain`, which now uses
XGBoost's native TreeSHAP. Comes free with a package rebuild (COMP-03).

**Effort.** Minutes. **Done when** the summary is written by code with no `shap` import.

## FIX-04 · Experiment records that exist only on this machine
**What is wrong.** The Tier C, P3, P4 and P6 run records live in the external data folder
and have never been in git (`PENDING.md` B1). The benchmark runs were tracked on
2026-09-22; these were missed.

**Why it matters.** Every number they support is unreproducible for anyone but us — the
exact criticism we already fixed for the benchmark runs.

**Fix.** Copy the JSON and logs into `Project/flowguard/experiments/runs/` and add a row
each to that directory's README table. Leave the raw feature caches out: they are gigabytes
and can be regenerated.

**Effort.** Under an hour. **Done when** every number in STATUS traces to a tracked file.

## FIX-05 · Machine-specific paths in the code
**What is wrong.** `configs/` and `_throughput_from_log` carry absolute paths from this
build machine (`/mnt/c/Users/vikam/...`). `PENDING.md` B2.

**Why it matters.** A fresh clone cannot follow them, and they are the first thing a
reviewer notices when judging reproducibility.

**Fix.** Read each from an environment variable with the current value as the default,
exactly as `scripts/measure/_paths.py` already does for `FLOWGUARD_DATA`.

**Effort.** Under an hour. **Done when** the suite passes with `FLOWGUARD_DATA` pointing
somewhere else.

## FIX-06 · The package can still be loaded through pickles
**What is wrong.** `calibrator.json` and `encoders/categorical.json` now ship and
`score.py` prefers them, but `calibrator.pkl` and `encoders/categorical.pkl` are still
written on every build and still work as a fallback. A pickle written under numpy 2 cannot
be read under numpy 1.24 at all. `PENDING.md` B3, in part.

**Why it matters.** While the pickles exist, a consumer can load them by accident and hit a
failure we have already solved.

**Fix.** Keep writing them for one release for older readers, but make `score.py` refuse a
package that has *only* pickles rather than silently falling back, and say so in
`contracts/README.md`. Drop them in the release after.

**Effort.** Under an hour. **Done when** a package with the pickles deleted loads, scores
and passes the contract tests — which is already true today.

## FIX-07 · `Vika/` in the other team's repository — *reclassified 2026-09-26*
**Listed here in error.** `Vika/` exists only inside their tree; there is no copy on this
machine, so there is nothing for us to take onto a branch. What it holds is our work, which
already lives here in its own right, so the remaining action is theirs — delete it. Tracked
as **BLK-09** in [PROBLEMS_2_BLOCKED.md](PROBLEMS_2_BLOCKED.md).

## FIX-08 · Repository litter
**What is wrong.** An empty `Project/flowguard/linuxone/nonexistent_home/` directory (a test
artefact) and an untracked `linuxone/RUN_PROMPT.md`.

**Why it matters.** Small, but both sit in the directory a judge opens first.

**Fix.** Delete the directory; track the file — it is the instruction sheet for running on
the VM and belongs in git.

**Effort.** Minutes. **Done when** `git status` shows neither.

---

# Part B — fixable, but needs a run

## COMP-01 · Undecided: should scoring use 741 trees or 841? — **DONE 2026-09-26**
**What is wrong.** Training used early stopping, which chose iteration 740 — 741 trees.
`predict_raw` calls `inplace_predict`, which uses **all 841**. We found this because `shap`
explained 741 while scoring used 841. Explanations now match scoring, but *which of the two
is correct* was never decided.

**Why it matters.** The extra 100 trees are past the point where validation stopped
improving, so they may be mild overfitting. Every published metric was measured with all
841, so a change here moves every number — which is why it must be measured, not assumed.

**Fix.** Score the test partition with `iteration_range=(0, 741)` and with every tree, and
compare PR-AUC, F1 and recall at 1%. If the difference is inside the seed spread (±0.0025
F1), keep 841 and record it in an ADR. If truncation wins, retrain and restate. Either way,
make the choice explicit in `predict_raw` instead of inheriting a library default.

**Effort.** About 30 minutes; the feature cache exists. **Done when** an ADR says which and
why, and the code states it.

**Result.** **ADR-016 accepted**. The difference was 0.0002 F1 against a seed spread of 0.0025. It is within noise, so we keep 841 trees explicitly. The package now passes `ALL_TREES = (0, 0)` explicitly so explanation and scoring can never drift apart again.

## COMP-02 · The LI-Small check never finished — **RAN 2026-09-29, gate FAILED**
**What is wrong.** Extraction reached **8 part files of about 28** before the session ended.
G1 (the shipped model applied unchanged) and G2 (the recipe retrained) never ran. The gates
were pre-registered in `WINNING_PLAN.md` before any result existed.

**Why it matters.** Every v2 decision was taken while looking at the HI-Small test period —
about seven looks. LI-Small is 6,924,049 rows no decision has touched, at half the
laundering rate (0.0496% against 0.0891%). It is our answer to "you tuned on your test set".
It is **not** external validation: same generator, same ACH convention
([CORPUS_COMPARISON.md](CORPUS_COMPARISON.md)).

**Fix.** Restart the extraction — it cannot resume, because GFP's graph cannot be serialised
(ADR-009) — then run G1 and G2 as scripted. Start it when the Windows host has about 9 GB
free: the last attempt died because the host had 4.4 GB of 15.6 GB free and WSL could not
grow into it.

**Effort.** About 4 hours, mostly unattended.

**Result, on a 2M-row chronological prefix** (the full run was abandoned; see
`WINNING_PLAN.md`, 2026-09-29). **G1 FAILS:** recall @1% **13.3%** against the 50% bar and
HI-Small's 78.3%. The threshold does transfer (alert rate 1.34%), and ROC-AUC stays 0.904,
so the model still ranks above chance — but 45% of this corpus's test laundering is off
ACH, where the model is blind (LIM-01), and even ACH recall falls from 84.9% to 22%.
**G2 is invalid rather than failed:** early stopping fired at trees 1, 2 and 37, because the
prefix held 221 training positives against HI-Small's 2,299. **Still open:** whether a
retrain on the *full* LI-Small (~2,100 training positives) recovers performance — one
uncontended 3–5 hour run.

## COMP-03 · Gate P9: 10.99 GB against a 10 GB budget — **DONE 2026-09-28**
**What is wrong.** `run_validation` trains over the whole feature table in memory and peaks
at 10.99 GB. `PENDING.md` A5.

**Why it matters.** It is a failing gate, and it is why the pipeline cannot run on a 6 GB
machine — the same constraint that forces the VM notebook onto a 2-day window
([PROBLEMS_2_BLOCKED.md](PROBLEMS_2_BLOCKED.md), BLK-06).

**Fix.** **The code already exists.** `linuxone/01_prepare_and_baseline.ipynb` streams
features to HDF5 and trains through `xgb.QuantileDMatrix` over a `DataIter`, holding about
one byte per value instead of four and never materialising the matrix. Lift that into
`run_validation` behind a flag, then make it the default once it reproduces today's metrics.
Scoring is already bounded: `score.py` reads only the rows it scores.

**Effort.** About half a day plus a validation run.

**Result.** **9.71 GB, P9 PASS**, in a 21m47s run. The fix was smaller than the plan above
assumed: the training matrices were never the problem, because `XGBModel.fit` already builds
a `QuantileDMatrix`. The peak was the full-corpus graph-feature frame (~3.9 GB) held beside
the three matrices built from it (~4.2 GB), and no partition ever needs another's rows, so
`read_varying_chunks` gained a `rows` filter and `build_inputs` reads per partition. The
HDF5/`DataIter` rewrite was not needed and is still available if the 6 GB VM becomes the
target. The model is identical to four decimals (PR-AUC 0.5949, F1 0.6126, recall@1% 78.3%),
all correctness gates still pass, and the same change let `score.py` drop a duplicate
filtered read. Record: `runs/COMP3_p9_validation.log`, package `models/flowguard_P9_v1/`.

## COMP-04 · The project cannot be built from the provided package list
**What is wrong.** Eleven modules read or write parquet — `config.py`, `data/eth.py`,
`features/gfp.py`, `pipeline/ingest.py`, `score.py`, `run_validation.py`, `run_benchmark.py`,
`run_baseline.py`, `run_graph.py`, `run_ablation.py`, `run_transfer.py` — and the datathon's
list has neither `pyarrow` nor `fastparquet`. `PENDING.md` B3.

**Why it matters.** In that environment the project does not start, however good the model
is. `shap` is already gone (native TreeSHAP) and the pickles are already optional (FIX-06),
so parquet is the last hard blocker.

**Fix.** Put the I/O behind two functions in one module — `read_table` / `write_table` —
defaulting to parquet where it exists and falling back otherwise: CSV for row data, and
**HDF5 via `h5py`, which is on the list**, for float blocks. CSV alone would bloat 5M × 189
floats beyond use. The notebooks already prove the HDF5 route on this data.

**Effort.** About a day. **Done when** the suite passes in a Python 3.10 environment built
only from the provided list.

## COMP-05 · Four results predate the extractor fix
**What is wrong.** Typology hinting (P4), the unsupervised arm (P6), the cascade (ADR-014)
and adaptive features (ADR-011) were all measured before the GFP double-insertion fix
(ADR-015). `PENDING.md` A8. Two are also PS9 requirements, FR-06 and FR-07.

**Why it matters.** Their *directions* are probably still right, but every magnitude we
quote for them came from features computed wrongly. Everything else was corrected; these
are the remainder.

**Fix.** Re-run each against the corrected cache, in this order: typology hinting (FR-06),
unsupervised arm (FR-07), cascade, adaptive features. Keep each original ADR and append the
re-measured figure, as ADR-012 already does.

**Effort.** About 2 hours each, independent. **Done when** no ADR quotes a pre-fix number
without its corrected value beside it.

## COMP-06 · Two F1 points behind the published benchmark
**What is wrong.** Our artifact-free, no-lookahead F1 is **0.614** against the paper's
**63.2**, which uses both the payment-rail artifact and within-batch lookahead.
`PENDING.md` A3.

**Why it matters.** It is the smallest open gap and the least damaging — we win the
comparison on honesty rather than on the number — but it is what a benchmark-minded judge
asks about.

**Fix.** Two candidates, cheapest first. Tune *artifact-free*: our search ran with
`payment_type` present, so its chosen parameters suit a feature the shipped model does not
use. Then widen the budget: the paper used successive halving, we used 24 random trials.
Pre-register the acceptance bar before running, as with every other step.

**Effort.** About 4 hours, uncertain payoff. **Done when** either F1 improves by more than
the seed spread, or the attempt is written up as a negative result — which counts as a
result here.

---

## Suggested order

1. **FIX-01** (commit) — everything else builds on it.
2. **COMP-01** (741 vs 841) — it can move every number, so settle it before rebuilding.
3. **COMP-03** (P9) — its rebuild also clears FIX-02 and FIX-03.
4. **FIX-04, FIX-05, FIX-07, FIX-08** — one hygiene pass.
5. **COMP-02** (LI-Small) — the strongest remaining answer to a methodological objection.
6. **COMP-04** (package list) — a day, and it decides whether the project runs in the
   judged environment at all.
7. **COMP-05**, then **COMP-06**, if time remains.
