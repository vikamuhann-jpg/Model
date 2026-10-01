# Reply to the LinuxONE handoff — 2026-09-26

From Vika, answering `HANDOFF_VIKA_2026-09-24.md`. Ordered as you numbered them.
Everything below is in this repository on branch `winning-plan`; nothing is pushed yet.

---

## 1. Your edits to my files (R7) — reviewed, and made at the source

Thank you for these. Three of the four were real defects in my code rather than in your
copies, so I fixed them here instead of accepting patches to a fork:

| Your edit | Verdict |
|---|---|
| `01` cell 16 keeps `e1_test_scores` / `N_E1_FEATURES` | **Correct, and mine had the same bug.** Cell 21 frees the E1 frames; cells 26, 27 and 37 still read them. Fixed the same way. My `01` had never been run end to end either. |
| `02` cell 1 loads protobuf 3.13.0 before TensorFlow; thread settings straight after `import tensorflow` | **Correct, and it overturns a claim of mine.** See §2. My `02` is PyTorch, so the edit does not apply to that file, but both documents were wrong and are corrected. |
| `02` cell 19 reads `pattern_type_codes` + `pattern_type_categories` | **Already correct here.** My `01` writes both and my `02` decodes them that way. This was a mismatch between your Keras `02` and my `01`. |
| Both `cell 3`: `FLOWGUARD_VARIANT`, outputs to `~/flowguard_outputs/<VARIANT>/` | **Adopted exactly.** Both notebooks now read `FLOWGUARD_VARIANT` (default `HI-Small`) and write under `~/flowguard_outputs/<VARIANT>/`. |

## 2. Keras: you were right, and my reasoning was wrong

My `STATUS.md` said TensorFlow 2.9.3 cannot run on the image and that "nothing installable
fixes it on s390x". Every observation behind that was accurate — the protobuf version, the
`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION` workaround, the
`RepeatedCompositeFieldContainer` error. The inference was not: I generalised from one
failing import path to the whole package set, and I never tested the simpler explanation
for my supporting evidence (the datathon's own TensorFlow notebooks have no saved outputs
because nobody had run them).

Both `linuxone/README.md` and `linuxone/STATUS.md` now record the correction, the mechanism
— two protobufs, the `3.13.0` beside TensorFlow shadowed by the `7.35.1` in `~/.local` —
and the thread-ordering constraint, credited to your run.

**Decided: Keras ships, so your bundle's notebook is the right one.** I have restored
`02_keras_model.ipynb` here as the neural notebook and removed the PyTorch port
(`02_neural_model.ipynb`), which stays in git history at `136c07a^` as the fallback if
TensorFlow ever breaks here again.

My cell 1 does the protobuf swap slightly differently from yours, and I would rather we
converge on one: instead of relying on import order alone, it puts the system
`site-packages` first **for the TensorFlow import only** and restores `sys.path`
afterwards, so nothing else silently changes version. It then prints which protobuf was
loaded and from where, and fails with that detail if a layer cannot be built. Please diff
it against yours and take whichever you prefer — but take one of them, not a merge of both.

## 3. Your §3 items

**R3 — the nameless bar. Fixed, and your one-line fix was the right one.**
`metrics.py:194` kept `""` because `isinstance("", str)` is true, and it reached both the
charts and gate P5. Worth knowing why `test_per_group_recall_handles_unlabelled_rows`
passed anyway: its unlabelled rows are all *negative*, so the `""` group holds no positives
and the `if not total` guard skips it. The case that matters is an unlabelled **positive**,
which is the common case — 38% of HI-Small positives and 71% of LI-Small ones carry no
typology. There is now a test for exactly that, and it fails against the old code.

**R4 — BIPARTITE at zero recall. Stated, with two fixes now in the notebook.** `02` prints
a named P5 failure instead of averaging it away. Beyond that, section **7b** adds two cells,
neither of which retrains anything:

1. **A diagnosis.** Zero recall at a 1% budget has two different causes. If the missed
   positives' *best percentile* is near 100, the pattern is visible and the budget is the
   binding constraint. If their median is near 50, the network cannot see it at all. We have
   never checked which of the two this is, and the fix differs.
