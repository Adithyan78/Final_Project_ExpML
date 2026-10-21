
from pymongo import AsyncMongoClient
from gridfs import AsyncGridFSBucket

from .config import MONGODB_URI, MONGODB_DATABASE

client = None
db = None
users = None
datasets = None
gridfs_bucket = None


async def connect_db():
    global client, db, users, datasets, gridfs_bucket

    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is missing from .env")

    client = AsyncMongoClient(MONGODB_URI)

    try:
        await client.admin.command("ping")

        db = client[MONGODB_DATABASE]
        users = db["users"]
        datasets = db["datasets"]
        gridfs_bucket = AsyncGridFSBucket(db)

        await users.create_index("email", unique=True)
        await datasets.create_index(
            [("owner_id", 1), ("created_at", -1)]
        )

        print("MongoDB connected successfully.")

    except Exception:
        await client.close()
        client = None
        db = None
        users = None
        datasets = None
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


def get_gridfs_bucket():
    if gridfs_bucket is None:
        raise RuntimeError("GridFS is not connected.")
    return gridfs_bucket


async def close_db():
    global client, db, users, datasets, gridfs_bucket

    if client is not None:
        await client.close()

    client = None
    db = None
    users = None
    datasets = None
    gridfs_bucket = None

    print("MongoDB connection closed.")
