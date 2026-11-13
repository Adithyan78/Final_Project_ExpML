
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import logging

from bson import ObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .auth import current_user
from .database import (
    get_datasets_collection,
    get_gridfs_bucket,
    get_training_runs_collection,
)
from .preprocessing import get_owned_run

from automl_trainer import run_from_directory, TrainingConfig


router = APIRouter(prefix="/training", tags=["AutoML Training"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------------------

class TrainingRequest(BaseModel):
    config: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------
# SERIALIZATION
# ---------------------------------------------------------------------

def json_safe(value):
    """Convert common MongoDB and Python values into JSON-safe values."""

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "item"):
        return json_safe(value.item())

    return value


# ---------------------------------------------------------------------
# ARTIFACT HELPERS
# ---------------------------------------------------------------------

def get_artifact_id(artifacts: dict, *names):
    """Resolve an artifact ID using supported artifact-name variants."""

    for name in names:
        value = artifacts.get(name)

        if value:
            return value

    return None


async def download_gridfs_file(bucket, file_id, destination: Path):
    """Download a GridFS artifact into a local file."""

    if isinstance(file_id, str) and ObjectId.is_valid(file_id):
        file_id = ObjectId(file_id)

    stream = await bucket.open_download_stream(file_id)
    contents = await stream.read()

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)


async def upload_training_artifact(
    bucket,
    source: Path,
    relative_name: str,
    owner_id: ObjectId,
    dataset_id: ObjectId,
    preprocessing_run_id: ObjectId,
    training_run_id: ObjectId,
):
    """Upload a generated training artifact to GridFS."""

    return await bucket.upload_from_stream(
        f"{training_run_id}_{Path(relative_name).name}",
        source.read_bytes(),
        metadata={
            "owner_id": str(owner_id),
            "dataset_id": str(dataset_id),
            "preprocessing_run_id": str(preprocessing_run_id),
            "training_run_id": str(training_run_id),
            "artifact_type": "automl_training_artifact",
            "relative_path": relative_name,
        },
    )


# ---------------------------------------------------------------------
# BACKGROUND TRAINING EXECUTION
# ---------------------------------------------------------------------

