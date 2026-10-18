"""G036: each verdict branch, with the class taken from V4."""

from app.engine.verdict import decide
from app.graph.db import delete_graph, query, ro_query
from app.graph.fixture import load_fixture

GRAPH = "hub_logic"


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def _verdict(ndc: str, **kwargs) -> dict:
    body = decide(ndc, fact_id="montelukast_bw_2020", graph=GRAPH, **kwargs)
    return body["results"][0]


def test_classes_come_from_the_graph() -> None:
    assert _verdict("31722-726-90")["verdict"] == "LANDED"
    assert _verdict("42291-622-30")["verdict"] == "LANDED_UNCODED"
    assert _verdict("68071-3355-9")["verdict"] == "NOT_LANDED_REVISED"
    assert _verdict("63187-626-30")["verdict"] == "NOT_LANDED_UNREVISED"
    assert _verdict("65862-843")["verdict"] == "NOT_IN_SCOPE"


def test_unknown_ndc() -> None:
    assert decide("00000-0000-00", graph=GRAPH)["reason"] == "NDC_NOT_FOUND"


def test_inactive_listing_and_missing_record() -> None:
    original = ro_query(
        GRAPH,
        "MATCH (p:Product {ndc: $ndc}) RETURN p.listing_expiration_d, p.listing_spl_id",
        {"ndc": "68071-3355"},
    ).result_set[0]
    query(
        GRAPH, "MATCH (p:Product {ndc: $ndc}) SET p.listing_expiration_d = 1", {"ndc": "68071-3355"}
    )
    assert _verdict("68071-3355-9")["verdict"] == "NOT_ASSESSED_INACTIVE_LISTING"
    query(
        GRAPH,
        "MATCH (p:Product {ndc: $ndc}) "
        "SET p.listing_expiration_d = $expiration, p.listing_spl_id = $spl",
        {"ndc": "68071-3355", "expiration": original[0], "spl": "missing-doc"},
    )
    missing = _verdict("68071-3355-9")
    assert missing["verdict"] == "UNKNOWN"
    assert missing["reason"] == "LABEL_OF_RECORD_NOT_INGESTED"
    query(
        GRAPH,
        "MATCH (p:Product {ndc: $ndc}) SET p.listing_spl_id = $spl",
        {"ndc": "68071-3355", "spl": original[1]},
    )


def test_strict_absence_is_unknown() -> None:
    result = _verdict("68071-3355-9", strict=True)
    assert result["verdict"] == "UNKNOWN"
