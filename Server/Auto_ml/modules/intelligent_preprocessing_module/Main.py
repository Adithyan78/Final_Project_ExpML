import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module import (
    PreprocessingEngine,
)


def run_preprocessing(
    dataset_path,
    profile_path,
    target_column,
    user_config=None,
):
    # Load analyzer profile
    with open(profile_path, "r", encoding="utf-8") as fh:
        analyzer_profile = json.load(fh)

    # Load dataset
    df = pd.read_csv(dataset_path)

    # Separate target
    y = df[target_column]
    X = df.drop(columns=[target_column])

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    # Create preprocessing engine
    engine = PreprocessingEngine()

    # Preprocess training data
    result = engine.fit_transform(
        X_train,
        y_train,
        analyzer_profile,
        user_config=user_config,
    )

    # Transform test data
    X_test_final = engine.transform(X_test)

    # Output directory
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Prepare outputs
    train_processed = result["data"].reset_index(drop=True)
    test_processed = X_test_final.reset_index(drop=True)

    cleaned_dataset = pd.concat(
        [train_processed, test_processed],
        ignore_index=True,
    )

    # Save datasets
    train_processed.to_csv(
        output_dir / "train_processed.csv",
        index=False,
    )

    test_processed.to_csv(
        output_dir / "test_processed.csv",
        index=False,
    )

    cleaned_dataset.to_csv(
        output_dir / "cleaned_dataset.csv",
        index=False,
    )

    # Save preprocessing log
    with open(
        output_dir / "preprocessing_log.json",
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            result["preprocessing_log"],
            fh,
            indent=2,
            default=str,
        )

    # Save feature provenance
    with open(
        output_dir / "feature_provenance.json",
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            result["feature_provenance"],
            fh,
            indent=2,
            default=str,
        )

    # Summary
    summary = {
        "input_shape": [
            int(len(df)),
            int(len(X.columns)),
        ],
        "train_shape": [
            int(len(train_processed)),
            int(len(train_processed.columns)),
        ],
        "test_shape": [
            int(len(test_processed)),
            int(len(test_processed.columns)),
        ],
        "cleaned_dataset_shape": [
            int(len(cleaned_dataset)),
            int(len(cleaned_dataset.columns)),
        ],
        "selected_features": result["selected_features"],
        "dropped_columns": engine.dropped_columns_,
        "output_files": [
            "cleaned_dataset.csv",
            "train_processed.csv",
            "test_processed.csv",
            "preprocessing_log.json",
            "feature_provenance.json",
            "preprocessing_summary.json",
        ],
    }

    with open(
        output_dir / "preprocessing_summary.json",
        "w",
        encoding="utf-8",
    ) as fh:
        json.dump(
            summary,
            fh,
            indent=2,
            default=str,
        )

    print(
        f"\nSaved preprocessing outputs to: {output_dir}"
    )

    print("=== Final training data shape ===")
    print(result["data"].shape)

    print("\n=== Selected features ===")
    print(result["selected_features"])

    print("\n=== Feature ranking ===")
    print(result["feature_ranking"])

    print("\n=== Sample preprocessing_log ===")
    for entry in result["preprocessing_log"][:8]:
        print(entry)

    print("\n=== Sample feature_provenance ===")
    for entry in result["feature_provenance"][:8]:
        print(entry)

    print("\n=== transform() on held-out test set ===")
    print(X_test_final.shape)
    print(X_test_final.head(3))

    return result