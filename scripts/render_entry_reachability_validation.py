#!/usr/bin/env python3
"""Audit packaged public render_* entry points against native desktop reachability."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
CATALOG_PATH = ROOT / "src-tauri" / "resources" / "surfaces.json"


def public_renderers(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("render_")
        and not node.name.startswith("render__")
    ]


def main() -> None:
    rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    targets = {
        (str(row.get("targetModule") or ""), str(row.get("targetCallable") or ""))
        for row in rows
        if isinstance(row, dict) and row.get("targetModule") and row.get("targetCallable")
    }

    discovered: list[tuple[str, str]] = []
    for path in sorted(UI_ROOT.glob("physical_lab_*.py")):
        module = path.stem
        for name in public_renderers(path):
            discovered.append((module, name))

    uncovered = sorted(pair for pair in discovered if pair not in targets)
    if uncovered:
        formatted = "\n".join(f"  - {module}.{name}" for module, name in uncovered)
        raise AssertionError(
            "public render_* entry points lack native reachability classification:\n" + formatted
        )

    print(json.dumps({
        "public_render_entries": len(discovered),
        "catalog_render_targets": len(targets),
        "unclassified_render_entries": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
