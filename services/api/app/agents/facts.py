"""Load data/facts.seed.json through I11, then derive REFERENCES with I12."""

import json
import time
from pathlib import Path

from falkordb import FalkorDB

from app.graph import queries
from app.graph.db import connect_once, query, ro_query


def _kind(application_id: str) -> str | None:
    for prefix in ("ANDA", "NDA", "BLA"):
        if application_id.startswith(prefix):
            return prefix
    return None


def _ensure(graph: str, fact: dict, now: int, db: FalkorDB) -> None:
    molecule = ro_query(
        graph,
        "MATCH (m:Molecule {key: $key}) RETURN m.key",
        {"key": fact["molecule_key"]},
        db=db,
    )
    if not molecule.result_set:
        query(
            graph,
            queries.I1,
            {"key": fact["molecule_key"], "name": fact["molecule_key"], "unii": None},
            db=db,
        )
    for item in fact["issued_on"]:
        application_id = item["application_id"]
        existing = ro_query(
            graph,
            "MATCH (a:Application {id: $id}) RETURN a.id",
            {"id": application_id},
            db=db,
        )
        if existing.result_set:
            continue
        query(
            graph,
            queries.I2,
            {
                "id": application_id,
                "kind": _kind(application_id),
                "sponsor": "",
                "dosage_forms": [],
                "marketing_status": None,
                "reference_drug": False,
                "reference_standard": False,
                "now": now,
                "molecule_key": fact["molecule_key"],
            },
            db=db,
        )


def facts_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "facts.seed.json"
        if candidate.is_file():
            return candidate
    return Path("/repo/data/facts.seed.json")


def load_facts(graph: str, db: FalkorDB | None = None) -> list[str]:
    client = db or connect_once()
    payload = json.loads(facts_path().read_text())
    now = int(time.time() * 1000)
    loaded = []
    molecules: set[str] = set()
    for fact in payload["facts"]:
        _ensure(graph, fact, now, client)
        issued_on = [
            {
                "application_id": item["application_id"],
                "supplement": item["supplement"],
                "approved": item["approved"],
            }
            for item in fact["issued_on"]
        ]
        query(
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
                "issued_on": issued_on,
            },
            db=client,
        )
        loaded.append(fact["id"])
        molecules.add(fact["molecule_key"])
    for molecule_key in sorted(molecules):
        query(graph, queries.I12, {"molecule_key": molecule_key}, db=client)
    return loaded
