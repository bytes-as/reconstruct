"""G022: DailyMed lists, archive ids, and synthetic archive ZIPs."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from app.config import get_settings
from app.sources.cache import DiskCache
from app.sources.dailymed import DailyMed, archive_ids_from_html
from app.sources.http import SourceClient

FIXTURES = Path(__file__).parent / "fixtures" / "dailymed"
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


def test_archive_ids_from_the_recorded_snippet() -> None:
    html = (FIXTURES / "archives.html").read_text()
    assert archive_ids_from_html(html) == [
        (4, "2021-06-01", 560257),
        (5, "2024-07-11", 809304),
    ]


@pytest.mark.asyncio
async def test_spls_by_drug_name_reads_every_page(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pages = [
        {
            "metadata": {"total_pages": 2, "current_page": 1},
            "data": [
                {
                    "setid": "set-a",
                    "spl_version": 1,
                    "title": "Synthetic",
                    "published_date": "Jun 1, 2021",
                }
            ],
        },
        {
            "metadata": {"total_pages": 2, "current_page": 2},
            "data": [
                {
                    "setid": "set-b",
                    "spl_version": 2,
                    "title": "Synthetic",
                    "published_date": "Jul 11, 2024",
                }
            ],
        },
    ]
    with respx.mock:
        respx.get(url__startswith=f"{BASE}/services/v2/spls.json").mock(
            side_effect=[httpx.Response(200, json=page) for page in pages]
        )
        rows = await DailyMed(client).spls_by_drug_name("montelukast")
        assert [row["setid"] for row in rows] == ["set-a", "set-b"]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_history_and_ndcs(tmp_path: Path) -> None:
    client = _client(tmp_path)
    with respx.mock:
        respx.get(f"{BASE}/services/v2/spls/set-a/history.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "spl": {"setid": "set-a", "title": "Synthetic"},
                        "history": [{"spl_version": 4, "published_date": "Jun 1, 2021"}],
                    }
                },
            )
        )
        respx.get(f"{BASE}/services/v2/spls/set-a/ndcs.json").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "setid": "set-a",
                        "spl_version": 5,
                        "published_date": "Jul 11, 2024",
                        "ndcs": [{"ndc": "68071-3355-9"}],
                    }
                },
            )
        )
        history = await DailyMed(client).history("set-a")
        ndcs = await DailyMed(client).ndcs("set-a")
        assert history["history"][0]["spl_version"] == 4
        assert ndcs["ndcs"] == ["68071-3355-9"]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_archived_xml_returns_the_first_xml_in_the_zip(tmp_path: Path) -> None:
    client = _client(tmp_path)
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("readme.txt", "not xml")
        archive.writestr("spl.xml", b"<document>synthetic</document>")
    with respx.mock:
        respx.get(f"{BASE}/getArchivalFile.cfm?archive_id=560257").mock(
            return_value=httpx.Response(200, content=blob.getvalue())
        )
        xml = await DailyMed(client).archived_xml(560257, setid="set-a", version=4)
        assert xml == b"<document>synthetic</document>"
    await client.client.aclose()
