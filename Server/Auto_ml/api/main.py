import sys
import json
import subprocess
import traceback

from pathlib import Path
from uuid import uuid4, UUID

import pandas as pd

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(r"D:\FYP_Auto_ML")

MODULES_DIR = (
    PROJECT_ROOT / "Server" / "Auto_ml" / "modules"
)

RUNS_DIR = (
    PROJECT_ROOT / "Server" / "Auto_ml" / "api" / "runs"
)

RUNS_DIR.mkdir(parents=True, exist_ok=True)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# EXISTING MODULE IMPORTS
# ============================================================

from Server.Auto_ml.modules.Dataset_Analyzer_module.Dataset_analyzer import (
    analyze_dataset,
    save_profile,
)

from Server.Auto_ml.modules.intelligent_preprocessing_module.Main import (
    run_preprocessing,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AutoML API",
    description=(
        "Independent API endpoints for dataset analysis, "
        "intelligent preprocessing, and model selection."
    ),
    version="1.0.0",
)


# ============================================================
# REQUEST MODELS
# ============================================================

class RunRequest(BaseModel):
    run_id: str = Field(min_length=1)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_run_dir(run_id: str) -> Path:
    """Validate the run ID and retrieve its directory."""

    try:
        validated_id = str(UUID(run_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid run_id.",
        )

    run_dir = (RUNS_DIR / validated_id).resolve()

    if not run_dir.is_relative_to(RUNS_DIR.resolve()):
        raise HTTPException(
            status_code=400,
            detail="Invalid run directory.",
        )

    if not run_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Run not found. Analyze the dataset first.",
        )

    return run_dir


def get_run_config(run_dir: Path) -> dict:
    """Load the saved target column and run configuration."""

    config_path = run_dir / "run_config.json"

    if not config_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Run configuration missing. Run analysis first.",
        )

    try:
        return json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read run configuration: {exc}",
        )


def check_dataset_columns(
    dataset_path: Path,
    target_column: str,
) -> list[str]:
    """Check that the user-selected target exists in the CSV."""

    try:
        columns = pd.read_csv(
            dataset_path,
            nrows=0,
        ).columns.tolist()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read CSV file: {exc}",
        )

    if target_column not in columns:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    f"Target column '{target_column}' "
                    "does not exist in the dataset."
                ),
                "available_columns": columns,
            },
        )

    return columns


def handle_error(exc: Exception):
    """Log unexpected errors and return an API error."""

    traceback.print_exc()

    raise HTTPException(
        status_code=500,
        detail=f"{type(exc).__name__}: {exc}",
    )


# ============================================================
# API 1: DATASET ANALYZER
# POST /api/v1/analyze
# ============================================================

