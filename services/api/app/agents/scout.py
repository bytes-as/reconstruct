"""Scout writes public label metadata into the hub through the I-queries."""

import json
import logging
import time
from datetime import date
from pathlib import Path

from falkordb import FalkorDB
from lxml.etree import XMLSyntaxError

from app.graph import queries
from app.graph.db import connect_once, query
from app.graph.schema import apply_block
from app.sources.dailymed import DailyMed
from app.sources.dates import to_d, to_iso
from app.sources.http import SourceClient, SourceError
from app.sources.openfda import OpenFda
from app.sources.slug import party_id
from app.sources.spl import parse_spl

logger = logging.getLogger("landfall.scout")


def molecules_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data" / "molecules.json"
        if candidate.is_file():
            return candidate
    return Path("/repo/data/molecules.json")


def load_molecules() -> list[dict]:
    payload = json.loads(molecules_path().read_text())
    return [item for item in payload["molecules"] if item.get("ingest")]


class HubWriter:
    def __init__(self, graph: str, db: FalkorDB | None = None) -> None:
        self.graph = graph
        self.db = db or connect_once()
        self.now = int(time.time() * 1000)
        apply_block(self.graph, queries.SCHEMA_HUB, db=self.db)

    def run(self, cypher: str, params: dict) -> None:
        query(self.graph, cypher, params, db=self.db)


def application_kind(application_id: str) -> str | None:
    for prefix in ("ANDA", "NDA", "BLA"):
        if application_id.startswith(prefix):
            return prefix
    return None


def product_for_package(package_ndc: str, product_ndcs: set[str]) -> str | None:
    for product in sorted(product_ndcs, key=len, reverse=True):
        if package_ndc == product or package_ndc.startswith(product + "-"):
            return product
    if "-" in package_ndc:
        return package_ndc.rsplit("-", 1)[0]
    return None


def _strength(listing: dict) -> str | None:
    parts = [
        item.get("strength")
        for item in (listing.get("active_ingredients") or [])
        if item.get("strength")
    ]
    return ";".join(parts) or None


async def ingest_molecule(
    molecule: dict,
    *,
    graph: str,
    http: SourceClient,
    today_d: int | None = None,
    db: FalkorDB | None = None,
) -> dict:
    """F2.1-F2.3 and F2.6: sets, listings, applications, then I12 and I13."""
    writer = HubWriter(graph, db)
    dailymed = DailyMed(http)
    openfda = OpenFda(http)
    as_of = today_d if today_d is not None else to_d(date.today().isoformat())
    writer.run(
        queries.I1,
        {"key": molecule["key"], "name": molecule["name"], "unii": molecule.get("unii")},
    )
    sets = await dailymed.spls_by_drug_name(molecule["drug_name"])
    product_ndcs: set[str] = set()
    application_ids: set[str] = set()
    for item in sets:
        try:
            await _ingest_set(writer, dailymed, molecule, item, product_ndcs, application_ids)
        except (SourceError, ValueError, OSError, XMLSyntaxError) as exc:
            logger.warning("skip set %s: %s", item.get("setid"), exc)
    listings = await openfda.ndc_by_generic(molecule["generic_name"])
    seen = {row.get("product_ndc") for row in listings}
    for ndc in sorted(product_ndcs - seen):
        listings.extend(await openfda.ndc_by_product(ndc))
    for listing in listings:
        if listing.get("application_number"):
            application_ids.add(listing["application_number"])
        _write_listing(writer, molecule, listing, product_ndcs)
    applications = await openfda.drugsfda_by_generic(molecule["generic_name"])
    have = {row.get("application_number") for row in applications}
    for application_id in sorted(application_ids - have):
        applications.extend(await openfda.drugsfda_by_application(application_id))
    for application in applications:
        _write_application(writer, molecule, application, as_of)
    writer.run(queries.I12, {"molecule_key": molecule["key"]})
    writer.run(queries.I13, {"molecule_key": molecule["key"], "today_d": as_of})
    return {"molecule": molecule["key"], "sets": len(sets), "listings": len(listings)}


