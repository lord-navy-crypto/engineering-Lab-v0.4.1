#!/usr/bin/env python3
"""Contract for first-class scientific Labs bundled with Engineering Lab."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"

BUNDLED = {
    "kerr-geodesics": {
        "name": "Kerr Black Hole Geodesics",
        "category": "Relativity & Astrophysics",
        "repo": "lord-navy-crypto/Physical-Lab-v0.4.1",
        "files": ("physical_lab_kerr_geodesics.py", "physical_lab_kerr_ui.py"),
        "validation": "kerr_geodesic_validation.py",
    },
    "solar-system-dynamics": {
        "name": "Sun–Jupiter–Saturn Dynamics",
        "category": "Computational Astrophysics",
        "repo": "lord-navy-crypto/Physical-Lab-v0.4.1",
        "files": ("physical_lab_solar_system_dynamics.py", "physical_lab_solar_system_ui.py"),
        "validation": "solar_system_dynamics_validation.py",
    },
    "honeycomb-lattice": {
        "name": "Multilayer Honeycomb Lattice",
        "category": "Materials & Condensed Matter",
        "repo": "lord-navy-crypto/Physical-Lab-v0.4.1",
        "files": ("physical_lab_lattice_dynamics.py", "physical_lab_lattice_ui.py"),
        "validation": "honeycomb_lattice_validation.py",
    },
    "rotating-utube": {
        "name": "Rotating U-Tube Research Studio",
        "category": "Fluid Dynamics & Experimental Physics",
        "repo": "lord-navy-crypto/engineering-Lab-v0.4.1",
        "files": (
            "physical_lab_utube_experiment_ui.py",
            "physical_lab_utube_uncertainty_ui.py",
            "physical_lab_utube_advanced_ui.py",
            "physical_lab_utube_robust_ui.py",
            "physical_lab_utube_hysteresis_ui.py",
        ),
        "validation": "utube_first_class_lab_validation.py",
    },
}

ORIGINAL_EXTERNAL_LABS = {
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radia-magnet-studio",
    "radiation-platform",
}


def main() -> int:
    modules = json.loads((ROOT / "src-tauri" / "resources" / "modules.json").read_text(encoding="utf-8"))
    labs = [m for m in modules if m.get("kind") == "lab"]
    runtimes = [m for m in modules if m.get("kind") == "runtime"]
    assert len(modules) == 14, len(modules)
    assert len(labs) == 11, len(labs)
    assert len(runtimes) == 3, len(runtimes)
    assert {m["id"] for m in labs if not m.get("bundled", False)} == ORIGINAL_EXTERNAL_LABS
    assert {m["id"] for m in labs if m.get("bundled", False)} == set(BUNDLED)

    available = {p.name for p in UI.iterdir()}
    for module_id, expected in BUNDLED.items():
        row = next(m for m in labs if m["id"] == module_id)
        assert row["name"] == expected["name"]
        assert row["category"] == expected["category"]
        assert row["repo"] == expected["repo"]
        assert row["branch"] == "main"
        assert row.get("revision") in {None, ""}, "bundled app source must not masquerade as a downloaded pinned repo revision"
        assert row["entrypoint"] == "app.py"
        assert row["requirements"] == "requirements.txt"
        assert row["safeBackend"] == "standard"
        assert row["fragileDependencies"] == []
        assert row["runtimeRequires"] == []
        assert set(row["supportedArches"]) == {"arm64", "x86_64"}
        for filename in expected["files"]:
            assert filename in available, filename
        assert (ROOT / "scripts" / expected["validation"]).is_file()

    host = (UI / "physical_lab_builtin_lab_entry.py").read_text(encoding="utf-8")
    for module_id in BUNDLED:
        assert module_id in host
    for marker in (
        "render_kerr_geodesic_workspace",
        "render_kerr_platform_workspace",
        "render_solar_system_workspace",
        "render_lattice_workspace",
        "render_new_model_refinement_for_variant",
        "render_utube_experiment",
        "render_utube_uncertainty",
        "render_utube_advanced",
        "render_project_workspace",
    ):
        assert marker in host, marker
    assert "usability_score" not in host

    refinement_ui = (UI / "physical_lab_new_model_refinement_ui.py").read_text(encoding="utf-8")
    assert "def render_new_model_refinement_for_variant" in refinement_ui
    for marker in ("KERR_VARIANT", "SOLAR_VARIANT", "LATTICE_VARIANT"):
        assert marker in refinement_ui

    # Bundled installation is deliberately generic: new bundled Labs must not
    # require a Rust per-profile branch or a network checkout.
    lib = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    for marker in (
        "bundled: bool",
        "fn prepare_bundled_lab_source",
        "if spec.bundled",
        "physical_lab_builtin_lab_entry.py",
        "physical_lab_builtin_requirements.txt",
    ):
        assert marker in lib, marker
    prep = lib.split("fn prepare_bundled_lab_source", 1)[1].split("async fn", 1)[0]
    assert "codeload.github.com" not in prep
    assert "fs::copy" in prep
    assert "physical-lab-bundled-source-v1" in prep

    # The three historical bundled numerical models still own dedicated native
    # smoke scripts. U-Tube has its separate first-class UI/reachability contract.
    runtime_support = (ROOT / "src-tauri" / "src" / "research_runtime_support.rs").read_text(encoding="utf-8")
    for marker in (
        '"kerr-geodesics"=>',
        '"solar-system-dynamics"=>',
        '"honeycomb-lattice"=>',
        'command.env("PYTHONPATH",ui)',
        "No scientific smoke script registered",
    ):
        assert marker in runtime_support, marker

    tauri = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resources = (tauri.get("bundle") or {}).get("resources") or {}
    for resource in (
        "resources/ui/physical_lab_builtin_lab_entry.py",
        "resources/ui/physical_lab_builtin_requirements.txt",
        "resources/ui/physical_lab_utube_experiment_ui.py",
        "resources/ui/physical_lab_utube_uncertainty_ui.py",
        "resources/ui/physical_lab_utube_advanced_ui.py",
        "resources/ui/physical_lab_utube_robust_ui.py",
        "resources/ui/physical_lab_utube_hysteresis_ui.py",
    ):
        assert resource in resources, resource

    self_check = (ROOT / "scripts" / "self_check.py").read_text(encoding="utf-8")
    assert "Modules: 14 (11 labs + 3 runtime/builders)" in self_check
    assert "Top-level Labs: 11" in self_check

    print("Bundled first-class model Labs: PASS")
    print("- catalog: 11 Labs + 3 runtimes")
    print("- Kerr / Solar / Honeycomb / Rotating U-Tube use packaged scientific UI/model modules")
    print("- installation path creates an isolated environment without external solver download")
    print("- shared Project / Evidence surface remains available outside focused Workbench deep-links")
    print("Boundary: launcher/product identity changes do not alter equations or imply experimental validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
