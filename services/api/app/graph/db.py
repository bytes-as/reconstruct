"""FalkorDB connection used by health. G010 adds query, copy and delete."""

from falkordb import FalkorDB

from app.config import get_settings

_EMPTY_HUB = {
    "label_sets": 0,
    "labels_of_record": 0,
    "versions": 0,
    "checks": 0,
    "facts_active": 0,
}


def connect() -> FalkorDB:
    settings = get_settings()
    password = settings.falkordb_password or None
    return FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port, password=password)


def list_graphs(db: FalkorDB) -> list[str]:
    raw = db.list_graphs()
    names: list[str] = []
    for item in raw:
        names.append(item.decode() if isinstance(item, bytes) else str(item))
    return names


def _count(db: FalkorDB, cypher: str) -> int:
    result = db.select_graph("hub").ro_query(cypher)
    if not result.result_set:
        return 0
    return int(result.result_set[0][0])


def hub_counts(db: FalkorDB, graphs: list[str]) -> dict[str, int]:
    if "hub" not in graphs:
        return dict(_EMPTY_HUB)
    return {
        "label_sets": _count(db, "MATCH (s:LabelSet) RETURN count(s)"),
        "labels_of_record": _count(db, "MATCH (s:LabelSet {label_of_record: true}) RETURN count(s)"),
        "versions": _count(db, "MATCH (v:LabelVersion) RETURN count(v)"),
        "checks": _count(db, "MATCH ()-[c:CHECKED]->() RETURN count(c)"),
        "facts_active": _count(db, "MATCH (f:SafetyFact {status: 'ACTIVE'}) RETURN count(f)"),
    }
