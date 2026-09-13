"""Scientific analysis, correlation and Pareto workspace for Engineering Lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_result_inspector import load_project_result
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_tradeoff_analysis import BOUNDARY as TRADEOFF_BOUNDARY, correlation_matrix, pareto_frontier
from physical_lab_visual_analytics import (
    axis_label,
    contract_field_metadata,
    convert_series,
    convertible_units,
    elasticity_sensitivity,
    field_metadata,
    local_sensitivity,
    response_surface,
    response_surface_slice,
    save_science_analysis_recipe,
    standardized_sensitivity,
    uncertainty_plot_record,
    uncertainty_records,
)


def _raw_result(project_path: Path, source: dict[str, Any]) -> dict[str, Any] | None:
    source_id = str(source.get("id") or "")
    if not source_id.startswith("result:"):
        return None
    try:
        result, _identity = load_project_result(project_path, source_id.split(":", 1)[1])
        return dict(result)
    except Exception:
        return None


def _save_recipe(st: Any, project_path: Path, source: dict[str, Any], analysis: dict[str, Any], profile: str, suffix: str) -> None:
    if st.button("Save Science Analysis Recipe", key=f"pl_science_recipe_{profile}_{suffix}"):
        identity = dict(source.get("identity") or {})
        identity.setdefault("source_id", source.get("id"))
        identity.setdefault("source_kind", source.get("kind"))
        try:
            saved = save_science_analysis_recipe(project_path, source_identity=identity, analysis=analysis)
            st.success(f"Saved {saved['recipe_id']} · sha256 {saved['sha256'][:16]}…")
        except Exception as exc:
            st.error(f"Could not save analysis recipe: {exc}")


def _render_semantics(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame = source["frame"]
    numeric = numeric_columns(frame)
    result = _raw_result(project_path, source)
    t1, t2 = st.tabs(["Units & contracts", "Native UQ"])
    with t1:
        if result is None:
            units = dict(source.get("units") or {})
            st.dataframe([{"field": c, "unit": units.get(c, "unspecified")} for c in numeric], hide_index=True, width="stretch")
            st.caption("Units are shown only when explicitly stored; names are never used to guess physical dimensions.")
        else:
            rows = []
            for field in numeric:
                clean = field[2:] if field.startswith("$.") else field
                rows.append({"frame_field": field, **field_metadata(result, clean)})
            st.dataframe(rows, hide_index=True, width="stretch")
            registered = [r for r in rows if r.get("registered") and r.get("unit") and r.get("frame_field") in frame.columns]
            if registered:
                selected = st.selectbox("Field for unit conversion preview", [r["frame_field"] for r in registered], key=f"pl_science_sem_field_{profile}")
                row = next(r for r in registered if r["frame_field"] == selected)
                original = str(row.get("unit") or "")
                targets = convertible_units(original) or [original]
                target = st.selectbox("Display unit", targets, key=f"pl_science_sem_target_{profile}")
                values = convert_series(frame[selected].tolist(), original, target)
                preview = pd.DataFrame({"row": range(len(values)), axis_label(selected, target): values})
                st.line_chart(preview.set_index("row"), height=320)
                st.caption(f"Display conversion only: {original} → {target}. Stored evidence is unchanged.")
            elif not contract_field_metadata(result):
                st.warning("This result schema has no registered contract; units and scientific quantities are not inferred.")
            else:
                st.caption("The current plotted fields have no explicit convertible unit in the registered contract.")
    with t2:
        if result is None:
            st.info("Native physical-lab-uncertainty-v1 objects are available on Project results.")
            return
        records = uncertainty_records(result)
        if not records:
            st.info("No explicit uncertainty object is present. Residual/error fields are not reinterpreted as uncertainty.")
            return
        st.dataframe(records, hide_index=True, width="stretch")
        valid = [r for r in records if r.get("valid")]
        if not valid:
            st.warning("Uncertainty objects were found, but none passed structural validation.")
            return
        path = st.selectbox("Uncertainty object", [str(r["path"]) for r in valid], key=f"pl_science_native_uq_{profile}")
        record = next(r for r in valid if str(r["path"]) == path)
        plotted = uncertainty_plot_record(record)
        error_y = None
        if plotted.get("error_plus") is not None:
            error_y = {"type": "data", "array": [plotted["error_plus"]], "arrayminus": [plotted["error_minus"]], "visible": True}
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[path], y=[plotted["estimate"]], mode="markers", marker={"size": 12}, error_y=error_y))
        fig.update_layout(height=420, yaxis_title=axis_label("estimate", plotted.get("unit")), title=f"Explicit UQ · {plotted['kind']}")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.json({"method": record.get("method"), "coverage_factor": record.get("coverage_factor"), "coverage_probability": record.get("coverage_probability"), "sha256": record.get("sha256")})
        st.caption("Structural validity does not establish completeness or correctness of the uncertainty model.")


def _render_sensitivity_surface(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame = source["frame"]
    numeric = numeric_columns(frame)
    t1, t2 = st.tabs(["Sensitivity", "Response Surface"])
    with t1:
        if len(numeric) < 2:
            st.info("At least two numeric fields are required.")
        else:
            output = st.selectbox("Output / response", numeric, index=min(1, len(numeric)-1), key=f"pl_science_sens_out_{profile}")
            params = [c for c in numeric if c != output]
            selected = st.multiselect("Candidate parameters", params, default=params[:min(6, len(params))], key=f"pl_science_sens_params_{profile}")
            screening = standardized_sensitivity(frame, selected, output) if selected else pd.DataFrame()
            if not screening.empty:
                fig = px.bar(screening, x="parameter", y="abs_standardized_slope", hover_data=["standardized_slope", "spearman", "n"], title=f"Sensitivity screening → {output}")
                fig.update_layout(height=500, yaxis_title="|standardized slope|")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.dataframe(screening, hide_index=True, width="stretch")
            local_parameter = st.selectbox("Local finite-difference parameter", params, key=f"pl_science_local_param_{profile}")
            try:
                local = elasticity_sensitivity(frame, local_parameter, output)
                c1, c2 = st.columns(2)
                with c1:
                    fig = px.line(local, x="parameter_center", y="sensitivity", markers=True, title=f"Local Δ{output} / Δ{local_parameter}")
                    fig.update_layout(height=420)
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                with c2:
                    fig = px.line(local, x="parameter_center", y="elasticity", markers=True, title="Local dimensionless elasticity")
                    fig.update_layout(height=420)
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.dataframe(local, hide_index=True, width="stretch")
            except Exception as exc:
                st.caption(f"Local sensitivity unavailable: {exc}")
            _save_recipe(st, project_path, source, {"kind": "sensitivity", "output": output, "parameters": selected, "local_parameter": local_parameter}, profile, "sensitivity")
            st.caption("Sensitivity is descriptive screening of the available table, not causal attribution or global Sobol analysis.")
    with t2:
        if len(numeric) < 3:
            st.info("At least three numeric fields are required.")
            return
        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.8])
        x = c1.selectbox("X parameter", numeric, key=f"pl_science_surface_x_{profile}")
        y = c2.selectbox("Y parameter", [c for c in numeric if c != x], key=f"pl_science_surface_y_{profile}")
        z = c3.selectbox("Response Z", [c for c in numeric if c not in {x, y}], key=f"pl_science_surface_z_{profile}")
        agg = c4.selectbox("Aggregate", ["mean", "median", "min", "max"], key=f"pl_science_surface_agg_{profile}")
        try:
            surface = response_surface(frame, x, y, z, agg=agg)
        except Exception as exc:
            st.warning(f"Response surface unavailable: {exc}")
            return
        m1, m2, m3 = st.columns(3)
        m1.metric("Rows", surface["rows"]); m2.metric("Grid cells", surface["grid_cells"]); m3.metric("Finite cells", surface["coverage"])
        mode = st.radio("Surface view", ["Heatmap", "Contour", "3D Surface"], horizontal=True, key=f"pl_science_surface_mode_{profile}")
        if mode == "Heatmap":
            fig = go.Figure(data=go.Heatmap(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z}))
        elif mode == "Contour":
            fig = go.Figure(data=go.Contour(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z}, contours={"showlabels": True}))
        else:
            fig = go.Figure(data=[go.Surface(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z})])
            fig.update_layout(scene={"xaxis_title": x, "yaxis_title": y, "zaxis_title": z})
        fig.update_layout(title=f"{z} over {x} × {y} · {agg}", height=650)
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
        coverage = surface["coverage"] / max(surface["grid_cells"], 1)
        st.caption(f"Grid coverage: {coverage:.1%}. Missing parameter combinations are not interpolated or invented.")

        s1, s2 = st.columns(2)
        slice_axis = s1.radio("Slice axis", ["x", "y"], horizontal=True, key=f"pl_science_slice_axis_{profile}")
        count = len(surface[slice_axis])
        slice_index = int(s2.number_input("Slice index", min_value=0, max_value=max(count-1, 0), value=0, step=1, key=f"pl_science_slice_index_{profile}"))
        try:
            sliced = response_surface_slice(surface, axis=slice_axis, index=slice_index)
            fig = px.line(sliced, x="coordinate", y="response", markers=True, title=f"Slice · fixed {slice_axis}={sliced['fixed_value'].iloc[0]:g}")
            fig.update_layout(height=420)
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(sliced, hide_index=True, width="stretch")
        except Exception as exc:
            st.caption(f"Surface slice unavailable: {exc}")
        _save_recipe(st, project_path, source, {"kind": "response-surface", "x": x, "y": y, "z": z, "aggregation": agg, "view": mode, "slice_axis": slice_axis, "slice_index": slice_index}, profile, "surface")


def render_tradeoff_analysis(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use the Science Analysis workspace.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Science Analysis · Semantics, Sensitivity & Trade-offs")
    st.caption("Explicit units/UQ, sensitivity screening, response surfaces, descriptive correlation and two-objective Pareto analysis over existing evidence.")
    if not sources:
        st.info("No project results, completed sweeps, or canonical datasets are available yet.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Analysis source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_tradeoff_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)
    frame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 1:
        st.warning("This source does not contain numeric fields.")
        return
    tab_sem, tab_sens, tab_corr, tab_pareto = st.tabs(["Scientific Semantics", "Sensitivity + Surface", "Correlation Matrix", "Pareto Frontier"])
    with tab_sem:
        _render_semantics(st, project_path, source, profile)
    with tab_sens:
        _render_sensitivity_surface(st, project_path, source, profile)
    with tab_corr:
        if len(numeric) < 2:
            st.info("At least two numeric fields are required.")
        else:
            columns = st.multiselect("Numeric fields", numeric, default=numeric[:min(8, len(numeric))], key=f"pl_tradeoff_corr_cols_{profile}")
            method = st.radio("Method", ["pearson", "spearman"], horizontal=True, key=f"pl_tradeoff_corr_method_{profile}")
            if len(columns) >= 2:
                try:
                    corr = correlation_matrix(frame, columns, method=method)
                    fig = px.imshow(corr, text_auto=".2f", zmin=-1, zmax=1, aspect="auto", title=f"{method.title()} correlation")
                    fig.update_layout(height=max(520, 52 * len(columns)))
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                    st.dataframe(corr, width="stretch")
                    _save_recipe(st, project_path, source, {"kind": "correlation", "fields": columns, "method": method}, profile, "correlation")
                    st.caption("Correlation summarizes association only; it does not establish causality or model validity.")
                except Exception as exc:
                    st.warning(f"Correlation matrix unavailable: {exc}")
    with tab_pareto:
        if len(numeric) < 2:
            st.info("At least two numeric fields are required.")
        else:
            c1, c2 = st.columns(2)
            x = c1.selectbox("Objective X", numeric, key=f"pl_tradeoff_x_{profile}")
            y = c2.selectbox("Objective Y", [c for c in numeric if c != x], key=f"pl_tradeoff_y_{profile}")
            d1, d2 = st.columns(2)
            x_goal = d1.radio("X direction", ["min", "max"], horizontal=True, key=f"pl_tradeoff_xgoal_{profile}")
            y_goal = d2.radio("Y direction", ["min", "max"], horizontal=True, key=f"pl_tradeoff_ygoal_{profile}")
            try:
                result = pareto_frontier(frame, x=x, x_goal=x_goal, y=y, y_goal=y_goal)
                if result.empty:
                    st.info("No finite objective pairs are available.")
                else:
                    frontier = result[result["pareto"]].copy(); dominated = result[~result["pareto"]].copy(); fig = go.Figure()
                    if not dominated.empty:
                        fig.add_trace(go.Scatter(x=dominated[x], y=dominated[y], mode="markers", name="Dominated", customdata=dominated[["source_index"]]))
                    if not frontier.empty:
                        ordered = frontier.sort_values(x)
                        fig.add_trace(go.Scatter(x=ordered[x], y=ordered[y], mode="lines+markers", name="Pareto frontier", customdata=ordered[["source_index"]]))
                    fig.update_layout(title=f"Pareto trade-off · {x_goal} {x} / {y_goal} {y}", xaxis_title=x, yaxis_title=y, height=620, hovermode="closest")
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
                    m1, m2, m3 = st.columns(3); m1.metric("Finite points", len(result)); m2.metric("Pareto points", int(result["pareto"].sum())); m3.metric("Dominated", int((~result["pareto"]).sum()))
                    st.dataframe(frontier[["source_index", x, y]], hide_index=True, width="stretch")
                    _save_recipe(st, project_path, source, {"kind": "pareto", "x": x, "x_goal": x_goal, "y": y, "y_goal": y_goal}, profile, "pareto")
                    st.caption("Pareto status is non-dominance only for the selected objectives/directions; feasibility, UQ and validity remain separate.")
            except Exception as exc:
                st.warning(f"Pareto analysis unavailable: {exc}")
    st.caption(TRADEOFF_BOUNDARY)
