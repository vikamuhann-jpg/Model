# Sample outputs

Real output from the shipped model, for the product repository to build against before it
has any data pipeline of its own. Each file matches its schema in
[`../contracts/`](../contracts/); a test enforces that.

| File | What it is |
|---|---|
| `transactions_sample.csv` | 50,000 input transactions — the start of the test period, which the model never trained or tuned on |
| `scores.csv` | Those 50,000 transactions, scored and ranked |
| `cases/*.json` | Evidence bundles for the ten highest-ranked alerts, one per subject account; graph reasons carry a plain-language `label` |
| `run.json` | Which model and threshold produced the above, and how many history rows fed the features |

Produced by `flowguard_V2_v1` through the real entry point (`score.run`), not hand-written.

## How they were scored — with history

The window was scored **with every earlier transaction as history** (`--emit-from`): history
rows build the graph and the account-behaviour features but are not scored, exactly as in
production. Scored cold instead, the same window alerted on **30.5%** of rows against a 1%
budget — with no history, every counterparty looks new and every sender looks dormant, which
are the red flags the model learned. If you score your own windows, give them history
(at least two days).

For how accurate the model is, read
`Project/flowguard/models/flowguard_V2_v1/metrics.json` and `model_card.md`; a 50,000-row
window is a format example, not an evaluation.

The data is synthetic — the IBM AML HI-Small corpus. No real person or account appears in it.

## Regenerating

```bash
cd Project/flowguard
python scripts/make_sample_outputs.py --rows 50000 --cases 10
```
