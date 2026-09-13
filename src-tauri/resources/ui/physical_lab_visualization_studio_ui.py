"""Interactive, model-agnostic Visualization Studio for Engineering Lab."""
from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets
from physical_lab_result_inspector import load_project_result
from physical_lab_sweep_executor import ADAPTERS, available_adapters, create_sweep_job, list_sweep_jobs, read_sweep_result, start_sweep_job
from physical_lab_visualization_studio import (
    BOUNDARY,
    axis_values,
    build_scan_design,
    dataset_frame,
    matrix_by_path,
    numeric_columns,
    numeric_inventory,
    result_frame,
    summary,
    sweep_frame,
    transform,
)

RECIPE_SCHEMA = "engineering-lab-visualization-recipe-v1"


def _adapter_signature(adapter: str) -> tuple[list[str], dict[str, Any]]:
    spec = ADAPTERS.get(adapter) or {}
    try:
        module = importlib.import_module(str(spec.get("module") or ""))
        fn = getattr(module, str(spec.get("function") or ""))
        sig = inspect.signature(fn)
    except Exception:
        return [], {}
    names: list[str] = []
    defaults: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if param.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        names.append(name)
        if param.default is not inspect.Parameter.empty and isinstance(param.default, (int, float)) and not isinstance(param.default, bool):
            defaults[name] = param.default
    return names, defaults


def _select_source(st: Any, project_path: Path, profile: str):
    doc = projects.open_project(project_path)
    project_results = dict(doc.get("results") or {})
    sweep_jobs = [j for j in list_sweep_jobs(limit=100) if j.get("status") == "succeeded" and read_sweep_result(str(j.get("id"))) is not None]
    datasets = list_canonical_datasets(project_path)
    choices = []
    if project_results:
        choices.append("Project result")
    if sweep_jobs:
        choices.append("Sweep campaign")
    if datasets:
        choices.append("Canonical dataset")
    if not choices:
        st.info("No project result, completed sweep, or canonical dataset is available yet.")
        return None
    source = st.radio("Visualization source", choices, horizontal=True, key=f"pl_vizstudio_source_{profile}")
    if source == "Project result":
        job_id = st.selectbox("Project result", list(project_results), key=f"pl_vizstudio_result_{profile}")
        result, identity = load_project_result(project_path, job_id)
        return {"kind": "result", "label": job_id, "frame": result_frame(result), "raw": result, "identity": identity}
    if source == "Sweep campaign":
        ids = [str(job["id"]) for job in sweep_jobs]
        job_id = st.selectbox("Sweep campaign", ids, key=f"pl_vizstudio_sweep_{profile}")
        result = read_sweep_result(job_id) or {}
        return {"kind": "sweep", "label": job_id, "frame": sweep_frame(result), "raw": result, "identity": {"sweep_job_id": job_id}}
    ids = [str(d.get("dataset_id")) for d in datasets]
    dataset_id = st.selectbox("Canonical dataset", ids, key=f"pl_vizstudio_dataset_{profile}")
    dataset = next(d for d in datasets if str(d.get("dataset_id")) == dataset_id)
    return {"kind": "dataset", "label": dataset_id, "frame": dataset_frame(dataset), "raw": dataset, "identity": {"dataset_id": dataset_id, "sha256": dataset.get("sha256")}}


def _filter_frame(st: Any, frame: pd.DataFrame, profile: str) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    numeric = numeric_columns(frame)
    if not numeric:
        return frame, None
    enabled = st.toggle("Filter rows by numeric range", value=False, key=f"pl_vizstudio_filter_on_{profile}")
    if not enabled:
        return frame, None
    column = st.selectbox("Filter field", numeric, key=f"pl_vizstudio_filter_col_{profile}")
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return frame, None
    lo, hi = float(values.min()), float(values.max())
    if lo == hi:
        st.caption(f"{column} is constant at {lo:g}; no range filter is needed.")
        return frame, {"field": column, "min": lo, "max": hi}
    selected = st.slider("Visible range", min_value=lo, max_value=hi, value=(lo, hi), key=f"pl_vizstudio_filter_range_{profile}")
    series = pd.to_numeric(frame[column], errors="coerce")
    return frame[(series >= selected[0]) & (series <= selected[1])].copy(), {"field": column, "min": float(selected[0]), "max": float(selected[1])}


