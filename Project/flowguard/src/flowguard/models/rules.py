"""E0 -- the rule-based baseline (plan v3 Phase 8).

Represents what legacy transaction monitoring does: fixed thresholds on
individual transactions, with no memory and no network view. It exists to be
beaten, and to quantify by how much.

Thresholds are fitted on the training partition only. A rule set tuned on the
evaluation data would not be a baseline, it would be a leak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from flowguard.data import schema as S


@dataclass
class RuleBaseline:
    """Weighted additive rule score in [0, 1].

    Each rule contributes its weight when it fires; the total is normalised.
    This yields a ranking rather than a binary flag, so E0 can be scored with
    PR-AUC on the same footing as the learned models.
    """

    amount_quantile: float = 0.99
    burst_quantile: float = 0.999
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "large_amount": 1.0,
            "very_large_amount": 1.5,
            "cross_currency": 0.75,
            "round_amount": 0.5,
            "odd_hour": 0.25,
            "non_self_transfer": 0.25,
        }
    )

    amount_threshold_: float | None = None
    burst_threshold_: float | None = None
    fit_rows_: int | None = None

    def fit(self, train: pd.DataFrame) -> RuleBaseline:
        """Learn thresholds from the training partition only."""
        amounts = train[S.AMOUNT].to_numpy(dtype="float64")
        self.amount_threshold_ = float(np.quantile(amounts, self.amount_quantile))
        self.burst_threshold_ = float(np.quantile(amounts, self.burst_quantile))
        self.fit_rows_ = len(train)
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if self.amount_threshold_ is None:
            raise RuntimeError("RuleBaseline used before fit")

        amount = df[S.AMOUNT].to_numpy(dtype="float64")
        ts = df[S.TIMESTAMP]

        fired = {
            "large_amount": amount > self.amount_threshold_,
            "very_large_amount": amount > self.burst_threshold_,
            "round_amount": np.mod(amount, 1000) == 0,
            "odd_hour": ((ts.dt.hour < 6) | (ts.dt.hour >= 22)).to_numpy(),
        }

        if S.CURRENCY_RECEIVED in df.columns:
            fired["cross_currency"] = (
                df[S.CURRENCY] != df[S.CURRENCY_RECEIVED]
            ).to_numpy()
        if S.IS_SELF_TRANSFER in df.columns:
            # Laundering moves value between accounts; a reinvestment does not.
            fired["non_self_transfer"] = (df[S.IS_SELF_TRANSFER] == 0).to_numpy()

        total = np.zeros(len(df), dtype="float64")
        applied = 0.0
        for name, mask in fired.items():
            weight = self.weights.get(name, 0.0)
            total += weight * mask.astype("float64")
            applied += weight

        return total / applied if applied else total

    def to_metadata(self) -> dict:
        return {
            "model": "RuleBaseline",
            "amount_quantile": self.amount_quantile,
            "burst_quantile": self.burst_quantile,
            "amount_threshold": self.amount_threshold_,
            "burst_threshold": self.burst_threshold_,
            "weights": self.weights,
            "fit_rows": self.fit_rows_,
            "fit_scope": "train",
        }
