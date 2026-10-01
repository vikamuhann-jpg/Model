"""Unseen-pattern split (plan v3 section 11 B).

Distinguishes **generalisation to novel structure** from **memorisation of one
generator's templates**. Train on a subset of typologies, test on the held-out
ones. A model that only recognises the eight shapes AMLSim injects has learned
the generator, not laundering.

A caveat this split must carry into the report: on HI-Small only **62%** of
positives have a `pattern_type` at all (3,209 of 5,177 before tail-trimming).
The remainder are labelled laundering with no typology annotation, so a
held-out-typology evaluation covers roughly two-thirds of the positive class.
Unannotated positives are excluded from the held-out side rather than silently
counted as negatives, because treating a positive as a negative would make the
measured precision wrong rather than merely incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S


@dataclass
class UnseenPatternSplit:
    """Train/test partition by typology rather than by time."""

    train_idx: pd.Index
    test_idx: pd.Index
    held_out: list[str]
    seen: list[str]
    excluded_unannotated: int
    coverage: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def sizes(self) -> dict[str, int]:
        return {"train": len(self.train_idx), "test": len(self.test_idx)}

    def apply(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        return df.loc[self.train_idx], df.loc[self.test_idx]

    def to_metadata(self) -> dict:
        return {
            "held_out_typologies": self.held_out,
            "seen_typologies": self.seen,
            "sizes": self.sizes,
            "excluded_unannotated_positives": self.excluded_unannotated,
            "positive_annotation_coverage": self.coverage,
            "notes": list(self.notes),
        }


def available_typologies(df: pd.DataFrame) -> list[str]:
    if S.PATTERN_TYPE not in df.columns:
        return []
    return sorted(str(t) for t in df[S.PATTERN_TYPE].dropna().unique())


def annotation_coverage(df: pd.DataFrame) -> float:
    """Share of positives carrying a typology label."""
    positives = df[df[S.IS_LAUNDERING] == 1]
    if positives.empty:
        return 0.0
    return float(positives[S.PATTERN_TYPE].notna().mean())


def split_by_typology(
    df: pd.DataFrame,
    held_out: list[str] | None = None,
    *,
    n_held_out: int = 2,
    seed: int = 42,
) -> UnseenPatternSplit:
    """Hold out whole typologies from training.

    Negatives go to both sides — they carry no typology and are needed for a
    meaningful base rate on each. Positives are routed by their annotation;
    unannotated positives stay on the training side only.
    """
    typologies = available_typologies(df)
    if not typologies:
        raise ValueError(
            "no pattern_type annotations present; the unseen-pattern split "
            "cannot be constructed and must be declared unavailable (v3 s11 B)"
        )

    if held_out is None:
        rng = np.random.default_rng(seed)
        n = min(n_held_out, max(1, len(typologies) - 1))
        held_out = sorted(
            rng.choice(np.array(typologies, dtype=object), size=n, replace=False).tolist()
        )

    unknown = set(held_out) - set(typologies)
    if unknown:
        raise ValueError(f"typologies not present in data: {sorted(unknown)}")
    seen = [t for t in typologies if t not in held_out]
    if not seen:
        raise ValueError("cannot hold out every typology")

    is_positive = df[S.IS_LAUNDERING] == 1
    annotated = df[S.PATTERN_TYPE].notna()
    in_held_out = df[S.PATTERN_TYPE].isin(held_out)

    # Positives: annotated ones follow their typology; unannotated stay in train.
    positive_test = is_positive & annotated & in_held_out
    positive_train = is_positive & ~positive_test

    # Negatives split randomly so both sides have a realistic base rate.
    rng = np.random.default_rng(seed)
    negative = ~is_positive
    to_test = pd.Series(False, index=df.index)
    negative_positions = np.flatnonzero(negative.to_numpy())
    chosen = rng.choice(
        negative_positions, size=len(negative_positions) // 2, replace=False
    )
    to_test.iloc[chosen] = True

    test_mask = positive_test | (negative & to_test)
    train_mask = positive_train | (negative & ~to_test)

    excluded = int((is_positive & ~annotated).sum())
    coverage = annotation_coverage(df)

    return UnseenPatternSplit(
        train_idx=df.index[train_mask.to_numpy()],
        test_idx=df.index[test_mask.to_numpy()],
        held_out=list(held_out),
        seen=seen,
        excluded_unannotated=excluded,
        coverage=coverage,
        notes=(
            f"{excluded:,} positives lack a typology annotation "
            f"({1 - coverage:.1%} of positives) and were kept on the training "
            "side; the held-out evaluation therefore covers only annotated "
            "patterns",
            "this split is not chronological -- it measures structural "
            "generalisation, not future performance, and must never be "
            "reported as the headline result",
        ),
    )
