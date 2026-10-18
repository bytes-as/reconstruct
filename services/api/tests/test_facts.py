"""G027: facts.seed.json loads through I11 and I12."""

from app.agents.facts import load_facts
from app.graph.db import delete_graph, query, ro_query
from app.graph.fixture import load_fixture

GRAPH = "hub_facts"


def _count(cypher: str, params: dict | None = None) -> int:
    result = ro_query(GRAPH, cypher, params or {})
    return int(result.result_set[0][0])


def test_seed_facts_on_the_fixture() -> None:
    try:
        load_fixture(GRAPH)
        query(GRAPH, "MATCH (f:SafetyFact) DETACH DELETE f", {})
        loaded = load_facts(GRAPH)
        assert loaded == ["montelukast_bw_2020", "zolpidem_bw_2019"]
        assert (
            _count(
                "MATCH (:SafetyFact {id: $id})-[e:ISSUED_ON]->() RETURN count(e)",
                {"id": "montelukast_bw_2020"},
            )
            == 3
        )
        status = ro_query(
            GRAPH,
            "MATCH (f:SafetyFact {id: $id}) RETURN f.status",
            {"id": "zolpidem_bw_2019"},
        ).result_set[0][0]
        active = ro_query(
            GRAPH,
            "MATCH (f:SafetyFact {id: $id}) RETURN f.status",
            {"id": "montelukast_bw_2020"},
        ).result_set[0][0]
        assert active == "ACTIVE"
        assert status == "UNVERIFIED"
        assert _count("MATCH ()-[r:REFERENCES]->() RETURN count(r)") == 25
    finally:
        delete_graph(GRAPH)