async def _ingest_set(writer, dailymed, molecule, item, product_ndcs, application_ids) -> None:
    set_id = item["setid"]
    version = int(item["spl_version"])
    xml = await dailymed.spl_xml(set_id, version=version)
    parsed = parse_spl(xml)
    packages = await dailymed.ndcs(set_id)
    published = to_iso(item.get("published_date"))
    labeler_name = parsed.get("labeler_name") or ""
    writer.run(
        queries.I4,
        {
            "set_id": set_id,
            "title": item.get("title"),
            "molecule_key": molecule["key"],
            "current_version": version,
            "current_doc_id": parsed.get("doc_id"),
            "current_published": published,
            "current_published_d": to_d(published),
            "now": writer.now,
            "labeler_id": party_id("labeler", labeler_name) if labeler_name else "labeler:unknown",
            "labeler_name": labeler_name,
        },
    )
    writer.run(
        queries.I5,
        {
            "set_id": set_id,
            "version_id": f"{set_id}#v{version}",
            "version": version,
            "doc_id": parsed.get("doc_id"),
            "effective": parsed.get("effective"),
            "published": published,
            "published_d": to_d(published),
            "archive_id": None,
            "labeler_name": labeler_name,
            "now": writer.now,
        },
    )
    for product in parsed["products"]:
        product_ndcs.add(product["ndc"])
        if product.get("approval_id"):
            application_ids.add(product["approval_id"])
        writer.run(
            queries.I6,
            {
                "ndc": product["ndc"],
                "labeler_name": labeler_name,
                "molecule_key": molecule["key"],
                "dosage_form": product.get("dosage_form"),
                "strength": None,
                "marketing_category": None,
                "listing_spl_id": None,
                "listing_expiration_d": None,
                "in_ndc_directory": False,
                "now": writer.now,
                "application_id": product.get("approval_id"),
            },
        )
        writer.run(queries.I7, {"set_id": set_id, "ndc": product["ndc"]})
        for source_ndc in product["source_ndcs"]:
            writer.run(
                queries.I9,
                {
                    "ndc": product["ndc"],
                    "source_ndc": source_ndc,
                    "source": "spl_equivalent",
                    "now": writer.now,
                },
            )
    known = set(product_ndcs)
    for package_ndc in packages.get("ndcs") or []:
        if not package_ndc:
            continue
        product_ndc = product_for_package(package_ndc, known)
        if product_ndc is None:
            continue
        if product_ndc not in known:
            writer.run(
                queries.I6,
                {
                    "ndc": product_ndc,
                    "labeler_name": labeler_name,
                    "molecule_key": molecule["key"],
                    "dosage_form": None,
                    "strength": None,
                    "marketing_category": None,
                    "listing_spl_id": None,
                    "listing_expiration_d": None,
                    "in_ndc_directory": False,
                    "now": writer.now,
                    "application_id": None,
                },
            )
            known.add(product_ndc)
        writer.run(
            queries.I8,
            {"product_ndc": product_ndc, "package_ndc": package_ndc, "description": None},
        )


def _write_listing(
    writer: HubWriter, molecule: dict, listing: dict, product_ndcs: set[str]
) -> None:
    ndc = listing.get("product_ndc")
    if not ndc:
        return
    product_ndcs.add(ndc)
    writer.run(
        queries.I6,
        {
            "ndc": ndc,
            "labeler_name": listing.get("labeler_name"),
            "molecule_key": molecule["key"],
            "dosage_form": listing.get("dosage_form"),
            "strength": _strength(listing),
            "marketing_category": listing.get("marketing_category"),
            "listing_spl_id": listing.get("spl_id"),
            "listing_expiration_d": to_d(listing.get("listing_expiration_date")),
            "in_ndc_directory": True,
            "now": writer.now,
            "application_id": listing.get("application_number"),
        },
    )
    for package in listing.get("packaging") or []:
        package_ndc = package.get("package_ndc")
        if package_ndc:
            writer.run(
                queries.I8,
                {
                    "product_ndc": ndc,
                    "package_ndc": package_ndc,
                    "description": package.get("description"),
                },
            )


def _write_application(writer: HubWriter, molecule: dict, application: dict, today_d: int) -> None:
    application_id = application.get("application_number")
    if not application_id:
        return
    products = application.get("products") or []
    forms = []
    for product in products:
        form = product.get("dosage_form")
        if form and form not in forms:
            forms.append(form)
    statuses = [
        product.get("marketing_status") for product in products if product.get("marketing_status")
    ]
    marketing = (
        "Prescription" if "Prescription" in statuses else (statuses[0] if statuses else None)
    )
    sponsor = application.get("sponsor_name") or ""
    writer.run(
        queries.I2,
        {
            "id": application_id,
            "kind": application_kind(application_id),
            "sponsor": sponsor,
            "dosage_forms": forms,
            "marketing_status": marketing,
            "reference_drug": any(product.get("reference_drug") == "Yes" for product in products),
            "reference_standard": any(
                product.get("reference_standard") == "Yes" for product in products
            ),
            "now": writer.now,
            "molecule_key": molecule["key"],
        },
    )
    if sponsor:
        writer.run(
            queries.I3,
            {
                "application_id": application_id,
                "party_id": party_id("sponsor", sponsor),
                "party_name": sponsor,
                "from_d": None,
                "today_d": today_d,
                "source": "drugsfda",
            },
        )


def main() -> None:
    import asyncio

    from app.graph.db import ro_query
    from app.sources.http import build_client

    async def run() -> None:
        http = build_client()
        lines = []
        for molecule in load_molecules():
            summary = await ingest_molecule(molecule, graph="hub", http=http)
            lines.append(
                f"{summary['molecule']} sets_fetched={summary['sets']} "
                f"listings={summary['listings']}"
            )
        await http.client.aclose()
        sets = int(ro_query("hub", "MATCH (s:LabelSet) RETURN count(s)").result_set[0][0])
        record = int(
            ro_query(
                "hub", "MATCH (s:LabelSet {label_of_record: true}) RETURN count(s)"
            ).result_set[0][0]
        )
        unkind = int(
            ro_query(
                "hub",
                "MATCH (p:Product)-[:UNDER]->(a:Application) WHERE a.kind IS NULL RETURN count(p)",
            ).result_set[0][0]
        )
        lines.append(f"label_sets {sets}")
        lines.append(f"labels_of_record {record}")
        lines.append(f"products_under_application_without_kind {unkind}")
        text = "\n".join(lines) + "\n"
        evidence = Path("/repo/docs/evidence")
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "ingest.txt").write_text(text)
        print(text, end="")

    asyncio.run(run())


if __name__ == "__main__":
    main()
