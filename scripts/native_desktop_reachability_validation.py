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
ADAPTERS_PATH = UI_ROOT / "physical_lab_native_workbench_adapters.py"
CATALOG_JS_PATH = ROOT / "web" / "surface_catalog.js"
LAUNCHER_JS_PATH = ROOT / "web" / "capability_launcher.js"
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
    "utube-studio", "utube-physical", "utube-uncertainty", "utube-experiment-planner",
    "utube-advanced", "utube-robust", "utube-hysteresis",
)
CORE_PLATFORM_IDS = (
    "application-scenarios", "compute-workspace", "diagnostics-workspace",
    "measurement-registry", "model-campaign", "model-engineering",
    "engineering-design-workflow",
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


def _merge_surface_rows(rows: list[dict]) -> list[dict]:
    spec = importlib.util.spec_from_file_location("_native_workbench_adapters_reachability", ADAPTERS_PATH)
    if spec is None or spec.loader is None:
        fail("could not load reviewed native surface extensions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    merge = getattr(module, "merge_native_surface_rows", None)
    return merge(rows) if callable(merge) else rows


def read_base_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        fail("missing native surface catalog: src-tauri/resources/surfaces.json")
    value = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        fail("native surface catalog must be a non-empty JSON array")
    if not all(isinstance(row, dict) for row in value):
        fail("every native surface catalog entry must be an object")
    return value


def read_catalog() -> list[dict]:
    return _merge_surface_rows(read_base_catalog())


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

    base_catalog = read_base_catalog()
    catalog = _merge_surface_rows(base_catalog)
    ids = [str(row.get("id") or "") for row in catalog]
    if any(not item for item in ids):
        fail("every native catalog row requires a non-empty id")
    if len(ids) != len(set(ids)):
        fail("native surface ids must be unique")

    missing_utube = [item for item in UTUBE_FAMILY_IDS if item not in ids]
    if missing_utube:
        fail("U-Tube experiment family missing native capabilities: " + ", ".join(missing_utube))
    missing_core = [item for item in CORE_PLATFORM_IDS if item not in ids]
    if missing_core:
        fail("core engineering platform missing native capabilities: " + ", ".join(missing_core))
    for promoted in ("radiation-sensitivity",):
        if promoted not in ids:
            fail(f"promoted buried workspace missing native capability: {promoted}")

    by_source = {str(row.get("sourceSurfaceId") or ""): row for row in catalog if row.get("sourceSurfaceId")}
    missing_registry = sorted(str(surface.surface_id) for surface in registry_surfaces if str(surface.surface_id) not in by_source)
    if missing_registry:
        fail("Surface Registry entries missing native desktop rows: " + ", ".join(missing_registry))

    # Base target associations remain evidence for embedded child ownership even
    # when an effective row is wrapped by a native prerequisite adapter.
    embedded_coverage = {
        str(row.get("targetModule") or "")
        for row in (base_catalog + catalog)
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

    if normalized_signature_rows:
        fail("effective native catalog contains stale argumentMode declarations: " + ", ".join(normalized_signature_rows))

    require_markers(CATALOG_JS_PATH, {
        "data-view=\"capabilities\"": "Workbench does not create a native sidebar entry",
        "capabilitiesView": "Workbench does not create the native capabilities view",
        "PhysicalLabCapabilityLauncher": "Workbench does not consume the shared capability launcher",
        "launcher.prepareAndOpen": "Workbench cannot launch through the shared capability launcher",
        "data-surface-open": "Workbench has no actionable capability controls",
        "showWorkbench": "Workbench navigation does not activate its injected native view",
        "UTUBE_PRIORITY": "Workbench does not explicitly prioritize the U-Tube experiment family",
        "utubeFamilyGrid": "Workbench lacks a featured U-Tube experiment family surface",
        "CORE_PLATFORM_PRIORITY": "Workbench does not explicitly prioritize recovered core workspaces",
        "corePlatformGrid": "Workbench lacks a featured core engineering platform surface",
        "renderCorePlatform": "Workbench does not render recovered core workspaces as a focused section",
        "sortSurfacesForWorkbench": "Workbench does not deterministically sort featured capabilities",
    })
    require_markers(LAUNCHER_JS_PATH, {
        "module_statuses": "shared capability launcher does not inspect host readiness",
        "install_module": "shared capability launcher cannot prepare a missing host Lab",
        "launch_module": "shared capability launcher cannot launch a capability",
        "stop_module": "shared capability launcher cannot clean up active hosts",
        "surface=${encodeURIComponent(id)}": "shared capability launcher does not deep-link the requested surface",
        "window.PhysicalLabCapabilityLauncher": "shared capability launcher is not exported",
    })
    require_markers(PREPARE_PATH, {
        "surfaces.json": "frontend prepare step does not consume surfaces.json",
        "surface_catalog.js": "frontend prepare step does not bundle Workbench source",
        "capability_launcher.js": "frontend prepare step does not bundle shared launcher source",
        "__PHYSICAL_LAB_SURFACES__": "frontend prepare step does not embed native catalog JSON",
        "merge_native_surface_rows": "frontend prepare step does not apply reviewed native surface extensions",
    })
    require_markers(DEEP_LINK_PATH, {
        'query_params.get("surface"': "Streamlit deep-link entry does not consume iframe surface query",
        "render_requested_surface": "Streamlit deep-link entry lacks requested-surface renderer",
        "native_route": "Streamlit deep-link entry lacks route dispatch",
        "merge_native_surface_rows": "Streamlit deep-link entry does not load effective reviewed surface metadata",
        "_renderer_signature_mode": "Streamlit deep-link entry lacks defensive signature compatibility",
        "st_profile_namespace": "Streamlit deep-link entry lacks namespace-aware child dispatch",
        "if requested:": "Desktop deep-link does not enter focused requested-workspace mode",
        "original(namespace)": "Normal Lab sessions no longer fall back to the existing advanced stack",
    })
    require_markers(SITECUSTOMIZE_PATH, {"physical_lab_native_surface_entry": "sitecustomize does not install native surface entry patch"})
    require_markers(TAURI_PATH, {
        '"resources/surfaces.json": "surfaces.json"': "tauri.conf.json does not bundle surfaces.json",
        '"resources/ui/physical_lab_native_surface_entry.py"': "tauri.conf.json does not bundle native surface entry module",
        '"resources/ui/physical_lab_native_workbench_adapters.py"': "tauri.conf.json does not bundle native Workbench adapters",
    })
    if DIST_APP.exists():
        require_markers(DIST_APP, {
            "Native Engineering Workbench": "prepared app.js lacks Workbench bundle",
            "window.__PHYSICAL_LAB_SURFACES__": "prepared app.js lacks embedded surface catalog",
            "window.PhysicalLabCapabilityLauncher": "prepared app.js lacks shared capability launcher",
            "data-surface-open": "prepared app.js lacks capability actions",
            "utubeFamilyGrid": "prepared app.js lacks featured U-Tube family UI",
            "corePlatformGrid": "prepared app.js lacks featured core engineering platform UI",
            "utube-experiment-planner": "prepared app.js lacks promoted U-Tube Experiment Planner",
            "radiation-sensitivity": "prepared app.js lacks promoted Radiation Sensitivity",
        })

    print(json.dumps({
        "registry_surfaces": len(registry_surfaces),
        "embedded_ui_modules": len(embedded_modules),
        "native_catalog_rows": len(catalog),
        "utube_family_capabilities": len(UTUBE_FAMILY_IDS),
        "core_platform_capabilities": len(CORE_PLATFORM_IDS),
        "signature_normalized_rows": [],
        "uncovered_registry_surfaces": 0,
        "uncovered_embedded_modules": 0,
        "shared_native_launcher": True,
        "native_desktop_reachability": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
