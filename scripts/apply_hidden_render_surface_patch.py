#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
TAURI = ROOT / "src-tauri" / "tauri.conf.json"

ALL_PROFILES = [
    "numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo",
    "nonlinear-chaos", "oscillation-integration", "radia-magnet-studio", "radiation-platform",
]
NON_ACCEL = [
    "numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo",
    "nonlinear-chaos", "oscillation-integration",
]
APP_PROFILES = ["numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo"]

NEW_ROWS = [
    {
        "id": "application-scenarios",
        "label": "Application Mode & Physics Scenarios",
        "category": "Experiments & Physics",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": APP_PROFILES,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_application_scenarios",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → Mathematical Tool / Physics Scenario + engineering review",
    },
    {
        "id": "compute-workspace",
        "label": "Experiment Kernel & Compute",
        "category": "Modeling & Simulation",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": ALL_PROFILES,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_compute_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → durable local compute queue and experiment manifests",
    },
    {
        "id": "diagnostics-workspace",
        "label": "Run & Diagnostics Log",
        "category": "Reproducibility & AI",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": ALL_PROFILES,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_diagnostics_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → unified run, worker and diagnostic event timeline",
    },
    {
        "id": "engineering-design-workflow",
        "label": "Engineering Design Workflow",
        "category": "Engineering Decisions & Reliability",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": ALL_PROFILES,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_engineering_workflow_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → requirements, Pareto, reliability, measured field, thermal/control and batch planning",
    },
    {
        "id": "model-campaign",
        "label": "Automated Model Campaign",
        "category": "Modeling & Simulation",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": NON_ACCEL,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_model_campaign_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → bounded model-specific refinement and replicate campaign",
    },
    {
        "id": "model-engineering",
        "label": "Model Engineering Scorecard",
        "category": "Engineering Decisions & Reliability",
        "kind": "surface",
        "launchMode": "profile",
        "profiles": NON_ACCEL,
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_model_engineering_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Native Workbench → domain scorecard, convergence/cost and replicate robustness",
    },
]

rows = json.loads(SURFACES.read_text(encoding="utf-8"))
by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict)}

measurement = by_id.get("measurement-registry")
if measurement is None:
    raise SystemExit("measurement-registry row missing")
measurement.clear()
measurement.update({
    "id": "measurement-registry",
    "label": "Measurement & Calibration Registry",
    "category": "Data & Measurement",
    "sourceSurfaceId": "measurement-registry",
    "kind": "surface",
    "launchMode": "profile",
    "profiles": ALL_PROFILES,
    "targetModule": "physical_lab_native_workbench_adapters",
    "targetCallable": "render_measurement_registry_native",
    "argumentMode": "st_profile_namespace",
    "routeHint": "Native Workbench → active .physlab Project → measurement and calibration evidence",
})

for new_row in NEW_ROWS:
    existing = by_id.get(new_row["id"])
    if existing is None:
        rows.append(new_row)
        by_id[new_row["id"]] = new_row
    else:
        existing.clear(); existing.update(new_row)

SURFACES.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

text = TAURI.read_text(encoding="utf-8")
needle = '"resources/ui/physical_lab_model_builder.py": "ui/physical_lab_model_builder.py"'
insert = '"resources/ui/physical_lab_native_workbench_adapters.py": "ui/physical_lab_native_workbench_adapters.py",\n      ' + needle
if "physical_lab_native_workbench_adapters.py" not in text:
    if needle not in text:
        raise SystemExit("tauri resource insertion anchor missing")
    text = text.replace(needle, insert, 1)
TAURI.write_text(text, encoding="utf-8")

print(json.dumps({"surface_rows": len(rows), "added": [r["id"] for r in NEW_ROWS], "measurement_registry_focused": True}, sort_keys=True))
