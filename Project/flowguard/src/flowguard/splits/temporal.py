"""Leakage-safe chronological splitting (plan v3 section 11).

The invariant this module exists to protect:

    Scoring a transaction at time T may use only information that existed at
    or before T.

Two details here are easy to get wrong and are handled explicitly:

1. **Boundaries are timestamps, not row indices.** A quantile of the timestamp
   column can land *inside* a run of identical timestamps, which would put the
   same instant in two partitions and break the ordering invariant. Boundaries
   are therefore snapped to an observed timestamp value.

2. **Patterns spanning a boundary** leak signal. Plan v3 section 11 lists three
   policies in order of preference; all three are implemented, and the count of
   affected patterns is always reported.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

import numpy as np
import pandas as pd

from flowguard.data.schema import (
    PATTERN_TYPE,
    SCENARIO_ID,
    TIMESTAMP,
    validate_schema,
)

DEFAULT_TRAIN_FRAC: Final = 0.70
DEFAULT_VAL_FRAC: Final = 0.15


class BoundaryPolicy(str, Enum):
    """How to treat a laundering pattern straddling a split boundary."""

    #: Drop transactions within a buffer around each boundary. Cleanest; costs data.
    PURGE = "purge"
    #: Whole pattern follows its first transaction. Preserves patterns; blurs boundary.
    PATTERN_START = "pattern_start"
    #: Split purely on time, accepting truncated patterns in test.
    HARD_CUT = "hard_cut"


class SplitError(ValueError):
    """Raised when a split cannot be produced safely."""


@dataclass(frozen=True)
class SplitSpec:
    """Frozen split configuration. Recorded verbatim in the experiment registry."""

    train_frac: float = DEFAULT_TRAIN_FRAC
    val_frac: float = DEFAULT_VAL_FRAC
    boundary_policy: BoundaryPolicy = BoundaryPolicy.PURGE
    #: Buffer half-width for PURGE. ``None`` derives it from observed pattern spans.
    purge_buffer: pd.Timedelta | None = None
    seed: int = 42

    def __post_init__(self) -> None:
        if not 0 < self.train_frac < 1:
            raise SplitError(f"train_frac must be in (0,1); got {self.train_frac}")
        if not 0 < self.val_frac < 1:
            raise SplitError(f"val_frac must be in (0,1); got {self.val_frac}")
        if self.train_frac + self.val_frac >= 1:
            raise SplitError(
                "train_frac + val_frac must leave room for test; got "
                f"{self.train_frac} + {self.val_frac}"
            )

    @property
    def test_frac(self) -> float:
        return 1.0 - self.train_frac - self.val_frac

    def to_metadata(self) -> dict:
        return {
            "train_frac": self.train_frac,
            "val_frac": self.val_frac,
            "test_frac": self.test_frac,
            "boundary_policy": self.boundary_policy.value,
            "purge_buffer": None if self.purge_buffer is None else str(self.purge_buffer),
            "seed": self.seed,
        }


@dataclass(frozen=True)
class TemporalSplit:
    """A split result. Index-based, so it applies to any aligned frame."""

    train_idx: pd.Index
    val_idx: pd.Index
    test_idx: pd.Index
    train_end: pd.Timestamp
    val_end: pd.Timestamp
    spec: SplitSpec
    patterns_spanning_boundary: int = 0
    purged_rows: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def sizes(self) -> dict[str, int]:
        return {
            "train": len(self.train_idx),
            "val": len(self.val_idx),
            "test": len(self.test_idx),
        }

    def to_metadata(self) -> dict:
        """Provenance block for the experiment registry."""
        return {
            "spec": self.spec.to_metadata(),
            "boundaries": {
                "train_end": self.train_end.isoformat(),
                "val_end": self.val_end.isoformat(),
            },
            "sizes": self.sizes,
            "patterns_spanning_boundary": self.patterns_spanning_boundary,
            "purged_rows": self.purged_rows,
            "notes": list(self.notes),
        }

    def apply(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Slice ``df`` into (train, val, test) using this split's indices."""
        return df.loc[self.train_idx], df.loc[self.val_idx], df.loc[self.test_idx]


# --------------------------------------------------------------------------
# Boundary selection
# --------------------------------------------------------------------------


def _snap_boundary(sorted_ts: pd.Series, target_pos: int) -> pd.Timestamp:
    """Return an observed timestamp that cleanly separates rows.

    ``target_pos`` is the desired row offset. The returned boundary ``b`` is the
    timestamp at that offset; rows are assigned with ``ts <= b`` going earlier.
    Because ``b`` is an actual observed value, every row sharing that instant
    lands in the same partition -- which is what preserves
    ``max(earlier) < min(later)``.
    """
    n = len(sorted_ts)
    target_pos = int(np.clip(target_pos, 1, n - 1))
    return sorted_ts.iloc[target_pos - 1]


def _pattern_key(df: pd.DataFrame) -> str | None:
    """Prefer scenario_id (instance-level) over pattern_type (class-level)."""
    for col in (SCENARIO_ID, PATTERN_TYPE):
        if col in df.columns and df[col].notna().any():
            return col
    return None


def _pattern_spans(df: pd.DataFrame, pattern_key: str) -> pd.DataFrame:
    """First and last transaction time of each pattern instance."""
    return (
        df.dropna(subset=[pattern_key])
        .groupby(pattern_key, observed=True)[TIMESTAMP]
        .agg(["min", "max"])
    )


