"""FalkorDB connection. Reads retry; writes go through parameterised query calls."""

import time
from collections.abc import Callable

from falkordb import FalkorDB

from app.config import get_settings

_EMPTY_HUB = {
    "label_sets": 0,
    "labels_of_record": 0,
    "versions": 0,
    "checks": 0,
    "facts_active": 0,
}


def connect_once() -> FalkorDB:
    settings = get_settings()
    password = settings.falkordb_password or None
    return FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port, password=password)


def retry(
    operation: Callable,
    attempts: int = 10,
    delay_s: float = 2,
    sleeper: Callable[[float], None] = time.sleep,
):
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last = exc
            if attempt == attempts - 1:
                break
            sleeper(delay_s)
    assert last is not None
    raise last


def connect() -> FalkorDB:
    return retry(connect_once)


def list_graphs(db: FalkorDB | None = None) -> list[str]:
    client = db or connect_once()
    raw = client.list_graphs()
    return [item.decode() if isinstance(item, bytes) else str(item) for item in raw]


def select(name: str, db: FalkorDB | None = None):
    client = db or connect_once()
    return client.select_graph(name)


def query(name: str, cypher: str, params: dict | None = None, db: FalkorDB | None = None):
    return select(name, db).query(cypher, params or {})


def ro_query(name: str, cypher: str, params: dict | None = None, db: FalkorDB | None = None):
    return select(name, db).ro_query(cypher, params or {})


def copy_graph(src: str, dst: str, db: FalkorDB | None = None) -> None:
    client = db or connect_once()
    client.connection.execute_command("GRAPH.COPY", src, dst)


def delete_graph(name: str, db: FalkorDB | None = None) -> None:
    client = db or connect_once()
    try:
        client.connection.execute_command("GRAPH.DELETE", name)
    except Exception as exc:
        if "invalid graph" in str(exc).lower() or "empty key" in str(exc).lower():
            return
        raise


def _count(db: FalkorDB, cypher: str) -> int:
    result = ro_query("hub", cypher, db=db)
    if not result.result_set:
        return 0
    return int(result.result_set[0][0])


def hub_counts(db: FalkorDB, graphs: list[str]) -> dict[str, int]:
    if "hub" not in graphs:
        return dict(_EMPTY_HUB)
    return {
        "label_sets": _count(db, "MATCH (s:LabelSet) RETURN count(s)"),
        "labels_of_record": _count(
            db, "MATCH (s:LabelSet {label_of_record: true}) RETURN count(s)"
        ),
        "versions": _count(db, "MATCH (v:LabelVersion) RETURN count(v)"),
        "checks": _count(db, "MATCH ()-[c:CHECKED]->() RETURN count(c)"),
        "facts_active": _count(db, "MATCH (f:SafetyFact {status: 'ACTIVE'}) RETURN count(f)"),
    }