2. **A rank blend with E2.** A rank-average of the two models needs no shared scale and no
   retraining, and it is the reliable way to keep the network's extra alerts while restoring
   a typology the trees already catch. The cell prints PR-AUC, recall at 1% and which
   typologies sit at zero recall for DNN weights 0 / 0.25 / 0.5 / 0.75 / 1, and writes
   `dnn_blend.csv`.

If the diagnosis says "invisible" rather than "near miss", the likeliest cause is scaling:
GFP counts are heavily skewed and `StandardScaler` compresses exactly the large values that
make a fan-in or bipartite structure stand out, while trees are scale-invariant. `log1p`
before scaling would be the next thing to try — about twenty lines and one retrain. I have
not added it speculatively, because the diagnosis should decide it.

**R5 — the 30-epoch cap.** Raised to 150 with patience 10, and the run now prints whether
it stopped on patience or hit the cap. A number produced by a budget should not be compared
with one produced by convergence, and nothing in the output used to say which it was.

**R6 — the seed.** Noted, and mine sets `torch.manual_seed(42)` and `np.random.seed(42)`
in cell 1, so it was already reproducible.

**Your seed sweep changes what we can claim, and I would keep your framing.** PR-AUC
0.0407 / 0.0462 / 0.0231 / 0.0297 against XGBoost's 0.0325 does not support "the DNN beats
XGBoost". Consistently catching 4–9 more of 127 at a 1% review budget is a narrower and
defensible claim, and it is what the comparison table should say.

**Three ways to make the neural arm worth shipping, in the order I would try them:**

1. **Ship the blend instead of the network** (free — the 7b cell already computes it). If
   rank-averaging beats both arms, the honest headline is the ensemble, and R4 very likely
   resolves with it.
2. **Average 3–5 seeds' ranks** (~15 minutes of VM time). A 0.0231 seed beside a 0.0462 one
   is variance; averaging stops us reporting whichever seed we happened to run. Your sweep
   is exactly the evidence that this is needed.
3. **Only then touch the architecture.** Depth, width and dropout are the slowest lever and
   the least likely to matter at this base rate.

The 30-epoch cap (R5) may also have been holding it back: nothing in the old output said
whether training converged or simply ran out of budget, and now it does.

## 4. The delivered model (R8) — all five done

1. **Calibrator as JSON.** `models/flowguard_V2_v1/calibrator.json`:
   `{"kind": "isotonic-piecewise", "x": [...], "y": [...]}`. Read it back with
   `numpy.interp(raw, x, y)`, flat outside the range — which is exactly what
   `IsotonicRegression(out_of_bounds="clip")` computes. Agreement with the pickle is
   **6.0e-8** over 20,100 points, inside the fitted range and outside it. `run_validation`
   writes it for every future package, and `score.py` prefers it over the pickle.
2. **Encoder as a JSON vocabulary.** `models/flowguard_V2_v1/encoders/categorical.json`:
   `{"kind": "ordinal", "unseen_code": -1, "categories": {"currency": {...}}}`. Unseen
   categories still map to `-1`. Nothing imports `flowguard`, so the package-name collision
   is gone.
3. **`top_features` in `scores.csv`.** The three features that pushed each alert up, named
   in plain language with signed contributions, for example
   `sender's outgoing transfers (24h window): fan/degree ratio (+3.111); earlier transfers
   from this sender to this receiver (0 = first-time counterparty) (+2.507)`. Empty for
   non-alert rows. `contracts/score.schema.json` documents it.
4. **Labels shipped.** `sample_outputs/labels.csv` (`transaction_id,is_laundering`) and
   `sample_outputs/window_metrics.json`, which is our own recomputation of the window so
   you can check our arithmetic instead of trusting it. Please treat those figures as a
   format example: 2.5 hours holding few positives. The 0.595 you wanted to reproduce is a
   full-test-period number and lives in the package's `metrics.json`.
