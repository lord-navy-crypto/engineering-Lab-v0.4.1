"""Advanced physics/engineering UI for the rotating U-tube experiment."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px

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


def render_utube_advanced(st: Any, profile: str) -> None:
    st.markdown("#### U-Tube Advanced Physics & Engineering")
    st.caption(
        "Move from forward prediction to scaling analysis, operating-envelope interpretation, inverse geometry design, design-space exploration and experiment planning."
    )
    tabs = st.tabs([
        "Research Questions",
        "Dimensionless Physics",
        "Operating Envelope",
        "Inverse Design",
        "Sensitivity & Design Space",
        "Experiment Planner",
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

    st.caption(BOUNDARY)
