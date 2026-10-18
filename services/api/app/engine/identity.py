"""V1 identity. A missing row is an unknown NDC."""

from app.graph import queries
from app.graph.db import ro_query

COLUMNS = (
    "product_ndc",
    "molecule_key",
    "labeler_name",
    "dosage_form",
    "strength",
    "listing_spl_id",
    "listing_expiration_d",
    "listing_active",
    "record_sets",
    "all_sets",
)


def identify(ndc: str, as_of_d: int, graph: str = "hub") -> dict | None:
    result = ro_query(graph, queries.V1, {"ndc": ndc, "as_of_d": as_of_d})
    if not result.result_set:
        return None
    row = result.result_set[0]
    found = dict(zip(COLUMNS, row, strict=True))
    found["record_sets"] = [item for item in (found["record_sets"] or []) if item]
    found["all_sets"] = [item for item in (found["all_sets"] or []) if item]
    found["listing_active"] = bool(found["listing_active"])
    return found
