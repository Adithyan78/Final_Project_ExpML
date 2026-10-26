import pytest

from automl_trainer import TrainingConfig
from automl_trainer.selector import evaluate_condition, load_rules, select_candidates

CTX = {"task": "classification", "n_rows": 500, "n_features": 10, "feature_row_ratio": 0.02,
       "binary_share": 0.5, "onehot_share": 0.5, "imbalanced": False, "has_categorical_source": False,
       "has_numeric_source": True, "max_abs_num_corr": 0.5, "max_target_association": 0.3,
       "outlier_heavy": False, "highly_skewed": False}


def test_config_validation():
    with pytest.raises(ValueError):
        TrainingConfig(cv_splits=1)
    with pytest.raises(ValueError):
        TrainingConfig(task="clustering")
    with pytest.raises(ValueError, match="Unknown config keys"):
        TrainingConfig.from_dict({"nope": 1})


def test_config_from_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("cv_splits: 3\ntune: false\nexclude: [KNN]\n")
    cfg = TrainingConfig.from_file(p)
    assert cfg.cv_splits == 3 and cfg.tune is False and cfg.exclude == ("KNN",)


def test_condition_evaluator():
    assert evaluate_condition({"metric": "n_rows", "op": "<", "value": 1000}, CTX)
    assert not evaluate_condition({"all": [{"metric": "n_rows", "op": "<", "value": 1000},
                                           {"metric": "imbalanced", "op": "==", "value": True}]}, CTX)
    assert evaluate_condition({"any": [{"metric": "imbalanced", "op": "==", "value": True},
                                       {"metric": "n_features", "op": "<=", "value": 10}]}, CTX)
    with pytest.raises(KeyError):
        evaluate_condition({"metric": "bogus", "op": "<", "value": 1}, CTX)
    with pytest.raises(ValueError):
        evaluate_condition({"metric": "n_rows", "op": "~", "value": 1}, CTX)


def test_all_default_rules_evaluate_on_a_full_context():
    for rule in load_rules()["rules"]:
        evaluate_condition(rule["when"], CTX)  # no unknown metrics anywhere in rules.yaml


def test_selection_responds_to_dataset_size():
    cfg = TrainingConfig()
    small = select_candidates(CTX, cfg)
    big = select_candidates({**CTX, "n_rows": 500_000}, cfg)
    assert "SVC" in small["shortlist"] and "SVC" in big["excluded"]
    assert big["scores"]["HistGradientBoosting"]["score"] > small["scores"]["HistGradientBoosting"]["score"]
    assert small["scores"]["LogisticRegression"]["reasons"]  # explanation is recorded


def test_include_only_and_exclude():
    sel = select_candidates(CTX, TrainingConfig(include_only=("RandomForest", "LogisticRegression")))
    assert set(sel["shortlist"]) == {"RandomForest", "LogisticRegression"}
    sel = select_candidates(CTX, TrainingConfig(exclude=("RandomForest",)))
    assert "RandomForest" not in sel["shortlist"]
