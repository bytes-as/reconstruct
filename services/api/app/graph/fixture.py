"""Load data/fixtures/hub_montelukast.json through the I-queries."""

import json
import os
import time
from pathlib import Path

from falkordb import FalkorDB

from app.graph import queries
from app.graph.db import connect_once, delete_graph, query
from app.graph.schema import apply_block


def fixture_path() -> Path:
    override = os.environ.get("LANDFALL_FIXTURE")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "fixtures" / "hub_montelukast.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("hub_montelukast.json")


def _run(graph: str, cypher: str, params: dict, db: FalkorDB) -> None:
    query(graph, cypher, params, db=db)


def load_fixture(graph: str, db: FalkorDB | None = None, path: Path | None = None) -> dict:
    client = db or connect_once()
    payload = json.loads((path or fixture_path()).read_text())
    now = int(time.time() * 1000)
    today_d = payload["as_of_d"]
    delete_graph(graph, db=client)
    apply_block(graph, queries.SCHEMA_HUB, db=client)

    for molecule in payload["molecules"]:
        _run(
            graph,
            queries.I1,
            {"key": molecule["key"], "name": molecule["name"], "unii": molecule["unii"]},
            client,
        )
    for application in payload["applications"]:
        _run(
            graph,
            queries.I2,
            {
                "id": application["id"],
                "kind": application["kind"],
                "sponsor": application["sponsor"],
                "dosage_forms": application["dosage_forms"],
                "marketing_status": application["marketing_status"],
                "reference_drug": application["reference_drug"],
                "reference_standard": application["reference_standard"],
                "now": now,
                "molecule_key": application["molecule_key"],
            },
            client,
        )
    for holder in payload["holders"]:
        _run(
            graph,
            queries.I3,
            {
                "application_id": holder["application_id"],
                "party_id": holder["party_id"],
                "party_name": holder["party_name"],
                "from_d": holder["from_d"],
                "today_d": today_d,
                "source": holder["source"],
            },
            client,
        )
    for label_set in payload["label_sets"]:
        _run(
            graph,
            queries.I4,
            {
                "set_id": label_set["set_id"],
                "title": label_set["title"],
                "molecule_key": label_set["molecule_key"],
                "current_version": label_set["current_version"],
                "current_doc_id": label_set["current_doc_id"],
                "current_published": label_set["current_published"],
                "current_published_d": label_set["current_published_d"],
                "now": now,
                "labeler_id": label_set["labeler_id"],
                "labeler_name": label_set["labeler_name"],
            },
            client,
        )
    for version in payload["versions"]:
        _run(
            graph,
            queries.I5,
            {
                "set_id": version["set_id"],
                "version_id": version["version_id"],
                "version": version["version"],
                "doc_id": version.get("doc_id"),
                "effective": version.get("effective"),
                "published": version["published"],
                "published_d": version["published_d"],
                "archive_id": version.get("archive_id"),
                "labeler_name": version.get("labeler_name"),
                "now": now,
            },
            client,
        )
    for product in payload["products"]:
        _run(
            graph,
            queries.I6,
            {
                "ndc": product["ndc"],
                "labeler_name": product.get("labeler_name"),
                "molecule_key": product.get("molecule_key"),
                "dosage_form": product.get("dosage_form"),
                "strength": product.get("strength"),
                "marketing_category": product.get("marketing_category"),
                "listing_spl_id": product.get("listing_spl_id"),
                "listing_expiration_d": product.get("listing_expiration_d"),
                "in_ndc_directory": product.get("in_ndc_directory", False),
                "now": now,
                "application_id": product.get("application_id"),
            },
            client,
        )
    for edge in payload["describes"]:
        _run(graph, queries.I7, {"set_id": edge["set_id"], "ndc": edge["ndc"]}, client)
    for package in payload["packages"]:
        _run(
            graph,
            queries.I8,
            {
                "product_ndc": package["product_ndc"],
                "package_ndc": package["package_ndc"],
                "description": package.get("description"),
            },
            client,
        )
    for edge in payload["sourced_from"]:
        _run(
            graph,
            queries.I9,
            {
                "ndc": edge["ndc"],
                "source_ndc": edge["source_ndc"],
                "source": edge["source"],
                "now": now,
            },
            client,
        )
    for fact in payload["facts"]:
        _run(
            graph,
            queries.I11,
            {
                "id": fact["id"],
                "molecule_key": fact["molecule_key"],
                "kind": fact["kind"],
                "title": fact["title"],
                "issued": fact["issued"],
                "issued_d": fact["issued_d"],
                "section_code": fact["section_code"],
                "phrase_key": fact["phrase_key"],
                "phrase_key_version": fact["phrase_key_version"],
                "source_url": fact["source_url"],
                "status": fact["status"],
                "issued_on": fact["issued_on"],
            },
            client,
        )
    for molecule in payload["molecules"]:
        _run(graph, queries.I12, {"molecule_key": molecule["key"]}, client)
    for check in payload["checks"]:
        _run(
            graph,
            queries.I10,
            {
                "version_id": check["version_id"],
                "fact_id": check["fact_id"],
                "result": check["result"],
                "method": check["method"],
                "tier": check["tier"],
                "phrase_key_version": check["phrase_key_version"],
                "now": now,
            },
            client,
        )
    for molecule in payload["molecules"]:
        _run(graph, queries.I13, {"molecule_key": molecule["key"], "today_d": today_d}, client)
    return payload


def main() -> None:
    graph = os.environ.get("GRAPH", "hub_test")
    load_fixture(graph)
    print(f"loaded {graph}")


if __name__ == "__main__":
    main()
