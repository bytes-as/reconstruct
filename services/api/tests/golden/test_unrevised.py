"""G040: Proficient Rx has not revised since before the warning."""

from app.engine.verdict import decide
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_unrevised"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_proficient_is_unrevised() -> None:
    result = decide("63187-626-30", fact_id="montelukast_bw_2020", graph=GRAPH)["results"][0]
    assert result["verdict"] == "NOT_LANDED_UNREVISED"
    assert result["current"]["version"] == 3
    assert result["current"]["published"] == "2019-11-21"
