# Benchmark run records

The raw output behind every number in [`README.md`](../../../../README.md) and
[`docs/STATUS.md`](../../../../docs/STATUS.md). Each JSON holds per-seed metrics, the model
parameters, the split, and the GFP extraction record (parameters, batch size, throughput);
tuning runs also hold every trial. Logs are the console output of the same runs.
Steps are described in [`WINNING_PLAN.md`](../../../../WINNING_PLAN.md).

| File | Step | Result |
|---|---|---|
| `S1b_default_b128.json` | Paper protocol, our GFP config, batch 128, default XGBoost | F1 0.280 ± 0.008 |
| `S2_tuned_b128.json` / `.log` | Same, tuned (24 trials; all trials inside) | F1 0.521 ± 0.004 |
| `S1e_paper_b128.json` / `.log` | Paper GFP config, batch 128, S2 params | F1 0.524 ± 0.021 |
| `S1c_paper_b1.json` / `.log` | Paper GFP config, **batch 1** (extraction throughput here) | F1 0.518 ± 0.027 |
| `S4_nopt_1000.json` / `.log` | Batch 1, **no `payment_type`** | F1 0.242 ± 0.040 |
| `S4_nopt_3000.json` / `.log` | Same, 3,000-round cap | F1 0.249 ± 0.044 |
| `S4_nopt_3000_bh.json` / `.log` | Same, **+ behaviour features** | F1 0.544 ± 0.036 |
| `S4b_no_ts_stats.json` / `.log` | Same, **timestamp statistics dropped** — the v2 configuration | F1 0.614 ± 0.003 |
| `V2a_with_ts_validation.log` | `run_validation` on S4 (first v2 build, superseded) | PR-AUC 0.559 |
| `V2_validation.log` | `run_validation` on S4b: every gate — the shipped v2 | PR-AUC 0.595, C1–C8 pass |
| `P2_speed_2000000.json` / `P2_speed.log` | Throughput, continuous vs reconstruction, 2M rows | 1,488 vs 1,507 tx/s, identical features |
| `P2_eth.log` | Ethereum extraction (stopped at the 1.25M-row prefix) | 135 tx/s |
| `P2_eth.json` / `P2_eth_eval.log` | Ethereum three-arm evaluation | graph Δ +0.0503; behaviour Δ +0.0098 |
| `P2_eth_bootstrap_ETH_gfp_parts_v2.json` / `P2_eth_bootstrap.log` | Paired bootstrap on the graph Δ | +0.0497 [0.0186, 0.1079] |
| `samples_v2.log` | `make_sample_outputs.py` with history | 630 alerts / 50,263 |

S1b's log was overwritten by the S2 launch (logged in WINNING_PLAN); its JSON survived.
Paths inside the records are the build machine's.

## Earlier tracks, added 2026-09-26

These backed published numbers while living only in the data folder — the gap
[`PENDING.md`](../../../../PENDING.md) B1 recorded. **Every one predates the GFP
double-insertion fix ([ADR-015](../../../../docs/ADR-015-gfp-double-insertion.md)) unless
its row says otherwise**, so read the magnitudes as pre-fix.

| File | Step | Backs |
|---|---|---|
| `COMP1_tree_range.json` | **Post-fix.** 841 trees against 741 on the test partition | [ADR-016](../../../../docs/ADR-016-tree-range-at-scoring.md) |
| `tier_c.json` · `tier_c.log` · `tier_c_salvage.log` | Tier C, the Ethereum transfer | [ADR-012](../../../../docs/ADR-012-account-disjoint-proxy.md) |
| `tier_c_bootstrap.json` · `tier_c_boot.log` | Paired bootstrap on the Tier C delta | ADR-012; superseded by `P2_eth_bootstrap_*` |
| `p3_cascade.json` · `p3_cascade_ETH.json` · `p3.log` · `p3_eth.log` | P3, the cheap-tier cascade | [ADR-014](../../../../docs/ADR-014-cascade-cannot-prefilter.md) |
| `p4p6.json` · `p3p4p6.log` | P4 typology hinting, P6 unsupervised arm | FR-06 and FR-07 in `PENDING.md` C |
| `p1_latency.json` · `p1_bench.log` | P1 inference latency | the package's `metrics.json` |
| `scaling_envelope.json` | S5 scaling envelope | [ADR-013](../../../../docs/ADR-013-degree-skew-dominates-cost.md) |
| `error_analysis_a2.json` | Where the artifact-free baseline fails | [`ERROR_ANALYSIS_A2.md`](../../../../docs/ERROR_ANALYSIS_A2.md) |
| `tierb_ablation.json` · `ablation_tx.json` | Tier B adaptive features, rejected | [ADR-011](../../../../docs/ADR-011-adaptive-features-rejected.md) |
| `baseline_results.json` · `e2_final.json` | E0/E1 baselines and the E2 result | `STATUS.md` history |
