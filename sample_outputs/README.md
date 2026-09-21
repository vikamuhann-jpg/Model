# Sample outputs

Real output from the shipped model, for the product repository to build against before it
has any data pipeline of its own. Each file matches its schema in
[`../contracts/`](../contracts/); a test enforces that.

| File | Size | What it is |
|---|---:|---|
| `transactions_sample.csv` | 5.3 MB | 50,000 input transactions — the start of the test period, which the model never trained or tuned on |
| `scores.csv` | 6.7 MB | Those 50,000 transactions, scored and ranked |
| `cases/*.json` | 10 files | Evidence bundles for the ten highest-ranked alerts, one per subject account |
| `run.json` | — | Which model and threshold produced the above |

Produced by `flowguard_A4_v1` through the real entry point, graph extraction included — not
hand-written. 50,000 transactions scored in about 11 seconds.

## Read these as format examples, not as accuracy

A 50,000-row window is about three hours of activity. It starts the transaction graph cold:
the first transactions have no history, so their graph features, and their scores, are weaker
than they would be mid-stream. That is also why this window alerts on 5.0% of transactions
rather than the 1% the threshold was set for.

For how accurate the model actually is, read
`Project/flowguard/models/flowguard_A4_v1/metrics.json` and `model_card.md`.

The data is synthetic — the IBM AML HI-Small corpus. No real person or account appears in it.

## Regenerating

```bash
cd Project/flowguard
python scripts/make_sample_outputs.py --rows 50000 --cases 10
```
