"""Canonical discoverability registry for Engineering Lab user-facing surfaces.

The registry is deliberately UI/navigation-only. It does not change scientific
algorithms, validation meaning, model assumptions, or execution semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any


CATEGORIES = (
    "Experiments & Physics",
    "Data & Measurement",
    "Visualization & Analysis",
    "Modeling & Simulation",
    "Engineering Decisions & Reliability",
    "Reproducibility & AI",
)


@dataclass(frozen=True)
class Surface:
    surface_id: str
    label: str
    category: str
    description: str
    module: str | None = None
    callable_name: str | None = None
    launch_mode: str = "direct"  # direct | route | profile | embedded
    argument_mode: str = "st_profile"
    profiles: tuple[str, ...] = ()
    route_hint: str = ""


def _s(
    surface_id: str,
    label: str,
    category: str,
    description: str,
    module: str | None = None,
    callable_name: str | None = None,
    *,
    launch_mode: str = "direct",
    argument_mode: str = "st_profile",
    profiles: tuple[str, ...] = (),
    route_hint: str = "",
) -> Surface:
    return Surface(
        surface_id=surface_id,
        label=label,
        category=category,
        description=description,
        module=module,
        callable_name=callable_name,
        launch_mode=launch_mode,
        argument_mode=argument_mode,
        profiles=profiles,
        route_hint=route_hint,
    )


SURFACES: tuple[Surface, ...] = (
    # Existing project-level research surface and its component workspaces.
    _s(
        "utube-studio", "U-Tube Research Studio", "Experiments & Physics",
        "Rotating U-tube model, threshold maps, theory↔experiment comparison, uncertainty, advanced design, hysteresis, robust design and digital twin.",
        launch_mode="route", route_hint="Rotating U-Tube Research Studio → choose a top-level workspace",
    ),
    _s("utube-physical", "U-Tube Physical Model & Data", "Experiments & Physics",
       "Physical view, threshold map, theory↔experiment comparison and DOE/sweep workflows.",
       "physical_lab_utube_experiment_ui", "render_utube_experiment"),
    _s("utube-uncertainty", "U-Tube Uncertainty", "Experiments & Physics",
       "Explicit model-input uncertainty and threshold sensitivity tools.",
       "physical_lab_utube_uncertainty_ui", "render_utube_uncertainty"),
    _s("utube-advanced", "U-Tube Advanced Design", "Experiments & Physics",
       "Dimensionless physics, operating envelope, inverse design, sensitivity, design-space exploration, experiment planning and DIY data view.",
       "physical_lab_utube_advanced_ui", "render_utube_advanced"),
    _s("utube-hysteresis", "U-Tube Hysteresis & Dynamics", "Experiments & Physics",
       "Measured spin-up/spin-down hysteresis and ramp-rate dynamic-threshold analysis.",
       "physical_lab_utube_hysteresis_ui", "render_utube_hysteresis"),
    _s("utube-robust", "U-Tube Robust Design & Digital Twin", "Engineering Decisions & Reliability",
       "Tolerance-corner screening, Pareto robust design, adaptive experiments, verification templates and measurement digital twins.",
       "physical_lab_utube_robust_ui", "render_utube_robust_engineering"),

    # Data and measurement.
    _s("data-bridge", "Canonical Data Bridge", "Data & Measurement",
       "Promote parsed numeric tables into reusable canonical project datasets and inspect/export them.",
       launch_mode="route", route_hint="Project Workspace → Project Tools → Data & LabBridge → Data Bridge"),
    _s("measurement-registry", "Measurement & Calibration Registry", "Data & Measurement",
       "Project measurement/calibration records and their explicit provenance links.",
       launch_mode="route", route_hint=".physlab Project / Evidence Center → Measurements & calibration"),
    _s("betterboard-discovery", "BetterBoard Discovery", "Data & Measurement",
       "Discover local BetterBoard measurement packages and connect real-world sensor evidence.",
       "physical_lab_betterboard_discovery_ui", "render_betterboard_discovery"),
    _s("betterboard-inbox", "BetterBoard Ingress / Inbox", "Data & Measurement",
       "Select, validate and explicitly ingest BetterBoard measurement packages without silent promotion.",
       launch_mode="route", route_hint="Project Workspace → Project Tools → Data & LabBridge → BetterBoard Discovery"),
    _s("labbridge", "LabBridge & Lab Journey", "Data & Measurement",
       "Promote measurements, preserve provenance and maintain the project lab journey.",
       "physical_lab_labbridge_ui", "render_labbridge"),
    _s("research-notebook", "Experiment Notebook & Annotations", "Data & Measurement",
       "Write project notebook entries, annotate evidence and browse preserved research records.",
       launch_mode="route", route_hint="Project Workspace → Project Tools → Data & LabBridge → LabBridge / Journey → Experiment Notebook"),
    _s("result-inspector", "Result Inspector", "Data & Measurement",
       "Inspect results, contracts, materialized datasets and execution environments.",
       "physical_lab_result_inspector_ui", "render_result_inspector"),
    _s("research-orchestrator", "Research Orchestrator", "Data & Measurement",
       "Reusable sweep, numeric table, comparison and convergence workflows.",
       "physical_lab_research_orchestrator_ui", "render_research_orchestrator"),

    # Visualization and analysis.
    _s("visualization-studio", "Visualization Studio", "Visualization & Analysis",
       "Build figures from project datasets with explicit visualization choices and provenance.",
       "physical_lab_visualization_studio_ui", "render_visualization_studio"),
    _s("visual-analytics", "Visual Analytics", "Visualization & Analysis",
       "Interactive uncertainty, selection, multi-run overlay and saved dashboard analysis.",
       "physical_lab_visual_analytics_ui", "render_visual_analytics"),
    _s("applied-analysis", "Applied Analysis", "Visualization & Analysis",
       "Core applied statistics, uncertainty and design-of-experiments analysis.",
       "physical_lab_applied_analysis_ui", "render_applied_analysis"),
    _s("advanced-applied-analysis", "Advanced Applied Analysis", "Visualization & Analysis",
       "Robust regression, model selection, screening and DOE-to-sweep workflows.",
       "physical_lab_applied_analysis_advanced_ui", "render_applied_analysis_advanced"),
    _s("deep-applied-math", "Deep Applied Math", "Visualization & Analysis",
       "Deeper numerical, linear-algebra and mathematical analysis workflows.",
       "physical_lab_applied_math_deep_ui", "render_applied_math_deep"),
    _s("sweep-design-bridge", "Sweep Design Bridge", "Visualization & Analysis",
       "Bridge statistical designs into bounded computational sweep jobs.",
       "physical_lab_sweep_design_bridge_ui", "render_sweep_design_bridge"),
    _s("science-analysis", "Science Analysis", "Visualization & Analysis",
       "Scientific semantics, sensitivity, response surfaces, comparison, correlation and Pareto analysis.",
       "physical_lab_tradeoff_analysis_ui", "render_tradeoff_analysis"),
    _s("science-protocol", "Science Protocol", "Visualization & Analysis",
       "Project-level analysis plan and protocol controls that preserve scientific interpretation boundaries.",
       "physical_lab_science_protocol_ui", "render_science_protocol_ui", argument_mode="st_profile_project"),

    # Modeling and simulation.
    _s("modelspec-diy", "ModelSpec DIY", "Modeling & Simulation",
       "Build bounded model controls without modifying source datasets.",
       "physical_lab_modelspec_diy_ui", "render_modelspec_diy"),
    _s("run-comparison", "Run Comparison", "Modeling & Simulation",
       "Visual parameter/metric deltas, comparability, UQ and environment/staleness provenance.",
       "physical_lab_run_comparison_ui", "render_run_comparison"),
    _s("model-coupling", "Model Coupling", "Modeling & Simulation",
       "Map canonical dataset values into explicit downstream model parameter packets.",
       "physical_lab_model_coupling_ui", "render_model_coupling"),
    _s("pipeline-dag", "Pipeline DAG", "Modeling & Simulation",
       "Build and inspect dependency graphs and workflow execution state.",
       "physical_lab_pipeline_graph_ui", "render_pipeline_graph"),
    _s("digital-twin", "Measurement Digital Twin", "Modeling & Simulation",
       "Measurement→calibration→model comparison→discrepancy and beam-statistics workspace.",
       "physical_lab_digital_twin_ui", "render_digital_twin_workspace",
       profiles=("radia-magnet-studio", "radiation-platform", "oscillation-integration"),
       route_hint="Available directly in RADIA Magnet Studio, Radiation Platform and Oscillation Integration profiles."),

    # Engineering layers that were previously buried inside Evidence Center tabs.
    _s("engineering-decisions", "Engineering Decisions", "Engineering Decisions & Reliability",
       "Evidence-linked alternatives, explicit metrics/constraints and Pareto trade studies without a synthetic master score.",
       "physical_lab_engineering_decision_ui", "render_engineering_decision_tab", argument_mode="st_project_profile_refs"),
    _s("operations-planning", "Operations Planning", "Engineering Decisions & Reliability",
       "Transparent finite-resource engineering task planning and dispatch-rule simulation.",
       "physical_lab_operations_ui", "render_operations_tab", argument_mode="st_project_profile"),
    _s("quality-reliability", "Quality & Reliability", "Engineering Decisions & Reliability",
       "Observed variation, DOE evidence and reliability-event analysis without qualification/certification claims.",
       "physical_lab_quality_reliability_ui", "render_quality_reliability_tab", argument_mode="st_project_profile_refs"),
    _s("risk-economics", "Risk & Engineering Economics", "Engineering Decisions & Reliability",
       "Declared risk scenarios and time-valued cash flows without automatic risk acceptance or recommendations.",
       "physical_lab_risk_economics_ui", "render_risk_economics_tab", argument_mode="st_project_profile_refs"),
    _s("requirements-verification", "Requirements & Verification", "Engineering Decisions & Reliability",
       "Traceable shall-statements, verification methods, evidence freshness and human review rationale.",
       "physical_lab_requirements_verification_ui", "render_requirements_verification_tab", argument_mode="st_project_profile_refs"),

    # Reproducibility / evidence / advisory layers.
    _s("evidence-center", "Evidence Center", "Reproducibility & AI",
       "Credibility passport, claims, cross-checks, evidence graph, snapshots and evidence diffs.",
       "physical_lab_evidence_center_ui", "render_evidence_center", argument_mode="st_project_profile"),
    _s("reproducibility-pack", "Reproducibility Pack", "Reproducibility & AI",
       "Package project metadata, datasets, analysis artifacts, environments, provenance and reports into a portable ZIP.",
       launch_mode="route", route_hint="Project Workspace → Project Tools → Reproducibility"),
    _s("local-ai", "Local AI Physics Tutor", "Reproducibility & AI",
       "Read-only local OpenPenguin/Ollama explanation layer; it cannot change parameters, execute model-provided code or replace solvers.",
       "physical_lab_local_ai", "render_local_ai_assistant", launch_mode="profile",
       profiles=("numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo", "nonlinear-chaos", "oscillation-integration", "radia-magnet-studio", "radiation-platform"),
       route_hint="Native Lab → Local AI Physics Tutor · OpenPenguin / Ollama"),
    _s("run-vault", "Run Vault", "Reproducibility & AI",
       "Persistent experiment snapshots for reproducibility, restoration, comparison, notes and bug reports.",
       "physical_lab_advanced", "_render_run_vault", launch_mode="profile",
       profiles=("numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo", "nonlinear-chaos", "oscillation-integration", "radia-magnet-studio", "radiation-platform"),
       route_hint="Native Lab → Run Vault"),
    _s("openguin-advisory", "OpenPenguin Advisory Bridge", "Reproducibility & AI",
       "Review/import advisory records while preserving the boundary that suggestions do not execute measurements, solvers or parameter changes.",
       launch_mode="route", route_hint="Project Workspace → Project Tools → Data & LabBridge → LabBridge / Journey → OpenPenguin advisory"),

    # Profile-scoped science/model families: centrally discoverable, but not falsely
    # launched without the profile/namespace state their existing integrations require.
    _s("engineering-vvuq", "Engineering V&V / UQ Suite", "Engineering Decisions & Reliability",
       "Profile-native engineering verification, validation and uncertainty surfaces hosting deeper science/model workspaces.",
       "physical_lab_engineering", "render_engineering_vvuq", launch_mode="profile",
       profiles=("numerical-methods", "ising-monte-carlo", "random-walk-monte-carlo", "nonlinear-chaos", "oscillation-integration", "radia-magnet-studio", "radiation-platform"),
       route_hint="Native Lab → Engineering V&V/UQ"),
    _s("kerr-geodesics", "Kerr Geodesic Dynamics", "Experiments & Physics",
       "Kerr geodesic dynamics workspace.", "physical_lab_kerr_ui", "render_kerr_geodesic_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos",), route_hint="Nonlinear Chaos → Engineering V&V/UQ"),
    _s("kerr-platform", "Kerr Experiment / Compute Workflow", "Experiments & Physics",
       "Kerr experiment and compute workflow with preserved experiment identity.", "physical_lab_kerr_platform_ui", "render_kerr_platform_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos",), route_hint="Nonlinear Chaos → Engineering V&V/UQ"),
    _s("kerr-shadow", "Kerr Shadow Morphology", "Experiments & Physics",
       "Kerr shadow morphology sweep and analysis.", "physical_lab_kerr_shadow_sweep_ui", "render_kerr_shadow_morphology_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos",), route_hint="Nonlinear Chaos → Deep Science"),
    _s("solar-system", "Sun–Jupiter–Saturn Dynamics", "Experiments & Physics",
       "Solar-system dynamics and workflow tools.", "physical_lab_solar_system_ui", "render_solar_system_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos",), route_hint="Nonlinear Chaos → Engineering V&V/UQ"),
    _s("lattice-dynamics", "Multilayer Honeycomb Lattice", "Experiments & Physics",
       "Lattice dynamics, phonons and associated workflow controls.", "physical_lab_lattice_ui", "render_lattice_workspace",
       launch_mode="profile", profiles=("oscillation-integration",), route_hint="Oscillation Integration → Engineering V&V/UQ"),
    _s("deep-science", "Deep Science Studio", "Experiments & Physics",
       "Advanced science analyses exposed by supported physics profiles.", "physical_lab_deep_science_ui", "render_deep_science_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos", "oscillation-integration", "numerical-methods"), route_hint="Supported physics profile → Engineering V&V/UQ"),
    _s("remaining-science", "Advanced Model Science", "Experiments & Physics",
       "Additional profile-specific science studies.", "physical_lab_remaining_science_ui", "render_remaining_science_workspace",
       launch_mode="profile", profiles=("ising-monte-carlo", "random-walk-monte-carlo", "nonlinear-chaos", "oscillation-integration"), route_hint="Supported physics profile → Engineering V&V/UQ"),
    _s("frequency-response", "Frequency Response Studio", "Experiments & Physics",
       "Frequency-response analysis for supported dynamic models.", "physical_lab_frequency_response_ui", "render_frequency_response_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos", "oscillation-integration"), route_hint="Supported dynamics profile → Engineering V&V/UQ"),
    _s("new-model-refinement", "New Model Refinement Studio", "Modeling & Simulation",
       "Model-refinement investigations exposed in supported dynamics profiles.", "physical_lab_new_model_refinement_ui", "render_new_model_refinement_workspace",
       launch_mode="profile", profiles=("nonlinear-chaos", "oscillation-integration"), route_hint="Supported dynamics profile → Engineering V&V/UQ"),
    _s("model-depth", "Model Depth", "Modeling & Simulation",
       "Profile-specific deeper model diagnostics and analyses.", "physical_lab_model_depth_ui", "render_model_depth_workspace",
       launch_mode="profile", profiles=("ising-monte-carlo", "nonlinear-chaos", "oscillation-integration", "numerical-methods"), route_hint="Supported profile → Engineering V&V/UQ"),
    _s("undulator-spectrum", "Undulator Spectrum & Beam Broadening", "Experiments & Physics",
       "Undulator spectrum and beam-broadening analysis requiring the native radiation/RADIA namespace.", "physical_lab_undulator_spectrum_ui", "render_undulator_spectrum_workspace",
       launch_mode="profile", profiles=("radia-magnet-studio", "radiation-platform"), route_hint="RADIA Magnet Studio / Radiation Platform → Engineering V&V/UQ"),
    _s("radiation-stokes", "Trajectory Radiation & Stokes Map", "Experiments & Physics",
       "Trajectory-linked radiation and Stokes analysis requiring RADIA namespace state.", "physical_lab_radiation_stokes_ui", "render_radiation_stokes_workspace",
       launch_mode="profile", profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → Engineering V&V/UQ"),
    _s("radiation-quality", "Radiation Quality Degradation", "Engineering Decisions & Reliability",
       "Manufacturing/radiation quality analysis requiring native RADIA state.", "physical_lab_radiation_quality_ui", "render_radiation_quality_workspace",
       launch_mode="profile", profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → Engineering V&V/UQ"),
    _s("radiation-seed-compare", "Nominal vs Seed Radiation", "Experiments & Physics",
       "Nominal-versus-seed radiation comparison requiring native RADIA state.", "physical_lab_radiation_seed_compare_ui", "render_seed_radiation_comparison",
       launch_mode="profile", profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → Engineering V&V/UQ"),
    _s("radia-forward", "RADIA Measurement Adapter", "Modeling & Simulation",
       "Use the current Magnet Studio configuration as the real RADIA forward model against measurement coordinates.",
       "physical_lab_radia_adapter", "render_radia_forward_workspace", launch_mode="profile",
       profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → Full mode → RADIA Measurement Adapter"),
    _s("radia-tolerance", "RADIA Nonlinear Tolerance Workspace", "Engineering Decisions & Reliability",
       "Profile-native nonlinear RADIA tolerance analysis using the current Magnet Studio namespace.",
       "physical_lab_radia_tolerance", "render_radia_tolerance_workspace", launch_mode="profile",
       profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → nonlinear RADIA tolerance workspace"),
    _s("radia-radiation-propagation", "RADIA → Radiation Tolerance Propagation", "Engineering Decisions & Reliability",
       "Propagate RADIA tolerance cases into radiation behavior without replacing native model provenance.",
       "physical_lab_radia_radiation_propagation", "render_radia_radiation_propagation", launch_mode="profile",
       profiles=("radia-magnet-studio",), route_hint="RADIA Magnet Studio → RADIA → Radiation tolerance propagation"),
)


# UI modules that are intentionally rendered by another registered workspace or
# require native namespace state. Keeping this explicit is what makes new orphan
# UI files fail CI instead of silently disappearing below the surface.
EMBEDDED_UI_MODULES = frozenset({
    "physical_lab_project_interop_ui",
    "physical_lab_utube_robust_ui",
    "physical_lab_utube_hysteresis_ui",
    "physical_lab_model_depth_iv_ui",
    "physical_lab_model_depth_v_ui",
    "physical_lab_model_depth_vi_ui",
    "physical_lab_model_depth_vii_ui",
    "physical_lab_model_depth_viii_ui",
    "physical_lab_model_depth_ix_ui",
    "physical_lab_radiation_interactions_ui",
    "physical_lab_radiation_response_surface_ui",
})

PROFILE_UI_MODULES = frozenset(
    row.module for row in SURFACES if row.launch_mode == "profile" and row.module and row.module.endswith("_ui")
)
DIRECT_UI_MODULES = frozenset(
    row.module for row in SURFACES if row.launch_mode == "direct" and row.module and row.module.endswith("_ui")
)
CLASSIFIED_UI_MODULES = frozenset(DIRECT_UI_MODULES | PROFILE_UI_MODULES | EMBEDDED_UI_MODULES)


def get_surface(surface_id: str) -> Surface | None:
    return next((row for row in SURFACES if row.surface_id == surface_id), None)


def surface_categories() -> tuple[str, ...]:
    return CATEGORIES


def surfaces_for_catalog(profile: str) -> list[Surface]:
    # Show every surface. Profile restrictions affect launchability, never
    # discoverability: the entire point of this catalog is to prevent hiding.
    return list(SURFACES)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def artifact_refs(project_path: Path) -> list[str]:
    """Return the same explicit evidence-reference vocabulary used by Evidence Center."""
    import physical_lab_project_kernel as projects

    path = Path(project_path).expanduser().resolve()
    doc = projects.open_project(path)
    rows: list[str] = []
    for kind, key in (("experiment", "experiments"), ("job", "jobs"), ("result", "results")):
        for item_id in sorted((doc.get(key) or {}).keys()):
            rows.append(f"{kind}:{item_id}")
    measurement_index = _read_json(path / "measurements" / "index.json")
    calibration_index = _read_json(path / "calibration" / "index.json")
    for item_id in sorted((measurement_index.get("measurements") or {}).keys()):
        rows.append(f"measurement:{item_id}")
    for item_id in sorted((calibration_index.get("calibrations") or {}).keys()):
        rows.append(f"calibration:{item_id}")
    return rows


def launchability(surface: Surface, profile: str, project_path: Path | None) -> tuple[bool, str]:
    if surface.launch_mode == "route":
        return True, "route"
    if surface.launch_mode == "embedded":
        return False, surface.route_hint or "Embedded in another workspace"
    if surface.launch_mode == "profile":
        native = profile in surface.profiles if surface.profiles else False
        return False, surface.route_hint or ("Available in current profile" if native else "Open its native profile")
    if surface.profiles and profile not in surface.profiles:
        return False, surface.route_hint or "Open a supported profile first"
    if surface.argument_mode in {"st_profile_project", "st_project_profile", "st_project_profile_refs"} and project_path is None:
        return False, "Open a .physlab project first"
    return True, "direct"


def render_surface(st: Any, surface: Surface, profile: str, project_path: Path | None = None) -> None:
    """Render one explicitly selected direct surface without changing its semantics."""
    if surface.launch_mode != "direct":
        st.info(surface.route_hint or "This workspace is available through its native Engineering Lab route.")
        return
    ok, reason = launchability(surface, profile, project_path)
    if not ok:
        st.info(reason)
        return
    if not surface.module or not surface.callable_name:
        st.warning(f"{surface.label} has no renderer configured.")
        return
    try:
        module = importlib.import_module(surface.module)
        renderer = getattr(module, surface.callable_name)
        if surface.argument_mode == "st_profile":
            renderer(st, profile)
        elif surface.argument_mode == "st_profile_project":
            renderer(st, profile, project_path)
        elif surface.argument_mode == "st_project_profile":
            renderer(st, project_path, profile)
        elif surface.argument_mode == "st_project_profile_refs":
            renderer(st, project_path, profile, artifact_refs(Path(project_path)))
        else:
            raise ValueError(f"unsupported surface argument mode: {surface.argument_mode}")
    except Exception as exc:
        st.warning(f"{surface.label} could not load: {exc}")
