"""Feature extractor interface with enforced label blindness (plan v3 section 6.2).

Every extractor in the project inherits from :class:`FeatureExtractor`. The
label check runs in :meth:`FeatureExtractor.run`, which is the only public entry
point -- subclasses implement ``_extract`` and cannot bypass it.

This is deliberately structural. "Remember not to pass the label into the
features" is the single most common way a project like this invalidates itself,
and a convention is not an enforcement mechanism.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from flowguard.data.schema import TRANSACTION_ID, assert_label_blind


class FeatureExtractor(ABC):
    """Base class for all feature families.

    Subclasses set :attr:`family` -- the prefix every emitted column carries, so
    that ablations can select a family by name alone (plan v3 section 21).
    """

    #: Column-name prefix for this family, e.g. ``"gfp"``, ``"tflow"``, ``"vflow"``.
    family: str = ""

    def __init__(self) -> None:
        if not self.family:
            raise ValueError(f"{type(self).__name__} must declare a non-empty family")

    @abstractmethod
    def _extract(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        """Compute features for ``tx_view``, which is already label-free.

        Must return a frame indexed identically to ``tx_view``.
        """

    def run(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        """Validate, extract, and namespace the output.

        Raises
        ------
        LabelLeakageError
            If ``tx_view`` carries an evaluation-only column.
        """
        assert_label_blind(tx_view)

        out = self._extract(tx_view)

        if len(out) != len(tx_view):
            raise ValueError(
                f"{type(self).__name__} returned {len(out)} rows for "
                f"{len(tx_view)} inputs; extraction must be row-aligned"
            )
        if not out.index.equals(tx_view.index):
            raise ValueError(
                f"{type(self).__name__} changed the index; extraction must preserve it"
            )

        prefix = f"{self.family}_"
        renamed = {
            col: (col if col.startswith(prefix) else prefix + col)
            for col in out.columns
            if col != TRANSACTION_ID
        }
        return out.rename(columns=renamed)

    @property
    def name(self) -> str:
        return type(self).__name__
