# FlowGuard

**A graph-based, temporal and resource-efficient anti-money-laundering detection pipeline.**

> Do graph-structural features measurably improve transaction-level AML detection over a
> tabular baseline — and at what cost in throughput and memory?

Both halves are the deliverable. A result reporting only detection quality has answered
half the question.

---

## What this repository is

A **Track R** research pipeline: raw corpus → canonical schema → leakage-safe temporal
split → streaming transaction graph → features → models → validation gates → a model
package. It stops at a validated model. There is no API, dashboard or case-management
layer, deliberately ([`docs/README.md`](docs/README.md) explains the scope decision).

| | |
|---|---|
| Governing plan | [`docs/FlowGuard_ML_Pipeline_Plan_v3.md`](docs/FlowGuard_ML_Pipeline_Plan_v3.md) |
| Working plan | [`docs/Execution_Plan_TrackR.md`](docs/Execution_Plan_TrackR.md) |
| Open items | [`docs/OPEN_ITEMS.md`](docs/OPEN_ITEMS.md) |
| Decision records | [`docs/ADR-00*.md`](docs/) — seven, each one a trap the checks caught |
| Corpus | IBM AML **HI-Small** — 5,077,237 transactions, 515,078 accounts, 4,522 positives (0.089%) |

## The headline result

**84% of the tabular baseline's apparent performance was a simulator artifact.**

| Arm | Features | PR-AUC | Recall @1% budget |
|---|---:|---:|---:|
| `payment_type` included | 13 | 0.0416 ± 0.0030 | 41.0% |
| `payment_type` **removed** | 12 | **0.0066 ± 0.0003** | **11.8%** |

Gate C8 (no feature above 50% of mean |SHAP|) fired at 56.8%. Investigating it found that
**2,553 of 2,554** annotated pattern transactions are ACH — AMLSim injects laundering over
a single payment rail, so "is ACH" nearly identifies an injected pattern. It is not
leakage: the rail is observable at scoring time. It is a spurious correlation that will
not survive contact with real data, and it was inflating every headline number.

The honest baseline is a **5.6× lift, not 35.7×** ([ADR-007](docs/ADR-007-payment-type-artifact.md)).

## Where the honest baseline fails

Recall at the 1% alert budget, by transaction amount
([full analysis](docs/ERROR_ANALYSIS_A2.md)):

| Amount band | Positives | Recall |
|---|---:|---:|
| ≤ $2,671 | 220 | **0.0%** |
| $2,671 – $17,158 | 442 | 14.7% |
| > $17,158 | 244 | 17.2% |

The model has learned *"large transfer"* — the legacy threshold behaviour this project set
out to improve on, and exactly what structuring defeats. This is the gate plan v3 §17.2
places in front of all feature work, and it produces one falsifiable prediction:

> Graph-structural features should recover **low-value** positives specifically, because a
> small transaction inside a fan-in, cycle or chain is identifiable by its position in the
> topology rather than its size. If graph features help, the gain must land
> disproportionately in the bottom three amount bands.

A uniform lift would mean the graph features are another magnitude proxy. Temporal-velocity
features are **not** evidence-supported — recall by chain position is flat.

## Quick start

Linux only. The Graph Feature Preprocessor's native backend ships only in snapml's
manylinux wheels ([ADR-001](docs/ADR-001-gfp-platform.md)).

```bash
# Windows: stage the wheelhouse (WSL here has no outbound network)
powershell -File Project/flowguard/scripts/refresh_wheelhouse.ps1

# WSL: build the environment and verify GFP actually works
cd Project/flowguard && bash scripts/setup_wsl.sh

# run it
python -m flowguard.pipeline.ingest        --variant HI-Small
python -m flowguard.pipeline.run_baseline  --variant HI-Small   # E0, E1, sanity baselines
python -m flowguard.pipeline.run_ablation  --variant HI-Small   # the artifact ablation
python -m flowguard.pipeline.run_graph     --variant HI-Small   # E2, GFP graph features
python -m flowguard.pipeline.run_validation --model-id E2       # gates + model package
```

