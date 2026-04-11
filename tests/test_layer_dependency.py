"""P11: Layer dependency — workflow/* must not import tools.* or skills.*"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

WORKFLOW_DIR = Path(__file__).parent.parent / "src" / "zotpilot" / "workflow"
TOOLS_DIR = Path(__file__).parent.parent / "src" / "zotpilot" / "tools"

_FORBIDDEN_FROM_WORKFLOW = ("zotpilot.tools", "zotpilot.skills")


def _resolve_relative(path: Path, level: int, module: str | None) -> str:
    """Resolve a relative import to an absolute zotpilot.* module name."""
    # Find the zotpilot package root
    src_root = WORKFLOW_DIR.parent.parent  # src/
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        rel = path.relative_to(TOOLS_DIR.parent.parent)

    parts = list(rel.with_suffix("").parts)  # e.g. ['zotpilot', 'workflow', 'batch']
    # Go up 'level' steps (1 = same package, 2 = parent, ...)
    base_parts = parts[: len(parts) - level + 1]  # include current package
    if level == 1:
        # from . import X  → same package
        base_parts = parts[:-1]
    else:
        base_parts = parts[: max(0, len(parts) - level)]

    base = ".".join(base_parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


def _collect_imports(path: Path) -> list[str]:
    """Return list of fully qualified module names imported in a .py file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import — resolve to absolute
                resolved = _resolve_relative(path, node.level, node.module)
                modules.append(resolved)
            elif node.module:
                modules.append(node.module)
    return modules


@pytest.mark.parametrize(
    "py_file",
    list(WORKFLOW_DIR.glob("*.py")),
    ids=lambda p: p.name,
)
def test_workflow_file_does_not_import_tools_or_skills(py_file: Path) -> None:
    """No file under workflow/ may import zotpilot.tools.* or zotpilot.skills.*"""
    # worker.py is allowed a local-scope import of tools.ingestion (inside function body)
    # We check top-level imports only for the hard rule; local-scope deferred imports
    # are implementation detail but let's check all imports to be strict.
    imports = _collect_imports(py_file)
    violations = [
        m for m in imports
        if any(m == prefix or m.startswith(prefix + ".") for prefix in _FORBIDDEN_FROM_WORKFLOW)
    ]
    assert violations == [], (
        f"{py_file.name} has forbidden imports into tools/skills layer: {violations}"
    )
