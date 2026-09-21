# Validation report — A4

Generated 2026-09-21T13:22:44.206291+00:00

## Headline

| Metric | Value |
|---|---:|
| PR-AUC | **0.1369** |
| Lift over base rate | 115.0x |
| ROC-AUC | 0.9469 |
| Recall @1% budget | 53.5% |
| Precision @1% budget | 6.37% |
| Test rows | 761,422 |
| Test positives | 906 |
| Base rate | 0.11899% |

Seed spread across 3 runs: mean
0.1400, sd 0.0030.

## Correctness gates

A failure here voids the result regardless of performance.

| Gate | Check | Status | Detail |
|---|---|---|---|
| C2 | Shuffled-label PR-AUC within 2x base rate | **PASS** | shuffled-label PR-AUC 0.001299 vs base rate 0.001190 |
| C3 | Random-score PR-AUC at base rate | **PASS** | random-score PR-AUC 0.001214 |
| C4 | Split boundary timestamps strictly ordered and recorded | **PASS** | train_end=2022-09-07 14:52:00+00:00, val_end=2022-09-09 03:14:00+00:00; strictly ordered=True |
| C5 | Training and inference feature schemas identical | **PASS** | feature schema hash ca7efed40f449a71 (train) vs ca7efed40f449a71 (test) |
| C7 | Same seed and data produce identical predictions | **PASS** | same seed and data reproduce predictions: True |
| C8 | No single feature above 50% of mean |SHAP| | **PASS** | top feature gfp_f185 holds 17.7% of mean |SHAP| |
| C1 | Leakage suite passes | **PASS** | 32 passed, 7 deselected, 2 warnings in 11.33s |
| C6 | One command reproduces the headline PR-AUC | **PASS** | `python -m flowguard.pipeline.run_validation` reproduces this report from the cached feature table; headline PR-AUC 0.1369 |

## Performance gates

A missed performance gate is a finding to report, not a defect to hide.

| Gate | Target | Status | Measured |
|---|---|---|---|
| P6 | PR-AUC standard deviation across seeds | **PASS** | sd 0.0030 vs < 0.02 |
| P1 | E2 beats E1 by > 2 sigma | **NOT_RUN** | A4 or E1 not in registry |
| P2 | E1 beats E0 by > 2 sigma | **PASS** | delta +0.0364 > 2 sigma (0.0061) |
| P3 | E7 beats E2 by > 2 sigma (or inconclusive) | **NOT_RUN** | E7 not built; feature research not reached |
| P4 | Recall at 1% alert budget | **PASS** | recall 53.5% at 1% budget vs >= 45% |
| P5 | No typology at zero recall | **PASS** | all typologies detected |
| P7 | No monotone decline across test sub-windows | **PASS** | no monotone decline; spread 0.1493 |
| P8 | Feature extraction throughput | **FAIL** | 487 tx/s vs >= 1,000 required |
| P9 | Peak resident memory | **FAIL** | 10.93 GB vs <= 10 GB allowed |

## Verdict

**Correctness gates all pass.** The result stands, subject to the performance findings above.
