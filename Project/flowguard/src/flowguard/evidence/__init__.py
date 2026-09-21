"""Case evidence: the object an investigator reads, and the only source of facts.

Unified Plan v2 section 30.1 requires every explanation, figure and narrative
sentence to read from the evidence object rather than recompute its own. This
package holds that object and the check that enforces the rule.
"""

from flowguard.evidence.bundle import (
    COVERAGE_WARNING,
    DEMONSTRATED_RAILS,
    SCHEMA_VERSION,
    UNKNOWN_RAIL_WARNING,
    EvidenceBundle,
    EvidenceError,
    Reason,
    build_bundle,
    reason_code,
)

__all__ = [
    "COVERAGE_WARNING",
    "DEMONSTRATED_RAILS",
    "SCHEMA_VERSION",
    "UNKNOWN_RAIL_WARNING",
    "EvidenceBundle",
    "EvidenceError",
    "Reason",
    "build_bundle",
    "reason_code",
]
