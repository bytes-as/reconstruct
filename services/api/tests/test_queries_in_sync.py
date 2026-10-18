"""G011: queries.py matches docs/queries.cypher."""

from pathlib import Path

from app.graph import queries


def parse_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    name = None
    kind = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal name, kind, buf
        if name is not None:
            key = f"SCHEMA_{name.upper()}" if kind == "schema" else name
            blocks[key] = "\n".join(buf).strip()
        name = None
        kind = None
        buf = []

    for line in text.splitlines():
        if line.startswith("// @query "):
            flush()
            kind = "query"
            name = line.split()[2]
            continue
        if line.startswith("// @schema "):
            flush()
            kind = "schema"
            name = line.split()[2]
            continue
        if line.startswith("// ====="):
            flush()
            continue
        if line.startswith("//") or name is None:
            continue
        buf.append(line)
    flush()
    return blocks


def cypher_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "docs" / "queries.cypher"
        if candidate.is_file():
            return candidate
    mounted = Path("/repo/docs/queries.cypher")
    if mounted.is_file():
        return mounted
    raise FileNotFoundError("docs/queries.cypher")


def norm(text: str) -> str:
    return " ".join(text.split())


REQUIRED = (
    ["SCHEMA_HUB", "SCHEMA_TENANT"]
    + [f"I{i}" for i in range(1, 14)]
    + [f"V{i}" for i in range(1, 7)]
    + [f"W{i}" for i in range(1, 5)]
    + [f"D{i}" for i in range(1, 7)]
    + [f"L{i}" for i in range(1, 4)]
    + [f"P{i}" for i in range(1, 4)]
    + ["R1"]
    + [f"A{i}" for i in range(1, 4)]
    + [f"T{i}" for i in range(1, 22)]
    + [f"K{i}" for i in range(1, 9)]
    + [f"X{i}" for i in range(1, 7)]
)


def test_constants_match_cypher_file() -> None:
    parsed = parse_blocks(cypher_path().read_text())
    constants = {name: getattr(queries, name) for name in queries.NAMES}
    assert set(parsed) == set(constants)
    assert set(REQUIRED) <= set(parsed)
    for name, block in parsed.items():
        assert norm(block) == norm(constants[name])
