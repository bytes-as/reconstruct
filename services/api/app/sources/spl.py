"""Parse an SPL document into identifiers, section hashes, and product NDCs."""

import hashlib
import re
import unicodedata

from lxml import etree

NS = "urn:hl7-org:v3"
NDC_SYSTEM = "2.16.840.1.113883.6.69"


def normalise_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", text).strip()


def text_norm_hash(value: str) -> str:
    return hashlib.sha256(normalise_text(value).encode()).hexdigest()


def _q(name: str) -> str:
    return f"{{{NS}}}{name}"


def parse_spl(xml: bytes | str) -> dict:
    root = etree.fromstring(xml)
    return {
        "doc_id": _attr(root, "id", "root"),
        "set_id": _attr(root, "setId", "root"),
        "version": _int(_attr(root, "versionNumber", "value")),
        "effective": _attr(root, "effectiveTime", "value"),
        "labeler_name": _labeler_name(root),
        "duns": _duns(root),
        "sections": _sections(root),
        "products": _products(root),
    }


def _attr(root: etree._Element, tag: str, name: str) -> str | None:
    found = root.find(_q(tag))
    if found is None:
        return None
    return found.get(name)


def _int(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    return int(value)


def _labeler_name(root: etree._Element) -> str | None:
    org = root.find(f".//{_q('representedOrganization')}")
    if org is None:
        return None
    name = org.find(_q("name"))
    if name is None or name.text is None:
        return None
    return name.text.strip()


def _duns(root: etree._Element) -> str | None:
    org = root.find(f".//{_q('representedOrganization')}")
    if org is None:
        return None
    identifier = org.find(_q("id"))
    if identifier is None:
        return None
    return identifier.get("extension")


def _sections(root: etree._Element) -> list[dict]:
    sections = []
    for section in root.findall(f".//{_q('section')}"):
        code = section.find(_q("code"))
        if code is None or not code.get("code"):
            continue
        text_el = section.find(_q("text"))
        raw = "" if text_el is None else "".join(text_el.itertext())
        sections.append(
            {
                "code": code.get("code"),
                "text_norm_hash": text_norm_hash(raw),
                "text_norm": normalise_text(raw),
            }
        )
    return sections


def _products(root: etree._Element) -> list[dict]:
    products = []
    for product in root.findall(f".//{_q('manufacturedProduct')}"):
        code = product.find(_q("code"))
        if code is None or code.get("codeSystem") != NDC_SYSTEM or not code.get("code"):
            continue
        form = product.find(_q("formCode"))
        products.append(
            {
                "ndc": code.get("code"),
                "dosage_form": None if form is None else form.get("displayName"),
                "source_ndcs": _sources(product),
                "approval_id": _approval(product),
            }
        )
    return products


def _sources(product: etree._Element) -> list[str]:
    found = []
    for equivalent in product.findall(_q("asEquivalentEntity")):
        code = equivalent.find(f"{_q('definingMaterialKind')}/{_q('code')}")
        if code is not None and code.get("code"):
            found.append(code.get("code"))
    return found


def _approval(product: etree._Element) -> str | None:
    for node in (product, product.getparent()):
        if node is None:
            continue
        found = node.find(f"{_q('subjectOf')}/{_q('approval')}/{_q('id')}")
        if found is not None and found.get("extension"):
            return found.get("extension")
    return None
