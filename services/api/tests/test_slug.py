"""G024: party slugs."""

from app.sources.slug import party_id, slug


def test_nucare_spellings_share_one_labeler_id() -> None:
    names = [
        "NuCare Pharmaceuticals,Inc.",
        "NuCare Pharmaceuticals, Inc",
        "NuCare Pharmaceuticals, Inc.",
    ]
    assert {party_id("labeler", name) for name in names} == {"labeler:nucare-pharmaceuticals"}


def test_ampersand_and_partnership_suffix() -> None:
    assert slug("Foo & Bar, L.P.") == "foo-and-bar"
    assert slug("Acme Corporation") == "acme"
