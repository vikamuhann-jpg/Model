"""The remaining v3 section 11 leakage tests.

Completes the required seven:

    test_split_boundaries_ordered   -> test_leakage_suite.py
    test_extractor_label_blind      -> test_leakage_suite.py
    test_deterministic_split        -> test_leakage_suite.py
    test_future_edge_invariance     -> test_gfp_insertion_order.py
    test_encoder_fit_scope          -> here
    test_threshold_source           -> here
    test_label_shuffle_collapse     -> here
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from flowguard.data import schema as S
from flowguard.evaluation.sanity import shuffled_label_test
from flowguard.evaluation.thresholds import (
    ThresholdSource,
    select_thresholds,
)
from flowguard.features.transaction import CategoricalEncoder, TransactionFeatures
from flowguard.models.tuning import rolling_origin_folds
from flowguard.splits.temporal import SplitSpec, chronological_split

pytestmark = pytest.mark.leakage


# --------------------------------------------------------------------------
# test_encoder_fit_scope
# --------------------------------------------------------------------------


def test_encoder_records_its_fit_scope(transactions):
    """An encoder must be able to prove where it was fitted."""
    split = chronological_split(transactions, SplitSpec())
    train, _, _ = split.apply(transactions)

    extractor = TransactionFeatures().fit(S.feature_view(train))
    meta = extractor.to_metadata()["encoder"]

    assert meta["fit_scope"] == "train"
    assert meta["fit_rows"] == len(train)


def test_encoder_fitted_on_train_only_ignores_test_categories(transactions):
    """A category appearing only in test must not gain an encoding.

    Otherwise the encoder has seen the evaluation partition, which is a
    fit-scope violation even though no label was touched.
    """
    split = chronological_split(transactions, SplitSpec())
    train, _, test = split.apply(transactions)

    test = test.copy()
    test.loc[test.index[0], S.PAYMENT_TYPE] = "NOVEL_RAIL"

    extractor = TransactionFeatures().fit(S.feature_view(train))
    encoded = extractor.run(S.feature_view(test))

    # Unseen category maps to the sentinel, not to a fresh code.
    assert encoded.loc[test.index[0], "tx_payment_type_code"] == -1


def test_encoder_rejects_use_before_fit():
    with pytest.raises(RuntimeError, match="before fit"):
        CategoricalEncoder().transform(pd.DataFrame({S.CURRENCY: ["USD"]}))


def test_rolling_origin_folds_never_see_their_future(transactions):
    """Each fold's validation block lies strictly after its training block."""
    folds = rolling_origin_folds(transactions, n_folds=3)
    assert len(folds) >= 1

    for fold in folds:
        train = transactions.loc[fold.train_idx]
        val = transactions.loc[fold.val_idx]
        assert not train.empty and not val.empty
        assert train[S.TIMESTAMP].max() < val[S.TIMESTAMP].min(), (
            "a rolling-origin fold trained on rows after its validation window"
        )


def test_rolling_origin_training_sets_grow(transactions):
    """Successive folds extend the training prefix rather than moving it."""
    folds = rolling_origin_folds(transactions, n_folds=3)
    sizes = [len(f.train_idx) for f in folds]
    assert sizes == sorted(sizes)


# --------------------------------------------------------------------------
# test_threshold_source
# --------------------------------------------------------------------------


def test_threshold_records_validation_provenance(transactions):
    rng = np.random.default_rng(0)
    y = transactions[S.IS_LAUNDERING].to_numpy().astype(int)
    scores = rng.random(len(y))

    thresholds = select_thresholds(y, scores, (0.01, 0.05))

    assert thresholds.source is ThresholdSource.VALIDATION
    for budget in thresholds.budgets:
        assert thresholds[budget].source.value == "validation"
        assert thresholds[budget].to_metadata()["source"] == "validation"


def test_selecting_thresholds_on_test_is_refused(transactions):
    """Fitting a threshold to the partition it is scored on is not an option."""
    y = transactions[S.IS_LAUNDERING].to_numpy().astype(int)
    scores = np.random.default_rng(0).random(len(y))

    with pytest.raises(ValueError, match="refusing to select thresholds on the test"):
        select_thresholds(y, scores, (0.01,), source=ThresholdSource.TEST)


def test_threshold_alert_volume_matches_budget(transactions):
    y = transactions[S.IS_LAUNDERING].to_numpy().astype(int)
    scores = np.linspace(0, 1, len(y))

    thresholds = select_thresholds(y, scores, (0.10,))
    flagged = thresholds[0.10].apply(scores)

    assert abs(flagged.sum() - round(len(y) * 0.10)) <= 1


# --------------------------------------------------------------------------
# test_label_shuffle_collapse
# --------------------------------------------------------------------------


def test_label_shuffle_collapses_to_base_rate():
    """Training on permuted labels must destroy all signal.

    This is the highest-value leak detector available: if a model trained on
    shuffled labels still scores above the base rate, information about the
    label reaches it by some path other than the label.

    Deliberately uses a large fixture rather than the shared one. The default
    300-row frame leaves a 45-row test partition with 4 positives, where PR-AUC
    swings wildly on chance alone -- the check would be measuring sampling noise
    rather than leakage.
    """
    from tests.conftest import make_transactions

    transactions = make_transactions(n=20_000, n_accounts=400, n_patterns=40)
    split = chronological_split(transactions, SplitSpec())
    train, _, test = split.apply(transactions)

    extractor = TransactionFeatures().fit(S.feature_view(train))
    X_train = extractor.run(S.feature_view(train))
    X_test = extractor.run(S.feature_view(test))
    y_train = train[S.IS_LAUNDERING].to_numpy().astype(int)
    y_test = test[S.IS_LAUNDERING].to_numpy().astype(int)

    if y_train.sum() == 0 or y_test.sum() == 0:
        pytest.skip("fixture split left a partition without positives")

    from flowguard.models.xgb import XGBModel

    def fit_predict(xt, yt, xs):
        model = XGBModel(n_estimators=40, early_stopping_rounds=0)
        model.fit(xt, yt)
        return model.predict_raw(xs)

    result = shuffled_label_test(fit_predict, X_train, y_train, X_test, y_test)
    assert result.passed, (
        f"shuffled-label PR-AUC {result.metrics.pr_auc:.5f} exceeds the base-rate "
        "ceiling -- label information is leaking into the features"
    )


def test_shuffle_test_detects_an_injected_leak(transactions):
    """The detector must fail when a leak is deliberately introduced.

    Without this, a passing shuffle test proves nothing -- it could be passing
    because the check itself is inert.
    """
    split = chronological_split(transactions, SplitSpec())
    train, _, test = split.apply(transactions)
    y_train = train[S.IS_LAUNDERING].to_numpy().astype(int)
    y_test = test[S.IS_LAUNDERING].to_numpy().astype(int)

    if y_train.sum() == 0 or y_test.sum() == 0:
        pytest.skip("fixture split left a partition without positives")

    # A feature that is the label.
    X_train = pd.DataFrame({"leak": y_train.astype(float)}, index=train.index)
    X_test = pd.DataFrame({"leak": y_test.astype(float)}, index=test.index)

    def leaky_fit_predict(xt, yt, xs):
        return xs["leak"].to_numpy()

    result = shuffled_label_test(leaky_fit_predict, X_train, y_train, X_test, y_test)
    assert not result.passed
