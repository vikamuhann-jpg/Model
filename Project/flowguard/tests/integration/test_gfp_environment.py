"""Environment gate: the Graph Feature Preprocessor must actually work here.

This is the first test in the project because every plan in docs/ builds its E2
baseline on GFP, and GFP's native backend is absent from the Windows snapml
wheel (see docs/ADR-001-gfp-platform.md). A silent failure here would not
surface until feature extraction, so it is asserted up front and in CI.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.environment

DAY = 86_400

# Hyphenated keys are deliberate -- GFP names them "scatter-gather", "temp-cycle"
# and "lc-cycle". set_params raises KeyError on anything else.
GFP_PARAMS = {
    "num_threads": 4,
    "time_window": 10 * DAY,
    "vertex_stats": True,
    "vertex_stats_tw": 10 * DAY,
    "vertex_stats_cols": [4],
    "vertex_stats_feats": [0, 1, 2, 3, 4, 8, 9, 10],
    "fan": True,
    "fan_tw": DAY,
    "degree": True,
    "degree_tw": DAY,
    "scatter-gather": True,
    "scatter-gather_tw": 5 * DAY,
    "temp-cycle": True,
    "temp-cycle_tw": 10 * DAY,
    "lc-cycle": True,
    "lc-cycle_tw": 10 * DAY,
    "lc-cycle_len": 10,
}

# [edge_id, source, target, timestamp, amount]
# 1->2->3->1 is a temporal cycle (round-tripping); 4,6,7->5 is a fan-in.
EDGES = np.array(
    [
        [0, 1, 2, 10, 1000.0],
        [1, 2, 3, 20, 980.0],
        [2, 3, 1, 30, 950.0],
        [3, 4, 5, 40, 100.0],
        [4, 6, 5, 45, 120.0],
        [5, 7, 5, 50, 130.0],
    ],
    dtype=np.float64,
)
N_RAW = EDGES.shape[1]
CYCLE_CLOSING_EDGE = 2
FAN_IN_EDGE = 5


@pytest.fixture
def gfp():
    from snapml import GraphFeaturePreprocessor

    preproc = GraphFeaturePreprocessor()
    preproc.set_params(GFP_PARAMS)
    return preproc


def test_native_backend_is_present():
    """Constructing GFP calls gf_allocate, which the Windows wheel lacks."""
    from snapml import GraphFeaturePreprocessor

    GraphFeaturePreprocessor()


def test_engineered_features_are_produced(gfp):
    out = gfp.fit_transform(EDGES)
    assert out.shape[0] == EDGES.shape[0]
    assert out.shape[1] > N_RAW, "no engineered features appended"


def test_cycle_edge_carries_cycle_features(gfp):
    """The edge closing a round-trip must differ from an ordinary edge."""
    out = gfp.fit_transform(EDGES)
    cycle = out[CYCLE_CLOSING_EDGE, N_RAW:]
    fan_in = out[FAN_IN_EDGE, N_RAW:]
    assert np.count_nonzero(cycle) > 0
    assert not np.array_equal(cycle, fan_in), "topology is not reflected in features"


def test_streaming_path_matches_batch_width(gfp):
    """partial_fit + transform is the convention plan v3 s12 requires.

    Features for an edge must be computed against the graph as it stood BEFORE
    that edge was inserted, or a transaction inflates its own structural
    features. That makes the streaming path the one the pipeline actually uses.
    """
    batch_width = gfp.fit_transform(EDGES).shape[1]

    from snapml import GraphFeaturePreprocessor

    streaming = GraphFeaturePreprocessor()
    streaming.set_params(GFP_PARAMS)
    streaming.partial_fit(EDGES[:-1])
    out = streaming.transform(EDGES[-1:])

    assert out.shape == (1, batch_width)


def test_unknown_param_fails_loudly(gfp):
    """Underscored spellings must not silently no-op."""
    with pytest.raises(KeyError):
        gfp.set_params({"scatter_gather": True})
