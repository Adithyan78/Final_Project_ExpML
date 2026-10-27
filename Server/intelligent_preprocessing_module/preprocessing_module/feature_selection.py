"""Post-preprocessing feature selection.

Pipeline (each stage independently toggle-able via config):

    1. VarianceThreshold       -- drop near-constant output features.
    2. mutual_info_classif     -- score every SURVIVING feature against
                                   y_train (train-only, by construction:
                                   the caller only ever passes y_train).
    3. Column-aware Top-K      -- individual one-hot/derived features are
                                   aggregated back to their SOURCE COLUMN
                                   (max/mean/sum, configurable), columns
                                   are ranked by that aggregated score, and
                                   the top-K source columns are kept. If a
                                   source column is kept, ALL of its
                                   surviving output features are kept too
                                   (per spec: "If a source column is
                                   selected, retain all of its transformed
                                   features.").

Every score computed here is stored, for every surviving feature -- not
just the ones ultimately selected -- so the log is auditable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold, mutual_info_classif

_VALID_AGGREGATIONS = ("max", "mean", "sum")


def _default_config() -> Dict[str, Any]:
    return {
        "variance": {"enabled": True, "threshold": 0.0},
        "mutual_information": {
            "enabled": True,
            "top_k": 10,
            "random_state": 42,
            "aggregation": "max",
        },
    }


def _merge_config(user_cfg: Dict[str, Any] = None) -> Dict[str, Any]:
    cfg = _default_config()
    if not user_cfg:
        return cfg
    for section in ("variance", "mutual_information"):
        if section in user_cfg:
            cfg[section].update(user_cfg[section])
    return cfg


def select_features(
    X: pd.DataFrame,
    y,
    feature_to_column: Dict[str, str],
    config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Returns a dict with keys:
        selected_features, feature_scores, feature_ranking,
        feature_selection_log, variance_selector, feature_names_after_variance
    """
    cfg = _merge_config(config)
    log: List[Dict[str, Any]] = []
    feature_names = list(X.columns)

    # ---- 1. Variance threshold -------------------------------------------------
    variance_cfg = cfg["variance"]
    variance_selector = None
    if variance_cfg.get("enabled", True) and len(feature_names) > 0:
        threshold = float(variance_cfg.get("threshold", 0.0))
        variance_selector = VarianceThreshold(threshold=threshold)
        variance_selector.fit(X.values)
        variances = variance_selector.variances_
        support = variance_selector.get_support()
        for feat, var, keep in zip(feature_names, variances, support):
            log.append(
                {
                    "feature": feat,
                    "source_column": feature_to_column.get(feat, feat),
                    "method": "variance_threshold",
                    "score": float(var),
                    "action": "keep" if keep else "drop",
                    "reason": (
                        f"Variance {var:.6g} "
                        f"{'>' if keep else '<='} threshold {threshold:g}."
                    ),
                }
            )
        surviving_features = [f for f, keep in zip(feature_names, support) if keep]
    else:
        surviving_features = list(feature_names)
        for feat in feature_names:
            log.append(
                {
                    "feature": feat,
                    "source_column": feature_to_column.get(feat, feat),
                    "method": "variance_threshold",
                    "score": None,
                    "action": "keep",
                    "reason": "Variance filtering disabled.",
                }
            )

    X_after_variance = X.loc[:, surviving_features] if surviving_features else X.iloc[:, 0:0]

    # ---- 2. Mutual information --------------------------------------------------
    mi_cfg = cfg["mutual_information"]
    feature_scores: Dict[str, float] = {}
    feature_ranking: List[str] = []
    selected_features: List[str] = list(surviving_features)

    if mi_cfg.get("enabled", True) and len(surviving_features) > 0:
        random_state = mi_cfg.get("random_state", 42)
        mi_scores = mutual_info_classif(
            X_after_variance.values, y, random_state=random_state
        )
        feature_scores = {
            feat: float(score) for feat, score in zip(surviving_features, mi_scores)
        }

        # ---- aggregate to source-column level ----
        aggregation = mi_cfg.get("aggregation", "max")
        if aggregation not in _VALID_AGGREGATIONS:
            raise ValueError(
                f"Unknown mutual_information.aggregation {aggregation!r}; "
                f"expected one of {_VALID_AGGREGATIONS}."
            )

        scores_by_column: Dict[str, List[float]] = {}
        for feat, score in feature_scores.items():
            col = feature_to_column.get(feat, feat)
            scores_by_column.setdefault(col, []).append(score)

        agg_fn = {"max": max, "mean": (lambda xs: sum(xs) / len(xs)), "sum": sum}[
            aggregation
        ]
        column_scores = {col: agg_fn(scores) for col, scores in scores_by_column.items()}

        # Deterministic ranking: score desc, ties broken by column name.
        feature_ranking = sorted(
            column_scores.keys(), key=lambda c: (-column_scores[c], c)
        )

        top_k = mi_cfg.get("top_k", 10)
        selected_columns = set(feature_ranking[: max(int(top_k), 0)])

        selected_features = [
            f for f in surviving_features if feature_to_column.get(f, f) in selected_columns
        ]

        for feat in surviving_features:
            col = feature_to_column.get(feat, feat)
            rank = feature_ranking.index(col) + 1
            selected = col in selected_columns
            log.append(
                {
                    "feature": feat,
                    "source_column": col,
                    "method": "mutual_information",
                    "score": feature_scores[feat],
                    "column_aggregated_score": column_scores[col],
                    "rank": rank,
                    "action": "keep" if selected else "drop",
                    "reason": (
                        f"Column '{col}' ranked #{rank} by {aggregation}-aggregated "
                        f"mutual information "
                        + (
                            f"and is within the configured top_k={top_k}."
                            if selected
                            else f"which falls outside the configured top_k={top_k}."
                        )
                    ),
                }
            )
    else:
        for feat in surviving_features:
            log.append(
                {
                    "feature": feat,
                    "source_column": feature_to_column.get(feat, feat),
                    "method": "mutual_information",
                    "score": None,
                    "action": "keep",
                    "reason": "Mutual-information selection disabled.",
                }
            )

    return {
        "selected_features": selected_features,
        "feature_scores": feature_scores,
        "feature_ranking": feature_ranking,
        "feature_selection_log": log,
        "variance_selector": variance_selector,
        "feature_names_after_variance": surviving_features,
    }