def _derived_variable(st: Any, frame: pd.DataFrame, profile: str) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    numeric = numeric_columns(frame)
    if not numeric or not st.toggle("Create safe derived variable", value=False, key=f"pl_vizstudio_derived_on_{profile}"):
        return frame, None
    op = st.selectbox("Derived operation", ["A - B", "A + B", "A × B", "A / B", "|A|", "ΔA", "ΔA / ΔB"], key=f"pl_vizstudio_derived_op_{profile}")
    c1, c2, c3 = st.columns(3)
    a = c1.selectbox("A", numeric, key=f"pl_vizstudio_derived_a_{profile}")
    needs_b = op in {"A - B", "A + B", "A × B", "A / B", "ΔA / ΔB"}
    b_options = [x for x in numeric if x != a] or numeric
    b = c2.selectbox("B", b_options, disabled=not needs_b, key=f"pl_vizstudio_derived_b_{profile}")
    name = c3.text_input("Derived field name", value=f"derived:{op}", key=f"pl_vizstudio_derived_name_{profile}").strip() or f"derived:{op}"
    out = frame.copy()
    sa = pd.to_numeric(out[a], errors="coerce")
    sb = pd.to_numeric(out[b], errors="coerce") if needs_b else None
    if op == "A - B": out[name] = sa - sb
    elif op == "A + B": out[name] = sa + sb
    elif op == "A × B": out[name] = sa * sb
    elif op == "A / B": out[name] = sa / sb.where(sb != 0)
    elif op == "|A|": out[name] = sa.abs()
    elif op == "ΔA": out[name] = sa.diff()
    elif op == "ΔA / ΔB": out[name] = sa.diff() / sb.diff().where(sb.diff() != 0)
    return out, {"name": name, "operation": op, "a": a, "b": b if needs_b else None, "boundary": "safe predefined display derivation; no arbitrary expression evaluation"}


def _save_recipe(project_path: Path, recipe: dict[str, Any]) -> dict[str, Any]:
    payload = dict(recipe)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    record = {**payload, "recipe_id": f"viz-{digest[:20]}", "sha256": digest}
    root = project_path / "reports" / "visualization-recipes"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record['recipe_id']}.json"
    if not path.exists():
        path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return {**record, "path": str(path)}


