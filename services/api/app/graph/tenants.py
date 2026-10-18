"""Load the fictional demo tenants. Rulings are not in these files."""

import sys
from pathlib import Path

from app.graph.db import connect_once, delete_graph, list_graphs, query
from app.graph.queries import SCHEMA_TENANT
from app.graph.schema import apply_block

TENANTS = {
    "tenant_bayview": "bayview.cypher",
    "tenant_northgate": "northgate.cypher",
}


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "demo_tenants").is_dir():
            return parent
    return Path("/repo")


def statements(path: Path) -> list[str]:
    found: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.endswith(";"):
            line = line[:-1].strip()
        if line:
            found.append(line)
    return found


def seed() -> None:
    db = connect_once()
    root = repo_root() / "data" / "demo_tenants"
    for graph, filename in TENANTS.items():
        delete_graph(graph, db)
        apply_block(graph, SCHEMA_TENANT, db=db)
        for statement in statements(root / filename):
            query(graph, statement, db=db)
        print(f"seeded {graph}")


def reset() -> None:
    db = connect_once()
    for name in list_graphs(db):
        if name.startswith("tenant_"):
            delete_graph(name, db)
            print(f"deleted {name}")
    seed()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if command == "seed":
        seed()
    elif command == "reset":
        reset()
    else:
        raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main()
