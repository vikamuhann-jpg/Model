# HI-Small Graph Features (E2) Metrics Report

This document breaks down the results of the `flowguard.pipeline.run_graph` execution (tested on the first 1M transactions). It explains the meaning, use-case, and purpose of every metric printed in the terminal output, reflecting the specific characteristics and known limitations of the IBM AMLworld dataset.

---

## 1. Graph Extraction Metrics

### `GFP time_window = 2.0 days`
* **Purpose:** Sets the memory bound for the graph. Edges older than 2 days are evicted.
* **Use Case:** Prevents the graph from growing infinitely large and exhausting system RAM.

### `batch_size=1` & `inserts each edge once`
* **Purpose:** Prevents same-batch data leakage.
* **Use Case:** Feeding transactions chronologically prevents the model from "seeing into the future." Using `batch_size=1` specifically stops transactions within the same batch from seeing each other, simulating a real-time production environment.

### `tx/s` (Transactions per Second)
* **Purpose:** Measures the throughput (speed) of the graph feature preprocessor. 
* **Your Result:** The progress counter printed values like 2,558 tx/s down to 318 tx/s; note that this counter shows a **running average** over all rows processed so far. The final overall timer reported **275 tx/s**. This final number counts *only edges inserted into the graph* (excluding self-transfers, which make up ~12% of HI-Small). This explains why the final 275 tx/s is exactly where you expect it to be compared to the final 318 tx/s progress log (318 × 0.88 ≈ 280).
* **Use Case:** This determines if the pipeline meets the project's **Gate P8** target of 1,000+ tx/s. 
* **Crucial Context:** The 275 tx/s measurement applies specifically to this developer laptop run. On LinuxONE, notebook 01's GFP extraction (also batch_size=1, 2-day window of 1,137,240 transactions) measured **4,933 tx/s**, passing P8. The two runs differ in entry point, data slice and machine, so the cause of the ~18x gap is not yet known. Both the 275 and 4,933 figures measure inserted edges, so they are directly comparable.

---

## 2. Model Training Metrics

### `base_rate=0.20495%`
* **Purpose:** The percentage of transactions in the test set that are actually labeled as money laundering.
* **Use Case:** Sets the baseline expectation. Because the data is so heavily imbalanced (roughly 2 out of every 1,000 transactions are bad), traditional accuracy metrics are useless. 

### `PR-AUC=0.3025 (lift 147.6x)`
* **Purpose:** Precision-Recall Area Under Curve. The primary metric for highly imbalanced fraud detection.
* **Your Result:** 0.3025. 
* **Use Case:** It measures how well the model balances catching laundering (recall) without falsely flagging normal behavior (precision). *Note: This score is not comparable with the shipped model's 0.595 (different data and setup).*

### `ROC-AUC=0.9776`
* **Purpose:** Receiver Operating Characteristic. Measures the model's ability to rank a random bad transaction higher than a random good transaction.
* **Use Case:** Evaluates global separability between normal and suspicious behavior.

### `@ 1.0% budget: precision=0.1322 recall=0.6451`
* **Purpose:** Simulates an assumed operating point where investigators can manually review 1% of all transactions.
* **Your Result:** At this 1% budget, the model caught **64.51%** of all money laundering in the test set (recall), and out of all the alerts it generated, **13.22%** were labeled laundering transactions (precision). 
* **Use Case:** This operating point yields a precision lift of roughly **64x** over the base rate (13.22% vs 0.205%), showing exactly how much more efficient the alert queue is compared to random sampling.

---

## 3. Feature Importance & Typology Breakdown

### `top features by gain`
* **Purpose:** Ranks inputs by how much they reduced the training loss.
* **Your Result:** `tx_payment_type_code` (44.0%) was the top feature, followed by `gfp_f183` (22.5%).
* **CRITICAL CONTEXT (ADR-007):** The dominance of `payment_type_code` is a **known artifact of the IBM generator**, which placed 84.7% of all laundering transactions (and 99.96% of injected named patterns) on the ACH rail. It is a flaw in the dataset, not intelligence. As documented in the `WINNING_PLAN`, removing this artifact drops PR-AUC drastically (from 0.504 to 0.203 in the benchmark run). *To get an honest evaluation of the model's intelligence, run `run_benchmark` with the `--no-payment-type` flag.*

### `graph features hold 49.4% of top-15 gain`
* **Purpose:** Shows that graph features account for nearly half of the total split gain among the top 15 features.
* **Use Case:** While gain share shows how often trees split on these features and how much they reduced training loss, the true proof of their value comes from comparing the PR-AUC of a model trained without graph features (E1) versus one trained with them (E2).

### `recall per typology @1% budget`
* **Purpose:** Breaks down the model's performance across different known money laundering shapes (Bipartite, Cycle, Fan-in, Scatter-Gather).
* **Your Result:** The model catches "Fan-Out" (80.6%) and "Scatter-Gather" (79.6%) patterns well, but struggles more with "Cycles" (58.3%).
* **Caveat:** This table *only* evaluates laundering that was explicitly assigned a pattern label by the generator. Approximately 38% of the laundering in HI-Small has no pattern label, and those transactions are excluded from these specific percentages.
