"""G042: the 69 labels of record, classed by V4."""

from app.engine.verdict import census
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_census"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_census_matches_the_fixture() -> None:
    counts = census(GRAPH)
    assert counts["LANDED"] == 54
    assert counts["LANDED_UNCODED"] == 2
    assert counts["NOT_LANDED_REVISED"] == 9
    assert counts["NOT_LANDED_UNREVISED"] == 4
    assert sum(counts.values()) == 69
