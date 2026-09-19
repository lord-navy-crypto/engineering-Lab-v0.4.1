"""Compatibility facade for Physical Lab engineering tools.

The original Engineering V&V/UQ implementation is retained in
``physical_lab_engineering_legacy``. This facade inserts project, measurement,
research-orchestration, model-specific, diagnostics and application workspaces
before delegating to the established engineering workflow.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    import physical_lab_engineering_legacy as _legacy
except ModuleNotFoundError:
    _legacy_path = Path(__file__).with_name("physical_lab_engineering_legacy.py")
    _spec = importlib.util.spec_from_file_location("physical_lab_engineering_legacy", _legacy_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Unable to load Physical Lab engineering implementation: {_legacy_path}")
    _legacy = importlib.util.module_from_spec(_spec)
    sys.modules.setdefault("physical_lab_engineering_legacy", _legacy)
    _spec.loader.exec_module(_legacy)

for _name, _value in vars(_legacy).items():
    if not _name.startswith("_") and _name != "render_engineering_vvuq":
        globals()[_name] = _value
_render_engineering_vvuq_legacy = _legacy.render_engineering_vvuq


def _load_module_by_path(module_name: str, filename: str):
    ui_dir = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(module_name, ui_dir / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load Physical Lab module: {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        raise
    return module


def _load(name: str, file: str):
    try:
        return __import__(name)
    except ModuleNotFoundError:
        return _load_module_by_path(name, file)


def _load_project_kernel_module():
    return _load("physical_lab_project_kernel", "physical_lab_project_kernel.py")


def _load_measurement_registry_module():
    return _load("physical_lab_measurement_registry", "physical_lab_measurement_registry.py")


def _load_research_orchestrator_ui_module():
    _load("physical_lab_research_orchestrator", "physical_lab_research_orchestrator.py")
    return _load("physical_lab_research_orchestrator_ui", "physical_lab_research_orchestrator_ui.py")


def _load_diagnostics_module():
    return _load("physical_lab_diagnostics", "physical_lab_diagnostics.py")


def _load_compute_engine_module():
    return _load("physical_lab_compute_engine", "physical_lab_compute_engine.py")


def _load_kerr_ui_module():
    _load("physical_lab_kerr_geodesics", "physical_lab_kerr_geodesics.py")
    return _load("physical_lab_kerr_ui", "physical_lab_kerr_ui.py")


def _load_kerr_platform_ui_module():
    _load("physical_lab_kerr_geodesics", "physical_lab_kerr_geodesics.py")
    _load("physical_lab_experiment_kernel", "physical_lab_experiment_kernel.py")
    _load("physical_lab_kerr_workflow", "physical_lab_kerr_workflow.py")
    return _load("physical_lab_kerr_platform_ui", "physical_lab_kerr_platform_ui.py")


def _load_solar_system_ui_module():
    _load("physical_lab_solar_system_dynamics", "physical_lab_solar_system_dynamics.py")
    _load("physical_lab_experiment_kernel", "physical_lab_experiment_kernel.py")
    _load("physical_lab_solar_system_workflow", "physical_lab_solar_system_workflow.py")
    return _load("physical_lab_solar_system_ui", "physical_lab_solar_system_ui.py")


def _load_lattice_ui_module():
    _load("physical_lab_lattice_dynamics", "physical_lab_lattice_dynamics.py")
    _load("physical_lab_lattice_phonons", "physical_lab_lattice_phonons.py")
    _load("physical_lab_experiment_kernel", "physical_lab_experiment_kernel.py")
    _load("physical_lab_lattice_workflow", "physical_lab_lattice_workflow.py")
    return _load("physical_lab_lattice_ui", "physical_lab_lattice_ui.py")


def _load_new_model_refinement_ui_module():
    _load("physical_lab_new_model_refinements", "physical_lab_new_model_refinements.py")
    return _load("physical_lab_new_model_refinement_ui", "physical_lab_new_model_refinement_ui.py")


def _load_frequency_response_ui_module():
    _load("physical_lab_frequency_response", "physical_lab_frequency_response.py")
    return _load("physical_lab_frequency_response_ui", "physical_lab_frequency_response_ui.py")


def _load_deep_science_ui_module():
    _load("physical_lab_deep_science", "physical_lab_deep_science.py")
    return _load("physical_lab_deep_science_ui", "physical_lab_deep_science_ui.py")


def _load_kerr_shadow_sweep_ui_module():
    _load("physical_lab_deep_science", "physical_lab_deep_science.py")
    _load("physical_lab_kerr_shadow_sweep", "physical_lab_kerr_shadow_sweep.py")
    return _load("physical_lab_kerr_shadow_sweep_ui", "physical_lab_kerr_shadow_sweep_ui.py")


def _load_remaining_science_ui_module():
    _load("physical_lab_remaining_science", "physical_lab_remaining_science.py")
    return _load("physical_lab_remaining_science_ui", "physical_lab_remaining_science_ui.py")


def _load_model_depth_ui_module():
    _load("physical_lab_model_depth", "physical_lab_model_depth.py")
    return _load("physical_lab_model_depth_ui", "physical_lab_model_depth_ui.py")


def _load_model_depth_v_ui_module():
    _load("physical_lab_model_depth_v", "physical_lab_model_depth_v.py")
    return _load("physical_lab_model_depth_v_ui", "physical_lab_model_depth_v_ui.py")


def _load_model_depth_vi_ui_module():
    _load("physical_lab_model_depth_vi", "physical_lab_model_depth_vi.py")
    return _load("physical_lab_model_depth_vi_ui", "physical_lab_model_depth_vi_ui.py")


def _load_undulator_spectrum_ui_module():
    _load("physical_lab_undulator_spectrum", "physical_lab_undulator_spectrum.py")
    return _load("physical_lab_undulator_spectrum_ui", "physical_lab_undulator_spectrum_ui.py")


def _load_radiation_stokes_ui_module():
    _load("physical_lab_radia_radiation_propagation", "physical_lab_radia_radiation_propagation.py")
    return _load("physical_lab_radiation_stokes_ui", "physical_lab_radiation_stokes_ui.py")


def _load_radiation_quality_ui_module():
    _load("physical_lab_radiation_quality", "physical_lab_radiation_quality.py")
    _load("physical_lab_radiation_sensitivity", "physical_lab_radiation_sensitivity.py")
    return _load("physical_lab_radiation_quality_ui", "physical_lab_radiation_quality_ui.py")


def _load_radiation_seed_compare_ui_module():
    _load("physical_lab_radiation_quality", "physical_lab_radiation_quality.py")
    _load("physical_lab_radia_radiation_propagation", "physical_lab_radia_radiation_propagation.py")
    _load("physical_lab_radiation_seed_compare", "physical_lab_radiation_seed_compare.py")
    return _load("physical_lab_radiation_seed_compare_ui", "physical_lab_radiation_seed_compare_ui.py")


def _record_module_exception(source: str, exc: Exception, profile: str) -> None:
    try:
        _load_diagnostics_module().record_exception(source, exc, profile=profile, code="PLATFORM_MODULE_ERROR")
    except Exception:
        pass


def _load_application_modules():
    application_modes = _load("physical_lab_application_modes", "physical_lab_application_modes.py")
    range_module = _load("physical_lab_display_ranges", "physical_lab_display_ranges.py")
    return application_modes, range_module.padded_range


def _load_engineering_scenario_module():
    return _load("physical_lab_engineering_scenarios", "physical_lab_engineering_scenarios.py")


def _render_guarded(st, profile: str, source: str, label: str, renderer) -> None:
    try:
        renderer()
    except Exception as exc:
        _record_module_exception(source, exc, profile)
        st.warning(f"Physical Lab {label} could not load: {exc}")


def _render_application_mode(st, profile: str, namespace: dict | None) -> None:
    application_modes, padded_range = _load_application_modules()
    application_modes.padded_range = padded_range
    application_modes.render_application_mode(st, profile, namespace)


def render_engineering_vvuq(st, profile: str, namespace: dict | None = None) -> None:
    """Focused engineering workbench.

    Keep the established scientific modules, but render one task at a time.
    This replaces the previous append-everything layout where unrelated controls,
    plots, V&V tables and project tools competed on one continuous page.
    """
    ui_system = _load("physical_lab_ui_system", "physical_lab_ui_system.py")
    ui_system.render_workbench_header(
        st,
        "Engineering Workspace",
        "Choose the engineering question you are answering now. Only one tool is rendered at a time; scientific model state and stored evidence stay unchanged when you switch views.",
        kicker="Focused analysis",
    )
    ui_system.render_stage_rail(st, [
        ("Analysis", "physics/model interpretation"),
        ("V&V", "uncertainty and requirements"),
        ("Research", "project and evidence workflow"),
        ("Diagnostics", "runtime and backend review"),
    ])

    section = st.radio(
        "Engineering task",
        ["Analysis", "V&V", "Research", "Diagnostics"],
        horizontal=True,
        key=f"pl_engineering_section_{profile}",
    )
    section_help = {
        "Analysis": "Model-specific studies and physics-facing interpretation.",
        "V&V": "Uncertainty, requirements, measurement comparison and scenario review.",
        "Research": "Project/evidence organization and multi-step research orchestration.",
        "Diagnostics": "Runtime, backend and platform diagnostics.",
    }
    st.caption(section_help[section])

    analysis_tools = []

    if profile == "nonlinear-chaos":
        analysis_tools.extend([
            ("Kerr geodesic dynamics", "Relativistic geodesic analysis without mixing it into the core chaos controls.", "kerr-geodesic-model",
             lambda: _load_kerr_ui_module().render_kerr_geodesic_workspace(st, profile)),
            ("Kerr experiment / compute workflow", "Experiment-kernel workflow for Kerr studies.", "kerr-platform-workflow",
             lambda: _load_kerr_platform_ui_module().render_kerr_platform_workspace(st, profile)),
            ("Sun–Jupiter–Saturn dynamics", "Dedicated computational-astrophysics workspace.", "solar-system-dynamics",
             lambda: _load_solar_system_ui_module().render_solar_system_workspace(st, profile)),
            ("Kerr shadow morphology", "Shadow morphology parameter sweep and derived structure.", "kerr-shadow-morphology",
             lambda: _load_kerr_shadow_sweep_ui_module().render_kerr_shadow_morphology_workspace(st, profile)),
        ])

    if profile == "oscillation-integration":
        analysis_tools.append(
            ("Multilayer honeycomb lattice", "Lattice/phonon dynamics kept separate from the oscillator controls.", "multilayer-honeycomb-lattice",
             lambda: _load_lattice_ui_module().render_lattice_workspace(st, profile))
        )

    if profile in {"ising-monte-carlo", "random-walk-monte-carlo", "nonlinear-chaos", "oscillation-integration"}:
        analysis_tools.append(
            ("Advanced model science", "Additional model-specific physics analysis.", "advanced-model-science",
             lambda: _load_remaining_science_ui_module().render_remaining_science_workspace(st, profile))
        )

    if profile in {"ising-monte-carlo", "nonlinear-chaos", "oscillation-integration", "numerical-methods"}:
        analysis_tools.append(
            ("Model depth", "Deeper model diagnostics and derived quantities.", "model-depth",
             lambda: _load_model_depth_ui_module().render_model_depth_workspace(st, profile))
        )

    if profile in {"random-walk-monte-carlo", "oscillation-integration"}:
        analysis_tools.extend([
            ("Model depth V", "Focused advanced model extension V.", "model-depth-v",
             lambda: _load_model_depth_v_ui_module().render_model_depth_v_workspace(st, profile)),
            ("Model depth VI", "Focused advanced model extension VI.", "model-depth-vi",
             lambda: _load_model_depth_vi_ui_module().render_model_depth_vi_workspace(st, profile)),
        ])

    if profile in {"radia-magnet-studio", "radiation-platform"}:
        analysis_tools.append(
            ("Undulator spectrum & beam broadening", "Finite-N harmonics, off-axis resonance and beam-spread broadening.", "undulator-spectrum-studio",
             lambda: _load_undulator_spectrum_ui_module().render_undulator_spectrum_workspace(st, namespace))
        )

    if profile == "radia-magnet-studio":
        analysis_tools.extend([
            ("Trajectory radiation & Stokes map", "Field/trajectory-linked radiation and polarization diagnostics.", "trajectory-radiation-stokes-map",
             lambda: _load_radiation_stokes_ui_module().render_radiation_stokes_workspace(st, profile, namespace)),
            ("Radiation quality degradation", "Manufacturing-to-radiation quality sensitivity.", "manufacturing-radiation-quality",
             lambda: _load_radiation_quality_ui_module().render_radiation_quality_workspace(st, profile, namespace)),
            ("Nominal vs seed radiation map", "Compare nominal and manufacturing-seed radiation behavior.", "manufacturing-seed-radiation-map",
             lambda: _load_radiation_seed_compare_ui_module().render_seed_radiation_comparison(st, profile, namespace)),
        ])

    if profile in {"nonlinear-chaos", "oscillation-integration", "numerical-methods"}:
        analysis_tools.append(
            ("Deep science studio", "Profile-specific deeper numerical/physics studies.", "deep-science-studio",
             lambda: _load_deep_science_ui_module().render_deep_science_workspace(st, profile))
        )

    if profile in {"nonlinear-chaos", "oscillation-integration"}:
        analysis_tools.extend([
            ("Frequency response", "Frequency-domain response with numerical/analytic cross-checks.", "frequency-response-studio",
             lambda: _load_frequency_response_ui_module().render_frequency_response_workspace(st, profile)),
            ("Model refinement", "Alternative-model/refinement studies separated from the primary experiment.", "new-model-refinement-studio",
             lambda: _load_new_model_refinement_ui_module().render_new_model_refinement_workspace(st, profile)),
        ])

    if profile in {"numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo"}:
        analysis_tools.append(
            ("Physics application", "Connect the mathematical tool to one bounded physical scenario.", "application-mode",
             lambda: _render_application_mode(st, profile, namespace))
        )

    def render_selected(group_key: str, tools) -> None:
        if not tools:
            st.info("No additional tools are registered for this section and profile.")
            return
        labels = [item[0] for item in tools]
        selected = st.selectbox(
            "Tool",
            labels,
            key=f"pl_engineering_tool_{group_key}_{profile}",
        )
        tool = next(item for item in tools if item[0] == selected)
        st.caption(tool[1])
        st.markdown("---")
        _render_guarded(st, profile, tool[2], tool[0], tool[3])

    if section == "Analysis":
        render_selected("analysis", analysis_tools)
        return

    if section == "V&V":
        vv_tools = [
            ("Engineering uncertainty & requirements", "Error budgets, tolerance stacks, requirement margins and simulation↔measurement comparison.", "engineering-vvuq",
             lambda: _render_engineering_vvuq_legacy(st, profile, namespace)),
            ("Measurement & calibration evidence", "Register measurement/calibration evidence without mixing it into model controls.", "measurement-calibration",
             lambda: _load_measurement_registry_module().render_measurement_workspace(st, profile)),
            ("Engineering scenario review", "Review the bounded engineering interpretation for this profile.", "engineering-scenario",
             lambda: _load_engineering_scenario_module().render_engineering_scenario_review(st, profile)),
        ]
        render_selected("vvuq", vv_tools)
        return

    if section == "Research":
        research_tools = [
            ("Project & evidence workspace", "Organize the current profile as a reproducible project/evidence workflow.", "project-kernel",
             lambda: _load_project_kernel_module().render_project_workspace(st, profile, namespace)),
            ("Research orchestrator", "Coordinate multi-step research tasks after the individual analysis is understood.", "research-orchestrator",
             lambda: _load_research_orchestrator_ui_module().render_research_orchestrator(st, profile)),
        ]
        render_selected("research", research_tools)
        return

    _render_guarded(
        st,
        profile,
        "diagnostics-workspace",
        "Run & Diagnostics Log",
        lambda: _load_diagnostics_module().render_diagnostics_workspace(st, profile, _load_compute_engine_module()),
    )