def _derive_purge_buffer(df: pd.DataFrame, pattern_key: str | None) -> pd.Timedelta:
    """Size the purge buffer to the longest observed pattern duration."""
    if pattern_key is None:
        raise SplitError(
            "purge_buffer could not be derived: no scenario_id or pattern_type "
            "column exists. Pass an explicit purge_buffer, or choose "
            "BoundaryPolicy.HARD_CUT and accept truncated test patterns."
        )
    spans = _pattern_spans(df, pattern_key)
    longest = (spans["max"] - spans["min"]).max()
    if pd.isna(longest):
        raise SplitError("could not derive purge_buffer: no pattern spans available")
    return pd.Timedelta(longest)


def _count_spanning_patterns(
    df: pd.DataFrame, pattern_key: str | None, boundaries: list[pd.Timestamp]
) -> int:
    """Count pattern instances with transactions on both sides of a boundary."""
    if pattern_key is None:
        return 0
    spans = _pattern_spans(df, pattern_key)
    if spans.empty:
        return 0
    spanning = np.zeros(len(spans), dtype=bool)
    for boundary in boundaries:
        spanning |= (spans["min"] <= boundary).to_numpy() & (
            spans["max"] > boundary
        ).to_numpy()
    return int(spanning.sum())


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def chronological_split(
    df: pd.DataFrame, spec: SplitSpec | None = None
) -> TemporalSplit:
    """Split ``df`` chronologically into train / validation / test.

    Deterministic: the same frame and spec always yield identical boundaries.
    No randomness is involved -- ``spec.seed`` is recorded for provenance only.
    """
    spec = spec or SplitSpec()
    validate_schema(df)

    if len(df) < 3:
        raise SplitError(f"need at least 3 rows to split; got {len(df)}")

    order = df[TIMESTAMP].sort_values(kind="stable")
    n = len(order)

    train_end = _snap_boundary(order, int(round(n * spec.train_frac)))
    val_end = _snap_boundary(order, int(round(n * (spec.train_frac + spec.val_frac))))

    if not train_end < val_end:
        raise SplitError(
            f"boundaries collapsed (train_end={train_end}, val_end={val_end}). "
            "The timestamp column is too coarse for these fractions -- widen the "
            "partitions or use a finer timestamp resolution."
        )

    ts = df[TIMESTAMP]
    train_mask = ts <= train_end
    val_mask = (ts > train_end) & (ts <= val_end)
    test_mask = ts > val_end

    pattern_key = _pattern_key(df)
    spanning = _count_spanning_patterns(df, pattern_key, [train_end, val_end])
    notes: list[str] = []
    purged = 0

    if pattern_key is None:
        notes.append(
            "no scenario_id/pattern_type column; boundary-spanning patterns "
            "could not be counted"
        )

    if spec.boundary_policy is BoundaryPolicy.PURGE:
        buffer = spec.purge_buffer or _derive_purge_buffer(df, pattern_key)
        purge_mask = pd.Series(False, index=df.index)
        for boundary in (train_end, val_end):
            purge_mask |= (ts > boundary - buffer) & (ts <= boundary + buffer)
        # A purged row belongs to no partition, so the boundary is a true gap.
        purged = int(purge_mask.sum())
        train_mask &= ~purge_mask
        val_mask &= ~purge_mask
        test_mask &= ~purge_mask
        notes.append(f"purge buffer +/-{buffer} around each boundary")
        if purged / n > 0.25:
            warnings.warn(
                f"purge dropped {purged}/{n} rows ({purged / n:.0%}). The longest "
                "pattern may be long relative to the corpus; consider "
                "BoundaryPolicy.PATTERN_START.",
                stacklevel=2,
            )

    elif spec.boundary_policy is BoundaryPolicy.PATTERN_START:
        if pattern_key is not None:
            starts = (
                df.dropna(subset=[pattern_key])
                .groupby(pattern_key, observed=True)[TIMESTAMP]
                .transform("min")
                .reindex(df.index)
            )
            keyed = starts.notna()
            # Reassign every row of a pattern to the split holding its first
            # transaction. This is exactly why PATTERN_START does not preserve
            # strict max(train) < min(val) ordering -- see the note below.
            train_mask = train_mask.where(~keyed, starts <= train_end)
            val_mask = val_mask.where(
                ~keyed, (starts > train_end) & (starts <= val_end)
            )
            test_mask = test_mask.where(~keyed, starts > val_end)
            train_mask = train_mask.fillna(False).astype(bool)
            val_mask = val_mask.fillna(False).astype(bool)
            test_mask = test_mask.fillna(False).astype(bool)
        notes.append(
            "patterns assigned by first transaction; strict timestamp ordering "
            "across partitions is intentionally NOT guaranteed under this policy"
        )

    else:  # HARD_CUT
        notes.append(
            f"hard cut; {spanning} pattern(s) truncated at a boundary and may be "
            "undetectable in test by construction"
        )

    return TemporalSplit(
        train_idx=df.index[train_mask.to_numpy()],
        val_idx=df.index[val_mask.to_numpy()],
        test_idx=df.index[test_mask.to_numpy()],
        train_end=train_end,
        val_end=val_end,
        spec=spec,
        patterns_spanning_boundary=spanning,
        purged_rows=purged,
        notes=tuple(notes),
    )
