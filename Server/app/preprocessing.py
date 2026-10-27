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


async def save_artifact(
    bucket,
    filename: str,
    contents: bytes,
    owner_id: ObjectId,
    dataset_id: ObjectId,
    run_id: ObjectId,
    artifact_type: str,
    content_type: str,
):
    """Save an artifact in GridFS with ownership and run metadata."""
    return await bucket.upload_from_stream(
        filename,
        contents,
        metadata={
            "owner_id": str(owner_id),
            "dataset_id": str(dataset_id),
            "run_id": str(run_id),
            "artifact_type": artifact_type,
            "content_type": content_type,
        },
    )


async def save_csv_artifact(
    bucket,
    filename: str,
    contents: bytes,
    owner_id: ObjectId,
    dataset_id: ObjectId,
    run_id: ObjectId,
    artifact_type: str,
):
    return await save_artifact(
        bucket, filename, contents, owner_id, dataset_id, run_id,
        artifact_type, "text/csv",
    )


async def save_json_artifact(
    bucket,
    filename: str,
    contents: bytes,
    owner_id: ObjectId,
    dataset_id: ObjectId,
    run_id: ObjectId,
    artifact_type: str,
):
    return await save_artifact(
        bucket, filename, contents, owner_id, dataset_id, run_id,
        artifact_type, "application/json",
    )


