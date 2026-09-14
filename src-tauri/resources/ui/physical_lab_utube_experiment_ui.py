"""Engineering Lab workspace for the rotating U-tube experiment."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
import physical_lab_sweep_executor as sweeps
from physical_lab_applied_analysis import design_experiment
from physical_lab_applied_analysis_advanced import adapter_parameter_names
from physical_lab_utube_experiment import (
    BOUNDARY,
    G,
    DEFAULT_A_M,
    DEFAULT_R_IN_M,
    angle_views,
    capacity,
    critical_speed,
    delta_free_energy,
    geometry,
    identify_dataset,
    model_spec,
    omega,
    quadrature_convergence,
    scientific_object,
    threshold,
    validate_dataset,
    vstar,
)
from physical_lab_visual_analytics_ui import _sources

VISUALIZATION_BOUNDARY = (
    "U-tube visualization products are deterministic derived views of the declared "
    "model inputs. Geometry traces are schematic centerline/reference views rather "
    "than CFD or reconstructed liquid interfaces. Effective-potential and threshold "
    "maps are model diagnostics, not experimental observations or safety limits."
)


def _reference_geometry(
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    *,
    bend_points: int = 181,
    leg_height_m: float | None = None,
) -> pd.DataFrame:
    geom = geometry(rin_m, a_m)
    R = geom["R_m"]
    ell = geom["ell_m"]
    n = max(31, min(int(bend_points), 1001))
    height = float(leg_height_m) if leg_height_m is not None else max(4.0 * a_m, 0.75 * R)
    if not np.isfinite(height) or height <= 0:
        raise ValueError("leg_height_m must be positive")
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n)
    bend = pd.DataFrame({
        "segment": "bend",
        "order": np.arange(n, dtype=int),
        "x_m": R * np.sin(theta),
        "z_m": ell - R * np.cos(theta),
        "theta_rad": theta,
    })
    leg_n = max(20, n // 4)
    z_leg = np.linspace(ell, ell + height, leg_n)
    left = pd.DataFrame({"segment": "left-leg", "order": np.arange(leg_n, dtype=int), "x_m": -R, "z_m": z_leg, "theta_rad": np.nan})
    right = pd.DataFrame({"segment": "right-leg", "order": np.arange(leg_n, dtype=int), "x_m": R, "z_m": z_leg, "theta_rad": np.nan})
    return pd.concat([left, bend, right], ignore_index=True)


def _effective_potential_profile(
    n_rpm: float,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    *,
    points: int = 361,
) -> pd.DataFrame:
    speed = float(n_rpm)
    if not np.isfinite(speed) or speed <= 0:
        raise ValueError("n_rpm must be finite and positive")
    geom = geometry(rin_m, a_m)
    R = geom["R_m"]
    ell = geom["ell_m"]
    w = float(omega(speed))
    n = max(51, min(int(points), 2001))
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n)
    x = R * np.sin(theta)
    z = ell - R * np.cos(theta)
    potential = G * z - 0.5 * w * w * x * x
    return pd.DataFrame({
        "theta_deg": np.degrees(theta),
        "x_m": x,
        "z_m": z,
        "effective_potential_J_kg": potential,
        "relative_potential_J_kg": potential - float(np.min(potential)),
    })


def _capacity_decomposition(volume_ml: float, n_rpm: float, nq: int = 84) -> dict[str, Any]:
    volume = float(volume_ml)
    speed = float(n_rpm)
    if not np.isfinite(volume) or not np.isfinite(speed) or volume <= 0 or speed <= 0:
        raise ValueError("volume_ml and n_rpm must be finite and positive")
    total, curved, legs = capacity(speed, nq=int(nq))
    ng = threshold(volume, nq=int(nq))
    nc = critical_speed()
    return {
        "volume_ml": volume,
        "n_rpm": speed,
        "critical_speed_rpm": nc,
        "threshold_rpm": ng,
        "threshold_margin_rpm": speed - ng,
        "capacity_total_ml": total,
        "capacity_curved_ml": curved,
        "capacity_legs_ml": legs,
        "capacity_margin_ml": total - volume,
        "curved_fraction": curved / total if total > 0 else None,
        "legs_fraction": legs / total if total > 0 else None,
    }


def _threshold_phase_map(
    volumes_ml: Iterable[float],
    speeds_rpm: Iterable[float],
    nq: int = 48,
    *,
    near_threshold_band_rpm: float = 3.0,
) -> pd.DataFrame:
    volumes = [float(v) for v in volumes_ml]
    speeds = [float(n) for n in speeds_rpm]
    if not volumes or not speeds:
        raise ValueError("volumes_ml and speeds_rpm must be non-empty")
    if any((not np.isfinite(v) or v <= 0) for v in volumes) or any((not np.isfinite(n) or n <= 0) for n in speeds):
        raise ValueError("all phase-map coordinates must be finite and positive")
    band = abs(float(near_threshold_band_rpm))
    nc = critical_speed()
    thresholds = {v: threshold(v, nq=int(nq)) for v in volumes}
    rows: list[dict[str, Any]] = []
    for volume in volumes:
        ng = thresholds[volume]
        for speed in speeds:
            if speed < nc:
                regime, code = "below-angular-bifurcation", 0
            elif abs(speed - ng) <= band:
                regime, code = "near-finite-volume-threshold", 2
            elif speed < ng:
                regime, code = "between-nc-and-ng", 1
            else:
                regime, code = "above-finite-volume-threshold", 3
            rows.append({"V_mL": volume, "n_rpm": speed, "critical_speed_rpm": nc, "threshold_rpm": ng, "threshold_margin_rpm": speed - ng, "regime": regime, "regime_code": code})
    return pd.DataFrame(rows)


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
        "id": source["id"], "label": f"U-tube · {source['label']}", "kind": source.get("kind", "dataset"),
        "frame": frame, "units": contract["units"],
        "identity": {**dict(source.get("identity") or {}), "utube_contract": contract, "utube_model": model_spec()},
    }


def _theory_tab(st: Any, profile: str) -> None:
    a, b, c = st.columns(3)
    volume = float(a.number_input("Liquid volume / mL", min_value=0.01, value=3.0, step=0.1, key=f"pl_utube_vol_{profile}"))
    speed = float(b.number_input("Rotation speed / rpm", min_value=1.0, value=260.0, step=1.0, key=f"pl_utube_speed_{profile}"))
    nq = int(c.number_input("Gauss-Legendre order", min_value=12, max_value=256, value=84, step=4, key=f"pl_utube_nq_{profile}"))
    try:
        state = _capacity_decomposition(volume, speed, nq=nq)
        geom_frame = _reference_geometry()
        potential = _effective_potential_profile(speed)
    except Exception as exc:
        st.warning(f"Theory calculation unavailable: {exc}")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Angular bifurcation n_c", f"{state['critical_speed_rpm']:.3f} rpm")
    c2.metric("Capacity threshold n_g", f"{state['threshold_rpm']:.3f} rpm")
    c3.metric("Capacity margin", f"{state['capacity_margin_ml']:+.4f} mL")
    c4.metric("Threshold margin", f"{state['threshold_margin_rpm']:+.3f} rpm")
    st.caption("n_c is an angular/effective-potential bifurcation; n_g is the finite-volume 3D capacity threshold. They are separate model quantities.")
    left, right = st.columns(2)
    with left:
        fig = go.Figure()
        labels = {"left-leg": "left leg", "bend": "curved section", "right-leg": "right leg"}
        for segment, sub in geom_frame.groupby("segment", sort=False):
            fig.add_trace(go.Scatter(x=sub["x_m"] * 1e3, y=sub["z_m"] * 1e3, mode="lines", name=labels.get(str(segment), str(segment))))
        fig.update_layout(title="U-tube reference geometry", xaxis_title="horizontal coordinate / mm", yaxis_title="vertical coordinate / mm", yaxis={"scaleanchor": "x", "scaleratio": 1}, legend={"orientation": "h"})
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
        st.caption("Centerline/reference geometry from the same R and ℓ definitions used by the capacity solver; it is not a reconstructed liquid interface or CFD result.")
    with right:
        fig = px.line(potential, x="theta_deg", y="relative_potential_J_kg", title="Rotating-frame effective potential along bend centerline")
        fig.add_vline(x=0.0, line_dash="dot")
        fig.update_layout(xaxis_title="bend angle θ / deg", yaxis_title="relative effective potential / J kg⁻¹")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
        st.caption("Potential is shifted by its minimum. This is a model diagnostic along the bend centerline, not a measured pressure or interface profile.")
    st.markdown("##### Capacity anatomy")
    cap_frame = pd.DataFrame({"component": ["curved section", "two legs", "selected liquid volume"], "volume_ml": [state["capacity_curved_ml"], state["capacity_legs_ml"], state["volume_ml"]]})
    fig = px.bar(cap_frame, x="component", y="volume_ml", title=f"Available low-potential capacity at {speed:.1f} rpm")
    fig.update_layout(yaxis_title="volume / mL", xaxis_title="")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.dataframe(pd.DataFrame([state]), hide_index=True, width="stretch")
    st.caption(VISUALIZATION_BOUNDARY)


def _phase_map_tab(st: Any, profile: str) -> None:
    st.markdown("##### Finite-volume threshold phase map")
    c1, c2, c3 = st.columns(3)
    v_lo = float(c1.number_input("Volume min / mL", min_value=0.05, value=1.0, step=0.25, key=f"pl_utube_phase_vlo_{profile}"))
    v_hi = float(c2.number_input("Volume max / mL", min_value=0.10, value=6.0, step=0.25, key=f"pl_utube_phase_vhi_{profile}"))
    points = int(c3.number_input("Volume samples", min_value=5, max_value=60, value=18, step=1, key=f"pl_utube_phase_nv_{profile}"))
    d1, d2, d3 = st.columns(3)
    n_lo = float(d1.number_input("Speed min / rpm", min_value=1.0, value=150.0, step=5.0, key=f"pl_utube_phase_nlo_{profile}"))
    n_hi = float(d2.number_input("Speed max / rpm", min_value=2.0, value=360.0, step=5.0, key=f"pl_utube_phase_nhi_{profile}"))
    n_points = int(d3.number_input("Speed samples", min_value=5, max_value=80, value=30, step=1, key=f"pl_utube_phase_nn_{profile}"))
    if v_hi <= v_lo or n_hi <= n_lo:
        st.warning("Upper bounds must be greater than lower bounds.")
        return
    try:
        phase = _threshold_phase_map(np.linspace(v_lo, v_hi, points), np.linspace(n_lo, n_hi, n_points), nq=48)
    except Exception as exc:
        st.warning(f"Phase-map evaluation unavailable: {exc}")
        return
    pivot = phase.pivot(index="n_rpm", columns="V_mL", values="regime_code")
    fig = go.Figure(data=go.Heatmap(x=pivot.columns, y=pivot.index, z=pivot.values, zmin=0, zmax=3, colorbar={"title": "regime", "tickvals": [0, 1, 2, 3], "ticktext": ["below n_c", "between", "near n_g", "above n_g"]}, hovertemplate="V=%{x:.3g} mL<br>n=%{y:.3g} rpm<br>regime code=%{z}<extra></extra>"))
    threshold_curve = phase[["V_mL", "threshold_rpm"]].drop_duplicates().sort_values("V_mL")
    nc = float(phase["critical_speed_rpm"].iloc[0])
    fig.add_trace(go.Scatter(x=threshold_curve["V_mL"], y=threshold_curve["threshold_rpm"], mode="lines", name="n_g(V)"))
    fig.add_hline(y=nc, line_dash="dash", annotation_text="n_c")
    fig.update_layout(title="U-tube operating-regime map", xaxis_title="liquid volume / mL", yaxis_title="rotation speed / rpm", height=560)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
    st.caption("The map explicitly separates the angular bifurcation n_c from the finite-volume threshold n_g(V). The near-threshold band is a visualization aid, not an uncertainty interval.")


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
    a, b = st.columns(2)
    a.metric("RMSE", f"{rmse:.4g} rpm")
    b.metric("MAPE", f"{mape:.3g}%")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grouped["V_mL"], y=grouped["theory_rpm"], mode="lines+markers", name="3D capacity model"))
    fig.add_trace(go.Scatter(x=grouped["V_mL"], y=grouped["mean"], mode="markers", name="experiment", error_y={"type": "data", "array": grouped["std"].fillna(0)}))
    fig.update_layout(xaxis_title="V / mL", yaxis_title="speed / rpm", title="Theory–experiment threshold comparison")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    residual_fig = px.scatter(grouped, x="V_mL", y="residual_rpm", title="Threshold residual: experiment − model")
    residual_fig.add_hline(y=0.0, line_dash="dash")
    residual_fig.update_layout(xaxis_title="V / mL", yaxis_title="residual / rpm")
    st.plotly_chart(residual_fig, width="stretch", config={"displaylogo": False})
    st.dataframe(grouped, hide_index=True, width="stretch")
    st.caption("RMSE/MAPE and residuals summarize discrepancy for this dataset. They do not establish model truth, causal mechanism, or uncertainty completeness.")


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


def _parse_factor_lines(text: str) -> list[dict[str, float | str]]:
    factors: list[dict[str, float | str]] = []
    seen: set[str] = set()
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            raise ValueError("Each factor line must be name,low,high")
        name = parts[0]
        low, high = float(parts[1]), float(parts[2])
        if name in seen:
            raise ValueError(f"duplicate factor: {name}")
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise ValueError(f"invalid bounds for {name}")
        seen.add(name)
        factors.append({"name": name, "low": low, "high": high})
    if not factors:
        raise ValueError("At least one factor is required")
    return factors


def _sweep_tab(st: Any, profile: str) -> None:
    st.markdown("##### U-Tube DOE → Sweep")
    available = {row["id"] for row in sweeps.available_adapters(profile)}
    if "utube-rotation" not in available:
        st.info("The U-tube Sweep adapter is allow-listed for the Numerical Methods and Oscillation/Integration profiles. Open this workspace from one of those profiles to queue a campaign.")
        return
    accepted = adapter_parameter_names(profile, "utube-rotation")
    st.caption("Allow-listed adapter parameters: " + ", ".join(accepted))
    default_factors = "volume_ml,1,6\nn_rpm,190,320\ngamma_mN_m,35,73"
    factor_text = st.text_area("Factors · name,low,high", value=default_factors, key=f"pl_utube_sweep_factors_{profile}")
    c1, c2, c3 = st.columns(3)
    method = c1.selectbox("DOE", ["latin-hypercube", "full-factorial", "random"], key=f"pl_utube_sweep_method_{profile}")
    samples = int(c2.number_input("Samples", min_value=2, max_value=200, value=24, step=1, key=f"pl_utube_sweep_samples_{profile}"))
    seed = int(c3.number_input("Seed", min_value=0, max_value=2_147_483_647, value=0, step=1, key=f"pl_utube_sweep_seed_{profile}"))
    try:
        factors = _parse_factor_lines(factor_text)
        unknown = sorted({str(x["name"]) for x in factors} - set(accepted))
        if unknown:
            raise ValueError(f"factors are not adapter parameters: {unknown}")
        design = design_experiment(factors, method=method, samples=samples, seed=seed)
        rows = design["rows"]
    except Exception as exc:
        st.warning(f"DOE preview unavailable: {exc}")
        return
    st.dataframe(pd.DataFrame(rows).head(200), hide_index=True, width="stretch")
    st.caption("This table is a prospective computational design only. Queueing does not execute the model and does not create experimental evidence.")
    if st.button("Queue U-Tube DOE as Sweep", type="primary", key=f"pl_utube_sweep_queue_{profile}"):
        try:
            job = sweeps.create_sweep_job(profile, "utube-rotation", rows)
            st.session_state[f"pl_utube_sweep_job_{profile}"] = job["id"]
            st.success(f"Queued {job['id']} · {job['point_count']} points · execution has not started.")
        except Exception as exc:
            st.error(f"Could not queue U-tube Sweep: {exc}")
    job_id = st.session_state.get(f"pl_utube_sweep_job_{profile}")
    if job_id:
        job = sweeps.read_sweep_job(str(job_id)) or {}
        st.json({k: job.get(k) for k in ("id", "adapter", "point_count", "status", "progress", "failed_points", "cached_points", "design_sha256")})
        if job.get("status") in {"queued", "interrupted", "failed", "cancelled"}:
            if st.button("Explicitly start U-Tube Sweep", key=f"pl_utube_sweep_start_{profile}"):
                try:
                    sweeps.start_sweep_job(str(job_id))
                    st.success("Explicit start requested. Completed results will re-enter the normal Sweep Feedback / Science Analysis pipeline.")
                except Exception as exc:
                    st.error(f"Could not start U-tube Sweep: {exc}")
    st.caption("Design → Queue → explicit Start → Sweep result → sensitivity / response surface / Morris / OpenPenguin. No step silently becomes experimental evidence.")


def render_utube_experiment(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("#### Rotating U-Tube Experiment")
    st.caption("Native deterministic model, domain-specific physical visualization, raw-data contracts, numerical convergence, theory–experiment validation, threshold-regime mapping and allow-listed DOE/Sweep execution.")
    tab_data, tab_theory, tab_phase, tab_validation, tab_numerics, tab_free, tab_sweep = st.tabs(["Data Contract", "Physical View", "Threshold Map", "Theory ↔ Experiment", "Numerical Convergence", "Free Energy", "DOE / Sweep"])
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
    with tab_phase:
        _phase_map_tab(st, profile)
    with tab_validation:
        if selected is None:
            st.info("Select a project source first.")
        else:
            _validation_tab(st, selected, profile)
    with tab_numerics:
        _numerics_tab(st, profile)
    with tab_free:
        _free_energy_tab(st, profile)
    with tab_sweep:
        _sweep_tab(st, profile)
    st.caption(BOUNDARY)
