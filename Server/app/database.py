
from pymongo import AsyncMongoClient
from gridfs import AsyncGridFSBucket

from .config import MONGODB_URI, MONGODB_DATABASE


client = None
db = None
users = None
datasets = None
preprocessing_runs = None
training_runs = None
gridfs_bucket = None


async def connect_db():
    global client, db, users, datasets
    global preprocessing_runs, training_runs, gridfs_bucket

    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is missing from .env")

    client = AsyncMongoClient(MONGODB_URI)

    try:
        await client.admin.command("ping")

        db = client[MONGODB_DATABASE]

        users = db["users"]
        datasets = db["datasets"]
        preprocessing_runs = db["preprocessing_runs"]
        training_runs = db["training_runs"]

        gridfs_bucket = AsyncGridFSBucket(db)

        # Indexes
        await users.create_index("email", unique=True)

        await datasets.create_index([
            ("owner_id", 1),
            ("created_at", -1)
        ])

        await preprocessing_runs.create_index([
            ("owner_id", 1),
            ("created_at", -1)
        ])

        await preprocessing_runs.create_index([
            ("dataset_id", 1),
            ("created_at", -1)
        ])

        await training_runs.create_index([
            ("owner_id", 1),
            ("created_at", -1)
        ])

        await training_runs.create_index([
            ("dataset_id", 1),
            ("created_at", -1)
        ])

        await training_runs.create_index([
            ("preprocessing_run_id", 1),
            ("created_at", -1)
        ])

        print("MongoDB connected successfully.")

    except Exception:
        await client.close()

        client = None
        db = None
        users = None
        datasets = None
        preprocessing_runs = None
        training_runs = None
        gridfs_bucket = None

        raise


def get_users_collection():
    if users is None:
        raise RuntimeError("Database is not connected.")
    return users


def get_datasets_collection():
    if datasets is None:
        raise RuntimeError("Database is not connected.")
    return datasets


def get_preprocessing_runs_collection():
    if preprocessing_runs is None:
        raise RuntimeError("Database is not connected.")
    return preprocessing_runs


def get_training_runs_collection():
    if training_runs is None:
        raise RuntimeError("Database is not connected.")
    return training_runs


def get_gridfs_bucket():
    if gridfs_bucket is None:
        raise RuntimeError("GridFS is not connected.")
    return gridfs_bucket


async def close_db():
    global client, db, users, datasets
    global preprocessing_runs, training_runs, gridfs_bucket

    if client is not None:
        await client.close()

    client = None
    db = None
    users = None
    datasets = None
    preprocessing_runs = None
    training_runs = None
    gridfs_bucket = None

    print("MongoDB connection closed.")
