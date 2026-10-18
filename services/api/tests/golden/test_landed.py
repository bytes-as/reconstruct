"""G039: Camber's label of record carries the coded section."""

from app.engine.verdict import decide
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_landed"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_camber_is_landed() -> None:
    result = decide("31722-726-90", fact_id="montelukast_bw_2020", graph=GRAPH)["results"][0]
    assert result["verdict"] == "LANDED"
