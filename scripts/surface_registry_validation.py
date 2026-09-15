#!/usr/bin/env python3
"""Validate that Engineering Lab user-facing surfaces are discoverable and bundled."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
REGISTRY_PATH = UI_ROOT / "physical_lab_surface_registry.py"
DESKTOP_SURFACE = UI_ROOT / "physical_lab_project_surface_patch.py"
TAURI = ROOT / "src-tauri" / "tauri.conf.json"


def fail(message: str) -> None:
    raise AssertionError(message)


def load_registry():
    if not REGISTRY_PATH.exists():
        fail("missing physical_lab_surface_registry.py")
    spec = importlib.util.spec_from_file_location("physical_lab_surface_registry", REGISTRY_PATH)
    if spec is None or spec.loader is None:
        fail("could not load surface registry spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    desktop_text = DESKTOP_SURFACE.read_text(encoding="utf-8")
    required_wiring = {
        '"All Workspaces"': "desktop surface does not expose All Workspaces",
        "physical_lab_surface_registry": "desktop surface is not wired to surface registry",
        "_render_all_workspaces": "desktop surface does not render the All Workspaces catalog",
        "render_project_workspace": "desktop surface lost Project Kernel wiring",
        "render_project_interop": "desktop surface lost Project Workspace wiring",
        '"Engineering Lab navigator"': "desktop surface lacks the top-level workspace navigator",
    }
    for marker, error in required_wiring.items():
        if marker not in desktop_text:
            fail(error)

    registry = load_registry()
    surfaces = list(getattr(registry, "SURFACES", ()))
    if not surfaces:
        fail("surface registry is empty")

    ids = [str(row.surface_id) for row in surfaces]
    if len(ids) != len(set(ids)):
        fail("surface ids must be unique")

    direct_modules = set(getattr(registry, "DIRECT_UI_MODULES", ()))
    classified_modules = set(getattr(registry, "CLASSIFIED_UI_MODULES", ()))
    if not direct_modules.issubset(classified_modules):
        fail("all direct UI modules must be classified")

    packaged_ui_modules = {
        path.stem
        for path in UI_ROOT.glob("physical_lab_*_ui.py")
        if path.is_file()
    }
    missing = sorted(packaged_ui_modules - classified_modules)
    if missing:
        fail("unclassified user-facing UI module(s): " + ", ".join(missing))

    extra = sorted(classified_modules - packaged_ui_modules)
    if extra:
        fail("registry classifies missing UI module(s): " + ", ".join(extra))

    tauri_text = TAURI.read_text(encoding="utf-8")
    if "physical_lab_surface_registry.py" not in tauri_text:
        fail("surface registry is not bundled by tauri.conf.json")

    for module_name in sorted(classified_modules):
        filename = module_name + ".py"
        if filename not in tauri_text:
            fail(f"classified UI module is not bundled: {filename}")

    for row in surfaces:
        if row.category not in getattr(registry, "CATEGORIES", ()):
            fail(f"surface {row.surface_id} has unknown category {row.category!r}")
        if row.launch_mode not in {"direct", "route", "profile", "embedded"}:
            fail(f"surface {row.surface_id} has unsupported launch mode {row.launch_mode!r}")
        if row.launch_mode == "direct":
            if not row.module or not row.callable_name:
                fail(f"direct surface {row.surface_id} lacks module/callable")
            module_path = UI_ROOT / f"{row.module}.py"
            if not module_path.exists():
                fail(f"direct surface module missing: {row.module}")
            source = module_path.read_text(encoding="utf-8")
            marker = f"def {row.callable_name}("
            if marker not in source:
                fail(f"direct renderer missing: {row.module}.{row.callable_name}")

    required_ids = {
        "utube-studio",
        "utube-physical",
        "utube-uncertainty",
        "utube-advanced",
        "visualization-studio",
        "visual-analytics",
        "applied-analysis",
        "advanced-applied-analysis",
        "deep-applied-math",
        "science-analysis",
        "run-comparison",
        "model-coupling",
        "pipeline-dag",
        "engineering-decisions",
        "operations-planning",
        "quality-reliability",
        "risk-economics",
        "requirements-verification",
        "digital-twin",
        "research-orchestrator",
        "evidence-center",
        "kerr-geodesics",
        "solar-system",
        "lattice-dynamics",
        "undulator-spectrum",
        "radiation-stokes",
    }
    missing_required = sorted(required_ids - set(ids))
    if missing_required:
        fail("major workspace(s) absent from registry: " + ", ".join(missing_required))

    print(
        json.dumps(
            {
                "surface_count": len(surfaces),
                "classified_ui_modules": len(classified_modules),
                "direct_ui_modules": len(direct_modules),
                "profile_scoped_surfaces": sum(1 for row in surfaces if row.launch_mode == "profile"),
                "orphan_ui_modules": 0,
                "desktop_catalog_wired": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
