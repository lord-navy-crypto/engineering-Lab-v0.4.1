"""Interactive Visual Analytics Workbench for Engineering Lab."""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets
from physical_lab_result_inspector import load_project_result
from physical_lab_sweep_executor import list_sweep_jobs, read_sweep_result
from physical_lab_visualization_studio import dataset_frame, numeric_columns, result_frame, sweep_frame
from physical_lab_visual_analytics import (
    BOUNDARY,
    common_numeric_columns,
    overlay_frame,
    save_dashboard,
    selection_indices,
    uncertainty_candidates,
    uncertainty_error_arrays,
)


def _sources(project_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        doc = projects.open_project(project_path)
    except Exception:
        doc = {}
    for job_id in (doc.get("results") or {}):
        try:
            result, identity = load_project_result(project_path, str(job_id))
            frame = result_frame(result)
            if not frame.empty:
                out.append({"id": f"result:{job_id}", "label": f"Result · {job_id}", "kind": "result", "frame": frame, "identity": identity})
        except Exception:
            continue
    try:
        jobs = list_sweep_jobs(limit=100)
    except Exception:
        jobs = []
    for job in jobs:
        if job.get("status") != "succeeded":
            continue
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        try:
            result = read_sweep_result(job_id) or {}
            frame = sweep_frame(result)
            if not frame.empty:
                out.append({"id": f"sweep:{job_id}", "label": f"Sweep · {job_id}", "kind": "sweep", "frame": frame, "identity": {"sweep_job_id": job_id, "adapter": result.get("adapter")}})
        except Exception:
            continue
    try:
        datasets = list_canonical_datasets(project_path)
    except Exception:
        datasets = []
    for dataset in datasets:
        dataset_id = str(dataset.get("dataset_id") or "")
        if not dataset_id:
            continue
        frame = dataset_frame(dataset)
        if not frame.empty:
            out.append({"id": f"dataset:{dataset_id}", "label": f"Dataset · {dataset_id}", "kind": "dataset", "frame": frame, "identity": {"dataset_id": dataset_id, "sha256": dataset.get("sha256")}})
    return out


def _selection_plot(st: Any, fig: go.Figure, *, key: str, row_count: int) -> list[int]:
    """Enable point/box/lasso selection when supported, with a no-break fallback."""
    try:
        params = inspect.signature(st.plotly_chart).parameters
    except Exception:
        params = {}
    if "on_select" in params:
        try:
            state = st.plotly_chart(
                fig,
                width="stretch",
                config={"displaylogo": False, "scrollZoom": True},
                key=key,
                on_select="rerun",
                selection_mode=("points", "box", "lasso"),
            )
            return selection_indices(state, row_count)
        except TypeError:
            pass
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True}, key=key)
    return []


