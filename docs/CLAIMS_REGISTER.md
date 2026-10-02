# Claims register

**Every number this project publishes, the record that proves it, and the test that keeps
the two equal.** If a number appears in the README, STATUS, a model card or a notebook and is
not in this table, it should not be there.

Enforced by `Project/flowguard/tests/unit/test_claims_register.py`: each test opens the
record, reads the value out, and compares it with the published figure, rounded as
published. Records live in `Project/flowguard/experiments/runs/` unless stated.

*Verified 2026-09-30. Numbers updated after `metrics.json` regenerated in `2a94e4a`. 278 tests pass (excluding snapml/pyarrow/numpy-2 expected failures and 2 claim tests now fixed).*

---

## The register

| # | Claim | Published | Evidence | Test |
|---|---|---|---|---|
| 1 | Shipped model, test partition | PR-AUC **0.595** · recall@1% **78.3%** | `models/flowguard_V2_v1/metrics.json` → `test` | `test_claim_01` |
| 2 | Against IBM's benchmark protocol, five seeds | F1 **0.614 ± 0.002** · PR-AUC **0.608** | `S4b_no_ts_stats.json` → `summary` | `test_claim_02` |
| 3 | The published benchmark | F1 **63.2 ± 0.2** | Blanuša et al., Table 4 — `papers/` | *external; not a run* |
| 4 | Within-batch lookahead is worth nothing | batch 1: **0.518 ± 0.027** · batch 128: **0.524 ± 0.021** | `S1c_paper_b1.json` · `S1e_paper_b128.json` | `test_claim_04` |
| 5 | Half the benchmark score is the payment-type artifact | F1 0.518 → **0.249** without it | `S1c_paper_b1.json` · `S4_nopt_3000.json` | `test_claim_05` |
| 6 | Timestamp statistics were a time proxy | F1 **0.544 → 0.614** when dropped | `S4_nopt_3000_bh.json` · `S4b_no_ts_stats.json` | `test_claim_06` |
| 7 | **What the model detects** | structured **95.3%** (1,276/1,339) · unstructured **27.9%** (128/458) · 75% of positives structured | `G1_diagnosis_HI-Small.json` | `test_claim_07` |
| 8 | The headline includes the generator's tail | dense window PR-AUC **0.406** (952,348 rows, 1,003 positives) | `metrics.json` → `temporal_stability.windows[0]` | `test_claim_08` |
| 9 | Graph features help on a real network | account PR-AUC **+0.050**, 95% CI **0.019–0.108** | `P2_eth_bootstrap_ETH_gfp_parts_v2.json` → `delta` | `test_claim_09` |
| 10 | Fresh data fails its pre-registered bar | recall@1% **13.3%** (bar 50%) · **88%** unstructured · structured still **41.2%** | `G1_zero_shot_LI-Small-2M.json` · `G1_diagnosis_LI-Small-2M.json` | `test_claim_10` |
| 11 | Blind off ACH | ACH **84.9%** · cheque **4.2%** · cash, card, Bitcoin **0%** | `metrics.json` → `error_analysis.slices.payment_type` | `test_claim_11` |
| 12 | Every correctness gate passes | C1–C8 **PASS** | `V2_validation.log` | `test_claim_12` |
| 13 | Memory gate passes | P9 **9.71 GB** ≤ 10 GB | `COMP3_p9_validation.log` | `test_claim_13` |
| 14 | Throughput gate fails, with the measured alternative | P8 **532 tx/s** (bar 1,000) · **2,785** at batch 128 | `S1c_paper_b1.json` · `S1e_paper_b128.json` → `extraction` | `test_claim_14` |
| 15 | Every reason is named in plain language | 206 of 206 features | the shipped `feature_schema.json` | `test_every_feature_of_the_shipped_model_has_a_plain_language_label` |
| 16 | Scoring uses every tree, deliberately | best F1 **0.6142** vs **0.6140** truncated | `COMP1_tree_range.json` · ADR-016 | `test_claim_16` |

The README is checked too: `test_the_readme_states_the_registered_numbers` fails if it stops
showing any headline figure above.

---

## Definitions — what each number means

**Recall at a 1% budget** is the share of laundering caught if investigators review the
top 1% of transactions. Two rankings are in use, and they differ by a handful of cases:

- **Headline figures (claims 1, 11, 12–13)** come from the validation run, which ranks by
  the *calibrated* score. Calibration ties heavily at the cut-off, and which tied rows fall
  inside it is not reproducible: two runs of the same model caught 1,402 and 1,400.
- **Breakdowns (claims 7 and 10)** rank by the *raw* score, which has no ties. The answer is
  identical on every run, and it is the order `scores.csv` presents alerts in. On HI-Small
  this catches 1,404 — two more than the headline's 1,402.

Where the two meet, the gap is at most four cases of 1,797: 78.3% against 78.4%.

**Best F1** (the model card's 0.6126) uses the threshold that is best *on the test set* — an
oracle figure, useful as a ceiling and not achievable in deployment. **F1 at a
validation-chosen threshold** (claim 2's 0.614) is the deployable one, and it is the one the
benchmark comparison uses.

**Rounding** is half-up at the precision shown.

---

## Corrections found while building this register

1. **The F1 spread was overstated.** Published as ± 0.003; the record holds 0.002475, which
   rounds to 0.002. The 4-place display (0.0025) had been rounded up a second time. Corrected
   in the README, STATUS, ADR-016 and the work log. The claimed reduction in seed spread
   becomes nearly fifteenfold, not twelvefold.
2. **The same breakdown existed in two versions.** A diagnosis script briefly ranked by the
   calibrated score and produced 1,400 caught where the shipped record says 1,402 and the
   raw ranking says 1,404. Resolved by fixing the definition above, not by choosing the
   convenient number.
3. **The dense-window figure (0.406) looked unsupported** — the only file containing those
   digits was a pre-fix record. It is in fact v2's own `temporal_stability` window, which is
   now the cited evidence.

## What this register does not cover

- **Claim 3** is a citation, checked by reading the paper, not by a test.
- **Pre-ADR-015 figures** (typology hinting, the unsupervised arm, the cascade, adaptive
  features) are deliberately absent: they were measured on features later found to be
  defective, and appear only in their own ADRs under a "pre-fix" banner.
- **The LinuxONE notebook's numbers** are a 2-day-window demonstration, not the shipped
  model, and are pending a rerun on the VM.
