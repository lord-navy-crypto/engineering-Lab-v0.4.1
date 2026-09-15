#!/usr/bin/env python3
"""Structural UI checks for staged Model Coupling and explicit queue/start boundary."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_model_coupling_ui.py"


def calls_in(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            fn = child.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def main() -> int:
    source = UI.read_text(encoding="utf-8")
    required_markers = (
        "Coupling task",
        "Configure Mapping",
        "Review Packet",
        "Save / Execute",
        "Provenance",
        "Queue downstream model",
        "Start queued downstream model",
        "_render_mapping_flow",
        "pl_couple_queued_job_",
        "packet_sha256",
        "execution_started",
    )
    for marker in required_markers:
        assert marker in source, f"missing staged coupling marker: {marker}"
    assert "Queue & start downstream model" not in source, "queue/start must remain separate explicit actions"
    assert "st.tabs" not in source, "Model Coupling should render only the selected task"
    assert "plotly_chart" in source, "mapping flow must be graphically rendered"

    tree = ast.parse(source)
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ("_queue_downstream_model", "_start_queued_downstream_model", "_render_mapping_flow", "render_model_coupling"):
        assert name in funcs, f"missing required function: {name}"

    queue_calls = calls_in(funcs["_queue_downstream_model"])
    start_calls = calls_in(funcs["_start_queued_downstream_model"])
    flow_calls = calls_in(funcs["_render_mapping_flow"])

    assert "queue_packet" in queue_calls, "queue helper must create the queued job"
    assert "start_sweep_job" not in queue_calls, "queue helper must not start execution"
    assert "start_sweep_job" in start_calls, "start helper must explicitly start the queued job"
    assert "queue_packet" not in start_calls, "start helper must not create a new queued job"
    assert "plotly_chart" in flow_calls, "mapping flow helper must render the visual mapping"

    render_calls = calls_in(funcs["render_model_coupling"])
    assert "_queue_downstream_model" in render_calls
    assert "_start_queued_downstream_model" in render_calls
    assert "_render_mapping_flow" in render_calls

    print("PASS: staged Model Coupling workflow + visual mapping + explicit queue/start boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