def _uncertainty_tab(st: Any, source: dict[str, Any], profile: str) -> dict[str, Any] | None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Select a source with at least two numeric fields for an uncertainty-aware plot.")
        return None
    c1, c2 = st.columns(2)
    x = c1.selectbox("X", numeric, key=f"pl_va_unc_x_{profile}")
    ys = [c for c in numeric if c != x] or numeric
    y = c2.selectbox("Y", ys, key=f"pl_va_unc_y_{profile}")

    suggestions = uncertainty_candidates(numeric, y)
    mode = st.radio("Error representation", ["None", "Symmetric field", "Lower + upper bounds"], horizontal=True, key=f"pl_va_unc_mode_{profile}")
    symmetric = lower = upper = None
    error_y = None
    try:
        if mode == "Symmetric field":
            options = [c for c in numeric if c != y]
            suggested = suggestions["symmetric"][0] if suggestions["symmetric"] else options[0]
            symmetric = st.selectbox("σ / error field", options, index=options.index(suggested) if suggested in options else 0, key=f"pl_va_unc_sym_{profile}")
            error_y = uncertainty_error_arrays(frame, y, symmetric=symmetric)
        elif mode == "Lower + upper bounds":
            options = [c for c in numeric if c != y]
            a, b = st.columns(2)
            suggested_lo = suggestions["lower"][0] if suggestions["lower"] else options[0]
            suggested_hi = suggestions["upper"][0] if suggestions["upper"] else options[min(1, len(options) - 1)]
            lower = a.selectbox("Lower bound field", options, index=options.index(suggested_lo) if suggested_lo in options else 0, key=f"pl_va_unc_lo_{profile}")
            upper = b.selectbox("Upper bound field", options, index=options.index(suggested_hi) if suggested_hi in options else min(1, len(options) - 1), key=f"pl_va_unc_hi_{profile}")
            error_y = uncertainty_error_arrays(frame, y, lower=lower, upper=upper)
    except Exception as exc:
        st.warning(f"Uncertainty fields are not currently valid: {exc}")
        error_y = None

    xv = pd.to_numeric(frame[x], errors="coerce")
    yv = pd.to_numeric(frame[y], errors="coerce")
    valid = xv.notna() & yv.notna()
    plot = frame.loc[valid].copy()
    err = None
    if error_y and len(plot) == len(frame):
        err = {"type": "data", "visible": True, "array": error_y["array"], "arrayminus": error_y["arrayminus"]}
    elif error_y:
        st.caption("Error bars were omitted because rows with non-numeric X/Y values were filtered; use a clean numeric source for aligned uncertainty visualization.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot[x], y=plot[y], mode="lines+markers", name=y, error_y=err, customdata=plot.index))
    fig.update_layout(title=f"{source['label']} · {y} vs {x}", xaxis_title=x, yaxis_title=y, height=620, hovermode="closest")
    selected = _selection_plot(st, fig, key=f"pl_va_unc_plot_{profile}", row_count=len(plot))
    if selected:
        st.markdown("##### Selected records")
        st.dataframe(plot.iloc[selected], hide_index=False, width="stretch")
        st.caption(f"{len(selected)} point(s) selected. Selection changes the view only; it does not alter the underlying result or dataset.")
    else:
        st.caption("Use point, box, or lasso selection when supported by the installed Streamlit version; otherwise the chart remains fully interactive for hover/zoom.")
    return {
        "kind": "uncertainty-plot",
        "source": {"id": source["id"], "identity": source.get("identity")},
        "x": x,
        "y": y,
        "error_mode": mode,
        "symmetric": symmetric,
        "lower": lower,
        "upper": upper,
    }


def _overlay_tab(st: Any, sources: list[dict[str, Any]], profile: str) -> dict[str, Any] | None:
    if len(sources) < 2:
        st.info("At least two plottable sources are required for a multi-run overlay.")
        return None
    labels = {s["id"]: s["label"] for s in sources}
    chosen = st.multiselect("Sources to overlay", [s["id"] for s in sources], default=[s["id"] for s in sources[:2]], format_func=lambda x: labels.get(x, x), key=f"pl_va_overlay_sources_{profile}")
    selected = [s for s in sources if s["id"] in chosen]
    if len(selected) < 2:
        st.info("Select at least two sources.")
        return None
    common = common_numeric_columns([s["frame"] for s in selected])
    if len(common) < 2:
        st.warning("The selected sources do not share at least two numeric field names. Choose sources generated from compatible schemas or promote them to a common canonical dataset schema first.")
        return None
    a, b = st.columns(2)
    x = a.selectbox("Common X field", common, key=f"pl_va_overlay_x_{profile}")
    y_options = [c for c in common if c != x] or common
    y = b.selectbox("Common Y field", y_options, key=f"pl_va_overlay_y_{profile}")
    long = overlay_frame([(s["label"], s["frame"]) for s in selected], x, y)
    if long.empty:
        st.warning("No finite common X/Y records are available.")
        return None
    fig = go.Figure()
    for label, group in long.groupby("source", sort=False):
        fig.add_trace(go.Scatter(x=group["x"], y=group["y"], mode="lines+markers", name=str(label), customdata=group[["source_row"]]))
    fig.update_layout(title=f"Multi-source overlay · {y} vs {x}", xaxis_title=x, yaxis_title=y, height=650, hovermode="closest")
    _selection_plot(st, fig, key=f"pl_va_overlay_plot_{profile}", row_count=len(long))
    st.dataframe(long.head(500), hide_index=True, width="stretch")
    st.caption("Overlay only shows sources on shared field names. It does not assert that units, calibration, model assumptions, or experimental conditions are equivalent.")
    return {
        "kind": "multi-source-overlay",
        "sources": [{"id": s["id"], "identity": s.get("identity")} for s in selected],
        "x": x,
        "y": y,
    }


def _dashboard_controls(st: Any, project_path: Path, profile: str, panel: dict[str, Any] | None) -> None:
    key = f"pl_va_panels_{profile}"
    panels = list(st.session_state.get(key) or [])
    c1, c2 = st.columns(2)
    if c1.button("Add current analysis as dashboard panel", disabled=panel is None, key=f"pl_va_add_panel_{profile}") and panel is not None:
        panels.append(panel)
        st.session_state[key] = panels
        st.rerun()
    if c2.button("Clear dashboard draft", disabled=not panels, key=f"pl_va_clear_panels_{profile}"):
        st.session_state[key] = []
        st.rerun()
    if not panels:
        st.caption("No dashboard panels collected yet.")
        return
    st.markdown("##### Dashboard draft")
    st.dataframe([{"panel": i + 1, "kind": p.get("kind"), "x": p.get("x"), "y": p.get("y")} for i, p in enumerate(panels)], hide_index=True, width="stretch")
    title = st.text_input("Dashboard title", value="Visual Analytics Dashboard", key=f"pl_va_dashboard_title_{profile}")
    if st.button("Save reproducible dashboard recipe", type="primary", key=f"pl_va_dashboard_save_{profile}"):
        try:
            saved = save_dashboard(project_path, title=title, panels=panels)
            st.success(f"Saved {saved['dashboard_id']} · sha256 {saved['sha256'][:16]}…")
        except Exception as exc:
            st.error(f"Could not save dashboard recipe: {exc}")


def render_visual_analytics(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use Visual Analytics.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Visual Analytics Workbench")
    st.caption("Uncertainty-aware plotting, linked point selection, multi-source overlays and reproducible dashboard recipes. These are analytical views over existing evidence, not new evidence.")
    if not sources:
        st.info("No project results, completed sweeps, or canonical datasets are available yet.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    chosen = st.selectbox("Primary source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_va_primary_{profile}")
    source = next(s for s in sources if s["id"] == chosen)
    a, b, c = st.columns(3)
    a.metric("Source type", source["kind"])
    b.metric("Rows", len(source["frame"]))
    c.metric("Numeric fields", len(numeric_columns(source["frame"])))
    tab_unc, tab_overlay, tab_dash = st.tabs(["Uncertainty + Selection", "Multi-run Overlay", "Dashboard Recipe"])
    panel: dict[str, Any] | None = None
    with tab_unc:
        panel = _uncertainty_tab(st, source, profile)
    with tab_overlay:
        overlay_panel = _overlay_tab(st, sources, profile)
        if overlay_panel is not None:
            st.session_state[f"pl_va_last_overlay_{profile}"] = overlay_panel
    with tab_dash:
        choice = st.radio("Panel source for dashboard", ["Current uncertainty view", "Last overlay view"], horizontal=True, key=f"pl_va_panel_choice_{profile}")
        dashboard_panel = panel if choice == "Current uncertainty view" else st.session_state.get(f"pl_va_last_overlay_{profile}")
        _dashboard_controls(st, project_path, profile, dashboard_panel)
    st.caption(BOUNDARY)
