"""G012: schema bootstrap is idempotent."""

from app.graph.db import connect_once, delete_graph, query
from app.graph.schema import bootstrap

GRAPH = "sbx_bootstrap"


def test_bootstrap_twice() -> None:
    db = connect_once()
    delete_graph(GRAPH, db=db)
    query(GRAPH, "RETURN 1", db=db)
    bootstrap(db)
    bootstrap(db)
    delete_graph(GRAPH, db=db)
