import numpy as np
import pandas as pd

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import PreprocessingEngine


def test_full_pipeline_runs_and_produces_clean_output(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()

    result = engine.fit_transform(X_train, y_train, titanic_profile)
    X_test_final = engine.transform(X_test)

    data = result["data"]
    assert isinstance(data, pd.DataFrame)
    assert len(data) == len(X_train)
    assert not data.isna().any().any()
    assert not X_test_final.isna().any().any()

    # Required output keys per spec.
    for key in (
        "data",
        "preprocessing_log",
        "feature_selection_log",
        "feature_scores",
        "feature_ranking",
        "selected_features",
        "feature_provenance",
        "preprocessor",
        "feature_selector",
    ):
        assert key in result

    # Every selected feature must be traceable to a source column.
    prov_map = {p["output_feature"]: p["source_column"] for p in result["feature_provenance"]}
    for feat in result["selected_features"]:
        assert feat in prov_map


def test_preprocessing_log_entries_have_required_fields(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    for entry in result["preprocessing_log"]:
        assert "column" in entry
        assert "action" in entry
        assert "reason" in entry
        assert "stage" in entry


def test_feature_selection_log_entries_have_required_fields(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    for entry in result["feature_selection_log"]:
        assert "method" in entry
        assert "action" in entry
        assert "reason" in entry
        assert "score" in entry or "column_aggregated_score" in entry


def test_top_k_ten_keeps_at_most_ten_source_columns(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    prov_map = {p["output_feature"]: p["source_column"] for p in result["feature_provenance"]}
    selected_source_columns = {prov_map[f] for f in result["selected_features"]}
    assert len(selected_source_columns) <= 10


def test_engine_respects_custom_rules_and_feature_selection_config(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    custom_rules = """
version: "1.0"
rules:
  - id: drop_everything_high_missing
    priority: 900
    stage: missing
    condition: "column.missing_pct > 50"
    action: "drop_column"
    reason: "Column {col} exceeds 50% missing."
  - id: numeric_impute
    priority: 100
    stage: missing
    condition: "column.type == 'numeric'"
    action: "impute_mean"
    reason: "Default numeric imputation."
  - id: numeric_scale
    priority: 100
    stage: scaling
    condition: "column.type == 'numeric'"
    action: "minmax_scale"
    reason: "Default min-max scaling."
  - id: cat_encode
    priority: 100
    stage: encoding
    condition: "column.type == 'categorical'"
    action: "one_hot"
    reason: "Default one-hot encoding."
"""
    engine = PreprocessingEngine(
        rules=custom_rules,
        feature_selection_config={
            "variance": {"enabled": False},
            "mutual_information": {"enabled": True, "top_k": 3, "random_state": 1, "aggregation": "mean"},
        },
    )
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    prov_map = {p["output_feature"]: p["source_column"] for p in result["feature_provenance"]}
    selected_source_columns = {prov_map[f] for f in result["selected_features"]}
    assert len(selected_source_columns) <= 3

    age_decisions = engine.decisions_by_column_["Age"]
    scaling_decision = next(d for d in age_decisions if d.stage == "scaling")
    assert scaling_decision.action == "minmax_scale"
