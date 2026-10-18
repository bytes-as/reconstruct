"""G016: fixture counts after loading through the I-queries."""

from app.graph.db import connect_once, delete_graph, ro_query
from app.graph.fixture import load_fixture

GRAPH = "hub_test"


def _count(db, cypher: str) -> int:
    result = ro_query(GRAPH, cypher, db=db)
    return int(result.result_set[0][0])


def test_fixture_counts() -> None:
    db = connect_once()
    load_fixture(GRAPH, db=db)
    assert _count(db, "MATCH (s:LabelSet) RETURN count(s)") == 71
    assert _count(db, "MATCH (v:LabelVersion) RETURN count(v)") == 388
    assert _count(db, "MATCH (p:Product) RETURN count(p)") == 100
    assert _count(db, "MATCH (k:Package) RETURN count(k)") == 275
    assert _count(db, "MATCH (a:Application) RETURN count(a)") == 28
    assert _count(db, "MATCH ()-[c:CHECKED]->() RETURN count(c)") == 230
    assert _count(db, "MATCH ()-[e:SOURCED_FROM]->() RETURN count(e)") == 45
    assert _count(db, "MATCH ()-[r:REFERENCES]->() RETURN count(r)") == 25
    assert _count(db, "MATCH (s:LabelSet {label_of_record: true}) RETURN count(s)") == 69
    delete_graph(GRAPH, db=db)