async def execute_training(
    training_run_id: ObjectId,
    preprocessing_run: dict,
    dataset: dict,
    owner_id: ObjectId,
    config_data: dict,
):
    """Execute AutoML training using preprocessing outputs."""

    runs = get_training_runs_collection()
    bucket = get_gridfs_bucket()

    uploaded_ids = {}

    try:
        # -------------------------------------------------------------
        # UPDATE STATUS
        # -------------------------------------------------------------

        await runs.update_one(
            {"_id": training_run_id},
            {
                "$set": {
                    "status": "running",
                    "started_at": datetime.now(timezone.utc),
                }
            },
        )

        # -------------------------------------------------------------
        # LOAD CONFIGURATION
        # -------------------------------------------------------------

        config = TrainingConfig.from_dict(config_data)

        # -------------------------------------------------------------
        # PREPARE TEMPORARY DIRECTORIES
        # -------------------------------------------------------------

        with TemporaryDirectory(
            prefix="autoexplainai_training_"
        ) as temp:

            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"

            input_dir.mkdir()
            output_dir.mkdir()

            # ---------------------------------------------------------
            # GET PREPROCESSING ARTIFACT REFERENCES
            # ---------------------------------------------------------

            artifacts = preprocessing_run.get("artifacts") or {}

            train_file_id = get_artifact_id(
                artifacts,
                "train_file_id",
                "train_processed.csv",
                "train_processed",
            )

            test_file_id = get_artifact_id(
                artifacts,
                "test_file_id",
                "test_processed.csv",
                "test_processed",
            )

            if not train_file_id or not test_file_id:
                raise ValueError(
                    "The preprocessing run is missing train/test CSV artifacts."
                )

            # ---------------------------------------------------------
            # DOWNLOAD PROCESSED DATASETS
            # ---------------------------------------------------------

            await download_gridfs_file(
                bucket,
                train_file_id,
                input_dir / "train_processed.csv",
            )

            await download_gridfs_file(
                bucket,
                test_file_id,
                input_dir / "test_processed.csv",
            )

            # ---------------------------------------------------------
            # DOWNLOAD OPTIONAL TARGET FILES
            # ---------------------------------------------------------

            y_train_file_id = get_artifact_id(
                artifacts,
                "y_train_file_id",
                "y_train.csv",
            )

            y_test_file_id = get_artifact_id(
                artifacts,
                "y_test_file_id",
                "y_test.csv",
            )

            if bool(y_train_file_id) != bool(y_test_file_id):
                raise ValueError(
                    "Both y_train.csv and y_test.csv must be provided together."
                )

            if y_train_file_id and y_test_file_id:
                await download_gridfs_file(
                    bucket,
                    y_train_file_id,
                    input_dir / "y_train.csv",
                )

                await download_gridfs_file(
                    bucket,
                    y_test_file_id,
                    input_dir / "y_test.csv",
                )

            # ---------------------------------------------------------
            # DOWNLOAD OPTIONAL UPSTREAM REPORTS
            # ---------------------------------------------------------

            report_ids = artifacts.get("json_reports") or {}

            if not isinstance(report_ids, dict):
                report_ids = {}

            # Dataset profile is OPTIONAL.
            # load_upstream() explicitly supports profile=None.
            profile_file_id = get_artifact_id(
                report_ids,
                "dataset_profile.json",
            )

            profile_path = None

            if profile_file_id:
                profile_path = input_dir / "dataset_profile.json"

                await download_gridfs_file(
                    bucket,
                    profile_file_id,
                    profile_path,
                )

            # These reports are also optional.
            optional_reports = {
                "feature_provenance.json": (
                    "feature_provenance.json",
                ),
                "preprocessing_summary.json": (
                    "preprocessing_summary.json",
                ),
            }

            for filename, aliases in optional_reports.items():
                file_id = get_artifact_id(report_ids, *aliases)

                if file_id:
                    await download_gridfs_file(
                        bucket,
                        file_id,
                        input_dir / filename,
                    )

            # ---------------------------------------------------------
            # RESOLVE TARGET COLUMN
            # ---------------------------------------------------------

            target_column = preprocessing_run.get("target_column")

            if not target_column:
                summary_path = input_dir / "preprocessing_summary.json"

                if summary_path.exists():
                    import json



                    try:
                        preprocessing_summary = json.loads(
                            summary_path.read_text(encoding="utf-8")
                        )

                        target_column = preprocessing_summary.get(
                            "target_column"
                        ) or preprocessing_summary.get("target")

                    except (ValueError, OSError):
                        logger.warning(
                            "Could not read preprocessing summary target."
                        )

            # Separate y_train/y_test files do not require target_column.
            has_separate_targets = (
                (input_dir / "y_train.csv").exists()
                and (input_dir / "y_test.csv").exists()
            )

            if not target_column and not has_separate_targets:
                raise ValueError(
                    "Target column is missing and separate target files "
                    "were not provided by preprocessing."
                )

            # ---------------------------------------------------------
            # EXECUTE AUTOML TRAINER
            # ---------------------------------------------------------

            logger.info(
                "Starting AutoML training: %s",
                training_run_id,
            )

            result = await run_in_threadpool(
                run_from_directory,
                input_dir,
                output_dir,
                profile_path,
                config,
                target_column,
            )

            # ---------------------------------------------------------
            # COLLECT GENERATED ARTIFACTS
            # ---------------------------------------------------------

            artifact_paths = sorted(
                path
                for path in output_dir.rglob("*")
                if path.is_file()
            )

            if not artifact_paths:
                raise RuntimeError(
                    "AutoML Trainer produced no artifacts."
                )

            # ---------------------------------------------------------
            # UPLOAD ARTIFACTS TO GRIDFS
            # ---------------------------------------------------------

            for path in artifact_paths:
                relative_name = path.relative_to(
                    output_dir
                ).as_posix()

                file_id = await upload_training_artifact(
                    bucket,
                    path,
                    relative_name,
                    owner_id,
                    preprocessing_run["dataset_id"],
                    preprocessing_run["_id"],
                    training_run_id,
                )

                uploaded_ids[relative_name] = file_id

            # ---------------------------------------------------------
            # PREPARE RESULTS
            # ---------------------------------------------------------

            summary = json_safe(result.summary)
            leaderboard = json_safe(result.leaderboard)

            if not isinstance(summary, dict):
                raise ValueError(
                    "AutoML Trainer returned an invalid summary."
                )

            # ---------------------------------------------------------
            # MARK TRAINING AS COMPLETED
            # ---------------------------------------------------------

            await runs.update_one(
                {"_id": training_run_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "summary": summary,
                        "leaderboard": leaderboard,
                        "best_model": summary.get("best_model"),
                        "task": summary.get("task"),
                        "primary_metric": summary.get("primary_metric"),
                        "artifacts": uploaded_ids,
                    },
                    "$unset": {
                        "error": "",
                    },
                },
            )

            logger.info(
                "AutoML training completed successfully: %s",
                training_run_id,
            )

    except Exception as exc:
        logger.exception(
            "AutoML training failed: %s",
            training_run_id,
        )

        # -------------------------------------------------------------
        # CLEAN UP PARTIALLY UPLOADED ARTIFACTS
        # -------------------------------------------------------------

        for file_id in uploaded_ids.values():
            try:
                await bucket.delete(file_id)

            except Exception:
                logger.exception(
                    "Could not clean up training artifact."
                )

        # -------------------------------------------------------------
        # MARK TRAINING AS FAILED
        # -------------------------------------------------------------

        await runs.update_one(
            {"_id": training_run_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                    "error": (
                        f"{type(exc).__name__}: {str(exc)[:1000]}"
                    ),
                    "artifacts": {},
                }
            },
        )


