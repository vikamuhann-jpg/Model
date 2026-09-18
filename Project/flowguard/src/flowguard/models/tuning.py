"""Rolling-origin hyperparameter search (plan v3 section 15.2).

**Never k-fold.** Standard cross-validation shuffles rows across time, which
hands a fold information from after its own evaluation window and reintroduces
precisely the leakage the temporal splitter exists to prevent. Rolling-origin
instead walks forward: train on a prefix, validate on the block that follows it,
repeat.

    |-- train --|-- val --|                     fold 1
    |------ train ------|-- val --|             fold 2
    |---------- train ---------|-- val --|      fold 3

The other rule this module enforces is **equal search budget**. If one
experiment gets 40 trials and another gets 10, the ablation measures tuning
effort rather than features. The budget is fixed up front and recorded with the
result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Sequence

import numpy as np
import pandas as pd

from flowguard.data import schema as S
from flowguard.evaluation.metrics import evaluate

#: Sampled per trial. Deliberately small and interpretable -- this is a search
#: over sensible gradient-boosting settings, not an unbounded AutoML sweep.
DEFAULT_SEARCH_SPACE: dict[str, Sequence[Any]] = {
    "max_depth": [4, 6, 8, 10],
    "learning_rate": [0.03, 0.05, 0.1, 0.2],
    "subsample": [0.6, 0.8, 1.0],
    "colsample_bytree": [0.6, 0.8, 1.0],
    "min_child_weight": [1, 5, 20, 50],
    "reg_lambda": [0.5, 1.0, 5.0, 20.0],
}

DEFAULT_BUDGET = 24


@dataclass(frozen=True)
class Fold:
    train_idx: pd.Index
    val_idx: pd.Index
    val_start: pd.Timestamp
    val_end: pd.Timestamp


def rolling_origin_folds(
    df: pd.DataFrame, n_folds: int = 3, *, min_train_frac: float = 0.4
) -> list[Fold]:
    """Split ``df`` into forward-walking folds by transaction time.

    Every fold's validation block lies strictly after its training block, so no
    fold can see its own future.
    """
    if n_folds < 1:
        raise ValueError(f"n_folds must be >= 1; got {n_folds}")

    order = df[S.TIMESTAMP].sort_values(kind="stable")
    n = len(order)
    if n < n_folds * 2:
        raise ValueError(f"need at least {n_folds * 2} rows for {n_folds} folds")

    start = int(n * min_train_frac)
    block = (n - start) // n_folds
    if block < 1:
        raise ValueError("folds would be empty; reduce n_folds or min_train_frac")

    folds: list[Fold] = []
    ts = df[S.TIMESTAMP]
    for i in range(n_folds):
        train_end_pos = start + i * block
        val_end_pos = min(train_end_pos + block, n)

        # Snap to observed timestamps so an instant never spans the boundary.
        train_end = order.iloc[train_end_pos - 1]
        val_end = order.iloc[val_end_pos - 1]
        if not train_end < val_end:
            continue

        folds.append(
            Fold(
                train_idx=df.index[(ts <= train_end).to_numpy()],
                val_idx=df.index[((ts > train_end) & (ts <= val_end)).to_numpy()],
                val_start=train_end,
                val_end=val_end,
            )
        )
    if not folds:
        raise ValueError("no usable folds; timestamps may be too coarse")
    return folds


def sample_params(
    space: dict[str, Sequence[Any]], budget: int, seed: int
) -> Iterator[dict[str, Any]]:
    """Random search over ``space``. Deterministic given ``seed``.

    Random search is used rather than grid: with six dimensions a grid is either
    tiny per-dimension or astronomically large, and random sampling explores the
    dimensions that matter more efficiently at a fixed budget.
    """
    rng = np.random.default_rng(seed)
    seen: set[tuple] = set()
    emitted = 0
    attempts = 0
    while emitted < budget and attempts < budget * 50:
        attempts += 1
        candidate = {k: rng.choice(np.asarray(v, dtype=object)) for k, v in space.items()}
        key = tuple(sorted((k, str(v)) for k, v in candidate.items()))
        if key in seen:
            continue
        seen.add(key)
        emitted += 1
        yield {k: v.item() if hasattr(v, "item") else v for k, v in candidate.items()}


@dataclass
class SearchResult:
    """Outcome of a search. ``budget`` is recorded so ablations can be checked."""

    best_params: dict[str, Any]
    best_score: float
    budget: int
    n_folds: int
    trials: list[dict] = field(default_factory=list)
    seconds: float | None = None

    def to_metadata(self) -> dict:
        return {
            "search": "rolling_origin_random",
            "budget": self.budget,
            "n_folds": self.n_folds,
            "best_params": self.best_params,
            "best_mean_pr_auc": self.best_score,
            "seconds": self.seconds,
            # Full trial log is kept so a reviewer can see the search was real
            # and that every experiment got the same number of attempts.
            "trials": self.trials,
        }


def search(
    df: pd.DataFrame,
    build_features,
    *,
    base_params: dict[str, Any],
    space: dict[str, Sequence[Any]] | None = None,
    budget: int = DEFAULT_BUDGET,
    n_folds: int = 3,
    seed: int = 42,
    n_estimators: int = 300,
    early_stopping_rounds: int = 100,
) -> SearchResult:
    """Search hyperparameters on the training partition only.

    Parameters
    ----------
    df
        Training partition. Never validation or test.
    build_features
        ``(fit_df, apply_df) -> DataFrame`` -- fitted per fold on that fold's
        training rows so encoders never see their own validation block.
    """
    from flowguard.models.xgb import XGBModel

    space = space or DEFAULT_SEARCH_SPACE
    folds = rolling_origin_folds(df, n_folds=n_folds)
    started = time.perf_counter()

    trials: list[dict] = []
    best_params: dict[str, Any] = {}
    best_score = -np.inf

    for trial, candidate in enumerate(sample_params(space, budget, seed)):
        scores = []
        for fold in folds:
            tr, va = df.loc[fold.train_idx], df.loc[fold.val_idx]
            y_tr = tr[S.IS_LAUNDERING].to_numpy().astype(int)
            y_va = va[S.IS_LAUNDERING].to_numpy().astype(int)
            if y_tr.sum() == 0 or y_va.sum() == 0:
                continue

            X_tr = build_features(tr, tr)
            X_va = build_features(tr, va)

            model = XGBModel(
                params={**base_params, **candidate},
                n_estimators=n_estimators,
                early_stopping_rounds=early_stopping_rounds,
            )
            model.fit(X_tr, y_tr, X_va, y_va)
            scores.append(evaluate(y_va, model.predict_raw(X_va)).pr_auc)

        mean_score = float(np.mean(scores)) if scores else float("nan")
        trials.append(
            {"trial": trial, "params": candidate, "mean_pr_auc": mean_score,
             "fold_scores": [float(s) for s in scores]}
        )
        if scores and mean_score > best_score:
            best_score, best_params = mean_score, candidate

    return SearchResult(
        best_params=best_params,
        best_score=float(best_score) if np.isfinite(best_score) else float("nan"),
        budget=budget,
        n_folds=len(folds),
        trials=trials,
        seconds=time.perf_counter() - started,
    )
