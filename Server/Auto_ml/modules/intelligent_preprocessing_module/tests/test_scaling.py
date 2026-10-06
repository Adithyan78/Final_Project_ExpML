import numpy as np
import pandas as pd

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import PreprocessingEngine


def test_fare_high_outliers_uses_robust_scale(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    fare_decisions = engine.decisions_by_column_["Fare"]
    scaling_decision = next(d for d in fare_decisions if d.stage == "scaling")
    assert scaling_decision.action == "robust_scale"
    assert scaling_decision.rule_id == "high_outlier_robust_scale"


def test_age_moderate_outliers_uses_standard_scale(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    age_decisions = engine.decisions_by_column_["Age"]
    scaling_decision = next(d for d in age_decisions if d.stage == "scaling")
    assert scaling_decision.action == "standard_scale"
    assert scaling_decision.rule_id == "default_numeric_scale"


def test_standard_scaled_output_is_roughly_standardized(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    full = engine.column_transformer_.transform(X_train)
    full_df = pd.DataFrame(full, columns=engine.all_feature_names_)
    age_mean = full_df["Age"].astype(float).mean()
    age_std = full_df["Age"].astype(float).std(ddof=0)
    assert abs(age_mean) < 1e-6
    assert abs(age_std - 1.0) < 1e-6
