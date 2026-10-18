"""G010: query, copy, delete and retry against FalkorDB."""

from app.graph.db import connect_once, copy_graph, delete_graph, list_graphs, query, retry, ro_query

GRAPH = "hub_dbtest"
COPY = "hub_dbtest_copy"


def test_retry_backs_off_without_sleeping_for_real() -> None:
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("down")
        return "up"

    slept: list[float] = []
    assert retry(flaky, attempts=10, delay_s=2, sleeper=slept.append) == "up"
    assert slept == [2, 2]


def test_query_copy_and_delete() -> None:
    db = connect_once()
    delete_graph(GRAPH, db=db)
    delete_graph(COPY, db=db)
    query(GRAPH, "CREATE (:Probe {id: $id})", {"id": "p1"}, db=db)
    found = ro_query(GRAPH, "MATCH (n:Probe {id: $id}) RETURN n.id", {"id": "p1"}, db=db)
    assert found.result_set[0][0] == "p1"
    copy_graph(GRAPH, COPY, db=db)
    names = list_graphs(db)
    assert COPY in names
    copied = ro_query(COPY, "MATCH (n:Probe {id: $id}) RETURN n.id", {"id": "p1"}, db=db)
    assert copied.result_set[0][0] == "p1"
    delete_graph(GRAPH, db=db)
    delete_graph(COPY, db=db)
    names = list_graphs(db)
    assert GRAPH not in names
    assert COPY not in names
