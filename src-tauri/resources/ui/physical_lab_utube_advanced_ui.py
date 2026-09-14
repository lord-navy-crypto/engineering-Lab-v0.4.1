"""Advanced physics/engineering UI for the rotating U-tube experiment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets
from physical_lab_utube_advanced import (
    BOUNDARY,
    design_space,
    dimensionless_groups,
    experiment_scan_plan,
    inverse_geometry_design,
    operating_state,
    research_questions,
    threshold_elasticity,
)
from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M, threshold
from physical_lab_utube_robust_ui import render_utube_robust_engineering
from physical_lab_utube_hysteresis_ui import render_utube_hysteresis


DIY_VIEW_BOUNDARY = (
    "DIY visualizations display the selected project data and optional deterministic U-tube model overlays. "
    "Column mapping, filtering, grouping and model parameters are user-controlled display choices; they do not change source data, establish units, or create validation evidence."
)


def _canonical_frame(dataset: dict[str, Any]) -> pd.DataFrame:
    columns = dataset.get("columns") or {}
    if not isinstance(columns, dict):
        return pd.DataFrame()
    try:
        return pd.DataFrame({str(name): list(values) for name, values in columns.items()})
    except Exception:
        return pd.DataFrame()


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(c) for c in frame.columns if pd.to_numeric(frame[c], errors="coerce").notna().sum() >= 2]


def _diy_data_view(st: Any, profile: str) -> None:
    st.markdown("##### DIY Research Data & Model View")
    st.caption("Pick your own dataset and column roles. Nothing here requires a registered U-tube raw-data contract.")
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active or not (Path(active) / "project.json").exists():
        st.info("Open a Project first, then promote or save research data as a canonical dataset.")
        return
    datasets = list_canonical_datasets(Path(active))
    if not datasets:
        st.info("No canonical project datasets are available yet.")
        return
    labels = [f"{d.get('name') or d.get('dataset_id')} · {d.get('dataset_id')}" for d in datasets]
    selected_label = st.selectbox("Research dataset", labels, key=f"pl_ut_diy_dataset_{profile}")
    dataset = datasets[labels.index(selected_label)]
    frame = _canonical_frame(dataset)
    if frame.empty:
        st.warning("The selected dataset has no tabular columns to visualize.")
        return
    numeric = _numeric_columns(frame)
    if len(numeric) < 2:
        st.warning("DIY plotting needs at least two columns containing numeric values.")
        return

    c1, c2, c3, c4 = st.columns(4)
    xcol = c1.selectbox("X column", numeric, key=f"pl_ut_diy_x_{profile}")
    ycol = c2.selectbox("Y column", numeric, index=min(1, len(numeric) - 1), key=f"pl_ut_diy_y_{profile}")
    y2_options = ["<none>"] + numeric
    y2col = c3.selectbox("Second Y", y2_options, key=f"pl_ut_diy_y2_{profile}")
    plot_mode = c4.selectbox("Plot", ["scatter", "line", "line + markers"], key=f"pl_ut_diy_mode_{profile}")

    non_numeric = [str(c) for c in frame.columns]
    d1, d2, d3 = st.columns(3)
    group_col = d1.selectbox("Group / series", ["<none>"] + non_numeric, key=f"pl_ut_diy_group_{profile}")
    sort_x = bool(d2.checkbox("Sort by X", value=True, key=f"pl_ut_diy_sort_{profile}"))
    max_rows = int(d3.number_input("Max plotted rows", min_value=20, max_value=5000, value=800, step=20, key=f"pl_ut_diy_rows_{profile}"))

    data = frame.copy()
    for column in {xcol, ycol} | ({y2col} if y2col != "<none>" else set()):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    required = [xcol, ycol] + ([y2col] if y2col != "<none>" else [])
    data = data.dropna(subset=required)
    if data.empty:
        st.warning("No finite rows remain for the selected X/Y mapping.")
        return

    x_values = pd.to_numeric(data[xcol], errors="coerce")
    x_min, x_max = float(x_values.min()), float(x_values.max())
    if np.isfinite(x_min) and np.isfinite(x_max) and x_max > x_min:
        selected_range = st.slider(
            "Visible X range",
            min_value=x_min,
            max_value=x_max,
            value=(x_min, x_max),
            key=f"pl_ut_diy_xrange_{profile}",
        )
        data = data[(data[xcol] >= selected_range[0]) & (data[xcol] <= selected_range[1])]
    if sort_x:
        data = data.sort_values(xcol, kind="stable")
    data = data.head(max_rows)

    fig = go.Figure()
    y_columns = [ycol] + ([y2col] if y2col != "<none>" and y2col != ycol else [])
    plotly_mode = "markers" if plot_mode == "scatter" else "lines" if plot_mode == "line" else "lines+markers"
    if group_col == "<none>":
        for y_name in y_columns:
            fig.add_trace(go.Scatter(x=data[xcol], y=data[y_name], mode=plotly_mode, name=y_name))
    else:
        group_values = list(pd.Series(data[group_col]).dropna().astype(str).drop_duplicates())[:12]
        for group_value in group_values:
            mask = data[group_col].astype(str) == group_value
            sub = data.loc[mask]
            for y_name in y_columns:
                fig.add_trace(go.Scatter(x=sub[xcol], y=sub[y_name], mode=plotly_mode, name=f"{group_value} · {y_name}"))
        if data[group_col].astype(str).nunique(dropna=True) > 12:
            st.caption("Only the first 12 groups are drawn to keep the chart readable; source data are unchanged.")

    overlay = st.checkbox("Overlay deterministic U-tube n_g(V) model", value=False, key=f"pl_ut_diy_overlay_{profile}")
    if overlay:
        st.caption("Use this only when the selected X column represents liquid volume in mL.")
        m1, m2, m3 = st.columns(3)
        rin = float(m1.number_input("Model R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_diy_rin_{profile}"))
        a = float(m2.number_input("Model a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_diy_a_{profile}"))
        nq = int(m3.number_input("Model quadrature order", min_value=12, max_value=160, value=48, step=4, key=f"pl_ut_diy_nq_{profile}"))
        try:
            model_x = np.linspace(float(data[xcol].min()), float(data[xcol].max()), min(120, max(24, len(data))))
            model_x = model_x[model_x > 0]
            model_y = [threshold(float(v), rin=rin, a=a, nq=nq) for v in model_x]
            fig.add_trace(go.Scatter(x=model_x, y=model_y, mode="lines", name="3-D model n_g(V)", line={"dash": "dash"}))
        except Exception as exc:
            st.warning(f"Model overlay unavailable for this X range: {exc}")

    fig.update_layout(
        title=f"DIY view · {dataset.get('name') or dataset.get('dataset_id')}",
        xaxis_title=xcol,
        yaxis_title=" / ".join(y_columns),
        legend={"orientation": "h"},
        hovermode="closest",
    )
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
    p1, p2, p3 = st.columns(3)
    p1.metric("Rows plotted", int(len(data)))
    p2.metric("X min", f"{float(data[xcol].min()):.6g}")
    p3.metric("X max", f"{float(data[xcol].max()):.6g}")
    with st.expander("Preview selected data", expanded=False):
        st.dataframe(data.head(300), hide_index=True, width="stretch")
        st.json({"dataset_id": dataset.get("dataset_id"), "source": dataset.get("source"), "units": dataset.get("units") or {}})
    st.caption(DIY_VIEW_BOUNDARY)


def render_utube_advanced(st: Any, profile: str) -> None:
    st.markdown("#### U-Tube Advanced Physics & Engineering")
    st.caption(
        "Move from forward prediction to scaling analysis, operating-envelope interpretation, inverse geometry design, design-space exploration, experiment planning and user-controlled research-data visualization."
    )
    tabs = st.tabs([
        "Research Questions",
        "Dimensionless Physics",
        "Operating Envelope",
        "Inverse Design",
        "Sensitivity & Design Space",
        "Experiment Planner",
        "DIY Data View",
    ])

    with tabs[0]:
        st.dataframe(pd.DataFrame(research_questions()), hide_index=True, width="stretch")
        st.caption("These questions define what the simulator is for: physical mechanism, numerical credibility, engineering design and experimental decision support.")

    with tabs[1]:
        c1, c2, c3, c4, c5 = st.columns(5)
        n = float(c1.number_input("n / rpm", min_value=1.0, value=260.0, key=f"pl_ut_adv_dim_n_{profile}"))
        rin = float(c2.number_input("R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_adv_dim_r_{profile}"))
        a = float(c3.number_input("a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_adv_dim_a_{profile}"))
        rho = float(c4.number_input("ρ / kg m⁻³", min_value=1.0, value=997.8, key=f"pl_ut_adv_dim_rho_{profile}"))
        gamma = float(c5.number_input("γ / mN m⁻¹", min_value=0.001, value=72.0, key=f"pl_ut_adv_dim_g_{profile}"))
        try:
            groups = dimensionless_groups(n, rin_m=rin, a_m=a, rho_kg_m3=rho, gamma_mN_m=gamma)
            st.json(groups)
            st.caption("Fr summarizes rotation vs gravity; Bond compares gravity and capillarity on tube-radius scale; rotational Weber is a scaling diagnostic using Ωℓ and a. None replaces the full 3-D threshold solver.")
        except Exception as exc:
            st.warning(str(exc))

    with tabs[2]:
        c1, c2, c3 = st.columns(3)
        V = float(c1.number_input("V / mL", min_value=0.01, value=3.0, key=f"pl_ut_adv_op_v_{profile}"))
        n = float(c2.number_input("n / rpm", min_value=1.0, value=260.0, key=f"pl_ut_adv_op_n_{profile}"))
        band = float(c3.number_input("Near-threshold band / rpm", min_value=0.1, value=3.0, key=f"pl_ut_adv_op_band_{profile}"))
        try:
            state = operating_state(V, n, near_threshold_band_rpm=band)
            a1, a2, a3 = st.columns(3)
            a1.metric("Regime", state["regime"])
            a2.metric("n − n_g", f"{state['threshold_margin_rpm']:.3f} rpm")
            a3.metric("capacity − V", f"{state['capacity_margin_ml']:.4f} mL")
            st.json(state)
        except Exception as exc:
            st.warning(str(exc))

    with tabs[3]:
        c1, c2, c3 = st.columns(3)
        target = float(c1.number_input("Target n_g / rpm", min_value=1.0, value=250.0, key=f"pl_ut_adv_inv_t_{profile}"))
        V = float(c2.number_input("Volume / mL", min_value=0.01, value=3.0, key=f"pl_ut_adv_inv_v_{profile}"))
        solve_for = c3.selectbox("Solve geometry", ["rin_m", "a_m"], key=f"pl_ut_adv_inv_s_{profile}")
        d1, d2 = st.columns(2)
        low = float(d1.number_input("Lower bound / m", min_value=0.001, value=0.005, format="%.6f", key=f"pl_ut_adv_inv_lo_{profile}"))
        high = float(d2.number_input("Upper bound / m", min_value=0.002, value=0.060, format="%.6f", key=f"pl_ut_adv_inv_hi_{profile}"))
        if st.button("Solve inverse geometry", key=f"pl_ut_adv_inv_go_{profile}"):
            try:
                result = inverse_geometry_design(target, V, solve_for=solve_for, bounds=(low, high))
                st.success(f"Solved {solve_for} = {result['solved_value_m']:.6g} m")
                st.json(result)
            except Exception as exc:
                st.warning(f"Inverse design unavailable: {exc}")
        st.caption("Inverse design solves the current model only. It does not certify manufacturability, structural integrity or experimental safety.")

    with tabs[4]:
        st.markdown("##### Local threshold elasticity")
        V = float(st.number_input("Elasticity volume / mL", min_value=0.01, value=3.0, key=f"pl_ut_adv_el_v_{profile}"))
        try:
            elas = threshold_elasticity(V)
            st.dataframe(elas, hide_index=True, width="stretch")
            fig = px.bar(elas, x="parameter", y="elasticity", title="Local d ln(n_g) / d ln(parameter)")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        except Exception as exc:
            st.warning(str(exc))

        st.markdown("##### Bounded design-space explorer")
        c1, c2, c3 = st.columns(3)
        volumes_text = c1.text_input("Volumes / mL", value="2,3,4", key=f"pl_ut_adv_ds_v_{profile}")
        rin_text = c2.text_input("R_in / m", value="0.012,0.01512,0.020", key=f"pl_ut_adv_ds_r_{profile}")
        a_text = c3.text_input("a / m", value="0.0065,0.00748,0.0085", key=f"pl_ut_adv_ds_a_{profile}")
        target = float(st.number_input("Optional target n_g / rpm", min_value=1.0, value=250.0, key=f"pl_ut_adv_ds_t_{profile}"))
        if st.button("Evaluate design space", key=f"pl_ut_adv_ds_go_{profile}"):
            try:
                vols = [float(x.strip()) for x in volumes_text.split(",") if x.strip()]
                rins = [float(x.strip()) for x in rin_text.split(",") if x.strip()]
                aa = [float(x.strip()) for x in a_text.split(",") if x.strip()]
                frame = design_space(volumes_ml=vols, rin_values_m=rins, a_values_m=aa, target_threshold_rpm=target)
                st.dataframe(frame.head(200), hide_index=True, width="stretch")
                fig = px.scatter(frame, x="critical_speed_rpm", y="threshold_rpm", size="V_mL", color="R_in_m", hover_data=["a_m", "abs_target_error_rpm"], title="Geometry design map")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            except Exception as exc:
                st.warning(f"Design-space evaluation unavailable: {exc}")

    with tabs[5]:
        c1, c2 = st.columns(2)
        V = float(c1.number_input("Planning volume / mL", min_value=0.01, value=3.0, key=f"pl_ut_adv_plan_v_{profile}"))
        nq = int(c2.number_input("Planning quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_adv_plan_nq_{profile}"))
        try:
            ng = threshold(V, nq=nq)
            plan = experiment_scan_plan(ng)
            st.metric("Predicted threshold", f"{ng:.3f} rpm")
            st.dataframe(plan, hide_index=True, width="stretch")
            fig = px.scatter(plan, x="n_rpm", y="phase", color="phase", title="Two-resolution scan plan")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("The scan plan is a sampling proposal around a model prediction. It does not define safe hardware limits or replace instrument-specific operating procedures.")
        except Exception as exc:
            st.warning(str(exc))

    with tabs[6]:
        _diy_data_view(st, profile)

    st.caption(BOUNDARY)
    render_utube_robust_engineering(st, profile)
    render_utube_hysteresis(st, profile)