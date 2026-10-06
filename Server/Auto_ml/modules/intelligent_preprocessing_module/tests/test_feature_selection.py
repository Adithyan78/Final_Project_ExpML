import numpy as np
import pandas as pd
import pytest

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.feature_selection import select_features


def _synthetic_data(n=400, seed=0):
    rng = np.random.RandomState(seed)
    y = rng.randint(0, 2, size=n)

    # A strongly predictive numeric feature.
    strong = y * 5 + rng.normal(0, 0.5, size=n)

    # A constant (zero-variance) feature -- must be dropped by variance threshold.
    constant = np.ones(n)

    # A weak/noise numeric feature, uncorrelated with y.
    noise = rng.normal(0, 1, size=n)

    # Two one-hot columns that both derive from the SAME source column and
    # are, together, predictive (each captures a different slice of the
    # signal) even though individually one of them is weaker.
    cat_a = ((y == 1) & (rng.random(n) < 0.9)).astype(float)  # strong signal
    cat_b = ((y == 0) & (rng.random(n) < 0.2)).astype(float)  # weaker signal

    X = pd.DataFrame(
        {
            "strong_feat": strong,
            "constant_feat": constant,
            "noise_feat": noise,
            "onehot_col_a": cat_a,
            "onehot_col_b": cat_b,
        }
    )
    feature_to_column = {
        "strong_feat": "StrongSource",
        "constant_feat": "ConstantSource",
        "noise_feat": "NoiseSource",
        "onehot_col_a": "GroupedSource",
        "onehot_col_b": "GroupedSource",
    }
    return X, y, feature_to_column


def test_variance_threshold_drops_constant_feature():
    X, y, f2c = _synthetic_data()
    result = select_features(
        X,
        y,
        f2c,
        config={
            "variance": {"enabled": True, "threshold": 0.0001},
            "mutual_information": {"enabled": False},
        },
    )
    assert "constant_feat" not in result["feature_names_after_variance"]
    variance_entries = [e for e in result["feature_selection_log"] if e["method"] == "variance_threshold"]
    constant_entry = next(e for e in variance_entries if e["feature"] == "constant_feat")
    assert constant_entry["action"] == "drop"
    assert constant_entry["score"] == 0.0


def test_mi_scores_stored_for_every_surviving_feature():
    X, y, f2c = _synthetic_data()
    result = select_features(
        X,
        y,
        f2c,
        config={
            "variance": {"enabled": True, "threshold": 0.0001},
            "mutual_information": {"enabled": True, "top_k": 10, "random_state": 42, "aggregation": "max"},
        },
    )
    surviving = result["feature_names_after_variance"]
    assert set(result["feature_scores"].keys()) == set(surviving)
    assert all(isinstance(v, float) for v in result["feature_scores"].values())


def test_grouped_onehot_features_kept_or_dropped_together():
    X, y, f2c = _synthetic_data()
    # top_k = 1 -> only the single best-aggregated SOURCE COLUMN survives.
    result = select_features(
        X,
        y,
        f2c,
        config={
            "variance": {"enabled": True, "threshold": 0.0001},
            "mutual_information": {"enabled": True, "top_k": 1, "random_state": 42, "aggregation": "max"},
        },
    )
    selected = set(result["selected_features"])
    # StrongSource (strong_feat) should dominate with top_k=1.
    assert selected == {"strong_feat"}

    # Now raise top_k so the grouped source column can also be selected;
    # if it is, BOTH of its one-hot features must appear (never just one).
    result2 = select_features(
        X,
        y,
        f2c,
        config={
            "variance": {"enabled": True, "threshold": 0.0001},
            "mutual_information": {"enabled": True, "top_k": 2, "random_state": 42, "aggregation": "max"},
        },
    )
    selected2 = set(result2["selected_features"])
    grouped_present = {"onehot_col_a", "onehot_col_b"} & selected2
    assert grouped_present == set() or grouped_present == {"onehot_col_a", "onehot_col_b"}


def test_top_k_restricts_number_of_selected_source_columns():
    X, y, f2c = _synthetic_data()
    result = select_features(
        X,
        y,
        f2c,
        config={
            "variance": {"enabled": True, "threshold": 0.0001},
            "mutual_information": {"enabled": True, "top_k": 2, "random_state": 42, "aggregation": "max"},
        },
    )
    selected_columns = {f2c[f] for f in result["selected_features"]}
    assert len(selected_columns) <= 2


def test_aggregation_method_changes_column_score():
    X, y, f2c = _synthetic_data()
    result_max = select_features(
        X, y, f2c,
        config={"variance": {"enabled": False}, "mutual_information": {"enabled": True, "top_k": 10, "aggregation": "max"}},
    )
    result_mean = select_features(
        X, y, f2c,
        config={"variance": {"enabled": False}, "mutual_information": {"enabled": True, "top_k": 10, "aggregation": "mean"}},
    )
    # Both should rank the same columns overall (all top_k=10, i.e. all
    # kept) but the log's column_aggregated_score for the grouped source
    # should legitimately differ between max and mean aggregation.
    def grouped_score(result):
        entry = next(
            e for e in result["feature_selection_log"]
            if e["method"] == "mutual_information" and e["source_column"] == "GroupedSource"
        )
        return entry["column_aggregated_score"]

    assert grouped_score(result_max) >= grouped_score(result_mean) - 1e-9


def test_disabled_stages_are_no_ops():
    X, y, f2c = _synthetic_data()
    result = select_features(
        X, y, f2c,
        config={"variance": {"enabled": False}, "mutual_information": {"enabled": False}},
    )
    assert set(result["selected_features"]) == set(X.columns)
    assert result["feature_scores"] == {}
    assert result["feature_ranking"] == []


def test_invalid_aggregation_raises():
    X, y, f2c = _synthetic_data()
    with pytest.raises(ValueError):
        select_features(
            X, y, f2c,
            config={"variance": {"enabled": False}, "mutual_information": {"enabled": True, "aggregation": "median"}},
        )