5. **Rank ties — already by `raw_score`.** `rank` orders by `score`, then `raw_score`, in
   the shipped file; I verified it row by row. Your note must come from the older D37
   delivery. It matters more than it sounds: isotonic calibration saturates, so **49,611 of
   50,263 rows share a calibrated score with another row**, and the tie-break decides
   nearly every rank. Ordering by `score` alone is close to arbitrary.

### One defect I found while doing (3), which affects what you already have

`shap.TreeExplainer` truncates an early-stopped booster at `best_iteration`, while our
scoring path uses every tree. On v2 that is **741 trees explained against 841 scored**, so
every evidence bundle we have shipped, D37 included, explained a model that never produced
its score. The fix is XGBoost's own `pred_contribs=True` — the same TreeSHAP implementation
`shap` calls into — which also removes `shap`, absent from the datathon package list, from
our dependencies. A test now asserts TreeSHAP's defining identity, contributions + bias ==
the scored margin, against the scoring path itself.

**What this changes for you:** regenerated bundles and `top_features` use the corrected
explanations. Raw model scores are unchanged, bit for bit. Calibrated scores move by 6e-8
from the JSON calibrator, which flipped exactly one row sitting precisely on the threshold,
so the sample window now holds **631 alerts rather than 630**. Nothing else moved.

### A second defect, in notebook 01's save cell

Cell 21 warns that E0/E1 score rows in the frame's order while E2 scores them in
chronological (HDF5) order, and that pairing one model's scores with the other's labels
"would silently produce a plausible, wrong number". Cell 35 then did exactly that: it wrote
`e2_test_predictions.csv` from `test_df` (frame order) with `e2_scores` (chronological), and
saved `test_labels.npy` from the frame-order labels beside chronological scores. Whenever
the raw file is not already sorted by timestamp, every row in that CSV is mislabelled.

Both now come from `test_meta`, the chronological frame the notebook already builds. If you
have used `e2_test_predictions.csv` or `test_labels.npy` for anything, please re-take them
from a fresh run. The metrics in `results.json` are unaffected — they never crossed the two
orders.

I also fixed a latent `NameError` in the same notebook: `_s` was called but never defined,
on the `SLIM_DTYPES = False` path.

## 5. LI-Small (R6) — files ready

Packaged with checksums, kept out of git because they are data:

| File | Size | SHA-256 (first 16) |
|---|---:|---|
| `LI-Small_Trans.csv.gz` | 118 MB | `44a7fe4b4e6222fc` |
| `LI-Small_accounts.csv.gz` | 13 MB | `9ee9c1f044ef2100` |
| `LI-Small_Patterns.txt` | 97 KB | `734c15b7ff4be1a0` |

Gzipped because both notebooks read `.csv.gz` transparently; `Patterns.txt` must stay
uncompressed, since `parse_patterns` opens it directly rather than through pandas. The
Patterns checksum matches our own ingest record, so it is the file our results were built
from.

**Agreed on the framing, and thank you for raising it.** LI-Small shares the IBM generator
and therefore the ACH convention, so it is a **base-rate contrast** (0.0496% against
0.0891%), never external validation; `docs/CORPUS_COMPARISON.md` says so and I would keep
that wording in anything a judge sees. One further caveat for the run: only 28.7% of its
positives carry a typology, against 62.0% on HI-Small, so per-typology charts there describe
under a third of the positive class.

## 6. What I need from you

1. **Run 01 and then 02 from this branch and send me section 7b's two tables** — the
   percentile diagnosis and the blend. They decide R4 and R3 between them, and neither
   needs a retrain. While you are there: `01` also had an ordering defect, which is why I
   need a fresh run rather than the numbers you already have (below).
2. **`Vika/` belongs on a branch in this repository, not untracked in yours** (your R9). I
   will take it; nothing of mine needs to sit in your tree.
3. **`flowguard_V2_v1` now carries the two JSON files** — please switch to them, and tell me
   if anything still forces a pickle load.
4. If you rebuild the bundle, take `metrics.py`, `score.py` and both notebooks from this
   branch, since the fixes are at the source rather than in your copies.
