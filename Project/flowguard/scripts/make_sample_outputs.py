"""Regenerate sample_outputs/ -- what the product repository builds against.

Takes a contiguous window from the start of the TEST period (rows the shipped
model never trained or tuned on), writes it as the example input, then scores
it with the real entry point (`score.run`) over the whole corpus, emitting only
the window. Everything before the window is history: it builds the graph and
behaviour features, as in production. The graph features come from the
training-time cache, so they are exactly what the model was validated on.

Accuracy figures live in the model package's metrics.json; a 2.5-hour window is
a format example, not an evaluation.

    cd Project/flowguard
    python scripts/make_sample_outputs.py [--rows 50000] [--cases 10]
"""

import argparse
import json
import os
import shutil
from pathlib import Path

import pandas as pd

from flowguard.data import schema as S
from flowguard.pipeline import score

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("FLOWGUARD_DATA", "/mnt/c/Users/vikam/flowguard_data"))
PACKAGE = REPO / "Project" / "flowguard" / "models" / "flowguard_V2_v1"
#: v2 was trained on the untrimmed corpus (benchmark protocol); A4 on the trimmed one.
CORPUS = DATA / "processed" / "benchmark" / "HI-Small_transactions.parquet"
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
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--graph-cache", type=Path,
                        default=CORPUS.parent / "gfp_paper_b1",
                        help="GFP parts extracted over --corpus with the package's params")
    args = parser.parse_args()

    provenance = json.loads((args.package / "PROVENANCE.json").read_text(encoding="utf-8"))
    val_end = pd.Timestamp(provenance["split"]["boundaries"]["val_end"])

    df = pd.read_parquet(args.corpus)
    test = df[df[S.TIMESTAMP] > val_end].sort_values(S.TIMESTAMP, kind="stable")
    # Whole minutes only: scoring selects by timestamp, so a window cut mid-minute
    # would score rows the sample file does not contain (50,263 vs 50,000 once).
    window = test[test[S.TIMESTAMP] <= test[S.TIMESTAMP].iloc[args.rows - 1]]
    OUT.mkdir(parents=True, exist_ok=True)
    # Generated files only: stale bundles from an older package must not sit
    # beside the new ones, where nothing would tell them apart.
    shutil.rmtree(OUT / "cases", ignore_errors=True)
    sample = window[INPUT_COLUMNS].copy()
    sample[S.TIMESTAMP] = sample[S.TIMESTAMP].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    sample.to_csv(OUT / "transactions_sample.csv", index=False)
    print(
        f"input: {len(sample):,} test-period rows, "
        f"{window[S.TIMESTAMP].min()} .. {window[S.TIMESTAMP].max()}",
        flush=True,
    )

    # Score the window WITH its history: every earlier transaction builds the
    # graph and behaviour features, exactly as in training. Scored cold, a
    # 50k-row window alerted on 30.5% of rows against a 1% budget -- every
    # counterparty looked new and every sender dormant. The graph cache is the
    # training-time extraction over this same corpus, so features match exactly.
    summary = score.run(
        args.package, args.corpus, OUT, graph_cache=args.graph_cache,
        n_cases=args.cases,
        emit_from=window[S.TIMESTAMP].min(), emit_until=window[S.TIMESTAMP].max(),
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
