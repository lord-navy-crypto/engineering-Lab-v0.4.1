"""Correlation and Pareto Trade-off Explorer UI for Engineering Lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_tradeoff_analysis import BOUNDARY, correlation_matrix, pareto_frontier


def render_tradeoff_analysis(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use the Trade-off Explorer.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Correlation & Pareto Trade-off Explorer")
    st.caption("Use descriptive correlation and two-objective Pareto analysis on existing project results, sweeps, or datasets. The analysis does not alter source evidence.")
    if not sources:
        st.info("No project results, completed sweeps, or canonical datasets are available yet.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Analysis source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_tradeoff_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)
    frame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.warning("This source does not contain enough numeric fields for correlation or Pareto analysis.")
        return

    tab_corr, tab_pareto = st.tabs(["Correlation Matrix", "Pareto Frontier"])
    with tab_corr:
        default = numeric[: min(8, len(numeric))]
        columns = st.multiselect("Numeric fields", numeric, default=default, key=f"pl_tradeoff_corr_cols_{profile}")
        method = st.radio("Method", ["pearson", "spearman"], horizontal=True, key=f"pl_tradeoff_corr_method_{profile}")
        if len(columns) >= 2:
            try:
                corr = correlation_matrix(frame, columns, method=method)
                fig = px.imshow(corr, text_auto=".2f", zmin=-1, zmax=1, aspect="auto", title=f"{method.title()} correlation")
                fig.update_layout(height=max(520, 52 * len(columns)))
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.dataframe(corr, width="stretch")
                st.caption("Correlation summarizes association in this table only. It does not establish causality, physical mechanism, or model validity.")
            except Exception as exc:
                st.warning(f"Correlation matrix unavailable: {exc}")
        else:
            st.info("Select at least two numeric fields.")

    with tab_pareto:
        c1, c2 = st.columns(2)
        x = c1.selectbox("Objective X", numeric, key=f"pl_tradeoff_x_{profile}")
        y_options = [c for c in numeric if c != x]
        y = c2.selectbox("Objective Y", y_options, key=f"pl_tradeoff_y_{profile}")
        d1, d2 = st.columns(2)
        x_goal = d1.radio("X direction", ["min", "max"], horizontal=True, key=f"pl_tradeoff_xgoal_{profile}")
        y_goal = d2.radio("Y direction", ["min", "max"], horizontal=True, key=f"pl_tradeoff_ygoal_{profile}")
        try:
            result = pareto_frontier(frame, x=x, x_goal=x_goal, y=y, y_goal=y_goal)
            if result.empty:
                st.info("No finite objective pairs are available.")
            else:
                frontier = result[result["pareto"]].copy()
                dominated = result[~result["pareto"]].copy()
                fig = go.Figure()
                if not dominated.empty:
                    fig.add_trace(go.Scatter(x=dominated[x], y=dominated[y], mode="markers", name="Dominated", customdata=dominated[["source_index"]]))
                if not frontier.empty:
                    ordered = frontier.sort_values(x)
                    fig.add_trace(go.Scatter(x=ordered[x], y=ordered[y], mode="lines+markers", name="Pareto frontier", customdata=ordered[["source_index"]]))
                fig.update_layout(title=f"Pareto trade-off · {x_goal} {x} / {y_goal} {y}", xaxis_title=x, yaxis_title=y, height=620, hovermode="closest")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
                m1, m2, m3 = st.columns(3)
                m1.metric("Finite points", len(result))
                m2.metric("Pareto points", int(result["pareto"].sum()))
                m3.metric("Dominated", int((~result["pareto"]).sum()))
                st.markdown("##### Pareto candidates")
                st.dataframe(frontier[["source_index", x, y]], hide_index=True, width="stretch")
                st.caption("A Pareto point is non-dominated only for the two selected objectives and directions. Constraints, uncertainty, calibration, feasibility and scientific validity remain separate questions.")
        except Exception as exc:
            st.warning(f"Pareto analysis unavailable: {exc}")

    st.caption(BOUNDARY)
