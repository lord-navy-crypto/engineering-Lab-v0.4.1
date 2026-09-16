"""Native Workbench adapters for real user-facing workspaces that predate the surface manifest.

These adapters only compose existing renderers and prerequisite selection flows.
They do not duplicate scientific models or change execution/validation semantics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


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
    """Expose diagnostics with compute-job events connected when the compute engine is available."""
    import physical_lab_compute_engine as compute_engine
    from physical_lab_diagnostics import render_diagnostics_workspace

    render_diagnostics_workspace(st, profile, compute_engine)


def render_measurement_registry_native(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    """Keep project selection visible instead of silently returning when no project is active."""
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
