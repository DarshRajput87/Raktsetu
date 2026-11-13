"""Project rule 1: backend/core must not import any heap / graph / queue library."""

import ast
from pathlib import Path

FORBIDDEN = {"heapq", "networkx", "collections", "sortedcontainers", "queue", "bisect"}
CORE = Path(__file__).resolve().parents[2] / "core"


def imported_modules(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_core_uses_no_forbidden_libraries():
    files = list(CORE.glob("*.py"))
    assert files
    for path in files:
        assert not imported_modules(path) & FORBIDDEN, path.name
