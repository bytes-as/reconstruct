"""Landfall API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routes.health import router as health_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()
    yield


app = FastAPI(title="Landfall", lifespan=lifespan)
app.include_router(health_router)