def _render_tabular_plot(st: Any, frame: pd.DataFrame, profile: str, project_path: Path, source: dict[str, Any]) -> None:
    numeric = numeric_columns(frame)
    if not numeric:
        st.warning("The selected source has no numeric columns that can be plotted.")
        return
    frame, filter_spec = _filter_frame(st, frame, profile)
    frame, derived_spec = _derived_variable(st, frame, profile)
    numeric = numeric_columns(frame)
    if frame.empty:
        st.warning("The current filter removed all rows.")
        return

    c1, c2, c3 = st.columns([1.2, 1.3, 1.0])
    chart_type = c1.selectbox("Chart", ["Line", "Scatter", "Bar", "Histogram", "Heatmap", "3D Scatter"], key=f"pl_vizstudio_chart_{profile}")
    x = c2.selectbox("X axis", numeric, index=0, key=f"pl_vizstudio_x_{profile}")
    transform_mode = c3.selectbox("Y transform", ["raw", "absolute", "z-score", "min-max"], key=f"pl_vizstudio_transform_{profile}")

    available_y = [c for c in numeric if c != x] or [x]
    z_field = None
    if chart_type == "Histogram":
        ys = [st.selectbox("Histogram field", numeric, key=f"pl_vizstudio_hist_y_{profile}")]
    elif chart_type == "Heatmap":
        y = st.selectbox("Y axis", available_y, key=f"pl_vizstudio_heat_y_{profile}")
        colors = [c for c in numeric if c not in {x, y}] or [y]
        color = st.selectbox("Cell value", colors, key=f"pl_vizstudio_heat_z_{profile}")
        ys = [y, color]
    elif chart_type == "3D Scatter":
        y = st.selectbox("Y axis", available_y, key=f"pl_vizstudio_3d_y_{profile}")
        z_options = [c for c in numeric if c not in {x, y}] or [y]
        z_field = st.selectbox("Z axis", z_options, key=f"pl_vizstudio_3d_z_{profile}")
        ys = [y, z_field]
    else:
        ys = st.multiselect("Y axis / series", available_y, default=available_y[:1], key=f"pl_vizstudio_y_{profile}")
        if not ys:
            st.info("Select at least one Y field.")
            return

    c4, c5, c6 = st.columns(3)
    x_log = c4.toggle("Log X", value=False, key=f"pl_vizstudio_logx_{profile}")
    y_log = c5.toggle("Log Y", value=False, key=f"pl_vizstudio_logy_{profile}")
    title = c6.text_input("Title", value="DIY result view", key=f"pl_vizstudio_title_{profile}")

    plot_frame = transform(frame, ys, transform_mode)
    fig = None
    try:
        if chart_type == "Line": fig = px.line(plot_frame, x=x, y=ys, title=title)
        elif chart_type == "Scatter": fig = px.scatter(plot_frame, x=x, y=ys, title=title)
        elif chart_type == "Bar": fig = px.bar(plot_frame, x=x, y=ys, title=title)
        elif chart_type == "Histogram": fig = px.histogram(plot_frame, x=ys[0], title=title)
        elif chart_type == "3D Scatter": fig = px.scatter_3d(plot_frame, x=x, y=ys[0], z=z_field, title=title)
        else:
            y, color = ys
            pivot = plot_frame.pivot_table(index=y, columns=x, values=color, aggfunc="mean")
            fig = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index, colorbar={"title": color}))
            fig.update_layout(title=title, xaxis_title=x, yaxis_title=y)
        if x_log and chart_type not in {"Histogram", "3D Scatter"}:
            x_values = pd.to_numeric(plot_frame[x], errors="coerce").dropna()
            if not x_values.empty and (x_values > 0).all(): fig.update_xaxes(type="log")
            else: st.warning("Log X was skipped because visible X values are not all positive.")
        if y_log and chart_type not in {"Histogram", "Heatmap", "3D Scatter"}:
            visible = pd.concat([pd.to_numeric(plot_frame[col], errors="coerce") for col in ys]).dropna()
            if not visible.empty and (visible > 0).all(): fig.update_yaxes(type="log")
            else: st.warning("Log Y was skipped because visible Y values are not all positive.")
        fig.update_layout(height=620, hovermode="closest")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
    except Exception as exc:
        st.error(f"Could not render the selected view: {exc}")

    st.markdown("##### Important data")
    st.dataframe(summary(plot_frame, ys), hide_index=True, width="stretch")
    if ys:
        rank_field = st.selectbox("Rank important rows by", ys, key=f"pl_vizstudio_rank_field_{profile}")
        r1, r2 = st.columns(2)
        direction = r1.selectbox("Ranking", ["Largest", "Smallest"], key=f"pl_vizstudio_rank_dir_{profile}")
        rank_n = int(r2.number_input("Rows", min_value=1, max_value=min(50, max(len(plot_frame), 1)), value=min(5, max(len(plot_frame), 1)), step=1, key=f"pl_vizstudio_rank_n_{profile}"))
        ranked = plot_frame.assign(__rank=pd.to_numeric(plot_frame[rank_field], errors="coerce")).sort_values("__rank", ascending=(direction == "Smallest")).drop(columns=["__rank"]).head(rank_n)
        st.dataframe(ranked, hide_index=True, width="stretch")
    row_index = st.number_input("Inspect exact row", min_value=0, max_value=max(len(plot_frame) - 1, 0), value=0, step=1, key=f"pl_vizstudio_row_{profile}")
    if len(plot_frame): st.json(plot_frame.iloc[int(row_index)].to_dict())

    d1, d2 = st.columns(2)
    d1.download_button("Download current data CSV", data=plot_frame.to_csv(index=False).encode("utf-8"), file_name="engineering-lab-diy-view.csv", mime="text/csv", key=f"pl_vizstudio_download_{profile}")
    if fig is not None:
        d2.download_button("Download interactive plot HTML", data=fig.to_html(full_html=True, include_plotlyjs=True).encode("utf-8"), file_name="engineering-lab-diy-plot.html", mime="text/html", key=f"pl_vizstudio_html_{profile}")

    recipe = {
        "schema": RECIPE_SCHEMA,
        "created_at_unix": time.time(),
        "profile": profile,
        "source": {"kind": source.get("kind"), "label": source.get("label"), "identity": source.get("identity")},
        "view": {"chart_type": chart_type, "x": x, "y": ys, "z": z_field, "transform": transform_mode, "log_x": bool(x_log), "log_y": bool(y_log), "title": title, "filter": filter_spec, "derived": derived_spec},
        "boundary": BOUNDARY,
    }
    if st.button("Save reproducible View Recipe", key=f"pl_vizstudio_recipe_save_{profile}"):
        saved = _save_recipe(project_path, recipe)
        st.success(f"Saved {saved['recipe_id']} · sha256 {saved['sha256'][:16]}…")


