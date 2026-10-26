"""Load and validate the outputs of the preprocessing module."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class DatasetBundle:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series


@dataclass
class UpstreamArtifacts:
    """Everything the earlier modules produced, all optional but useful."""
    profile: dict | None = None        # Dataset Analyzer -> dataset_profile.json
    provenance: list | None = None     # Preprocessing    -> feature_provenance.json
    summary: dict | None = None        # Preprocessing    -> preprocessing_summary.json


def _load_json(path: Path | None):
    if path is None or not Path(path).exists():
        return None
    return json.loads(Path(path).read_text())


def load_upstream(input_dir: str | Path, profile_path: str | Path | None = None,
                  provenance_path: str | Path | None = None,
                  summary_path: str | Path | None = None) -> UpstreamArtifacts:
    """Load analyzer/preprocessing JSON. Provenance and summary are auto-discovered in input_dir."""
    d = Path(input_dir)
    return UpstreamArtifacts(
        profile=_load_json(Path(profile_path)) if profile_path else None,
        provenance=_load_json(Path(provenance_path) if provenance_path else d / "feature_provenance.json"),
        summary=_load_json(Path(summary_path) if summary_path else d / "preprocessing_summary.json"),
    )


def _read_target(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    if df.shape[1] != 1:
        raise ValueError(f"{path.name} must have exactly one column, found {df.shape[1]}.")
    return df.iloc[:, 0]


def load_dataset(input_dir: str | Path, target_col: str | None = None) -> DatasetBundle:
    """Load train/test features + targets from the preprocessing output folder.

    Targets come from y_train.csv / y_test.csv, or, if ``target_col`` is given and present in
    the processed CSVs, are split off from them.
    """
    d = Path(input_dir)
    for name in ("train_processed.csv", "test_processed.csv"):
        if not (d / name).exists():
            raise FileNotFoundError(f"{d / name} not found.")
    X_train, X_test = pd.read_csv(d / "train_processed.csv"), pd.read_csv(d / "test_processed.csv")

    if (d / "y_train.csv").exists() and (d / "y_test.csv").exists():
        y_train, y_test = _read_target(d / "y_train.csv"), _read_target(d / "y_test.csv")
    elif target_col and target_col in X_train.columns and target_col in X_test.columns:
        y_train, y_test = X_train.pop(target_col), X_test.pop(target_col)
    else:
        raise FileNotFoundError(
            f"No target found in {d}. Provide y_train.csv and y_test.csv (one column each, same row "
            "order as train_processed.csv / test_processed.csv), or keep the target as a column in "
            "the processed CSVs and pass target_col."
        )
    return validate_dataset(DatasetBundle(X_train, y_train.reset_index(drop=True),
                                          X_test, y_test.reset_index(drop=True)))


def validate_dataset(data: DatasetBundle) -> DatasetBundle:
    X_train, X_test, y_train, y_test = data.X_train, data.X_test, data.y_train, data.y_test
    if len(y_train) != len(X_train) or len(y_test) != len(X_test):
        raise ValueError("Target length does not match its feature file (row counts differ).")
    if len(X_train) < 20:
        raise ValueError(f"Only {len(X_train)} training rows; need at least 20.")
    if list(X_train.columns) != list(X_test.columns):
        raise ValueError("train_processed.csv and test_processed.csv have different columns.")
    bad = [c for c in X_train.columns if not pd.api.types.is_numeric_dtype(X_train[c])]
    if bad:
        raise ValueError(f"Non-numeric feature columns (encode them in preprocessing): {bad}")
    for name, frame in (("train", X_train), ("test", X_test)):
        arr = frame.to_numpy(dtype=float)
        if not np.isfinite(arr).all():
            cols = frame.columns[~np.isfinite(arr).all(axis=0)].tolist()
            raise ValueError(f"{name}_processed.csv has NaN/inf values in {cols}; impute in preprocessing.")
    if y_train.isna().any() or y_test.isna().any():
        raise ValueError("Target contains missing values.")
    return data


def infer_task(y: pd.Series, profile: dict | None, requested: str = "auto") -> str:
    if requested in ("classification", "regression"):
        return requested
    if profile:
        name = profile.get("target", {}).get("name")
        if profile.get("columns", {}).get(name, {}).get("inferred_type") == "categorical":
            return "classification"
    if not pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y):
        return "classification"  # strings, categories, booleans
    if pd.api.types.is_integer_dtype(y) and y.nunique() <= 20:
        return "classification"
    if pd.api.types.is_float_dtype(y) and y.nunique() <= 10 and (y % 1 == 0).all():
        return "classification"
    return "regression"
