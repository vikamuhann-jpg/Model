"""Operating thresholds with recorded provenance (plan v3 section 15.4).

A threshold is only meaningful alongside two facts: the alert budget it was
chosen for, and the partition it was chosen on. Both are carried on the object
rather than remembered, because plan v3 section 11 makes "thresholds selected on
validation only" a rule that a test has to be able to check.

Selecting on test is the classic way to report a number nobody can reproduce:
the threshold is fitted to the very data it is then evaluated on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class ThresholdSource(str, Enum):
    """Which partition a threshold was chosen on."""

    VALIDATION = "validation"
    TRAIN = "train"
    TEST = "test"  # never legitimate for a reported result


@dataclass(frozen=True)
class Threshold:
    """One operating point."""

    budget: float
    value: float
    source: ThresholdSource
    #: Metrics observed on the partition the threshold was selected on.
    selection_precision: float
    selection_recall: float
    selection_alerts: int

    def apply(self, scores: np.ndarray) -> np.ndarray:
        """Boolean alert mask for ``scores`` at this threshold."""
        return np.asarray(scores, dtype=float) >= self.value

    def to_metadata(self) -> dict:
        return {
            "budget": self.budget,
            "value": float(self.value),
            "source": self.source.value,
            "selection_precision": self.selection_precision,
            "selection_recall": self.selection_recall,
            "selection_alerts": self.selection_alerts,
        }


@dataclass
class ThresholdSet:
    """Thresholds at several budgets, all from one partition."""

    source: ThresholdSource
    thresholds: dict[float, Threshold] = field(default_factory=dict)

    def __getitem__(self, budget: float) -> Threshold:
        return self.thresholds[budget]

    @property
    def budgets(self) -> list[float]:
        return sorted(self.thresholds)

    def to_metadata(self) -> dict:
        return {
            "source": self.source.value,
            "thresholds": {
                str(b): t.to_metadata() for b, t in sorted(self.thresholds.items())
            },
        }


def select_thresholds(
    y: np.ndarray,
    scores: np.ndarray,
    budgets: tuple[float, ...],
    *,
    source: ThresholdSource = ThresholdSource.VALIDATION,
) -> ThresholdSet:
    """Choose a score cutoff per alert budget.

    An alert budget is the fraction of transactions an investigation team can
    review. Expressing thresholds this way rather than as a fixed probability is
    how detection systems are actually operated -- capacity is the constraint,
    not a belief about calibrated probability.
    """
    y = np.asarray(y).astype(int)
    scores = np.asarray(scores, dtype=float)
    if len(y) != len(scores):
        raise ValueError(f"length mismatch: {len(y)} labels, {len(scores)} scores")

    if source is ThresholdSource.TEST:
        raise ValueError(
            "refusing to select thresholds on the test partition: the threshold "
            "would be fitted to the data it is then evaluated on (v3 s11)"
        )

    positives = int(y.sum())
    n = len(scores)
    out = ThresholdSet(source=source)

    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    sorted_y = y[order]
    cumulative_tp = np.cumsum(sorted_y)

    for budget in budgets:
        k = max(1, int(round(n * budget)))
        k = min(k, n)
        tp = int(cumulative_tp[k - 1])
        out.thresholds[budget] = Threshold(
            budget=budget,
            value=float(sorted_scores[k - 1]),
            source=source,
            selection_precision=tp / k,
            selection_recall=tp / positives if positives else 0.0,
            selection_alerts=k,
        )
    return out
