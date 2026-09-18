"""Corpus windowing -- trimming the generator's sparse tail.

The IBM AML corpora stop generating background traffic before the injected
laundering patterns finish running. HI-Small measured:

===========  =========  ===========  ==========
Date         Rows       Positives    Rate
===========  =========  ===========  ==========
2022-09-09   552,206    464          0.084%
2022-09-10   208,325    442          0.212%
2022-09-11       396    232          58.6%
...              ...    ...          ...
2022-09-18        11      8          72.7%
===========  =========  ===========  ==========

The trailing 1,108 transactions are ~59% laundering against a 0.10% corpus base
rate -- a ~290x enrichment. That region is not a hard detection problem, it is
an edge effect of how the data was generated, and leaving it in makes any
feature that merely identifies the tail look like a detector.

Trimming it is what makes the reported span match the 10 days the source
material describes.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from flowguard.data import schema as S

#: A day holding less than this fraction of the reference daily volume (the
#: 75th percentile) is treated as tail rather than corpus. The real cliff on
#: HI-Small is ~500x (208,325 -> 396), so the precise value is not delicate.
DEFAULT_MIN_DENSITY = 0.05


@dataclass(frozen=True)
class WindowReport:
    """What trimming removed, for the provenance record."""

    applied: bool
    cutoff: pd.Timestamp | None
    rows_before: int
    rows_after: int
    positives_before: int
    positives_after: int
    days_dropped: list[str]
    min_density: float

    @property
    def rows_dropped(self) -> int:
        return self.rows_before - self.rows_after

    @property
    def positives_dropped(self) -> int:
        return self.positives_before - self.positives_after

    def to_metadata(self) -> dict:
        return {
            "applied": self.applied,
            "cutoff": self.cutoff.isoformat() if self.cutoff is not None else None,
            "min_density": self.min_density,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_dropped": self.rows_dropped,
            "positives_before": self.positives_before,
            "positives_after": self.positives_after,
            "positives_dropped": self.positives_dropped,
            "days_dropped": self.days_dropped,
        }


def daily_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Rows, positives and laundering rate per calendar day."""
    grouped = df.groupby(df[S.TIMESTAMP].dt.date)[S.IS_LAUNDERING].agg(["size", "sum"])
    grouped.columns = ["rows", "positives"]
    grouped["rate"] = grouped["positives"] / grouped["rows"]
    return grouped


def trim_sparse_tail(
    df: pd.DataFrame, *, min_density: float = DEFAULT_MIN_DENSITY
) -> tuple[pd.DataFrame, WindowReport]:
    """Drop the trailing low-volume days.

    Only a *trailing* run is removed. A quiet day in the middle of the corpus is
    real variation and is kept; the tail is defined by the last contiguous run of
    sparse days, which is the shape the generator actually produces.
    """
    profile = daily_profile(df)
    positives_before = int(df[S.IS_LAUNDERING].sum())

    if len(profile) < 2:
        return df, WindowReport(
            applied=False,
            cutoff=None,
            rows_before=len(df),
            rows_after=len(df),
            positives_before=positives_before,
            positives_after=positives_before,
            days_dropped=[],
            min_density=min_density,
        )

    # Reference level is the 75th percentile of daily volume, not the median.
    # The median is dragged into the tail whenever the tail has comparably many
    # days to the dense period -- on a 6-dense/4-sparse corpus the median lands
    # among the sparse days and nothing is trimmed. A high quantile is stable
    # against a long tail, and unlike max() it is not thrown by one spike day.
    threshold = profile["rows"].quantile(0.75) * min_density

    # Walk back from the end while days remain below threshold.
    sparse_tail: list = []
    for day in reversed(profile.index):
        if profile.loc[day, "rows"] < threshold:
            sparse_tail.append(day)
        else:
            break

    if not sparse_tail:
        return df, WindowReport(
            applied=False,
            cutoff=None,
            rows_before=len(df),
            rows_after=len(df),
            positives_before=positives_before,
            positives_after=positives_before,
            days_dropped=[],
            min_density=min_density,
        )

    sparse_tail.reverse()
    cutoff = pd.Timestamp(sparse_tail[0], tz="UTC")
    kept = df[df[S.TIMESTAMP] < cutoff].copy()

    return kept, WindowReport(
        applied=True,
        cutoff=cutoff,
        rows_before=len(df),
        rows_after=len(kept),
        positives_before=positives_before,
        positives_after=int(kept[S.IS_LAUNDERING].sum()),
        days_dropped=[str(d) for d in sparse_tail],
        min_density=min_density,
    )
