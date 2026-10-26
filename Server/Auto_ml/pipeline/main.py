

import sys
import subprocess
from pathlib import Path

# ==================================================
# PROJECT PATHS
# ==================================================

# Absolute path to the modules directory
MODULES_DIR = Path(
    r"D:\FYP_Auto_ML\Server\Auto_ml\modules"
)

# Ensure the project root is available for imports
PROJECT_ROOT = Path(
    r"D:\FYP_Auto_ML"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ==================================================
# MODULE IMPORTS
# ==================================================

from Server.Auto_ml.modules.Dataset_Analyzer_module.Dataset_analyzer import (
    analyze_dataset,
    save_profile,
)

from Server.Auto_ml.modules.intelligent_preprocessing_module.Main import (
    run_preprocessing,
)


def main():

    # ==================================================
    # CONFIGURATION
    # ==================================================

    dataset_path = (
        MODULES_DIR
        / "Dataset_Analyzer_module"
        / "Titanic-Dataset.csv"
    )

    profile_path = (
        MODULES_DIR
        / "Dataset_Analyzer_module"
        / "dataset_profile.json"
    )

    preprocessing_output_dir = (
        MODULES_DIR
        / "intelligent_preprocessing_module"
        / "output"
    )

    model_output_dir = (
        MODULES_DIR
        / "automl_trainer_module"
        / "model_output"
    )

    target_column = "Survived"

    # ==================================================
    # VALIDATE DATASET
    # ==================================================

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            "Please verify the CSV file location."
        )

    preprocessing_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ==================================================
    # MODULE 1: DATASET ANALYZER
    # ==================================================

    print("\n" + "=" * 60)
    print("MODULE 1: DATASET ANALYZER")
    print("=" * 60)

    profile = analyze_dataset(
        str(dataset_path),
        target_column=target_column,
    )

    save_profile(
        profile,
        str(profile_path),
    )

    print("Dataset analysis completed.")
    print(f"Profile saved to: {profile_path}")

    # ==================================================
    # MODULE 2: INTELLIGENT PREPROCESSING
    # ==================================================

    print("\n" + "=" * 60)
    print("MODULE 2: INTELLIGENT PREPROCESSING")
    print("=" * 60)

    run_preprocessing(
        dataset_path=str(dataset_path),
        profile_path=str(profile_path),
        target_column=target_column,
    )

    print("Preprocessing execution completed.")

    # ==================================================
    # VALIDATE PREPROCESSING OUTPUT
    # ==================================================

    if not preprocessing_output_dir.exists():
        raise FileNotFoundError(
            "Preprocessing output directory not found: "
            f"{preprocessing_output_dir}"
        )

    # ==================================================
    # MODULE 3: MODEL SELECTION
    # ==================================================

    print("\n" + "=" * 60)
    print("MODULE 3: MODEL SELECTION")
    print("=" * 60)

    command = [
        sys.executable,
        "-m",
        "automl_trainer_module",
        "--input-dir",
        str(preprocessing_output_dir),
        "--profile",
        str(profile_path),
        "--out-dir",
        str(model_output_dir),
    ]

    print("Executing model selection...")
    print(f"Input directory: {preprocessing_output_dir}")
    print(f"Profile: {profile_path}")
    print(f"Output directory: {model_output_dir}")

    subprocess.run(
        command,
        cwd=str(MODULES_DIR),
        check=True,
    )

    # ==================================================
    # PIPELINE COMPLETED
    # ==================================================

    print("\n" + "=" * 60)
    print("COMPLETE AUTOML PIPELINE FINISHED SUCCESSFULLY")
    print("=" * 60)

    print(f"Dataset: {dataset_path}")
    print(f"Dataset profile: {profile_path}")
    print(f"Preprocessing outputs: {preprocessing_output_dir}")
    print(f"Model outputs: {model_output_dir}")


if __name__ == "__main__":
    main()