"""Computational profiling (plan v3 section 20, gates P8 and P9).

Half the research question is cost. A result that reports only detection
quality has answered half of it -- v3 section 1 is explicit that a feature
improving recall while tripling extraction latency is a trade-off to report, not
a win to claim.

The measurement rule learned the hard way here: **a stateful streaming component
must be profiled at steady state, not at startup.** GFP throughput measured over
the first 20,000 transactions read 17,500 tx/s; by 44% of the corpus it had
fallen to 822 tx/s as the internal graph filled (docs/ADR-006). Any single
headline throughput number for such a component is close to meaningless, so this
module records the curve.
"""

from __future__ import annotations

import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np

#: Gate thresholds, fixed in configs/experiment.yaml before E7 runs.
P8_MIN_THROUGHPUT = 1_000.0  # tx/s, feature extraction
P9_MAX_PEAK_GB = 10.0


def peak_rss_gb() -> float:
    """Peak resident set size of this process, in GB.

    Reads the kernel's own high-water mark rather than sampling, so a spike
    between samples cannot be missed.
    """
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        pass
    return float("nan")


@dataclass
class ThroughputCurve:
    """Throughput sampled across a streaming run."""

    checkpoints: list[tuple[int, float]] = field(default_factory=list)

    def record(self, processed: int, rate: float) -> None:
        self.checkpoints.append((processed, rate))

    @property
    def start_rate(self) -> float:
        return self.checkpoints[0][1] if self.checkpoints else float("nan")

    @property
    def end_rate(self) -> float:
        return self.checkpoints[-1][1] if self.checkpoints else float("nan")

    @property
    def degradation(self) -> float:
        """How many times slower the end is than the start."""
        if not self.checkpoints or self.end_rate == 0:
            return float("nan")
        return self.start_rate / self.end_rate

    @property
    def steady_state_rate(self) -> float:
        """Median rate over the back half -- the honest number to quote."""
        if not self.checkpoints:
            return float("nan")
        back = [r for _, r in self.checkpoints[len(self.checkpoints) // 2:]]
        return float(np.median(back)) if back else float("nan")

    def to_metadata(self) -> dict:
        return {
            "checkpoints": [
                {"processed": p, "tx_per_s": round(r, 1)} for p, r in self.checkpoints
            ],
            "start_tx_per_s": round(self.start_rate, 1),
            "end_tx_per_s": round(self.end_rate, 1),
            "steady_state_tx_per_s": round(self.steady_state_rate, 1),
            "degradation_factor": round(self.degradation, 1),
        }


@dataclass
class CostProfile:
    """The cost block recorded with every experiment."""

    stage: str
    rows: int
    seconds: float
    peak_rss_gb: float
    throughput: ThroughputCurve | None = None

    @property
    def rows_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else float("nan")

    def gate_p8(self) -> tuple[bool, str]:
        """Judged on steady-state throughput, not the startup burst."""
        rate = (
            self.throughput.steady_state_rate
            if self.throughput and self.throughput.checkpoints
            else self.rows_per_second
        )
        ok = bool(rate >= P8_MIN_THROUGHPUT)
        return ok, f"{rate:,.0f} tx/s vs >= {P8_MIN_THROUGHPUT:,.0f} required"

    def gate_p9(self) -> tuple[bool, str]:
        ok = bool(self.peak_rss_gb <= P9_MAX_PEAK_GB)
        return ok, f"{self.peak_rss_gb:.2f} GB vs <= {P9_MAX_PEAK_GB:.0f} GB allowed"

    def to_metadata(self) -> dict:
        p8_ok, p8_detail = self.gate_p8()
        p9_ok, p9_detail = self.gate_p9()
        return {
            "stage": self.stage,
            "rows": self.rows,
            "seconds": round(self.seconds, 2),
            "rows_per_second": round(self.rows_per_second, 1),
            "peak_rss_gb": round(self.peak_rss_gb, 3),
            "gate_p8": {"passes": p8_ok, "detail": p8_detail},
            "gate_p9": {"passes": p9_ok, "detail": p9_detail},
            "throughput_curve": (
                self.throughput.to_metadata() if self.throughput else None
            ),
        }

    def summary(self) -> str:
        p8_ok, p8_detail = self.gate_p8()
        p9_ok, p9_detail = self.gate_p9()
        return "\n".join(
            [
                f"{self.stage}: {self.rows:,} rows in {self.seconds:.1f}s "
                f"({self.rows_per_second:,.0f}/s)",
                f"  P8 {'PASS' if p8_ok else 'FAIL'}: {p8_detail}",
                f"  P9 {'PASS' if p9_ok else 'FAIL'}: {p9_detail}",
            ]
        )


@contextmanager
def profile(stage: str, rows: int):
    """Time a stage and capture its peak memory.

    Yields a mutable holder; the populated :class:`CostProfile` is at
    ``holder["profile"]`` once the block exits.
    """
    holder: dict = {}
    started = time.perf_counter()
    try:
        yield holder
    finally:
        holder["profile"] = CostProfile(
            stage=stage,
            rows=rows,
            seconds=time.perf_counter() - started,
            peak_rss_gb=peak_rss_gb(),
            throughput=holder.get("throughput"),
        )


def inference_latency(
    model, X, *, repeats: int = 5, batch: int = 1
) -> dict:
    """Per-transaction scoring latency.

    Single-row batches are the honest measure for a system that scores payments
    as they arrive; a large batch amortises overhead a real-time path cannot.
    """
    sample = X.iloc[:batch]
    timings = []
    for _ in range(repeats):
        started = time.perf_counter()
        model.predict(sample)
        timings.append((time.perf_counter() - started) * 1000.0)

    return {
        "batch_size": batch,
        "repeats": repeats,
        "median_ms": float(np.median(timings)),
        "p95_ms": float(np.percentile(timings, 95)),
        "min_ms": float(np.min(timings)),
    }
