"""Graph operations over the transaction corpus.

Distinct from :mod:`flowguard.features.gfp`, which also builds a graph but only
to emit feature vectors. This package is for traversal: following funds, which
is what an investigator does and what a feature vector cannot express.
"""

from flowguard.graph.trace import (
    BACKWARD,
    DEFAULT_DEGREE_CAP,
    DEFAULT_EDGE_BUDGET,
    FORWARD,
    TraceError,
    TraceIndex,
    TraceLimits,
    TraceResult,
    trace,
)

__all__ = [
    "BACKWARD",
    "DEFAULT_DEGREE_CAP",
    "DEFAULT_EDGE_BUDGET",
    "FORWARD",
    "TraceError",
    "TraceIndex",
    "TraceLimits",
    "TraceResult",
    "trace",
]
