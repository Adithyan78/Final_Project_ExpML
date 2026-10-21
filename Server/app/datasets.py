
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath

import pandas as pd
from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from .auth import current_user
from .database import (
    get_datasets_collection,
    get_gridfs_bucket,
)
from .dataset_analyzer import analyze_dataset


router = APIRouter(tags=["Datasets"])

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_COLUMNS = 500


def serialize_dataset(doc):
    """Convert MongoDB dataset metadata into a JSON-safe response."""
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "size_bytes": doc["size_bytes"],
        "n_rows": doc["n_rows"],
        "n_cols": doc["n_cols"],
        "target_column": doc.get("target_column"),
        "profile": doc["profile"],
        "created_at": doc["created_at"].isoformat(),
    }


def owned_dataset_query(dataset_id, user_id):
    """Build a query restricted to the authenticated user's dataset."""
    if not ObjectId.is_valid(dataset_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    return {
        "_id": ObjectId(dataset_id),
        "owner_id": ObjectId(user_id),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    target_column: str | None = Form(default=None),
    user: dict = Depends(current_user),
):
    """Upload a CSV, analyze it, and store the file and metadata."""

    filename = PurePosixPath(file.filename or "").name

    if not filename or not filename.lower().endswith(".csv"):
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a CSV file.",
        )

    try:
        # Read at most 50 MB + 1 byte to enforce the size limit.
        contents = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Maximum CSV size is 50 MB.",
        )

    try:
        df = pd.read_csv(BytesIO(contents))
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to read this CSV. Check its encoding and format.",
        ) from exc

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The CSV has no data rows.",
        )

    if len(df.columns) > MAX_COLUMNS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV exceeds the {MAX_COLUMNS}-column limit.",
        )

    if not all(isinstance(column, str) for column in df.columns):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column names must be text.",
        )

    if target_column:
        if target_column not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target column '{target_column}' was not found.",
            )

    try:
        profile = analyze_dataset(
            df,
            target_column=target_column or None,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset analysis failed. Check the CSV and target column.",
        ) from exc
    except Exception as exc:
        # Log the exception server-side when application logging is configured.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The CSV was read, but analysis could not be completed.",
        ) from exc

    user_id = ObjectId(user["id"])
    bucket = get_gridfs_bucket()
    collection = get_datasets_collection()

    file_id = None

    try:
        # Store the original CSV in MongoDB GridFS.
        file_id = await bucket.upload_from_stream(
            filename,
            contents,
            metadata={
                "owner_id": str(user_id),
                "content_type": "text/csv",
            },
        )

        document = {
            "owner_id": user_id,
            "name": filename,
            "size_bytes": len(contents),
            "file_id": file_id,
            "n_rows": int(df.shape[0]),
            "n_cols": int(df.shape[1]),
            "target_column": target_column or None,
            "profile": profile,
            "created_at": datetime.now(timezone.utc),
        }

        result = await collection.insert_one(document)
        document["_id"] = result.inserted_id

        return serialize_dataset(document)

    except Exception as exc:
        # Remove the GridFS file if saving the metadata fails.
        if file_id is not None:
            try:
                await bucket.delete(file_id)
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the dataset. Please try again.",
        ) from exc


@router.get("")
async def list_datasets(
    user: dict = Depends(current_user),
):
    """List the authenticated user's datasets without full profiles."""

    collection = get_datasets_collection()
    user_id = ObjectId(user["id"])

    cursor = (
        collection.find({"owner_id": user_id})
        .sort("created_at", -1)
        .limit(100)
    )

    results = []

    async for doc in cursor:
        results.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "size_bytes": doc["size_bytes"],
            "n_rows": doc["n_rows"],
            "n_cols": doc["n_cols"],
            "target_column": doc.get("target_column"),
            "created_at": doc["created_at"].isoformat(),
        })

    return {"datasets": results}


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    user: dict = Depends(current_user),
):
    """Return one dataset and its analysis profile."""

    collection = get_datasets_collection()
    query = owned_dataset_query(dataset_id, user["id"])

    doc = await collection.find_one(query)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    return serialize_dataset(doc)


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    user: dict = Depends(current_user),
):
    """Delete a dataset's original CSV and metadata."""

    collection = get_datasets_collection()
    bucket = get_gridfs_bucket()
    query = owned_dataset_query(dataset_id, user["id"])

    doc = await collection.find_one(query)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    # Delete the stored CSV first, retaining metadata if this fails.
    try:
        await bucket.delete(doc["file_id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Could not delete the original CSV. "
                "Dataset metadata was retained."
            ),
        ) from exc

    await collection.delete_one(query)

    return {"message": "Dataset deleted successfully."}
