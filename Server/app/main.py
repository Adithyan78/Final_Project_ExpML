
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .auth import router as auth_router
from .datasets import router as datasets_router
from .dashboard import router as dashboard_router
from .database import connect_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is missing from .env")

    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="AutoExplainAI API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(datasets_router, prefix="/datasets")
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"message": "AutoExplainAI API is running."}


@app.get("/health")
async def health():
    return {"status": "ok"}
