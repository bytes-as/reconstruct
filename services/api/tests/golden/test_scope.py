"""G041: no path to a reference application."""

from app.engine.verdict import decide
from app.graph import queries
from app.graph.db import delete_graph, query
from app.graph.fixture import load_fixture

GRAPH = "hub_scope"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_bulk_ingredient_is_not_in_scope() -> None:
    result = decide("65862-843", fact_id="montelukast_bw_2020", graph=GRAPH)["results"][0]
    assert result["verdict"] == "NOT_IN_SCOPE"
    assert result["proof"]["searched"] == "SOURCED_FROM|UNDER|REFERENCES*1..5"


def test_application_without_kind_is_unresolved() -> None:
    query(
        GRAPH,
        queries.I6,
        {
            "ndc": "99999-1",
            "labeler_name": "Synthetic",
            "molecule_key": "montelukast",
            "dosage_form": "TABLET",
            "strength": "10 mg/1",
            "marketing_category": "ANDA",
            "listing_spl_id": None,
            "listing_expiration_d": 30000,
            "in_ndc_directory": True,
            "now": 1,
            "application_id": "ANDA999999",
        },
    )
    result = decide("99999-1", fact_id="montelukast_bw_2020", graph=GRAPH)["results"][0]
    assert result["verdict"] == "UNKNOWN"
    assert result["reason"] == "SCOPE_UNRESOLVED"
