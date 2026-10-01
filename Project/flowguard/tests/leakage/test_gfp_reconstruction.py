"""Does rebuilding the preprocessor change any feature? (Tier S1)

GFP evicts edges but retains every vertex it has ever seen, so extraction cost
climbs even under a bounded time window (docs/ADR-006). The proposed fix is to
periodically discard the preprocessor and replay only the edges still inside the
window, bounding the vertex set to accounts active in it.

That is sound **only if** the windowed edge set is the entire state affecting a
future feature. This file is the test of that claim, and it is what decides
whether the optimisation ships -- not the throughput number. If a rebuild
changes any feature by any amount, GFP carries state beyond the windowed edges,
and the optimisation is abandoned rather than tuned.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.features.gfp import DAY, DEFAULT_GFP_PARAMS, GFPFeatures

# `slow` as well as `leakage`: these four run full extractions at batch_size=1
# purely to document a rejected optimisation (ADR-008). They belong in the
# suite, but re-running them on every validation costs ~14 minutes and tells
# the gate nothing new, so the C1 gate deselects them.
pytestmark = [pytest.mark.leakage, pytest.mark.slow]

BASE = pd.Timestamp("2026-01-01T00:00:00Z")


def _frame(n: int = 400, accounts: int = 40, seed: int = 0) -> pd.DataFrame:
    """A dense stream with repeat counterparties, so structure actually forms."""
    rng = np.random.default_rng(seed)
    src = rng.integers(0, accounts, n)
    dst = (src + rng.integers(1, accounts, n)) % accounts
    return pd.DataFrame(
        {
            S.TRANSACTION_ID: [f"TX{i:06d}" for i in range(n)],
            # 30-minute spacing over ~8 days, so a 2-day window evicts roughly
            # three quarters of the stream by the end.
            S.TIMESTAMP: [BASE + pd.Timedelta(minutes=30 * i) for i in range(n)],
            S.SOURCE_ACCOUNT: [f"A{v}" for v in src],
            S.DESTINATION_ACCOUNT: [f"A{v}" for v in dst],
            S.AMOUNT: np.round(rng.lognormal(6, 1, n), 2),
            S.CURRENCY: "USD",
            S.PAYMENT_TYPE: "ACH",
        }
    )


def _params(window_days: float = 2.0) -> dict:
    params = dict(DEFAULT_GFP_PARAMS)
    # One thread. GFP spins up its OpenMP pool per transform call, which on a
    # ~100-edge test graph costs ~18 ms of pure overhead per call and makes the
    # suite take minutes. The real run amortises it over a 1M-edge window.
    params["num_threads"] = 1
    window = int(window_days * DAY)
    params["time_window"] = window
    for key in ("vertex_stats_tw", "scatter-gather_tw", "temp-cycle_tw", "lc-cycle_tw"):
        params[key] = min(params[key], window)
    return params


# Was xfail(strict) until 2026-09-21: the "retained state" ADR-008 measured was
# our own double insertion (transform + partial_fit). With each edge inserted
# once, rebuilding is feature-identical. See WINNING_PLAN.md, S1 log.
def test_reconstruction_is_feature_identical():
    """The decisive test: rebuilding mid-stream must change nothing.

    Any difference means GFP's state is not reducible to the windowed edge set,
    and periodic reconstruction is unsound.
    """
    frame = _frame()
    params = _params()

    continuous = GFPFeatures(params=params, progress_every=0).run_streaming(frame)
    rebuilt = GFPFeatures(
        params=params, progress_every=0, rebuild_every=100
    ).run_streaming(frame)

    assert rebuilt.shape == continuous.shape
    np.testing.assert_array_equal(
        rebuilt.to_numpy(),
        continuous.to_numpy(),
        err_msg=(
            "rebuilding the preprocessor changed extracted features -- GFP "
            "carries state beyond the windowed edge set, so periodic "
            "reconstruction is unsound and must not be used"
        ),
    )


def test_reconstruction_actually_happened():
    """Guard against the test passing because nothing was rebuilt."""
    with pytest.warns(UserWarning, match="UNSOUND"):
        extractor = GFPFeatures(params=_params(), progress_every=0, rebuild_every=100)
    extractor.run_streaming(_frame())
    assert extractor.n_rebuilds_ >= 3, (
        f"only {extractor.n_rebuilds_} rebuilds occurred; the identity test "
        "would pass vacuously"
    )


@pytest.mark.parametrize("rebuild_every", [50, 137, 250])
def test_identical_at_several_rebuild_cadences(rebuild_every):
    """The result must not depend on how often the rebuild happens."""
    frame = _frame(n=300, seed=3)
    params = _params()

    continuous = GFPFeatures(params=params, progress_every=0).run_streaming(frame)
    rebuilt = GFPFeatures(
        params=params, progress_every=0, rebuild_every=rebuild_every
    ).run_streaming(frame)

    np.testing.assert_array_equal(rebuilt.to_numpy(), continuous.to_numpy())


def test_rebuild_disabled_by_default():
    """Opt-in only: the default path stays the one already validated."""
    assert GFPFeatures().rebuild_every == 0


def test_rebuild_is_inert_without_a_window():
    """With no time_window there is nothing to evict, so nothing may rebuild.

    Replaying a 'window' that spans the whole stream would be pure overhead,
    and worse, would silently differ if it were ever truncated.
    """
    params = dict(DEFAULT_GFP_PARAMS)
    params["time_window"] = -1
    with pytest.warns(UserWarning, match="UNSOUND"):
        extractor = GFPFeatures(params=params, progress_every=0, rebuild_every=50)
    extractor.run_streaming(_frame(n=200))
    assert extractor.n_rebuilds_ == 0
