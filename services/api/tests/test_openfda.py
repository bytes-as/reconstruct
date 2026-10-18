"""G021: parse recorded openFDA responses. Fixtures hold metadata only."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.config import get_settings
from app.sources.cache import DiskCache
from app.sources.http import SourceClient
from app.sources.openfda import parse_application, parse_label, parse_ndc

FIXTURES = Path(__file__).parent / "fixtures" / "openfda"
TEXT_FIELDS = {
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "warnings",
    "warnings_and_cautions",
    "contraindications",
    "adverse_reactions",
    "clinical_pharmacology",
    "information_for_patients",
}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SourceClient:
    monkeypatch.setenv("OPENFDA_API_KEY", "test-key")
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


def test_recorded_files_have_no_label_text() -> None:
    def walk(value: object) -> None:
        if isinstance(value, dict):
            assert TEXT_FIELDS.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for path in FIXTURES.glob("*.json"):
        walk(json.loads(path.read_text()))


def test_parse_ndc_listing() -> None:
    parsed = parse_ndc(_load("ndc.json")["results"][0])
    assert parsed["product_ndc"] == "68071-3355"
    assert parsed["application_number"] == "ANDA202717"
    assert parsed["packaging"][0]["package_ndc"] == "68071-3355-9"
    assert parsed["spl_set_id"] == ["549f1d1a-81f5-29f5-e054-00144ff8d46c"]
    assert parsed["active_ingredients"][0]["strength"] == "10 mg/1"


def test_parse_application() -> None:
    parsed = parse_application(_load("drugsfda.json")["results"][0])
    assert parsed["application_number"] == "ANDA203037"
    assert parsed["sponsor_name"] == "PHARMOBEDIENT"
    assert parsed["products"][0]["reference_drug"] == "No"
    assert parsed["submissions"][0]["submission_class_code"] == "LABELING"


def test_parse_label_without_boxed_warning_text() -> None:
    parsed = parse_label(_load("label.json")["results"][0])
    assert parsed["set_id"] == "549f1d1a-81f5-29f5-e054-00144ff8d46c"
    assert parsed["version"] == "5"
    assert parsed["has_boxed_warning"] is False
    assert "boxed_warning" not in parsed
    assert parsed["openfda"]["product_ndc"] == ["68071-3355"]


def test_parse_label_keeps_boxed_warning_when_the_api_sends_it() -> None:
    parsed = parse_label({"set_id": "s", "id": "d", "boxed_warning": ["SYNTHETIC"]})
    assert parsed["has_boxed_warning"] is True
    assert parsed["boxed_warning"] == ["SYNTHETIC"]


@pytest.mark.asyncio
async def test_pages_labels_and_sends_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.sources.openfda import OpenFda

    client = _client(tmp_path, monkeypatch)
    first = _load("label.json")
    first["meta"]["results"]["total"] = 150
    second = {
        "meta": {"results": {"skip": 100, "limit": 100, "total": 150}},
        "results": [
            {
                "set_id": "second-set",
                "id": "doc-2",
                "version": "1",
                "effective_time": "20200101",
                "openfda": {"generic_name": ["montelukast sodium"]},
            }
        ],
    }
    with respx.mock:
        route = respx.get(url__startswith="https://api.fda.gov/drug/label.json").mock(
            side_effect=[
                httpx.Response(200, json=first),
                httpx.Response(200, json=second),
            ]
        )
        rows = await OpenFda(client).labels_by_generic("montelukast sodium")
        assert [row["set_id"] for row in rows] == [
            "549f1d1a-81f5-29f5-e054-00144ff8d46c",
            "second-set",
        ]
        assert route.call_count == 2
        assert "api_key=test-key" in str(route.calls[0].request.url)
        assert "limit=100" in str(route.calls[0].request.url)
        assert "skip=100" in str(route.calls[1].request.url)
    await client.client.aclose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_missing_application_is_an_empty_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.sources.openfda import OpenFda

    client = _client(tmp_path, monkeypatch)
    with respx.mock:
        respx.get(url__startswith="https://api.fda.gov/drug/drugsfda.json").mock(
            return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
        )
        assert await OpenFda(client).drugsfda_by_application("ANDA000000") == []
    await client.client.aclose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ndc_by_product_uses_recorded_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.sources.openfda import OpenFda

    client = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(url__startswith="https://api.fda.gov/drug/ndc.json").mock(
            return_value=httpx.Response(200, json=_load("ndc.json"))
        )
        rows = await OpenFda(client).ndc_by_product("68071-3355")
        assert rows[0]["product_ndc"] == "68071-3355"
        assert "product_ndc" in str(route.calls[0].request.url)
        assert "limit=1000" in str(route.calls[0].request.url)
    await client.client.aclose()
    get_settings.cache_clear()
