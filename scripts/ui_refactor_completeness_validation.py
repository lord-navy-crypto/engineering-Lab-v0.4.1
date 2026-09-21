#!/usr/bin/env python3
"""Regression contract for the PR #91 UI/visualization reconstruction.

This protects user-visible capabilities and behavior that existed before the
refactor baseline 4342087a731ed932c4bb8fa8117ca4562a89e209 while allowing the
presentation hierarchy to evolve.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"

def read(name: str) -> str:
    path = UI / name
    assert path.is_file(), f"missing UI module: {name}"
    return path.read_text(encoding="utf-8")

advanced = read("physical_lab_advanced.py")
engineering = read("physical_lab_engineering.py")
frequency = read("physical_lab_frequency_response_ui.py")
undulator = read("physical_lab_undulator_spectrum_ui.py")
digital = read("physical_lab_digital_twin_ui.py")
kerr = read("physical_lab_kerr_ui.py")
solar = read("physical_lab_solar_system_ui.py")
lattice = read("physical_lab_lattice_ui.py")
visualization = read("physical_lab_visualization.py")
engineering_viz = read("physical_lab_visualization_engineering.py")
project_patch = read("physical_lab_project_surface_patch.py")
ui_system = read("physical_lab_ui_system.py")
builtin_entry = read("physical_lab_builtin_lab_entry.py")

# 1. Research Workbench top-level capabilities.
for label in ["Science", "Engineering", "Validation", "Assistant", "Runs"]:
    assert label in advanced, f"Research Workbench lost {label}"
for token in [
    "render_engineering_vvuq(st, profile, namespace)",
    "render_digital_twin_workspace(st, profile)",
    "render_radia_forward_workspace(st, namespace)",
    "render_radia_tolerance_workspace(st, namespace)",
    "render_radia_radiation_propagation(st, namespace)",
    "render_local_ai_assistant(st, profile, namespace)",
    "_render_run_vault(st, profile)",
]:
    assert token in advanced, f"Research Workbench lost behavior: {token}"

# 2. Every engineering renderer that existed before PR #91 must still be
# reachable from the focused Engineering workspace.
engineering_capabilities = [
    "Kerr geodesic dynamics",
    "Kerr experiment / compute workflow",
    "Sun–Jupiter–Saturn dynamics",
    "Kerr shadow morphology",
    "Multilayer honeycomb lattice",
    "Advanced model science",
    "Model depth",
    "Model depth IV · numerical structure",
    "Model depth VII–IX · inverse, signals & control",
    "Model depth V",
    "Model depth VI",
    "Undulator spectrum & beam broadening",
    "Trajectory radiation & Stokes map",
    "Radiation quality degradation",
    "Nominal vs seed radiation map",
    "Deep science studio",
    "Frequency response",
    "Model refinement",
    "Physics application",
    "Engineering uncertainty & requirements",
    "Measurement & calibration evidence",
    "Engineering scenario review",
    "Project & evidence workspace",
    "Research orchestrator",
    "Run & Diagnostics Log",
]
for label in engineering_capabilities:
    assert label in engineering, f"Engineering capability lost: {label}"

renderer_tokens = [
    "render_kerr_geodesic_workspace",
    "render_kerr_platform_workspace",
    "render_solar_system_workspace",
    "render_kerr_shadow_morphology_workspace",
    "render_lattice_workspace",
    "render_remaining_science_workspace",
    "render_model_depth_workspace",
    "render_model_depth_iv_workspace",
    "render_model_depth_vii_workspace",
    "render_model_depth_v_workspace",
    "render_model_depth_vi_workspace",
    "render_undulator_spectrum_workspace",
    "render_radiation_stokes_workspace",
    "render_radiation_quality_workspace",
    "render_seed_radiation_comparison",
    "render_deep_science_workspace",
    "render_frequency_response_workspace",
    "render_new_model_refinement_workspace",
    "render_application_mode",
    "_render_engineering_vvuq_legacy",
    "render_measurement_workspace",
    "render_engineering_scenario_review",
    "render_project_workspace",
    "render_research_orchestrator",
    "render_diagnostics_workspace",
]
for token in renderer_tokens:
    assert token in engineering, f"Engineering renderer lost: {token}"

# 3. High-value scientific workspaces retain their actions and numerical calls.
for token in [
    "Run forced-response sweep",
    "Run nonlinear continuation sweep",
    "linear_forced_response_sweep",
    "duffing_frequency_sweep",
    "Setup & run",
    "Numerical verification",
    "Diagnostics",
]:
    assert token in frequency, f"Frequency Response behavior lost: {token}"

for token in [
    "Run harmonic spectrum",
    "Run angular resonance map",
    "Run beam-broadened resonance",
    "Harmonic spectrum",
    "Off-axis resonance",
    "Beam broadening",
]:
    assert token in undulator, f"Undulator behavior lost: {token}"

for token in [
    "Fit calibration",
    "Create calibrated derived dataset",
    "Compare field series",
    "Fit affine discrepancy",
    "Analyze phase space",
    "Rank remeasurement points",
    "fit_linear_calibration",
    "compare_field_series",
    "fit_model_affine",
    "analyze_beam_phase_space",
    "suggest_residual_measurement_points",
]:
    assert token in digital, f"Digital Twin behavior lost: {token}"

for token in [
    "Run Kerr geodesic",
    "Run massive ↔ photon comparison",
    "Run spin sweep",
    "Run refinement audit",
    "Single orbit",
    "Massive ↔ photon",
    "Spin sweep",
    "Numerical verification",
]:
    assert token in kerr, f"Kerr UI behavior lost: {token}"

for token in [
    "Run interactive orbital model",
    "Run finite-time divergence audit",
    "pl_solar_system_result",
    "pl_solar_system_ftle",
    "Setup & run",
    "Results",
    "Sensitivity audit",
    "Analysis & V&V",
    "Campaign / Project",
    "Solver refinement",
    "Inclination sweep",
    "Model-effect audit",
    "Requirement screening",
]:
    assert token in solar, f"Solar UI behavior lost: {token}"

for token in [
    "Run interactive lattice model",
    "Run normal-mode audit",
    "Run Bloch dispersion + DOS",
    "pl_lattice_result",
    "pl_lattice_modes",
    "pl_lattice_phonons",
    "Setup & run",
    "Dynamics results",
    "Modes & phonons",
    "Advanced tools",
]:
    assert token in lattice, f"Lattice UI behavior lost: {token}"

# 4. Visualization controls are progressive, but the underlying controls still
# exist; refactoring must not achieve simplicity by deleting them.
for token in ["Essentials", "Advanced", "Transforms & axes", "Rendering & performance", "visualization_context"]:
    assert token in visualization, f"Visualization control lost: {token}"
for token in ["Engineering overlays", "Review", "Comparison", "3D presentation", "engineering_visualization_context"]:
    assert token in engineering_viz, f"Engineering visualization control lost: {token}"

# 5. Shared visual system is additive and bundled, not a replacement for model
# execution.
for token in ["Physical Lab visual system v3", "def apply_plotly_design", "def render_workbench_header", "def render_stage_rail"]:
    assert token in ui_system, f"Shared UI system incomplete: {token}"
assert "The model workspace renders the visible title/hierarchy" in builtin_entry

# 6. Project/Evidence capability must exist exactly once for workbench profiles,
# while bundled first-class Labs retain a standalone mount. Legacy sync remains
# active for all supported profiles.
for token in [
    "WORKBENCH_PROJECT_PROFILES",
    "STANDALONE_PROJECT_PROFILES",
    "synchronize_legacy_workspaces",
    "LEGACY_SYNC_SESSION_KEY",
]:
    assert token in project_patch, f"Project compatibility behavior lost: {token}"
assert "if profile in STANDALONE_PROJECT_PROFILES:" in project_patch
assert "All Workspaces" in project_patch
assert "utube-studio" in project_patch
assert "render_project_workspace(st, profile, namespace)" in project_patch
assert "Project & evidence workspace" in engineering

# 7. All managed Lab profiles remain represented across the workbench /
# standalone Project surface contract, including the restored first-class U-Tube.
profiles = [
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radia-magnet-studio",
    "radiation-platform",
    "kerr-geodesics",
    "solar-system-dynamics",
    "honeycomb-lattice",
    "utube-rotation",
]
combined = advanced + engineering + project_patch + builtin_entry
for profile in profiles:
    assert profile in combined, f"Managed profile lost from UI routing: {profile}"

# 8. First-class bundled model routing must not regress to hidden legacy-host-only profiles.
surface_registry = read("physical_lab_surface_registry.py")
for token in [
    'profile not in {"nonlinear-chaos", "solar-system-dynamics"}',
    '"Analysis & V&V"',
    '"Campaign / Project"',
]:
    assert token in solar, f"Solar first-class routing/analysis lost: {token}"
for token in [
    'profile not in {PROFILE, "kerr-geodesics"}',
]:
    assert token in kerr, f"Kerr first-class routing lost: {token}"
for token in [
    'profile not in {"oscillation-integration", "honeycomb-lattice"}',
]:
    assert token in lattice, f"Lattice first-class routing lost: {token}"
for token in [
    '"Solar-system workspace"',
    '"Orbital Dynamics"',
    '"Refinement & Resonance"',
    '"Kerr workspace"',
    '"Lattice workspace"',
    '"U-Tube workspace"',
]:
    assert token in builtin_entry, f"First-class bundled workspace selector lost: {token}"
for token in [
    'profiles=("nonlinear-chaos", "solar-system-dynamics")',
    'profiles=("nonlinear-chaos", "kerr-geodesics")',
    'profiles=("oscillation-integration", "honeycomb-lattice")',
    '"U-Tube Hysteresis & Dynamics"',
    '"U-Tube Robust Design & Digital Twin"',
]:
    assert token in surface_registry, f"Capability registry first-class route lost: {token}"

print("Engineering Lab PR #91 UI refactor completeness: PASS")
print(f"- protected Engineering capabilities: {len(engineering_capabilities)}")
print(f"- protected renderer routes: {len(renderer_tokens)}")
print("- Science / Engineering / Validation / Assistant / Runs preserved")
print("- Frequency Response / Undulator / Digital Twin / Kerr / Solar / Lattice behaviors preserved")
print("- Model Depth IV and VII–IX remain directly reachable from Engineering → Analysis")
print("- visualization controls preserved under progressive disclosure")
print("- Project/Evidence duplicate removed without losing legacy sync or bundled-Lab access")
