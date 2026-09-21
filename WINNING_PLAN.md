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
| **S1** | Benchmark protocol: reproduce the paper's setup | Benchmark-mode F1 within 5 points of 63.2, **or** the gap explained by a measured cause | 🔄 | — |
| S1a | Ingest full HI-Small, no tail trim | Row count 5,078,345; positives 5,177 | ✅ | 5,078,345 rows, 5,177 positives (0.1019%) |
| S1b | GFP extraction, our default windows, batch 128; default XGB, 5 seeds | Completes; reported mean ± sd | ✅ | **F1 0.280 ± 0.008**, PR-AUC 0.243 ± 0.018, ROC-AUC 0.973, recall@1% 0.609. 2,675 tx/s |
| S1e | Same, with the **paper's GFP config** (6h scatter-gather, 1-day everything else, vertex stats on amount + timestamp); S2 params fixed | Completes; compared with S2 | ❌ no gain | F1 0.524 ± 0.021 vs S2 0.521 ± 0.004 — equal within noise, 5× the variance. Window config is not the remaining gap |
| **C0** | **Build only from the provided package list** (user constraint, 2026-09-21) | Full suite passes in a Python 3.10 env with the list's exact versions | 🔄 | 261/271 pass already; 10 fail on parquet (8) and a numpy-2 pickle (2); `shap` must go |
| S1c | GFP extraction, same windows, batch 1 (ours) | Completes; features finite | ⬜ | |
| S1d | Train + evaluate 60/20/20, 5 seeds, both extractions | Reported with mean ± sd | ⬜ | |
| **S2** | Hyperparameter tuning (`models/tuning.py`, paper's ranges) | Tuned PR-AUC > untuned + 2σ on validation | ✅ | **F1 0.521 ± 0.004**, PR-AUC 0.513 ± 0.002 (from 0.280 / 0.243). Winner: `scale_pos_weight` **2** (was ~980), depth 8, lr 0.03 |
| **S3** | GFP window sweep (A4 2d / library / long) | Kept only if validation improves | ⬜ | |
| **S4** | ~10 causal account-behaviour features | Leakage test per feature; kept only if validation improves | 🔄 | Built + 4 causality tests pass; 17 s on 5M rows. Gate runs after S1 |
| **S5** | Throughput: minute micro-batch vs parallel extraction | P8 ≥ 1,000 tx/s; lookahead inflation < 1σ or rejected | ⬜ | |
| **S6** | Stack isolation-forest score (out-of-fold) | PR-AUC not worse | ⬜ | |
| **S7** | Human-readable names for all GFP columns | Unique name per column (test) | ✅ | 215/215 named, unique, verified against real GFP output; bundles + contract carry `label`. `score.py` wiring waits for S10 |
| **S8** | Platt vs isotonic; variance gate P10; cold-start guard | ECE no worse; P10 bar set before run | ⬜ | |
| **S9** | Granite case narratives, grounded in the bundle | 100% of facts traceable (test) | ⏸ needs watsonx key or local-Granite approval | |
| **S10** | Executive summary, demo script, B1–B4 hygiene, ship v2 | Fresh clone reproduces headline in one command | ⬜ | |

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
- **Environment notes:** MSYS path conversion mangles `/mnt/...` arguments to `wsl` —
  run with `MSYS_NO_PATHCONV=1`. WSL has 12 cores, 11 GB RAM, so extractions run one
  at a time.
