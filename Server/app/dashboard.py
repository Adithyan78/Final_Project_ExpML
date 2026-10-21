
from bson import ObjectId
from fastapi import APIRouter, Depends

from .auth import current_user
from .database import get_datasets_collection

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def dashboard_summary(
    user: dict = Depends(current_user),
):
    collection = get_datasets_collection()
    owner_id = ObjectId(user["id"])

    total_datasets = await collection.count_documents(
        {"owner_id": owner_id}
    )

    recent_uploads = []
    cursor = (
        collection.find({"owner_id": owner_id})
        .sort("created_at", -1)
        .limit(5)
    )

    async for doc in cursor:
        recent_uploads.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "n_rows": doc["n_rows"],
            "n_cols": doc["n_cols"],
            "created_at": doc["created_at"].isoformat(),
        })

    return {
        "stats": {
            "total_projects": 0,
            "total_datasets": total_datasets,
            "experiments": 0,
            "completed_runs": 0,
        },
        "recent_uploads": recent_uploads,
    }
