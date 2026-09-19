#!/usr/bin/env python3
"""Structural and helper contract for coordinated U-tube scientific views."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
UI = UI_ROOT / "physical_lab_utube_experiment_ui.py"
sys.path.insert(0, str(UI_ROOT))


def calls_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        fn = child.func
        if isinstance(fn, ast.Name):
            out.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            out.add(fn.attr)
    return out


def main() -> int:
    source = UI.read_text(encoding="utf-8")
    markers = (
        "U-Tube task",
        "Coordinated operating point",
        "_coordinated_operating_point",
        "_operating_point_controls",
        "_operating_point_summary",
        "Selected model operating point · context only",
        "Physical View",
        "Threshold Map",
        "Theory ↔ Experiment",
        "n_c",
        "n_g",
    )
    for marker in markers:
        assert marker in source, f"missing coordinated-view marker: {marker}"
    assert "st.tabs" not in source, "U-Tube experiment should render only the selected task"

    tree = ast.parse(source)
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required = (
        "_coordinated_operating_point",
        "_operating_point_controls",
        "_operating_point_summary",
        "_theory_tab",
        "_phase_map_tab",
        "_validation_tab",
        "render_utube_experiment",
    )
    for name in required:
        assert name in funcs, f"missing required function: {name}"

    top_calls = calls_in(funcs["render_utube_experiment"])
    for name in ("_operating_point_controls", "_theory_tab", "_phase_map_tab", "_validation_tab"):
        assert name in top_calls, f"top-level U-Tube workflow missing coordinated call: {name}"
    assert "_capacity_decomposition" in calls_in(funcs["_coordinated_operating_point"])
    assert "_operating_point_summary" in calls_in(funcs["_theory_tab"])

    import physical_lab_utube_experiment_ui as ui
    point = ui._coordinated_operating_point(3.0, 260.0, 48)
    assert point["volume_ml"] == 3.0
    assert point["n_rpm"] == 260.0
    assert point["quadrature_order"] == 48
    assert point["critical_speed_rpm"] > 0
    assert point["threshold_rpm"] > 0
    assert point["critical_speed_rpm"] != point["threshold_rpm"], "n_c and n_g must remain distinct quantities"

    print("PASS: coordinated U-Tube operating point across physical/map/validation views")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
