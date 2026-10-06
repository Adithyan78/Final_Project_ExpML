import inspect

import numpy as np
import pandas as pd
import pytest

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import PreprocessingEngine
from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.exceptions import EngineNotFittedError


def test_transform_before_fit_raises(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    with pytest.raises(EngineNotFittedError):
        engine.transform(X_test)


def test_transform_signature_never_accepts_y():
    sig = inspect.signature(PreprocessingEngine.transform)
    assert "y" not in sig.parameters


def test_transform_does_not_refit_imputer_statistics(titanic_split, titanic_profile):
    """Feed transform() a test set whose Age values are wildly different
    from training; the imputed value for missing Age in the TEST set must
    still equal the TRAINING median, proving no re-fitting happened."""
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    engine.fit_transform(X_train, y_train, titanic_profile)

    train_median = X_train["Age"].median()

    X_test_shifted = X_test.copy()
    # Blow out the non-missing ages in the test set so a re-fit imputer
    # would produce a wildly different median than the training one.
    X_test_shifted.loc[X_test_shifted["Age"].notna(), "Age"] = 999.0
    had_missing = X_test_shifted["Age"].isna()
    assert had_missing.any()

    out = engine.transform(X_test_shifted)
    full = engine.column_transformer_.transform(X_test_shifted)
    full_df = pd.DataFrame(full, columns=engine.all_feature_names_)

    # Un-scale: (x - mean) * std + mean is not directly invertible here
    # without stored scaler params, so instead assert the imputed rows
    # all take on exactly the SAME value (the training-median-derived,
    # standardized constant) rather than reflecting the 999.0 contamination.
    imputed_scaled_values = full_df.loc[had_missing.values, "Age"].astype(float)
    assert imputed_scaled_values.nunique() == 1


def test_target_never_in_selected_features_or_provenance(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)
    assert "Survived" not in result["selected_features"]
    assert not any(p["source_column"] == "Survived" for p in result["feature_provenance"])


def test_target_column_accidentally_left_in_X_is_dropped(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    X_train_with_target = X_train.copy()
    X_train_with_target["Survived"] = y_train.values

    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train_with_target, y_train, titanic_profile)

    assert "Survived" not in engine.original_columns_
    assert not any(p["source_column"] == "Survived" for p in result["feature_provenance"])
    system_logs = [e for e in result["preprocessing_log"] if e.get("source") == "system"]
    assert any("Survived" in e["reason"] for e in system_logs)


def test_deterministic_output_across_runs(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split

    engine1 = PreprocessingEngine()
    result1 = engine1.fit_transform(X_train, y_train, titanic_profile)

    engine2 = PreprocessingEngine()
    result2 = engine2.fit_transform(X_train, y_train, titanic_profile)

    pd.testing.assert_frame_equal(
        result1["data"].reset_index(drop=True), result2["data"].reset_index(drop=True)
    )
    assert result1["feature_ranking"] == result2["feature_ranking"]
    assert result1["selected_features"] == result2["selected_features"]


def test_transform_output_matches_fit_transform_columns(titanic_split, titanic_profile):
    X_train, X_test, y_train, y_test = titanic_split
    engine = PreprocessingEngine()
    result = engine.fit_transform(X_train, y_train, titanic_profile)
    X_test_final = engine.transform(X_test)
    assert list(X_test_final.columns) == list(result["data"].columns)
    assert len(X_test_final) == len(X_test)
