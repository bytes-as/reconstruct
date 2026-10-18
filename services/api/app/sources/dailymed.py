"""DailyMed set lists, SPL XML, history, and label archives."""

import io
import json
import re
import zipfile
from datetime import datetime
from urllib.parse import urlencode

from app.config import Settings
from app.sources.http import SourceClient, SourceError

_DATE_VERSION = re.compile(r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+(\d+)")
_ARCHIVE = re.compile(r"getArchivalFile\.cfm\?archive_id=(\d+)")


def parse_spl_list(payload: dict) -> list[dict]:
    return [
        {
            "setid": item.get("setid"),
            "spl_version": item.get("spl_version"),
            "title": item.get("title"),
            "published_date": item.get("published_date"),
        }
        for item in (payload.get("data") or [])
    ]


def parse_history(payload: dict) -> dict:
    data = payload.get("data") or payload
    spl = data.get("spl") or {}
    return {
        "setid": spl.get("setid"),
        "title": spl.get("title"),
        "history": data.get("history") or [],
    }


def parse_ndcs(payload: dict) -> dict:
    data = payload.get("data") or payload
    ndcs = []
    for item in data.get("ndcs") or []:
        ndcs.append(item.get("ndc") if isinstance(item, dict) else item)
    return {
        "setid": data.get("setid"),
        "spl_version": data.get("spl_version"),
        "published_date": data.get("published_date"),
        "ndcs": ndcs,
    }


def archive_ids_from_html(html: str) -> list[tuple[int, str, int]]:
    """Return (version, ISO date, archive id) for each archive link."""
    found: list[tuple[int, str, int]] = []
    for match in _ARCHIVE.finditer(html):
        before = html[max(0, match.start() - 120) : match.start()]
        dated = None
        for candidate in _DATE_VERSION.finditer(before):
            dated = candidate
        if dated is None:
            continue
        day = datetime.strptime(dated.group(1), "%b %d, %Y").date().isoformat()
        found.append((int(dated.group(2)), day, int(match.group(1))))
    return found


def first_xml(blob: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".xml"):
                return archive.read(name)
    raise SourceError("archive zip has no xml")


class DailyMed:
    def __init__(self, http: SourceClient, settings: Settings | None = None) -> None:
        self.http = http
        self.settings = settings or http.settings

    async def spls_by_drug_name(self, name: str) -> list[dict]:
        return await self._spl_pages({"drug_name": name})

    async def spls_by_ndc(self, ndc: str) -> list[dict]:
        return await self._spl_pages({"ndc": ndc})

    async def spl_xml(self, setid: str, version: int | str | None = None) -> bytes:
        url = f"{self._base()}/services/v2/spls/{setid}.xml"
        key = None if version is None else f"{setid}@{version}"
        return await self.http.get(url, immutable_key=key)

    async def history(self, setid: str) -> dict:
        url = f"{self._base()}/services/v2/spls/{setid}/history.json"
        return parse_history(json.loads(await self.http.get(url)))

    async def ndcs(self, setid: str) -> dict:
        url = f"{self._base()}/services/v2/spls/{setid}/ndcs.json"
        return parse_ndcs(json.loads(await self.http.get(url)))

    async def archive_ids(self, setid: str) -> list[tuple[int, str, int]]:
        url = f"{self._base()}/drugInfo.cfm?setid={setid}"
        html = (await self.http.get(url)).decode("utf-8", errors="replace")
        return archive_ids_from_html(html)

    async def archived_xml(
        self,
        archive_id: int,
        *,
        setid: str | None = None,
        version: int | str | None = None,
    ) -> bytes:
        url = f"{self._base()}/getArchivalFile.cfm?archive_id={archive_id}"
        key = f"{setid}@{version}" if setid and version is not None else f"archive@{archive_id}"
        return first_xml(await self.http.get(url, immutable_key=key))

    async def _spl_pages(self, query: dict[str, str]) -> list[dict]:
        page = 1
        rows: list[dict] = []
        while True:
            params = {**query, "pagesize": "100", "page": str(page)}
            url = f"{self._base()}/services/v2/spls.json?{urlencode(params)}"
            payload = json.loads(await self.http.get(url))
            rows.extend(parse_spl_list(payload))
            total_pages = int((payload.get("metadata") or {}).get("total_pages") or 1)
            if page >= total_pages:
                return rows
            page += 1

    def _base(self) -> str:
        return self.settings.dailymed_base_url.rstrip("/")
