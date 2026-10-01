"""Two-tier scoring, so the throughput gate can be met (FR-12).

Gate P8 asks for 1,000 tx/s of feature extraction. The graph extractor sustains
~450 tx/s on HI-Small and ~139 tx/s on a real network (ADR-013), the library is
closed, and the cost tracks the tail of the degree distribution. So the gate
cannot be met by running the same thing faster.

It can be met by not running it on everything. The gate was written as though
every transaction needs the full feature set; production fraud systems score
cheaply first and spend the expensive model only on what survives::

    all transactions -> tier 0: row-local features      (~50k tx/s)
                            |
                            +- top K% -> graph features -> final score

**Ranking semantics.** Tier 0 is a recall filter, not a competing opinion, so a
transaction it rejected can never outrank one it accepted. Scores from the two
tiers are not on a common scale and are never mixed arithmetically: selected
rows occupy the top band ordered by their tier-1 score, everything else the
bottom band ordered by tier 0. At any alert budget below K this makes the
cascade's alerts exactly tier 1's alerts, which is the property the recall gate
turns on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_K = 0.05


class CascadeError(ValueError):
    """Raised when a cascade cannot be formed as asked."""


@dataclass(frozen=True)
class CascadeResult:
    """Combined scores plus the arithmetic behind the throughput claim."""

    scores: np.ndarray
    selected: np.ndarray
    k: float
    tier0_rate: float | None = None
    tier1_rate: float | None = None

    @property
    def n_selected(self) -> int:
        return int(self.selected.sum())

    @property
    def end_to_end_rate(self) -> float | None:
        """Throughput of the whole pipeline, transactions per second.

        Every transaction pays tier 0; a ``k`` share also pays tier 1. The
        reciprocals add because the costs are sequential per transaction.
        """
        if self.tier0_rate is None or self.tier1_rate is None:
            return None
        return 1.0 / (1.0 / self.tier0_rate + self.k / self.tier1_rate)

    def summary(self) -> str:
        lines = [
            f"cascade K={self.k:.1%}: {self.n_selected:,} of {len(self.scores):,} "
            f"transactions routed to the graph extractor"
        ]
        if self.end_to_end_rate is not None:
            lines.append(
                f"  tier 0 {self.tier0_rate:,.0f} tx/s | tier 1 "
                f"{self.tier1_rate:,.0f} tx/s | end to end "
                f"{self.end_to_end_rate:,.0f} tx/s"
            )
        return "\n".join(lines)


def select(tier0_scores: np.ndarray, k: float = DEFAULT_K) -> np.ndarray:
    """Boolean mask of the top ``k`` share by tier-0 score."""
    if not 0.0 < k <= 1.0:
        raise CascadeError(f"k must be in (0, 1]; got {k}")
    scores = np.asarray(tier0_scores, dtype=float)
    n_select = max(1, int(round(k * len(scores))))
    mask = np.zeros(len(scores), dtype=bool)
    # argpartition rather than a full sort: the boundary is all that matters.
    mask[np.argpartition(-scores, n_select - 1)[:n_select]] = True
    return mask


def _rank01(values: np.ndarray) -> np.ndarray:
    """Ranks mapped to [0, 1], ties broken by position for determinism."""
    if len(values) == 0:
        return values.astype(float)
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks / max(len(values) - 1, 1)


def combine(
    tier0_scores: np.ndarray,
    tier1_scores: np.ndarray,
    mask: np.ndarray,
    *,
    k: float = DEFAULT_K,
    tier0_rate: float | None = None,
    tier1_rate: float | None = None,
) -> CascadeResult:
    """Fold two tiers into one ranking.

    ``tier1_scores`` is only read where ``mask`` is true; its values elsewhere
    are ignored, so a caller that never computed them may pass anything.
    """
    tier0_scores = np.asarray(tier0_scores, dtype=float)
    tier1_scores = np.asarray(tier1_scores, dtype=float)
    mask = np.asarray(mask, dtype=bool)
    if not (len(tier0_scores) == len(tier1_scores) == len(mask)):
        raise CascadeError("tier scores and mask must be the same length")

    combined = np.empty(len(mask), dtype=float)
    # Bottom band [0, 0.5): rejected by tier 0, ordered by tier 0.
    combined[~mask] = _rank01(tier0_scores[~mask]) * 0.5
    # Top band [0.5, 1]: accepted, ordered by tier 1.
    combined[mask] = 0.5 + _rank01(tier1_scores[mask]) * 0.5
    return CascadeResult(
        scores=combined,
        selected=mask,
        k=k,
        tier0_rate=tier0_rate,
        tier1_rate=tier1_rate,
    )


def cascade(
    tier0_scores: np.ndarray,
    tier1_scores: np.ndarray,
    *,
    k: float = DEFAULT_K,
    tier0_rate: float | None = None,
    tier1_rate: float | None = None,
) -> CascadeResult:
    """Select on tier 0, then rank the survivors by tier 1."""
    mask = select(tier0_scores, k)
    return combine(
        tier0_scores,
        tier1_scores,
        mask,
        k=k,
        tier0_rate=tier0_rate,
        tier1_rate=tier1_rate,
    )
