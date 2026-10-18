"""G035: V1 identity and the listing gate on the fixture."""

from app.engine.identity import identify
from app.graph.db import delete_graph
from app.graph.fixture import load_fixture

GRAPH = "hub_identity"
AS_OF = 20742


def setup_module() -> None:
    load_fixture(GRAPH)


def teardown_module() -> None:
    delete_graph(GRAPH)


def test_hero_package_resolves_to_its_label_of_record() -> None:
    found = identify("68071-3355-9", AS_OF, GRAPH)
    assert found is not None
    assert found["product_ndc"] == "68071-3355"
    assert found["listing_active"] is True
    assert found["record_sets"] == ["549f1d1a-81f5-29f5-e054-00144ff8d46c"]


def test_old_set_is_not_the_label_of_record() -> None:
    found = identify("65862-574-10", AS_OF, GRAPH)
    assert found is not None
    assert any(item.startswith("ba42b0a9") for item in found["record_sets"])
    assert any(item.startswith("7636a692") for item in found["all_sets"])
    assert not any(item.startswith("7636a692") for item in found["record_sets"])


def test_unknown_ndc_has_no_row() -> None:
    assert identify("00000-0000-00", AS_OF, GRAPH) is None
