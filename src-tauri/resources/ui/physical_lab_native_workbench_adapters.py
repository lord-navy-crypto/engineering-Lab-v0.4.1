"""Native Workbench adapters for real user-facing workspaces that predate the surface manifest.

These adapters only compose existing renderers and prerequisite selection flows.
They do not duplicate scientific models or change execution/validation semantics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

# Small canonical overlay for capabilities discovered after the original generated
# surfaces.json was established. Existing IDs are merged field-by-field; new IDs
# are appended. Keeping this beside the adapters means desktop preparation and the
# bundled Python deep-link entry consume exactly the same migration metadata.
NATIVE_SURFACE_OVERRIDES: tuple[dict[str, Any], ...] = (
    {"id": "local-ai", "argumentMode": "st_profile_namespace"},
    {"id": "engineering-vvuq", "argumentMode": "st_profile_namespace"},
    {"id": "undulator-spectrum", "argumentMode": "st_namespace"},
    {"id": "radiation-stokes", "argumentMode": "st_profile_namespace"},
    {
        "id": "radiation-quality",
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_radiation_quality_native",
        "argumentMode": "st_profile_namespace",
    },
    {
        "id": "radiation-seed-compare",
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_radiation_seed_compare_native",
        "argumentMode": "st_profile_namespace",
    },
    {
        "id": "radiation-interactions",
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_radiation_interactions_native",
        "argumentMode": "st_profile_namespace",
    },
    {
        "id": "radiation-response-surface",
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_radiation_response_surface_native",
        "argumentMode": "st_profile_namespace",
    },
    {"id": "radia-forward", "argumentMode": "st_namespace"},
    {"id": "radia-tolerance", "argumentMode": "st_namespace"},
    {"id": "radia-radiation-propagation", "argumentMode": "st_namespace"},
    {
        "id": "utube-experiment-planner",
        "label": "U-Tube Experiment Planner",
        "category": "Experiments & Physics",
        "kind": "embedded",
        "launchMode": "direct",
        "profiles": ["rotating-utube"],
        "preferredProfiles": ["rotating-utube"],
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_utube_experiment_planner_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "Rotating U-Tube Research Studio → focused model-based experiment planning",
    },
    {
        "id": "radiation-sensitivity",
        "label": "Manufacturing → Radiation Sensitivity",
        "category": "Engineering Decisions & Reliability",
        "kind": "embedded",
        "launchMode": "profile",
        "profiles": ["radia-magnet-studio"],
        "preferredProfiles": ["radia-magnet-studio"],
        "targetModule": "physical_lab_native_workbench_adapters",
        "targetCallable": "render_radiation_sensitivity_native",
        "argumentMode": "st_profile_namespace",
        "routeHint": "RADIA Magnet Studio → focused one-factor manufacturing/radiation screening",
    },
)


def merge_native_surface_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge the reviewed migration overlay without changing row ordering."""
    output = [dict(row) for row in rows if isinstance(row, dict)]
    index = {str(row.get("id") or ""): i for i, row in enumerate(output) if row.get("id")}
    for patch in NATIVE_SURFACE_OVERRIDES:
        sid = str(patch.get("id") or "")
        if not sid:
            continue
        if sid in index:
            output[index[sid]].update(dict(patch))
        else:
            index[sid] = len(output)
            output.append(dict(patch))
    return output


def render_application_scenarios(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    """Expose the Mathematical Tool / Physics Scenario switch and its engineering review together."""
    from physical_lab_application_modes import render_application_mode
    from physical_lab_engineering_scenarios import render_engineering_scenario_review
    render_application_mode(st, profile, namespace or {})
    render_engineering_scenario_review(st, profile)


def render_compute_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    from physical_lab_compute_engine import render_compute_workspace
    render_compute_workspace(st, profile, namespace or {})


def render_diagnostics_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    import physical_lab_compute_engine as compute_engine
    from physical_lab_diagnostics import render_diagnostics_workspace
    render_diagnostics_workspace(st, profile, compute_engine)


def render_measurement_registry_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    import physical_lab_project_kernel as projects
    from physical_lab_measurement_registry import render_measurement_workspace
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "").strip()
    project = Path(active).expanduser().resolve() if active else None
    if project is None or not (project / "project.json").is_file():
        st.info("Measurement & Calibration Registry needs an active .physlab Project. Select or create one below.")
        projects.render_project_workspace(st, profile, namespace or {})
        return
    render_measurement_workspace(st, profile)


def render_model_campaign_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    from physical_lab_model_campaigns import render_model_campaign
    render_model_campaign(st, profile, dict(namespace or {}))


def render_model_engineering_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    from physical_lab_model_engineering import render_model_engineering
    render_model_engineering(st, profile, dict(namespace or {}))


def render_engineering_workflow_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    from physical_lab_engineering_workflow import render_engineering_workflow
    render_engineering_workflow(st, profile, dict(namespace or {}))


