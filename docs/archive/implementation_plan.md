# Tier A Execution Plan (Updated)

This plan details the exact sequence of commands and evaluations we will run once the `E2` WSL extraction completes. It incorporates the four corrections to ensure we don't accidentally validate a tabular-only model under `E2`'s name, and that we run the correct evidentiary controls.

## A1. E2 Extraction Completes *(Currently Running)*

The `run_graph.py` process is currently running in WSL and streaming parts to `HI-Small_gfp_w2_parts/`. 
Wait for the WSL watcher (`wait_e2.sh`) to report `run_graph exited` and confirm the parts are successfully on disk.

## A2. Run the Completion Script (The Evidentiary Controls)

We will run the `E2` model and compare it against the `A2` (tabular-only) baseline and our controls to prove the pipeline actually works.

**The pre-registered test:**
- Mean recall gain in the three lowest amount bands (currently **zero** recall) must exceed the gain in the two highest.

**The controls:**
1. **Hard-negative enrichment**: Run against the 1.02× control in `finish_e2.py`. If `E2` buys recall by alerting on legitimately complex accounts, that's a false-positive cost, not a win.
2. **E_LEAK**: Run the deliberate leaky control (via `run_ablation.py`). `E_LEAK` at ~0.35 against an honest `E2` at ~0.01 proves the pipeline is correctly sealed and works far better than prose claiming it does.

## A3. Validation Gates and Model Package

Generate the model package (`models/flowguard_E2_v1/`) and judge all `C1-C8` and `P1-P9` gates.

> [!WARNING]
> **CRITICAL FIX**: `run_validation.py` must be passed the `--gfp-cache` argument pointing to the **parts directory**, not a `.parquet` file. Omitting this silently produces a tabular-only result filed under E2's name with every gate passing.

**Command to run:**
```bash
python -m flowguard.pipeline.run_validation --model-id E2 --gfp-cache C:/Users/vikam/flowguard_data/processed/HI-Small_gfp_w2_parts/
```

## A4. Update the Report & "Gate A" Fork

Check the PR-AUC `delta = E2 - A2` against the 2σ threshold (**0.0034**). 

| Outcome | What it means | Next |
|---|---|---|
| Δ > +0.0034 **and** low-band concentrated | Graph structure adds real information | Proceed to Tier B (Value-flow & Sub-graph features) |
| Δ > +0.0034, uniform across bands | Another magnitude proxy | Proceed to Tier B, **narrowed to adaptive/neighbourhood features** (which encode structure rather than size) |
| \|Δ\| ≤ 0.0034 | Graph features do not help here | **Skip Tier B.** Go straight to Tier C |

---

## User Review Required

Does this accurately reflect the exact sequence and checks we need to run once the watcher alerts us that the extraction is done? If approved, I will wait for the extraction to finish and then execute these steps.
