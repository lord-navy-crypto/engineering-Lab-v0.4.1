"""Scientific Visualization workspace for Engineering Lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_result_inspector import load_project_result
from physical_lab_visual_analytics_ui import _sources
from physical_lab_scientific_visualization import BOUNDARY, contract_field_metadata


def _raw_result(project_path: Path, source: dict[str, Any]) -> dict[str, Any] | None:
    source_id = str(source.get("id") or "")
    if not source_id.startswith("result:"):
        return None
    try:
        result, _identity = load_project_result(project_path, source_id.split(":", 1)[1])
        return dict(result)
    except Exception:
        return None


def render_scientific_visualization(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use Scientific Visualization.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Scientific Visualization")
    st.caption("Unit-aware axes, explicit UQ objects, sensitivity screening and response surfaces built on Engineering Lab scientific contracts.")
    if not sources:
        st.info("No project results, completed sweeps, or canonical datasets are available yet.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Scientific source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_sv_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)
    result = _raw_result(project_path, source)
    a, b, c = st.columns(3)
    a.metric("Source", source["kind"])
    b.metric("Rows", len(source["frame"]))
    c.metric("Contract", "registered" if result is not None and contract_field_metadata(result) else "unregistered / N/A")
    from physical_lab_scientific_visualization_units_ui import render_units_uq
    from physical_lab_scientific_visualization_analysis_ui import render_sensitivity_surface
    tab_units, tab_analysis = st.tabs(["Units & Native UQ", "Sensitivity & Response Surface"])
    with tab_units:
        render_units_uq(st, source, result, profile)
    with tab_analysis:
        render_sensitivity_surface(st, source, profile)
    st.caption(BOUNDARY)
