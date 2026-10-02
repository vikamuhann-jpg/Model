# FlowGuard — Winning Plan and Work Log

**Started:** 2026-09-21
**Purpose:** close the gap between our headline number and the published benchmark, then
package the result for judges. Every step is logged below as it happens — including what
went wrong — so the final report can be written from this file alone.
**Rules:** gates are written *before* a run; the test set is touched once per candidate; a
change is kept only if it passes its gate; nothing is committed without asking.

---

## Where we start

| | Value | Source |
|---|---|---|
| Shipped model | `flowguard_A4_v1`, 167 features, no `payment_type` | `Project/flowguard/models/flowguard_A4_v1/` |
| Test F1 (best threshold) | **0.235** | A4 model card |
| PR-AUC | 0.140 ± 0.003 (3 seeds) | A4 model card |
| Published GFP+XGBoost, HI-Small | **F1 63.23 ± 0.17** (batch 128) · 64.77 ± 0.47 (batch 2048) | GFP paper (Blanuša et al.), Table 4 — *verified from `papers/research_paper (1).pdf`* |
| Published XGBoost, no graph features | F1 19.75 ± 0.89 | same table |

**Read that last row carefully:** our graph model (23.5) sits barely above the published
*no-graph* baseline (19.75). A judge will see this in seconds. It is the first thing to fix.

### Why our number differs — protocol, as verified in the paper

| | Published protocol | Ours (A4) |
|---|---|---|
| Split | 60 / 20 / 20 chronological | 70 / 15 / 15 chronological, HARD_CUT |
| Corpus | full HI-Small (0.102% illicit — matches untrimmed) | sparse tail trimmed (ADR-003) |
| GFP test batching | 128 or 2048 transactions per batch | 1 (ADR-004: batching lets an edge see later batch-mates) |
| GFP windows | library-style multi-day windows | all capped at 2 days (`windowed_params(2.0)`) |
| Tuning | successive halving; XGB `max_depth` 1–15, `lr` 10^-2.5–10^-1, `lambda` 10^-2–10^2, `scale_pos_weight` 1–10, `colsample` 0.5–1, rounds 10–1000 | none — defaults |
| Runs | mean of 5 | 3 seeds |

---

## Tracker

Status: ⬜ not started · 🔄 in progress · ✅ done (gate passed) · ❌ done (gate failed / rejected) · ⏸ blocked

