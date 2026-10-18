"""G013 and G014: no string-built Cypher, and every variable-length path is bounded."""

import ast
import re
from pathlib import Path

from app.graph import queries

APP = Path(__file__).resolve().parents[1] / "app"


def _calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"query", "ro_query"}:
            yield node


def _built(node: ast.AST) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return True
    return any(_built(child) for child in ast.iter_child_nodes(node))


def test_query_calls_are_not_string_built() -> None:
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for call in _calls(tree):
            for arg in list(call.args) + [keyword.value for keyword in call.keywords]:
                if _built(arg):
                    offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == []


def test_variable_length_paths_are_bounded() -> None:
    text = "\n".join(getattr(queries, name) for name in queries.NAMES)
    unbounded: list[str] = []
    for match in re.finditer(r"\[\s*:[^\]]+\]", text):
        body = match.group(0)
        if "*" in body and not re.search(r"\*\d+\.\.\d+", body):
            unbounded.append(body)
    assert unbounded == []
