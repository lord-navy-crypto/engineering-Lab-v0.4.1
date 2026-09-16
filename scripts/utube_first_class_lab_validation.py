#!/usr/bin/env python3
"""Require the rotating U-Tube research suite to be a first-class bundled Physics Lab."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src-tauri" / "resources" / "modules.json"
ENTRY = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_builtin_lab_entry.py"
ADVANCED = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_utube_advanced_ui.py"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
ADAPTERS = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_native_workbench_adapters.py"
UTUBE_IDS = (
    "utube-studio", "utube-physical", "utube-uncertainty", "utube-experiment-planner",
    "utube-advanced", "utube-robust", "utube-hysteresis",
)


def effective_surfaces() -> list[dict]:
    rows = json.loads(SURFACES.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("_utube_native_adapters", ADAPTERS)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load native U-Tube surface extensions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    merge = getattr(module, "merge_native_surface_rows", None)
    return merge(rows) if callable(merge) else rows


def main() -> None:
    modules = json.loads(MODULES.read_text(encoding="utf-8"))
    rows = [row for row in modules if isinstance(row, dict) and row.get("id") == "rotating-utube"]
    if len(rows) != 1:
        raise AssertionError("modules.json must contain exactly one rotating-utube Lab")
    row = rows[0]
    if row.get("kind") != "lab" or row.get("bundled") is not True:
        raise AssertionError("rotating-utube must be a bundled first-class Lab")
    if row.get("entrypoint") != "app.py":
        raise AssertionError("rotating-utube bundled entrypoint must be app.py")
    if row.get("safeBackend") != "standard":
        raise AssertionError("rotating-utube must use the standard safe backend")
    verify = set(row.get("verifyImports") or [])
    for package in ("numpy", "scipy", "pandas", "plotly", "streamlit"):
        if package not in verify:
            raise AssertionError(f"rotating-utube missing verify import: {package}")

    entry = ENTRY.read_text(encoding="utf-8")
    markers = {
        '"rotating-utube"': "bundled entry does not recognize rotating-utube",
        'PROFILE == "rotating-utube"': "bundled entry lacks dedicated rotating-utube renderer branch",
        "render_utube_experiment": "bundled U-Tube Lab does not render the physical model",
        "render_utube_uncertainty": "bundled U-Tube Lab does not render uncertainty",
        "render_utube_advanced": "bundled U-Tube Lab does not render advanced/experiment-planner views",
        "render_requested_surface": "bundled U-Tube host does not honor direct Workbench deep-links",
    }
    for marker, error in markers.items():
        if marker not in entry:
            raise AssertionError(error)

    advanced = ADVANCED.read_text(encoding="utf-8")
    if "render_utube_robust_engineering(st, profile)" not in advanced:
        raise AssertionError("U-Tube Advanced no longer continues into Robust Design / Digital Twin")
    if "render_utube_hysteresis(st, profile)" not in advanced:
        raise AssertionError("U-Tube Advanced no longer continues into Dynamic Threshold / Hysteresis")

    surfaces = effective_surfaces()
    by_id = {str(item.get("id")): item for item in surfaces if isinstance(item, dict)}
    for surface_id in UTUBE_IDS:
        surface = by_id.get(surface_id)
        if surface is None:
            raise AssertionError(f"missing U-Tube Workbench surface: {surface_id}")
        preferred = list(surface.get("preferredProfiles") or [])
        profiles = list(surface.get("profiles") or [])
        if "rotating-utube" not in preferred + profiles:
            raise AssertionError(f"{surface_id} does not prefer/allow the first-class rotating-utube host")
    planner = by_id["utube-experiment-planner"]
    if planner.get("targetCallable") != "render_utube_experiment_planner_native":
        raise AssertionError("focused U-Tube Experiment Planner is not wired to its native adapter")

    print(json.dumps({
        "first_class_utube_lab": True,
        "module_id": "rotating-utube",
        "utube_workbench_surfaces": len(UTUBE_IDS),
        "focused_experiment_planner": True,
        "advanced_includes_robust_and_hysteresis": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
