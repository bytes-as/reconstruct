"""Landfall API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect
from app.graph.schema import bootstrap
from app.logging import RequestIdMiddleware, configure_logging, logger
from app.routes.health import router as health_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()
    try:
        db = connect()
        bootstrap(db)
        logger.info("schema bootstrap complete")
    except Exception:
        logger.warning("FalkorDB is down at startup; /api/health will report falkordb down")
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Landfall", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
