"""G038: AvKARE carries the phrase outside a coded section."""

from app.engine.verdict import decide
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_uncoded"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_avkare_is_landed_uncoded() -> None:
    result = decide("42291-622-30", fact_id="montelukast_bw_2020", graph=GRAPH)["results"][0]
    assert result["verdict"] == "LANDED_UNCODED"
    assert result["current"]["version"] == 22
    assert result["current"]["published"] == "2025-12-19"