| Step | Work | Gate (pre-registered) | Status | Result |
|---|---|---|---|---|
| **S0** | **Fix GFP double insertion** (found during S1) | Streamed features equal an insert-once reference (test) | ✅ | Every edge had been in the graph twice since E2. Fixed; A4 must be retrained |
| **S1** | Benchmark protocol: reproduce the paper's setup | Benchmark-mode F1 within 5 points of 63.2, **or** the gap explained by a measured cause | ✅ | Gap explained: class weight (S2), the ACH artifact (S4-pt), timestamp statistics (S4b). Final artifact-free, no-lookahead **F1 0.614** vs 63.2 |
| S1a | Ingest full HI-Small, no tail trim | Row count 5,078,345; positives 5,177 | ✅ | 5,078,345 rows, 5,177 positives (0.1019%) |
| S1b | GFP extraction, our default windows, batch 128; default XGB, 5 seeds | Completes; reported mean ± sd | ✅ | **F1 0.280 ± 0.008**, PR-AUC 0.243 ± 0.018, ROC-AUC 0.973, recall@1% 0.609. 2,675 tx/s |
| S1e | Same, with the **paper's GFP config** (6h scatter-gather, 1-day everything else, vertex stats on amount + timestamp); S2 params fixed | Completes; compared with S2 | ❌ no gain | F1 0.524 ± 0.021 vs S2 0.521 ± 0.004 — equal within noise, 5× the variance. Window config is not the remaining gap |
| **C0** | **Build only from the provided package list** (user constraint, 2026-09-21) | Full suite passes in a Python 3.10 env with the list's exact versions | 🔄 | 261/271 pass already; 10 fail on parquet (8) and a numpy-2 pickle (2); `shap` must go |
| S1c | Paper GFP config at **batch 1** (no lookahead), S2 params fixed, 5 seeds | Reported next to S1e (same config, batch 128) | ✅ | **F1 0.518 ± 0.027**, PR-AUC 0.504 ± 0.020 vs batch 128: 0.524 ± 0.021 / 0.516 ± 0.020 — **lookahead worth nothing measurable**. Extraction 532 tx/s |
| **S2** | Hyperparameter tuning (`models/tuning.py`, paper's ranges) | Tuned PR-AUC > untuned + 2σ on validation | ✅ | **F1 0.521 ± 0.004**, PR-AUC 0.513 ± 0.002 (from 0.280 / 0.243). Winner: `scale_pos_weight` **2** (was ~980), depth 8, lr 0.03 |
| **S3** | GFP window sweep (A4 2d / library / long) | Kept only if validation improves | ❌ | Ours vs the paper's windows equal within noise (S2 vs S1e); no further sweep |
| **S4b** | Drop GFP timestamp statistics (explainability) | Decided before the run; report val and test | ✅ | val 0.541 → 0.494, **test 0.570 → 0.608**, F1 0.614 ± 0.002 — a time proxy. Shipped |
| **S4** | ~10 causal account-behaviour features | Leakage test per feature; kept only if validation improves | ✅ | Artifact-free, batch 1: val PR-AUC 0.291 → **0.541 ± 0.004**; test **F1 0.544 ± 0.036** (oracle 0.601), **PR-AUC 0.570 ± 0.012**, recall@1% 71.6%. KEPT |
| S4-pt | Same model **without `payment_type`** (the ACH artifact), no behaviour | Reported | ✅ finding | F1 0.518 → **0.249**, PR-AUC 0.504 → 0.203: **half the benchmark-protocol score was the artifact** |
| **S5** | Throughput: minute micro-batch vs parallel extraction | P8 ≥ 1,000 tx/s; lookahead inflation < 1σ or rejected | 🔄 | Batch 128: 2,785 tx/s, lookahead inflation < 1σ (S1c vs S1e). Reconstruction: sound, +1%. Adoption not decided (PENDING A4) |
| **S6** | Stack isolation-forest score (out-of-fold) | PR-AUC not worse | ⬜ | |
| **S7** | Human-readable names for all GFP columns | Unique name per column (test) | ✅ | 215/215 named, unique, verified against real GFP output; bundles + contract carry `label`. `score.py` wiring waits for S10 |
| **S8** | Platt vs isotonic; variance gate P10; cold-start guard | ECE no worse; P10 bar set before run | ⬜ | |
| **S9** | Granite case narratives, grounded in the bundle | 100% of facts traceable (test) | ⏸ needs watsonx key or local-Granite approval | |
| **S10** | Executive summary, demo script, B1–B4 hygiene, ship v2 | Fresh clone reproduces headline in one command | 🔄 | v2 shipped (all correctness gates), samples regenerated with history, README/STATUS/PENDING rewritten, B2/B3 closed. Open: executive summary, demo notebook |
| **P2-eth** | Ethereum transfer re-run with corrected features | Graph Δ > 2σ; bootstrap CI | ✅ | Δ +0.0497 [0.0186, 0.1079] — holds; behaviour +0.0098 (> 2σ 0.0085) |
| **G1** | **v2 unchanged on LI-Small** (zero-shot: no refit, shipped threshold), test = last 20% | Recall@1% ≥ 0.50; alert rate at the shipped threshold within 0.5–2% (the threshold transfers) | ❌ | **Recall@1% 13.3% — FAIL.** Alert rate 1.34% — the threshold transfers. PR-AUC 0.0049 (14× base rate), ROC-AUC 0.904. On a 2M-row prefix, 143 test positives; 45% of them off ACH |
| **G2** | **v2 recipe retrained on LI-Small** (S4b config, S4b params, 5 seeds) | Test PR-AUC ≥ 0.30 (half HI's 0.608, for half the base rate); F1 sd ≤ 0.05 | ⚠️ invalid | PR-AUC 0.0035 ± 0.0017 — **not a verdict**: early stopping fired at trees 1, 2 and 37 of 3,000. The prefix gave 221 training positives against HI-Small's 2,299 |
| **G3** | G2 **without behaviour features** (PENDING A2) | Behaviour kept if G2 − G3 test PR-AUC > 2σ | ⏸ | Not run: G2 has no valid model to compare against |

---

## Log

Newest last. Each entry: what was done, what came out, **what went wrong**, what it changes.

### 2026-09-21 — Plan created
- Verified the published benchmark from the GFP paper in `papers/` (Table 4 and the
  "Data split" section). Earlier sessions quoted "about 0.6" from memory; the exact figure
  is 63.23 ± 0.17.
- **Found:** the published pipeline feeds test transactions to GFP in batches of 128/2048.
  Our ADR-004 measured that batching lets a transaction see later batch-mates. So part
  of the published number may come from within-batch lookahead. S1b vs S1c measures
  exactly how much. That comparison is itself a result worth presenting.
- **Found:** A4's `windowed_params(2.0)` cut the cycle and scatter-gather windows from
  3 days to 2 — the model was partly blind to round-tripping, the pattern PS9 names.
- **Found:** `models/tuning.py` is complete (rolling-origin, equal budget) but no runner
  calls it.

### 2026-09-21 — S1 started
- **S1a ✅** `ingest --min-density 0` into `flowguard_data/processed/benchmark/`: 5,078,345
  rows, 5,177 positives, 0.1019% — matches the paper's 0.102%, confirming it used the
  untrimmed corpus. A4's processed data is untouched.
- **New code:** `pipeline/run_benchmark.py` — the paper's protocol (untrimmed, 60/20/20,
  batched GFP, 5 seeds, minority F1 at a validation-chosen threshold, oracle F1 alongside).
  `--tune N` runs S2's search. `--batch-size 1` gives the S1c comparison.
- **Went wrong → fixed:** `GFPFeatures` crashed at `batch_size=128`
  (`could not broadcast (128,215) into (16,215)`). The chunk buffer assumed a batch never
  straddles a part file, which only held at batch size 1. Fixed in `__post_init__` by
  rounding `chunk_rows` to a multiple of `batch_size`; regression test
  `test_batches_never_straddle_part_files`.
- **Went wrong → fixed:** chunked `run_streaming` always re-assembled all 215 columns at
  the end — the step that has OOM'd WSL before. Added `assemble=False`; the runner reads
  only varying columns.
- **Found (likely big):** the paper tunes `scale_pos_weight` over **1–10**; ours is
  negatives/positives ≈ **980**. Such heavy positive weighting inflates false positives,
  which is exactly what F1 punishes. `XGBModel` now lets an explicit `scale_pos_weight`
  override the automatic ratio (no existing caller passes one, so A4 is unaffected); S2
  searches {1, 2, 5, 10, 30, 100}.
- **Went wrong — the big one (S0): every GFP feature since E2 was computed on a graph
  holding each edge twice.** The Snap ML docs say `transform()` *inserts* its batch and
  then computes features. Our extractor treated it as read-only and followed it with
  `partial_fit()` on the same batch. Proof on a 4-edge fan-in: the probe edge's target
  in-degree read **7** instead of **4**, amount sum 700 instead of 400, and a histogram
  count moved bins. Not leakage (train and test were equally distorted), but it corrupts
  the very signal GFP exists to give — a strong candidate for much of the gap to the paper.
  - Fixed in `run_streaming`: `transform` alone inserts; self-transfers are never sent to
    GFP and get NaN graph features (XGBoost routes NaN natively).
  - Test `test_each_edge_enters_the_graph_once` replaces
    `test_transaction_does_not_inflate_its_own_features`, whose premise (transform is
    read-only) was false; it only passed because double insertion inflates even more.
  - The first S1b run (batch 128) was extracting with the bug; stopped at ~70% and
    relaunched into a new cache (`gfp_b128v2`). The old parts in `gfp_b128` are invalid.
- **Consequence — ADR-008 was wrong.** Its "GFP retains state beyond the windowed edges"
  was our double insertion: a rebuild replays each edge once, the continuous graph held
  each edge twice. With the fix, the four strict-xfail reconstruction tests pass
  (feature-identical at every cadence); markers removed. Periodic reconstruction —
  which bounds the vertex set, the cause of the throughput decay — is back on the table
  for S5. The `rebuild_every` "UNSOUND" warning is left in place until S5 measures it
  at scale.
- **Consequence — the shipped A4 package is now stale.** It was trained on double-inserted
  features; `score.py` now extracts corrected ones, so A4's scores would be computed on
  inputs it never saw. A4 must be retrained (S10 ships v2) before `sample_outputs/` is
  regenerated. Until then, do not publish new A4 scores.
- ADR-004 (batching leaks within a batch) is unaffected — it is a property of `transform`
  inserting the whole batch before computing.
- **S7 ✅ (done while S1b extracts).** `features/gfp.py: feature_labels(params)` names all
  215 GFP columns from the documented layout: 7 histograms (fan-in, fan-out, degree-in,
  degree-out, scatter-gather, temporal cycle: 29 bins each; length-constrained cycle: 9)
  = 183, then 4 vertex blocks (sender out/in, receiver out/in) × 8 stats = 32. Default
  bins read from `get_params()`. `test_gfp_labels.py` checks count = real output width
  under both parameter sets, uniqueness, and **meaning**: on a 4-edge fan-in the last edge
  reads "fan-in size 4" = 1, receiver incoming count = 4, total = 400. Passed first time.
  - `Reason.label` added; `build_bundle(gfp_params=...)` names graph reasons and clears
    `opaque`. Contract: optional `label` (old bundles stay valid); UI rule 7 rewritten.
  - This retracts an earlier claim of ours: the reasons were never *inherently* opaque —
    we had not read the library's docs closely enough.
  - Not yet wired into `score.py`: it hardcodes a 2-day window; S10's v2 package will
    carry its GFP params and pass them to both extraction and labelling.
- **S4 built (gate pending).** `features/behaviour.py`: ten history features GFP lacks —
  sender velocity (1h/24h count, 24h amount), sender's 24h inflow count, **pass-through**
  (this amount ÷ what the sender received in 24h), receiver in/out 24h counts, seconds
  since the sender's last send, prior transfers on this pair, prior transfers in the
  reverse direction. Every one counts only **strictly earlier timestamps** (same-minute
  rows are mutually blind). Vectorised with sorted keys + `searchsorted`: 17 s on 5.08M
  rows. `tests/leakage/test_behaviour_causality.py`: hand-computed values, future-row
  invariance, same-minute blindness, label rejection — 4/4 pass.
  - Medians, laundering vs normal: pass-through **0.67 vs 0.19**; prior pair transfers
    **0 vs 5**; seconds since last send **61,320 vs 1,080**. Laundering here goes to a
    new counterparty from a dormant account and moves most of what just arrived.
  - Caution for the write-up: strong separation on a synthetic corpus can be a
    generator trait (as `payment_type` was, ADR-007). If S4 is kept, check it on the
    LI-Small corpus and the ETH slice before claiming it as behaviour.
  - Wired as `run_benchmark --behaviour`.
### 2026-09-21 — S1b result and what it rules out
- **S1b ✅** (paper protocol, corrected extractor, batch 128, default XGBoost, 5 seeds):
  **F1 0.280 ± 0.008** (oracle 0.300), PR-AUC 0.243 ± 0.018, ROC-AUC 0.973, recall@1%
  0.609. Beats A4 (0.235 / 0.140) but is nowhere near the paper's 63.2. So **protocol
  alone does not explain the gap.** Extraction 1,899 s = 2,675 tx/s at batch 128.
- **Found:** the model is under-trained — best iteration 272–299 of a 300-round cap on
  every seed. S2 allows 1,000 rounds with early stopping.
- **Found:** XGBoost runs on the GPU inside WSL (~55 s per fit).
- **Ruled out as the main cause — within-batch lookahead:** the paper's batch 128 and
  2048 differ by only 1.5 F1 points, so the lookahead batching adds cannot be worth 35.
- **Found — the paper's GFP configuration differs from ours** ("Graph Feature
  Preprocessor setup", verified in the PDF): scatter-gather over **6 h**, every other
  pattern and the vertex statistics over **1 day**, vertex statistics on **Amount and
  Timestamp**. Ours: scatter-gather 2 d, cycles 3 d, vertex stats 2 d on amount only,
  graph 10 d. Their Table 5 is the tell: **fan-in/fan-out features alone give XGBoost
  56.9 F1**; our full set gives 28. That points at feature computation, not the model.
  Added `run_benchmark --paper-params` (S1e). `feature_labels` now names timestamp stats.
- **Went wrong → fixed:** the S2 launch reused S1b's output names, so S1b's *log* was
  overwritten (the JSON survived and is filed as `runs/S1b_default_b128.json`;
  its extraction stats live in the JSON). New `run.sh` writes `runs/<name>.{json,log}`
  and refuses to overwrite.
### 2026-09-21 — S2 result: tuning nearly doubles F1
- **S2 ✅** 24-trial rolling-origin random search on the training partition only
  (2 folds, ≤1,000 rounds, early stopping 50; 2,082 s on GPU), then 5 seeds on the S1b
  features: **F1 0.5205 ± 0.0042** (oracle 0.527), **PR-AUC 0.5134 ± 0.0024**.
  From S1b's 0.280 / 0.243 — PR-AUC more than doubled.
- **Winning params:** `scale_pos_weight` **2**, `max_depth` 8, `learning_rate` 0.03,
  `subsample` 0.8, `colsample_bytree` 0.75, `min_child_weight` 1, `reg_lambda` 0.01.
  Top-2 trials both use weight 2–5; the automatic negatives/positives ratio (~980) that
  every model since E1 used was the single largest drag on the metrics.
- **Still under-trained:** best iterations 807–999 of 1,000. Next: raise the cap.
- **Gate note (honest):** the gate said "on validation"; the runner reports test. The
  params were chosen on training folds only, test was touched once, and the effect is
  ~15σ of S1b's spread — the gate passes by any reading, but future runs will also log
  validation PR-AUC.
- Gap to the paper now **63.2 − 52.1 = 11 points**, down from 35. S1e (the paper's GFP
  config) is next, run with S2's params fixed so it measures features, not tuning.
### 2026-09-22 — S1e, and the package constraint (C0)
- **S1e ❌** Paper GFP config (6 h scatter-gather, 1 day for everything else incl.
  vertex stats, vertex stats on amount + timestamp) with S2's model held fixed:
  **F1 0.524 ± 0.021**, PR-AUC 0.516 ± 0.020 — indistinguishable from S2
  (0.521 ± 0.004) and far noisier. 2,785 tx/s. The window configuration is **not** the
  remaining 11 points. Keep our config (lower variance). Remaining suspects: model
  capacity (S2 hit the 1,000-round cap), tuning budget (paper: successive halving over a
  wider range), and S4 features.
- **New constraint from the user:** the project must be built **only from the package
  list they supplied** (snapml 1.16.0, xgboost 2.0.3, numpy 1.24.4, pandas 2.1.4,
  scikit-learn 1.4.0, scipy 1.12.0, PyYAML 5.4.1, …; Python not listed, but tensorflow
  2.9.3 implies ≤3.10). Saved as a standing rule.
- **Measured, not guessed:** built `/root/ibmenv` in WSL — Python 3.10.21 + the exact
  versions (PyYAML 5.4.1 would not build from source on modern setuptools; the target
  environment has it prebuilt, and we only call `safe_load`). Results:
  - every `flowguard` module imports on Python 3.10;
  - **snapml 1.16.0 and 1.17.2 produce bit-identical GFP output** (2,999 × 220, max
    diff 0.0) — the feature pipeline transfers as-is;
  - xgboost 2.0.3 loads A4's `model.json` (300 trees);
  - **261 of 271 tests pass; 10 fail**, for exactly two reasons:
    1. **no parquet engine** (pyarrow / fastparquet are not in the list) — 8 tests;
       parquet is used at ~35 sites (processed data, GFP part files, caches);
    2. **A4's `calibrator.pkl` was pickled under numpy 2** → `No module named
       'numpy._core'` under numpy 1.24 — 2 tests (live scoring);
  - and **`shap` is not in the list** (used by `local_contributions` / `explain`).
- **C0 plan** (all with listed packages only):
  1. Storage: GFP part files → `.npy` (+ row-id `.npy`), read column-selectively via
     `np.load(mmap_mode="r")`; data frames → pandas pickle. One conversion of existing
     processed data.
  2. SHAP → `booster.predict(DMatrix, pred_contribs=True)` — XGBoost's own TreeSHAP,
     same algorithm, no dependency.
  3. Model package → no pickles: calibrator as JSON (isotonic breakpoints, applied with
     `np.interp`), encoder as JSON; booster already JSON.
  4. `pyproject.toml`: `requires-python >=3.10`, dependencies pinned to the list, drop
     pyarrow / shap / networkx (unused).
  5. Gate: the **whole suite passes in `/root/ibmenv`**, and v2 is trained and packaged
     there, not in the dev venv.
- **Open question for the user:** the list includes `thinc_bigendian_ops`, which hints at
  an IBM Z (s390x) machine. If so there is no GPU: S2's 55 s GPU fits become several
  minutes each on CPU, so tuning stays on this machine and only the chosen params ship.
### 2026-09-22 — P0 (credibility), started after the user approved the commit
- **Committed** the session's work as `d59a125` on a new branch `winning-plan`
  (`main` untouched).
- **ADR-015** written: the double-insertion defect, how it was found, why no test caught
  it, the fix, and a table of every affected result with where it is quoted.
  **ADR-008** marked superseded (its conclusion was the same bug). One-line ADR-015
  banners added to ADR-006, -011, -012, -013, -014, ERROR_ANALYSIS_A2 and STATUS;
  correction notes in TRACK_P_PLAN and OPEN_IT  EMS.
- **"No feature names" removed:** README blocker row deleted; PENDING FR-09 → built;
  TRACK_P_PLAN corrected; `Project/flowguard/README.md` no longer teaches the wrong
  insertion convention.
- **Docs consolidated:** six superseded planning documents moved (`git mv`) to
  `docs/archive/planning/`; `docs/README.md` rewritten as a short reading order plus an
  ADR table with each record's current status.
- **Found → fixed:** `experiments/results.csv` — the registry behind every number — was
  never in git (the nested `.gitignore`'s `*.csv` caught it) although the README says it
  is tracked. Now un-ignored.
- **Found → fixed (would have shipped a false gate):** `run_validation`'s P8 fell back to
  parsing a fixed old extraction log when a run had no throughput figure — the smoke test
  reported A4's stale 487 tx/s for a different cache. With a graph record it now uses the
  extracting run's measurement or reports NOT_RUN; `--extraction-from` names that run.
- **v2 plumbing:** `run_validation --from-run/--extraction-from/--behaviour/--n-estimators`
  (tuned params and the 60/20/20 split reach every gate through one model factory);
  packages carry `graph.json` (GFP params, batch size, insertion convention, behaviour);
  `score.py` rebuilds features from it and passes the params to evidence bundles, so
  reasons are labelled. The model card's training table is now computed from the data —
  it had A4's corpus and split typed in. Smoke-tested end to end on the 300k sample.
- **Also found:** every benchmark run so far kept `payment_type` (the ACH artifact,
  ADR-007) — correct for comparing with the paper, which uses it, but the shipped model
  must not. The S4 comparisons and v2 are artifact-free.
- **Compute:** S1c (paper params, batch 1) running — 12.7k tx/s at 10%, 1.1k cumulative
  at 54%, decaying as GFP accumulates vertices. Queued behind it: three artifact-free
  training runs (S2 settings; 3,000-round cap; cap + behaviour), then the P2 speed test
  (2M rows, continuous vs rebuild every 100k, with a full-scale identity check), then —
  after v2 — the Ethereum re-run on the full 2.02M-row slice.
### 2026-09-22 — S1c, S4: the deployment-honest numbers
- **S1c ✅** paper GFP config at **batch 1** (strictly no lookahead), S2 params:
  **F1 0.518 ± 0.027, PR-AUC 0.504 ± 0.020** — vs 0.524 / 0.516 at batch 128 (S1e).
  Equal within noise: the paper's within-batch lookahead is worth nothing measurable
  here. Our strict protocol loses nothing against the published one.
- **Throughput, corrected extractor, batch 1, full corpus: 532 tx/s** (9,539 s) — decays
  from 16.6k tx/s at 5% as GFP accumulates vertices. P8 (≥ 1,000) still fails at batch 1
  without reconstruction; the P2 speed test measures reconstruction.
- **S4-pt — the artifact, measured with corrected features:** the same model **without
  `payment_type`** falls from F1 0.518 to **0.249** and PR-AUC 0.504 to **0.203**. About
  half the benchmark-protocol score is the ACH artifact (ADR-007). The paper's 63.2 uses
  payment type as a basic feature too, so it carries the same effect. Every earlier
  benchmark row in this file includes `payment_type`, as the paper does.
- **Round cap:** raising 1,000 → 3,000 changed four of five seeds not at all — without
  the artifact, early stopping ends at ~150 rounds. Not a lever on its own.
- **S4 ✅ behaviour features, artifact-free, batch 1:** val PR-AUC **0.291 → 0.541 ±
  0.004**; test **F1 0.544 ± 0.036** (oracle 0.601 ± 0.010), **PR-AUC 0.570 ± 0.012**,
  ROC-AUC 0.967, recall@1% **71.6%**. Best iterations 589–793 (stable). Gate passes at
  ~10× the 2σ bar. This model uses **neither the artifact nor lookahead** and sits within
  ~6 F1 points of the paper's figure, which uses both.
  - Why they help: they are standard AML red flags GFP does not compute — a first-time
    counterparty (`bh_pair_n_prior`), a dormant account suddenly sending
    (`bh_src_secs_since_out`), and funds passed straight through (`bh_src_passthrough_24h`).
  - Caution kept: a synthetic generator can exaggerate exactly these traits. Claim them
    as behaviour only after checking another corpus; say so in the write-up.
- **Decision:** v2 = paper GFP config, batch 1, artifact-free, behaviour features, S2
  params, ≤ 3,000 rounds. Packaged through `run_validation` so every gate runs on it.

### 2026-09-22 — P2 speed: reconstruction is sound, and does not help
- `scripts/measure/p2_speed.py`, first 2M rows, batch 1, paper params:
  continuous **1,488 tx/s**; rebuild every 100k (19 rebuilds, 54 s spent rebuilding)
  **1,507 tx/s** (+1%). Rebuilt and continuous features **identical over all 2M rows**
  (max |diff| 0.0) — ADR-015 confirmed at full scale, not only on fixtures.
- So ADR-008's *reason* was wrong but its *outcome* stands: reconstruction buys nothing,
  because the decay is not accumulated vertices (a rebuild would have cleared those) — it
  is the live graph inside the window. Not adopted.
- **Throughput, honestly:** batch 1 over the full corpus 532 tx/s (P8 fails); batch 128
  2,785 tx/s (P8 passes) — and S1c vs S1e showed batch 128 costs **no measurable
  accuracy**. On HI-Small 128 transactions ≈ 23 s of traffic (338 tx/min), so
  micro-batching is a measured trade: ≤ ~23 s alert latency for 5× throughput. Recorded
  as a deployment option; v2 is built and gated at batch 1.
### 2026-09-22 — v2 packaged; what broke on the way
- **v2 ✅** `run_validation --model-id V2` (S4 config, 3,000-round cap): PR-AUC **0.559**
  (5 seeds sd 0.014), best F1 0.599, ROC-AUC 0.967, recall@1% **72.2%**, precision@0.1%
  **82.2%**. **All 8 correctness gates pass** (shuffled-label PR-AUC 0.0017 = base rate).
  P4 passes for the first time (72.2% ≥ 45%); P2, P5, P6, P7 pass; P8 (532 tx/s) and P9
  (10.88 GB, a live kernel reading) fail. Package `models/flowguard_V2_v1/` (8.7 MB) with
  `graph.json`; A4's git exception moved to V2.
- **Found — the headline is tail-lifted:** P7's windows show the test period's last ~60k
  rows are 20–68% laundering (the generator's sparse tail, ADR-003). On the dense first
  window (952k rows) PR-AUC is **0.382**. Both figures now reported; the paper's protocol
  includes the same tail.
- **Found — timestamp statistics:** the top-SHAP graph columns are *average timestamp* of an
  account's 24h transfers. Test values lie beyond the training range, so trees cannot split
  on absolute time within test; SHAP is offset + missingness. With vs without these stats
  scored the same (S2 vs S1e). Reported as a caveat (PENDING A8).
- **Went wrong → fixed: cold-start samples alerted on 30.5%.** The first v2 sample run scored a
  2.5-hour window with no history: every counterparty looked new, every sender dormant —
  exactly the learned red flags. `score.run(emit_from, emit_until)` / `--emit-from` now use
  earlier rows as history (features + tracing) and score only the window; `run.json` records
  `history_transactions`. Samples are regenerated over the full corpus with v2's own graph
  cache. Test `test_history_rows_build_features_but_are_not_scored`.
- **Also fixed:** the model card's training table was typed in for A4 (now computed from the
  data); `make_sample_outputs.py` clears stale `cases/` so A4 and v2 bundles cannot mix;
  `configs/experiment.yaml` paired the trimmed corpus's rows with the full corpus's account
  count (515,088 vs the correct 515,078 — the tail holds ten accounts; PENDING B3 closed);
  STATUS.md's first line began `ts# ` — fixed.
- **Tracked now:** `experiments/results.csv` and `experiments/runs/` (every benchmark JSON
  and log, indexed).
- **Docs:** README rewritten (470 → ~200 lines, current numbers, two-protocol table, the
  artifact, the tail, the timestamp caveat, hosted reports marked as superseded); STATUS
  gains a current section on top, pre-fix content kept below a "Historical" divider;
  PENDING rewritten; package README, contracts README, samples README updated.
- **ETH (P2):** corrected extraction starts at 1,358 tx/s and decays like the buggy run — on a
  real, degree-skewed network the cost is still super-linear (ADR-013's conclusion holds).
  Evaluating on the same 1.25M-row prefix as the original Tier C, with a third arm (T3 =
  graph + behaviour) — the first test of the behaviour features off the synthetic generator.
  `tier_c_bootstrap.py` now takes the parts folder (it was hardcoded to the defective cache).
### 2026-09-22 — P2 Ethereum result; timestamp statistics dropped (S4b)
- **ETH ✅ (corrected extractor, same 1.25M-row prefix as Tier C, 20 scored positives):**
  T1 row-local 0.0031 · T2 + graph **0.0533 ± 0.0015** · T3 + behaviour **0.0631 ± 0.0070**.
  Graph Δ **+0.0503** (pre-fix: +0.0504). Paired bootstrap Δ **+0.0497, 95% CI
  [0.0186, 0.1079]**, 2,000/2,000 resamples favour graph (pre-fix: [0.0187, 0.1231]).
  **The real-network claim survives the fix unchanged.** Behaviour Δ +0.0098 vs 2σ 0.0085:
  just above the bar on 20 positives — the first sign, not proof, that the behaviour
  features are not only a generator trait. Extraction: 135 tx/s cumulative at 1.25M rows
  (pre-fix 139) — degree skew, not the defect, drove that cost (ADR-013 holds).
- **Samples, first history-aware run:** 945 alerts / 50,263 (1.9%) vs 30.5% cold.
  **Went wrong → fixed:** the window was cut mid-minute, so 50,263 rows were scored against
  a 50,000-row sample file; the window is now whole minutes.
- **Found in the samples:** all 60 graph reasons were labelled — and the top ones read
  "sender's outgoing transfers (24h window): average timestamp". Unusable for an
  investigator, and the calendar-proxy concern made concrete. Decided **before** measuring,
  on explainability grounds (expecting no lift, per S2 vs S1e): drop the timestamp
  statistics (8 varying columns). `gfp.timestamp_stat_columns`, `--drop-timestamp-stats`
  in both runners, recorded in `graph.json`.
- **S4b result — validation and test disagree, which is itself the finding:**

  | | val PR-AUC | test PR-AUC | test F1 | recall@1% | F1 sd |
  |---|---:|---:|---:|---:|---:|
  | S4 with timestamp stats | **0.541** | 0.570 | 0.544 | 71.6% | 0.036 |
  | S4b without | 0.494 | **0.608** | **0.614** | **78.5%** | **0.002** |

  The timestamp statistics encode position in time: they help on validation (adjacent to
  training time, where values are still splittable) and hurt on test (further out). The
  F1 instability at the transferred threshold disappears without them. The drop was
  decided on explainability before the run, so this is not selecting on test; the
  validation fall is reported, not hidden. **Artifact-free, no-lookahead F1 0.614 — within
  2 points of the paper's 63.2, which uses both.**
- Labels added for all behaviour and row-local features (`LABELS` in `behaviour.py` and
  `transaction.py`); test `test_every_feature_of_the_shipped_model_has_a_plain_language_label`.
- v2 rebuilt through `run_validation` without timestamp statistics (the first v2 build's log
  kept as `V2a_with_ts_validation.log`).
- **Environment notes:** MSYS path conversion mangles `/mnt/...` arguments to `wsl` —
  run with `MSYS_NO_PATHCONV=1`. WSL has 12 cores, 11 GB RAM, so extractions run one
  at a time.

### 2026-09-22 — G: validation on LI-Small (gates set before any run)
- **Why:** every v2 decision was taken looking at the HI-Small test period (about seven
  looks). LI-Small is 6.9M rows no decision has touched, with half the laundering rate
  (0.05% vs 0.10%).
- **What it is not:** external validation. It shares the generator and its ACH convention
  ([CORPUS_COMPARISON.md](docs/CORPUS_COMPARISON.md)); simulator independence stays with the
  Ethereum result (P2-eth). Reported as a **fresh-data and base-rate test**, never more.
- **Protocol:** untrimmed ingest (`--min-density 0`), paper GFP config at batch 1 (the S1c
  path), 60/20/20 chronological split. G1 loads `models/flowguard_V2_v1` as scoring does
  (`scripts/measure/transfer_zero_shot.py`); G2 is `run_benchmark --variant LI-Small` with
  S4b's flags and parameters. `run_benchmark` gained `--variant` (default HI-Small).
- **Gates** as in the tracker, fixed here before extraction started.


### 2026-09-26 — LinuxONE handoff: the items that were ours
Shivraj ran the deployment notebooks on the datathon VM (2 vCPU, 6 GB, s390x) and returned
`HANDOFF_VIKA_2026-09-24.md`. His §1 edits were made to his copies; the same defects were
in ours, so they are fixed here at the source.

- **R3 — the nameless typology bar.** `per_group_recall` turned unlabelled rows into `""`
  and then kept `""` as a group, because `isinstance("", str)` is true. It reached every
  per-typology chart and gate P5. The existing test missed it: its unlabelled rows were all
  *negative*, so the group was empty and skipped. Unlabelled **positives** are the normal
  case — 38% on HI-Small, 71% on LI-Small. Fixed, plus a test that fails on the old code.
- **R8 — the package is now readable without unpickling.** `calibrator.json`
  (`isotonic-piecewise`: the knots, read back with `np.interp`) and
  `encoders/categorical.json` (the ordinal vocabulary). Both are written by
  `run_validation` and preferred by `score.py`; the pickles stay for older packages.
  Agreement with the pickled calibrator: **6.0e-8** over 20,100 points (their `np.interp`
  reimplementation measured 4.6e-6).
- **Found while doing it — explanations did not describe the scored model.**
  `shap.TreeExplainer` truncates an early-stopped booster at `best_iteration`; our scoring
  path uses every tree. On v2 that is **741 trees explained against 841 scored**, so every
  evidence bundle explained a model that never produced its score. `shap` is also absent
  from the datathon package list. Both are fixed at once by XGBoost's own
  `pred_contribs=True` — the same TreeSHAP implementation `shap` calls — pinned by a test
  asserting contributions + bias == the scored margin.
- **R8 — `top_features` in `scores.csv`:** the three named features that pushed each alert
  up, as `label (+0.123)`, computed for alerts only. Contract updated.
- **R8 — rank ties were already correct.** `rank` orders by `score` then `raw_score` in the
  shipped file; the request came from the older D37 delivery. It matters more than it
  sounds: isotonic calibration saturates, so **49,611 of 50,263 rows share a score with
  another row** and the tie-break decides nearly every rank.
- **R8 — labels shipped:** `sample_outputs/labels.csv` and `window_metrics.json`, so the
  window can be recomputed rather than trusted.
- **Scoring no longer materialises features for rows it will not score.** A 50k window over
  a 5M-row corpus read 5M x 192 float32 (3.8 GB) to score 39 MB of it; history rows shape
  the features but their engineered columns are never needed. `graph_features(rows=...)`
  reads one part file at a time; the few rows a case trace reaches are fetched on demand.
  This is also what makes the path viable on a 6 GB VM.
- **R4/R5 in the notebooks:** the epoch cap now says whether it stopped on patience or hit
  the cap (30 was a budget, not convergence; raised to 150/10), and notebook 02 reports a
  P5 failure by name instead of averaging it away. Notebook 01 had the same
  delete-then-use crash Shivraj found in his copy — cell 21 frees the E1 frames, cells 26,
  27 and 37 still read them — fixed by keeping the score vector and the feature count.
- **Corpus is now a setting:** `FLOWGUARD_VARIANT`, with outputs under
  `~/flowguard_outputs/<VARIANT>/` so a second dataset cannot overwrite the first.
- **Keras was never the problem.** Our STATUS said TF 2.9.3 cannot run on the image and
  "nothing installable fixes it". Every observation was right; the inference was wrong. The
  image carries two protobufs, and importing the `3.13.0` beside TensorFlow rather than the
  `7.35.1` in `~/.local` makes Keras work with nothing installed. Corrected in both
  `linuxone/` documents, with what the reasoning got wrong.

### 2026-09-28 — Sessions 2 and 3: gate P9 passes, and P1 was grading the wrong model
- **P9: 10.99 GB → 9.71 GB, PASS** (`runs/COMP3_p9_validation.log`, 21m47s). The peak was
  never the training matrices — `XGBModel.fit` already builds a `QuantileDMatrix`, about a
  byte per value. It was the **full-corpus graph-feature frame (~3.9 GB) held beside the
  three matrices built from it (~4.2 GB)**, and no partition ever needs another partition's
  rows. `read_varying_chunks` gained a `rows` filter; `build_inputs` reads per partition.
  The planned HDF5/`DataIter` rewrite was not needed. **The model is unchanged to four
  decimals:** PR-AUC 0.5949, best F1 0.6126, recall@1% 78.3%, all correctness gates pass.
  The same filter let `score.py` drop the duplicate read added a session earlier.
- **P1 was comparing each build against its own predecessor.** The gate reads
  `registry.load(model_id)`, but this run's record is written at the *end* of validation,
  so the V2 report quoted **0.5587** — the superseded 214-feature build — for a model
  scoring 0.5949. Fixed to use the metrics just measured; the registry is still read for
  the other side of the comparison. The verdict never changed (+0.52 over E1); the number
  did. This is what `STATUS.md` had recorded as a stale quote, and rebuilding would not
  have cleared it.
- **A partial GFP cache was being reused as if complete** (found while restarting LI-Small):
  8 part files of ~28 covering 2,000,000 of 6,924,049 rows. `read_varying_chunks` reindexes
  to the full frame, so the missing 70% would have arrived as NaN features and trained
  silently. `gfp_block` now counts rows from parquet metadata and re-extracts. Test:
  `test_a_half_written_cache_is_not_reused_as_if_it_were_complete`.
- **ADR-016 — score with every tree, explicitly.** Early stopping chose 741 of 841 trees
  and nothing decided which to score with; `shap` used 741, `inplace_predict` used 841.
  Measured on the test partition: PR-AUC 0.6034 vs 0.6036, F1 0.6142 vs 0.6140 — inside the
  0.0025 seed spread. Keep all trees, pass the range from one constant in both paths.
- **Throughput, honestly:** the LI-Small extraction reads 4,937 tx/s at 18% and 412 tx/s by
  the time the graph fills. Quoting the early figure is the same mistake ADR-006 records and
  `_throughput_from_log` exists to avoid; the run is ~4 hours, not the 19 minutes the early
  rate implied.

### 2026-09-29 — G: the shipped model on fresh data fails its pre-registered gate
**Setup.** The full LI-Small extraction was abandoned (two runs had been writing one cache
at once — see below), and at the user's direction the check ran on a **chronological
2M-row prefix**: 2,000,493 rows, 468 positives, 1.5 days, 645k accounts. It is the sparsest
stretch of LI-Small (base rate 0.023%, against 0.050% for the whole corpus and 0.089% for
HI-Small). Records: `runs/G1_zero_shot_LI-Small-2M.json`, `runs/G2_LI2M_retrain.json`.

**G1 — the shipped v2, unchanged. FAIL.**

| | HI-Small (shipped) | LI-Small prefix |
|---|---:|---:|
| Recall @1% | 78.3% | **13.3%** (19 of 143) |
| PR-AUC | 0.595 | 0.0049 (14× base rate) |
| ROC-AUC | 0.982 | 0.904 |
| Alert rate at shipped threshold | 1.0% | **1.34% — transfers** |
| Test positives on ACH | 92% | **55%** |
| Recall @1% on ACH | 84.9% | 22% |
| Recall @1% off ACH | 0–4% | 0–7% |

The threshold transfers and the model still ranks well above chance, but recall collapses.
The largest visible cause is the rail mix: **45% of this corpus's test laundering is off
ACH**, where the model was already known to be blind (LIM-01), against 8% on HI-Small. That
is not the whole story — ACH recall falls from 84.9% to 22% as well — so the model's
HI-Small strength does not carry over even on the rail it was built for.

**G2 — the recipe retrained on the prefix. Invalid, not failed.** PR-AUC 0.0035 ± 0.0017,
but early stopping fired at **trees 1, 2 and 37** of 3,000: validation PR-AUC never rose
above ~0.001. The prefix holds **221 training positives against HI-Small's 2,299**, and the
parameters were tuned for the latter. This measures an under-powered training set, not the
method. **Went wrong:** the prefix was chosen after checking only *test* positives (143);
training positives are what a retrain needs, and nobody checked them before the run.

**G3** was not run — without a valid G2 there is nothing to compare it against.

**What this settles.** The pre-registered claim — that v2's HI-Small result holds on data
no decision touched — **does not hold** on this corpus. Stated plainly, since this is
exactly the result pre-registration exists to catch: the headline is specific to HI-Small's
rail mix and density. LIM-01 is not a HI-Small quirk; on a corpus where laundering is less
concentrated on ACH, it is the dominant failure.

**What it does not settle.** Whether retraining on LI-Small recovers performance. That
needs the full corpus (~2,100 training positives) — a 3–5 hour uncontended extraction.

**Why the full run was abandoned.** Two extraction processes wrote the same cache directory:
the previous session's job survived its "stopped" notification, and a new one started
beside it. They split 12 cores, pushed 2.5 GB into swap, and throughput fell from 2,022 to
**60 tx/s** — a 24-hour floor for the remainder. The new partial-cache check then deleted
the directory while the other process still wrote to it, so the parts interleaved two runs.
Both killed, the cache deleted. `prefix_run.sh` now refuses to start while another
extraction is alive. A single uncontended run did the 2M prefix at **2,102 tx/s**.

### 2026-09-29 — Option A: the claim now says what the model detects
Decision taken from `docs/DECISION_REPORT_LI_TRANSFER.md`: keep the method, narrow the claim.
- **The split behind the headline** (`runs/G1_diagnosis_*.json`): on HI-Small the model
  catches **95.3%** of structured laundering and **27.9%** of unstructured; 75% of that
  corpus is structured. On the LI-Small prefix, 88% is unstructured, and the same model
  scores 13.3% — about two-thirds of the drop is composition, a third a genuine per-group
  fall. Unstructured laundering off ACH is 1–3% on both corpora.
- **README** now opens with what the model detects — laundering that leaves a graph shape —
  and carries the split and the fresh-data result in its status table.
- **The model card called the weak half a coverage caveat.** "Only ~62% of positives carry
  a typology label" was true and hid that those are the positives the model misses. The
  generator now measures the structured/unstructured split from the data (new
  `structure_recall_at_1pct` in `metrics.json`); the shipped V2 card is updated by hand from
  the diagnosis and says so. A test pins it.
- **LIM-08** added: laundering with no graph shape is largely missed, on every corpus.
- **Scoring could not score any corpus but its own** — found running the diagnosis. It read
  the graph columns that vary in the *new* cache; 25 of the model's columns are constant on
  LI-Small, so they vanished. `graph_features` now takes the package's own column list.
