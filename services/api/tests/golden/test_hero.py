"""G037: the NuCare package on the fixture."""

from app.engine.verdict import decide
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_hero"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_hero_is_revised_without_the_warning() -> None:
    body = decide("68071-3355-9", fact_id="montelukast_bw_2020", graph=GRAPH)
    result = body["results"][0]
    assert result["verdict"] == "NOT_LANDED_REVISED"
    assert result["current"]["version"] == 5
    assert result["current"]["published"] == "2024-07-11"
    assert result["revisions_after_fact"] == 2
    assert result["revised_on"] == ["2021-02-16", "2024-07-11"]
    assert result["scope"]["path"] == ["68071-3355", "ANDA202717", "NDA020829"]
    assert result["scope"]["rels"] == ["UNDER", "REFERENCES"]
