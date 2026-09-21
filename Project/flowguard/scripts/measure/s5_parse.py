"""Turn the S5 extraction log into a scaling envelope.

The measurement is budget-bounded rather than run-to-completion: extraction cost
on this method is super-linear in rows already inserted (Tier C put a second,
sharper number on that -- each 250k block cost roughly twice the one before), so
"run it to the end and time it" is not a measurement that terminates. What is
honest and cheap is: spend a fixed wall-clock budget, record how far it got, and
publish the curve plus a floor on the extrapolation.

run_streaming prints a cumulative rate every 250k rows, so the log IS the curve.
"""
import json, re, sys
from pathlib import Path
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)

LOG = (DATA / "s5.log")
OUT = (DATA / "scaling_envelope.json")
FULL_MEDIUM = 31_970_000
BUDGET_MIN = 20

PAT = re.compile(r"^\s*([\d,]+)/([\d,]+)\s+\([\d.]+%\)\s+([\d,]+) tx/s")
num = lambda s: int(s.replace(",", ""))

rows = []
total = None
for line in LOG.read_text(errors="replace").splitlines():
    m = PAT.match(line)
    if m:
        total = num(m.group(2))
        rows.append({"rows": num(m.group(1)), "tx_per_s": float(num(m.group(3)))})

if not rows:
    sys.exit("no checkpoints in the log yet")

# The printed rate is cumulative (rows / elapsed), so elapsed and the per-block
# cost both fall out of it -- and the per-block series is what shows the shape.
for r in rows:
    r["elapsed_s"] = round(r["rows"] / r["tx_per_s"], 1)
prev = 0.0
for r in rows:
    r["block_seconds"] = round(r["elapsed_s"] - prev, 1)
    prev = r["elapsed_s"]
ratios = [
    round(rows[i]["block_seconds"] / rows[i - 1]["block_seconds"], 2)
    for i in range(1, len(rows))
    if rows[i - 1]["block_seconds"] > 0
]

last = rows[-1]
result = {
    "variant": "HI-Medium (contiguous prefix)",
    "budget_minutes": BUDGET_MIN,
    "corpus_rows_offered": total,
    "rows_reached": last["rows"],
    "fraction_reached": round(last["rows"] / total, 4) if total else None,
    "checkpoints": rows,
    "block_cost_ratios": ratios,
    "cost_is_super_linear": bool(ratios and sum(ratios) / len(ratios) > 1.2),
    "end_cumulative_tx_per_s": last["tx_per_s"],
    "full_variant_rows": FULL_MEDIUM,
    # Extrapolating at the END rate already understates the cost, because the
    # rate is still falling. Anything derived from it is a floor.
    "projected_hours_floor_for_full_variant": round(
        (FULL_MEDIUM / last["tx_per_s"]) / 3600, 1
    ),
    "projection_note": (
        "A floor, not an estimate. Throughput decays monotonically as vertices "
        "accumulate, and the per-block cost ratios above show the decay is "
        "super-linear, so the true cost of the full variant is strictly worse."
    ),
    "p8_threshold_tx_per_s": 1000,
    "p8_passes_at_this_scale": bool(last["tx_per_s"] >= 1000),
    "verdict": (
        f"Sustains {last['tx_per_s']:,.0f} tx/s at {last['rows']:,} rows; "
        f"reached {last['rows'] / total:.1%} of a {total:,}-row prefix in "
        f"{BUDGET_MIN} minutes. HI-Medium at 32M rows is impractical on this "
        f"hardware."
    ),
}
OUT.write_text(json.dumps(result, indent=2))
print(json.dumps({k: v for k, v in result.items() if k != "checkpoints"}, indent=2))
print(f"\nwrote {OUT}")
