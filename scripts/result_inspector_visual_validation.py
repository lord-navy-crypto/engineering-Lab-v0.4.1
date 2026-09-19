#!/usr/bin/env python3
"""Structural and helper checks for Result Inspector schema/provenance visualization."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
UI = UI_ROOT / "physical_lab_result_inspector_ui.py"
sys.path.insert(0, str(UI_ROOT))


def calls_in(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        fn = child.func
        if isinstance(fn, ast.Name):
            names.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            names.add(fn.attr)
    return names


def main() -> int:
    source = UI.read_text(encoding="utf-8")
    required = (
        "Schema map",
        "Provenance chain",
        "_schema_tree_layout",
        "_render_schema_tree",
        "_render_provenance_chain",
        "plotly_chart",
        "read-only",
    )
    for marker in required:
        assert marker in source, f"missing Result Inspector visualization marker: {marker}"

    tree = ast.parse(source)
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ("_schema_tree_layout", "_render_schema_tree", "_render_provenance_chain", "_render_inspection"):
        assert name in funcs, f"missing required function: {name}"
    assert "plotly_chart" in calls_in(funcs["_render_schema_tree"]), "schema tree must render graphically"
    assert "plotly_chart" in calls_in(funcs["_render_provenance_chain"]), "provenance chain must render graphically"
    inspection_calls = calls_in(funcs["_render_inspection"])
    assert "_render_schema_tree" in inspection_calls
    assert "_render_provenance_chain" in inspection_calls

    import physical_lab_result_inspector_ui as ui

    inventory = [
        {"path": "$", "kind": "object", "role": "container"},
        {"path": "$.trajectory", "kind": "object", "role": "container"},
        {"path": "$.trajectory.x", "kind": "vector", "role": "output", "unit": "m"},
        {"path": "$.trajectory.y", "kind": "vector", "role": "output", "unit": "m"},
        {"path": "$.energy", "kind": "scalar", "role": "output", "unit": "J"},
    ]
    layout = ui._schema_tree_layout(inventory)
    by_path = {row["path"]: row for row in layout}
    assert by_path["$"]["parent"] is None
    assert by_path["$.trajectory"]["parent"] == "$"
    assert by_path["$.trajectory.x"]["parent"] == "$.trajectory"
    assert by_path["$.trajectory.x"]["depth"] == 2
    assert by_path["$.energy"]["parent"] == "$"

    print("PASS: Result Inspector schema map + provenance chain visualization contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
