
from pymongo import AsyncMongoClient

from .config import MONGODB_URI, MONGODB_DATABASE

client = None
db = None
users = None


async def connect_db():
    global client, db, users

    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is missing from .env")

    client = AsyncMongoClient(MONGODB_URI)

    try:
        # Verify that MongoDB Atlas is reachable.
        await client.admin.command("ping")

        db = client[MONGODB_DATABASE]
        users = db["users"]

        # Prevent duplicate accounts with the same email.
        await users.create_index("email", unique=True)

        print("MongoDB connected successfully.")

    except Exception:
        await client.close()
        client = None
        db = None
        users = None
        raise


def get_users_collection():
    if users is None:
        raise RuntimeError("Database is not connected.")

    return users


async def close_db():
    global client, db, users

    if client is not None:
        await client.close()

    client = None
    db = None
    users = None

    print("MongoDB connection closed.")
