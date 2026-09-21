"""Why did ETH extraction collapse where HI-Medium did not?

Same code, same 2-day window, similar edges-per-account, 80x throughput gap.
Corpus size does not explain it. Degree skew would: GFP's pattern searches
(scatter-gather, cycles) enumerate over a vertex's neighbours, so a single
hub with enormous degree costs more than thousands of ordinary vertices.
"""
import pandas as pd
from flowguard.data import schema as S
from flowguard.data.loader import load_transactions
from pathlib import Path
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

def profile(name, src, dst):
    deg = pd.concat([src, dst]).value_counts()
    n = len(deg)
    print(f"\n{name}")
    print(f"  vertices          {n:,}")
    print(f"  edges             {len(src):,}")
    print(f"  mean degree       {deg.mean():.2f}")
    print(f"  median degree     {deg.median():.0f}")
    for q in (0.99, 0.999, 0.9999):
        print(f"  p{q*100:<7.2f} degree  {deg.quantile(q):,.0f}")
    print(f"  MAX degree        {deg.max():,}")
    top = deg.head(5).to_numpy()
    print(f"  top-5 degrees     {list(top)}")
    print(f"  share of edge endpoints in top 0.01% of vertices: "
          f"{deg.head(max(1, n//10000)).sum() / deg.sum():.1%}")

P = (DATA / "processed")
lo, hi = (DATA / "eth_slice.txt").read_text().split("|")
eth = pd.read_parquet(P / "ETH_transactions.parquet",
                      columns=[S.TIMESTAMP, S.SOURCE_ACCOUNT, S.DESTINATION_ACCOUNT])
eth = eth[(eth[S.TIMESTAMP] >= pd.Timestamp(lo, tz="UTC"))
          & (eth[S.TIMESTAMP] < pd.Timestamp(hi, tz="UTC"))].head(1_250_000)
profile("ETH phishing slice (1.25M edges)", eth[S.SOURCE_ACCOUNT], eth[S.DESTINATION_ACCOUNT])
del eth

RAW = (REPO / "Dataset_/IBM_Dataset")
med, _ = load_transactions(RAW / "HI-Medium_Trans.csv", nrows=1_250_000)
profile("HI-Medium prefix (1.25M edges)", med[S.SOURCE_ACCOUNT], med[S.DESTINATION_ACCOUNT])
