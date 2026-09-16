#!/usr/bin/env python3
"""Validate that every user-facing Engineering Lab capability is reachable from the native desktop."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
REGISTRY_PATH = UI_ROOT / "physical_lab_surface_registry.py"
CATALOG_PATH = ROOT / "src-tauri" / "resources" / "surfaces.json"
INDEX_PATH = ROOT / "web" / "index.html"
CATALOG_JS_PATH = ROOT / "web" / "surface_catalog.js"
LIB_PATH = ROOT / "src-tauri" / "src" / "lib.rs"
SITECUSTOMIZE_PATH = UI_ROOT / "sitecustomize.py"
TAURI_PATH = ROOT / "src-tauri" / "tauri.conf.json"

SUPPORTED_ROUTE_TARGETS = {
    "utube-studio",
    "data-bridge",
    "measurement-registry",
    "betterboard-inbox",
    "research-notebook",
    "reproducibility-pack",
    "openguin-advisory",
    "project-workspace",
}
VALID_LAUNCH_MODES = {"direct", "profile", "route", "embedded"}
VALID_ARGUMENT_MODES = {
    "st_profile",
    "st_profile_project",
    "st_project_profile",
    "st_project_profile_refs",
    "st_profile_namespace",
    "native_route",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_registry():
    spec = importlib.util.spec_from_file_location("physical_lab_surface_registry", REGISTRY_PATH)
    if spec is None or spec.loader is None:
        fail("could not load Surface Registry")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        fail("missing native surface catalog: src-tauri/resources/surfaces.json")
    value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        fail("native surface catalog must be a non-empty JSON array")
    if not all(isinstance(row, dict) for row in value):
        fail("every native surface catalog entry must be an object")
    return value


def require_markers(path: Path, markers: dict[str, str]) -> None:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    for marker, error in markers.items():
        if marker not in text:
            fail(error)


def main() -> None:
    registry = load_registry()
    registry_surfaces = list(getattr(registry, "SURFACES", ()))
    embedded_modules = set(getattr(registry, "EMBEDDED_UI_MODULES", ()))
    categories = set(getattr(registry, "CATEGORIES", ()))
    if not registry_surfaces:
        fail("Surface Registry is empty")
    if not embedded_modules:
        fail("embedded UI classification is empty")

    catalog = read_catalog()
    ids = [str(row.get("id") or "") for row in catalog]
    if any(not item for item in ids):
        fail("every native catalog row requires a non-empty id")
    if len(ids) != len(set(ids)):
        fail("native surface ids must be unique")

    by_source = {str(row.get("sourceSurfaceId") or ""): row for row in catalog if row.get("sourceSurfaceId")}
    missing_registry = sorted(str(surface.surface_id) for surface in registry_surfaces if str(surface.surface_id) not in by_source)
    if missing_registry:
        fail("Surface Registry entries missing native desktop rows: " + ", ".join(missing_registry))

    embedded_coverage = {
        str(row.get("targetModule") or "")
        for row in catalog
        if row.get("kind") == "embedded" and row.get("targetModule")
    }
    missing_embedded = sorted(embedded_modules - embedded_coverage)
    if missing_embedded:
        fail("embedded UI modules missing native child capabilities: " + ", ".join(missing_embedded))

    for row in catalog:
        item_id = str(row.get("id") or "")
        category = str(row.get("category") or "")
        launch_mode = str(row.get("launchMode") or "")
        argument_mode = str(row.get("argumentMode") or "")
        profiles = [str(x) for x in (row.get("profiles") or []) if str(x)]
        preferred = [str(x) for x in (row.get("preferredProfiles") or []) if str(x)]
        target_module = str(row.get("targetModule") or "")
        target_callable = str(row.get("targetCallable") or "")
        route_target = str(row.get("routeTarget") or "")

        if category not in categories:
            fail(f"native capability {item_id} has unknown category {category!r}")
        if launch_mode not in VALID_LAUNCH_MODES:
            fail(f"native capability {item_id} has unsupported launchMode {launch_mode!r}")
        if argument_mode not in VALID_ARGUMENT_MODES:
            fail(f"native capability {item_id} has unsupported argumentMode {argument_mode!r}")
        if launch_mode == "profile" and not profiles:
            fail(f"profile capability {item_id} requires at least one legal host profile")
        if preferred and any(profile not in profiles and profiles for profile in preferred):
            fail(f"capability {item_id} has preferredProfiles outside its legal profiles")
        if launch_mode in {"direct", "profile"} or (launch_mode == "embedded" and argument_mode != "native_route"):
            if not target_module or not target_callable:
                fail(f"capability {item_id} lacks a direct-render target")
            module_path = UI_ROOT / f"{target_module}.py"
            if not module_path.exists():
                fail(f"capability {item_id} target module does not exist: {target_module}")
            source = module_path.read_text(encoding="utf-8")
            if f"def {target_callable}(" not in source:
                fail(f"capability {item_id} target callable does not exist: {target_module}.{target_callable}")
        if launch_mode == "route" or argument_mode == "native_route":
            if route_target not in SUPPORTED_ROUTE_TARGETS:
                fail(f"capability {item_id} has unsupported routeTarget {route_target!r}")

    require_markers(
        INDEX_PATH,
        {
            'data-view="capabilities"': "native sidebar lacks Workbench entry",
            'id="capabilitiesView"': "native desktop lacks capabilitiesView",
            'surface_catalog.js': "native desktop does not load surface_catalog.js",
        },
    )
    require_markers(
        CATALOG_JS_PATH,
        {
            "list_surface_catalog": "Workbench does not load native surface catalog",
            "module_statuses": "Workbench does not inspect host readiness",
            "install_module": "Workbench cannot prepare a missing host Lab",
            "launch_module": "Workbench cannot launch a capability",
            "surfaceId": "Workbench does not pass capability deep-link id",
            "data-surface-open": "Workbench has no actionable capability controls",
        },
    )
    require_markers(
        LIB_PATH,
        {
            "struct SurfaceSpec": "Rust backend lacks SurfaceSpec",
            "fn surface_specs()": "Rust backend lacks surfaces.json parser",
            "fn list_surface_catalog": "Rust backend lacks list_surface_catalog command",
            "surface_id: Option<String>": "launch_module lacks optional surface deep-link argument",
            "PHYSICAL_LAB_INITIAL_SURFACE": "launch_module does not export initial surface to Streamlit",
            "list_surface_catalog,": "list_surface_catalog is not registered with Tauri",
        },
    )
    require_markers(
        SITECUSTOMIZE_PATH,
        {
            "physical_lab_native_surface_entry": "sitecustomize does not install native surface entry patch",
        },
    )
    require_markers(
        TAURI_PATH,
        {
            "surfaces.json": "tauri.conf.json does not bundle surfaces.json",
            "physical_lab_native_surface_entry.py": "tauri.conf.json does not bundle native surface entry module",
        },
    )

    print(json.dumps({
        "registry_surfaces": len(registry_surfaces),
        "embedded_ui_modules": len(embedded_modules),
        "native_catalog_rows": len(catalog),
        "uncovered_registry_surfaces": 0,
        "uncovered_embedded_modules": 0,
        "native_desktop_reachability": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
