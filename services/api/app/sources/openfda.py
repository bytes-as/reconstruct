"""openFDA NDC Directory, Drugs@FDA, and label metadata."""

import json
from urllib.parse import urlencode

from app.config import Settings
from app.sources.http import SourceClient, SourceError

NDC_FIELDS = (
    "product_ndc",
    "labeler_name",
    "application_number",
    "marketing_category",
    "dosage_form",
    "active_ingredients",
    "listing_expiration_date",
    "marketing_start_date",
    "spl_id",
    "packaging",
)
LABEL_OPENFDA_FIELDS = (
    "application_number",
    "manufacturer_name",
    "product_ndc",
    "package_ndc",
    "original_packager_product_ndc",
    "spl_id",
    "spl_set_id",
    "generic_name",
    "brand_name",
    "unii",
)


def parse_ndc(row: dict) -> dict:
    parsed = {name: row.get(name) for name in NDC_FIELDS}
    parsed["spl_set_id"] = (row.get("openfda") or {}).get("spl_set_id")
    parsed["packaging"] = [
        {"package_ndc": item.get("package_ndc"), "description": item.get("description")}
        for item in (row.get("packaging") or [])
    ]
    parsed["active_ingredients"] = [
        {"name": item.get("name"), "strength": item.get("strength")}
        for item in (row.get("active_ingredients") or [])
    ]
    return parsed


def parse_application(row: dict) -> dict:
    return {
        "application_number": row.get("application_number"),
        "sponsor_name": row.get("sponsor_name"),
        "products": row.get("products") or [],
        "submissions": row.get("submissions") or [],
    }


def parse_label(row: dict) -> dict:
    openfda = row.get("openfda") or {}
    parsed = {
        "set_id": row.get("set_id"),
        "id": row.get("id"),
        "version": row.get("version"),
        "effective_time": row.get("effective_time"),
        "has_boxed_warning": "boxed_warning" in row,
        "openfda": {name: openfda.get(name) for name in LABEL_OPENFDA_FIELDS},
    }
    if "boxed_warning" in row:
        parsed["boxed_warning"] = row["boxed_warning"]
    return parsed


class OpenFda:
    def __init__(self, http: SourceClient, settings: Settings | None = None) -> None:
        self.http = http
        self.settings = settings or http.settings

    async def ndc_by_product(self, ndc: str) -> list[dict]:
        rows = await self._collect("drug/ndc.json", f'product_ndc:"{ndc}"', limit=1000)
        return [parse_ndc(row) for row in rows]

    async def ndc_by_package(self, ndc: str) -> list[dict]:
        rows = await self._collect("drug/ndc.json", f'package_ndc:"{ndc}"', limit=1000)
        return [parse_ndc(row) for row in rows]

    async def ndc_by_generic(self, name: str) -> list[dict]:
        rows = await self._collect("drug/ndc.json", f'generic_name:"{name}"', limit=1000)
        return [parse_ndc(row) for row in rows]

    async def drugsfda_by_application(self, application_id: str) -> list[dict]:
        rows = await self._collect(
            "drug/drugsfda.json", f"application_number:{application_id}", limit=100
        )
        return [parse_application(row) for row in rows]

    async def drugsfda_by_generic(self, name: str) -> list[dict]:
        rows = await self._collect(
            "drug/drugsfda.json", f'openfda.generic_name:"{name}"', limit=100
        )
        return [parse_application(row) for row in rows]

    async def labels_by_generic(self, name: str) -> list[dict]:
        rows = await self._collect("drug/label.json", f'openfda.generic_name:"{name}"', limit=100)
        return [parse_label(row) for row in rows]

    async def _collect(self, endpoint: str, search: str, limit: int) -> list[dict]:
        skip = 0
        found: list[dict] = []
        while True:
            try:
                raw = await self.http.get(self._url(endpoint, search, limit, skip))
            except SourceError as exc:
                if exc.status_code == 404 and skip == 0:
                    return []
                raise
            payload = json.loads(raw)
            page = payload.get("results") or []
            found.extend(page)
            total = int((payload.get("meta") or {}).get("results", {}).get("total", len(found)))
            skip += limit
            if not page or skip >= total:
                return found

    def _url(self, endpoint: str, search: str, limit: int, skip: int) -> str:
        base = self.settings.openfda_base_url.rstrip("/")
        query = urlencode({"search": search, "limit": str(limit), "skip": str(skip)})
        return f"{base}/{endpoint}?{query}"
