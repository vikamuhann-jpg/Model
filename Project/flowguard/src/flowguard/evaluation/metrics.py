"""Evaluation metrics (plan v3 Phase 10).

Every experiment is scored through this module. Sharing one implementation is
what makes E0…E7 comparable at all -- a second scoring path is a second set of
conventions, and the comparison silently stops meaning anything.

PR-AUC is the headline. Accuracy is deliberately absent: at a 0.102% base rate
a model predicting "never" scores 99.9%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
)

#: Alert budgets to report at. A budget is the fraction of transactions an
#: investigation team can actually review -- the operational currency of a
#: detection system, and more meaningful than an arbitrary 0.5 cutoff.
DEFAULT_BUDGETS: tuple[float, ...] = (0.001, 0.005, 0.01, 0.05)


@dataclass(frozen=True)
class BudgetPoint:
    """Performance at one alert budget."""

    budget: float
    threshold: float
    alerts: int
    true_positives: int
    precision: float
    recall: float

    def to_metadata(self) -> dict:
        return {
            "budget": self.budget,
            "threshold": float(self.threshold),
            "alerts": self.alerts,
            "true_positives": self.true_positives,
            "precision": self.precision,
            "recall": self.recall,
        }


@dataclass(frozen=True)
class Metrics:
    """The full metric block recorded for every experiment."""

    n: int
    positives: int
    base_rate: float
    pr_auc: float
    roc_auc: float
    best_f1: float
    best_f1_threshold: float
    budgets: list[BudgetPoint] = field(default_factory=list)

    @property
    def lift(self) -> float:
        """PR-AUC relative to the base rate -- how much better than guessing."""
        return self.pr_auc / self.base_rate if self.base_rate else float("nan")

    def at_budget(self, budget: float) -> BudgetPoint | None:
        for point in self.budgets:
            if point.budget == budget:
                return point
        return None

    def to_metadata(self) -> dict:
        return {
            "n": self.n,
            "positives": self.positives,
            "base_rate": self.base_rate,
            "pr_auc": self.pr_auc,
            "roc_auc": self.roc_auc,
            "lift_over_base_rate": self.lift,
            "best_f1": self.best_f1,
            "best_f1_threshold": float(self.best_f1_threshold),
            "budgets": [b.to_metadata() for b in self.budgets],
        }

    def summary(self) -> str:
        lines = [
            f"  n={self.n:,}  positives={self.positives:,}  "
            f"base_rate={self.base_rate:.5%}",
            f"  PR-AUC={self.pr_auc:.4f}  (lift {self.lift:.1f}x)  "
            f"ROC-AUC={self.roc_auc:.4f}  best-F1={self.best_f1:.4f}",
        ]
        for point in self.budgets:
            lines.append(
                f"  @{point.budget:>6.1%} budget: "
                f"precision={point.precision:.4f} recall={point.recall:.4f} "
                f"({point.true_positives}/{point.alerts} alerts)"
            )
        return "\n".join(lines)


def _budget_point(
    y_true: np.ndarray, scores: np.ndarray, budget: float
) -> BudgetPoint:
    """Score the top ``budget`` fraction of transactions by model score."""
    n = len(scores)
    k = max(1, int(round(n * budget)))
    # argpartition is O(n) and enough -- we only need the top-k set.
    top = np.argpartition(-scores, kth=k - 1)[:k]
    threshold = float(scores[top].min())
    tp = int(y_true[top].sum())
    positives = int(y_true.sum())
    return BudgetPoint(
        budget=budget,
        threshold=threshold,
        alerts=k,
        true_positives=tp,
        precision=tp / k if k else 0.0,
        recall=tp / positives if positives else 0.0,
    )


def evaluate(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    budgets: tuple[float, ...] = DEFAULT_BUDGETS,
) -> Metrics:
    """Score predictions. ``scores`` may be probabilities or raw rankings."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)

    if len(y_true) != len(scores):
        raise ValueError(f"length mismatch: {len(y_true)} labels, {len(scores)} scores")

    positives = int(y_true.sum())
    n = len(y_true)
    base_rate = positives / n if n else 0.0

    if positives == 0 or positives == n:
        # Degenerate -- report rather than raise, so sanity baselines still log.
        return Metrics(
            n=n,
            positives=positives,
            base_rate=base_rate,
            pr_auc=float("nan"),
            roc_auc=float("nan"),
            best_f1=float("nan"),
            best_f1_threshold=float("nan"),
            budgets=[],
        )

    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.where(
            (precision + recall) > 0, 2 * precision * recall / (precision + recall), 0.0
        )
    best = int(np.nanargmax(f1))
    # precision_recall_curve returns one more point than thresholds.
    best_threshold = float(thresholds[min(best, len(thresholds) - 1)])

    return Metrics(
        n=n,
        positives=positives,
        base_rate=base_rate,
        pr_auc=float(average_precision_score(y_true, scores)),
        roc_auc=float(roc_auc_score(y_true, scores)),
        best_f1=float(f1[best]),
        best_f1_threshold=best_threshold,
        budgets=[_budget_point(y_true, scores, b) for b in budgets],
    )


def per_group_recall(
    y_true: np.ndarray, scores: np.ndarray, groups: np.ndarray, budget: float
) -> dict[str, dict]:
    """Recall per typology at a fixed budget (gate P5: no typology at zero recall)."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    # pandas NA does not compare cleanly inside numpy object arrays -- it yields
    # NA rather than False and then raises "truth value is ambiguous". Unlabelled
    # rows become empty strings, which compare normally and are skipped below.
    groups = pd.Series(groups).astype("object").where(pd.notna(groups), "").to_numpy()

    n = len(scores)
    k = max(1, int(round(n * budget)))
    top = np.argpartition(-scores, kth=k - 1)[:k]
    flagged = np.zeros(n, dtype=bool)
    flagged[top] = True

    out: dict[str, dict] = {}
    for group in sorted({g for g in groups if isinstance(g, str)}):
        mask = (groups == group) & (y_true == 1)
        total = int(mask.sum())
        if not total:
            continue
        caught = int((mask & flagged).sum())
        out[group] = {
            "positives": total,
            "caught": caught,
            "recall": caught / total,
        }
    return out