Frozen experimental rules: [`configs/experiment.yaml`](Project/flowguard/configs/experiment.yaml).

## The seven traps

Four of these would each have produced a clean, impressive, entirely false result.

| ADR | What it caught |
|---|---|
| [001](docs/ADR-001-gfp-platform.md) | GFP's native backend is **absent from the Windows wheel** — all six binaries export zero `gf_*` symbols. Import succeeds; construction raises. |
| [002](docs/ADR-002-boundary-policy.md) | The plan's **preferred split policy erases the corpus** — pattern durations reach 8d10h against a 10-day span, so an honest purge buffer drops 100% of rows. |
| [003](docs/ADR-003-sparse-tail-trim.md) | The corpus tail is **~59% laundering** against a 0.089% base rate, which made `day_of_week` alone outscore the entire model. |
| [004](docs/ADR-004-gfp-batch-leakage.md) | GFP's `transform` lets an edge **see later edges in its own batch** — a fan feature reads 1.0 alone and 4.0 batched. `batch_size=50,000` would have inflated E2 and nothing else. |
| [005](docs/ADR-005-gpu-training.md) | GPU training **silently undertrained** the model: early stopping halted at iteration 80 while it improved through 220, costing 22% PR-AUC. |
| [006](docs/ADR-006-gfp-time-window.md) | An unbounded graph window makes extraction **fail to terminate** — throughput fell 16.5×. Bounding it helps 37–53%, but does not fix it: the vertex map grows regardless. |
| [007](docs/ADR-007-payment-type-artifact.md) | The dominant feature is a **generator artifact** worth 84% of the baseline's performance. |

Two recurring lessons sit underneath them: **a stateful streaming component must be
profiled at steady state, not at startup**; and **a single run on this corpus carries
±0.002 PR-AUC of noise**, so no comparison means anything until it is repeated across
seeds. That seed spread fixes the project's inclusion bar at **2σ ≈ 0.0034 PR-AUC**.

## Layout

```
docs/                     plans, seven ADRs, error analysis, open items
Dataset_/IBM_Dataset/     raw corpora (~39 GB, gitignored)
Project/flowguard/
  configs/                frozen experimental rules
  src/flowguard/
    data/                 schema, loader, patterns, validator, windowing
    splits/               temporal, hard_negative, unseen_pattern
    graph/ features/      GFP wrapper, transaction features
    models/               rules, xgb, rolling-origin tuning
    evaluation/           metrics, sanity, thresholds, interpretation,
                          stability, profiling, error_analysis, gates
    registry/ pipeline/   experiment log, runners
  tests/
    unit/ leakage/ integration/      117 tests
```

`tests/leakage/` is a **first-class, merge-blocking** category, not a subfolder of unit
tests. All seven checks required by plan v3 §11 are implemented, including
`test_future_edge_invariance` — the strongest one available.

## Status and honest limits

E0, E1 and the artifact ablation are measured and logged. **E2 (GFP graph features) is
the open experiment.** E3–E7 are deliberately unbuilt: which families get written is an
*output* of the error analysis, not an input.

* **No cross-dataset validation.** Everything here is one synthetic generator.
  Generalisation beyond AMLSim is unmeasured, and ADR-007 makes that the most important
  gap in the project.
* **Typology recall covers ~62% of positives** — the rest carry no annotation.
* **140 of 370 patterns are truncated** at a split boundary; their recall is a floor.
* **Gate P4 will be reported as a miss.** Its 45% target was set against the
  artifact-inflated baseline. Moving a pre-registered gate after seeing results is the
  thing gates exist to stop — but pre-registering against preliminary numbers inherits
  whatever contaminates them, and that is worth stating.
* **The test set has been scored once.**

A negative result is a success condition here. If graph features do not beat the tabular
baseline under controlled conditions, that is a publishable finding, and plan v3 §1 says
so outright.
