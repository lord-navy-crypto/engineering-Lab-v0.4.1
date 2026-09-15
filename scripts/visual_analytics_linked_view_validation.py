#!/usr/bin/env python3
"""Structural contract for task-oriented linked Visual Analytics views."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_visual_analytics_ui.py"


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
    required_markers = (
        "Analysis task",
        "Investigate Selection",
        "Compare Sources",
        "Dashboard Recipe",
        "_render_selection_inspector",
        "Selected records",
        "Selected numeric summary",
        "Selected distribution",
        "Download selected rows CSV",
        "Selection changes the view only",
    )
    for marker in required_markers:
        assert marker in source, f"missing linked-view marker: {marker}"
    assert "st.tabs" not in source, "Visual Analytics should render only the selected task"
    assert "download_button" in source, "selected subset must be exportable"
    assert "Histogram" in source, "selected subset needs a distribution view"

    tree = ast.parse(source)
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ("_render_selection_inspector", "_uncertainty_tab", "_overlay_tab", "render_visual_analytics"):
        assert name in funcs, f"missing required function: {name}"

    inspector_calls = calls_in(funcs["_render_selection_inspector"])
    uncertainty_calls = calls_in(funcs["_uncertainty_tab"])
    overlay_calls = calls_in(funcs["_overlay_tab"])
    render_calls = calls_in(funcs["render_visual_analytics"])

    assert "dataframe" in inspector_calls, "linked inspector must show selected records/summary"
    assert "plotly_chart" in inspector_calls, "linked inspector must render selected distribution"
    assert "download_button" in inspector_calls, "linked inspector must export selected rows"
    assert "_render_selection_inspector" in uncertainty_calls, "selection plot must drive linked inspector"
    assert "_render_selection_inspector" in overlay_calls, "overlay selection must drive linked inspector"
    assert "radio" in render_calls, "top-level Visual Analytics must use a task selector"

    print("PASS: Visual Analytics task workflow + linked selection rows/summary/distribution/export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
