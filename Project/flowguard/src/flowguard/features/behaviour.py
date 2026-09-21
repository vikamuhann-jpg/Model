"""Account-history features GFP does not provide (WINNING_PLAN.md, S4).

Computed once over the whole chronologically ordered corpus -- like GFP, and
unlike the row-local TransactionFeatures -- so a validation row still sees the
training-period history before it. Every feature counts only transactions at a
**strictly earlier timestamp**: rows sharing a minute cannot see each other,
because their order within the minute is undefined (ingest validator).

Implementation: sort (key, time) once and answer "how many events for this key
fall in [t - w, t)" with two searchsorted calls, and sums with a prefix sum.
Per-account rolling windows would be orders of magnitude slower on 5M rows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from flowguard.data import schema as S

HOUR = 3_600
DAY = 86_400


class _Timeline:
    """Events for many keys, answerable as strictly-earlier window queries."""

    def __init__(self, keys: np.ndarray, t: np.ndarray, amount: np.ndarray):
        self.span = int(t.max()) + 2 * DAY + 1  # > any t + window offset
        order = np.lexsort((t, keys))
        self.flat = keys[order].astype("int64") * self.span + t[order]
        self.t = t[order]
        self.csum = np.concatenate([[0.0], np.cumsum(amount[order])])

    def _bounds(self, keys, t, window):
        base = keys.astype("int64") * self.span
        hi = np.searchsorted(self.flat, base + t, "left")
        lo = np.searchsorted(self.flat, base + np.maximum(t - window, 0), "left") \
            if window is not None else np.searchsorted(self.flat, base, "left")
        return lo, hi

    def count(self, keys, t, window=None) -> np.ndarray:
        lo, hi = self._bounds(keys, t, window)
        return (hi - lo).astype("float32")

    def total(self, keys, t, window=None) -> np.ndarray:
        lo, hi = self._bounds(keys, t, window)
        return (self.csum[hi] - self.csum[lo]).astype("float32")

    def since_last(self, keys, t) -> np.ndarray:
        lo, hi = self._bounds(keys, t, None)
        prev = np.where(hi > lo, self.t[np.maximum(hi - 1, 0)], np.nan)
        return (t - prev).astype("float32")


def behaviour_features(tx_view: pd.DataFrame) -> pd.DataFrame:
    """Ten causal history features per row, indexed like ``tx_view``."""
    S.assert_label_blind(tx_view)
    ts = tx_view[S.TIMESTAMP]
    t = ((ts - ts.min()).dt.total_seconds()).to_numpy(dtype="int64")
    amount = tx_view[S.AMOUNT].to_numpy(dtype="float64")

    accounts, _ = pd.factorize(
        pd.concat([tx_view[S.SOURCE_ACCOUNT], tx_view[S.DESTINATION_ACCOUNT]]),
        sort=False,
    )
    n = len(tx_view)
    src, dst = accounts[:n].astype("int64"), accounts[n:].astype("int64")

    sent = _Timeline(src, t, amount)       # events: account sent money
    received = _Timeline(dst, t, amount)   # events: account received money
    n_acc = int(accounts.max()) + 1
    pair_keys = src * n_acc + dst
    pairs = _Timeline(pair_keys, t, amount)

    out = pd.DataFrame(index=tx_view.index)
    out["bh_src_out_n_1h"] = sent.count(src, t, HOUR)
    out["bh_src_out_n_24h"] = sent.count(src, t, DAY)
    out["bh_src_out_amt_24h"] = sent.total(src, t, DAY)
    out["bh_src_in_n_24h"] = received.count(src, t, DAY)
    src_in_amt = received.total(src, t, DAY)
    # Share of what the sender received in the last day that this one transfer
    # moves on -- money in, money straight out is the shape of layering.
    with np.errstate(divide="ignore", invalid="ignore"):
        out["bh_src_passthrough_24h"] = np.where(
            src_in_amt > 0, amount / src_in_amt, np.nan).astype("float32")
    out["bh_dst_in_n_24h"] = received.count(dst, t, DAY)
    out["bh_dst_out_n_24h"] = sent.count(dst, t, DAY)
    out["bh_src_secs_since_out"] = sent.since_last(src, t)
    out["bh_pair_n_prior"] = pairs.count(pair_keys, t)
    out["bh_reverse_pair_n_prior"] = pairs.count(dst * n_acc + src, t)
    return out
