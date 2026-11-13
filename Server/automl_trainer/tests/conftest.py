import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification, make_regression


def write_dataset(path, X, y, split=0.75, target="target"):
    X = pd.DataFrame(X, columns=[f"f{i}" for i in range(X.shape[1])])
    n = int(len(X) * split)
    X.iloc[:n].to_csv(path / "train_processed.csv", index=False)
    X.iloc[n:].to_csv(path / "test_processed.csv", index=False)
    pd.DataFrame({target: y[:n]}).to_csv(path / "y_train.csv", index=False)
    pd.DataFrame({target: y[n:]}).to_csv(path / "y_test.csv", index=False)
    return path


@pytest.fixture
def clf_dir(tmp_path):
    X, y = make_classification(n_samples=400, n_features=8, n_informative=5, random_state=0)
    return write_dataset(tmp_path, X, y)


@pytest.fixture
def reg_dir(tmp_path):
    X, y = make_regression(n_samples=300, n_features=6, noise=5, random_state=0)
    return write_dataset(tmp_path, X, y)


FAST = dict(cv_splits=3, tune_iterations=4, tune_top_n=2, n_jobs=1, max_candidates=6)
