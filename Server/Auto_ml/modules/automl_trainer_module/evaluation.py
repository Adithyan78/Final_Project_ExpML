"""Metrics, cross-validation, ranking and held-out evaluation."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    make_scorer,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import (
    KFold,
    RepeatedKFold,
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_validate,
)

log = logging.getLogger("automl_trainer")

LOWER_IS_BETTER = {"rmse", "mae"}


def scorers_for(task: str, n_classes: int) -> dict:
    if task == "regression":
        return {"r2": "r2", "rmse": "neg_root_mean_squared_error", "mae": "neg_mean_absolute_error"}
    return {
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "f1": make_scorer(f1_score, average="weighted", zero_division=0),
        "precision": make_scorer(precision_score, average="weighted", zero_division=0),
        "recall": make_scorer(recall_score, average="weighted", zero_division=0),
        "roc_auc": "roc_auc_ovr_weighted" if n_classes > 2 else "roc_auc",
    }


def default_primary(task: str) -> str:
    return "accuracy" if task == "classification" else "r2"


def secondary_metric(task: str, primary: str) -> str:
    if task == "classification":
        return "f1" if primary != "f1" else "balanced_accuracy"
    return "rmse" if primary != "rmse" else "r2"


def make_splitter(task: str, y: pd.Series, splits: int, repeats: int, seed: int):
    if task == "classification":
        min_count = int(y.value_counts().min())
        if min_count < splits:
            splits = max(2, min_count)
            log.warning("Smallest class has %d rows; using %d CV folds.", min_count, splits)
        if repeats > 1:
            return RepeatedStratifiedKFold(n_splits=splits, n_repeats=repeats, random_state=seed)
        return StratifiedKFold(n_splits=splits, shuffle=True, random_state=seed)
    if repeats > 1:
        return RepeatedKFold(n_splits=splits, n_repeats=repeats, random_state=seed)
    return KFold(n_splits=splits, shuffle=True, random_state=seed)


def cv_evaluate(est, X, y, cv, scorers: dict, n_jobs: int) -> dict:
    """Cross-validate; return mean/std per metric (errors reported positive), train scores, timings."""
    res = cross_validate(est, X, y, cv=cv, scoring=scorers, n_jobs=n_jobs,
                         return_train_score=True, error_score="raise")
    out: dict[str, float] = {}
    for m in scorers:
        sign = -1.0 if m in LOWER_IS_BETTER else 1.0
        test, train = sign * res[f"test_{m}"], sign * res[f"train_{m}"]
        out[f"cv_{m}_mean"], out[f"cv_{m}_std"] = float(test.mean()), float(test.std())
        out[f"train_{m}_mean"] = float(train.mean())
    out["cv_fit_time_s"] = float(res["fit_time"].mean())
    out["cv_score_time_s"] = float(res["score_time"].mean())
    return out


def is_better(a: float, b: float, metric: str, margin: float = 0.0) -> bool:
    return a < b - margin if metric in LOWER_IS_BETTER else a > b + margin


def rank_key(rec: dict, primary: str, secondary: str):
    """Sort key, best first: primary metric, secondary metric, lower variance, faster."""
    sp = -1.0 if primary in LOWER_IS_BETTER else 1.0
    ss = -1.0 if secondary in LOWER_IS_BETTER else 1.0
    return (-sp * rec[f"cv_{primary}_mean"], -ss * rec[f"cv_{secondary}_mean"],
            rec[f"cv_{primary}_std"], rec["cv_fit_time_s"])


def overfit_gap(rec: dict, primary: str) -> float:
    gap = rec[f"train_{primary}_mean"] - rec[f"cv_{primary}_mean"]
    return -gap if primary in LOWER_IS_BETTER else gap


def test_metrics(model, X, y_enc: np.ndarray, task: str) -> dict:
    """Score a fitted model once on held-out data. Classification y must be label-encoded."""
    pred = model.predict(X)
    if task == "regression":
        return {"r2": float(r2_score(y_enc, pred)),
                "rmse": float(root_mean_squared_error(y_enc, pred)),
                "mae": float(mean_absolute_error(y_enc, pred))}
    out = {
        "accuracy": float(accuracy_score(y_enc, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_enc, pred)),
        "precision": float(precision_score(y_enc, pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_enc, pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_enc, pred, average="weighted", zero_division=0)),
        "roc_auc": None,
    }
    try:
        has_proba = hasattr(model, "predict_proba")
        score = model.predict_proba(X) if has_proba else model.decision_function(X)
        if score.ndim == 1 or score.shape[1] == 2:
            col = score if score.ndim == 1 else score[:, 1]
            out["roc_auc"] = float(roc_auc_score(y_enc, col))
        elif has_proba:
            out["roc_auc"] = float(roc_auc_score(y_enc, score, multi_class="ovr", average="weighted"))
    except Exception:  # class missing from the test split, etc.
        pass
    return out


def classification_details(model, X, y_enc, class_names: list) -> dict:
    pred = model.predict(X)
    return {
        "classes": class_names,
        "confusion_matrix": confusion_matrix(y_enc, pred).tolist(),
        "classification_report": classification_report(
            y_enc, pred, target_names=[str(c) for c in class_names], output_dict=True, zero_division=0),
    }
