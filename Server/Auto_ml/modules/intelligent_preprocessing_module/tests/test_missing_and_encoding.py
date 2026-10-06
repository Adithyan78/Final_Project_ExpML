import numpy as np

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import PreprocessingEngine


def test_high_missing_column_dropped(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    assert "Cabin" in engine.dropped_columns_
    assert not any(p["source_column"] == "Cabin" for p in result["feature_provenance"])


def test_id_like_columns_dropped(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)

    assert "PassengerId" in engine.dropped_columns_
    assert "Name" in engine.dropped_columns_


def test_age_missing_values_imputed(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    assert X_train["Age"].isna().any()  # sanity: fixture really has NaNs

    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)
    data = result["data"]

    age_like_cols = [c for c in engine.all_feature_names_ if c == "Age"]
    assert age_like_cols, "Age should survive as an output feature name"
    # Look at the full transformed frame (pre-selection) via the engine's
    # internal all_feature_names_ + column_transformer, since 'data' may
    # have filtered Age out during feature selection -- either way, the
    # ColumnTransformer's own output must contain no NaNs for Age.
    full = engine.column_transformer_.transform(X_train)
    import pandas as pd

    full_df = pd.DataFrame(full, columns=engine.all_feature_names_)
    assert not full_df["Age"].isna().any()


def test_embarked_missing_values_imputed(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    embarked_outputs = [f for f in engine.all_feature_names_ if f.startswith("Embarked")]
    assert len(embarked_outputs) > 0
    full = engine.column_transformer_.transform(X_train)
    import pandas as pd

    full_df = pd.DataFrame(full, columns=engine.all_feature_names_)
    assert not full_df[embarked_outputs].isna().any().any()


def test_sex_one_hot_encoded(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    sex_outputs = [f for f in engine.all_feature_names_ if f.startswith("Sex")]
    assert len(sex_outputs) >= 1  # OneHotEncoder with 2 categories -> >=1 dummy col


def test_high_cardinality_ticket_target_encoded(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    ticket_decisions = engine.decisions_by_column_["Ticket"]
    encoding_decision = next(d for d in ticket_decisions if d.stage == "encoding")
    assert encoding_decision.action == "target_encode"
    assert encoding_decision.rule_id == "high_cardinality"


def test_user_override_changes_age_imputation_strategy(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(
        X_train, y_train, titanic_profile, user_config={"Age": {"action": "impute_mean"}}
    )
    age_decisions = engine.decisions_by_column_["Age"]
    missing_decision = next(d for d in age_decisions if d.stage == "missing")
    assert missing_decision.action == "impute_mean"
    assert missing_decision.source == "user_override"
