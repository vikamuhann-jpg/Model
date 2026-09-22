"""Transaction-only features -- the E1 baseline (plan v3 Phase 7).

Deliberately contains **no** cross-row information: no account history, no
aggregates, no graph. E1 exists to answer "how far does a single transaction's
own attributes get you?", and any leakage of neighbouring rows into it would
inflate the floor that E2's graph features must clear.

Categorical encoders are fitted on training rows only and their fit scope is
recorded, per the leakage rules in v3 section 11.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.features.base import FeatureExtractor


class CategoricalEncoder:
    """Ordinal encoder with an explicit, recorded fit scope.

    Unseen categories map to -1 rather than raising: a test-period payment type
    absent from training is a real occurrence, and crashing on it would hide a
    distribution shift that should instead be measured.
    """

    def __init__(self) -> None:
        self.categories_: dict[str, dict[str, int]] = {}
        self.fit_rows_: int | None = None

    def fit(self, df: pd.DataFrame, columns: list[str]) -> CategoricalEncoder:
        self.categories_ = {}
        for col in columns:
            values = sorted({v for v in df[col].dropna().unique()})
            self.categories_[col] = {v: i for i, v in enumerate(values)}
        self.fit_rows_ = len(df)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.fit_rows_ is None:
            raise RuntimeError("encoder used before fit")
        out = {}
        for col, mapping in self.categories_.items():
            out[f"{col}_code"] = (
                df[col].map(mapping).fillna(-1).astype("int32").to_numpy()
            )
        return pd.DataFrame(out, index=df.index)

    def to_metadata(self) -> dict:
        return {
            "fit_rows": self.fit_rows_,
            "fit_scope": "train",
            "columns": {c: len(m) for c, m in self.categories_.items()},
        }


#: What each column means, for evidence-bundle reasons (columns carry a ``tx_`` prefix).
LABELS = {
    "tx_amount": "transaction amount",
    "tx_amount_log": "transaction amount (log scale)",
    "tx_amount_is_round_1k": "amount is a round thousand",
    "tx_amount_is_round_100": "amount is a round hundred",
    "tx_amount_decimals": "cents part of the amount",
    "tx_hour": "hour of day",
    "tx_minute_of_day": "minute of day",
    "tx_is_self_transfer": "transfer between the same account",
    "tx_amount_received_log": "amount received (log scale)",
    "tx_amount_ratio": "amount received ÷ amount paid",
    "tx_is_cross_currency": "paid and received in different currencies",
    "tx_currency_code": "payment currency",
    "tx_payment_type_code": "payment rail",
}


class TransactionFeatures(FeatureExtractor):
    """Row-local features only."""

    family = "tx"

    CATEGORICAL = [S.CURRENCY, S.PAYMENT_TYPE]

    def __init__(
        self,
        encoder: CategoricalEncoder | None = None,
        *,
        include_payment_type: bool = True,
    ) -> None:
        super().__init__()
        self.encoder = encoder or CategoricalEncoder()
        # payment_type is a GENERATOR ARTIFACT on the IBM AML corpora: 2,553 of
        # 2,554 annotated pattern transactions are ACH, so "is ACH" nearly
        # identifies an injected pattern. It is a legitimate observable at
        # scoring time -- not leakage -- but it is a spurious correlation that
        # will not transfer to real data, where laundering uses every rail.
        # Excluding it is how we measure whether the model learned structure or
        # learned the generator. See docs/ADR-007-payment-type-artifact.md.
        self.include_payment_type = include_payment_type

    @property
    def categorical(self) -> list[str]:
        if self.include_payment_type:
            return list(self.CATEGORICAL)
        return [c for c in self.CATEGORICAL if c != S.PAYMENT_TYPE]

    def fit(self, tx_view: pd.DataFrame) -> TransactionFeatures:
        S.assert_label_blind(tx_view)
        self.encoder.fit(tx_view, self.categorical)
        return self

    def _extract(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        ts = tx_view[S.TIMESTAMP]
        amount = tx_view[S.AMOUNT].to_numpy(dtype="float64")

        out = pd.DataFrame(index=tx_view.index)
        out["amount"] = amount
        # Amounts span many orders of magnitude; the log is what trees can split
        # on sensibly without needing hundreds of thresholds.
        out["amount_log"] = np.log1p(np.clip(amount, 0, None))

        # Round-number amounts are a weak structuring signal.
        out["amount_is_round_1k"] = (np.mod(amount, 1000) == 0).astype("int8")
        out["amount_is_round_100"] = (np.mod(amount, 100) == 0).astype("int8")
        out["amount_decimals"] = (
            np.round(np.mod(amount, 1) * 100).astype("int16")
        )

        # Within-day position only. day_of_week and is_weekend are deliberately
        # ABSENT: over a 10-day corpus they are near-collinear with the calendar
        # date, so under a chronological split they identify which part of the
        # test window a row sits in rather than describing its behaviour. On
        # HI-Small, day_of_week alone scored PR-AUC 0.0926 against the full
        # model's 0.0829 -- it was reading the generator's tail, not laundering.
        out["hour"] = ts.dt.hour.astype("int8")
        out["minute_of_day"] = (ts.dt.hour * 60 + ts.dt.minute).astype("int16")

        if S.IS_SELF_TRANSFER in tx_view.columns:
            out["is_self_transfer"] = tx_view[S.IS_SELF_TRANSFER].astype("int8")

        if S.AMOUNT_RECEIVED in tx_view.columns:
            received = tx_view[S.AMOUNT_RECEIVED].to_numpy(dtype="float64")
            out["amount_received_log"] = np.log1p(np.clip(received, 0, None))
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.where(amount > 0, received / amount, 1.0)
            out["amount_ratio"] = np.clip(ratio, 0, 1e6)

        if S.CURRENCY_RECEIVED in tx_view.columns:
            out["is_cross_currency"] = (
                tx_view[S.CURRENCY] != tx_view[S.CURRENCY_RECEIVED]
            ).astype("int8")

        encoded = self.encoder.transform(tx_view)
        for col in encoded.columns:
            out[col] = encoded[col]

        return out

    def to_metadata(self) -> dict:
        return {
            "family": self.family,
            "include_payment_type": self.include_payment_type,
            "encoder": self.encoder.to_metadata(),
        }
