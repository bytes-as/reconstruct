"""G028 and G030: XML carry check, and XML replacing an openFDA JSON result."""

import time
from pathlib import Path

from app.engine.matcher import match_openfda, match_xml
from app.graph import queries
from app.graph.db import delete_graph, query, ro_query
from app.graph.fixture import load_fixture

FIXTURES = Path(__file__).parent / "fixtures"
FACT = {
    "phrase_key": "WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS",
    "section_code": "34066-1",
    "phrase_key_version": 1,
}
GRAPH = "hub_matcher"


def test_synthetic_labels() -> None:
    assert match_xml((FIXTURES / "spl_coded.xml").read_bytes(), FACT) == "CARRIES_CODED"
    assert match_xml((FIXTURES / "spl_uncoded.xml").read_bytes(), FACT) == "CARRIES_UNCODED"
    assert match_xml((FIXTURES / "spl_absent.xml").read_bytes(), FACT) == "ABSENT"


def test_openfda_fast_path_uses_the_boxed_warning_field() -> None:
    assert (
        match_openfda({"boxed_warning": ["WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS"]}, FACT)
        == "CARRIES_CODED"
    )
    assert (
        match_openfda({"indications_and_usage": ["WARNING: SERIOUS NEUROPSYCHIATRIC EVENTS"]}, FACT)
        == "CARRIES_UNCODED"
    )
    assert match_openfda({"id": "doc"}, FACT) == "ABSENT"


def test_xml_result_replaces_json_result() -> None:
    try:
        load_fixture(GRAPH)
        version_id = ro_query(GRAPH, "MATCH (v:LabelVersion) RETURN v.id LIMIT 1").result_set[0][0]
        now = int(time.time() * 1000)
        params = {
            "version_id": version_id,
            "fact_id": "montelukast_bw_2020",
            "phrase_key_version": 1,
            "now": now,
        }
        query(
            GRAPH,
            queries.I10,
            {**params, "result": "CARRIES_CODED", "method": "matcher_openfda_json", "tier": 1},
        )
        query(
            GRAPH, queries.I10, {**params, "result": "ABSENT", "method": "matcher_xml", "tier": 1}
        )
        row = ro_query(
            GRAPH,
            "MATCH (:LabelVersion {id: $id})-[c:CHECKED]->(:SafetyFact {id: $fact}) "
            "RETURN c.method, c.result",
            {"id": version_id, "fact": "montelukast_bw_2020"},
        ).result_set[0]
        assert row[0] == "matcher_xml"
        assert row[1] == "ABSENT"
    finally:
        delete_graph(GRAPH)
