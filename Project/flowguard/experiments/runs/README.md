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
