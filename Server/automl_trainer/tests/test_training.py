import json

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification

import automl_trainer as at
from automl_trainer import registry
from automl_trainer.cli import main as cli_main
from conftest import FAST, write_dataset


def run(d, out=None, **kw):
    return at.run_from_directory(d, out, config=at.TrainingConfig(**{**FAST, **kw}))


def test_classification_end_to_end(clf_dir, tmp_path):
    out = tmp_path / "out"
    res = run(clf_dir, out)
    s = res.summary
    assert s["task"] == "classification" and s["primary_metric"] == "accuracy"
    assert s["best_cv_score"] > s["baseline_cv_score"]
    assert s["best_test_metrics"]["accuracy"] > 0.7
    for f in ("best_model.joblib", "run_summary.json", "leaderboard.csv", "selection_report.json",
              "training_results.json", "test_evaluation.json", "manifest.json"):
        assert (out / f).exists(), f
    assert res.leaderboard[0]["rank"] == 1 and res.leaderboard[0]["algorithm"] == s["best_model"]
    json.loads((out / "run_summary.json").read_text())


def test_bundle_roundtrip_and_checksum(clf_dir, tmp_path):
    out = tmp_path / "out"
    run(clf_dir, out)
    bundle = at.load_bundle(out / "best_model.joblib")
    X = pd.read_csv(clf_dir / "test_processed.csv")
    shuffled = X.iloc[:, ::-1]  # column order must not matter
    assert len(at.predict(bundle, shuffled)) == len(X)
    with pytest.raises(ValueError, match="Missing feature"):
        at.predict(bundle, X.drop(columns=["f0"]))
    with open(out / "best_model.joblib", "ab") as f:  # tamper
        f.write(b"x")
    with pytest.raises(ValueError, match="checksum"):
        at.load_bundle(out / "best_model.joblib")


def test_string_labels_are_decoded(tmp_path):
    X, y = make_classification(n_samples=300, n_features=6, random_state=1)
    d = write_dataset(tmp_path, X, np.where(y == 1, "yes", "no"))
    res = run(d, tune=False)
    pred = at.predict(res.bundle, pd.read_csv(d / "test_processed.csv"))
    assert set(pred) <= {"yes", "no"}


def test_regression(reg_dir):
    res = run(reg_dir)
    assert res.summary["task"] == "regression" and res.summary["primary_metric"] == "r2"
    assert res.summary["best_test_metrics"]["r2"] > 0.8


def test_successive_halving_subsamples_large_data(tmp_path):
    X, y = make_classification(n_samples=1200, n_features=8, n_informative=5, random_state=0)
    d = write_dataset(tmp_path, X, y)
    res = run(d, screening_max_rows=300, tune=False, ensemble=False)
    rungs = res.summary["rungs"]
    assert len(rungs) == 2 and rungs[0]["rows"] == 300 and rungs[1]["rows"] == 900
    assert len(rungs[1]["evaluated"]) <= len(rungs[0]["kept"])
    assert res.summary["models_finalists"] <= res.summary["models_screened"]
    assert res.eliminated  # losers are recorded with a reason


def test_weak_models_are_pruned_early(clf_dir):
    res = run(clf_dir, tune=False, ensemble=False, keep_fraction=0.3, keep_min=2)
    assert res.summary["models_finalists"] < res.summary["models_screened"]


def test_one_failing_model_does_not_kill_run(clf_dir, monkeypatch):
    def boom(ctx, seed):
        raise RuntimeError("boom")
    for spec in registry.REGISTRY:
        if spec.name == "RandomForest" and spec.task == "classification":
            monkeypatch.setattr(spec, "factory", boom)
    res = run(clf_dir, tune=False)
    assert "RandomForest" in res.summary["failures"]
    assert res.summary["best_model"] != "RandomForest"


