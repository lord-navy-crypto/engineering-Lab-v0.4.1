"""Tolerance-aware engineering design, Pareto, adaptive planning and verification UI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px

import physical_lab_project_kernel as projects
import physical_lab_requirements_verification as requirements
from physical_lab_utube_advanced import (
    BOUNDARY,
    adaptive_threshold_plan,
    pareto_robust_design,
    robust_design_space,
    verification_requirements,
)
from physical_lab_utube_digital_twin_ui import render_utube_digital_twin
from physical_lab_utube_experiment import threshold


def _numbers(text: str) -> list[float]:
    values = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    if not values or any(not np.isfinite(x) or x <= 0 for x in values):
        raise ValueError("values must be finite, positive and comma separated")
    return values


def _observations(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 2:
            raise ValueError("each observation must be `rpm,below` or `rpm,above`")
        rows.append({"n_rpm": float(parts[0]), "state": parts[1].lower()})
    return rows


def _robust_design(st: Any, profile: str) -> None:
    st.markdown("##### Deterministic tolerance-corner screening")
    c1, c2, c3 = st.columns(3)
    volumes_text = c1.text_input("Nominal V / mL", value="2.5,3,3.5", key=f"pl_ut_rob_v_{profile}")
    rin_text = c2.text_input("Nominal R_in / m", value="0.0145,0.01512,0.016", key=f"pl_ut_rob_r_{profile}")
    a_text = c3.text_input("Nominal a / m", value="0.0070,0.00748,0.0080", key=f"pl_ut_rob_a_{profile}")
    d1, d2, d3, d4 = st.columns(4)
    vtol = float(d1.number_input("±V tolerance / mL", min_value=0.0, value=0.05, step=0.01, key=f"pl_ut_rob_vtol_{profile}"))
    rtol = float(d2.number_input("±R_in tolerance / m", min_value=0.0, value=0.0002, format="%.6f", key=f"pl_ut_rob_rtol_{profile}"))
    atol = float(d3.number_input("±a tolerance / m", min_value=0.0, value=0.0001, format="%.6f", key=f"pl_ut_rob_atol_{profile}"))
    target = float(d4.number_input("Target n_g / rpm", min_value=1.0, value=250.0, key=f"pl_ut_rob_target_{profile}"))
    if st.button("Evaluate tolerance envelope & Pareto", type="primary", key=f"pl_ut_rob_go_{profile}"):
        try:
            frame = robust_design_space(
                volumes_ml=_numbers(volumes_text), rin_values_m=_numbers(rin_text), a_values_m=_numbers(a_text),
                volume_tolerance_ml=vtol, rin_tolerance_m=rtol, a_tolerance_m=atol, target_threshold_rpm=target,
            )
            st.session_state[f"pl_ut_rob_frame_{profile}"] = pareto_robust_design(frame)
        except Exception as exc:
            st.warning(f"Robust design unavailable: {exc}")
    frame = st.session_state.get(f"pl_ut_rob_frame_{profile}")
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Nominal designs", len(frame)); m2.metric("Pareto candidates", int(frame["pareto"].sum())); m3.metric("Best separation floor", f"{frame['separation_floor_rpm'].max():.3f} rpm")
        st.dataframe(frame.head(300), hide_index=True, width="stretch")
        fig = px.scatter(frame, x="worst_abs_target_error_rpm", y="threshold_span_rpm", color="separation_floor_rpm", symbol="pareto", hover_data=["V_mL", "R_in_m", "a_m", "nominal_threshold_rpm", "corner_count"], title="Robust-design Pareto view · target error vs tolerance sensitivity")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.caption("Pareto membership uses the common Trade-off engine and only the two plotted objectives. Separation floor stays explicit instead of being hidden inside an invented master score.")
    st.caption("Tolerance corners are deterministic screening cases, not probability distributions or process-capability claims.")


def _adaptive_planner(st: Any, profile: str) -> None:
    st.markdown("##### Adaptive threshold sampling")
    c1, c2, c3 = st.columns(3)
    volume = float(c1.number_input("Planning V / mL", min_value=0.01, value=3.0, key=f"pl_ut_adapt_v_{profile}"))
    nq = int(c2.number_input("Quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_adapt_nq_{profile}"))
    target_width = float(c3.number_input("Target empirical bracket / rpm", min_value=0.1, value=2.0, step=0.5, key=f"pl_ut_adapt_width_{profile}"))
    text = st.text_area("Observed classifications · one `rpm,below` or `rpm,above` per line", value="", placeholder="240,below\n260,above", key=f"pl_ut_adapt_obs_{profile}")
    try:
        prediction = threshold(volume, nq=nq)
        result = adaptive_threshold_plan(_observations(text), prediction, target_bracket_rpm=target_width)
        a, b, c = st.columns(3)
        a.metric("Model n_g", f"{prediction:.3f} rpm"); b.metric("Planner state", result["status"]); c.metric("Bracket width", "—" if result["empirical_bracket_width_rpm"] is None else f"{result['empirical_bracket_width_rpm']:.3f} rpm")
        st.json(result)
        if result["next_measurements_rpm"]:
            st.dataframe(pd.DataFrame({"next_n_rpm": result["next_measurements_rpm"], "reason": result["status"]}), hide_index=True, width="stretch")
        st.caption("Once a valid below/above bracket exists, the next point is its midpoint. The empirical bracket is bookkeeping for sampling, not a confidence interval or equipment limit.")
    except Exception as exc:
        st.warning(f"Adaptive planning unavailable: {exc}")


def _verification(st: Any, profile: str) -> None:
    st.markdown("##### U-Tube verification requirement templates")
    c1, c2, c3, c4 = st.columns(4)
    target = float(c1.number_input("Target n_g / rpm", min_value=1.0, value=250.0, key=f"pl_ut_req_target_{profile}"))
    tol = float(c2.number_input("Threshold tolerance / rpm", min_value=0.1, value=5.0, key=f"pl_ut_req_tol_{profile}"))
    sep = float(c3.number_input("Minimum n_g−n_c / rpm", min_value=0.0, value=10.0, key=f"pl_ut_req_sep_{profile}"))
    num = float(c4.number_input("Max numerical Δn_g / rpm", min_value=0.001, value=0.25, key=f"pl_ut_req_num_{profile}"))
    try:
        matrix = verification_requirements(target_threshold_rpm=target, threshold_tolerance_rpm=tol, minimum_separation_rpm=sep, maximum_numerical_change_rpm=num)
    except Exception as exc:
        st.warning(f"Verification matrix unavailable: {exc}"); return
    st.dataframe(matrix[["requirement_id", "statement", "verification_method", "verification_activity", "success_criteria"]], hide_index=True, width="stretch")
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab Project to register these templates into Requirements & Verification."); return
    if st.button("Register templates in current Project", type="primary", key=f"pl_ut_req_register_{profile}"):
        created: list[str] = []
        try:
            for row in matrix.to_dict("records"):
                record = requirements.register_requirement(Path(active), requirement_id=str(row["requirement_id"]), statement=str(row["statement"]), verification_method=str(row["verification_method"]), verification_activity=str(row["verification_activity"]), success_criteria=str(row["success_criteria"]), references=[], source_document="U-Tube Advanced Physics & Engineering", source_locator="Verification Matrix template", rationale=str(row["rationale"]), level="subsystem", intended_use="U-tube model development and project evidence review")
                created.append(str(record["requirement_id"]))
            st.success("Registered/updated: " + ", ".join(created))
            st.caption("No evidence is auto-attached. The common Requirements layer therefore begins these plans as EVIDENCE_MISSING until explicit Project evidence is linked and reviewed.")
        except Exception as exc:
            st.error(f"Could not register templates: {exc}")
    st.caption("Template registration creates requirement plans, not automatic compliance or verification decisions.")


def render_utube_robust_engineering(st: Any, profile: str) -> None:
    st.markdown("#### U-Tube Robust Design, Adaptive Experiment & Verification")
    st.caption("Tolerance-aware design screening and experiment/verification planning built on the same deterministic 3-D threshold model and common Engineering Lab infrastructure.")
    tab_robust, tab_adaptive, tab_verify = st.tabs(["Robust Design & Pareto", "Adaptive Experiment", "Verification Matrix"])
    with tab_robust: _robust_design(st, profile)
    with tab_adaptive: _adaptive_planner(st, profile)
    with tab_verify: _verification(st, profile)
    st.caption(BOUNDARY)
    render_utube_digital_twin(st, profile)
