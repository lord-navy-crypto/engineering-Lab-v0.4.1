#!/usr/bin/env python3
"""Validate first-principles Home architecture and shared native discovery wiring."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
HOME_LAYOUT = ROOT / "src-tauri" / "resources" / "home_layout.json"
INDEX = ROOT / "web" / "index.html"
APP = ROOT / "web" / "app.js"
WORKBENCH = ROOT / "web" / "surface_catalog.js"
LAUNCHER = ROOT / "web" / "capability_launcher.js"
PREPARE = ROOT / "scripts" / "prepare.py"

REQUIRED_TASK_FAMILIES = {"experiment", "measure", "model", "analyze"}
UTUBE_FAMILY = [
    "utube-studio",
    "utube-physical",
    "utube-uncertainty",
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


def main() -> None:
    surfaces = json.loads(read_text(SURFACES))
    surface_ids = {str(row.get("id") or "") for row in surfaces if isinstance(row, dict)}

    if not HOME_LAYOUT.exists():
        fail("missing native Home layout metadata: src-tauri/resources/home_layout.json")
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
        fail("rotating-utube featured family must preserve the canonical six-entry order")

    index = read_text(INDEX)
    for marker, message in {
        'id="homeTaskGrid"': "Home missing four-intent task grid hook",
        'id="homeContinueContext"': "Home missing Continue/Recent context hook",
        'id="homeFeaturedFamilies"': "Home missing featured experiment family hook",
        'id="homeReadiness"': "Home missing compact readiness hook",
        'data-home-explore-all': "Home missing Explore all capabilities action",
    }.items():
        require(index, marker, message)

    launcher = read_text(LAUNCHER)
    for marker, message in {
        "window.PhysicalLabCapabilityLauncher": "shared capability launcher global is missing",
        "prepareAndOpen": "shared capability launcher cannot prepare/open capabilities",
        "resolveHost": "shared capability launcher lacks host resolution",
        "stopActiveHost": "shared capability launcher lacks active-host cleanup",
    }.items():
        require(launcher, marker, message)

    workbench = read_text(WORKBENCH)
    require(workbench, "PhysicalLabCapabilityLauncher.prepareAndOpen", "Workbench does not use the shared capability launcher")
    if "invoke('install_module'" in workbench or "invoke('launch_module'" in workbench:
        fail("Workbench still duplicates install/launch logic instead of using shared launcher")

    app = read_text(APP)
    require(app, "PhysicalLabCapabilityLauncher.prepareAndOpen", "Home/search do not use the shared capability launcher")
    require(app, "__PHYSICAL_LAB_HOME_LAYOUT__", "native app does not consume embedded Home layout metadata")
    require(app, "renderUnifiedSearch", "global search has not been upgraded to unified discovery")

    prepare = read_text(PREPARE)
    require(prepare, "home_layout.json", "frontend prepare step does not consume home_layout.json")
    require(prepare, "capability_launcher.js", "frontend prepare step does not bundle shared capability launcher")
    require(prepare, "__PHYSICAL_LAB_HOME_LAYOUT__", "frontend prepare step does not embed Home layout metadata")

    print(json.dumps({
        "task_families": sorted(REQUIRED_TASK_FAMILIES),
        "referenced_capabilities": len(referenced),
        "utube_featured_entries": len(UTUBE_FAMILY),
        "shared_launcher": True,
        "unified_search": True,
        "home_information_architecture": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
