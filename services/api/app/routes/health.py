"""GET /api/health."""

from fastapi import APIRouter

from app.config import get_settings
from app.graph.db import connect, hub_counts, list_graphs

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    settings = get_settings()
    try:
        db = connect()
        graphs = list_graphs(db)
        hub = hub_counts(db, graphs)
        falkordb = "up"
    except Exception:
        graphs = []
        hub = {
            "label_sets": 0,
            "labels_of_record": 0,
            "versions": 0,
            "checks": 0,
            "facts_active": 0,
        }
        falkordb = "down"
    return {
        "ok": falkordb == "up",
        "falkordb": falkordb,
        "graphs": graphs,
        "hub": hub,
        "sources": {"dailymed": "ok", "openfda": "ok"},
        "fixture_mode": settings.fixture_mode,
        "version": settings.version,
    }
