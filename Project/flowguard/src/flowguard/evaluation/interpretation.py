"""SHAP interpretation, used as a leakage detector (plan v3 section 19).

SHAP is **not** in scope here as a compliance explanation feature. Its job is to
tell you whether the model learned something real.

Gate C8: no single feature may carry more than 50% of mean absolute SHAP. A
feature that dominates that heavily is usually not a triumph but a warning --
either it encodes the label, or the problem is trivial, or an artifact is doing
the work. That is exactly how the `day_of_week` tail artifact was caught
(docs/ADR-003), and a dominance check would have caught it a second way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: Gate C8 ceiling: share of mean |SHAP| a single feature may hold.
DOMINANCE_CEILING = 0.50

#: SHAP over millions of rows is pointless and slow; a sample is sufficient for
#: a stable global ranking.
DEFAULT_SAMPLE = 20_000


@dataclass
class Interpretation:
    """Global SHAP summary plus the C8 verdict."""

    mean_abs_shap: dict[str, float]
    top_feature: str
    top_share: float
    passes_c8: bool
    n_sampled: int
    family_shares: dict[str, float] = field(default_factory=dict)

    def ranked(self, top: int = 20) -> list[tuple[str, float]]:
        return sorted(self.mean_abs_shap.items(), key=lambda kv: kv[1], reverse=True)[:top]

    def to_metadata(self) -> dict:
        return {
            "n_sampled": self.n_sampled,
            "top_feature": self.top_feature,
            "top_share_of_mean_abs_shap": self.top_share,
            "c8_ceiling": DOMINANCE_CEILING,
            "passes_c8": self.passes_c8,
            "family_shares": self.family_shares,
            "mean_abs_shap": dict(self.ranked(50)),
        }

    def summary(self) -> str:
        lines = [
            f"SHAP over {self.n_sampled:,} sampled rows",
            f"  top feature: {self.top_feature} at {self.top_share:.1%} of mean |SHAP|",
            f"  gate C8 (<{DOMINANCE_CEILING:.0%}): "
            f"{'PASS' if self.passes_c8 else 'FAIL'}",
        ]
        if self.family_shares:
            lines.append("  share by family:")
            for family, share in sorted(
                self.family_shares.items(), key=lambda kv: kv[1], reverse=True
            ):
                lines.append(f"    {family:10s} {share:6.1%}")
        lines.append("  top features:")
        for name, value in self.ranked(12):
            total = sum(self.mean_abs_shap.values()) or 1.0
            lines.append(f"    {name:32s} {value / total:6.1%}")
        return "\n".join(lines)


def _family_of(column: str) -> str:
    """Feature families are encoded as a name prefix (`gfp_`, `tx_`, ...)."""
    return column.split("_", 1)[0] if "_" in column else column


def explain(
    model,
    X: pd.DataFrame,
    *,
    sample: int = DEFAULT_SAMPLE,
    seed: int = 42,
) -> Interpretation:
    """Compute global SHAP importance and evaluate gate C8."""
    import shap

    rng = np.random.default_rng(seed)
    if len(X) > sample:
        idx = rng.choice(len(X), size=sample, replace=False)
        X_sample = X.iloc[np.sort(idx)]
    else:
        X_sample = X

    booster = model.booster_ if hasattr(model, "booster_") else model
    # TreeExplainer on CPU: the GPU path needs the frame resident on device and
    # this is a one-off diagnostic, not a hot loop.
    if hasattr(booster, "set_param"):
        booster.set_param({"device": "cpu"})

    explainer = shap.TreeExplainer(booster)
    values = explainer.shap_values(X_sample)
    if isinstance(values, list):  # older SHAP returns per-class lists
        values = values[-1]

    mean_abs = np.abs(values).mean(axis=0)
    total = float(mean_abs.sum()) or 1.0
    mean_abs_shap = {
        col: float(v) for col, v in zip(X_sample.columns, mean_abs)
    }

    top_feature = max(mean_abs_shap, key=lambda k: mean_abs_shap[k])
    top_share = mean_abs_shap[top_feature] / total

    families: dict[str, float] = {}
    for col, value in mean_abs_shap.items():
        families[_family_of(col)] = families.get(_family_of(col), 0.0) + value / total

    return Interpretation(
        mean_abs_shap=mean_abs_shap,
        top_feature=top_feature,
        top_share=top_share,
        passes_c8=bool(top_share < DOMINANCE_CEILING),
        n_sampled=len(X_sample),
        family_shares=families,
    )


def stability_across_seeds(
    interpretations: list[Interpretation], top: int = 10
) -> dict:
    """How consistent the top-N feature ranking is across seeds (v3 section 19.4).

    Unstable importance makes any narrative built on it unreliable -- "the graph
    features mattered" means little if a different seed promotes a different ten.
    """
    if not interpretations:
        return {}

    rankings = [[name for name, _ in i.ranked(top)] for i in interpretations]
    first = set(rankings[0])
    overlaps = [len(first & set(r)) / top for r in rankings[1:]]

    counts: dict[str, int] = {}
    for ranking in rankings:
        for name in ranking:
            counts[name] = counts.get(name, 0) + 1

    return {
        "n_runs": len(interpretations),
        "top_n": top,
        "mean_overlap_with_first": float(np.mean(overlaps)) if overlaps else 1.0,
        "always_present": sorted(
            name for name, c in counts.items() if c == len(rankings)
        ),
        "appearance_counts": dict(
            sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        ),
    }
