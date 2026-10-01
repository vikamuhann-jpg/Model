"""Extraction throughput with the corrected extractor, with and without periodic
graph reconstruction (WINNING_PLAN P2; ADR-015 overturned ADR-008).

    python p2_speed.py [rows] [rebuild_every]

Streams the first ``rows`` HI-Small transactions (chronological, untrimmed corpus)
through GFP at batch_size=1 with the GFP paper's parameters, once continuously and
once rebuilding the preprocessor every ``rebuild_every`` transactions. Reports
steady-state throughput for both and checks the two feature blocks are identical --
the full-scale version of test_reconstruction_is_feature_identical.
"""

from __future__ import annotations

import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

from _paths import DATA
from flowguard.data import schema as S
from flowguard.features.gfp import GFPFeatures
from flowguard.pipeline.run_benchmark import PAPER_GFP_PARAMS

rows = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
rebuild_every = int(sys.argv[2]) if len(sys.argv) > 2 else 100_000

df = pd.read_parquet(DATA / "processed" / "benchmark" / "HI-Small_transactions.parquet")
view = S.feature_view(df.sort_values(S.TIMESTAMP, kind="stable").head(rows))
print(f"{len(view):,} rows, batch_size=1, paper params", flush=True)

results, blocks = {}, {}
for name, every in (("continuous", 0), (f"rebuild_{rebuild_every}", rebuild_every)):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gfp = GFPFeatures(params=dict(PAPER_GFP_PARAMS), rebuild_every=every,
                          progress_every=250_000)
    started = time.perf_counter()
    blocks[name] = gfp.run_streaming(view)
    seconds = time.perf_counter() - started
    results[name] = {"seconds": round(seconds, 1), "tx_per_s": round(len(view) / seconds),
                     "rebuilds": gfp.n_rebuilds_,
                     "rebuild_seconds": round(gfp.rebuild_seconds_, 1)}
    print(name, results[name], flush=True)

a, b = (blocks[k].to_numpy() for k in blocks)
results["identical"] = bool(np.array_equal(a, b, equal_nan=True))
results["max_abs_diff"] = float(np.nanmax(np.abs(a - b))) if a.size else 0.0
results["rows"] = len(view)
print(json.dumps(results, indent=2))
(DATA / "runs" / f"P2_speed_{rows}.json").write_text(json.dumps(results, indent=2))
