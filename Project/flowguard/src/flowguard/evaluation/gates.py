"""Validation gates C1-C8 and P1-P9 (plan v3 section 26).

The terminus of the plan. Gates are defined **before** results exist — a gate
chosen after seeing the numbers is not a gate — and the thresholds live in
`configs/experiment.yaml`.

The two categories are not equivalent:

* **Correctness (C)** — a failure *voids the result*. No amount of good
  performance compensates.
* **Performance (P)** — a failure is a **finding to report**, not something to
  hide. v3 says P3 in particular may legitimately come out inconclusive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GateKind(str, Enum):
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    NOT_RUN = "not_run"


@dataclass
class GateResult:
    gate_id: str
    kind: GateKind
    description: str
    status: GateStatus
    detail: str = ""
    measured: float | None = None
    threshold: float | None = None

    @property
    def blocking(self) -> bool:
        """Correctness failures void the result; performance failures do not."""
        return self.kind is GateKind.CORRECTNESS and self.status is GateStatus.FAIL

    def to_metadata(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "kind": self.kind.value,
            "description": self.description,
            "status": self.status.value,
            "detail": self.detail,
            "measured": self.measured,
            "threshold": self.threshold,
        }


@dataclass
class GateReport:
    results: list[GateResult] = field(default_factory=list)

    def add(self, result: GateResult) -> None:
        self.results.append(result)

    @property
    def correctness(self) -> list[GateResult]:
        return [r for r in self.results if r.kind is GateKind.CORRECTNESS]

    @property
    def performance(self) -> list[GateResult]:
        return [r for r in self.results if r.kind is GateKind.PERFORMANCE]

    @property
    def voided(self) -> bool:
        """True if any correctness gate failed."""
        return any(r.blocking for r in self.results)

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in GateStatus}
        for r in self.results:
            out[r.status.value] += 1
        return out

    def to_metadata(self) -> dict:
        return {
            "voided": self.voided,
            "counts": self.counts(),
            "correctness": [r.to_metadata() for r in self.correctness],
            "performance": [r.to_metadata() for r in self.performance],
        }

    def summary(self) -> str:
        icon = {
            GateStatus.PASS: "PASS",
            GateStatus.FAIL: "FAIL",
            GateStatus.INCONCLUSIVE: "INCONC",
            GateStatus.NOT_RUN: "SKIP",
        }
        lines = ["CORRECTNESS GATES (a failure voids the result)"]
        for r in self.correctness:
            lines.append(f"  [{icon[r.status]:6s}] {r.gate_id}  {r.description}")
            if r.detail:
                lines.append(f"            {r.detail}")
        lines.append("")
        lines.append("PERFORMANCE GATES (a failure is a finding, not a defect)")
        for r in self.performance:
            lines.append(f"  [{icon[r.status]:6s}] {r.gate_id}  {r.description}")
            if r.detail:
                lines.append(f"            {r.detail}")
        lines.append("")
        lines.append(
            "RESULT VOIDED -- a correctness gate failed"
            if self.voided
            else "Correctness gates all pass; result stands."
        )
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Table form for `validation_report.md`."""
        lines = [
            "## Correctness gates",
            "",
            "A failure here voids the result regardless of performance.",
            "",
            "| Gate | Check | Status | Detail |",
            "|---|---|---|---|",
        ]
        for r in self.correctness:
            lines.append(
                f"| {r.gate_id} | {r.description} | "
                f"**{r.status.value.upper()}** | {r.detail or '—'} |"
            )
        lines += [
            "",
            "## Performance gates",
            "",
            "A missed performance gate is a finding to report, not a defect to hide.",
            "",
            "| Gate | Target | Status | Measured |",
            "|---|---|---|---|",
        ]
        for r in self.performance:
            lines.append(
                f"| {r.gate_id} | {r.description} | "
                f"**{r.status.value.upper()}** | {r.detail or '—'} |"
            )
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Gate definitions
# --------------------------------------------------------------------------

C_GATES = {
    "C1": "Leakage suite passes",
    "C2": "Shuffled-label PR-AUC within 2x base rate",
    "C3": "Random-score PR-AUC at base rate",
    "C4": "Split boundary timestamps strictly ordered and recorded",
    "C5": "Training and inference feature schemas identical",
    "C6": "One command reproduces the headline PR-AUC",
    "C7": "Same seed and data produce identical predictions",
    "C8": "No single feature above 50% of mean |SHAP|",
}

P_GATES = {
    "P1": "E2 beats E1 by > 2 sigma",
    "P2": "E1 beats E0 by > 2 sigma",
    "P3": "E7 beats E2 by > 2 sigma (or inconclusive)",
    "P4": "Recall at 1% alert budget",
    "P5": "No typology at zero recall",
    "P6": "PR-AUC standard deviation across seeds",
    "P7": "No monotone decline across test sub-windows",
    "P8": "Feature extraction throughput",
    "P9": "Peak resident memory",
}


def correctness(gate_id: str, status: GateStatus, detail: str = "") -> GateResult:
    return GateResult(
        gate_id=gate_id,
        kind=GateKind.CORRECTNESS,
        description=C_GATES[gate_id],
        status=status,
        detail=detail,
    )


def performance(
    gate_id: str,
    status: GateStatus,
    detail: str = "",
    measured: float | None = None,
    threshold: float | None = None,
) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        kind=GateKind.PERFORMANCE,
        description=P_GATES[gate_id],
        status=status,
        detail=detail,
        measured=measured,
        threshold=threshold,
    )


def two_sigma_verdict(
    delta: float, sigma: float, *, allow_inconclusive: bool = False
) -> tuple[GateStatus, str]:
    """Judge a difference against the 2-sigma inclusion criterion (v3 s21).

    Replaces "measurable improvement" with something testable.
    """
    bar = 2 * sigma
    if delta > bar:
        return GateStatus.PASS, f"delta {delta:+.4f} > 2 sigma ({bar:.4f})"
    if allow_inconclusive and abs(delta) <= bar:
        return GateStatus.INCONCLUSIVE, (
            f"delta {delta:+.4f} within 2 sigma ({bar:.4f}) -- no measurable effect"
        )
    return GateStatus.FAIL, f"delta {delta:+.4f} does not exceed 2 sigma ({bar:.4f})"
