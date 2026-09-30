# Sample outputs

Real output from the shipped model, for the product repository to build against before it
has any data pipeline of its own. Each file matches its schema in
[`../contracts/`](../contracts/); a test enforces that.

| File | What it is |
|---|---|
| `transactions_sample.csv` | 50,263 input transactions — the start of the test period, which the model never trained or tuned on |
| `scores.csv` | Those transactions, scored and ranked. Each alert carries `top_features`: the three features that pushed its score up, named, with signed contributions. Empty for rows that did not alert |
| `cases/*.json` | Evidence bundles for the ten highest-ranked alerts, one per subject account; every reason carries a plain-language `label` |
| `run.json` | Which model and threshold produced the above, and how many history rows fed the features |
| `labels.csv` | The true `is_laundering` flag for each row, so you can recompute our numbers instead of trusting them. Never an input to scoring |
| `window_metrics.json` | Our own recomputation from those labels — PR-AUC, recall at a 1% budget, and what the shipped threshold caught |

Produced by `flowguard_V2_v1` through the real entry point (`score.run`), not hand-written.

## How they were scored — with history

The window was scored **with every earlier transaction as history** (`--emit-from`): history
rows build the graph and the account-behaviour features but are not scored, exactly as in
production. Scored cold instead, the same window alerted on **30.5%** of rows against a 1%
budget — with no history, every counterparty looks new and every sender looks dormant, which
are the red flags the model learned. If you score your own windows, give them history
(at least two days).

**For how accurate the model is, read
`Project/flowguard/models/flowguard_V2_v1/metrics.json` and `model_card.md`.** This window
is a format example rather than an evaluation: 2.5 hours holding 76 laundering transactions,
so every figure in `window_metrics.json` carries a wide interval. Measured over the full
test period the model reaches PR-AUC 0.595; over this window it happens to read 0.568.

The data is synthetic — the IBM AML HI-Small corpus. No real person or account appears in it.

## Regenerating

```bash
cd Project/flowguard
python scripts/make_sample_outputs.py --rows 50000 --cases 10
```
