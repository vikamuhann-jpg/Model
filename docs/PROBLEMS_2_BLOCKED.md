# Problems blocked on someone else

**As of 2026-09-26.** Each of these has a solution we cannot execute ourselves: it needs
the LinuxONE VM, the other team's rerun, or a decision only the project owner can make. For
each one, the part *we* could do is already done, and what remains is written out as
instructions for whoever is holding it.

Companion pages: **[PROBLEMS_1_FIXABLE.md](PROBLEMS_1_FIXABLE.md)** (ours to do) ·
**[PROBLEMS_3_LIMITS.md](PROBLEMS_3_LIMITS.md)** (cannot be fixed, only stated).

| Blocked on | Items |
|---|---:|
| The VM, which we cannot reach | 3 |
| The other team's rerun | 2 |
| A decision or action only you can take | 3 |

**The single most useful unblock:** one Run All of notebooks 01 and 02 on the VM from this
branch. It clears BLK-01 to BLK-04 at once and produces the two tables that decide the
neural arm.

---

# Blocked on the VM

## BLK-01 · The protobuf fix has never run on the VM
**What is wrong.** `02_keras_model.ipynb` cell 1 now loads the system protobuf 3.13.0
before TensorFlow instead of the 7.35.1 in `~/.local` that shadows it. Our version differs
from Shivraj's: it puts the system `site-packages` first **for the TensorFlow import only**
and restores `sys.path` afterwards, so no other package silently changes version. It prints
which protobuf loaded and from where, and fails with that detail if a layer cannot be built.

**Why we cannot finish it.** TensorFlow is not installed here, and the architectures differ:
the VM is s390x (big-endian IBM Z), this machine is x86. Passing locally would prove nothing.

**What we did instead.** Checked that every code cell parses, that no name is read before it
is defined, and that no cell reads a variable a later cell deletes. That catches `NameError`
and syntax faults, not runtime behaviour.

**Solution — for whoever has the VM.** Restart the kernel, run cell 1 alone, and confirm the
printed protobuf is below 3.20 and its path is the system `site-packages`, not `~/.local`.
If the layer build fails, the error names the loaded version and path — send that line.
Then diff our cell 1 against Shivraj's and keep **one**, not a merge of both.

## BLK-02 · The E2/E3 cells have never executed
**What is wrong.** Section 7b of `02_keras_model.ipynb` adds two cells: a percentile
diagnosis and a rank blend with the tree model. Neither has run.

**Why it matters.** Their output *is* the decision for both open neural-arm items — whether
the missed typology is a near miss or invisible, and whether a blend beats both arms. Until
they run, E2 and E3 in [`../PENDING.md`](../PENDING.md) stay open on our side too.

**Solution.** Run 01 (which writes `e2_test_scores.npy`), then 02, and send back the two
printed tables and `dnn_blend.csv`. Neither cell retrains anything, so both take seconds
once the notebooks are loaded. How to read them:

* **Diagnosis.** A *best percentile* near 100 means the pattern is visible and the 1% budget
  is the binding constraint → the blend is the fix. A *median* near 50 means the network
  cannot see it → the fix is feature scaling (`log1p` before `StandardScaler`, about twenty
  lines and one retrain), because GFP counts are heavily skewed, and trees are
  scale-invariant where a network is not.
* **Blend.** The row with the best PR-AUC that also reads "none" under *typologies at zero
  recall* is the arm to ship.

## BLK-03 · The measured LinuxONE numbers are stale
**What is wrong.** The figures in the handoff — E2 PR-AUC 0.0325, DNN 0.0407, notebook 01 in
5 min 52 s at 2.11 GB — predate this branch. Since then the epoch cap changed (30 → 150),
patience changed (5 → 10), the typology grouping changed (the unnamed bar is gone, which
moves every per-typology chart), and a row-ordering defect in notebook 01 was fixed.

**Why it matters.** They are the only numbers measured on the target hardware, and they are
quoted in the handoff. They must not reach anything judge-facing until re-measured.

**Solution.** The same single rerun. Replace the table in `linuxone/STATUS.md` and in the
handoff reply with the new values, noting the date and branch beside them.

---

# Blocked on the other team's rerun

## BLK-04 · Two of their files contain mislabelled rows
**What is wrong.** Notebook 01 cell 35 wrote `e2_test_predictions.csv` by pairing `test_df`
ids (input-file order) with `e2_scores` (chronological order), and saved `test_labels.npy`
from file-order labels beside chronological scores. Cell 21's own comment warns about
exactly this hazard. Whenever the raw CSV is not already sorted by timestamp, every row in
that file is mislabelled.

