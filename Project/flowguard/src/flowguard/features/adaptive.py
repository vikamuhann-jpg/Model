"""Degree-normalised neighbourhood features (Tier B, narrowed by Gate A).

Gate A said graph features work -- PR-AUC 0.0065 -> 0.1400 -- but it also
falsified the prediction that gains would concentrate in low amount bands, and
the hard-negative control moved from **1.02x to 2.10x**. The graph model alerts
on structurally complex but *benign* accounts at twice the rate it alerts on
ordinary benign traffic. Some of its recall is bought with false positives on
legitimate complexity.

So this family does not chase more recall. It targets that enrichment.

The idea: raw structural counts punish hubs for being hubs. A merchant
settlement account with 400 counterparties has a high fan-in because it is a
merchant, not because it is laundering. Normalising each structural signal by
what is *typical for an account of that degree* asks a different question --
not "is this account busy?" but "is this account behaving unusually **for its
size**?"

Nothing here uses the label, and nothing uses information from after the
transaction being scored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.features.base import FeatureExtractor

#: Degree buckets for the peer comparison. Log-spaced because account activity
#: is heavy-tailed: the gap between 1 and 10 counterparties matters far more
#: than the gap between 300 and 310.
DEGREE_BINS = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, np.inf]


class AdaptiveFeatures(FeatureExtractor):
    """Neighbourhood features normalised against same-degree peers.

    Fitted on the training partition only -- the peer norms are statistics of
    the population, so fitting them on evaluation rows would leak.
    """

    family = "adp"

    def __init__(self) -> None:
        super().__init__()
        self.out_degree_: pd.Series | None = None
        self.in_degree_: pd.Series | None = None
        self.account_median_: pd.Series | None = None
        self.peer_norms_: pd.DataFrame | None = None
        self.global_median_: float = 0.0
        self.fit_rows_: int | None = None

    # ---------------------------------------------------------------- fit
    def fit(self, tx_view: pd.DataFrame) -> AdaptiveFeatures:
        S.assert_label_blind(tx_view)

        self.out_degree_ = tx_view.groupby(S.SOURCE_ACCOUNT, observed=True)[
            S.DESTINATION_ACCOUNT
        ].nunique()
        self.in_degree_ = tx_view.groupby(S.DESTINATION_ACCOUNT, observed=True)[
            S.SOURCE_ACCOUNT
        ].nunique()
        self.account_median_ = tx_view.groupby(S.SOURCE_ACCOUNT, observed=True)[
            S.AMOUNT
        ].median()
        self.global_median_ = float(tx_view[S.AMOUNT].median())

        # What a typical amount looks like for an account of each degree. This
        # is the reference the normalised features are measured against.
        degree = (
            self.out_degree_.reindex(tx_view[S.SOURCE_ACCOUNT].to_numpy())
            .fillna(0)
            .to_numpy()
        )
        bucket = np.digitize(degree, DEGREE_BINS)
        peers = pd.DataFrame(
            {"bucket": bucket, "amount": tx_view[S.AMOUNT].to_numpy()}
        )
        self.peer_norms_ = peers.groupby("bucket")["amount"].agg(
            ["median", "std", "count"]
        )
        self.fit_rows_ = len(tx_view)
        return self

    # ------------------------------------------------------------ extract
    def _extract(self, tx_view: pd.DataFrame) -> pd.DataFrame:
        if self.out_degree_ is None:
            raise RuntimeError("AdaptiveFeatures used before fit")

        src = tx_view[S.SOURCE_ACCOUNT].to_numpy()
        dst = tx_view[S.DESTINATION_ACCOUNT].to_numpy()
        amount = tx_view[S.AMOUNT].to_numpy(dtype="float64")

        out_deg = self.out_degree_.reindex(src).fillna(0).to_numpy(dtype="float64")
        in_deg = self.in_degree_.reindex(dst).fillna(0).to_numpy(dtype="float64")

        out = pd.DataFrame(index=tx_view.index)

        # Raw degree, logged. Kept so the model can still see size if size is
        # genuinely informative -- the point is to ADD the normalised view, not
        # to hide the raw one.
        out["out_degree_log"] = np.log1p(out_deg)
        out["in_degree_log"] = np.log1p(in_deg)

        # Asymmetry: a pass-through account receives and forwards in similar
        # numbers. A merchant receives from many and pays few.
        total = out_deg + in_deg
        with np.errstate(divide="ignore", invalid="ignore"):
            out["degree_asymmetry"] = np.where(
                total > 0, (out_deg - in_deg) / total, 0.0
            )

        # Amount relative to this account's own history. A 500 transfer is
        # unremarkable globally and extraordinary for an account whose median
        # is 30. Unseen accounts fall back to the global median rather than to
        # zero, which would make every new account look anomalous.
        own_median = (
            self.account_median_.reindex(src)
            .fillna(self.global_median_)
            .to_numpy(dtype="float64")
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(own_median > 0, amount / own_median, 1.0)
        out["amount_vs_own_median"] = np.log1p(np.clip(ratio, 0, 1e6))

        # Amount relative to same-degree peers. This is the feature that should
        # move the hard-negative number: a hub transacting like other hubs
        # scores near zero however large its degree.
        bucket = np.digitize(out_deg, DEGREE_BINS)
        peer_median = (
            self.peer_norms_["median"]
            .reindex(bucket)
            .fillna(self.global_median_)
            .to_numpy(dtype="float64")
        )
        peer_std = (
            self.peer_norms_["std"].reindex(bucket).fillna(0.0).to_numpy(dtype="float64")
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            out["amount_vs_peer_median"] = np.log1p(
                np.clip(np.where(peer_median > 0, amount / peer_median, 1.0), 0, 1e6)
            )
            out["amount_peer_z"] = np.where(
                peer_std > 0, (amount - peer_median) / peer_std, 0.0
            )
        out["amount_peer_z"] = np.clip(out["amount_peer_z"], -50, 50)

        # Degree-normalised value: value moved per counterparty. A hub moving a
        # lot across many parties is ordinary; a low-degree account moving the
        # same amount is not.
        with np.errstate(divide="ignore", invalid="ignore"):
            out["amount_per_counterparty"] = np.log1p(
                np.where(out_deg > 0, amount / out_deg, amount)
            )

        # Is either endpoint unseen in training? A genuinely new account is a
        # different situation from a known quiet one, and conflating them is
        # how "no history" gets mistaken for "no activity".
        out["source_unseen"] = (
            ~pd.Index(src).isin(self.out_degree_.index)
        ).astype("int8")
        out["dest_unseen"] = (
            ~pd.Index(dst).isin(self.in_degree_.index)
        ).astype("int8")

        return out

    def to_metadata(self) -> dict:
        return {
            "family": self.family,
            "fit_rows": self.fit_rows_,
            "fit_scope": "train",
            "degree_bins": [b for b in DEGREE_BINS if np.isfinite(b)],
            "global_median_amount": self.global_median_,
            "targets": (
                "hard-negative enrichment (1.02x tabular -> 2.10x with GFP); "
                "degree-normalised so hubs are not penalised for being hubs"
            ),
        }
