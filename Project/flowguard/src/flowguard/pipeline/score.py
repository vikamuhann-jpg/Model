"""Batch scoring with a shipped model package.

This is the boundary between the AI repository and the product repository. The
product side never loads a model; it reads what this writes::

    python -m flowguard.pipeline.score \\
        --package models/flowguard_A4_v1 \\
        --transactions transactions.parquet \\
        --out outputs/ \\
        [--graph-cache <parts dir>] [--cases 25]

Writes three things, each shaped by a schema in ``contracts/``:

=========================  ====================================  ==============================
``scores.csv``             one row per transaction               ``score.schema.json``
``cases/<case_id>.json``   evidence bundles for the top alerts   ``evidence_bundle.schema.json``
``run.json``               what produced this output             ``run.schema.json``
=========================  ====================================  ==============================

**Why batch, not a live API.** 155 of the model's inputs are graph features from
IBM Snap ML's Graph Feature Preprocessor. It runs only on Linux and must replay
transaction history in time order, at roughly 450 transactions a second on the
synthetic corpus and less on real networks (ADR-013). One transaction cannot be
scored in isolation; a window of history can. So scoring runs as a job and the
product reads its results from a database.

The package's pickles are loaded as trusted local files. Do not point
``--package`` at a model directory from an untrusted source.
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.interpretation import local_contributions
from flowguard.evidence import build_bundle
from flowguard.features.gfp import GFPFeatures, read_varying_chunks, windowed_params
from flowguard.features.transaction import TransactionFeatures
from flowguard.graph.trace import TraceIndex, TraceLimits
from flowguard.models.xgb import XGBModel

#: Alert budget whose threshold defines ``alert`` in scores.csv.
DEFAULT_BUDGET = "0.01"
#: Bounds for the trace behind each exported case, as used for the P2 case.
CASE_LIMITS = TraceLimits(degree_cap=16, edge_budget=200)
CASE_HORIZON = 3


class ScoringError(ValueError):
    """Raised when inputs cannot be scored faithfully by the package."""


@dataclass
class Package:
    """A model package, loaded exactly as training left it."""

    path: Path
    model: XGBModel
    extractor: TransactionFeatures
    columns: list[str]
    schema_hash: str
    threshold: float
    threshold_source: str
    provenance: dict

    @property
    def model_id(self) -> str:
        return self.path.name

    @property
    def uses_payment_type(self) -> bool:
        return S.PAYMENT_TYPE in self.extractor.encoder.categories_


def load_package(path: Path, budget: str = DEFAULT_BUDGET) -> Package:
    import xgboost as xgb

    path = Path(path)
    booster = xgb.Booster()
    booster.load_model(str(path / "model.json"))
    with (path / "calibrator.pkl").open("rb") as fh:
        calibrator = pickle.load(fh)
    with (path / "encoders" / "categorical.pkl").open("rb") as fh:
        encoder = pickle.load(fh)

    # Rebuild the training objects rather than re-implementing their maths:
    # XGBModel.predict is the exact code path validation measured.
    model = XGBModel()
    model.booster_ = booster
    model.calibrator_ = calibrator
    # The pickled encoder's own categories decide which columns it emits.
    extractor = TransactionFeatures(
        encoder, include_payment_type=S.PAYMENT_TYPE in encoder.categories_
    )

    schema = json.loads((path / "feature_schema.json").read_text(encoding="utf-8"))
    thresholds = json.loads((path / "thresholds.json").read_text(encoding="utf-8"))
    if budget not in thresholds["thresholds"]:
        raise ScoringError(
            f"budget {budget} not in package; "
            f"available: {sorted(thresholds['thresholds'])}"
        )
    chosen = thresholds["thresholds"][budget]
    return Package(
        path=path,
        model=model,
        extractor=extractor,
        columns=list(schema["columns"]),
        schema_hash=schema["schema_hash"],
        threshold=float(chosen["value"]),
        threshold_source=f"{chosen['source']} @ {float(budget):.1%} alert budget",
        provenance=json.loads((path / "PROVENANCE.json").read_text(encoding="utf-8")),
    )


def read_transactions(path: Path) -> pd.DataFrame:
    path = Path(path)
    tx = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    missing = {
        S.TRANSACTION_ID,
        S.TIMESTAMP,
        S.SOURCE_ACCOUNT,
        S.DESTINATION_ACCOUNT,
        S.AMOUNT,
        S.CURRENCY,
    } - set(tx.columns)
    if missing:
        raise ScoringError(
            f"transactions are missing required columns: {sorted(missing)}"
        )
    tx[S.TIMESTAMP] = pd.to_datetime(tx[S.TIMESTAMP], utc=True)
    # Graph features are order-dependent, so history is replayed in time order.
    # The index is deliberately NOT reset: it is each row's position in the
    # input file, which is the id cached graph parts are keyed by. Resetting it
    # would silently hand every row another row's graph features.
    tx = tx.sort_values(S.TIMESTAMP, kind="stable")
    if S.IS_SELF_TRANSFER not in tx.columns:
        tx[S.IS_SELF_TRANSFER] = (
            tx[S.SOURCE_ACCOUNT] == tx[S.DESTINATION_ACCOUNT]
        ).astype("int8")
    return tx


def graph_features(
    tx: pd.DataFrame, cache: Path | None = None, window_days: float = 2.0
) -> pd.DataFrame:
    """Graph features for every row of ``tx``, indexed like ``tx``.

    With ``cache``, reuse part files extracted earlier over this same frame --
    their row ids are positions in it. Without one, extract now: slow, and the
    reason scoring is a batch job.
    """
    if cache is not None:
        graph = read_varying_chunks(cache)
        absent = tx.index.difference(graph.index)
        if len(absent):
            raise ScoringError(
                f"graph cache covers {len(tx) - len(absent):,} of {len(tx):,} rows; "
                "it must have been extracted over this exact transaction frame"
            )
        return graph.loc[tx.index]
    return GFPFeatures(params=windowed_params(window_days)).run_streaming(
        S.feature_view(tx)
    )


def feature_matrix(
    pkg: Package, tx: pd.DataFrame, graph: pd.DataFrame
) -> pd.DataFrame:
    tabular = pkg.extractor.run(S.feature_view(tx))
    X = pd.concat([tabular, graph], axis=1)
    missing = [c for c in pkg.columns if c not in X.columns]
    if missing:
        # Never fill with zeros: a model scored on inputs it never saw returns
        # a confident, meaningless number.
        raise ScoringError(
            f"{len(missing)} feature(s) the package needs are absent, "
            f"e.g. {missing[:5]}. Check the input carries amount_received and "
            "currency_received, and that graph features used the training window."
        )
    return X[pkg.columns]


def score_frame(pkg: Package, tx: pd.DataFrame, X: pd.DataFrame) -> pd.DataFrame:
    raw = pkg.model.predict_raw(X)
    calibrated = pkg.model.calibrator_.predict(raw)
    out = pd.DataFrame(
        {
            "transaction_id": tx[S.TRANSACTION_ID].astype(str).to_numpy(),
            "timestamp": tx[S.TIMESTAMP].dt.strftime("%Y-%m-%dT%H:%M:%SZ").to_numpy(),
            "source_account": tx[S.SOURCE_ACCOUNT].astype(str).to_numpy(),
            "destination_account": tx[S.DESTINATION_ACCOUNT].astype(str).to_numpy(),
            "amount": tx[S.AMOUNT].astype(float).to_numpy(),
            "score": np.asarray(calibrated, dtype=float),
            # Isotonic calibration saturates its top bin at 1.0, so the calibrated
            # score alone cannot order the most severe alerts. The raw score can.
            "raw_score": np.asarray(raw, dtype=float),
        },
        index=tx.index,
    )
    if S.PAYMENT_TYPE in tx.columns:
        out.insert(5, "payment_type", tx[S.PAYMENT_TYPE].astype(str).to_numpy())
    order = np.lexsort((-out["raw_score"].to_numpy(), -out["score"].to_numpy()))
    rank = np.empty(len(out), dtype=np.int64)
    rank[order] = np.arange(1, len(out) + 1)
    out["rank"] = rank
    out["alert"] = out["score"] >= pkg.threshold
    return out


def export_cases(
    pkg: Package,
    tx: pd.DataFrame,
    X: pd.DataFrame,
    scores: pd.DataFrame,
    out_dir: Path,
    n_cases: int,
) -> list[str]:
    """Evidence bundles for the highest-ranked alerts, one per subject account."""
    if n_cases <= 0:
        return []
    index = TraceIndex(tx)
    written: list[str] = []
    seen: set[str] = set()
    for i in scores.sort_values("rank").index:
        if len(written) >= n_cases or not scores.at[i, "alert"]:
            break
        subject = scores.at[i, "source_account"]
        if subject in seen:
            continue
        seen.add(subject)
        result = index.trace(
            subject, horizon=CASE_HORIZON, at=tx.at[i, S.TIMESTAMP], limits=CASE_LIMITS
        )
        if result.n_edges == 0:
            continue
        bundle = build_bundle(
            result,
            score=float(scores.at[i, "score"]),
            threshold=pkg.threshold,
            threshold_source=pkg.threshold_source,
            model={
                "model_id": pkg.model_id,
                "git_commit": pkg.provenance.get("git_commit"),
                "feature_schema_hash": pkg.schema_hash,
                "uses_payment_type": pkg.uses_payment_type,
            },
            # By index, not position: edges keep the source frame's index.
            contributions=local_contributions(pkg.model, X.loc[result.edges.index]),
            transactions=tx,
        )
        bundle.write(out_dir / "cases" / f"{bundle.case_id}.json")
        written.append(bundle.case_id)
    return written


def run(
    package: Path,
    transactions: Path,
    out_dir: Path,
    *,
    graph_cache: Path | None = None,
    n_cases: int = 25,
    budget: str = DEFAULT_BUDGET,
) -> dict:
    started = time.perf_counter()
    pkg = load_package(package, budget)
    tx = read_transactions(transactions)
    X = feature_matrix(pkg, tx, graph_features(tx, graph_cache))
    scores = score_frame(pkg, tx, X)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.sort_values("rank").to_csv(out_dir / "scores.csv", index=False)
    cases = export_cases(pkg, tx, X, scores, out_dir, n_cases)

    summary = {
        "model_id": pkg.model_id,
        "git_commit": pkg.provenance.get("git_commit"),
        "feature_schema_hash": pkg.schema_hash,
        "uses_payment_type": pkg.uses_payment_type,
        "threshold": pkg.threshold,
        "threshold_source": pkg.threshold_source,
        "n_transactions": int(len(scores)),
        "n_alerts": int(scores["alert"].sum()),
        "case_ids": cases,
        "scored_at": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seconds": round(time.perf_counter() - started, 1),
    }
    (out_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--transactions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--graph-cache", type=Path, default=None)
    parser.add_argument("--cases", type=int, default=25)
    parser.add_argument("--budget", default=DEFAULT_BUDGET)
    args = parser.parse_args(argv)
    summary = run(
        args.package,
        args.transactions,
        args.out,
        graph_cache=args.graph_cache,
        n_cases=args.cases,
        budget=args.budget,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
