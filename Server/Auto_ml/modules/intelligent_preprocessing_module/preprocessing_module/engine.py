"""The public entry point of the Intelligent Preprocessing Module.

    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, analyzer_profile, user_config=None)
    X_test_final = engine.transform(X_test)

Design principle:  YAML decides -> Python executes -> provenance tracks -> logs record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from .action_registry import ActionRegistry
from .exceptions import EngineNotFittedError, LeakageError
from .feature_selection import select_features
from .pipeline_builder import build_column_transformer
from .profile_adapter import build_all_column_facts, target_column_name
from .provenance import build_feature_provenance
from .rule_engine import Decision, decide_all
from .rule_loader import load_ruleset

_PACKAGE_DIR = Path(__file__).parent
_DEFAULT_RULES_PATH = _PACKAGE_DIR / "config" / "default_rules.yaml"
_DEFAULT_FEATURE_SELECTION_PATH = _PACKAGE_DIR / "config" / "default_feature_selection.yaml"


def _load_default_feature_selection_config() -> Dict[str, Any]:
    import yaml

    with open(_DEFAULT_FEATURE_SELECTION_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["feature_selection"]


class FittedFeatureSelector:
    """Lightweight container standing in for `feature_selector` in the
    result dict. Not a full sklearn estimator (feature selection here
    spans several stages -- variance, MI, column-aware top-K -- that
    don't reduce to a single sklearn `.transform()` call) but it exposes
    the same information a caller would want to inspect or re-apply.
    """

    def __init__(
        self,
        variance_selector,
        feature_names_after_variance: List[str],
        selected_features: List[str],
        config: Dict[str, Any],
    ):
        self.variance_selector = variance_selector
        self.feature_names_after_variance = feature_names_after_variance
        self.selected_features = selected_features
        self.config = config

    def transform_columns(self, all_feature_names: List[str]) -> List[str]:
        """Given the full set of feature names a fitted ColumnTransformer
        would produce, return just the ones this selector kept."""
        selected = set(self.selected_features)
        return [f for f in all_feature_names if f in selected]


class PreprocessingEngine:
    def __init__(
        self,
        rules: Optional[Union[str, Path, Dict[str, Any]]] = None,
        feature_selection_config: Optional[Dict[str, Any]] = None,
        action_registry: Optional[ActionRegistry] = None,
        action_params: Optional[Dict[str, Any]] = None,
    ):
        self.action_registry = action_registry or ActionRegistry()
        rules_source = rules if rules is not None else _DEFAULT_RULES_PATH
        self.ruleset = load_ruleset(
            rules_source, known_actions=self.action_registry.known_action_names()
        )
        self.feature_selection_config = (
            feature_selection_config
            if feature_selection_config is not None
            else _load_default_feature_selection_config()
        )
        self.action_params = action_params or {}

        # Fitted state (populated by fit_transform)
        self.column_transformer_ = None
        self.decisions_by_column_: Dict[str, List[Decision]] = {}
        self.dropped_columns_: List[str] = []
        self.original_columns_: List[str] = []
        self.all_feature_names_: List[str] = []
        self.selected_features_: List[str] = []
        self.feature_provenance_: List[Dict[str, Any]] = []
        self.feature_selector_: Optional[FittedFeatureSelector] = None
        self._is_fitted = False

    # ------------------------------------------------------------------
    def fit_transform(
        self,
        X_train: pd.DataFrame,
        y_train,
        analyzer_profile: Dict[str, Any],
        user_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(X_train, pd.DataFrame):
            raise TypeError(
                "X_train must be a pandas DataFrame with named columns matching "
                "the analyzer_profile."
            )

        preprocessing_log: List[Dict[str, Any]] = []

        X_train = X_train.copy()
        tgt_name = target_column_name(analyzer_profile)
        if tgt_name and tgt_name in X_train.columns:
            # Defense in depth: the target must never be used as an input
            # feature, even if the caller accidentally left it in X.
            X_train = X_train.drop(columns=[tgt_name])
            preprocessing_log.append(
                {
                    "column": tgt_name,
                    "stage": "system",
                    "action": "drop_column",
                    "reason": (
                        f"'{tgt_name}' is the target column and was removed from "
                        f"the feature set to prevent target leakage."
                    ),
                    "rule_id": None,
                    "source": "system",
                }
            )

        columns = list(X_train.columns)
        column_facts = build_all_column_facts(analyzer_profile, columns)

        decisions_by_column = decide_all(
            columns,
            column_facts,
            self.ruleset,
            self.action_registry,
            user_config=user_config,
        )
        for col_decisions in decisions_by_column.values():
            preprocessing_log.extend(d.to_dict() for d in col_decisions)

        column_transformer, dropped_columns = build_column_transformer(
            columns, decisions_by_column, self.action_registry, self.action_params
        )

        y_arr = np.asarray(y_train)
        transformed = column_transformer.fit_transform(X_train, y_arr)
        transformed = np.asarray(transformed)

        all_feature_names = list(column_transformer.get_feature_names_out())
        X_transformed = pd.DataFrame(
            transformed, columns=all_feature_names, index=X_train.index
        )

        feature_provenance = build_feature_provenance(column_transformer, decisions_by_column)
        feature_to_column = {
            p["output_feature"]: p["source_column"] for p in feature_provenance
        }

        selection_result = select_features(
            X_transformed, y_arr, feature_to_column, self.feature_selection_config
        )
        selected_features = selection_result["selected_features"]

        final_data = X_transformed.loc[:, selected_features]

        # ---- persist fitted state ----
        self.column_transformer_ = column_transformer
        self.decisions_by_column_ = decisions_by_column
        self.dropped_columns_ = dropped_columns
        self.original_columns_ = columns
        self.all_feature_names_ = all_feature_names
        self.selected_features_ = selected_features
        self.feature_provenance_ = feature_provenance
        self.feature_selector_ = FittedFeatureSelector(
            variance_selector=selection_result["variance_selector"],
            feature_names_after_variance=selection_result["feature_names_after_variance"],
            selected_features=selected_features,
            config=self.feature_selection_config,
        )
        self._is_fitted = True

        for col in dropped_columns:
            preprocessing_log.append(
                {
                    "column": col,
                    "stage": "system",
                    "action": "dropped_from_output",
                    "reason": f"Column '{col}' produced zero output features (dropped upstream).",
                    "rule_id": None,
                    "source": "system",
                }
            )

        return {
            "data": final_data,
            "preprocessing_log": preprocessing_log,
            "feature_selection_log": selection_result["feature_selection_log"],
            "feature_scores": selection_result["feature_scores"],
            "feature_ranking": selection_result["feature_ranking"],
            "selected_features": selected_features,
            "feature_provenance": feature_provenance,
            "preprocessor": column_transformer,
            "feature_selector": self.feature_selector_,
        }

    # ------------------------------------------------------------------
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self._is_fitted:
            raise EngineNotFittedError(
                "PreprocessingEngine.transform() called before fit_transform()."
            )
        if not isinstance(X, pd.DataFrame):
            raise TypeError("X must be a pandas DataFrame.")

        missing_cols = [c for c in self.original_columns_ if c not in X.columns]
        if missing_cols:
            raise LeakageError(
                f"Cannot transform: input is missing column(s) seen during "
                f"fit_transform: {missing_cols}."
            )

        X = X.loc[:, self.original_columns_].copy()

        # `.transform()` on a fitted ColumnTransformer never refits any of
        # its sub-transformers -- this is what makes it leakage-safe for
        # target encoding, imputation statistics, and scaler parameters.
        transformed = self.column_transformer_.transform(X)
        transformed = np.asarray(transformed)

        X_transformed = pd.DataFrame(
            transformed, columns=self.all_feature_names_, index=X.index
        )
        return X_transformed.loc[:, self.selected_features_]
