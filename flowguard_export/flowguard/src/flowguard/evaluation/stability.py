"""Temporal stability and drift (plan v3 section 16.4, gate P7).

Aggregate test performance hides decay. A model that scores well overall while
declining monotonically across the test period has a shelf life, and the report
should say what it is rather than quote one number that was true on average.

Two measurements:

* **Sub-window performance** -- PR-AUC across five equal slices of the test
  period. Gate P7 fails on a monotone decline.
* **Feature drift** -- PSI and KS between train and test distributions, which is
  the leading indicator for why performance would decay.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import Metrics, evaluate

DEFAULT_SUBWINDOWS = 5

#: Conventional PSI reading: <0.1 stable, 0.1-0.25 moderate, >0.25 significant.
PSI_SIGNIFICANT = 0.25


@dataclass
class TemporalStability:
    """PR-AUC across test sub-windows."""

    windows: list[dict] = field(default_factory=list)

    @property
    def scores(self) -> list[float]:
        return [w["pr_auc"] for w in self.windows if np.isfinite(w["pr_auc"])]

    @property
    def is_monotone_decline(self) -> bool:
        s = self.scores
        if len(s) < 3:
            return False
        return all(b <= a for a, b in zip(s, s[1:]))

    def gate_p7(self) -> tuple[bool, str]:
        if len(self.scores) < 3:
            return True, "too few evaluable sub-windows to judge"
        if self.is_monotone_decline:
            return False, (
                f"PR-AUC declines monotonically across sub-windows: "
                f"{' -> '.join(f'{s:.4f}' for s in self.scores)}"
            )
        spread = max(self.scores) - min(self.scores)
        return True, f"no monotone decline; spread {spread:.4f}"

    def to_metadata(self) -> dict:
        ok, detail = self.gate_p7()
        return {
            "windows": self.windows,
            "gate_p7": {"passes": ok, "detail": detail},
            "mean_pr_auc": float(np.mean(self.scores)) if self.scores else float("nan"),
            "sd_pr_auc": (
                float(np.std(self.scores, ddof=1)) if len(self.scores) > 1 else 0.0
            ),
        }

    def summary(self) -> str:
        ok, detail = self.gate_p7()
        lines = [f"temporal stability -- P7 {'PASS' if ok else 'FAIL'}: {detail}"]
        for w in self.windows:
            lines.append(
                f"  {w['start']} .. {w['end']}  n={w['n']:>8,} "
                f"pos={w['positives']:>5,} PR-AUC={w['pr_auc']:.4f}"
            )
        return "\n".join(lines)


def temporal_subwindows(
    test_df: pd.DataFrame, scores: np.ndarray, *, n_windows: int = DEFAULT_SUBWINDOWS
) -> TemporalStability:
    """Evaluate PR-AUC across equal-time slices of the test period."""
    scores = np.asarray(scores, dtype=float)
    ts = test_df[S.TIMESTAMP]
    start, end = ts.min(), ts.max()
    edges = pd.date_range(start, end, periods=n_windows + 1)

    stability = TemporalStability()
    for i in range(n_windows):
        lo, hi = edges[i], edges[i + 1]
        mask = (ts >= lo) & (ts <= hi if i == n_windows - 1 else ts < hi)
        mask = mask.to_numpy()
        if mask.sum() == 0:
            continue
        y = test_df.loc[mask, S.IS_LAUNDERING].to_numpy().astype(int)
        window_metrics: Metrics = evaluate(y, scores[mask])
        stability.windows.append(
            {
                "start": str(lo),
                "end": str(hi),
                "n": int(mask.sum()),
                "positives": int(y.sum()),
                "pr_auc": window_metrics.pr_auc,
                "base_rate": window_metrics.base_rate,
            }
        )
    return stability


def population_stability_index(
    reference: np.ndarray, current: np.ndarray, *, bins: int = 10
) -> float:
    """PSI between two distributions.

    Bin edges come from the reference (training) distribution, since the
    question is how far the new data has moved relative to what was learned.
    """
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)
    reference = reference[np.isfinite(reference)]
    current = current[np.isfinite(current)]
    if len(reference) == 0 or len(current) == 0:
        return float("nan")

    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(reference, quantiles))
    if len(edges) < 3:
        return 0.0  # effectively constant feature
    edges[0], edges[-1] = -np.inf, np.inf

    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    # Laplace-style floor keeps an empty bin from producing an infinite PSI.
    ref_pct = np.clip(ref_counts / ref_counts.sum(), 1e-6, None)
    cur_pct = np.clip(cur_counts / cur_counts.sum(), 1e-6, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def feature_drift(
    X_train: pd.DataFrame, X_test: pd.DataFrame, *, top: int = 20
) -> dict:
    """PSI and KS per feature, ranked by PSI."""
    from scipy.stats import ks_2samp

    rows = []
    for col in X_train.columns:
        if col not in X_test.columns:
            continue
        ref = X_train[col].to_numpy(dtype="float64", na_value=np.nan)
        cur = X_test[col].to_numpy(dtype="float64", na_value=np.nan)
        psi = population_stability_index(ref, cur)
        try:
            ks = float(ks_2samp(ref[np.isfinite(ref)], cur[np.isfinite(cur)]).statistic)
        except Exception:
            ks = float("nan")
        rows.append({"feature": col, "psi": psi, "ks": ks})

    rows.sort(key=lambda r: (-r["psi"] if np.isfinite(r["psi"]) else 0))
    significant = [r for r in rows if np.isfinite(r["psi"]) and r["psi"] > PSI_SIGNIFICANT]

    return {
        "psi_threshold": PSI_SIGNIFICANT,
        "n_features": len(rows),
        "n_significant_drift": len(significant),
        "significant_features": [r["feature"] for r in significant[:top]],
        "top_by_psi": rows[:top],
    }
