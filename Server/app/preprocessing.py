from datetime import datetime, timezone
from fastapi.responses import StreamingResponse
from io import BytesIO
from typing import Any

import json
import logging

import numpy as np
import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sklearn.model_selection import train_test_split

from .auth import current_user
from .database import (
    get_datasets_collection,
    get_gridfs_bucket,
    get_preprocessing_runs_collection,
)
from .datasets import owned_dataset_query
from .dataset_analyzer import analyze_dataset

from intelligent_preprocessing_module.preprocessing_module import (
    PreprocessingEngine,
)

router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])
logger = logging.getLogger(__name__)


class PreprocessingRequest(BaseModel):
    target_column: str | None = None
    test_size: float = Field(default=0.2, gt=0.0, lt=0.5)
    user_config: dict[str, dict[str, Any]] | None = None


def json_safe(value):
    """Convert NumPy and other common values into JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())

    if isinstance(value, np.generic):
        return json_safe(value.item())

    if isinstance(value, (datetime, ObjectId)):
        return str(value)

    if value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, float) and not np.isfinite(value):
        return None

    return value


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


async def save_csv_artifact(
    bucket,
    filename: str,
    contents: bytes,
    owner_id: ObjectId,
    dataset_id: ObjectId,
    run_id: ObjectId,
    artifact_type: str,
):
    return await bucket.upload_from_stream(
        filename,
        contents,
        metadata={
            "owner_id": str(owner_id),
            "dataset_id": str(dataset_id),
            "run_id": str(run_id),
            "artifact_type": artifact_type,
            "content_type": "text/csv",
        },
    )


@router.post("/{dataset_id}", status_code=status.HTTP_201_CREATED)
async def preprocess_dataset(
    dataset_id: str,
    request: PreprocessingRequest,
    user: dict = Depends(current_user),
):
    """Preprocess an owned dataset and save separate train/test artifacts."""

    datasets = get_datasets_collection()
    runs = get_preprocessing_runs_collection()
    bucket = get_gridfs_bucket()

    # Never allow a user to access another user's dataset.
    query = owned_dataset_query(dataset_id, user["id"])
    dataset = await datasets.find_one(query)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    target = request.target_column or dataset.get("target_column")

    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a target column before preprocessing.",
        )

    if target not in dataset["profile"].get("columns", {}):
        # Analyzer profiles may use a different shape, so the CSV below
        # is checked as the authoritative source of available columns.
        pass

    try:
        stream = await bucket.open_download_stream(dataset["file_id"])
        original_bytes = await stream.read()
        df = pd.read_csv(BytesIO(original_bytes))
    except Exception as exc:
        logger.exception("Could not read original dataset %s", dataset_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read the original dataset.",
        ) from exc

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The dataset contains no data rows.",
        )

    if target not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target column '{target}' was not found.",
        )

    # The current feature selector uses mutual_info_classif.
    # Do not silently run it as though regression were supported.
    if df[target].nunique(dropna=True) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target must contain at least two distinct classes.",
        )

    # Remove rows whose target is missing; feature missing values are
    # left for the preprocessing engine to handle.
    missing_target_rows = int(df[target].isna().sum())
    df = df.loc[df[target].notna()].copy()

    if len(df) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least five rows with a target value are required.",
        )

    y = df[target]
    X = df.drop(columns=[target])

    if X.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The dataset must contain at least one feature besides the target.",
        )

    # Stratify only when every class has enough samples for both splits.
    class_counts = y.value_counts()
    n_test = int(np.ceil(len(df) * request.test_size))
    n_train = len(df) - n_test
    stratify = (
        y
        if len(class_counts) > 1
        and int(class_counts.min()) >= 2
        and n_test >= len(class_counts)
        and n_train >= len(class_counts)
        else None
    )

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=request.test_size,
            random_state=42,
            stratify=stratify,
        )

        # Generate a fresh profile for the selected target so that the
        # engine's target metadata matches this run.
        profile = analyze_dataset(df, target_column=target)

        engine = PreprocessingEngine()
        result = engine.fit_transform(
            X_train,
            y_train,
            profile,
            user_config=request.user_config,
        )

        X_train_processed = result["data"].copy()
        X_test_processed = engine.transform(X_test)

        # Align targets using the original row indexes retained by the engine.
        X_train_processed[target] = y_train.loc[X_train_processed.index]
        X_test_processed[target] = y_test.loc[X_test_processed.index]

        train_csv = dataframe_to_csv_bytes(
            X_train_processed.reset_index(drop=True)
        )
        test_csv = dataframe_to_csv_bytes(
            X_test_processed.reset_index(drop=True)
        )

    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Preprocessing rejected for dataset %s", dataset_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Preprocessing could not be completed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Preprocessing failed for dataset %s", dataset_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Preprocessing failed. Check the dataset and preprocessing configuration.",
        ) from exc

    owner_id = ObjectId(user["id"])
    dataset_object_id = ObjectId(dataset_id)
    run_id = ObjectId()
    created_at = datetime.now(timezone.utc)

    saved_file_ids = []

    try:
        train_file_id = await save_csv_artifact(
            bucket,
            f"{run_id}_train.csv",
            train_csv,
            owner_id,
            dataset_object_id,
            run_id,
            "processed_train",
        )
        saved_file_ids.append(train_file_id)

        test_file_id = await save_csv_artifact(
            bucket,
            f"{run_id}_test.csv",
            test_csv,
            owner_id,
            dataset_object_id,
            run_id,
            "processed_test",
        )
        saved_file_ids.append(test_file_id)

        run_document = {
            "_id": run_id,
            "owner_id": owner_id,
            "dataset_id": dataset_object_id,
            "target_column": target,
            "test_size": request.test_size,
            "random_state": 42,
            "created_at": created_at,
            "status": "completed",
            "rows_before_target_cleanup": int(dataset["n_rows"]),
            "rows_removed_missing_target": missing_target_rows,
            "rows_after_target_cleanup": int(len(df)),
            "train_rows": int(len(X_train_processed)),
            "test_rows": int(len(X_test_processed)),
            "feature_count": int(len(result["selected_features"])),
            "selected_features": json_safe(result["selected_features"]),
            "dropped_columns": json_safe(engine.dropped_columns_),
            "preprocessing_log": json_safe(result["preprocessing_log"]),
            "feature_selection_log": json_safe(
                result["feature_selection_log"]
            ),
            "feature_scores": json_safe(result["feature_scores"]),
            "feature_ranking": json_safe(result["feature_ranking"]),
            "feature_provenance": json_safe(result["feature_provenance"]),
            "artifacts": {
                "train_file_id": train_file_id,
                "test_file_id": test_file_id,
            },
        }

        await runs.insert_one(run_document)

    except Exception as exc:
        # Avoid leaving orphaned GridFS artifacts if saving the run fails.
        for file_id in saved_file_ids:
            try:
                await bucket.delete(file_id)
            except Exception:
                logger.exception("Could not clean up artifact %s", file_id)

        logger.exception("Could not save preprocessing run")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save preprocessing results.",
        ) from exc

    return {
        "run_id": str(run_id),
        "dataset_id": dataset_id,
        "status": "completed",
        "target_column": target,
        "test_size": request.test_size,
        "rows_removed_missing_target": missing_target_rows,
        "train_rows": int(len(X_train_processed)),
        "test_rows": int(len(X_test_processed)),
        "feature_count": int(len(result["selected_features"])),
        "selected_features": json_safe(result["selected_features"]),
        "dropped_columns": json_safe(engine.dropped_columns_),
        "preprocessing_log": json_safe(result["preprocessing_log"]),
        "feature_selection_log": json_safe(result["feature_selection_log"]),
        "feature_scores": json_safe(result["feature_scores"]),
        "feature_ranking": json_safe(result["feature_ranking"]),
        "feature_provenance": json_safe(result["feature_provenance"]),
        "artifacts": {
            "train_file_id": str(train_file_id),
            "test_file_id": str(test_file_id),
        },
        "created_at": created_at.isoformat(),
    }


async def get_owned_run(run_id: str, user: dict):
    """Fetch a run only if it belongs to the authenticated user."""
    if not ObjectId.is_valid(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preprocessing run not found.",
        )

    owner_id = ObjectId(user["id"])
    runs = get_preprocessing_runs_collection()
    datasets = get_datasets_collection()

    run = await runs.find_one({
        "_id": ObjectId(run_id),
        "owner_id": owner_id,
    })

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preprocessing run not found.",
        )

    # Also verify the original dataset still belongs to this user.
    dataset = await datasets.find_one({
        "_id": run["dataset_id"],
        "owner_id": owner_id,
    })

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    return run


def serialize_run(run: dict) -> dict:
    """Return safe, JSON-serializable run metadata."""
    artifacts = run.get("artifacts", {})

    return {
        "run_id": str(run["_id"]),
        "dataset_id": str(run["dataset_id"]),
        "status": run.get("status"),
        "target_column": run.get("target_column"),
        "test_size": run.get("test_size"),
        "random_state": run.get("random_state"),
        "created_at": run["created_at"].isoformat(),
        "train_rows": run.get("train_rows"),
        "test_rows": run.get("test_rows"),
        "rows_removed_missing_target": run.get(
            "rows_removed_missing_target", 0
        ),
        "feature_count": run.get("feature_count"),
        "selected_features": json_safe(
            run.get("selected_features", [])
        ),
        "dropped_columns": json_safe(
            run.get("dropped_columns", [])
        ),
        "preprocessing_log": json_safe(
            run.get("preprocessing_log", [])
        ),
        "feature_selection_log": json_safe(
            run.get("feature_selection_log", [])
        ),
        "feature_scores": json_safe(
            run.get("feature_scores", {})
        ),
        "feature_ranking": json_safe(
            run.get("feature_ranking", [])
        ),
        "feature_provenance": json_safe(
            run.get("feature_provenance", [])
        ),
        "artifacts": {
            "train_available": bool(artifacts.get("train_file_id")),
            "test_available": bool(artifacts.get("test_file_id")),
        },
    }


@router.get("/{dataset_id}/runs")
async def list_preprocessing_runs(
    dataset_id: str,
    user: dict = Depends(current_user),
):
    """List recent preprocessing runs for an owned dataset."""
    datasets = get_datasets_collection()
    query = owned_dataset_query(dataset_id, user["id"])

    dataset = await datasets.find_one(query)

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    runs = get_preprocessing_runs_collection()
    cursor = (
        runs.find({
            "dataset_id": dataset["_id"],
            "owner_id": ObjectId(user["id"]),
        })
        .sort("created_at", -1)
        .limit(100)
    )

    results = []

    async for run in cursor:
        results.append(serialize_run(run))

    return {
        "dataset_id": dataset_id,
        "runs": results,
    }


@router.get("/runs/{run_id}")
async def get_preprocessing_run(
    run_id: str,
    user: dict = Depends(current_user),
):
    """Get the details of one owned preprocessing run."""
    run = await get_owned_run(run_id, user)
    return serialize_run(run)


@router.get("/runs/{run_id}/download/{split}")
async def download_preprocessed_csv(
    run_id: str,
    split: str,
    user: dict = Depends(current_user),
):
    """Download the processed training or testing CSV."""
    if split not in {"train", "test"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Split must be 'train' or 'test'.",
        )

    run = await get_owned_run(run_id, user)

    artifact_key = f"{split}_file_id"
    file_id = run.get("artifacts", {}).get(artifact_key)

    if not file_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested artifact not found.",
        )

    bucket = get_gridfs_bucket()

    try:
        stream = await bucket.open_download_stream(file_id)
        contents = await stream.read()
    except Exception as exc:
        logger.exception(
            "Could not read %s artifact for run %s", split, run_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processed file not found.",
        ) from exc

    filename = f"preprocessed_{split}_{run_id}.csv"

    return StreamingResponse(
        BytesIO(contents),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
