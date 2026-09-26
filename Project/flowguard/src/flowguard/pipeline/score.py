"""Batch scoring with a shipped model package.

This is the boundary between the AI repository and the product repository. The
product side never loads a model; it reads what this writes::

    python -m flowguard.pipeline.score \\
        --package models/flowguard_V2_v1 \\
        --transactions transactions.parquet \\
        --out outputs/ \\
        [--emit-from <timestamp>] [--graph-cache <parts dir>] [--cases 25]

Writes three things, each shaped by a schema in ``contracts/``:

=========================  ====================================  ==============================
``scores.csv``             one row per transaction               ``score.schema.json``
``cases/<case_id>.json``   evidence bundles for the top alerts   ``evidence_bundle.schema.json``
``run.json``               what produced this output             ``run.schema.json``
=========================  ====================================  ==============================

**Why batch, not a live API.** Most of the model's inputs are graph and account-
history features. GFP runs only on Linux and must replay transaction history in
time order -- ~530 transactions a second strictly one at a time over the full
synthetic corpus, less on real networks (ADR-013). One transaction cannot be
scored in isolation; a window with its history can (``--emit-from``). So scoring
runs as a job and the product reads its results from a database.

The package is read as plain data -- JSON and XGBoost's own model format.
Nothing here unpickles. Do not point
``--package`` at a model directory from an untrusted source.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.interpretation import local_contributions
from flowguard.evidence import build_bundle
from flowguard.evidence.bundle import label_for
from flowguard.features.behaviour import behaviour_features
from flowguard.features.gfp import (
    GFPFeatures,
    read_varying_chunks,
    varying_columns,
    windowed_params,
)
from flowguard.features.transaction import CategoricalEncoder, TransactionFeatures
from flowguard.graph.trace import TraceIndex, TraceLimits, TraceResult
from flowguard.models.xgb import PiecewiseCalibrator, XGBModel

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
    #: How the graph features were built: GFP ``params``, ``batch_size``, and
    #: whether ``behaviour`` features are included. Scoring must rebuild them
    #: identically, so it reads them from the package rather than a default.
    graph: dict

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
    # JSON first, pickle only for packages written before it existed. The JSON
    # pair is what a consumer outside this repository can actually read, so it
    # is also the path exercised here rather than a second, untested one.
    calibrator_json = path / "calibrator.json"
    encoder_json = path / "encoders" / "categorical.json"
    if not (calibrator_json.exists() and encoder_json.exists()):
        # Loud, rather than a quiet fallback to the pickles. A pickle needs
        # scikit-learn's exact version and an importable ``flowguard``, and one
        # written under numpy 2 cannot be read under numpy 1.x at all -- so the
        # fallback works here and fails on the machine that matters. Packages
        # built before 2026-09-26 predate these files and need rebuilding.
        missing = [str(p.relative_to(path)) for p in (calibrator_json, encoder_json)
                   if not p.exists()]
        raise ScoringError(
            f"{path.name} is missing {missing}, so it could only be loaded by "
            "unpickling. Rebuild it with run_validation, which writes both, or "
            "regenerate the two files from the pickles on the machine that wrote them."
        )

    calibrator = PiecewiseCalibrator.from_json(
        json.loads(calibrator_json.read_text(encoding="utf-8"))
    )
    encoder = CategoricalEncoder.from_json(
        json.loads(encoder_json.read_text(encoding="utf-8"))
    )

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
    graph_file = path / "graph.json"
    graph = (
        json.loads(graph_file.read_text(encoding="utf-8"))
        if graph_file.exists()
        # Packages before v2 carried no graph.json; they were built this way.
        else {"params": windowed_params(2.0), "batch_size": 1, "behaviour": False}
    )
    return Package(
        path=path,
        model=model,
        extractor=extractor,
        columns=list(schema["columns"]),
        schema_hash=schema["schema_hash"],
        threshold=float(chosen["value"]),
        threshold_source=f"{chosen['source']} @ {float(budget):.1%} alert budget",
        provenance=json.loads((path / "PROVENANCE.json").read_text(encoding="utf-8")),
        graph=graph,
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
    tx: pd.DataFrame,
    cache: Path | None = None,
    params: dict | None = None,
    rows: pd.Index | None = None,
) -> pd.DataFrame:
    """Graph features for every row of ``tx``, indexed like ``tx``.

    With ``cache``, reuse part files extracted earlier over this same frame --
    their row ids are positions in it. Without one, extract now: slow, and the
    reason scoring is a batch job.

    ``rows`` narrows the result to those rows, reading one part file at a time
    and keeping only what it needs. History rows still have to be *present* in
    ``tx`` -- they build the graph and the behaviour timeline -- but their
    engineered columns are never asked for, and loading them is what made
    scoring a 50k window cost the whole corpus in memory: 5M rows x 192 float32
    is 3.8 GB, against 39 MB for the window itself.
    """
    if cache is not None:
        if rows is not None:
            parts = sorted(Path(cache).glob("part_*.parquet"))
            if not parts:
                raise FileNotFoundError(f"no part files in {cache}")
            keep, _ = varying_columns(parts)
            frames = []
            for part in parts:
                block = pd.read_parquet(part, columns=["_row"] + keep).set_index("_row")
                frames.append(block[block.index.isin(rows)])
            graph = pd.concat(frames)
        else:
            graph = read_varying_chunks(cache)
        wanted = tx.index if rows is None else pd.Index(rows)
        absent = wanted.difference(graph.index)
        if len(absent):
            raise ScoringError(
                f"graph cache covers {len(wanted) - len(absent):,} of {len(wanted):,} "
                "rows; it must have been extracted over this exact transaction frame"
            )
        return graph.loc[wanted]
    return GFPFeatures(params=dict(params or windowed_params(2.0))).run_streaming(
        S.feature_view(tx)
    )


def feature_matrix(
    pkg: Package, tx: pd.DataFrame, graph: pd.DataFrame, rows: pd.Index | None = None
) -> pd.DataFrame:
    """The package's feature matrix for ``rows`` (default: all of ``tx``).

    Behaviour features are always computed over the whole of ``tx``: they are an
    account's history, so a row scored without the rows before it is a different
    row. Only the *output* is narrowed.
    """
    wanted = tx.index if rows is None else pd.Index(rows)
    tabular = pkg.extractor.run(S.feature_view(tx.loc[wanted]))
    parts = [tabular, graph.loc[wanted]]
    if pkg.graph.get("behaviour"):
        parts.append(behaviour_features(S.feature_view(tx)).loc[wanted])
    X = pd.concat(parts, axis=1)
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


#: Named drivers written into ``scores.csv`` for each alert.
TOP_FEATURES = 3


def top_features(
    pkg: Package, X: pd.DataFrame, alert: np.ndarray, n: int = TOP_FEATURES
) -> np.ndarray:
    """The ``n`` features that pushed each alert's score up, named and signed.

    A row of scores.csv is the only thing some consumers ever see, so an alert
    that arrives without a reason cannot be triaged. Contributions are TreeSHAP
    from the scoring model itself, computed for the alerts alone -- the full
    matrix is one float per feature per row, which for a whole corpus is larger
    than the corpus.
    """
    out = np.full(len(X), "", dtype=object)
    if not alert.any():
        return out

    contributions = local_contributions(pkg.model, X.loc[alert])
    params = pkg.graph.get("params")
    for position, (_, row) in zip(np.flatnonzero(alert), contributions.iterrows()):
        drivers = row[row > 0].sort_values(ascending=False).head(n)
        out[position] = "; ".join(
            f"{label_for(str(feature), params) or feature} (+{value:.3f})"
            for feature, value in drivers.items()
        )
    return out


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
    out["top_features"] = top_features(pkg, X, out["alert"].to_numpy())
    return out


def _rows_of(
    X: pd.DataFrame,
    rows: pd.Index,
    features_for: Callable[[pd.Index], pd.DataFrame] | None,
) -> pd.DataFrame:
    """``X`` for ``rows``, building the ones it does not hold."""
    missing = rows.difference(X.index)
    if not len(missing):
        return X.loc[rows]
    if features_for is None:
        raise ScoringError(
            f"{len(missing):,} traced row(s) have no features and no way to build "
            "them; pass features_for="
        )
    return pd.concat([X.loc[rows.intersection(X.index)], features_for(missing)]).loc[rows]


def export_cases(
    pkg: Package,
    tx: pd.DataFrame,
    X: pd.DataFrame,
    scores: pd.DataFrame,
    out_dir: Path,
    n_cases: int,
    features_for: Callable[[pd.Index], pd.DataFrame] | None = None,
) -> list[str]:
    """Evidence bundles for the highest-ranked alerts, one per subject account.

    A trace follows hops, not time, so it can reach any row of ``tx`` -- rows
    that were never scored and whose graph features are therefore not in ``X``.
    ``features_for`` fetches those few rows on demand; without it, ``X`` must
    already cover everything a trace can reach.
    """
    if n_cases <= 0:
        return []
    index = TraceIndex(tx)

    # Trace first, fetch once. Every trace that needs history rows would
    # otherwise re-read the whole feature cache on its own -- ten cases, twenty
    # one part files each. The traces themselves are in-memory and cheap.
    traced: list[tuple[int, TraceResult]] = []
    seen: set[str] = set()
    for i in scores.sort_values("rank").index:
        if len(traced) >= n_cases or not scores.at[i, "alert"]:
            break
        subject = scores.at[i, "source_account"]
        if subject in seen:
            continue
        seen.add(subject)
        result = index.trace(
            subject, horizon=CASE_HORIZON, at=tx.at[i, S.TIMESTAMP], limits=CASE_LIMITS
        )
        if result.n_edges:
            traced.append((i, result))

    if traced and features_for is not None:
        wanted = pd.Index([]).append([r.edges.index for _, r in traced]).unique()
        missing = wanted.difference(X.index)
        if len(missing):
            X = pd.concat([X, features_for(missing)])

    written: list[str] = []
    for i, result in traced:
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
            contributions=local_contributions(
                pkg.model, _rows_of(X, result.edges.index, features_for)
            ),
            transactions=tx,
            gfp_params=pkg.graph["params"],
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
    emit_from: pd.Timestamp | None = None,
    emit_until: pd.Timestamp | None = None,
) -> dict:
    """Score ``transactions``; with ``emit_from``/``emit_until``, rows outside that
    window are **history**: they build graph and behaviour features and can be traced
    through, but are not scored. A window scored without history starts cold -- every
    counterparty looks new and every sender dormant -- and alerts far above budget.
    """
    started = time.perf_counter()
    pkg = load_package(package, budget)
    tx = read_transactions(transactions)

    emit = pd.Series(True, index=tx.index)
    if emit_from is not None:
        emit &= tx[S.TIMESTAMP] >= pd.Timestamp(emit_from)
    if emit_until is not None:
        emit &= tx[S.TIMESTAMP] <= pd.Timestamp(emit_until)

    # Features for the scored rows only. History rows still shape those features
    # -- they are in `tx`, so they build the graph and the behaviour timeline --
    # but materialising their engineered columns made a 50k-row window cost the
    # whole corpus: 3.8 GB against 39 MB, which no 6 GB machine can pay.
    def features_for(rows: pd.Index) -> pd.DataFrame:
        graph = graph_features(tx, graph_cache, pkg.graph["params"], rows=rows)
        return feature_matrix(pkg, tx, graph, rows=rows)

    X = features_for(tx.index[emit])
    scores = score_frame(pkg, tx[emit], X)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.sort_values("rank").to_csv(out_dir / "scores.csv", index=False)
    # A trace can reach history rows, whose features are not in X; those few are
    # built on demand.
    cases = export_cases(pkg, tx, X, scores, out_dir, n_cases, features_for)

    summary = {
        "model_id": pkg.model_id,
        "git_commit": pkg.provenance.get("git_commit"),
        "feature_schema_hash": pkg.schema_hash,
        "uses_payment_type": pkg.uses_payment_type,
        "threshold": pkg.threshold,
        "threshold_source": pkg.threshold_source,
        "n_transactions": int(len(scores)),
        "n_alerts": int(scores["alert"].sum()),
        "history_transactions": int((~emit).sum()),
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
    parser.add_argument("--emit-from", default=None,
                        help="score only rows at/after this timestamp; earlier rows "
                             "are history (recommended: at least 2 days of it)")
    parser.add_argument("--emit-until", default=None)
    args = parser.parse_args(argv)
    summary = run(
        args.package,
        args.transactions,
        args.out,
        graph_cache=args.graph_cache,
        n_cases=args.cases,
        budget=args.budget,
        emit_from=pd.Timestamp(args.emit_from, tz="UTC") if args.emit_from else None,
        emit_until=pd.Timestamp(args.emit_until, tz="UTC") if args.emit_until else None,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
