#!/usr/bin/env python3
"""Structural contract for sweep parameter-space visualization and explicit execution."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_research_orchestrator_ui.py"


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
    markers = (
        "Research task",
        "Sweep Design",
        "Campaign Execution",
        "Data / Convergence / Compare",
        "Parameter-space coverage",
        "_render_parameter_space",
        "Queue sweep campaign",
        "Start queued sweep campaign",
        "pl_orch_queued_job_",
        "QUEUED · NOT STARTED",
    )
    for marker in markers:
        assert marker in source, f"missing orchestrator marker: {marker}"
    assert "Create & start sweep campaign" not in source, "campaign creation and execution must remain separate"
    assert "st.tabs" not in source, "Research Orchestrator should render only the selected task"
    assert "Scatter3d" in source, "3D parameter-space coverage must be supported"
    assert "plotly_chart" in source, "parameter-space coverage must render graphically"

    tree = ast.parse(source)
    funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required = (
        "_parameter_axes",
        "_render_parameter_space",
        "_queue_sweep_campaign",
        "_start_queued_sweep_campaign",
        "_render_sweep",
        "_render_executor",
        "render_research_orchestrator",
    )
    for name in required:
        assert name in funcs, f"missing required function: {name}"

    queue_calls = calls_in(funcs["_queue_sweep_campaign"])
    start_calls = calls_in(funcs["_start_queued_sweep_campaign"])
    sweep_calls = calls_in(funcs["_render_sweep"])
    executor_calls = calls_in(funcs["_render_executor"])
    top_calls = calls_in(funcs["render_research_orchestrator"])

    assert "create_sweep_job" in queue_calls
    assert "start_sweep_job" not in queue_calls, "queue helper must not start execution"
    assert "start_sweep_job" in start_calls
    assert "create_sweep_job" not in start_calls, "start helper must not create a new campaign"
    assert "_render_parameter_space" in sweep_calls, "design view must visualize parameter-space coverage"
    assert "_render_parameter_space" in executor_calls, "campaign results must map status back into parameter space"
    for name in ("_render_sweep", "_render_executor", "_render_table_and_convergence"):
        assert name in top_calls, f"top-level task selector missing {name}"

    print("PASS: sweep parameter-space visualization + explicit queue/start execution boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
