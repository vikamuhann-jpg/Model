"""Regenerate sample_outputs/ -- what the product repository builds against.

Takes a contiguous window from the start of the TEST period (rows the shipped
model never trained or tuned on), writes it as the example input, then scores
it with the real entry point, without a graph cache. So the samples prove the
inference path end to end, not just the file format.

**Read the scores as format examples, not as accuracy.** A window this short
starts the graph cold: the first transactions have no history, so their graph
features -- and scores -- are weaker than they would be mid-stream. Accuracy
figures live in the model package's metrics.json.

    cd Project/flowguard
    python scripts/make_sample_outputs.py [--rows 50000] [--cases 10]
"""

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from flowguard.data import schema as S
from flowguard.pipeline import score

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("FLOWGUARD_DATA", "/mnt/c/Users/vikam/flowguard_data"))
PACKAGE = REPO / "Project" / "flowguard" / "models" / "flowguard_A4_v1"
OUT = REPO / "sample_outputs"

INPUT_COLUMNS = [
    S.TRANSACTION_ID,
    S.TIMESTAMP,
    S.SOURCE_ACCOUNT,
    S.DESTINATION_ACCOUNT,
    S.AMOUNT,
    S.CURRENCY,
    S.AMOUNT_RECEIVED,
    S.CURRENCY_RECEIVED,
    S.PAYMENT_TYPE,
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--cases", type=int, default=10)
    args = parser.parse_args()

    provenance = json.loads((PACKAGE / "PROVENANCE.json").read_text(encoding="utf-8"))
    val_end = pd.Timestamp(provenance["split"]["boundaries"]["val_end"])

    df = pd.read_parquet(DATA / "processed" / "HI-Small_transactions.parquet")
    window = (
        df[df[S.TIMESTAMP] > val_end]
        .sort_values(S.TIMESTAMP, kind="stable")
        .head(args.rows)
    )
    OUT.mkdir(parents=True, exist_ok=True)
    sample = window[INPUT_COLUMNS].copy()
    sample[S.TIMESTAMP] = sample[S.TIMESTAMP].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    sample.to_csv(OUT / "transactions_sample.csv", index=False)
    print(
        f"input: {len(sample):,} test-period rows, "
        f"{window[S.TIMESTAMP].min()} .. {window[S.TIMESTAMP].max()}",
        flush=True,
    )

    summary = score.run(
        PACKAGE, OUT / "transactions_sample.csv", OUT, n_cases=args.cases
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
