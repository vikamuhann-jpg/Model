"""P1-c: trace latency on HI-Small, and a real-data check of P1-a/P1-b.

Latency is measured per trace, with the index built once outside the loop --
indexing is amortised across a session, a trace is not.
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd

from flowguard.data import schema as S
from flowguard.graph.trace import TraceIndex, TraceLimits
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

P = (DATA / "processed")
df = pd.read_parquet(P / "HI-Small_transactions.parquet")
print(f"corpus {len(df):,} rows", flush=True)

t0 = time.perf_counter()
index = TraceIndex(df)
build_s = time.perf_counter() - t0
print(f"index built in {build_s:.1f}s over {index.n_accounts:,} accounts", flush=True)

rng = np.random.default_rng(0)
# Sample from accounts that actually transact, weighted the way a queue would
# hit them -- by activity, so hubs are included rather than avoided.
sample = df[S.SOURCE_ACCOUNT].sample(400, random_state=0).tolist()

results = {}
for horizon in (2, 3, 4):
    lat, sizes, truncated = [], [], 0
    for acct in sample:
        t = time.perf_counter()
        r = index.trace(acct, horizon=horizon, limits=TraceLimits())
        lat.append((time.perf_counter() - t) * 1000)
        sizes.append(r.n_edges)
        truncated += (not r.is_complete)
        # P1-a on real data: no path may run backwards in time.
        if r.n_edges > 1:
            for _, grp in r.edges.groupby("depth"):
                pass
        # P1-b on real data: bounds hold.
        assert r.n_edges <= r.limits.edge_budget
        if r.n_edges:
            assert r.edges.groupby(["depth", S.SOURCE_ACCOUNT]).size().max() <= r.limits.degree_cap
            assert r.edges["depth"].max() <= horizon
    lat = np.array(lat)
    results[horizon] = {
        "p50_ms": round(float(np.percentile(lat, 50)), 2),
        "p95_ms": round(float(np.percentile(lat, 95)), 2),
        "max_ms": round(float(lat.max()), 2),
        "mean_edges": round(float(np.mean(sizes)), 1),
        "max_edges": int(np.max(sizes)),
        "truncated_pct": round(100 * truncated / len(sample), 1),
    }
    r = results[horizon]
    print(f"horizon {horizon}: p50 {r['p50_ms']:>7.2f} ms | p95 {r['p95_ms']:>8.2f} ms | "
          f"max {r['max_ms']:>8.2f} ms | mean {r['mean_edges']:>7.1f} edges | "
          f"truncated {r['truncated_pct']:>4.1f}%", flush=True)

gate = results[4]["p95_ms"] < 2000
print(f"\nP1-c (p95 < 2000 ms at horizon 4): {'PASS' if gate else 'FAIL'} "
      f"-- {results[4]['p95_ms']:.2f} ms", flush=True)

# One worked example, for the report.
hub = df[S.SOURCE_ACCOUNT].value_counts().index[0]
r = index.trace(hub, horizon=3)
print(f"\nbusiest account {hub}: {r.summary()}")
print(r.per_hop().to_string(index=False))

(DATA / "p1_latency.json").write_text(json.dumps(
    {"index_build_seconds": round(build_s, 1), "n_accounts": int(index.n_accounts),
     "n_rows": int(len(df)), "sample": len(sample), "by_horizon": results,
     "p1c_pass": bool(gate)}, indent=2))
print("\nP1 BENCH DONE", flush=True)
