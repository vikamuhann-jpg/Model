"""XGBoost classifier with calibration (plan v3 Phase 9).

Imbalance is handled with ``scale_pos_weight``, never SMOTE. Plan v3 section 15
prohibits synthetic interpolation here for a concrete reason: interpolating
between two transactions' features -- graph degrees, cycle counts, timestamps --
produces rows that could not exist, and on a temporally ordered graph it also
breaks the ordering the whole pipeline is built to respect.

Probabilities are calibrated on the validation partition, because a threshold
expressed as a probability is meaningless if the probabilities are not
calibrated.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import IsotonicRegression

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "aucpr",
    "tree_method": "hist",
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_lambda": 1.0,
    "n_jobs": 8,
    "random_state": 42,
}


def cuda_available() -> bool:
    """Whether XGBoost can actually train on a GPU here.

    Checks the build rather than just the driver: a CPU-only wheel on a machine
    with a working GPU still cannot use it, and the failure mode is a confusing
    runtime error rather than a clear one.
    """
    try:
        import xgboost as xgb

        if not xgb.build_info().get("USE_CUDA"):
            return False
        import ctypes

        ctypes.CDLL("libcuda.so.1")
        return True
    except Exception:
        return False


@dataclass
class XGBModel:
    """Thin wrapper that keeps provenance alongside the booster."""

    params: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    n_estimators: int = 300
    #: 100, not 30. GPU hist produces a flatter early validation curve on this
    #: extreme imbalance (2,856 positives in 3.55M rows), so 30 rounds of
    #: patience stops at ~80 iterations while the model is still improving --
    #: costing 22% PR-AUC (0.0461 -> 0.0371). At 100 the GPU reaches 0.0452,
    #: within 2% of CPU, at 11x the speed. See docs/ADR-005-gpu-training.md.
    early_stopping_rounds: int = 100
    use_scale_pos_weight: bool = True
    #: "auto" uses the GPU when one is usable and falls back to CPU otherwise.
    #: Measured on this machine (RTX 5060): 69.5s -> 1.8s on a 400k x 60 fit.
    #: The device is recorded in the experiment metadata, because a result that
    #: cannot be reproduced on the hardware it claims is not reproducible.
    device: str = "auto"
    resolved_device_: str | None = None

    booster_: Any = None
    calibrator_: IsotonicRegression | None = None
    feature_names_: list[str] = field(default_factory=list)
    best_iteration_: int | None = None
    train_seconds_: float | None = None
    scale_pos_weight_: float | None = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame | None = None,
        y_val: np.ndarray | None = None,
    ) -> XGBModel:
        import xgboost as xgb

        started = time.perf_counter()
        y_train = np.asarray(y_train).astype(int)
        params = dict(self.params)

        if self.device == "auto":
            self.resolved_device_ = "cuda" if cuda_available() else "cpu"
        else:
            self.resolved_device_ = self.device
            if self.device.startswith("cuda") and not cuda_available():
                warnings.warn(
                    "device='cuda' requested but no usable GPU/CUDA build was "
                    "found; falling back to CPU.",
                    stacklevel=2,
                )
                self.resolved_device_ = "cpu"
        params["device"] = self.resolved_device_

        if self.use_scale_pos_weight:
            positives = int(y_train.sum())
            negatives = len(y_train) - positives
            self.scale_pos_weight_ = (
                negatives / positives if positives else 1.0
            )
            params["scale_pos_weight"] = self.scale_pos_weight_

        self.feature_names_ = list(X_train.columns)
        # QuantileDMatrix bins up front instead of materialising the dense
        # matrix, which is what keeps 5M x ~230 float32 inside 8 GB of VRAM.
        dtrain = xgb.QuantileDMatrix(
            X_train, label=y_train, feature_names=self.feature_names_
        )

        evals = [(dtrain, "train")]
        early = None
        if X_val is not None and y_val is not None and int(np.asarray(y_val).sum()) > 0:
            dval = xgb.QuantileDMatrix(
                X_val,
                label=np.asarray(y_val).astype(int),
                feature_names=self.feature_names_,
                ref=dtrain,
            )
            evals.append((dval, "val"))
            early = self.early_stopping_rounds

        self.booster_ = xgb.train(
            params,
            dtrain,
            num_boost_round=self.n_estimators,
            evals=evals,
            early_stopping_rounds=early,
            verbose_eval=False,
        )
        self.best_iteration_ = getattr(self.booster_, "best_iteration", None)
        self.train_seconds_ = time.perf_counter() - started
        return self

    def predict_raw(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster_ is None:
            raise RuntimeError("model used before fit")
        # Move the booster to CPU for inference. Input frames live in host
        # memory, so a cuda-resident booster triggers XGBoost's device-mismatch
        # fallback and warns on every call. Predictions are unaffected: the
        # trees are fixed at training time, and GPU vs CPU inference agrees to
        # ~1e-7 (docs/ADR-005).
        self.booster_.set_param({"device": "cpu"})
        return np.asarray(self.booster_.inplace_predict(X))

    def calibrate(self, X_val: pd.DataFrame, y_val: np.ndarray) -> XGBModel:
        """Fit an isotonic calibrator on validation only."""
        raw = self.predict_raw(X_val)
        self.calibrator_ = IsotonicRegression(out_of_bounds="clip")
        self.calibrator_.fit(raw, np.asarray(y_val).astype(int))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.predict_raw(X)
        if self.calibrator_ is not None:
            return self.calibrator_.predict(raw)
        return raw

    def importance(self, top: int = 20) -> dict[str, float]:
        if self.booster_ is None:
            return {}
        scores = self.booster_.get_score(importance_type="gain")
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return dict(ranked[:top])

    def to_metadata(self) -> dict:
        return {
            "model": "XGBoost",
            "params": self.params,
            "n_estimators": self.n_estimators,
            "best_iteration": self.best_iteration_,
            "early_stopping_rounds": self.early_stopping_rounds,
            "scale_pos_weight": self.scale_pos_weight_,
            "imbalance_handling": "scale_pos_weight (SMOTE prohibited, v3 s15)",
            "calibration": (
                "isotonic, fitted on validation" if self.calibrator_ else "none"
            ),
            "n_features": len(self.feature_names_),
            "device_requested": self.device,
            "device_used": self.resolved_device_,
            "train_seconds": self.train_seconds_,
        }
