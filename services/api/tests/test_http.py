"""G020: retries, timeout, and disk cache for source HTTP."""

import os
import time
from pathlib import Path

import httpx
import pytest
import respx

from app.config import get_settings
from app.sources.cache import LIST_TTL_S, DiskCache
from app.sources.http import SourceClient, SourceError

URL = "https://api.fda.gov/drug/ndc.json?search=product_ndc:68071-3355"


def _client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides
) -> tuple[SourceClient, list[float]]:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    get_settings.cache_clear()
    settings = get_settings()
    raw = httpx.AsyncClient()
    client = SourceClient(
        settings,
        raw,
        DiskCache(tmp_path),
        sleep=sleep,
        dailymed_rps=1_000_000_000,
        openfda_rps=1_000_000_000,
        **overrides,
    )
    return client, slept


@pytest.mark.asyncio
async def test_retries_429_using_retry_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "7"}),
                httpx.Response(200, content=b"ok"),
            ]
        )
        assert await client.get(URL) == b"ok"
        assert route.call_count == 2
    assert slept == [7]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_429_without_retry_after_waits_20_seconds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, content=b"ok")])
        await client.get(URL)
    assert slept == [20]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_retries_5xx_with_backoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(502),
                httpx.Response(200, content=b"back"),
            ]
        )
        assert await client.get(URL) == b"back"
        assert route.call_count == 3
    assert slept == [1, 2]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_timeout_then_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        respx.get(URL).mock(
            side_effect=[httpx.TimeoutException("timed out"), httpx.Response(200, content=b"ok")]
        )
        assert await client.get(URL) == b"ok"
    assert slept == [1]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_gives_up_after_three_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(500))
        with pytest.raises(SourceError):
            await client.get(URL)
        assert route.call_count == 4
    assert slept == [1, 2, 4]
    await client.client.aclose()


@pytest.mark.asyncio
async def test_list_cache_hit_skips_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(200, content=b"listed"))
        assert await client.get(URL) == b"listed"
        assert await client.get(URL) == b"listed"
        assert route.call_count == 1
    await client.client.aclose()


@pytest.mark.asyncio
async def test_expired_list_cache_is_fetched_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(URL).mock(return_value=httpx.Response(200, content=b"fresh"))
        await client.get(URL)
        cached = next((tmp_path / "lists").iterdir())
        old = time.time() - LIST_TTL_S - 5
        os.utime(cached, (old, old))
        await client.get(URL)
        assert route.call_count == 2
    await client.client.aclose()


@pytest.mark.asyncio
async def test_immutable_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _slept = _client(tmp_path, monkeypatch)
    key = "set-1@4"
    with respx.mock:
        route = respx.get("https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/set-1.xml").mock(
            return_value=httpx.Response(200, content=b"<xml/>")
        )
        url = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/set-1.xml"
        assert await client.get(url, immutable_key=key) == b"<xml/>"
        assert await client.get(url, immutable_key=key) == b"<xml/>"
        assert route.call_count == 1
    await client.client.aclose()


@pytest.mark.asyncio
async def test_user_agent_and_openfda_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFDA_API_KEY", "test-key")
    client, _slept = _client(tmp_path, monkeypatch)
    with respx.mock:
        route = respx.get(url__startswith="https://api.fda.gov/drug/ndc.json").mock(
            return_value=httpx.Response(200, content=b"{}")
        )
        await client.get(URL)
        request = route.calls[0].request
        assert request.headers["user-agent"] == "Landfall/1.0 (+arunsin997@gmail.com)"
        assert "api_key=test-key" in str(request.url)
    await client.client.aclose()
    get_settings.cache_clear()
