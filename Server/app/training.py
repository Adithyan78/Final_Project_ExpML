
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import json
import logging

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
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


class TrainingRequest(BaseModel):
    config: dict = Field(default_factory=dict)


def json_safe(value):
    """Convert common MongoDB and Python values into JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "item"):
        return json_safe(value.item())

    return value


async def download_gridfs_file(bucket, file_id, destination: Path):
    stream = await bucket.open_download_stream(file_id)
    contents = await stream.read()
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


async def execute_training(
    training_run_id: ObjectId,
    preprocessing_run: dict,
    dataset: dict,
    owner_id: ObjectId,
    config_data: dict,
):
    runs = get_training_runs_collection()
    bucket = get_gridfs_bucket()

    uploaded_ids = {}

    try:
        await runs.update_one(
            {"_id": training_run_id},
            {
                "$set": {
                    "status": "running",
                    "started_at": datetime.now(timezone.utc),
                }
            },
        )

        config = TrainingConfig.from_dict(config_data)

        with TemporaryDirectory(prefix="autoexplainai_training_") as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"

            input_dir.mkdir()
            output_dir.mkdir()

            artifacts = preprocessing_run.get("artifacts", {})

            train_file_id = artifacts.get("train_file_id")
            test_file_id = artifacts.get("test_file_id")

            if not train_file_id or not test_file_id:
                raise ValueError(
                    "The preprocessing run is missing train/test CSV artifacts."
                )

            await download_gridfs_file(
                bucket, train_file_id, input_dir / "train_processed.csv"
            )

            await download_gridfs_file(
                bucket, test_file_id, input_dir / "test_processed.csv"
            )


            if not isinstance(profile, dict):
                raise ValueError("Dataset analysis profile is unavailable.")

            profile_path = input_dir / "dataset_profile.json"
            profile_path.write_text(
                json.dumps(json_safe(profile), indent=2),
                encoding="utf-8",
            )

            # Download preprocessing reports for AutoML context.
            report_ids = artifacts.get("json_reports", {})

            for filename in (
                "feature_provenance.json",
                "preprocessing_summary.json",
            ):
                file_id = report_ids.get(filename)

                if file_id:
                    await download_gridfs_file(
                        bucket, file_id, input_dir / filename
                    )

            # Run the synchronous AutoML pipeline outside the event loop.
            result = await run_in_threadpool(
                run_from_directory,
                input_dir,
                output_dir,
                profile_path,
                config,
                preprocessing_run["target_column"],
            )

            # Upload every generated artifact to GridFS.
            artifact_paths = sorted(
                path for path in output_dir.rglob("*") if path.is_file()
            )

            if not artifact_paths:
                raise RuntimeError("AutoML Trainer produced no artifacts.")

            for path in artifact_paths:
                relative_name = path.relative_to(output_dir).as_posix()
                file_id = await upload_training_artifact(
                    bucket,
                    path,
                    relative_name,
                    owner_id,
                    preprocessing_run["dataset_id"],
                    preprocessing_run["_id"],
                    training_run_id,
                )

                uploaded_ids[path.relative_to(output_dir).as_posix()] = file_id

            summary = json_safe(result.summary)
            leaderboard = json_safe(result.leaderboard)

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
                    }
                },
            )

    except Exception as exc:
        logger.exception("AutoML training failed: %s", training_run_id)

        # Remove artifacts uploaded before the failure.
        for file_id in uploaded_ids.values():
            try:
                await bucket.delete(file_id)
            except Exception:
                logger.exception("Could not clean up training artifact.")

        await runs.update_one(
            {"_id": training_run_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                    "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                    "artifacts": {},
                }
            },
        )


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
    owner_id = ObjectId(user["id"])

    preprocessing_run = await get_owned_run(
        preprocessing_run_id, user
    )

    if preprocessing_run.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="The preprocessing run has not completed.",
        )

    datasets = get_datasets_collection()

    dataset = await datasets.find_one({
        "_id": preprocessing_run["dataset_id"],
        "owner_id": owner_id,
    })

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    # Validate configuration before creating a job.
    try:
        config = TrainingConfig.from_dict(request.config)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

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

    await get_training_runs_collection().insert_one(training_document)

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


@router.get("/runs/{training_run_id}")
async def get_training_run(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(status_code=404, detail="Training run not found.")

    run = await get_training_runs_collection().find_one({
        "_id": ObjectId(training_run_id),
        "owner_id": ObjectId(user["id"]),
    })

    if not run:
        raise HTTPException(status_code=404, detail="Training run not found.")

    return {
        "training_run_id": str(run["_id"]),
        "dataset_id": str(run["dataset_id"]),
        "preprocessing_run_id": str(run["preprocessing_run_id"]),
        "status": run["status"],
        "config": json_safe(run.get("config", {})),
        "created_at": run["created_at"].isoformat(),
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

@router.get("/runs/{training_run_id}/artifacts")
async def get_training_artifacts(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(status_code=404, detail="Training run not found.")

    run = await get_training_runs_collection().find_one({
        "_id": ObjectId(training_run_id),
        "owner_id": ObjectId(user["id"]),
    })

    if not run:
        raise HTTPException(status_code=404, detail="Training run not found.")

    if run.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Training is {run.get('status')}.",
        )

    return {
        "training_run_id": training_run_id,
        "artifacts": list(run.get("artifacts", {}).keys()),
    }

@router.get("/runs/{training_run_id}/leaderboard")
async def get_training_leaderboard(
    training_run_id: str,
    user: dict = Depends(current_user),
):
    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(status_code=404, detail="Training run not found.")

    run = await get_training_runs_collection().find_one({
        "_id": ObjectId(training_run_id),
        "owner_id": ObjectId(user["id"]),
    })

    if not run:
        raise HTTPException(status_code=404, detail="Training run not found.")

    if run.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Training is {run.get('status')}.",
        )

    return {
        "training_run_id": training_run_id,
        "leaderboard": json_safe(run.get("leaderboard", [])),
    }



@router.get("/runs/{training_run_id}/artifacts/download")
async def download_training_artifact(
    training_run_id: str,
    artifact_path: str,
    user: dict = Depends(current_user),
):
    if not ObjectId.is_valid(training_run_id):
        raise HTTPException(
            status_code=404,
            detail="Training run not found.",
        )

    run = await get_training_runs_collection().find_one({
        "_id": ObjectId(training_run_id),
        "owner_id": ObjectId(user["id"]),
    })

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
        stream = await get_gridfs_bucket().open_download_stream(file_id)
        contents = await stream.read()
    except Exception as exc:
        logger.exception("Could not download training artifact.")
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



