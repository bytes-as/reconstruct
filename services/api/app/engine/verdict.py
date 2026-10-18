"""Landed verdict. The class string comes from V4."""

from app.engine.identity import identify
from app.graph import queries
from app.graph.db import ro_query
from app.sources.dates import to_d

DISCLAIMER = (
    "Automated screening of public FDA and NLM data. Not medical, legal or regulatory advice. "
    "Not endorsed by FDA or NLM."
)
BULK = {
    "BULK INGREDIENT",
    "BULK INGREDIENT FOR HUMAN PRESCRIPTION COMPOUNDING",
    "DRUG FOR FURTHER PROCESSING",
}
SCOPE_QUERY = (
    "MATCH (p:Product {ndc: $ndc}) "
    "OPTIONAL MATCH (p)-[:UNDER]->(a:Application) "
    "RETURN p.marketing_category AS category, p.molecule_key AS molecule_key, "
    "collect(a.kind) AS kinds"
)
V2_COLUMNS = ("rld", "no_path", "path", "rels")
V3_COLUMNS = (
    "fact_id",
    "title",
    "kind",
    "issued",
    "issued_d",
    "section_code",
    "phrase_key",
    "status",
    "source_url",
)
V4_COLUMNS = (
    "set_id",
    "fact_issued",
    "section_code",
    "current",
    "versions",
    "revisions_after_fact",
    "revised_on",
    "first_carry",
    "verdict",
)


def _rows(result, columns: tuple[str, ...]) -> list[dict]:
    return [dict(zip(columns, row, strict=True)) for row in result.result_set]


def decide(
    ndc: str,
    *,
    fact_id: str | None = None,
    as_of: str = "2026-10-16",
    strict: bool = False,
    graph: str = "hub",
    grace_days: int = 30,
) -> dict:
    as_of_d = to_d(as_of)
    found = identify(ndc, as_of_d or 0, graph)
    base = {"ndc": ndc, "disclaimer": DISCLAIMER, "as_of": as_of}
    if found is None:
        return {**base, "verdict": "UNKNOWN", "reason": "NDC_NOT_FOUND"}
    facts = _rows(
        ro_query(
            graph,
            queries.V3,
            {"molecule_key": found["molecule_key"], "include_unverified": False},
        ),
        V3_COLUMNS,
    )
    if fact_id:
        facts = [fact for fact in facts if fact["fact_id"] == fact_id]
    if not facts:
        molecule = found["molecule_key"]
        return {
            **base,
            "results": [],
            "message": f"No verified safety fact for {molecule} in Landfall yet.",
        }
    results = []
    for fact in facts:
        results.append(_one(found, fact, as_of_d or 0, strict, graph, grace_days, as_of))
    return {**base, "product_ndc": found["product_ndc"], "results": results}


def _one(found, fact, as_of_d, strict, graph, grace_days, as_of) -> dict:
    scope_rows = _rows(
        ro_query(
            graph,
            queries.V2,
            {"fact_id": fact["fact_id"], "product_ndc": found["product_ndc"]},
        ),
        V2_COLUMNS,
    )
    linked = [row for row in scope_rows if not row["no_path"]]
    outcome = {
        "fact_id": fact["fact_id"],
        "disclaimer": DISCLAIMER,
    }
    if scope_rows and not linked:
        if _scope_complete(found, fact, graph):
            outcome["verdict"] = "NOT_IN_SCOPE"
            outcome["proof"] = {
                "searched": "SOURCED_FROM|UNDER|REFERENCES*1..5",
                "targets": [row["rld"] for row in scope_rows],
                "from": found["product_ndc"],
            }
        else:
            outcome["verdict"] = "UNKNOWN"
            outcome["reason"] = "SCOPE_UNRESOLVED"
        return outcome
    if linked:
        outcome["scope"] = {"path": linked[0]["path"], "rels": linked[0]["rels"]}
    if not found["listing_active"]:
        outcome["verdict"] = "NOT_ASSESSED_INACTIVE_LISTING"
        return outcome
    if not found["record_sets"]:
        outcome["verdict"] = "UNKNOWN"
        outcome["reason"] = "LABEL_OF_RECORD_NOT_INGESTED"
        return outcome
    timeline = _rows(
        ro_query(
            graph,
            queries.V4,
            {
                "fact_id": fact["fact_id"],
                "set_id": found["record_sets"][0],
                "as_of_d": as_of_d,
                "min_tier": 2 if strict else 1,
                "grace_days": grace_days,
            },
        ),
        V4_COLUMNS,
    )
    if not timeline:
        outcome["verdict"] = "UNKNOWN"
        outcome["reason"] = "NOT_CHECKED"
        return outcome
    row = timeline[0]
    outcome["verdict"] = row["verdict"]
    outcome["revisions_after_fact"] = row["revisions_after_fact"]
    outcome["revised_on"] = row["revised_on"]
    outcome["current"] = row["current"]
    if row["verdict"] == "UNKNOWN":
        outcome["reason"] = "NOT_CHECKED"
    return outcome


def _scope_complete(found: dict, fact: dict, graph: str) -> bool:
    if fact.get("molecule_key") and found["molecule_key"] != fact["molecule_key"]:
        return True
    result = ro_query(graph, SCOPE_QUERY, {"ndc": found["product_ndc"]})
    if not result.result_set:
        return False
    category, molecule_key, kinds = result.result_set[0]
    if fact.get("molecule_key") and molecule_key != fact["molecule_key"]:
        return True
    values = list(kinds or [])
    if any(kind is None for kind in values):
        return False
    if values:
        return True
    return category in BULK
