#!/usr/bin/env python3
"""Deterministic integrity checks for shared scientific UI semantics.

This validator intentionally checks both behavior and integration boundaries.  The
shared presentation layer must never promote execution/provenance into scientific
validation/support, and participating workspaces must opt in explicitly.
"""
from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
SEMANTICS = UI / "physical_lab_ui_semantics.py"
TAURI = ROOT / "src-tauri" / "tauri.conf.json"

REQUIRED_OBJECT_TYPES = {"MEASUREMENT", "DATASET", "MODEL", "RESULT"}
REQUIRED_AXES = {"Validation", "Scientific Status", "Provenance", "Execution"}
FIRST_PHASE_FILES = {
    "physical_lab_project_interop_ui.py": {"render_context_header", "render_status_card"},
    "physical_lab_result_inspector_ui.py": {"render_context_header", "render_object_card", "render_status_card"},
    "physical_lab_visual_analytics_ui.py": {"render_context_header", "render_object_card"},
    "physical_lab_model_coupling_ui.py": {"render_context_header", "render_object_card", "render_status_card"},
    "physical_lab_pipeline_graph_ui.py": {"render_context_header", "render_status_card"},
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _call_names(text: str) -> set[str]:
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _source(path: Path) -> str:
    _require(path.exists(), f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _validate_core_source() -> None:
    semantics_text = _source(SEMANTICS)
    for token in REQUIRED_OBJECT_TYPES:
        _require(token in semantics_text, f"shared semantics missing object type {token}")
    for axis in REQUIRED_AXES:
        _require(axis in semantics_text, f"shared semantics missing status axis label {axis}")
    for helper in (
        "normalize_object_type",
        "normalize_status_axes",
        "render_context_header",
        "render_object_card",
        "render_status_card",
    ):
        _require(helper in semantics_text, f"shared semantics missing helper {helper}")
    _require("SUCCEEDED" in semantics_text and "PASS" in semantics_text, "execution/validation vocabularies missing")
    _require("RECORDED" in semantics_text and "SUPPORTED" in semantics_text, "provenance/scientific vocabularies missing")

    tauri_text = _source(TAURI)
    _require(
        '"resources/ui/physical_lab_ui_semantics.py": "ui/physical_lab_ui_semantics.py"' in tauri_text,
        "physical_lab_ui_semantics.py is not bundled in tauri.conf.json",
    )


def _validate_behavior() -> None:
    sys.path.insert(0, str(UI))
    try:
        module = importlib.import_module("physical_lab_ui_semantics")
    finally:
        if sys.path and sys.path[0] == str(UI):
            sys.path.pop(0)

    normalize_object_type = module.normalize_object_type
    normalize_status_axes = module.normalize_status_axes
    status_display = module.status_display

    for object_type in REQUIRED_OBJECT_TYPES:
        _require(normalize_object_type(object_type) == object_type, f"object type {object_type} not stable")
    _require(normalize_object_type("schema") == "UNKNOWN", "object type must not be inferred from arbitrary text")
    _require(normalize_object_type("") == "UNKNOWN", "missing object type must remain UNKNOWN")

    axes = normalize_status_axes(execution="SUCCEEDED")
    _require(axes["validation"] == "NOT ESTABLISHED", "SUCCEEDED must not imply validation PASS")
    _require(axes["scientific"] == "NOT ESTABLISHED", "SUCCEEDED must not imply scientific support")
    _require(axes["execution"] == "SUCCEEDED", "explicit execution state was not preserved")

    axes = normalize_status_axes(provenance="RECORDED")
    _require(axes["scientific"] == "NOT ESTABLISHED", "RECORDED provenance must not imply SUPPORTED science")
    _require(axes["validation"] == "NOT ESTABLISHED", "RECORDED provenance must not imply validation PASS")

    axes = normalize_status_axes()
    _require(axes == {
        "validation": "NOT ESTABLISHED",
        "scientific": "NOT ESTABLISHED",
        "provenance": "UNSPECIFIED",
        "execution": "NOT APPLICABLE",
    }, f"missing statuses must fail closed, got {axes}")

    axes = normalize_status_axes(validation="definitely-good", scientific="certain", provenance="perfect", execution="done")
    _require(axes["validation"] == "NOT ESTABLISHED", "unknown validation must fail closed")
    _require(axes["scientific"] == "NOT ESTABLISHED", "unknown scientific status must fail closed")
    _require(axes["provenance"] == "UNSPECIFIED", "unknown provenance must fail closed")
    _require(axes["execution"] == "NOT APPLICABLE", "unknown execution must fail closed")

    for axis, value in normalize_status_axes(execution="RUNNING").items():
        rendered = status_display(axis, value)
        _require(value in rendered, f"status display for {axis} omits text label")
        _require(rendered != value, f"status display for {axis} must include a visible symbol")


def _validate_integrations() -> None:
    texts: dict[str, str] = {}
    for filename, helpers in FIRST_PHASE_FILES.items():
        text = _source(UI / filename)
        texts[filename] = text
        _require("physical_lab_ui_semantics" in text, f"{filename} does not import shared semantics")
        calls = _call_names(text)
        for helper in helpers:
            _require(helper in calls, f"{filename} does not call {helper}")

    project = texts["physical_lab_project_interop_ui.py"]
    _require("do not imply scientific validation" in project, "Project Home scientific boundary was weakened")

    inspector = texts["physical_lab_result_inspector_ui.py"]
    _require('object_type="RESULT"' in inspector, "Result Inspector must explicitly identify RESULT objects")

    analytics = texts["physical_lab_visual_analytics_ui.py"]
    _require("selection" in analytics.lower(), "Visual Analytics linked-selection behavior unexpectedly missing")
    _require('object_type=' in analytics, "Visual Analytics must explicitly supply a source object type")

    coupling = texts["physical_lab_model_coupling_ui.py"]
    _require('object_type="DATASET"' in coupling, "Model Coupling must explicitly identify DATASET source")
    _require('object_type="MODEL"' in coupling, "Model Coupling must explicitly identify MODEL target")
    for phrase in ("compatibility", "causality", "calibration validity", "model suitability"):
        _require(phrase in coupling.lower(), f"Model Coupling scientific boundary missing phrase: {phrase}")
    _require("Queue downstream model" in coupling and "Start queued downstream model" in coupling,
             "Model Coupling Queue/Start boundary changed")

    pipeline = texts["physical_lab_pipeline_graph_ui.py"]
    _require("physical data transfer" in pipeline.lower(), "Pipeline DAG data-transfer boundary was weakened")


def main() -> None:
    _validate_core_source()
    _validate_behavior()
    _validate_integrations()
    print(json.dumps({
        "shared_semantics": "ok",
        "object_types": sorted(REQUIRED_OBJECT_TYPES),
        "status_axes": sorted(REQUIRED_AXES),
        "integrated_workspaces": sorted(FIRST_PHASE_FILES),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
