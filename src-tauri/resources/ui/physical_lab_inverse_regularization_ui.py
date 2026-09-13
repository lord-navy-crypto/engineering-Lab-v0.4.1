"""TSVD/GCV/L-curve and completed-sweep handoff UI for Engineering Lab."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px

from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_applied_math_deep import sweep_feedback
from physical_lab_inverse_regularization import (
    BOUNDARY,
    gcv_choice,
    lcurve_choice,
    lcurve_curvature,
    tikhonov_gcv_path,
    truncated_svd_regression,
    tsvd_path,
)


def _inverse_regularization(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Inverse regularization requires at least two numeric fields.")
        return
    response = st.selectbox("Inverse response", numeric, index=len(numeric)-1, key=f"pl_invreg_y_{profile}")
    predictors = st.multiselect("Inverse predictors", [c for c in numeric if c != response], default=[c for c in numeric if c != response][:min(5, len(numeric)-1)], key=f"pl_invreg_x_{profile}")
    standardize = st.checkbox("Standardize predictors", value=True, key=f"pl_invreg_std_{profile}")
    if not predictors:
        st.info("Select at least one predictor.")
        return
    tab_tsvd, tab_gcv = st.tabs(["TSVD", "GCV + L-curve"])
    with tab_tsvd:
        try:
            path = tsvd_path(frame, predictors, response, standardize=standardize)
            max_rank = int(path["rank"].max())
            rank = int(st.slider("Retained singular components", 1, max_rank, max_rank, key=f"pl_invreg_rank_{profile}"))
            result = truncated_svd_regression(frame, predictors, response, rank=rank, standardize=standardize)
            a, b, c = st.columns(3)
            a.metric("Retained rank", f"{rank} / {max_rank}")
            b.metric("RMSE", f"{result['rmse']:.6g}")
            c.metric("Solution norm", f"{result['solution_norm']:.6g}")
            st.dataframe(result["coefficients"], hide_index=True, width="stretch")
            fig = px.line(path, x="rank", y="rmse", markers=True, title="TSVD rank path")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("TSVD suppresses directions associated with discarded singular components. Retained rank is a numerical regularization choice, not a physical dimension claim.")
        except Exception as exc:
            st.warning(f"TSVD unavailable: {exc}")
    with tab_gcv:
        try:
            path = tikhonov_gcv_path(frame, predictors, response, standardize=standardize)
            gcv = gcv_choice(path)
            curved = lcurve_curvature(path)
            lcurve = lcurve_choice(path)
            a, b = st.columns(2)
            a.metric("GCV candidate λ", f"{gcv['regularization']:.6g}")
            b.metric("L-curve candidate λ", f"{lcurve['regularization']:.6g}")
            fig = px.line(path, x="regularization", y="gcv", log_x=True, markers=True, title="Generalized cross-validation path")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            fig = px.line(curved, x="solution_norm", y="data_residual_norm", markers=True, hover_data=["regularization", "lcurve_curvature"], title="L-curve trade-off")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(curved[["regularization", "gcv", "effective_degrees_of_freedom", "data_residual_norm", "solution_norm", "lcurve_curvature"]], hide_index=True, width="stretch")
            st.caption("GCV and maximum discrete L-curve curvature are diagnostics/candidates. They are not guaranteed to recover a physically correct regularization strength.")
        except Exception as exc:
            st.warning(f"GCV/L-curve analysis unavailable: {exc}")


def _prepare_handoff(st: Any, profile: str, source_id: str, recommendation: dict[str, Any]) -> None:
    analysis = str(recommendation.get("analysis") or "")
    params = list(recommendation.get("parameters") or [])
    outputs = list(recommendation.get("outputs") or [])
    if not outputs:
        return
    output = outputs[0]
    if analysis == "factorial-effects":
        st.session_state[f"pl_adv_source_{profile}"] = source_id
        st.session_state[f"pl_adv_fact_y_{profile}"] = output
        st.session_state[f"pl_adv_fact_x_{profile}"] = params
        st.session_state[f"pl_analysis_handoff_{profile}"] = {"target": "Advanced Applied Analysis → Factorial + Morris", "analysis": analysis, "source_id": source_id}
    elif analysis == "morris-effects":
        st.session_state[f"pl_adv_source_{profile}"] = source_id
        st.session_state[f"pl_adv_morris_y_{profile}"] = output
        st.session_state[f"pl_adv_morris_fx_{profile}"] = params
        st.session_state[f"pl_analysis_handoff_{profile}"] = {"target": "Advanced Applied Analysis → Factorial + Morris", "analysis": analysis, "source_id": source_id}
    elif analysis == "response-surface" and len(params) >= 2:
        st.session_state[f"pl_tradeoff_source_{profile}"] = source_id
        st.session_state[f"pl_science_surface_x_{profile}"] = params[0]
        st.session_state[f"pl_science_surface_y_{profile}"] = params[1]
        st.session_state[f"pl_science_surface_z_{profile}"] = output
        st.session_state[f"pl_analysis_handoff_{profile}"] = {"target": "Science Analysis → Sensitivity + Surface", "analysis": analysis, "source_id": source_id}
    elif analysis == "sensitivity-screening" and params:
        st.session_state[f"pl_tradeoff_source_{profile}"] = source_id
        st.session_state[f"pl_science_sens_out_{profile}"] = output
        st.session_state[f"pl_science_sens_params_{profile}"] = params
        st.session_state[f"pl_science_local_param_{profile}"] = params[0]
        st.session_state[f"pl_analysis_handoff_{profile}"] = {"target": "Science Analysis → Sensitivity + Surface", "analysis": analysis, "source_id": source_id}


def _sweep_handoff(st: Any, sources: list[dict[str, Any]], profile: str) -> None:
    sweeps = [s for s in sources if str(s.get("kind")) == "sweep"]
    if not sweeps:
        st.info("No completed sweep is available for analysis handoff.")
        return
    labels = {s["id"]: s["label"] for s in sweeps}
    source_id = st.selectbox("Completed sweep for handoff", [s["id"] for s in sweeps], format_func=lambda x: labels.get(x, x), key=f"pl_handoff_sweep_{profile}")
    source = next(s for s in sweeps if s["id"] == source_id)
    try:
        feedback = sweep_feedback(source["frame"])
    except Exception as exc:
        st.warning(f"Sweep feedback unavailable: {exc}")
        return
    recommendations = list(feedback.get("recommendations") or [])
    if not recommendations:
        st.info("No compatible downstream analysis was detected for this sweep.")
        return
    st.dataframe(recommendations, hide_index=True, width="stretch")
    for i, recommendation in enumerate(recommendations[:8]):
        analysis = str(recommendation.get("analysis") or "analysis")
        params = ", ".join(recommendation.get("parameters") or [])
        outputs = ", ".join(recommendation.get("outputs") or [])
        label = f"Prepare {analysis} · {params} → {outputs}"
        if st.button(label, key=f"pl_handoff_{profile}_{i}_{analysis}"):
            _prepare_handoff(st, profile, source_id, recommendation)
            handoff = st.session_state.get(f"pl_analysis_handoff_{profile}")
            if handoff:
                st.success(f"Prepared {analysis}. Open {handoff['target']}; fields are preselected. No execution or new evidence was created.")
    handoff = st.session_state.get(f"pl_analysis_handoff_{profile}")
    if handoff:
        st.json(handoff)
    st.caption("Handoff writes view-selection state only. It does not start a sweep, rerun a model, or create a scientific conclusion.")


def render_inverse_regularization(st: Any, profile: str) -> None:
    sources = _sources(Path(str(st.session_state.get("physical_lab_active_project") or st.session_state.get("pl_active_project") or "."))) if False else _sources_for_state(st)
    if not sources:
        return
    st.markdown("#### Inverse Regularization & Analysis Handoff")
    labels = {s["id"]: s["label"] for s in sources}
    source_id = st.selectbox("Regularization source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_invreg_source_{profile}")
    source = next(s for s in sources if s["id"] == source_id)
    tab_inverse, tab_handoff = st.tabs(["TSVD / GCV / L-curve", "Completed Sweep Handoff"])
    with tab_inverse:
        _inverse_regularization(st, source, profile)
    with tab_handoff:
        _sweep_handoff(st, sources, profile)
    st.caption(BOUNDARY)


def _sources_for_state(st: Any) -> list[dict[str, Any]]:
    import physical_lab_project_kernel as projects
    from pathlib import Path
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return []
    return _sources(Path(active))
