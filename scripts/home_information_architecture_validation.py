#!/usr/bin/env python3
"""Validate first-principles Home architecture and shared native discovery wiring."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
ADAPTERS = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_native_workbench_adapters.py"
HOME_LAYOUT = ROOT / "src-tauri" / "resources" / "home_layout.json"
HOME_UI = ROOT / "web" / "home_progressive.js"
WORKBENCH = ROOT / "web" / "surface_catalog.js"
LAUNCHER = ROOT / "web" / "capability_launcher.js"
PREPARE = ROOT / "scripts" / "prepare.py"
DIST_APP = ROOT / "dist" / "app.js"

REQUIRED_TASK_FAMILIES = {"experiment", "measure", "model", "analyze"}
UTUBE_FAMILY = [
    "utube-studio",
    "utube-physical",
    "utube-uncertainty",
    "utube-experiment-planner",
    "utube-advanced",
    "utube-robust",
    "utube-hysteresis",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, marker: str, message: str) -> None:
    if marker not in text:
        fail(message)


def effective_surfaces() -> list[dict]:
    rows = json.loads(read_text(SURFACES))
    spec = importlib.util.spec_from_file_location("_home_native_adapters", ADAPTERS)
    if spec is None or spec.loader is None:
        fail("unable to load native surface extensions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    merge = getattr(module, "merge_native_surface_rows", None)
    return merge(rows) if callable(merge) else rows


def main() -> None:
    surfaces = effective_surfaces()
    surface_ids = {str(row.get("id") or "") for row in surfaces if isinstance(row, dict)}

    layout = json.loads(read_text(HOME_LAYOUT))
    families = layout.get("taskFamilies")
    if not isinstance(families, list):
        fail("home_layout.json taskFamilies must be an array")
    by_id = {str(row.get("id") or ""): row for row in families if isinstance(row, dict)}
    missing_families = sorted(REQUIRED_TASK_FAMILIES - set(by_id))
    if missing_families:
        fail("Home missing task families: " + ", ".join(missing_families))

    referenced: set[str] = set()
    for family_id in REQUIRED_TASK_FAMILIES:
        row = by_id[family_id]
        featured = row.get("featured") or []
        if not isinstance(featured, list) or not featured:
            fail(f"Home task family {family_id} requires non-empty featured capability ids")
        referenced.update(str(x) for x in featured)
    unknown = sorted(item for item in referenced if item not in surface_ids)
    if unknown:
        fail("Home task families reference unknown capabilities: " + ", ".join(unknown))

    featured_families = layout.get("featuredFamilies") or []
    utube = next((row for row in featured_families if isinstance(row, dict) and row.get("id") == "rotating-utube"), None)
    if utube is None:
        fail("Home layout missing rotating-utube featured family")
    if list(utube.get("surfaceIds") or []) != UTUBE_FAMILY:
        fail("rotating-utube featured family must preserve the canonical seven-entry order including Experiment Planner")

    home_ui = read_text(HOME_UI)
    for marker, message in {
        'id="homeTaskGrid"': "Home missing four-intent task grid hook",
        'id="homeContinueContext"': "Home missing Continue/Recent context hook",
        'id="homeFeaturedFamilies"': "Home missing featured experiment family hook",
        'id="homeReadiness"': "Home missing compact readiness hook",
        'data-home-explore-all': "Home missing Explore all capabilities action",
        "renderProgressiveHome": "Home presentation layer lacks deterministic render function",
        "renderUnifiedSearch": "global search has not been upgraded to unified discovery",
        "PhysicalLabCapabilityLauncher": "Home/search do not consume the shared capability launcher",
        "data-search-kind": "unified search results have no actionable discovery rows",
    }.items():
        require(home_ui, marker, message)

    launcher = read_text(LAUNCHER)
    for marker, message in {
        "window.PhysicalLabCapabilityLauncher": "shared capability launcher global is missing",
        "prepareAndOpen": "shared capability launcher cannot prepare/open capabilities",
        "resolveHost": "shared capability launcher lacks host resolution",
        "stopActiveHost": "shared capability launcher lacks active-host cleanup",
        "install_module": "shared capability launcher cannot prepare a missing host Lab",
        "launch_module": "shared capability launcher cannot launch a capability",
        "surface=${encodeURIComponent(id)}": "shared capability launcher does not deep-link capability ids",
    }.items():
        require(launcher, marker, message)

    workbench = read_text(WORKBENCH)
    require(workbench, "PhysicalLabCapabilityLauncher", "Workbench does not use the shared capability launcher")
    require(workbench, "launcher.prepareAndOpen", "Workbench does not delegate opening to the shared launcher")
    if "invoke('install_module'" in workbench or "invoke('launch_module'" in workbench:
        fail("Workbench still duplicates install/launch logic instead of using shared launcher")

    prepare = read_text(PREPARE)
    for marker, message in {
        "home_layout.json": "frontend prepare step does not consume home_layout.json",
        "capability_launcher.js": "frontend prepare step does not bundle shared capability launcher",
        "home_progressive.js": "frontend prepare step does not bundle progressive Home source",
        "__PHYSICAL_LAB_HOME_LAYOUT__": "frontend prepare step does not embed Home layout metadata",
        "merge_native_surface_rows": "frontend prepare step does not apply reviewed native surface extensions",
    }.items():
        require(prepare, marker, message)

    if DIST_APP.exists():
        built = read_text(DIST_APP)
        for marker, message in {
            "window.__PHYSICAL_LAB_HOME_LAYOUT__": "prepared app.js lacks embedded Home layout",
            "window.PhysicalLabCapabilityLauncher": "prepared app.js lacks shared capability launcher",
            "homeTaskGrid": "prepared app.js lacks progressive Home UI",
            "renderUnifiedSearch": "prepared app.js lacks unified discovery",
            "utube-experiment-planner": "prepared app.js lacks focused U-Tube Experiment Planner",
            "radiation-sensitivity": "prepared app.js lacks promoted Radiation Sensitivity surface",
        }.items():
            require(built, marker, message)

    print(json.dumps({
        "task_families": sorted(REQUIRED_TASK_FAMILIES),
        "referenced_capabilities": len(referenced),
        "utube_featured_entries": len(UTUBE_FAMILY),
        "effective_surface_rows": len(surfaces),
        "shared_launcher": True,
        "unified_search": True,
        "home_information_architecture": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
