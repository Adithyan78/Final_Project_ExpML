import json
from pathlib import Path

import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def titanic_profile():
    with open(FIXTURES_DIR / "titanic_profile.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def titanic_raw():
    return pd.read_csv(FIXTURES_DIR / "titanic.csv")


@pytest.fixture(scope="session")
def titanic_split(titanic_raw):
    df = titanic_raw.copy()
    y = df["Survived"]
    X = df.drop(columns=["Survived"])
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    return X_train.reset_index(drop=True), X_test.reset_index(drop=True), y_train.reset_index(drop=True), y_test.reset_index(drop=True)
