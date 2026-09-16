#!/usr/bin/env python3
"""Validate that every user-facing Engineering Lab capability is reachable from the native desktop."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
REGISTRY_PATH = UI_ROOT / "physical_lab_surface_registry.py"
CATALOG_PATH = ROOT / "src-tauri" / "resources" / "surfaces.json"
CATALOG_JS_PATH = ROOT / "web" / "surface_catalog.js"
PREPARE_PATH = ROOT / "scripts" / "prepare.py"
DEEP_LINK_PATH = UI_ROOT / "physical_lab_native_surface_entry.py"
SITECUSTOMIZE_PATH = UI_ROOT / "sitecustomize.py"
TAURI_PATH = ROOT / "src-tauri" / "tauri.conf.json"
DIST_APP = ROOT / "dist" / "app.js"

SUPPORTED_ROUTE_TARGETS = {
    "utube-studio", "data-bridge", "measurement-registry", "betterboard-inbox",
    "research-notebook", "reproducibility-pack", "openguin-advisory", "project-workspace",
}
VALID_LAUNCH_MODES = {"direct", "profile", "route", "embedded"}
VALID_ARGUMENT_MODES = {
    "st_profile", "st_profile_project", "st_project_profile", "st_project_profile_refs",
    "st_profile_namespace", "st_namespace", "native_route",
}
UTUBE_FAMILY_IDS = (
    "utube-studio", "utube-physical", "utube-uncertainty",
    "utube-advanced", "utube-robust", "utube-hysteresis",
)


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


def renderer_args(path: Path, callable_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name:
            return [arg.arg for arg in node.args.args]
    return []


def inferred_signature_mode(args: list[str], declared: str) -> str:
    lowered = [name.lower() for name in args]
    if len(lowered) >= 3 and lowered[2] in {"namespace", "ns"}:
        return "st_profile_namespace"
    if len(lowered) == 2 and lowered[1] in {"namespace", "ns"}:
        return "st_namespace"
    return declared


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

    missing_utube = [item for item in UTUBE_FAMILY_IDS if item not in ids]
    if missing_utube:
        fail("U-Tube experiment family missing native capabilities: " + ", ".join(missing_utube))

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

    normalized_signature_rows: list[str] = []
    for row in catalog:
        item_id = str(row.get("id") or "")
        category = str(row.get("category") or "")
        launch_mode = str(row.get("launchMode") or "")
        argument_mode = str(row.get("argumentMode") or "")
        profiles = [str(x) for x in (row.get("profiles") or []) if str(x)]
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
        if launch_mode in {"direct", "profile"} or (launch_mode == "embedded" and argument_mode != "native_route"):
            if not target_module or not target_callable:
                fail(f"capability {item_id} lacks a direct-render target")
            module_path = UI_ROOT / f"{target_module}.py"
            if not module_path.exists():
                fail(f"capability {item_id} target module does not exist: {target_module}")
            args = renderer_args(module_path, target_callable)
            if not args:
                fail(f"capability {item_id} target callable does not exist: {target_module}.{target_callable}")
            inferred = inferred_signature_mode(args, argument_mode)
            if inferred != argument_mode:
                normalized_signature_rows.append(f"{item_id}:{argument_mode}->{inferred}")
        if launch_mode == "route" or argument_mode == "native_route":
            if route_target not in SUPPORTED_ROUTE_TARGETS:
                fail(f"capability {item_id} has unsupported routeTarget {route_target!r}")

    require_markers(
        CATALOG_JS_PATH,
        {
            "data-view=\"capabilities\"": "Workbench does not create a native sidebar entry",
            "capabilitiesView": "Workbench does not create the native capabilities view",
            "__PHYSICAL_LAB_SURFACES__": "Workbench does not consume the canonical embedded surface catalog",
            "module_statuses": "Workbench does not inspect host readiness",
            "install_module": "Workbench cannot prepare a missing host Lab",
            "launch_module": "Workbench cannot launch a capability",
            "surface=${encodeURIComponent(id)}": "Workbench does not deep-link the requested surface into the iframe URL",
            "data-surface-open": "Workbench has no actionable capability controls",
            "showWorkbench": "Workbench navigation does not activate its injected native view",
            "backFromLab": "Workbench-launched hosts are not cleaned up on return",
            "UTUBE_PRIORITY": "Workbench does not explicitly prioritize the U-Tube experiment family",
            "utubeFamilyGrid": "Workbench lacks a featured U-Tube experiment family surface",
            "sortSurfacesForWorkbench": "Workbench does not deterministically sort featured capabilities",
        },
    )
    require_markers(
        PREPARE_PATH,
        {
            "surfaces.json": "frontend prepare step does not consume surfaces.json",
            "surface_catalog.js": "frontend prepare step does not bundle Workbench source",
            "__PHYSICAL_LAB_SURFACES__": "frontend prepare step does not embed native catalog JSON",
        },
    )
    require_markers(
        DEEP_LINK_PATH,
        {
            'query_params.get("surface"': "Streamlit deep-link entry does not consume iframe surface query",
            "render_requested_surface": "Streamlit deep-link entry lacks requested-surface renderer",
            "native_route": "Streamlit deep-link entry lacks route dispatch",
            "_renderer_signature_mode": "Streamlit deep-link entry does not normalize legacy renderer signatures",
            "inspect.signature": "Streamlit deep-link entry does not inspect real renderer signatures",
            "st_profile_namespace": "Streamlit deep-link entry lacks namespace-aware child dispatch",
            "if requested:": "Desktop deep-link does not enter focused requested-workspace mode",
            "original(namespace)": "Normal Lab sessions no longer fall back to the existing advanced stack",
        },
    )
    require_markers(
        SITECUSTOMIZE_PATH,
        {"physical_lab_native_surface_entry": "sitecustomize does not install native surface entry patch"},
    )
    require_markers(
        TAURI_PATH,
        {
            '"resources/surfaces.json": "surfaces.json"': "tauri.conf.json does not bundle surfaces.json",
            '"resources/ui/physical_lab_native_surface_entry.py"': "tauri.conf.json does not bundle native surface entry module",
        },
    )
    if DIST_APP.exists():
        require_markers(
            DIST_APP,
            {
                "Native Engineering Workbench": "prepared app.js lacks Workbench bundle",
                "window.__PHYSICAL_LAB_SURFACES__": "prepared app.js lacks embedded surface catalog",
                "data-surface-open": "prepared app.js lacks capability actions",
                "utubeFamilyGrid": "prepared app.js lacks featured U-Tube family UI",
            },
        )

    print(json.dumps({
        "registry_surfaces": len(registry_surfaces),
        "embedded_ui_modules": len(embedded_modules),
        "native_catalog_rows": len(catalog),
        "utube_family_capabilities": len(UTUBE_FAMILY_IDS),
        "signature_normalized_rows": normalized_signature_rows,
        "uncovered_registry_surfaces": 0,
        "uncovered_embedded_modules": 0,
        "native_desktop_reachability": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