def test_ensemble_must_clear_margin(clf_dir):
    never = run(clf_dir, ensemble=True, ensemble_min_gain=1.0, tune=False)
    assert never.summary["best_model"] != "SoftVotingEnsemble"
    assert any(r["algorithm"] == "SoftVotingEnsemble" for r in never.leaderboard)  # still reported
    off = run(clf_dir, ensemble=False, tune=False)
    assert all(r["algorithm"] != "SoftVotingEnsemble" for r in off.leaderboard)


def test_time_budget_still_returns_a_model(clf_dir):
    res = run(clf_dir, time_budget_s=0.0, tune=False)
    assert res.summary["best_model"]  # baseline + at least the first model complete


def test_tuning_is_reproducible(clf_dir):
    a, b = run(clf_dir), run(clf_dir)
    assert a.summary["best_model"] == b.summary["best_model"]
    assert a.summary["best_cv_score"] == b.summary["best_cv_score"]


def test_imbalance_warning(tmp_path):
    X, y = make_classification(n_samples=500, n_features=6, weights=[0.95], random_state=0)
    res = run(write_dataset(tmp_path, X, y), tune=False)
    assert any("imbalance" in w.lower() for w in res.summary["warnings"])


def test_uses_profile_and_provenance(clf_dir):
    profile = {"overview": {}, "columns": {"t": {"inferred_type": "categorical"}},
               "target": {"name": "t", "imbalance_flag": True},
               "target_association": {}}
    (clf_dir / "feature_provenance.json").write_text(json.dumps(
        [{"output_feature": f"f{i}", "source_column": f"src{i}", "transformation": "one_hot"} for i in range(8)]))
    data = at.load_dataset(clf_dir)
    upstream = at.load_upstream(clf_dir)
    upstream.profile = profile
    res = at.AutoTrainer(at.TrainingConfig(**FAST, tune=False)).run(data, upstream)
    ctx = res.selection["context"]
    assert ctx["imbalanced"] is True and ctx["used_provenance"] and ctx["onehot_share"] == 1.0


@pytest.mark.parametrize("breaker, match", [
    ("nan", "NaN"), ("rows", "row counts"), ("notarget", "y_train.csv"), ("cols", "different columns")])
def test_input_validation(clf_dir, breaker, match):
    if breaker == "nan":
        df = pd.read_csv(clf_dir / "train_processed.csv"); df.loc[0, "f0"] = np.nan
        df.to_csv(clf_dir / "train_processed.csv", index=False)
    elif breaker == "rows":
        pd.DataFrame({"t": [0, 1]}).to_csv(clf_dir / "y_train.csv", index=False)
    elif breaker == "notarget":
        (clf_dir / "y_train.csv").unlink()
    else:
        df = pd.read_csv(clf_dir / "test_processed.csv").rename(columns={"f0": "zzz"})
        df.to_csv(clf_dir / "test_processed.csv", index=False)
    with pytest.raises((ValueError, FileNotFoundError), match=match):
        at.load_dataset(clf_dir)


def test_target_column_inside_csv(tmp_path):
    X, y = make_classification(n_samples=200, n_features=4, random_state=0)
    df = pd.DataFrame(X, columns=list("abcd")).assign(Survived=y)
    df.iloc[:150].to_csv(tmp_path / "train_processed.csv", index=False)
    df.iloc[150:].to_csv(tmp_path / "test_processed.csv", index=False)
    data = at.load_dataset(tmp_path, target_col="Survived")
    assert "Survived" not in data.X_train.columns and len(data.y_test) == 50


def test_cli(clf_dir, tmp_path, capsys):
    out = tmp_path / "cli_out"
    code = cli_main(["--input-dir", str(clf_dir), "--out-dir", str(out), "--no-tune", "--cv-splits", "3",
                     "--max-candidates", "4", "--n-jobs", "1"])
    assert code == 0 and (out / "best_model.joblib").exists()
    assert "Best model:" in capsys.readouterr().out
    assert cli_main(["--input-dir", str(tmp_path / "missing")]) == 2
