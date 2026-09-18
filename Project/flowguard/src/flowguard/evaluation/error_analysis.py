"""Error analysis and slice performance (plan v3 Phase 11).

This module exists to gate the feature work. Plan v3 section 17.2 is explicit:
features designed before the error analysis exists are guesses. The point is to
find out *where* the model fails before deciding what to build next, so that
E3..E7 target measured failures rather than intuitions.

Aggregate metrics hide systematic blind spots -- a model can post a respectable
PR-AUC while missing every small-amount transaction or every pattern that spans
more than three hops.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S


def flag_at_budget(scores: np.ndarray, budget: float) -> np.ndarray:
    """Boolean mask for the top ``budget`` fraction by score."""
    scores = np.asarray(scores, dtype=float)
    n = len(scores)
    k = max(1, int(round(n * budget)))
    top = np.argpartition(-scores, kth=k - 1)[:k]
    flagged = np.zeros(n, dtype=bool)
    flagged[top] = True
    return flagged


@dataclass
class ErrorAnalysis:
    """False positives and negatives at a fixed alert budget."""

    budget: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    slices: dict[str, pd.DataFrame] = field(default_factory=dict)
    fn_profile: dict = field(default_factory=dict)
    fp_profile: dict = field(default_factory=dict)

    def to_metadata(self) -> dict:
        return {
            "budget": self.budget,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "slices": {
                name: frame.to_dict(orient="index")
                for name, frame in self.slices.items()
            },
            "false_negative_profile": self.fn_profile,
            "false_positive_profile": self.fp_profile,
        }

    def summary(self) -> str:
        lines = [
            f"at {self.budget:.1%} alert budget:",
            f"  TP={self.true_positives:,}  FP={self.false_positives:,}  "
            f"FN={self.false_negatives:,}  TN={self.true_negatives:,}",
        ]
        for name, frame in self.slices.items():
            lines.append(f"\n  recall by {name}:")
            for key, row in frame.iterrows():
                lines.append(
                    f"    {str(key):22s} {row['recall']:6.1%} "
                    f"({int(row['caught'])}/{int(row['positives'])})"
                )
        return "\n".join(lines)


def _recall_by(
    df: pd.DataFrame, keys: pd.Series, flagged: np.ndarray
) -> pd.DataFrame:
    positive = df[S.IS_LAUNDERING].to_numpy() == 1
    frame = pd.DataFrame(
        {"key": keys.to_numpy(), "positive": positive, "flagged": flagged}
    )
    grouped = frame[frame["positive"]].groupby("key", observed=True)["flagged"].agg(
        ["size", "sum"]
    )
    grouped.columns = ["positives", "caught"]
    grouped["recall"] = grouped["caught"] / grouped["positives"]
    return grouped.sort_values("recall")


def analyse(
    test_df: pd.DataFrame,
    scores: np.ndarray,
    *,
    budget: float = 0.01,
    amount_bins: int = 5,
) -> ErrorAnalysis:
    """Categorise errors and measure recall across slices."""
    flagged = flag_at_budget(scores, budget)
    positive = test_df[S.IS_LAUNDERING].to_numpy() == 1

    analysis = ErrorAnalysis(
        budget=budget,
        true_positives=int((flagged & positive).sum()),
        false_positives=int((flagged & ~positive).sum()),
        false_negatives=int((~flagged & positive).sum()),
        true_negatives=int((~flagged & ~positive).sum()),
    )

    # --- slice: typology -------------------------------------------------
    if S.PATTERN_TYPE in test_df.columns:
        typology = test_df[S.PATTERN_TYPE].fillna("(unannotated)")
        analysis.slices["typology"] = _recall_by(test_df, typology, flagged)

    # --- slice: amount magnitude ----------------------------------------
    amounts = test_df[S.AMOUNT]
    try:
        bands = pd.qcut(amounts, amount_bins, duplicates="drop")
        analysis.slices["amount_band"] = _recall_by(
            test_df, bands.astype(str), flagged
        )
    except ValueError:
        pass  # too few distinct amounts to band

    # --- slice: hour of day ---------------------------------------------
    analysis.slices["hour_band"] = _recall_by(
        test_df,
        pd.cut(
            test_df[S.TIMESTAMP].dt.hour,
            bins=[-1, 5, 11, 17, 23],
            labels=["00-05", "06-11", "12-17", "18-23"],
        ).astype(str),
        flagged,
    )

    # --- slice: payment type --------------------------------------------
    if S.PAYMENT_TYPE in test_df.columns:
        analysis.slices["payment_type"] = _recall_by(
            test_df, test_df[S.PAYMENT_TYPE].astype(str), flagged
        )

    # --- slice: position within its pattern ------------------------------
    # A chain's first hop has no prior structure to detect; the last has the
    # most. If recall is concentrated at the tail, the model needs history the
    # early hops do not yet have -- which is a temporal-feature finding.
    if S.SCENARIO_ID in test_df.columns and test_df[S.SCENARIO_ID].notna().any():
        annotated = test_df.dropna(subset=[S.SCENARIO_ID])
        rank = annotated.groupby(S.SCENARIO_ID, observed=True)[S.TIMESTAMP].rank(
            method="first"
        )
        size = annotated.groupby(S.SCENARIO_ID, observed=True)[S.TIMESTAMP].transform(
            "size"
        )
        position = pd.cut(
            (rank - 1) / size.clip(lower=1),
            bins=[-0.01, 0.33, 0.66, 1.0],
            labels=["early", "middle", "late"],
        ).astype(str)
        sub_flagged = flagged[test_df.index.get_indexer(annotated.index)]
        analysis.slices["pattern_position"] = _recall_by(
            annotated, position, sub_flagged
        )

    # --- profiles --------------------------------------------------------
    missed = test_df[~flagged & positive]
    caught = test_df[flagged & positive]
    false_alarms = test_df[flagged & ~positive]

    def profile(frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {}
        return {
            "count": len(frame),
            "median_amount": float(frame[S.AMOUNT].median()),
            "self_transfer_rate": (
                float(frame[S.IS_SELF_TRANSFER].mean())
                if S.IS_SELF_TRANSFER in frame.columns
                else None
            ),
            "top_payment_types": (
                frame[S.PAYMENT_TYPE].value_counts().head(3).to_dict()
                if S.PAYMENT_TYPE in frame.columns
                else {}
            ),
        }

    analysis.fn_profile = profile(missed) | {"caught_for_contrast": profile(caught)}
    analysis.fp_profile = profile(false_alarms)

    return analysis