@router.post("/{dataset_id}", status_code=status.HTTP_201_CREATED)
async def preprocess_dataset(
    dataset_id: str,
    request: PreprocessingRequest,
    user: dict = Depends(current_user),
):
    """Preprocess an owned dataset and save CSV and JSON run artifacts."""
    datasets = get_datasets_collection()
    runs = get_preprocessing_runs_collection()
    bucket = get_gridfs_bucket()

    query = owned_dataset_query(dataset_id, user["id"])
    dataset = await datasets.find_one(query)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    target = request.target_column or dataset.get("target_column")
    if not target:
        raise HTTPException(
            status_code=400,
            detail="Select a target column before preprocessing.",
        )

    try:
        stream = await bucket.open_download_stream(dataset["file_id"])
        original_bytes = await stream.read()
        df = pd.read_csv(BytesIO(original_bytes))
    except Exception as exc:
        logger.exception("Could not read original dataset %s", dataset_id)
        raise HTTPException(
            status_code=500, detail="Could not read the original dataset."
        ) from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="The dataset contains no data rows.")
    if target not in df.columns:
        raise HTTPException(
            status_code=400, detail=f"Target column '{target}' was not found."
        )
    if df[target].nunique(dropna=True) < 2:
        raise HTTPException(
            status_code=400,
            detail="The target must contain at least two distinct classes.",
        )

    missing_target_rows = int(df[target].isna().sum())
    df = df.loc[df[target].notna()].copy()
    if len(df) < 5:
        raise HTTPException(
            status_code=400,
            detail="At least five rows with a target value are required.",
        )

    y = df[target]
    X = df.drop(columns=[target])
    if X.empty:
        raise HTTPException(
            status_code=400,
            detail="The dataset must contain at least one feature besides the target.",
        )

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
            X, y, test_size=request.test_size, random_state=42, stratify=stratify
        )
        profile = analyze_dataset(df, target_column=target)
        engine = PreprocessingEngine()
        result = engine.fit_transform(
            X_train, y_train, profile, user_config=request.user_config
        )

        X_train_processed = result["data"].copy()
        X_test_processed = engine.transform(X_test)
        X_train_processed[target] = y_train.loc[X_train_processed.index]
        X_test_processed[target] = y_test.loc[X_test_processed.index]

        train_csv = dataframe_to_csv_bytes(X_train_processed.reset_index(drop=True))
        test_csv = dataframe_to_csv_bytes(X_test_processed.reset_index(drop=True))
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Preprocessing rejected for dataset %s", dataset_id)
        raise HTTPException(
            status_code=400,
            detail=f"Preprocessing could not be completed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Preprocessing failed for dataset %s", dataset_id)
        raise HTTPException(
            status_code=422,
            detail="Preprocessing failed. Check the dataset and preprocessing configuration.",
        ) from exc

    owner_id = ObjectId(user["id"])
    dataset_object_id = ObjectId(dataset_id)
    run_id = ObjectId()
    created_at = datetime.now(timezone.utc)
    saved_file_ids = []

    # Store the actual data already returned by this engine as readable JSON reports.
    summary_report = {
        "run_id": str(run_id),
        "dataset_id": dataset_id,
        "target_column": target,
        "test_size": request.test_size,
        "rows_before_target_cleanup": int(dataset.get("n_rows", len(df) + missing_target_rows)),
        "rows_removed_missing_target": missing_target_rows,
        "rows_after_target_cleanup": int(len(df)),
        "train_rows": int(len(X_train_processed)),
        "test_rows": int(len(X_test_processed)),
        "feature_count": int(len(result["selected_features"])),
        "selected_features": json_safe(result["selected_features"]),
        "dropped_columns": json_safe(engine.dropped_columns_),
        "created_at": created_at.isoformat(),
    }
    log_report = {
        "preprocessing_log": json_safe(result["preprocessing_log"]),
        "feature_selection_log": json_safe(result["feature_selection_log"]),
    }
    provenance_report = {
        "feature_provenance": json_safe(result["feature_provenance"]),
        "feature_scores": json_safe(result["feature_scores"]),
        "feature_ranking": json_safe(result["feature_ranking"]),
    }

    json_reports = {
        "preprocessing_summary.json": ("preprocessing_summary", summary_report),
        "preprocessing_log.json": ("preprocessing_log", log_report),
        "feature_provenance.json": ("feature_provenance", provenance_report),
    }

    try:
        train_file_id = await save_csv_artifact(
            bucket, f"{run_id}_train.csv", train_csv, owner_id,
            dataset_object_id, run_id, "processed_train"
        )
        saved_file_ids.append(train_file_id)
        test_file_id = await save_csv_artifact(
            bucket, f"{run_id}_test.csv", test_csv, owner_id,
            dataset_object_id, run_id, "processed_test"
        )
        saved_file_ids.append(test_file_id)

        json_artifact_ids = {}
        for filename, (artifact_type, payload) in json_reports.items():
            contents = json.dumps(
                json_safe(payload), ensure_ascii=False, indent=2
            ).encode("utf-8")
            file_id = await save_json_artifact(
                bucket, f"{run_id}_{filename}", contents, owner_id,
                dataset_object_id, run_id, artifact_type
            )
            saved_file_ids.append(file_id)
            json_artifact_ids[filename] = file_id

        run_document = {
            "_id": run_id,
            "owner_id": owner_id,
            "dataset_id": dataset_object_id,
            "target_column": target,
            "test_size": request.test_size,
            "random_state": 42,
            "created_at": created_at,
            "status": "completed",
            "rows_before_target_cleanup": int(dataset.get("n_rows", len(df) + missing_target_rows)),
            "rows_removed_missing_target": missing_target_rows,
            "rows_after_target_cleanup": int(len(df)),
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
                "train_file_id": train_file_id,
                "test_file_id": test_file_id,
                "json_reports": json_artifact_ids,
            },
        }
        await runs.insert_one(run_document)
    except Exception as exc:
        for file_id in saved_file_ids:
            try:
                await bucket.delete(file_id)
            except Exception:
                logger.exception("Could not clean up artifact %s", file_id)
        logger.exception("Could not save preprocessing run")
        raise HTTPException(
            status_code=500, detail="Could not save preprocessing results."
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
        "json_reports": list(json_artifact_ids.keys()),
        "artifacts": {
            "train_file_id": str(train_file_id),
            "test_file_id": str(test_file_id),
        },
        "created_at": created_at.isoformat(),
    }


async def get_owned_run(run_id: str, user: dict):
    """Fetch a run only if it belongs to the authenticated user."""
    if not ObjectId.is_valid(run_id):
        raise HTTPException(status_code=404, detail="Preprocessing run not found.")
    owner_id = ObjectId(user["id"])
    runs = get_preprocessing_runs_collection()
    datasets = get_datasets_collection()
    run = await runs.find_one({"_id": ObjectId(run_id), "owner_id": owner_id})
    if not run:
        raise HTTPException(status_code=404, detail="Preprocessing run not found.")
    dataset = await datasets.find_one({"_id": run["dataset_id"], "owner_id": owner_id})
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return run


