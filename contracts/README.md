# Contracts — what the AI repository hands to the product repository

This folder is the **only** agreement between this repository (the model) and the product
repository (frontend, backend, database, dashboards). Build against these four schemas and
the files in [`../sample_outputs/`](../sample_outputs/) — never against model internals.

| Contract | Describes | Produced as |
|---|---|---|
| [`transaction.schema.json`](transaction.schema.json) | One input transaction | the file you hand to scoring |
| [`score.schema.json`](score.schema.json) | One scored transaction | a row of `scores.csv` |
| [`evidence_bundle.schema.json`](evidence_bundle.schema.json) | One investigation case | `cases/<case_id>.json` |
| [`run.schema.json`](run.schema.json) | One scoring run | `run.json` |

Every file in `sample_outputs/` is validated against these schemas by
`Project/flowguard/tests/unit/test_contracts.py`, so the samples cannot drift from them.

---

## How the pieces connect

```text
 transactions (CSV/parquet)
          │
          ▼
 python -m flowguard.pipeline.score        ← this repo · Linux · batch job
          │
          ├── scores.csv        one row per transaction
          ├── cases/*.json      evidence bundles for the top alerts
          └── run.json          which model produced this
          │
          ▼
 database  ──►  backend API  ──►  dashboards / case views     ← product repo
```

**Scoring is a batch job, not a live API.** 155 of the model's 167 inputs are graph features
from IBM Snap ML, which runs only on Linux and must replay transaction history in time order
(about 450 transactions a second on the training corpus, less on real networks). One
transaction cannot be scored on its own. So: run scoring on a schedule, load its outputs into
the database, and have the product read from the database. Nothing in the product repository
needs Python, Snap ML or the model.

---

## A starting point for the database

| Table | Source | Key |
|---|---|---|
| `scoring_runs` | `run.json` | `run_id` (generate one); store `model_id`, `feature_schema_hash`, `threshold` |
| `scores` | `scores.csv` rows | (`run_id`, `transaction_id`) |
| `cases` | `cases/*.json` | `case_id`; store the bundle whole (e.g. Postgres `JSONB`) and index `subject_account`, `risk.score`, `disposition` |

Store bundles whole rather than normalising them. A bundle is self-validating evidence; if a
UI rebuilds its figures from separate tables, it can disagree with its own evidence.

---

## Rules the product must follow

These are not style preferences. Each one stops a UI from telling an investigator something
the model does not support.

1. **Show `coverage.warning` on the case itself, whenever it is set — not behind a link.**
   The model catches 599 of 796 ACH laundering transactions and 1 of 100 on every other
   payment rail. A case touching a non-ACH rail must say so where the investigator is looking.

2. **Order alerts by `rank`, not by `score`.** Calibrated scores saturate: many top alerts
   share the same score. `rank` breaks the ties with `raw_score`.

3. **Do not read small scores as low risk.** Scores are calibrated probabilities against a
   base rate of about 0.09%. A score of 0.066 is roughly 70× the base rate. Colour scales must
   be relative to the threshold in `run.json`, not to 0–1.

4. **Do not assume 1% of transactions alert.** The threshold was set for a 1% alert budget on
   the validation period. On the 50,000-row sample it alerts on **5.0%**, because a short
   window starts the transaction graph cold. Show the actual alert count from `run.json`.

5. **When `trace.is_complete` is false, label the fund-flow graph as a sample.** The trace hit
   a bound; the neighbourhood is larger than what is drawn. About a third of real traces
   truncate.

6. **Never label `trace.per_hop` amounts as "funds traced".** They are amounts observed at each
   hop. Money entering an account mixes with the balance already there; transaction data
   cannot say which funds moved on.

7. **Show a reason's `label` when it has one; show `opaque` reasons as graph patterns.**
   `gfp_f*` features carry most of the model's signal. From 2026-09-21 bundles name them
   from the graph library's documented layout (e.g. "count of fan-in patterns of size 4
   containing this transaction (24h window)"). A reason with `opaque: true` has no label —
   display it as "graph structure feature" rather than inventing a meaning.

8. **Write `disposition` and `investigator_notes` back into the bundle.** Analyst outcomes are
   the only route this project has to real labels — and to measuring its false-positive rate.

---

## Versioning

- `run.json` carries `model_id` and `feature_schema_hash`. Store them with every run; a change
  in either means scores from different runs are not directly comparable.
- Every bundle carries `schema_version`. A breaking change to these contracts bumps it.
- The shipped model is `flowguard_V2_v1` (A4 is retired, [ADR-015](../docs/ADR-015-gfp-double-insertion.md)).
  Its `uses_payment_type` is `false`, and a test fails if a model that uses the payment-type
  artifact is ever committed.
- `run.json` may carry `history_transactions`: rows used as history for features but not
  scored (`score.py --emit-from`). Store it; a run with little history alerts above budget.