def _render_result_matrices(st: Any, result: dict[str, Any], profile: str) -> None:
    matrices = [row for row in numeric_inventory(result) if row["kind"] == "matrix"]
    if not matrices:
        return
    st.markdown("##### Matrix / field viewer")
    path = st.selectbox("Matrix field", [str(row["path"]) for row in matrices], key=f"pl_vizstudio_matrix_{profile}")
    arr = matrix_by_path(result, path)
    mode = st.selectbox("Matrix display", ["raw", "absolute", "log10 |z|", "z-score"], key=f"pl_vizstudio_matrix_mode_{profile}")
    shown = arr.copy()
    if mode == "absolute": shown = abs(shown)
    elif mode == "log10 |z|":
        import numpy as np
        positive = abs(shown[shown != 0])
        if positive.size: shown = np.log10(np.maximum(abs(shown), float(positive.min())))
    elif mode == "z-score":
        sd = float(shown.std()); shown = (shown - float(shown.mean())) / sd if sd > 0 else shown * 0
    fig = go.Figure(data=go.Heatmap(z=shown))
    fig.update_layout(title=path, height=600)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})


def _render_scan_builder(st: Any, profile: str) -> None:
    st.markdown("#### DIY Parameter Scan Builder")
    st.caption("Build a bounded 1-D or 2-D parameter grid for an existing allow-listed model adapter. Parameter names are explicit; no arbitrary code is evaluated.")
    adapters = available_adapters(profile)
    if not adapters:
        st.info("No allow-listed sweep adapter is currently registered for this profile.")
        return
    adapter_ids = [a["id"] for a in adapters]
    labels = {a["id"]: a["label"] for a in adapters}
    adapter = st.selectbox("Model adapter", adapter_ids, format_func=lambda x: labels.get(x, x), key=f"pl_diy_scan_adapter_{profile}")
    parameters, defaults = _adapter_signature(adapter)
    if parameters:
        st.caption("Accepted model parameters: " + ", ".join(parameters))
        with st.expander("Numeric defaults", expanded=False): st.json(defaults)

    c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 0.8, 1])
    param_a = c1.text_input("Parameter A", value=(parameters[0] if parameters else "parameter"), key=f"pl_diy_scan_a_{profile}")
    start_a = c2.number_input("A start", value=float(defaults.get(param_a, 0.0)), key=f"pl_diy_scan_a0_{profile}")
    stop_a = c3.number_input("A stop", value=float(defaults.get(param_a, 1.0) or 1.0), key=f"pl_diy_scan_a1_{profile}")
    count_a = c4.number_input("A points", min_value=1, max_value=500, value=21, step=1, key=f"pl_diy_scan_an_{profile}")
    spacing_a = c5.selectbox("A spacing", ["linear", "log"], key=f"pl_diy_scan_as_{profile}")

    use_b = st.toggle("Add second scanned parameter (2-D grid)", value=False, key=f"pl_diy_scan_use_b_{profile}")
    param_b = ""; values_b = None
    if use_b:
        candidates = [p for p in parameters if p != param_a]
        d1, d2, d3, d4, d5 = st.columns([1.5, 1, 1, 0.8, 1])
        param_b = d1.text_input("Parameter B", value=(candidates[0] if candidates else "parameter_b"), key=f"pl_diy_scan_b_{profile}")
        start_b = d2.number_input("B start", value=float(defaults.get(param_b, 0.0)), key=f"pl_diy_scan_b0_{profile}")
        stop_b = d3.number_input("B stop", value=float(defaults.get(param_b, 1.0) or 1.0), key=f"pl_diy_scan_b1_{profile}")
        count_b = d4.number_input("B points", min_value=1, max_value=500, value=11, step=1, key=f"pl_diy_scan_bn_{profile}")
        spacing_b = d5.selectbox("B spacing", ["linear", "log"], key=f"pl_diy_scan_bs_{profile}")
        try: values_b = axis_values(float(start_b), float(stop_b), int(count_b), spacing_b)
        except Exception as exc: st.error(str(exc)); values_b = []

    fixed_text = st.text_area("Fixed numeric parameters (JSON object)", value="{}", height=100, key=f"pl_diy_scan_fixed_{profile}")
    try:
        fixed = json.loads(fixed_text or "{}")
        if not isinstance(fixed, dict): raise ValueError("fixed parameters must be a JSON object")
        values_a = axis_values(float(start_a), float(stop_a), int(count_a), spacing_a)
        design = build_scan_design(parameter_a=param_a, values_a=values_a, fixed=fixed, parameter_b=(param_b if use_b else None), values_b=values_b)
        st.caption(f"Preview · {len(design)} point(s), maximum 500")
        st.dataframe(design[:100], hide_index=True, width="stretch")
        if st.button("Create and start DIY scan", type="primary", key=f"pl_diy_scan_launch_{profile}"):
            job = create_sweep_job(profile, adapter, design)
            started = start_sweep_job(str(job["id"]))
            st.success(f"Started {started['id']} · {started['point_count']} point(s)")
            st.rerun()
    except Exception as exc:
        st.warning(f"Scan preview unavailable: {exc}")

    recent = list_sweep_jobs(profile=profile, limit=20)
    if recent:
        st.markdown("##### Recent scans")
        st.dataframe([{"id": r.get("id"), "adapter": r.get("adapter_label"), "points": r.get("point_count"), "status": r.get("status"), "progress": r.get("progress"), "failed": r.get("failed_points"), "cached": r.get("cached_points")} for r in recent], hide_index=True, width="stretch")


def render_visualization_studio(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use the Visualization Studio.")
        return
    project_path = Path(active)
    st.markdown("### Visualization Studio")
    st.caption("Choose what to look at after computation: axes, fields, filters, transforms, safe derived variables, chart type, matrix view and parameter scans are independent from the model implementation.")
    tab_plot, tab_scan = st.tabs(["DIY Plot Builder", "DIY Scan Builder"])
    with tab_plot:
        selected = _select_source(st, project_path, profile)
        if selected:
            frame = selected["frame"]
            a, b, c = st.columns(3)
            a.metric("Source", selected["kind"]); b.metric("Rows", len(frame)); c.metric("Numeric fields", len(numeric_columns(frame)))
            with st.expander("Source identity", expanded=False): st.json(selected["identity"])
            _render_tabular_plot(st, frame, profile, project_path, selected)
            if selected["kind"] == "result": _render_result_matrices(st, selected["raw"], profile)
    with tab_scan:
        _render_scan_builder(st, profile)
    st.caption(BOUNDARY)
