"""G025: Scout writes I1-I9, I12 and I13 from mocked DailyMed and openFDA."""

from pathlib import Path

import httpx
import pytest
import respx

from app.config import get_settings
from app.graph.db import delete_graph, ro_query
from app.sources.cache import DiskCache
from app.sources.http import SourceClient

FIXTURES = Path(__file__).parent / "fixtures"
GRAPH = "hub_scout"
BASE = "https://dailymed.nlm.nih.gov/dailymed"


def _client(tmp_path: Path) -> SourceClient:
    get_settings.cache_clear()

    async def sleep(_seconds: float) -> None:
        return None

    return SourceClient(
        get_settings(),
        httpx.AsyncClient(),
        DiskCache(tmp_path),
        sleep=sleep,
        dailymed_rps=1_000_000_000,
        openfda_rps=1_000_000_000,
    )


def _count(cypher: str) -> int:
    result = ro_query(GRAPH, cypher)
    return int(result.result_set[0][0])


@pytest.mark.asyncio
async def test_scout_writes_the_set_listing_and_application(tmp_path: Path) -> None:
    from app.agents.scout import ingest_molecule

    client = _client(tmp_path)
    listing = {
        "meta": {"results": {"total": 1}},
        "results": [
            {
                "product_ndc": "68071-3355",
                "labeler_name": "NuCare Pharmaceuticals, Inc.",
                "application_number": "ANDA202717",
                "marketing_category": "ANDA",
                "dosage_form": "TABLET, FILM COATED",
                "active_ingredients": [{"name": "MONTELUKAST SODIUM", "strength": "10 mg/1"}],
                "listing_expiration_date": "20271231",
                "spl_id": "doc-coded",
                "packaging": [
                    {"package_ndc": "68071-3355-9", "description": "90 TABLET IN 1 BOTTLE"}
                ],
            }
        ],
    }
    application = {
        "meta": {"results": {"total": 1}},
        "results": [
            {
                "application_number": "ANDA202717",
                "sponsor_name": "NuCare Pharmaceuticals, Inc.",
                "products": [
                    {
                        "dosage_form": "TABLET, FILM COATED",
                        "marketing_status": "Prescription",
                        "reference_drug": "No",
                        "reference_standard": "No",
                    }
                ],
                "submissions": [],
            }
        ],
    }
    try:
        with respx.mock:
            respx.get(url__startswith=f"{BASE}/services/v2/spls.json").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "metadata": {"total_pages": 1},
                        "data": [
                            {
                                "setid": "set-coded",
                                "spl_version": 5,
                                "title": "Synthetic tablet",
                                "published_date": "Jul 11, 2024",
                            }
                        ],
                    },
                )
            )
            respx.get(f"{BASE}/services/v2/spls/set-coded.xml").mock(
                return_value=httpx.Response(200, content=(FIXTURES / "spl_coded.xml").read_bytes())
            )
            respx.get(f"{BASE}/services/v2/spls/set-coded/ndcs.json").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": {"setid": "set-coded", "ndcs": [{"ndc": "68071-3355-9"}]}},
                )
            )
            respx.get(url__startswith="https://api.fda.gov/drug/ndc.json").mock(
                return_value=httpx.Response(200, json=listing)
            )
            respx.get(url__startswith="https://api.fda.gov/drug/drugsfda.json").mock(
                return_value=httpx.Response(200, json=application)
            )
            summary = await ingest_molecule(
                {
                    "key": "montelukast",
                    "name": "Montelukast",
                    "drug_name": "montelukast",
                    "generic_name": "montelukast",
                    "unii": "MHM278SD3E",
                },
                graph=GRAPH,
                http=client,
                today_d=20742,
            )
        assert summary["sets"] == 1
        assert _count("MATCH (s:LabelSet) RETURN count(s)") == 1
        assert _count("MATCH (s:LabelSet {label_of_record: true}) RETURN count(s)") == 1
        linked = _count(
            "MATCH (p:Product)-[:UNDER]->(a:Application) "
            "WHERE a.kind IS NOT NULL RETURN count(p)"
        )
        assert linked >= 1
        assert _count("MATCH ()-[e:SOURCED_FROM]->() RETURN count(e)") == 1
    finally:
        await client.client.aclose()
        delete_graph(GRAPH)
        get_settings.cache_clear()