# ---------------------------------------------------------------------
# START TRAINING
# ---------------------------------------------------------------------

@router.post(
    "/{preprocessing_run_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_training(
    preprocessing_run_id: str,
    background_tasks: BackgroundTasks,
    request: TrainingRequest,
    user: dict = Depends(current_user),
):
    """Validate a preprocessing run and queue AutoML training."""

    owner_id = ObjectId(user["id"])

    # -------------------------------------------------------------
    # VERIFY PREPROCESSING RUN OWNERSHIP
    # -------------------------------------------------------------

    preprocessing_run = await get_owned_run(
        preprocessing_run_id,
        user,
    )

    if preprocessing_run.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="The preprocessing run has not completed.",
        )

    # -------------------------------------------------------------
    # VERIFY DATASET OWNERSHIP
    # -------------------------------------------------------------

    datasets = get_datasets_collection()

    dataset = await datasets.find_one(
        {
            "_id": preprocessing_run["dataset_id"],
            "owner_id": owner_id,
        }
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    # -------------------------------------------------------------
    # VALIDATE CONFIGURATION
    # -------------------------------------------------------------

    try:
        config = TrainingConfig.from_dict(request.config)

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # -------------------------------------------------------------
    # CREATE TRAINING RUN
    # -------------------------------------------------------------

    training_run_id = ObjectId()
    created_at = datetime.now(timezone.utc)

    training_document = {
        "_id": training_run_id,
        "owner_id": owner_id,
        "dataset_id": preprocessing_run["dataset_id"],
        "preprocessing_run_id": preprocessing_run["_id"],
        "status": "pending",
        "config": config.to_dict(),
        "created_at": created_at,
        "artifacts": {},
    }

    await get_training_runs_collection().insert_one(
        training_document
    )

    # -------------------------------------------------------------
    # QUEUE BACKGROUND TASK
    # -------------------------------------------------------------

    background_tasks.add_task(
        execute_training,
        training_run_id,
        preprocessing_run,
        dataset,
        owner_id,
        config.to_dict(),
    )

    return {
        "training_run_id": str(training_run_id),
        "preprocessing_run_id": preprocessing_run_id,
        "status": "pending",
        "message": "AutoML training has been queued.",
    }


# ---------------------------------------------------------------------
# GET TRAINING RUN
# ---------------------------------------------------------------------

@router.get("/runs/{training_run_id}")
async def get_training_run(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    """Retrieve the status and results of an owned training run."""

    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    run = await get_training_runs_collection().find_one(
        {
            "_id": ObjectId(training_run_id),
            "owner_id": ObjectId(user["id"]),
        }
    )

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    return {
        "training_run_id": str(run["_id"]),
        "dataset_id": str(run["dataset_id"]),
        "preprocessing_run_id": str(run["preprocessing_run_id"]),
        "status": run["status"],
        "config": json_safe(run.get("config", {})),
        "created_at": (
            run["created_at"].isoformat()
            if run.get("created_at") else None
        ),
        "started_at": (
            run["started_at"].isoformat()
            if run.get("started_at") else None
        ),
        "completed_at": (
            run["completed_at"].isoformat()
            if run.get("completed_at") else None
        ),
        "error": run.get("error"),
        "summary": json_safe(run.get("summary")),
        "leaderboard": json_safe(run.get("leaderboard")),
        "best_model": run.get("best_model"),
        "task": run.get("task"),
        "primary_metric": run.get("primary_metric"),
        "artifacts": list(run.get("artifacts", {}).keys()),
    }


# ---------------------------------------------------------------------
# GET TRAINING ARTIFACT LIST
# ---------------------------------------------------------------------

@router.get("/runs/{training_run_id}/artifacts")
async def get_training_artifacts(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    """List generated artifacts for a completed training run."""

    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    run = await get_training_runs_collection().find_one(
        {
            "_id": ObjectId(training_run_id),
            "owner_id": ObjectId(user["id"]),
        }
    )

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    if run.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Training is {run.get('status')}.",
        )

    return {
        "training_run_id": training_run_id,
        "artifacts": list(run.get("artifacts", {}).keys()),
    }


# ---------------------------------------------------------------------
# GET LEADERBOARD
# ---------------------------------------------------------------------

@router.get("/runs/{training_run_id}/leaderboard")
async def get_training_leaderboard(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    """Retrieve the model leaderboard for a completed run."""

    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    run = await get_training_runs_collection().find_one(
        {
            "_id": ObjectId(training_run_id),
            "owner_id": ObjectId(user["id"]),
        }
    )

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    if run.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Training is {run.get('status')}.",
        )

    return {
        "training_run_id": training_run_id,
        "leaderboard": json_safe(run.get("leaderboard", [])),
    }


# ---------------------------------------------------------------------
# DOWNLOAD TRAINING ARTIFACT
# ---------------------------------------------------------------------

@router.get("/runs/{training_run_id}/artifacts/download")
async def download_training_artifact(
    training_run_id: str,
    artifact_path: str,
    user: dict = Depends(current_user),
):
    """Download a generated artifact belonging to an owned run."""

    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    run = await get_training_runs_collection().find_one(
        {
            "_id": ObjectId(training_run_id),
            "owner_id": ObjectId(user["id"]),
        }
    )

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    file_id = run.get("artifacts", {}).get(artifact_path)

    if not file_id:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found.",
        )

    try:
        stream = await get_gridfs_bucket().open_download_stream(
            file_id
        )

        contents = await stream.read()

    except Exception as exc:
        logger.exception(
            "Could not download training artifact."
        )

        raise HTTPException(
            status_code=404,
            detail="Artifact could not be read.",
        ) from exc

    return StreamingResponse(
        BytesIO(contents),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{Path(artifact_path).name}"'
            )
        },
    )