@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    target_column: str = Form(...),
):
    """
    Upload a CSV and choose the target column.

    Returns a run_id used by the subsequent endpoints.
    """

    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    target_column = target_column.strip()

    if not target_column:
        raise HTTPException(
            status_code=400,
            detail="Target column cannot be empty.",
        )

    # Generate an isolated directory for this run.
    run_id = str(uuid4())
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    dataset_path = run_dir / "dataset.csv"
    profile_path = run_dir / "dataset_profile.json"

    try:
        # Save uploaded dataset.
        with dataset_path.open("wb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                destination.write(chunk)

        # Validate the selected target.
        check_dataset_columns(
            dataset_path,
            target_column,
        )

        # Run Module 1.
        profile = analyze_dataset(
            str(dataset_path),
            target_column=target_column,
        )

        save_profile(
            profile,
            str(profile_path),
        )

        if not profile_path.exists():
            raise RuntimeError(
                "Dataset Analyzer did not generate the profile JSON."
            )

        # Persist configuration for subsequent API calls.
        config = {
            "run_id": run_id,
            "target_column": target_column,
            "dataset_path": str(dataset_path),
            "profile_path": str(profile_path),
            "status": {
                "analysis": "completed",
                "preprocessing": "pending",
                "model_selection": "pending",
            },
        }

        (run_dir / "run_config.json").write_text(
            json.dumps(config, indent=2),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "module": "dataset_analyzer",
            "run_id": run_id,
            "target_column": target_column,
            "available_columns": pd.read_csv(
                dataset_path,
                nrows=0,
            ).columns.tolist(),
            "profile_path": str(profile_path),
            "message": "Dataset analysis completed.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        handle_error(exc)
    finally:
        await file.close()


# ============================================================
# API 2: INTELLIGENT PREPROCESSING
# POST /api/v1/preprocess
# ============================================================

@app.post("/api/v1/preprocess")
def preprocess(request: RunRequest):
    """
    Run preprocessing for an existing analyzed dataset.

    The target column is loaded from the saved run configuration.
    """

    run_dir = get_run_dir(request.run_id)
    config = get_run_config(run_dir)

    dataset_path = run_dir / "dataset.csv"
    profile_path = run_dir / "dataset_profile.json"
    output_dir = run_dir / "preprocessing_output"

    if not dataset_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Dataset is missing. Run analysis first.",
        )

    if not profile_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Dataset profile is missing. Run analysis first.",
        )

    target_column = config["target_column"]

    # Revalidate the target before preprocessing.
    check_dataset_columns(
        dataset_path,
        target_column,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        # Module 2.
        #
        # IMPORTANT:
        # Your existing run_preprocessing() function must
        # support the output_dir parameter and save its
        # generated artifacts to this directory.

        run_preprocessing(
            dataset_path=str(dataset_path),
            profile_path=str(profile_path),
            target_column=target_column,
            output_dir=str(output_dir),
        )

        config["status"]["preprocessing"] = "completed"

        (run_dir / "run_config.json").write_text(
            json.dumps(config, indent=2),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "module": "intelligent_preprocessing",
            "run_id": request.run_id,
            "target_column": target_column,
            "output_dir": str(output_dir),
            "message": "Preprocessing completed.",
        }

    except Exception as exc:
        handle_error(exc)


# ============================================================
# API 3: MODEL SELECTION
# POST /api/v1/select-model
# ============================================================

@app.post("/api/v1/select-model")
def select_model(request: RunRequest):
    """
    Run model selection using the existing preprocessing output.

    The trainer uses the dataset profile and processed data.
    """

    run_dir = get_run_dir(request.run_id)
    config = get_run_config(run_dir)

    profile_path = run_dir / "dataset_profile.json"
    preprocessing_dir = run_dir / "preprocessing_output"
    model_output_dir = run_dir / "model_output"

    if config["status"]["preprocessing"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=(
                "Preprocessing has not completed for this run. "
                "Call /api/v1/preprocess first."
            ),
        )

    if not profile_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Dataset profile not found.",
        )

    if not preprocessing_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Preprocessing output directory not found.",
        )

    # Check that the output directory is not empty.
    if not any(preprocessing_dir.iterdir()):
        raise HTTPException(
            status_code=400,
            detail="Preprocessing output directory is empty.",
        )

    model_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        # Reuse your existing trainer entry point and CLI.
        command = [
            sys.executable,
            "-m",
            "automl_trainer_module",
            "--input-dir",
            str(preprocessing_dir),
            "--profile",
            str(profile_path),
            "--out-dir",
            str(model_output_dir),
        ]

        result = subprocess.run(
            command,
            cwd=str(MODULES_DIR),
            capture_output=True,
            text=True,
            check=True,
        )

        config["status"]["model_selection"] = "completed"

        (run_dir / "run_config.json").write_text(
            json.dumps(config, indent=2),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "module": "model_selection",
            "run_id": request.run_id,
            "target_column": config["target_column"],
            "output_dir": str(model_output_dir),
            "stdout": result.stdout[-4000:],
            "message": "Model selection completed.",
        }

    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Model selection failed.",
                "stdout": (
                    exc.stdout[-4000:] if exc.stdout else ""
                ),
                "stderr": (
                    exc.stderr[-4000:] if exc.stderr else ""
                ),
            },
        )

    except Exception as exc:
        handle_error(exc)


# ============================================================
# HEALTH CHECK
# GET /health
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AutoML API",
        "modules": [
            "dataset_analyzer",
            "intelligent_preprocessing",
            "model_selection",
        ],
    }