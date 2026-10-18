"""Deterministic carry check. The phrase is compared in memory and never stored."""

import json
import re
import unicodedata

from lxml import etree

from app.sources.spl import NS

SECTION = "34066-1"


def normalise(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text.upper()


def match_xml(xml: bytes | str, fact: dict) -> str:
    root = etree.fromstring(xml)
    phrase = normalise(fact["phrase_key"])
    section_code = fact.get("section_code") or SECTION
    in_coded = False
    for section in root.findall(f".//{{{NS}}}section"):
        code = section.find(f"{{{NS}}}code")
        text_el = section.find(f"{{{NS}}}text")
        raw = "" if text_el is None else "".join(text_el.itertext())
        if code is not None and code.get("code") == section_code and phrase in normalise(raw):
            in_coded = True
            break
    if in_coded:
        return "CARRIES_CODED"
    if phrase in normalise("".join(root.itertext())):
        return "CARRIES_UNCODED"
    return "ABSENT"


def match_openfda(label: dict, fact: dict) -> str:
    phrase = normalise(fact["phrase_key"])
    boxed = label.get("boxed_warning") or []
    if isinstance(boxed, str):
        boxed = [boxed]
    if boxed and phrase in normalise(" ".join(boxed)):
        return "CARRIES_CODED"
    others = {key: value for key, value in label.items() if key != "boxed_warning"}
    if phrase in normalise(json.dumps(others)):
        return "CARRIES_UNCODED"
    return "ABSENT"
