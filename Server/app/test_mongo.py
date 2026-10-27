
import asyncio
from pymongo import AsyncMongoClient
from app.config import MONGODB_URI


async def main():
    client = AsyncMongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000,
    )

    try:
        result = await client.admin.command("ping")
        print("MongoDB connection successful!")
        print(result)
    except Exception as e:
        print(f"MongoDB connection failed: {type(e).__name__}")
        print(e)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
