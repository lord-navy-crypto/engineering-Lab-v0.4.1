"""Scientific analysis, comparison and trade-off workspace for Engineering Lab."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets
from physical_lab_result_inspector import load_project_result
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_tradeoff_analysis import (
    BOUNDARY as TRADEOFF_BOUNDARY,
    convert_comparison_values,
    correlation_matrix,
    pareto_frontier,
    robust_sensitivity_summary,
    save_analysis_summary,
    unit_aware_comparison_contract,
)
from physical_lab_visual_analytics import (
    axis_label,
    common_numeric_columns,
    contract_field_metadata,
    convert_series,
    convertible_units,
    elasticity_sensitivity,
    field_metadata,
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


def _source_unit(project_path: Path, source: dict[str, Any], field: str) -> str:
    if source.get("kind") == "result":
        result = _raw_result(project_path, source)
        if result is not None:
            clean = field[2:] if str(field).startswith("$.") else str(field)
            return str(field_metadata(result, clean).get("unit") or "")
    if source.get("kind") == "dataset":
        dataset_id = str((source.get("identity") or {}).get("dataset_id") or "")
        try:
            for dataset in list_canonical_datasets(project_path):
                if str(dataset.get("dataset_id") or "") == dataset_id:
                    return str((dataset.get("units") or {}).get(field) or "")
        except Exception:
            pass
    return str((source.get("units") or {}).get(field) or "")


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


def _analysis_recommendations(question: str, source_kind: str, numeric_count: int, has_native_uq: bool) -> list[dict[str, str]]:
    text = str(question or "").lower().strip()
    rows: list[dict[str, str]] = []
    def add(tab: str, tool: str, reason: str) -> None:
        if not any(r["tool"] == tool for r in rows):
            rows.append({"tab": tab, "tool": tool, "reason": reason})
    if any(k in text for k in ("uncert", "confidence", "interval", "error bar", "误差", "不确定")):
        add("Scientific Semantics", "Native UQ", "Inspect explicit physical-lab-uncertainty-v1 objects instead of reinterpreting residual/error fields.")
    if any(k in text for k in ("unit", "convert", "dimension", "compare run", "单位", "换算", "比较")):
        add("Unit-aware Compare", "Strict unit comparison", "Compare runs only when both axes have explicit compatible units.")
    if any(k in text for k in ("sensitive", "sensitivity", "influence", "affect", "important parameter", "robust", "影响", "敏感")):
        add("Sensitivity + Surface", "Robust sensitivity screening", "Inspect standardized slope, rank association, local slopes, sign consistency and elasticity separately.")
    if any(k in text for k in ("surface", "heatmap", "interaction", "2d", "grid", "响应面", "交互")):
        add("Sensitivity + Surface", "Response Surface", "Inspect observed two-parameter response structure without inventing missing grid cells.")
    if any(k in text for k in ("trade", "pareto", "balance", "compromise", "optimum", "optimal", "权衡", "最优")):
        add("Pareto Frontier", "Pareto analysis", "Find non-dominated candidates for two explicitly chosen objective directions.")
    if any(k in text for k in ("correl", "relationship", "association", "related", "相关", "关系")):
        add("Correlation Matrix", "Correlation", "Inspect descriptive Pearson/Spearman association; correlation is not causality.")
    if any(k in text for k in ("report", "summary", "export", "汇总", "报告")):
        add("Analysis Summary", "Reproducible summary", "Combine saved Science Analysis Recipes into content-addressed JSON and Markdown artifacts.")
    if not rows:
        if source_kind == "sweep" and numeric_count >= 3:
            add("Sensitivity + Surface", "Sensitivity + Response Surface", "Completed sweeps are naturally suited to parameter screening and response-surface inspection.")
            add("Pareto Frontier", "Pareto analysis", "A sweep can also be screened for two-objective trade-offs.")
        elif source_kind == "result":
            add("Scientific Semantics", "Contracts + Native UQ", "Start by checking explicit result semantics, units and uncertainty objects.")
        elif numeric_count >= 2:
            add("Correlation Matrix", "Correlation", "A numeric table can be explored descriptively before choosing a stronger scientific interpretation.")
    if has_native_uq:
        add("Scientific Semantics", "Native UQ", "This result contains an explicit uncertainty object that can be inspected directly.")
    return rows[:5]


def _render_semantics(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame = source["frame"]
    numeric = numeric_columns(frame)
    result = _raw_result(project_path, source)
    t1, t2 = st.tabs(["Units & contracts", "Native UQ"])
    with t1:
        if result is None:
            units = {field: _source_unit(project_path, source, field) for field in numeric}
            st.dataframe([{"field": c, "unit": units.get(c) or "unspecified"} for c in numeric], hide_index=True, width="stretch")
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
            return
        output = st.selectbox("Output / response", numeric, index=min(1, len(numeric)-1), key=f"pl_science_sens_out_{profile}")
        params = [c for c in numeric if c != output]
        selected = st.multiselect("Candidate parameters", params, default=params[:min(6, len(params))], key=f"pl_science_sens_params_{profile}")
        screening = standardized_sensitivity(frame, selected, output) if selected else pd.DataFrame()
        if not screening.empty:
            fig = px.bar(screening, x="parameter", y="abs_standardized_slope", hover_data=["standardized_slope", "spearman", "n"], title=f"Sensitivity screening → {output}")
            fig.update_layout(height=460, yaxis_title="|standardized slope|")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        robust = robust_sensitivity_summary(frame, selected, output) if selected else pd.DataFrame()
        if not robust.empty:
            st.markdown("##### Robust descriptive sensitivity summary")
            st.dataframe(robust, hide_index=True, width="stretch")
            st.caption("No synthetic master score is created. Standardized slope, Spearman association, local slope stability and elasticity remain separate diagnostics.")
        local_parameter = st.selectbox("Local finite-difference parameter", params, key=f"pl_science_local_param_{profile}")
        try:
            local = elasticity_sensitivity(frame, local_parameter, output)
            c1, c2 = st.columns(2)
            with c1:
                fig = px.line(local, x="parameter_center", y="sensitivity", markers=True, title=f"Local Δ{output} / Δ{local_parameter}")
                fig.update_layout(height=400)
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            with c2:
                fig = px.line(local, x="parameter_center", y="elasticity", markers=True, title="Local dimensionless elasticity")
                fig.update_layout(height=400)
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        except Exception as exc:
            st.caption(f"Local sensitivity unavailable: {exc}")
        _save_recipe(st, project_path, source, {"kind": "robust-sensitivity", "output": output, "parameters": selected, "local_parameter": local_parameter}, profile, "sensitivity")
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
        fig.update_layout(title=f"{z} over {x} × {y} · {agg}", height=620)
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
            fig.update_layout(height=400)
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(sliced, hide_index=True, width="stretch")
        except Exception as exc:
            st.caption(f"Surface slice unavailable: {exc}")
        _save_recipe(st, project_path, source, {"kind": "response-surface", "x": x, "y": y, "z": z, "aggregation": agg, "view": mode, "slice_axis": slice_axis, "slice_index": slice_index}, profile, "surface")


def _render_unit_compare(st: Any, project_path: Path, sources: list[dict[str, Any]], profile: str) -> None:
    if len(sources) < 2:
        st.info("At least two sources are required for a unit-aware comparison.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    chosen_ids = st.multiselect("Sources", [s["id"] for s in sources], default=[s["id"] for s in sources[:2]], format_func=lambda x: labels.get(x, x), key=f"pl_science_compare_sources_{profile}")
    chosen = [s for s in sources if s["id"] in chosen_ids]
    if len(chosen) < 2:
        st.info("Select at least two sources.")
        return
    common = common_numeric_columns([s["frame"] for s in chosen])
    if len(common) < 2:
        st.warning("Selected sources do not share at least two numeric field names.")
        return
    a, b = st.columns(2)
    x = a.selectbox("Common X field", common, key=f"pl_science_compare_x_{profile}")
    y = b.selectbox("Common Y field", [c for c in common if c != x], key=f"pl_science_compare_y_{profile}")
    x_sources = [{"id": s["id"], "unit": _source_unit(project_path, s, x)} for s in chosen]
    y_sources = [{"id": s["id"], "unit": _source_unit(project_path, s, y)} for s in chosen]
    x_contract = unit_aware_comparison_contract(x_sources)
    y_contract = unit_aware_comparison_contract(y_sources)
    st.dataframe([
        {"axis": "X", "field": x, "status": x_contract["status"], "target_unit": x_contract.get("target_unit")},
        {"axis": "Y", "field": y, "status": y_contract["status"], "target_unit": y_contract.get("target_unit")},
    ], hide_index=True, width="stretch")
    if not x_contract["comparable"] or not y_contract["comparable"]:
        st.warning("Strict comparison is blocked because at least one axis has unspecified or incompatible units. Add explicit units/contracts instead of overriding this check.")
        return
    target_x = str(x_contract["target_unit"]); target_y = str(y_contract["target_unit"])
    fig = go.Figure()
    for source in chosen:
        xu = _source_unit(project_path, source, x); yu = _source_unit(project_path, source, y)
        xv = convert_comparison_values(source["frame"][x].tolist(), xu, target_x)
        yv = convert_comparison_values(source["frame"][y].tolist(), yu, target_y)
        plot = pd.DataFrame({"x": xv, "y": yv}).dropna()
        fig.add_trace(go.Scatter(x=plot["x"], y=plot["y"], mode="lines+markers", name=source["label"]))
    fig.update_layout(title=f"Unit-aware comparison · {y} vs {x}", xaxis_title=axis_label(x, target_x), yaxis_title=axis_label(y, target_y), height=620, hovermode="closest")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
    st.caption("Compatible units permit representation on one axis. They do not establish equivalent calibration, provenance, experimental conditions or model assumptions.")


def _render_summary(st: Any, project_path: Path, profile: str) -> None:
    root = project_path / "reports" / "science-analysis-recipes"
    records: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.glob("science-*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(record, dict) and record.get("analysis"):
                    records.append(record)
            except Exception:
                continue
    if not records:
        st.info("Save one or more Science Analysis Recipes first.")
        return
    labels = {str(r.get("recipe_id")): f"{r.get('recipe_id')} · {(r.get('analysis') or {}).get('kind', 'analysis')}" for r in records}
    selected_ids = st.multiselect("Recipes to include", list(labels), default=list(labels)[:min(4, len(labels))], format_func=lambda x: labels[x], key=f"pl_science_summary_recipes_{profile}")
    selected = [r for r in records if str(r.get("recipe_id")) in selected_ids]
    title = st.text_input("Summary title", value="Science Analysis Summary", key=f"pl_science_summary_title_{profile}")
    if selected:
        st.dataframe([{"recipe_id": r.get("recipe_id"), "kind": (r.get("analysis") or {}).get("kind"), "sha256": str(r.get("sha256") or "")[:16]} for r in selected], hide_index=True, width="stretch")
    if st.button("Generate reproducible analysis summary", disabled=not selected, type="primary", key=f"pl_science_summary_build_{profile}"):
        source_identity = {"project": project_path.name, "recipe_ids": [r.get("recipe_id") for r in selected]}
        analyses = [{"recipe_id": r.get("recipe_id"), **dict(r.get("analysis") or {})} for r in selected]
        try:
            saved = save_analysis_summary(project_path, title=title, source_identity=source_identity, analyses=analyses)
            st.session_state[f"pl_science_summary_last_{profile}"] = saved
        except Exception as exc:
            st.error(f"Could not generate summary: {exc}")
    saved = st.session_state.get(f"pl_science_summary_last_{profile}")
    if saved:
        json_path = Path(saved["json_path"]); md_path = Path(saved["markdown_path"])
        st.success(f"Saved {saved['summary_id']} · sha256 {saved['sha256'][:16]}…")
        if md_path.exists():
            st.download_button("Download Markdown summary", data=md_path.read_bytes(), file_name=md_path.name, mime="text/markdown", key=f"pl_science_summary_md_{profile}")
        if json_path.exists():
            st.download_button("Download JSON summary", data=json_path.read_bytes(), file_name=json_path.name, mime="application/json", key=f"pl_science_summary_json_{profile}")
        st.caption("Summary files live under reports/science-analysis-summaries and therefore enter the existing reproducibility pack.")


def render_tradeoff_analysis(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use the Science Analysis workspace.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Science Analysis · Semantics, Sensitivity & Trade-offs")
    st.caption("Explicit units/UQ, robust sensitivity screening, strict unit-aware comparison, response surfaces, correlation, Pareto analysis and reproducible summaries over existing evidence.")
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
    question = st.text_input("What are you trying to understand?", placeholder="e.g. Which parameter most affects the output?", key=f"pl_science_question_{profile}")
    raw = _raw_result(project_path, source)
    has_native_uq = bool(uncertainty_records(raw)) if raw is not None else False
    recommendations = _analysis_recommendations(question, str(source.get("kind") or ""), len(numeric), has_native_uq)
    if recommendations:
        with st.expander("Recommended analysis path", expanded=bool(question.strip())):
            st.dataframe(recommendations, hide_index=True, width="stretch")
            st.caption("Recommendations route you to existing analytical views. They do not infer scientific conclusions or validate the data.")
    tab_sem, tab_sens, tab_compare, tab_corr, tab_pareto, tab_summary = st.tabs(["Scientific Semantics", "Sensitivity + Surface", "Unit-aware Compare", "Correlation Matrix", "Pareto Frontier", "Analysis Summary"])
    with tab_sem:
        _render_semantics(st, project_path, source, profile)
    with tab_sens:
        _render_sensitivity_surface(st, project_path, source, profile)
    with tab_compare:
        _render_unit_compare(st, project_path, sources, profile)
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
    with tab_summary:
        _render_summary(st, project_path, profile)
    st.caption(TRADEOFF_BOUNDARY)
