"""Typology hinting (FR-06): which laundering pattern does this look like?

PS9 asks the system to detect layering, round-tripping and structuring **by
name**. The pipeline measures recall per typology but nothing classifies one:
the model emits a single score.

The labels exist -- ``*_Patterns.txt`` annotates 370 injected patterns across
eight typologies -- but the honest size of the problem was stated before any of
this was built: **2,554 annotated transactions**, ~62% of positives carry no
annotation at all, and 140 of 370 patterns straddle a split boundary (ADR-002).

That supports a **hint with calibrated confidence**. It does not support a
classifier anyone should trust unsupervised, and the class is named for what it
is. Below ``confidence_floor`` the hint is :data:`UNCLASSIFIED` rather than the
argmax of a distribution nobody should read that far into.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

UNCLASSIFIED = "unclassified"
DEFAULT_CONFIDENCE_FLOOR = 0.40
DEFAULT_PARAMS: dict = {
    "objective": "multi:softprob",
    "eval_metric": "mlogloss",
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    # The corpus offers a couple of thousand labelled rows across eight classes,
    # so the model is deliberately small. A deeper one memorises the patterns.
    "min_child_weight": 5,
    "num_boost_round": 200,
}


class TypologyError(ValueError):
    """Raised when a hinter cannot be fitted or used as asked."""


@dataclass(frozen=True)
class Hint:
    """One typology hint: a name, a confidence, and the full distribution."""

    label: str
    confidence: float
    distribution: dict[str, float]

    @property
    def is_classified(self) -> bool:
        return self.label != UNCLASSIFIED

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "distribution": self.distribution,
        }


def expected_calibration_error(
    confidence: np.ndarray, correct: np.ndarray, *, bins: int = 10
) -> float:
    """ECE over the predicted-class confidence.

    A hint that says 80% must be right about 80% of the time, or the number is
    decoration. Bins are equal-width over [0, 1]; empty bins contribute nothing.
    """
    confidence = np.asarray(confidence, dtype=float)
    correct = np.asarray(correct, dtype=float)
    if len(confidence) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        in_bin = (confidence > lo) & (confidence <= hi)
        if not in_bin.any():
            continue
        total += in_bin.mean() * abs(correct[in_bin].mean() - confidence[in_bin].mean())
    return float(total)


@dataclass
class TypologyHinter:
    """Multi-class head over the existing feature view.

    Fitted only on annotated rows. Unannotated positives are *not* treated as a
    negative class: their typology is unknown, not absent, and folding them in
    would teach the model that two thirds of laundering looks like nothing.
    """

    params: dict = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR
    classes_: list[str] = field(default_factory=list)
    booster_: object | None = None
    n_train_: int = 0

    def fit(
        self,
        X: pd.DataFrame,
        labels: pd.Series,
        X_val: pd.DataFrame | None = None,
        labels_val: pd.Series | None = None,
    ) -> TypologyHinter:
        import xgboost as xgb

        annotated = labels.notna()
        if not annotated.any():
            raise TypologyError("no annotated rows to fit on")
        X_fit, y_fit = X[annotated.to_numpy()], labels[annotated]
        self.classes_ = sorted(y_fit.unique())
        if len(self.classes_) < 2:
            raise TypologyError(f"need at least two typologies; got {self.classes_}")
        index = {name: i for i, name in enumerate(self.classes_)}
        self.n_train_ = int(annotated.sum())

        params = dict(self.params)
        rounds = params.pop("num_boost_round")
        params["num_class"] = len(self.classes_)

        train = xgb.DMatrix(X_fit, label=y_fit.map(index).to_numpy())
        watch = [(train, "train")]
        if X_val is not None and labels_val is not None:
            seen = labels_val.notna() & labels_val.isin(self.classes_)
            if seen.any():
                watch.append(
                    (
                        xgb.DMatrix(
                            X_val[seen.to_numpy()],
                            label=labels_val[seen].map(index).to_numpy(),
                        ),
                        "val",
                    )
                )
        self.booster_ = xgb.train(
            params,
            train,
            num_boost_round=rounds,
            evals=watch,
            early_stopping_rounds=30 if len(watch) > 1 else None,
            verbose_eval=False,
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        import xgboost as xgb

        if self.booster_ is None:
            raise TypologyError("predict called before fit")
        proba = self.booster_.predict(xgb.DMatrix(X))
        return pd.DataFrame(proba, index=X.index, columns=self.classes_)

    def hint(self, X: pd.DataFrame) -> list[Hint]:
        proba = self.predict_proba(X)
        hints = []
        for _, row in proba.iterrows():
            label = str(row.idxmax())
            confidence = float(row.max())
            hints.append(
                Hint(
                    label=label if confidence >= self.confidence_floor else UNCLASSIFIED,
                    confidence=confidence,
                    distribution={k: float(v) for k, v in row.items()},
                )
            )
        return hints

    def to_metadata(self) -> dict:
        return {
            "classes": list(self.classes_),
            "n_train_rows": self.n_train_,
            "confidence_floor": self.confidence_floor,
            "deliverable": "hint, not classification",
            "limits": (
                "fitted on 2,554 annotated transactions across eight typologies; "
                "~62% of positives carry no annotation and 140 of 370 patterns "
                "straddle a split boundary"
            ),
        }
