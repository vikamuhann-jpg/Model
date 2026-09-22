"""Evidence bundles: the case object an investigator reads (FR-09, FR-11).

Built to the schema Unified Plan v2 section 30.2 specifies, with the rule from
section 30.1 enforced rather than merely stated:

    Every explanation, dashboard element, narrative sentence and exported report
    reads from the evidence object. Nothing generates its own facts.

So the bundle carries its *primitives* -- the traced transactions and the model
outputs -- and every aggregate in it (``accounts``, ``per_hop``, the rail counts)
is derived from those primitives at build time and re-derivable from them
afterwards. :meth:`EvidenceBundle.check_internal_consistency` recomputes them and
is the machine-checkable form of the rule.

Three deliberate omissions from the v2 schema, because those fields describe work
that does not exist and a bundle must not invent facts:

* ``primary_typology`` / ``secondary_typologies`` -- nothing classifies a
  typology yet; that is P4, and until it lands the field would be a guess.
* ``vflow_*`` / ``tflow_*`` supporting features -- the value-flow family was
  ruled out before being built and the adaptive family was measured and rejected
  (ADR-011). Neither exists to report.
* ``risk_category`` -- a banding policy nobody has set. The calibrated score and
  the threshold that produced the alert are both present; inventing HIGH/MEDIUM
  bands on top would be the bundle generating its own facts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from flowguard.data import schema as S
from flowguard.features.behaviour import LABELS as BEHAVIOUR_LABELS
from flowguard.features.gfp import feature_label
from flowguard.features.transaction import LABELS as TX_LABELS
from flowguard.graph.trace import TraceResult

SCHEMA_VERSION = "1.0"

#: Payment rails on which the validated model has demonstrated recall. Per
#: ADR-007 the corpus injects laundering almost exclusively over ACH, and the
#: validated model catches 599/796 ACH positives against 1/100 everywhere else.
DEMONSTRATED_RAILS = ("ACH",)

COVERAGE_WARNING = (
    "This case involves payment rails on which the model has NOT demonstrated "
    "recall. On the validation corpus it caught 599 of 796 ACH laundering "
    "transactions and 1 of 100 across all other rails combined (ADR-007). "
    "Absence of an alert on these transactions is not evidence of absence."
)

UNKNOWN_RAIL_WARNING = (
    "This corpus does not record a payment rail, so the model's demonstrated "
    "coverage (ACH only, per ADR-007) cannot be confirmed for this case."
)


class EvidenceError(ValueError):
    """Raised when a bundle cannot be built or verified."""


def _iso(value) -> str:
    """UTC ISO-8601. Stored as text so a bundle round-trips byte-identically."""
    ts = pd.Timestamp(value)
    ts = ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")
    return ts.isoformat()


@dataclass(frozen=True)
class Reason:
    """One attribution-derived reason, grounded in specific transactions.

    ``code`` is derived mechanically from the feature name and the sign of its
    contribution -- never written by hand per typology, which would be an
    assertion dressed as an explanation.
    """

    code: str
    feature: str
    contribution: float
    transaction_ids: list[str]
    #: True when the feature's *meaning* is not recoverable. GFP has no
    #: ``get_feature_names``, but its docs define the output layout, so
    #: ``gfp_f042`` can be named from the extraction parameters
    #: (:func:`flowguard.features.gfp.feature_labels`). Opaque only when those
    #: parameters were not supplied.
    opaque: bool = False
    #: Plain-language meaning of ``feature``; None when unknown.
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "feature": self.feature,
            "label": self.label,
            "contribution": self.contribution,
            "opaque": self.opaque,
            "transaction_ids": list(self.transaction_ids),
        }


def reason_code(feature: str, contribution: float) -> str:
    """A stable code from a feature name and the direction of its effect."""
    direction = "RAISED" if contribution > 0 else "LOWERED"
    return f"{feature.upper()}_{direction}"


def _is_opaque(feature: str) -> bool:
    return feature.startswith("gfp_f")


@dataclass
class EvidenceBundle:
    """A single case. Self-contained: everything an investigator is shown."""

    case_id: str
    created_at: str
    subject_account: str
    risk: dict[str, Any]
    transaction_ids: list[str]
    accounts: list[str]
    path: list[dict[str, Any]]
    trace: dict[str, Any]
    reasons: list[Reason]
    coverage: dict[str, Any]
    model: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    investigator_notes: list[str] = field(default_factory=list)
    disposition: str | None = None

    # ------------------------------------------------------------------ io

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": list(self.accounts),
            "case_id": self.case_id,
            "coverage": self.coverage,
            "created_at": self.created_at,
            "disposition": self.disposition,
            "investigator_notes": list(self.investigator_notes),
            "model": self.model,
            "path": list(self.path),
            "reasons": [r.to_dict() for r in self.reasons],
            "risk": self.risk,
            "schema_version": self.schema_version,
            "subject_account": self.subject_account,
            "trace": self.trace,
            "transaction_ids": list(self.transaction_ids),
        }

    def to_json(self) -> str:
        # sort_keys plus a fixed indent is what makes export/import/export
        # byte-identical, which is gate P2-c. Floats round-trip exactly through
        # Python's repr, so no formatting is applied to them.
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceBundle:
        known = {
            "accounts",
            "case_id",
            "coverage",
            "created_at",
            "disposition",
            "investigator_notes",
            "model",
            "path",
            "reasons",
            "risk",
            "schema_version",
            "subject_account",
            "trace",
            "transaction_ids",
        }
        unknown = set(payload) - known
        if unknown:
            raise EvidenceError(f"unrecognised fields in bundle: {sorted(unknown)}")
        return cls(
            case_id=payload["case_id"],
            created_at=payload["created_at"],
            subject_account=payload["subject_account"],
            risk=payload["risk"],
            transaction_ids=list(payload["transaction_ids"]),
            accounts=list(payload["accounts"]),
            path=list(payload["path"]),
            trace=payload["trace"],
            reasons=[
                Reason(
                    code=r["code"],
                    feature=r["feature"],
                    contribution=r["contribution"],
                    transaction_ids=list(r["transaction_ids"]),
                    opaque=r["opaque"],
                    label=r.get("label"),
                )
                for r in payload["reasons"]
            ],
            coverage=payload["coverage"],
            model=payload["model"],
            schema_version=payload["schema_version"],
            investigator_notes=list(payload["investigator_notes"]),
            disposition=payload["disposition"],
        )

    @classmethod
    def from_json(cls, text: str) -> EvidenceBundle:
        return cls.from_dict(json.loads(text))

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: Path) -> EvidenceBundle:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # -------------------------------------------------------------- checks

    def check_internal_consistency(self) -> None:
        """Section 30.1 as an assertion: no field states a fact the path does not.

        Raises :class:`EvidenceError` naming the first inconsistency found.
        """
        path_ids = [hop["transaction_id"] for hop in self.path]
        if sorted(path_ids) != sorted(self.transaction_ids):
            raise EvidenceError("transaction_ids do not match the path")

        endpoints = {hop["from"] for hop in self.path} | {hop["to"] for hop in self.path}
        if sorted(endpoints) != sorted(self.accounts):
            raise EvidenceError("accounts do not match the endpoints in the path")

        present = set(self.transaction_ids)
        for reason in self.reasons:
            missing = set(reason.transaction_ids) - present
            if missing:
                raise EvidenceError(
                    f"reason {reason.code} cites transactions absent from the "
                    f"bundle: {sorted(missing)}"
                )

        by_depth: dict[int, list[dict]] = {}
        for hop in self.path:
            by_depth.setdefault(hop["depth"], []).append(hop)
        for row in self.trace["per_hop"]:
            hops = by_depth.get(row["depth"], [])
            if row["n_transactions"] != len(hops):
                raise EvidenceError(
                    f"per_hop depth {row['depth']} claims {row['n_transactions']} "
                    f"transactions; the path holds {len(hops)}"
                )
            total = round(sum(h["amount"] for h in hops), 6)
            if round(row["amount"], 6) != total:
                raise EvidenceError(
                    f"per_hop depth {row['depth']} claims {row['amount']}; "
                    f"the path sums to {total}"
                )

        rails = self.coverage.get("rails") or {}
        if rails:
            counted: dict[str, int] = {}
            for hop in self.path:
                rail = hop.get("payment_type")
                if rail is not None:
                    counted[rail] = counted.get(rail, 0) + 1
            if counted != rails:
                raise EvidenceError("coverage rail counts do not match the path")

    def summary(self) -> str:
        lines = [
            f"{self.case_id}  subject {self.subject_account}  "
            f"score {self.risk['score']:.4f} (threshold {self.risk['threshold']:.4f})",
            f"  {len(self.transaction_ids):,} transactions across "
            f"{len(self.accounts):,} accounts",
        ]
        if not self.trace["is_complete"]:
            lines.append(
                f"  TRACE TRUNCATED: {self.trace['truncation']['reason']} -- this is a "
                f"sample of the neighbourhood, not the neighbourhood"
            )
        if self.coverage["warning"]:
            lines.append(f"  COVERAGE: {self.coverage['warning']}")
        lines.append("  top reasons:")
        for reason in self.reasons[:5]:
            mark = " [opaque]" if reason.opaque else ""
            lines.append(f"    {reason.code:38s} {reason.contribution:+.5f}{mark}")
            if reason.label:
                lines.append(f"      {reason.label}")
        return "\n".join(lines)


def _coverage(path: list[dict[str, Any]]) -> dict[str, Any]:
    rails: dict[str, int] = {}
    unknown = 0
    for hop in path:
        rail = hop.get("payment_type")
        if rail is None:
            unknown += 1
        else:
            rails[rail] = rails.get(rail, 0) + 1

    if unknown:
        warning: str | None = UNKNOWN_RAIL_WARNING
    elif any(rail not in DEMONSTRATED_RAILS for rail in rails):
        warning = COVERAGE_WARNING
    else:
        warning = None
    return {
        "rails": dict(sorted(rails.items())),
        "unknown_rail_transactions": unknown,
        "demonstrated_rails": list(DEMONSTRATED_RAILS),
        "warning": warning,
    }


def build_bundle(
    result: TraceResult,
    *,
    score: float,
    threshold: float,
    threshold_source: str,
    model: dict[str, Any],
    contributions: pd.DataFrame | None = None,
    transactions: pd.DataFrame | None = None,
    top_reasons: int = 8,
    created_at: datetime | None = None,
    gfp_params: dict[str, Any] | None = None,
) -> EvidenceBundle:
    """Assemble a case from a trace, a score and (optionally) SHAP values.

    ``contributions`` is the signed per-row SHAP matrix from
    :func:`flowguard.evaluation.interpretation.local_contributions`, indexed to
    match ``result.edges``. Without it the bundle carries no reasons rather than
    fabricated ones. ``gfp_params`` -- the parameters the graph features were
    extracted with -- names graph reasons; without them they stay opaque.
    """
    edges = result.edges
    rail_lookup: dict[str, Any] = {}
    if transactions is not None and S.PAYMENT_TYPE in transactions.columns:
        rail_lookup = dict(
            zip(transactions[S.TRANSACTION_ID], transactions[S.PAYMENT_TYPE])
        )

    path: list[dict[str, Any]] = []
    for _, row in edges.iterrows():
        hop = {
            "transaction_id": str(row[S.TRANSACTION_ID]),
            "from": str(row[S.SOURCE_ACCOUNT]),
            "to": str(row[S.DESTINATION_ACCOUNT]),
            "amount": float(row[S.AMOUNT]),
            "at": _iso(row[S.TIMESTAMP]),
            "depth": int(row["depth"]),
        }
        rail = rail_lookup.get(str(row[S.TRANSACTION_ID]))
        if rail is not None:
            hop["payment_type"] = str(rail)
        path.append(hop)

    transaction_ids = [hop["transaction_id"] for hop in path]
    accounts = sorted({hop["from"] for hop in path} | {hop["to"] for hop in path})

    per_hop = [
        {
            "depth": int(row["depth"]),
            "n_transactions": int(row["n_transactions"]),
            "n_accounts": int(row["n_accounts"]),
            "amount": float(row["amount"]),
        }
        for _, row in result.per_hop().iterrows()
    ]

    truncation = {
        "degree_cap": result.limits.degree_cap,
        "edge_budget": result.limits.edge_budget,
        "capped_vertices": len(result.capped_vertices),
        "budget_exhausted": result.budget_exhausted,
        "reason": (
            None
            if result.is_complete
            else "; ".join(
                filter(
                    None,
                    [
                        f"{len(result.capped_vertices)} vertices hit the degree cap"
                        if result.capped_vertices
                        else None,
                        f"edge budget {result.limits.edge_budget} exhausted"
                        if result.budget_exhausted
                        else None,
                    ],
                )
            )
        ),
    }

    reasons: list[Reason] = []
    if contributions is not None and not edges.empty:
        aligned = contributions.loc[edges.index]
        ranked = aligned.sum(axis=0).abs().sort_values(ascending=False)
        for feature in ranked.index[:top_reasons]:
            column = aligned[feature]
            total = float(column.sum())
            if total == 0.0:
                continue
            # Ground the reason in the transactions that actually drove it:
            # those contributing in the same direction as the net effect.
            driving = column[column > 0] if total > 0 else column[column < 0]
            cited = [
                str(edges.loc[i, S.TRANSACTION_ID])
                for i in driving.sort_values(ascending=total < 0).index
            ]
            label = (feature_label(str(feature), gfp_params) if gfp_params else None) \
                or BEHAVIOUR_LABELS.get(str(feature)) or TX_LABELS.get(str(feature))
            reasons.append(
                Reason(
                    code=reason_code(feature, total),
                    feature=str(feature),
                    contribution=total,
                    transaction_ids=cited,
                    opaque=_is_opaque(str(feature)) and label is None,
                    label=label,
                )
            )

    digest = hashlib.blake2b(
        "|".join(transaction_ids).encode() or result.root.encode(), digest_size=4
    ).hexdigest()
    created = created_at or datetime.now(timezone.utc)

    bundle = EvidenceBundle(
        case_id=f"FG-{digest}",
        created_at=_iso(created),
        subject_account=result.root,
        risk={
            "score": float(score),
            "threshold": float(threshold),
            "threshold_source": threshold_source,
            "above_threshold": bool(score >= threshold),
        },
        transaction_ids=transaction_ids,
        accounts=accounts,
        path=path,
        trace={
            "root": result.root,
            "direction": result.direction,
            "horizon": result.horizon,
            "is_complete": result.is_complete,
            "truncation": truncation,
            "terminals": list(result.terminals),
            "per_hop": per_hop,
        },
        reasons=reasons,
        coverage=_coverage(path),
        model=dict(model),
    )
    bundle.check_internal_consistency()
    return bundle
