"""Uncertainty-aware U-tube analysis controls for Engineering Lab."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px

import physical_lab_project_kernel as projects
from physical_lab_utube_uncertainty import BOUNDARY, local_uncertainty_budget, predictive_interval_check, propagate_uncertainty
from physical_lab_visual_analytics_ui import _sources


def _input_controls(st: Any, profile: str) -> tuple[dict[str, float], dict[str, float], int, int]:
    st.markdown("##### Mean inputs and standard uncertainties")
    labels = [
        ("volume_ml", "V / mL", 3.0, 0.05),
        ("n_rpm", "n / rpm", 260.0, 1.0),
        ("rin_m", "R_in / m", 0.01512, 0.00005),
        ("a_m", "a / m", 0.00748, 0.00003),
        ("rho_kg_m3", "ρ / kg m⁻³", 997.8, 0.5),
        ("gamma_mN_m", "γ / mN m⁻¹", 54.54, 0.5),
        ("theta_deg", "θ / deg", 48.9, 0.5),
    ]
    means: dict[str, float] = {}
    std: dict[str, float] = {}
    for i, (key, label, mean_default, sd_default) in enumerate(labels):
        a, b = st.columns(2)
        means[key] = float(a.number_input(label, value=float(mean_default), key=f"pl_ut_uq_mean_{profile}_{i}"))
        std[key] = float(b.number_input(f"u({label})", min_value=0.0, value=float(sd_default), key=f"pl_ut_uq_sd_{profile}_{i}"))
    c1, c2 = st.columns(2)
    samples = int(c1.number_input("Monte Carlo samples", min_value=8, max_value=5000, value=300, step=50, key=f"pl_ut_uq_samples_{profile}"))
    seed = int(c2.number_input("Seed", min_value=0, value=0, step=1, key=f"pl_ut_uq_seed_{profile}"))
    return means, std, samples, seed


def render_utube_uncertainty(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    st.markdown("#### U-Tube Uncertainty & Validation")
    st.caption("Propagate explicitly supplied parameter uncertainty through the deterministic U-tube model and compare predictive intervals with experiment. No uncertainty source is inferred automatically.")

    tab_mc, tab_budget, tab_compare = st.tabs(["Monte Carlo Propagation", "Uncertainty Budget", "Theory ↔ Experiment Interval"])
    with tab_mc:
        means, std, samples, seed = _input_controls(st, profile)
        if st.button("Run uncertainty propagation", type="primary", key=f"pl_ut_uq_run_{profile}"):
            try:
                st.session_state[f"pl_ut_uq_result_{profile}"] = propagate_uncertainty(means, std, samples=samples, seed=seed, nq=48)
            except Exception as exc:
                st.error(f"Uncertainty propagation failed: {exc}")
        result = st.session_state.get(f"pl_ut_uq_result_{profile}")
        if isinstance(result, dict):
            st.json({k: result[k] for k in ["assumptions","samples_requested","samples_succeeded","samples_failed","outputs","boundary"] if k in result})
            frame = pd.DataFrame(result.get("records") or [])
            if not frame.empty:
                numeric_outputs = [c for c in ["n_c_rpm","n_g_rpm","vstar_ml","delta_f_j"] if c in frame.columns]
                if numeric_outputs:
                    chosen = st.selectbox("Predictive output", numeric_outputs, key=f"pl_ut_uq_hist_{profile}")
                    fig = px.histogram(frame, x=chosen, nbins=40, title=f"Predictive distribution · {chosen}")
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

    with tab_budget:
        means, std, _, _ = _input_controls(st, profile + "_budget")
        output = st.selectbox("Output for local budget", ["n_g_rpm", "n_c_rpm", "vstar_ml"], key=f"pl_ut_budget_output_{profile}")
        if st.button("Compute local uncertainty budget", key=f"pl_ut_budget_run_{profile}"):
            try:
                st.session_state[f"pl_ut_budget_{profile}"] = local_uncertainty_budget(means, std, output=output, nq=48)
            except Exception as exc:
                st.error(f"Uncertainty budget failed: {exc}")
        budget = st.session_state.get(f"pl_ut_budget_{profile}")
        if isinstance(budget, pd.DataFrame) and not budget.empty:
            st.dataframe(budget, hide_index=True, width="stretch")
            fig = px.bar(budget, x="parameter", y="fraction_of_variance_proxy", title="First-order variance proxy by input")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("This is a local first-order budget around the selected mean point, not a global Sobol decomposition.")

    with tab_compare:
        result = st.session_state.get(f"pl_ut_uq_result_{profile}")
        sources = _sources(__import__('pathlib').Path(active)) if active else []
        candidates = [s for s in sources if {"V_mL","n_minus_rpm","n_plus_rpm"}.issubset(set(map(str, s["frame"].columns)))]
        if not isinstance(result, dict):
            st.info("Run Monte Carlo propagation first to create a predictive distribution.")
        elif not active:
            st.info("Select or create a Project with a macro-volume experiment dataset to compare predictive intervals with measurements.")
        elif not candidates:
            st.info("No macro-volume experiment dataset is available for predictive-interval comparison.")
        else:
            labels = {s["id"]: s["label"] for s in candidates}
            sid = st.selectbox("Experimental dataset", [s["id"] for s in candidates], format_func=lambda x: labels.get(x, x), key=f"pl_ut_uq_compare_source_{profile}")
            source = next(s for s in candidates if s["id"] == sid)
            frame = source["frame"].copy()
            for col in ["V_mL","n_minus_rpm","n_plus_rpm"]:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
            frame = frame.dropna(subset=["V_mL","n_minus_rpm","n_plus_rpm"])
            volumes = sorted(frame["V_mL"].unique().tolist())
            volume = float(st.selectbox("Compare volume / mL", volumes, key=f"pl_ut_uq_compare_volume_{profile}"))
            observed = 0.5 * (frame.loc[frame["V_mL"] == volume, "n_minus_rpm"].to_numpy(float) + frame.loc[frame["V_mL"] == volume, "n_plus_rpm"].to_numpy(float))
            records = pd.DataFrame(result.get("records") or [])
            pred = pd.to_numeric(records.get("n_g_rpm", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy(float)
            try:
                comparison = predictive_interval_check(observed, pred)
                st.json(comparison)
                if comparison["observed_mean_inside_predictive_95pct"]:
                    st.success("Observed mean lies inside the current model predictive 95% interval under the supplied uncertainty assumptions.")
                else:
                    st.warning("Observed mean lies outside the current model predictive 95% interval under the supplied uncertainty assumptions.")
            except Exception as exc:
                st.warning(f"Predictive comparison unavailable: {exc}")
            st.caption("For a strict volume-specific predictive comparison, run the Monte Carlo propagation with the same selected volume as its mean V input.")

    st.caption(BOUNDARY)
