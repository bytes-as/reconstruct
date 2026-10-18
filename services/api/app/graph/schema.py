"""Idempotent schema bootstrap for hub, tenant, and sandbox graphs."""

from falkordb import FalkorDB

from app.graph import queries
from app.graph.db import list_graphs, query


def statements(block: str) -> list[str]:
    return [part.strip() for part in block.split(";") if part.strip()]


def apply_block(graph: str, block: str, db: FalkorDB | None = None) -> None:
    for statement in statements(block):
        try:
            query(graph, statement, db=db)
        except Exception as exc:
            if "already indexed" in str(exc).lower():
                continue
            raise


def bootstrap(db: FalkorDB | None = None) -> None:
    apply_block("hub", queries.SCHEMA_HUB, db=db)
    for name in list_graphs(db):
        if name.startswith("tenant_") or name.startswith("sbx_"):
            apply_block(name, queries.SCHEMA_TENANT, db=db)
