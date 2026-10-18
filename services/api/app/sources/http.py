"""Shared async client for DailyMed and openFDA."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.config import Settings, get_settings
from app.sources.cache import DiskCache

OPENFDA_RPS = 4
TIMEOUT_S = 15.0
BACKOFF_S = (1, 2, 4)
DEFAULT_RETRY_AFTER_S = 20
MAX_RETRIES = 3

Sleep = Callable[[float], Awaitable[None]]


class SourceError(Exception):
    def __init__(self, message: str, retry_after_s: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class HostLimiter:
    """Spaces requests to one host. The first request is not delayed."""

    def __init__(self, rps: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.interval = 1 / rps if rps else 0
        self.clock = clock
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self, sleep: Sleep) -> None:
        async with self._lock:
            now = self.clock()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if delay:
            await sleep(delay)


class SourceClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        cache: DiskCache,
        sleep: Sleep = asyncio.sleep,
        dailymed_rps: int | None = None,
        openfda_rps: int = OPENFDA_RPS,
    ) -> None:
        self.settings = settings
        self.client = client
        self.cache = cache
        self.sleep = sleep
        dailymed_host = urlparse(settings.dailymed_base_url).netloc
        openfda_host = urlparse(settings.openfda_base_url).netloc
        daily_rate = settings.dailymed_rps if dailymed_rps is None else dailymed_rps
        self.limiters = {
            dailymed_host: HostLimiter(daily_rate),
            openfda_host: HostLimiter(openfda_rps),
        }

    def headers(self) -> dict[str, str]:
        return {"User-Agent": f"Landfall/1.0 (+{self.settings.http_contact})"}

    async def get(self, url: str, *, immutable_key: str | None = None) -> bytes:
        cached = self._read(url, immutable_key)
        if cached is not None:
            return cached
        body = await self._fetch(self._with_api_key(url))
        self._write(url, immutable_key, body)
        return body

    def _read(self, url: str, immutable_key: str | None) -> bytes | None:
        if immutable_key:
            return self.cache.get_immutable(immutable_key)
        return self.cache.get_list(url)

    def _write(self, url: str, immutable_key: str | None, body: bytes) -> None:
        if immutable_key:
            self.cache.put_immutable(immutable_key, body)
            return
        self.cache.put_list(url, body)

    def _with_api_key(self, url: str) -> str:
        host = urlparse(url).netloc
        openfda_host = urlparse(self.settings.openfda_base_url).netloc
        if host != openfda_host or not self.settings.openfda_api_key:
            return url
        parts = urlparse(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if "api_key" in query:
            return url
        query["api_key"] = self.settings.openfda_api_key
        return urlunparse(parts._replace(query=urlencode(query)))

    async def _fetch(self, url: str) -> bytes:
        last: Exception | None = None
        retry_after: int | None = None
        for attempt in range(MAX_RETRIES + 1):
            await self._limit(url)
            try:
                response = await self.client.get(url, headers=self.headers(), timeout=TIMEOUT_S)
            except httpx.TimeoutException as exc:
                last = exc
                if attempt == MAX_RETRIES:
                    break
                await self.sleep(BACKOFF_S[attempt])
                continue
            if response.status_code == 429:
                retry_after = _retry_after(response)
                last = SourceError("source returned 429", retry_after_s=retry_after)
                if attempt == MAX_RETRIES:
                    break
                await self.sleep(retry_after)
                continue
            if response.status_code >= 500:
                last = SourceError(f"source returned {response.status_code}")
                if attempt == MAX_RETRIES:
                    break
                await self.sleep(BACKOFF_S[attempt])
                continue
            if response.status_code >= 400:
                raise SourceError(f"source returned {response.status_code}")
            return response.content
        raise SourceError(str(last) if last else "source request failed", retry_after_s=retry_after)

    async def _limit(self, url: str) -> None:
        limiter = self.limiters.get(urlparse(url).netloc)
        if limiter is not None:
            await limiter.wait(self.sleep)


def _retry_after(response: httpx.Response) -> int:
    raw = response.headers.get("Retry-After", "")
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_RETRY_AFTER_S


def build_client(settings: Settings | None = None) -> SourceClient:
    current = settings or get_settings()
    return SourceClient(
        current,
        httpx.AsyncClient(timeout=TIMEOUT_S),
        DiskCache(Path(current.cache_dir)),
    )
