# Validation report — V2

Generated 2026-09-22T12:27:54.024049+00:00

## Headline

| Metric | Value |
|---|---:|
| PR-AUC | **0.5949** |
| Lift over base rate | 336.2x |
| ROC-AUC | 0.9820 |
| Recall @1% budget | 78.0% |
| Precision @1% budget | 13.80% |
| Test rows | 1,015,564 |
| Test positives | 1,797 |
| Base rate | 0.17695% |

Seed spread across 5 runs: mean
0.5970, sd 0.0024.

## Correctness gates

A failure here voids the result regardless of performance.

| Gate | Check | Status | Detail |
|---|---|---|---|
| C2 | Shuffled-label PR-AUC within 2x base rate | **PASS** | shuffled-label PR-AUC 0.002060 vs base rate 0.001769 |
| C3 | Random-score PR-AUC at base rate | **PASS** | random-score PR-AUC 0.001772 |
| C4 | Split boundary timestamps strictly ordered and recorded | **PASS** | train_end=2022-09-06 13:36:00+00:00, val_end=2022-09-08 16:12:00+00:00; strictly ordered=True |
| C5 | Training and inference feature schemas identical | **PASS** | feature schema hash 7c58a20d069f9985 (train) vs 7c58a20d069f9985 (test) |
| C7 | Same seed and data produce identical predictions | **PASS** | same seed and data reproduce predictions: True |
| C8 | No single feature above 50% of mean |SHAP| | **PASS** | top feature bh_pair_n_prior holds 31.0% of mean |SHAP| |
| C1 | Leakage suite passes | **PASS** | 36 passed, 7 deselected, 2 warnings in 7.66s |
| C6 | One command reproduces the headline PR-AUC | **PASS** | `python -m flowguard.pipeline.run_validation` reproduces this report from the cached feature table; headline PR-AUC 0.5949 |

## Performance gates

A missed performance gate is a finding to report, not a defect to hide.

| Gate | Target | Status | Measured |
|---|---|---|---|
| P6 | PR-AUC standard deviation across seeds | **PASS** | sd 0.0024 vs < 0.02 |
| P1 | E2 beats E1 by > 2 sigma | **PASS** | delta +0.5211 > 2 sigma (0.0049) |
| P2 | E1 beats E0 by > 2 sigma | **PASS** | delta +0.0364 > 2 sigma (0.0049) |
| P3 | E7 beats E2 by > 2 sigma (or inconclusive) | **NOT_RUN** | E7 not built; feature research not reached |
| P4 | Recall at 1% alert budget | **PASS** | recall 78.0% at 1% budget vs >= 45% |
| P5 | No typology at zero recall | **PASS** | all typologies detected |
| P7 | No monotone decline across test sub-windows | **PASS** | no monotone decline; spread 0.5929 |
| P8 | Feature extraction throughput | **FAIL** | 532 tx/s vs >= 1,000 required |
| P9 | Peak resident memory | **FAIL** | 10.99 GB vs <= 10 GB allowed |

## Verdict

**Correctness gates all pass.** The result stands, subject to the performance findings above.
