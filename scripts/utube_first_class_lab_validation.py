#!/usr/bin/env python3
"""Require the rotating U-Tube research suite to be a first-class bundled Physics Lab."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src-tauri" / "resources" / "modules.json"
ENTRY = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_builtin_lab_entry.py"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"


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
        "render_utube_robust_engineering": "bundled U-Tube Lab does not expose robust design / digital twin",
        "render_utube_hysteresis": "bundled U-Tube Lab does not expose dynamic threshold / hysteresis",
    }
    for marker, error in markers.items():
        if marker not in entry:
            raise AssertionError(error)

    surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
    by_id = {str(item.get("id")): item for item in surfaces if isinstance(item, dict)}
    for surface_id in ("utube-studio", "utube-physical", "utube-uncertainty", "utube-advanced", "utube-robust", "utube-hysteresis"):
        surface = by_id.get(surface_id)
        if surface is None:
            raise AssertionError(f"missing U-Tube Workbench surface: {surface_id}")
        preferred = list(surface.get("preferredProfiles") or [])
        profiles = list(surface.get("profiles") or [])
        if surface_id != "utube-studio" and "rotating-utube" not in preferred + profiles:
            raise AssertionError(f"{surface_id} does not prefer/allow the first-class rotating-utube host")

    print(json.dumps({
        "first_class_utube_lab": True,
        "module_id": "rotating-utube",
        "utube_workbench_surfaces": 6,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