def render_utube_experiment_planner_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    """Expose the existing U-Tube model-based sampling proposal as a focused native workspace."""
    import plotly.express as px
    from physical_lab_utube_advanced import BOUNDARY, experiment_scan_plan
    from physical_lab_utube_experiment import threshold

    st.markdown("#### U-Tube Experiment Planner")
    st.caption(
        "Build a two-resolution RPM sampling proposal around the current deterministic 3-D threshold prediction. "
        "The proposal is not a hardware safety limit and does not replace instrument-specific procedures."
    )
    c1, c2 = st.columns(2)
    volume = float(c1.number_input("Planning volume / mL", min_value=0.01, value=3.0, key=f"pl_ut_native_plan_v_{profile}"))
    nq = int(c2.number_input("Planning quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_native_plan_nq_{profile}"))
    try:
        predicted = threshold(volume, nq=nq)
        plan = experiment_scan_plan(predicted)
        st.metric("Predicted finite-volume threshold n_g(V)", f"{predicted:.3f} rpm")
        st.dataframe(plan, hide_index=True, width="stretch")
        fig = px.scatter(plan, x="n_rpm", y="phase", color="phase", title="Two-resolution scan proposal")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.caption(
            "Sampling density is centered on the model prediction. Proposed RPM points are experimental planning aids, "
            "not measured thresholds, confidence bounds, or certified operating limits."
        )
    except Exception as exc:
        st.warning(f"Experiment plan unavailable: {exc}")
    st.caption(BOUNDARY)


def _render_radiation_propagation_prerequisite(st: Any, namespace: Mapping[str, Any] | None, *, target: str) -> None:
    from physical_lab_radia_radiation_propagation import render_radia_radiation_propagation
    st.info(
        f"{target} needs a completed RADIA → trajectory → radiation manufacturing ensemble first. "
        "Configure and explicitly run that prerequisite below; opening this page does not start a solve."
    )
    render_radia_radiation_propagation(st, dict(namespace or {}))


def render_radiation_quality_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio":
        st.info("Radiation Quality Degradation is available through RADIA Magnet Studio.")
        return
    if not st.session_state.get("pl_rrp_result"):
        _render_radiation_propagation_prerequisite(st, namespace, target="Radiation Quality Degradation")
        return
    from physical_lab_radiation_quality_ui import render_radiation_quality_workspace
    render_radiation_quality_workspace(st, profile, namespace)


def render_radiation_seed_compare_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio":
        st.info("Radiation Seed Comparison is available through RADIA Magnet Studio.")
        return
    if not st.session_state.get("pl_rrp_result"):
        _render_radiation_propagation_prerequisite(st, namespace, target="Radiation Seed Comparison")
        return
    from physical_lab_radiation_seed_compare_ui import render_seed_radiation_comparison
    render_seed_radiation_comparison(st, profile, namespace)


def _active_radiation_error_families(namespace: Mapping[str, Any] | None) -> list[str]:
    from physical_lab_radiation_response_surface import ERROR_KEYS
    params = dict((namespace or {}).get("current_params") or {})
    active: list[str] = []
    for key in ERROR_KEYS:
        try:
            if abs(float(params.get(key, 0.0) or 0.0)) > 0.0:
                active.append(str(key))
        except Exception:
            continue
    return active


def render_radiation_interactions_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio":
        st.info("Radiation Interactions is available through RADIA Magnet Studio.")
        return
    active = _active_radiation_error_families(namespace)
    if len(active) < 2:
        st.info(
            "Pairwise Radiation Interactions needs at least two non-zero RADIA manufacturing-error families. "
            "Enable two or more error magnitudes in Magnet Studio, then return here."
        )
        st.caption(f"Currently active: {', '.join(active) if active else 'none'}")
        return
    from physical_lab_radiation_interactions_ui import render_radiation_interactions_workspace
    render_radiation_interactions_workspace(st, profile, namespace)


def render_radiation_response_surface_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio":
        st.info("Radiation Response Surface is available through RADIA Magnet Studio.")
        return
    active = _active_radiation_error_families(namespace)
    if len(active) < 2:
        st.info(
            "Radiation Response Surface needs at least two non-zero RADIA manufacturing-error families. "
            "Enable two or more error magnitudes in Magnet Studio, then return here."
        )
        st.caption(f"Currently active: {', '.join(active) if active else 'none'}")
        return
    from physical_lab_radiation_response_surface_ui import render_radiation_response_surface_workspace
    render_radiation_response_surface_workspace(st, profile, namespace)


def render_radiation_sensitivity_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio":
        st.info("Radiation Sensitivity is available through RADIA Magnet Studio.")
        return
    st.markdown("## Physical Lab · Manufacturing → Radiation Sensitivity")
    st.caption(
        "Focused entry to the existing one-factor-at-a-time screening workflow. "
        "It uses configured RADIA manufacturing-error magnitudes and real bounded solver runs; it does not establish causality or validation."
    )
    from physical_lab_radiation_quality_ui import _render_sensitivity
    _render_sensitivity(st, namespace)
