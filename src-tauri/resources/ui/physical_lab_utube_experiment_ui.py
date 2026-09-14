"""Engineering Lab workspace for the rotating U-tube experiment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_utube_experiment import (
    BOUNDARY,
    angle_views,
    capacity,
    critical_speed,
    delta_free_energy,
    identify_dataset,
    model_spec,
    quadrature_convergence,
    scientific_object,
    threshold,
    validate_dataset,
    vstar,
)
from physical_lab_visual_analytics_ui import _sources


def _source_contract(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    matches = identify_dataset(frame)
    if not matches:
        st.info("This source does not match a registered U-tube raw-data contract.")
        return
    role = st.selectbox("U-tube data role", matches, key=f"pl_utube_role_{profile}")
    try:
        contract = validate_dataset(frame, role=role)
    except Exception as exc:
        st.warning(f"Dataset contract validation failed: {exc}")
        return
    st.success(f"Validated {role} · {contract['rows']} rows · sha256 {contract['sha256'][:16]}…")
    st.json(contract)
    if "theta_deg" in frame.columns:
        explicit = angle_views(frame)
        st.markdown("##### Explicit angle semantics")
        st.dataframe(explicit[[c for c in explicit.columns if c in {"n_rpm", "theta_deg", "theta_deg_signed", "theta_deg_magnitude"}]].head(300), hide_index=True, width="stretch")
        st.caption("Signed orientation and absolute magnitude are stored separately. Magnitude is never substituted for the signed measurement.")
    st.session_state[f"pl_utube_science_source_{profile}"] = {
        "id": source["id"],
        "label": f"U-tube · {source['label']}",
        "kind": source.get("kind", "dataset"),
        "frame": frame,
        "units": contract["units"],
        "identity": {**dict(source.get("identity") or {}), "utube_contract": contract, "utube_model": model_spec()},
    }


def _theory_tab(st: Any, profile: str) -> None:
    a, b, c = st.columns(3)
    volume = float(a.number_input("Liquid volume / mL", min_value=0.01, value=3.0, step=0.1, key=f"pl_utube_vol_{profile}"))
    speed = float(b.number_input("Rotation speed / rpm", min_value=1.0, value=260.0, step=1.0, key=f"pl_utube_speed_{profile}"))
    nq = int(c.number_input("Gauss-Legendre order", min_value=12, max_value=256, value=84, step=4, key=f"pl_utube_nq_{profile}"))
    try:
        nc = critical_speed()
        ng = threshold(volume, nq=nq)
        total, curved, legs = capacity(speed, nq=nq)
    except Exception as exc:
        st.warning(f"Theory calculation unavailable: {exc}")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Angular bifurcation n_c", f"{nc:.3f} rpm")
    c2.metric("Capacity threshold n_g", f"{ng:.3f} rpm")
    c3.metric("Capacity at selected speed", f"{total:.4f} mL")
    c4.metric("Curved / legs", f"{curved:.3f} / {legs:.3f} mL")
    st.caption("n_c is an angular/effective-potential bifurcation; n_g is the 3D capacity threshold for the selected volume. They are not interchangeable quantities.")


def _validation_tab(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    if not {"V_mL", "n_minus_rpm", "n_plus_rpm"}.issubset(frame.columns):
        st.info("Select a macro-volume dataset containing V_mL, n_minus_rpm and n_plus_rpm for direct theory–experiment validation.")
        return
    data = frame[["V_mL", "n_minus_rpm", "n_plus_rpm"]].copy()
    for c in data.columns:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    data = data.dropna()
    data["n_break_rpm"] = 0.5 * (data["n_minus_rpm"] + data["n_plus_rpm"])
    grouped = data.groupby("V_mL", as_index=False)["n_break_rpm"].agg(["mean", "std", "count"]).reset_index()
    grouped["theory_rpm"] = [threshold(float(v)) for v in grouped["V_mL"]]
    grouped["residual_rpm"] = grouped["mean"] - grouped["theory_rpm"]
    rmse = float(np.sqrt(np.mean(grouped["residual_rpm"] ** 2)))
    mape = float(np.mean(np.abs(grouped["residual_rpm"]) / grouped["theory_rpm"]) * 100)
    a, b = st.columns(2); a.metric("RMSE", f"{rmse:.4g} rpm"); b.metric("MAPE", f"{mape:.3g}%")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grouped["V_mL"], y=grouped["theory_rpm"], mode="lines+markers", name="3D capacity model"))
    fig.add_trace(go.Scatter(x=grouped["V_mL"], y=grouped["mean"], mode="markers", name="experiment", error_y={"type":"data", "array": grouped["std"].fillna(0)}))
    fig.update_layout(xaxis_title="V / mL", yaxis_title="speed / rpm", title="Theory–experiment threshold comparison")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.dataframe(grouped, hide_index=True, width="stretch")
    st.caption("RMSE/MAPE summarize discrepancy for this dataset. They do not establish model truth, causal mechanism, or uncertainty completeness.")


def _numerics_tab(st: Any, profile: str) -> None:
    text = st.text_input("Volumes for convergence study / mL", value="1,2,3,4,5,6", key=f"pl_utube_conv_v_{profile}")
    try:
        volumes = [float(x.strip()) for x in text.split(",") if x.strip()]
        table = quadrature_convergence(volumes)
    except Exception as exc:
        st.warning(f"Convergence study unavailable: {exc}")
        return
    fig = px.line(table, x="nq", y="threshold_rpm", color="V_mL", markers=True, title="Gauss-Legendre convergence of n_g")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.dataframe(table, hide_index=True, width="stretch")
    finite = pd.to_numeric(table["delta_from_previous_rpm"], errors="coerce").dropna()
    if not finite.empty:
        st.metric("Maximum adjacent-order change", f"{finite.max():.6g} rpm")
    st.caption("A numerical plateau supports quadrature convergence for this computation only; it is not physical validation.")


def _free_energy_tab(st: Any, profile: str) -> None:
    a, b, c = st.columns(3)
    speed = float(a.number_input("n / rpm", min_value=1.0, value=260.0, key=f"pl_utube_fe_n_{profile}"))
    gamma = float(b.number_input("γ / mN m⁻¹", min_value=0.001, value=54.54, key=f"pl_utube_fe_g_{profile}"))
    theta = float(c.number_input("θ / deg", min_value=0.0, max_value=180.0, value=48.9, key=f"pl_utube_fe_t_{profile}"))
    try:
        crossing = vstar(speed, gamma, theta)
        V = np.linspace(0.01, max(0.30, crossing * 2.0), 400)
        dF = np.asarray(delta_free_energy(V, speed, gamma, theta), dtype=float)
    except Exception as exc:
        st.warning(f"Free-energy scaling model unavailable: {exc}")
        return
    st.metric("Free-energy crossing V*", f"{crossing:.6g} mL")
    fig = px.line(pd.DataFrame({"V_mL": V, "deltaF_uJ": dF * 1e6}), x="V_mL", y="deltaF_uJ", title="ΔF = F_two − F_one")
    fig.add_hline(y=0)
    fig.add_vline(x=crossing, line_dash="dash")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption("V* is a prediction of the stated free-energy scaling model under explicit γ and θ assumptions; it is not an observed transition volume unless independently measured.")


def render_utube_experiment(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("#### Rotating U-Tube Experiment")
    st.caption("Native deterministic model, raw-data contracts, numerical convergence and theory–experiment validation extracted from the publication analysis workflow.")
    tab_data, tab_theory, tab_validation, tab_numerics, tab_free = st.tabs(["Data Contract", "3D Theory", "Theory ↔ Experiment", "Numerical Convergence", "Free Energy"])
    selected = None
    if sources:
        labels = {s["id"]: s["label"] for s in sources}
        selected_id = st.selectbox("Project source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_utube_source_{profile}")
        selected = next(s for s in sources if s["id"] == selected_id)
    with tab_data:
        if selected is None:
            st.info("Promote the experiment CSVs to canonical project datasets first; Engineering Lab will then identify compatible U-tube contracts by column schema.")
        else:
            _source_contract(st, selected, profile)
            st.json(scientific_object(dict(selected.get("identity") or {})))
    with tab_theory:
        _theory_tab(st, profile)
    with tab_validation:
        if selected is None: st.info("Select a project source first.")
        else: _validation_tab(st, selected, profile)
    with tab_numerics:
        _numerics_tab(st, profile)
    with tab_free:
        _free_energy_tab(st, profile)
    st.caption(BOUNDARY)
