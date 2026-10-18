"""G023: synthetic SPL files. Phrase key only; no copied label text."""

from pathlib import Path

from app.sources.spl import normalise_text, parse_spl, text_norm_hash

FIXTURES = Path(__file__).parent / "fixtures"
PHRASE = "warning: serious neuropsychiatric events"


def _parse(name: str) -> dict:
    return parse_spl((FIXTURES / name).read_bytes())


def test_coded_boxed_warning_section() -> None:
    parsed = _parse("spl_coded.xml")
    assert parsed["doc_id"] == "doc-coded"
    assert parsed["set_id"] == "set-coded"
    assert parsed["version"] == 5
    assert parsed["effective"] == "20240711"
    assert parsed["labeler_name"] == "NuCare Pharmaceuticals, Inc."
    assert parsed["duns"] == "999999999"
    coded = next(section for section in parsed["sections"] if section["code"] == "34066-1")
    assert PHRASE in coded["text_norm"]
    assert coded["text_norm_hash"] == text_norm_hash(coded["text_norm"])
    assert parsed["products"][0]["ndc"] == "68071-3355"
    assert parsed["products"][0]["source_ndcs"] == ["16729-119"]
    assert parsed["products"][0]["approval_id"] == "ANDA202717"
    assert parsed["products"][0]["dosage_form"] == "TABLET, FILM COATED"


def test_phrase_outside_a_coded_boxed_warning_section() -> None:
    parsed = _parse("spl_uncoded.xml")
    assert all(section["code"] != "34066-1" for section in parsed["sections"])
    assert any(PHRASE in section["text_norm"] for section in parsed["sections"])


def test_no_phrase() -> None:
    parsed = _parse("spl_absent.xml")
    assert all(PHRASE not in section["text_norm"] for section in parsed["sections"])
    assert parsed["version"] == 3


def test_multi_product_equivalent_entities() -> None:
    parsed = _parse("spl_multi.xml")
    by_ndc = {product["ndc"]: product for product in parsed["products"]}
    assert by_ndc["42291-622"]["source_ndcs"] == ["16729-119"]
    assert by_ndc["42291-622"]["approval_id"] == "ANDA202717"
    assert by_ndc["50268-574"]["source_ndcs"] == ["65862-574", "16729-120"]
    assert by_ndc["50268-574"]["approval_id"] == "ANDA204290"


def test_normalise_collapses_case_and_whitespace() -> None:
    assert normalise_text("  Warning:\nSERIOUS   neuropsychiatric\u00a0events ") == PHRASE