def serialize_run(run: dict) -> dict:
    artifacts = run.get("artifacts", {})
    json_reports = artifacts.get("json_reports", {})
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
        "rows_removed_missing_target": run.get("rows_removed_missing_target", 0),
        "feature_count": run.get("feature_count"),
        "selected_features": json_safe(run.get("selected_features", [])),
        "dropped_columns": json_safe(run.get("dropped_columns", [])),
        "preprocessing_log": json_safe(run.get("preprocessing_log", [])),
        "feature_selection_log": json_safe(run.get("feature_selection_log", [])),
        "feature_scores": json_safe(run.get("feature_scores", {})),
        "feature_ranking": json_safe(run.get("feature_ranking", [])),
        "feature_provenance": json_safe(run.get("feature_provenance", [])),
        "artifacts": {
            "train_available": bool(artifacts.get("train_file_id")),
            "test_available": bool(artifacts.get("test_file_id")),
            "json_reports": list(json_reports.keys()),
        },
    }


@router.get("/{dataset_id}/runs")
async def list_preprocessing_runs(
    dataset_id: str,
    user: dict = Depends(current_user),
):
    datasets = get_datasets_collection()
    dataset = await datasets.find_one(owned_dataset_query(dataset_id, user["id"]))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
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
    return {"dataset_id": dataset_id, "runs": results}


@router.get("/runs/{run_id}")
async def get_preprocessing_run(
    run_id: str,
    user: dict = Depends(current_user),
):
    run = await get_owned_run(run_id, user)
    return serialize_run(run)


@router.get("/runs/{run_id}/reports")
async def get_preprocessing_reports(
    run_id: str,
    user: dict = Depends(current_user),
):
    """Return the stored JSON reports for a run owned by the current user."""
    run = await get_owned_run(run_id, user)
    bucket = get_gridfs_bucket()
    report_ids = run.get("artifacts", {}).get("json_reports", {})
    reports = {}

    for filename, file_id in report_ids.items():
        try:
            stream = await bucket.open_download_stream(file_id)
            contents = await stream.read()
            reports[filename] = json.loads(contents.decode("utf-8"))
        except Exception as exc:
            logger.exception("Could not read JSON report %s for run %s", filename, run_id)
            raise HTTPException(
                status_code=404,
                detail=f"Report '{filename}' could not be read.",
            ) from exc
    return {"run_id": run_id, "reports": reports}


@router.get("/runs/{run_id}/reports/{filename}")
async def download_preprocessing_report(
    run_id: str,
    filename: str,
    user: dict = Depends(current_user),
):
    """Download one of the stored JSON reports for an owned run."""
    run = await get_owned_run(run_id, user)
    report_ids = run.get("artifacts", {}).get("json_reports", {})
    file_id = report_ids.get(filename)
    if not file_id or filename not in {
        "preprocessing_summary.json",
        "preprocessing_log.json",
        "feature_provenance.json",
    }:
        raise HTTPException(status_code=404, detail="JSON report not found.")

    bucket = get_gridfs_bucket()
    try:
        stream = await bucket.open_download_stream(file_id)
        contents = await stream.read()
    except Exception as exc:
        logger.exception("Could not download report %s for run %s", filename, run_id)
        raise HTTPException(status_code=404, detail="JSON report not found.") from exc

    return StreamingResponse(
        BytesIO(contents),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/download/{split}")
async def download_preprocessed_csv(
    run_id: str,
    split: str,
    user: dict = Depends(current_user),
):
    if split not in {"train", "test"}:
        raise HTTPException(status_code=400, detail="Split must be 'train' or 'test'.")
    run = await get_owned_run(run_id, user)
    file_id = run.get("artifacts", {}).get(f"{split}_file_id")
    if not file_id:
        raise HTTPException(status_code=404, detail="Requested artifact not found.")
    bucket = get_gridfs_bucket()
    try:
        stream = await bucket.open_download_stream(file_id)
        contents = await stream.read()
    except Exception as exc:
        logger.exception("Could not read %s artifact for run %s", split, run_id)
        raise HTTPException(status_code=404, detail="Processed file not found.") from exc
    filename = f"preprocessed_{split}_{run_id}.csv"
    return StreamingResponse(
        BytesIO(contents),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
