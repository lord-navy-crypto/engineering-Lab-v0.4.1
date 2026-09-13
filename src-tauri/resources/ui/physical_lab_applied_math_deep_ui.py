"""Deep applied mathematics UI for Engineering Lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_applied_math_deep import (
    BOUNDARY,
    conditioning_diagnostics,
    pca_svd,
    regularization_path,
    sweep_feedback,
    tikhonov_regression,
)


def _linear_algebra_tab(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("PCA/SVD and inverse analysis require at least two numeric fields.")
        return
    sub_pca, sub_cond, sub_inv = st.tabs(["PCA / SVD", "Conditioning", "Regularized inverse"])
    with sub_pca:
        selected = st.multiselect("Numeric variables", numeric, default=numeric[:min(6, len(numeric))], key=f"pl_deep_pca_cols_{profile}")
        standardize = st.checkbox("Standardize columns", value=True, key=f"pl_deep_pca_std_{profile}")
        if len(selected) >= 2:
            try:
                result = pca_svd(frame, selected, standardize=standardize, max_components=min(6, len(selected)))
                a, b, c = st.columns(3)
                a.metric("Rows", result["rows"])
                b.metric("Effective rank", result["effective_rank"])
                c.metric("Variables", len(result["columns"]))
                variance = pd.DataFrame({
                    "component": [f"PC{i+1}" for i in range(len(result["explained_variance_ratio"]))],
                    "explained": result["explained_variance_ratio"],
                    "cumulative": result["cumulative_variance_ratio"],
                })
                fig = go.Figure()
                fig.add_trace(go.Bar(x=variance["component"], y=variance["explained"], name="Explained"))
                fig.add_trace(go.Scatter(x=variance["component"], y=variance["cumulative"], mode="lines+markers", name="Cumulative"))
                fig.update_layout(title="PCA/SVD variance structure", yaxis_title="Variance ratio", height=480)
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.dataframe(result["loadings"], hide_index=True, width="stretch")
                scores = result["scores"]
                if {"PC1", "PC2"}.issubset(scores.columns):
                    fig = px.scatter(scores, x="PC1", y="PC2", hover_data=["row"], title="Scores · PC1 vs PC2")
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.caption("PCA/SVD identifies linear variance structure in the selected representation; components are not automatically physical latent variables.")
            except Exception as exc:
                st.warning(f"PCA/SVD unavailable: {exc}")
    with sub_cond:
        selected = st.multiselect("Matrix columns", numeric, default=numeric[:min(6, len(numeric))], key=f"pl_deep_cond_cols_{profile}")
        center = st.checkbox("Center columns", value=True, key=f"pl_deep_cond_center_{profile}")
        standardize = st.checkbox("Standardize for conditioning", value=False, key=f"pl_deep_cond_std_{profile}")
        if selected:
            try:
                result = conditioning_diagnostics(frame, selected, center=center, standardize=standardize)
                a, b, c = st.columns(3)
                cond = result["condition_number"]
                a.metric("Condition number", "∞" if not np.isfinite(cond) else f"{cond:.6g}")
                b.metric("Rank", f"{result['rank']} / {result['column_count']}")
                c.metric("Full column rank", "yes" if result["full_column_rank"] else "no")
                spectrum = pd.DataFrame({"index": range(1, len(result["singular_values"])+1), "singular_value": result["singular_values"]})
                fig = px.line(spectrum, x="index", y="singular_value", markers=True, log_y=True, title="Singular-value spectrum")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.caption(result["boundary"])
            except Exception as exc:
                st.warning(f"Conditioning diagnostics unavailable: {exc}")
    with sub_inv:
        response = st.selectbox("Observed response", numeric, index=len(numeric)-1, key=f"pl_deep_inv_y_{profile}")
        predictors = st.multiselect("Forward-model columns", [c for c in numeric if c != response], default=[c for c in numeric if c != response][:min(4, len(numeric)-1)], key=f"pl_deep_inv_x_{profile}")
        standardize = st.checkbox("Standardize predictors", value=True, key=f"pl_deep_inv_std_{profile}")
        lam = float(st.number_input("Tikhonov λ", min_value=0.0, value=0.001, format="%.8f", key=f"pl_deep_inv_lambda_{profile}"))
        if predictors:
            try:
                result = tikhonov_regression(frame, predictors, response, regularization=lam, standardize=standardize)
                st.dataframe(result["coefficients"], hide_index=True, width="stretch")
                a, b, c = st.columns(3)
                a.metric("RMSE", f"{result['rmse']:.6g}")
                b.metric("Data residual norm", f"{result['data_residual_norm']:.6g}")
                c.metric("Regularization norm", f"{result['regularization_norm']:.6g}")
                diag = result["diagnostics"]
                fig = px.scatter(diag, x="predicted", y="residual", title="Regularized inverse residuals")
                fig.add_hline(y=0)
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                path = regularization_path(frame, predictors, response, standardize=standardize)
                fig = px.line(path, x="regularization_norm", y="data_residual_norm", markers=True, hover_data=["regularization", "rmse"], title="Regularization trade-off path")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.caption(result["boundary"])
            except Exception as exc:
                st.warning(f"Regularized inverse analysis unavailable: {exc}")


def _sweep_feedback_tab(st: Any, sources: list[dict[str, Any]], profile: str) -> None:
    sweep_sources = [s for s in sources if str(s.get("kind")) == "sweep"]
    if not sweep_sources:
        st.info("No completed Sweep source is available yet.")
        return
    labels = {s["id"]: s["label"] for s in sweep_sources}
    selected_id = st.selectbox("Completed sweep", [s["id"] for s in sweep_sources], format_func=lambda x: labels.get(x, x), key=f"pl_deep_feedback_source_{profile}")
    source = next(s for s in sweep_sources if s["id"] == selected_id)
    try:
        feedback = sweep_feedback(source["frame"])
    except Exception as exc:
        st.warning(f"Sweep feedback unavailable: {exc}")
        return
    a, b, c = st.columns(3)
    a.metric("Parameters", len(feedback["parameter_columns"]))
    b.metric("Outputs", len(feedback["output_columns"]))
    c.metric("Morris metadata", "ready" if feedback["morris_ready"] else "not present")
    st.dataframe(feedback["parameter_summary"], hide_index=True, width="stretch")
    if feedback["recommendations"]:
        st.markdown("##### Compatible downstream analyses")
        st.dataframe(feedback["recommendations"], hide_index=True, width="stretch")
    else:
        st.info("This completed sweep does not expose enough varying numeric parameters/outputs for an automatic downstream recommendation.")
    st.caption(feedback["boundary"])


def render_applied_math_deep(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("#### Deep Applied Mathematics")
    st.caption("PCA/SVD, conditioning, regularized inverse problems and completed-sweep feedback over existing Engineering Lab evidence.")
    if not sources:
        st.info("No project result, completed sweep or canonical dataset is available yet.")
        return
    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Deep-analysis source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_deep_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)
    tab_linear, tab_feedback = st.tabs(["Linear Algebra & Inverse Problems", "Completed Sweep Feedback"])
    with tab_linear:
        _linear_algebra_tab(st, source, profile)
    with tab_feedback:
        _sweep_feedback_tab(st, sources, profile)
    st.caption(BOUNDARY)