**Why we cannot finish it.** We fixed the notebook — both now come from `test_meta`, the
chronological frame it already builds — but the *files* were produced on the VM.

**Solution.** Re-take both from a fresh run of 01 and discard any analysis built on them.
`results.json` is unaffected: it never crossed the two orders.

## BLK-05 · LI-Small has not been run as a second corpus
**What is wrong.** The three files are packaged and checksummed at
`C:\Users\vikam\flowguard_data\handoff_LI-Small\` (118 MB + 13 MB + 97 KB), but nobody has
run the notebooks against them.

**Why we cannot finish it.** We cannot send files from here, and the run belongs on the VM.

**Solution.** You send the three files; they run both notebooks with
`FLOWGUARD_VARIANT=LI-Small`, which now writes into its own output directory so the
HI-Small results are not overwritten. **Frame the result correctly:** LI-Small shares the
generator and its ACH convention, so it is a **base-rate contrast** (0.0496% against
0.0891%), never external validation ([CORPUS_COMPARISON.md](CORPUS_COMPARISON.md)). Flag
too that only 28.7% of its positives carry a typology, against 62.0% on HI-Small, so
per-typology charts there describe under a third of the positive class.

---

# Blocked on a decision or an action only you can take

## BLK-06 · The demo notebook and the headline disagree by roughly 18×
**What is wrong.** The VM notebook trains on a **2-day window**
(`WINDOW_DAYS = 2022/09/08–09`, 170,585 test rows, 127 positives) and reports E2 PR-AUC
**0.0325**. Our headline, from the full 5,078,345-row corpus, is **0.595**. Both are ours,
and nothing on screen explains the difference.

**Why it matters.** This is the most dangerous item across all three pages. A judge who runs
the notebook sees the small number beside a README claiming the large one, and the
uncharitable reading is the default one.

**Why it cannot simply be fixed.** The VM has 6 GB and 2 vCPUs. Full-corpus extraction takes
hours there and the feature file is about 3.8 GB — see
[PROBLEMS_3_LIMITS.md](PROBLEMS_3_LIMITS.md), LIM-06. The gap can be narrowed, not closed.

**Solution, mostly writing rather than computing:**
1. **Reconcile it in plain words** at the top of notebook 01 and in `linuxone/README.md`: a
   three-row table giving *this notebook, this VM, 2 days of data* against *the shipped
   model, full corpus, reproduced by `run_validation`*, and one sentence saying the
   difference is the training window, not the method. About 30 minutes, and it removes the
   appearance of contradiction entirely.
2. **Widen the window** as far as 6 GB allows — 3 to 4 days instead of 2 — so the demo
   number is less extreme. About an hour, plus a VM run to confirm it fits.
3. **Decide who sees which.** If judges see only the notebook, the reconciliation table is
   the deliverable. If they see the repository, the README headline governs and the notebook
   is an illustration.

**Your call:** which audience we optimise for. We can do (1) and (2) either way.

## BLK-07 · Four hosted reports still quote pre-ADR-015 figures
**What is wrong.** Four reports published on 2026-09-21 — Validation Report, Project Ledger,
Six Phases Sixteen Gates, Case Desk — all quote A4-era numbers, taken before the GFP
double-insertion defect was found. The README already labels them superseded.

**Why we cannot finish it.** They are published under your account, and republishing or
deleting them is an outward-facing act that is yours to authorise.

**Solution.** Pick one. **Update** them to the v2 numbers — we can rewrite them from
`STATUS.md` and the package's `metrics.json` — or **unpublish** them and let the repository
be the single source. Updating is right if they have already been shared; unpublishing is
right if they have not. Either way, settle it before the repository is shown: a stale link
is worse than no link.

## BLK-08 · The work is uncommitted, and nothing is pushed
**What is wrong.** 38 changed files with no commit; branch `winning-plan` is two commits
ahead of its remote and has never been pushed.

**Why we cannot finish it.** Committing is ours to do (FIX-01) but needs your yes each time,
and **pushing or merging to `main` is a separate decision we will not take on our own.**

**Solution.** Say the word for the commit. Then decide separately whether `winning-plan`
goes to the remote now, after the LI-Small result lands, or only once BLK-07 is settled.
