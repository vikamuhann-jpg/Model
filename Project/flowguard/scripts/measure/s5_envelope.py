"""S5 -- measure the scaling envelope instead of assuming it.

Extraction throughput decays as the graph fills (ADR-006) and reconstruction was
rejected as unsound (ADR-008), so the cost is a property of the method. One
streaming pass over an HI-Medium prefix; run_streaming already reports the
cumulative rate every 250k rows, so the curve comes out of a single pass rather
than re-extracting every prefix (which is what stalled the first attempt).
"""
import io, json, re, sys, time
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd

from flowguard.data import schema as S
from flowguard.data.loader import load_transactions
from flowguard.evaluation.profiling import peak_rss_gb
from flowguard.features.gfp import DAY, DEFAULT_GFP_PARAMS, GFPFeatures
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

RAW = (REPO / "Dataset_/IBM_Dataset")
OUT = (DATA / "scaling_envelope.json")
SAMPLE_ROWS = 4_000_000
FULL_MEDIUM = 31_970_000

params = dict(DEFAULT_GFP_PARAMS)
window = int(2 * DAY)
params["time_window"] = window
for k in ("vertex_stats_tw", "scatter-gather_tw", "temp-cycle_tw", "lc-cycle_tw"):
    params[k] = min(params[k], window)

print(f"loading a contiguous {SAMPLE_ROWS:,}-row prefix of HI-Medium", flush=True)
t0 = time.perf_counter()
df, _ = load_transactions(RAW / "HI-Medium_Trans.csv", nrows=SAMPLE_ROWS)
n_accounts = len(set(df[S.SOURCE_ACCOUNT]) | set(df[S.DESTINATION_ACCOUNT]))
print(f"  loaded in {time.perf_counter()-t0:.0f}s | accounts {n_accounts:,}", flush=True)

view = S.feature_view(df).sort_values(S.TIMESTAMP, kind="stable")
del df

# Tee run_streaming's progress lines: they carry the cumulative throughput.
class Tee(io.StringIO):
    def write(self, s):
        sys.__stdout__.write(s); sys.__stdout__.flush()
        return super().write(s)

tee = Tee()
started = time.perf_counter()
with redirect_stdout(tee):
    GFPFeatures(params=params, progress_every=250_000,
                chunk_dir=(DATA / "s5_parts")
                ).run_streaming(view)
total_s = time.perf_counter() - started

PAT = re.compile(r"^\s*([\d,]+)/[\d,]+\s+\([\d.]+%\)\s+([\d,]+) tx/s")
checkpoints = [
    {"rows": int(m.group(1).replace(",", "")),
     "tx_per_s": float(m.group(2).replace(",", ""))}
    for line in tee.getvalue().splitlines() if (m := PAT.match(line))
]
last = checkpoints[-1]
result = {
    "variant": "HI-Medium (contiguous prefix)",
    "rows_processed": len(view),
    "accounts": n_accounts,
    "wall_seconds": round(total_s, 1),
    "checkpoints": checkpoints,
    # Cumulative rate at the end -- the honest figure for "how long would N take",
    # and already degraded relative to the early instantaneous rate.
    "end_to_end_tx_per_s": round(len(view) / total_s, 1),
    "peak_rss_gb": round(peak_rss_gb(), 2),
    "full_variant_rows": FULL_MEDIUM,
    "projected_hours_for_full_variant": round(
        (FULL_MEDIUM / (len(view) / total_s)) / 3600, 1),
    "projection_is_a_floor": True,
    "projection_note": (
        "Throughput decays monotonically as the graph fills, so extrapolating at "
        "the rate measured on a 4M prefix understates the cost of 32M. The figure "
        "is a lower bound on the time, not an estimate."
    ),
    "p8_threshold_tx_per_s": 1000,
    "p8_passes_at_this_scale": bool(len(view) / total_s >= 1000),
}
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(f"\nend-to-end {result['end_to_end_tx_per_s']:,.0f} tx/s over {len(view):,} rows")
print(f"peak RSS {result['peak_rss_gb']:.2f} GB")
print(f"projected floor for full HI-Medium (32M): "
      f"{result['projected_hours_for_full_variant']:.1f} hours")
print(f"P8 (>=1,000 tx/s): {'PASS' if result['p8_passes_at_this_scale'] else 'FAIL'}")
print(f"wrote {OUT}")
print("S5 DONE", flush=True)
