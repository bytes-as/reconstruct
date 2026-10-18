"""G048: verdicts as of a past date skip the listing gate."""

from app.engine.verdict import decide
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_asof"
FACT = "montelukast_bw_2020"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def _class(ndc: str, as_of: str) -> dict:
    result = decide(ndc, fact_id=FACT, as_of=as_of, graph=GRAPH)["results"][0]
    assert result["replay"] is True
    assert result["gate_skipped"] is True
    return result


def test_accord_avkare_and_preferred() -> None:
    assert _class("16729-119-15", "2020-06-01")["verdict"] == "NOT_LANDED_UNREVISED"
    assert _class("16729-119-15", "2021-03-10")["verdict"] == "NOT_LANDED_REVISED"
    assert _class("16729-119-15", "2021-06-01")["verdict"] == "LANDED"
    assert _class("42291-622-30", "2025-11-01")["verdict"] == "NOT_LANDED_REVISED"
    assert _class("42291-622-30", "2025-11-20")["verdict"] == "LANDED_UNCODED"
    assert _class("68788-7669-1", "2020-05-15")["verdict"] == "NOT_LANDED_UNREVISED"
    assert _class("68788-7669-1", "2021-09-01")["verdict"] == "LANDED"
