"""Tolerance-aware U-tube engineering, experiment, verification and digital-twin UI."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
import physical_lab_requirements_verification as requirements
from physical_lab_digital_twin import fit_model_affine, suggest_residual_measurement_points
from physical_lab_project_interop import list_canonical_datasets, save_canonical_dataset
from physical_lab_utube_advanced import (
    BOUNDARY,
    adaptive_threshold_plan,
    pareto_robust_design,
    robust_design_space,
    verification_requirements,
)
from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M, threshold

UTUBE_TWIN_BOUNDARY = (
    "U-tube digital-twin results are model-to-measurement comparisons within declared dataset conventions. "
    "Threshold residuals do not by themselves validate the model. The fitted RPM time constant is a first-order reduced-order apparatus descriptor, "
    "not viscosity, contact-angle hysteresis, a hardware safety margin or a complete fluid-dynamics identification."
)


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


def compare_threshold_twin(
    volumes_ml: Iterable[float], observed_threshold_rpm: Iterable[float], *,
    rin_m: float = DEFAULT_R_IN_M, a_m: float = DEFAULT_A_M, nq: int = 48,
) -> dict[str, Any]:
    rows: list[dict[str, float]] = []
    for volume, observed in zip(volumes_ml, observed_threshold_rpm):
        try:
            volume = float(volume); observed = float(observed)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(volume) and math.isfinite(observed) and volume > 0 and observed > 0):
            continue
        modeled = float(threshold(volume, rin=float(rin_m), a=float(a_m), nq=int(nq)))
        rows.append({
            "V_mL": volume,
            "observed_threshold_rpm": observed,
            "model_threshold_rpm": modeled,
            "residual_rpm": observed - modeled,
            "abs_residual_rpm": abs(observed - modeled),
        })
    if len(rows) < 2:
        raise ValueError("at least two finite positive volume/threshold observations are required")
    frame = pd.DataFrame(rows).sort_values("V_mL", kind="stable").reset_index(drop=True)
    residual = frame["residual_rpm"].to_numpy(float)
    affine = fit_model_affine(frame["observed_threshold_rpm"], frame["model_threshold_rpm"])
    return {
        "frame": frame,
        "metrics": {
            "n": int(len(frame)),
            "rmse_rpm": float(np.sqrt(np.mean(residual * residual))),
            "mae_rpm": float(np.mean(np.abs(residual))),
            "bias_rpm": float(np.mean(residual)),
            "max_abs_residual_rpm": float(np.max(np.abs(residual))),
            "affine_scale": float(affine.scale),
            "affine_offset_rpm": float(affine.offset),
            "affine_rmse_before_rpm": float(affine.rmse_before),
            "affine_rmse_after_rpm": float(affine.rmse_after),
        },
        "geometry": {"R_in_m": float(rin_m), "a_m": float(a_m), "quadrature_order": int(nq)},
        "boundary": "Affine discrepancy is descriptive correction only; it is not physical parameter inference or validation evidence by itself.",
    }


def suggest_threshold_remeasurements(twin: dict[str, Any], *, count: int = 3) -> list[dict[str, float]]:
    frame = twin.get("frame")
    if not isinstance(frame, pd.DataFrame) or len(frame) < 3:
        return []
    suggestions = suggest_residual_measurement_points(frame["V_mL"], frame["observed_threshold_rpm"], frame["model_threshold_rpm"], count=count)
    return [{"V_mL": float(r["position"]), "residual_rpm": float(r["residual"]), "priority_score": float(r["score"])} for r in suggestions]


def first_order_rpm_response(time_s: Iterable[float], commanded_rpm: Iterable[float], tau_s: float, *, initial_rpm: float | None = None) -> list[float]:
    t = np.asarray(list(time_s), dtype=float); u = np.asarray(list(commanded_rpm), dtype=float)
    if len(t) != len(u) or len(t) < 2:
        raise ValueError("time and commanded RPM must contain at least two paired samples")
    if not np.isfinite(t).all() or not np.isfinite(u).all() or np.any(np.diff(t) <= 0):
        raise ValueError("time must be finite and strictly increasing; commanded RPM must be finite")
    tau = float(tau_s)
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("tau_s must be positive and finite")
    y = np.empty_like(u); y[0] = float(u[0] if initial_rpm is None else initial_rpm)
    for i in range(1, len(u)):
        alpha = math.exp(-float(t[i] - t[i - 1]) / tau)
        y[i] = u[i - 1] + (y[i - 1] - u[i - 1]) * alpha
    return y.tolist()


def fit_first_order_rpm_lag(
    time_s: Iterable[float], commanded_rpm: Iterable[float], measured_rpm: Iterable[float], *,
    tau_bounds_s: tuple[float, float] = (0.02, 30.0), grid_points: int = 240,
) -> dict[str, Any]:
    rows = []
    for t, u, y in zip(time_s, commanded_rpm, measured_rpm):
        try: t = float(t); u = float(u); y = float(y)
        except (TypeError, ValueError): continue
        if math.isfinite(t) and math.isfinite(u) and math.isfinite(y): rows.append((t, u, y))
    if len(rows) < 4:
        raise ValueError("at least four finite time/command/measured samples are required")
    rows.sort(key=lambda x: x[0])
    t = np.asarray([r[0] for r in rows], dtype=float); u = np.asarray([r[1] for r in rows], dtype=float); y = np.asarray([r[2] for r in rows], dtype=float)
    if np.any(np.diff(t) <= 0): raise ValueError("time values must be unique and strictly increasing")
    lo, hi = map(float, tau_bounds_s)
    if not (0 < lo < hi): raise ValueError("tau bounds must satisfy 0 < lower < upper")
    points = int(grid_points)
    if points < 20 or points > 4000: raise ValueError("grid_points must be in 20..4000")
    best = None
    for tau in np.geomspace(lo, hi, points):
        pred = np.asarray(first_order_rpm_response(t, u, float(tau), initial_rpm=float(y[0])), dtype=float)
        residual = y - pred; rmse = float(np.sqrt(np.mean(residual * residual)))
        if best is None or rmse < best[0]: best = (rmse, float(tau), pred, residual)
    rmse, tau, pred, residual = best
    sst = float(np.sum((y - np.mean(y)) ** 2)); sse = float(np.sum(residual * residual))
    return {
        "tau_s": tau, "rmse_rpm": rmse, "mae_rpm": float(np.mean(np.abs(residual))), "bias_rpm": float(np.mean(residual)),
        "r2": None if sst <= 1e-15 else float(1.0 - sse / sst), "settling_time_2pct_s": float(4.0 * tau),
        "time_s": t.tolist(), "commanded_rpm": u.tolist(), "measured_rpm": y.tolist(), "predicted_rpm": pred.tolist(), "residual_rpm": residual.tolist(),
        "boundary": "First-order reduced-order fit only. Tau summarizes observed command-to-speed lag and must not be interpreted as viscosity or a hardware safety constant.",
    }


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
            frame = robust_design_space(volumes_ml=_numbers(volumes_text), rin_values_m=_numbers(rin_text), a_values_m=_numbers(a_text), volume_tolerance_ml=vtol, rin_tolerance_m=rtol, a_tolerance_m=atol, target_threshold_rpm=target)
            st.session_state[f"pl_ut_rob_frame_{profile}"] = pareto_robust_design(frame)
        except Exception as exc: st.warning(f"Robust design unavailable: {exc}")
    frame = st.session_state.get(f"pl_ut_rob_frame_{profile}")
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        m1, m2, m3 = st.columns(3); m1.metric("Nominal designs", len(frame)); m2.metric("Pareto candidates", int(frame["pareto"].sum())); m3.metric("Best separation floor", f"{frame['separation_floor_rpm'].max():.3f} rpm")
        st.dataframe(frame.head(300), hide_index=True, width="stretch")
        st.plotly_chart(px.scatter(frame, x="worst_abs_target_error_rpm", y="threshold_span_rpm", color="separation_floor_rpm", symbol="pareto", hover_data=["V_mL", "R_in_m", "a_m"], title="Robust-design Pareto view"), width="stretch", config={"displaylogo": False})
    st.caption("Tolerance corners are deterministic screening cases, not probability distributions or process-capability claims.")


def _adaptive_planner(st: Any, profile: str) -> None:
    st.markdown("##### Adaptive threshold sampling")
    c1, c2, c3 = st.columns(3)
    volume = float(c1.number_input("Planning V / mL", min_value=0.01, value=3.0, key=f"pl_ut_adapt_v_{profile}")); nq = int(c2.number_input("Quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_adapt_nq_{profile}")); target_width = float(c3.number_input("Target empirical bracket / rpm", min_value=0.1, value=2.0, key=f"pl_ut_adapt_width_{profile}"))
    text = st.text_area("Observed classifications · `rpm,below` / `rpm,above`", value="", placeholder="240,below\n260,above", key=f"pl_ut_adapt_obs_{profile}")
    try:
        prediction = threshold(volume, nq=nq); result = adaptive_threshold_plan(_observations(text), prediction, target_bracket_rpm=target_width)
        a, b, c = st.columns(3); a.metric("Model n_g", f"{prediction:.3f} rpm"); b.metric("Planner state", result["status"]); c.metric("Bracket width", "—" if result["empirical_bracket_width_rpm"] is None else f"{result['empirical_bracket_width_rpm']:.3f} rpm")
        st.json(result)
    except Exception as exc: st.warning(f"Adaptive planning unavailable: {exc}")


def _verification(st: Any, profile: str) -> None:
    st.markdown("##### U-Tube verification requirement templates")
    c1, c2, c3, c4 = st.columns(4)
    target = float(c1.number_input("Target n_g / rpm", min_value=1.0, value=250.0, key=f"pl_ut_req_target_{profile}")); tol = float(c2.number_input("Threshold tolerance / rpm", min_value=0.1, value=5.0, key=f"pl_ut_req_tol_{profile}")); sep = float(c3.number_input("Minimum n_g−n_c / rpm", min_value=0.0, value=10.0, key=f"pl_ut_req_sep_{profile}")); num = float(c4.number_input("Max numerical Δn_g / rpm", min_value=0.001, value=0.25, key=f"pl_ut_req_num_{profile}"))
    matrix = verification_requirements(target_threshold_rpm=target, threshold_tolerance_rpm=tol, minimum_separation_rpm=sep, maximum_numerical_change_rpm=num)
    st.dataframe(matrix[["requirement_id", "statement", "verification_method", "verification_activity", "success_criteria"]], hide_index=True, width="stretch")
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if active and st.button("Register templates in current Project", type="primary", key=f"pl_ut_req_register_{profile}"):
        created = []
        for row in matrix.to_dict("records"):
            rec = requirements.register_requirement(Path(active), requirement_id=str(row["requirement_id"]), statement=str(row["statement"]), verification_method=str(row["verification_method"]), verification_activity=str(row["verification_activity"]), success_criteria=str(row["success_criteria"]), references=[], source_document="U-Tube Advanced Physics & Engineering", source_locator="Verification Matrix template", rationale=str(row["rationale"]), level="subsystem", intended_use="U-tube model development and project evidence review")
            created.append(str(rec["requirement_id"]))
        st.success("Registered/updated: " + ", ".join(created))


def _dataset_frame(dataset: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame({str(k): list(v) for k, v in (dataset.get("columns") or {}).items()})


def _digital_twin(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    st.markdown("#### U-Tube Measurement Digital Twin")
    st.caption("Canonical project measurements → 3-D threshold residuals / remeasurement priorities / reduced-order RPM dynamics.")
    if not active or not (Path(active) / "project.json").exists():
        st.info("Open a Project and promote measurement data through Data Bridge first."); return
    project_path = Path(active); datasets = list_canonical_datasets(project_path)
    if not datasets:
        st.info("No canonical project datasets yet."); return
    labels = [f"{d.get('name') or d['dataset_id']} · {d['dataset_id']}" for d in datasets]
    dataset = datasets[labels.index(st.selectbox("Twin dataset", labels, key=f"pl_ut_twin_ds_{profile}"))]
    frame = _dataset_frame(dataset)
    numeric = [str(c) for c in frame.columns if pd.to_numeric(frame[c], errors="coerce").notna().sum() >= 2]
    if len(numeric) < 2:
        st.warning("Dataset needs at least two numeric columns."); return
    tab_threshold, tab_dynamic = st.tabs(["Threshold twin", "RPM dynamic twin"])
    with tab_threshold:
        c1, c2, c3, c4, c5 = st.columns(5)
        vcol = c1.selectbox("V / mL", numeric, key=f"pl_ut_twin_v_{profile}"); ocol = c2.selectbox("Observed n_g / rpm", numeric, index=min(1, len(numeric)-1), key=f"pl_ut_twin_o_{profile}"); rin = float(c3.number_input("R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_twin_r_{profile}")); a = float(c4.number_input("a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_twin_a_{profile}")); nq = int(c5.number_input("nq", 12, 128, 48, 4, key=f"pl_ut_twin_nq_{profile}"))
        if st.button("Run threshold twin", type="primary", key=f"pl_ut_twin_go_{profile}"):
            try: st.session_state[f"pl_ut_twin_result_{profile}"] = compare_threshold_twin(frame[vcol], frame[ocol], rin_m=rin, a_m=a, nq=nq)
            except Exception as exc: st.error(str(exc))
        twin = st.session_state.get(f"pl_ut_twin_result_{profile}")
        if twin:
            tf = twin["frame"]; m = twin["metrics"]; q1,q2,q3,q4 = st.columns(4); q1.metric("RMSE", f"{m['rmse_rpm']:.3f} rpm"); q2.metric("Bias", f"{m['bias_rpm']:.3f} rpm"); q3.metric("Max |residual|", f"{m['max_abs_residual_rpm']:.3f} rpm"); q4.metric("Affine scale", f"{m['affine_scale']:.5g}")
            fig = go.Figure(); fig.add_scatter(x=tf["V_mL"], y=tf["observed_threshold_rpm"], mode="markers+lines", name="Observed"); fig.add_scatter(x=tf["V_mL"], y=tf["model_threshold_rpm"], mode="markers+lines", name="3-D model"); fig.update_layout(title="Threshold digital twin", xaxis_title="Volume / mL", yaxis_title="Threshold / rpm"); st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            suggestions = suggest_threshold_remeasurements(twin, count=min(3, len(tf)))
            if suggestions: st.dataframe(pd.DataFrame(suggestions), hide_index=True, width="stretch")
            if st.button("Save threshold twin dataset", key=f"pl_ut_twin_save_{profile}"):
                rec = save_canonical_dataset(project_path, name=f"{dataset.get('name') or 'utube'} threshold twin", profile=profile, columns={k: tf[k].tolist() for k in tf.columns}, units={"V_mL":"mL","observed_threshold_rpm":"rpm","model_threshold_rpm":"rpm","residual_rpm":"rpm","abs_residual_rpm":"rpm"}, source=str(dataset.get("dataset_id") or ""), notes="Derived U-tube threshold twin; source dataset retains measurement provenance.")
                st.success(f"Saved {rec['dataset_id']}")
            st.caption(twin["boundary"])
    with tab_dynamic:
        if len(numeric) < 3:
            st.info("Dynamic twin needs time, command RPM and measured RPM columns.")
        else:
            c1,c2,c3,c4,c5 = st.columns(5)
            tcol = c1.selectbox("Time / s", numeric, key=f"pl_ut_dyn_t_{profile}"); ucol = c2.selectbox("Command RPM", numeric, index=min(1,len(numeric)-1), key=f"pl_ut_dyn_u_{profile}"); ycol = c3.selectbox("Measured RPM", numeric, index=min(2,len(numeric)-1), key=f"pl_ut_dyn_y_{profile}"); lo = float(c4.number_input("τ min / s", min_value=0.001, value=0.02, key=f"pl_ut_dyn_lo_{profile}")); hi = float(c5.number_input("τ max / s", min_value=0.002, value=30.0, key=f"pl_ut_dyn_hi_{profile}"))
            if st.button("Fit RPM dynamic twin", type="primary", key=f"pl_ut_dyn_go_{profile}"):
                try: st.session_state[f"pl_ut_dyn_result_{profile}"] = fit_first_order_rpm_lag(frame[tcol], frame[ucol], frame[ycol], tau_bounds_s=(lo,hi))
                except Exception as exc: st.error(str(exc))
            fit = st.session_state.get(f"pl_ut_dyn_result_{profile}")
            if fit:
                d1,d2,d3,d4 = st.columns(4); d1.metric("τ", f"{fit['tau_s']:.4g} s"); d2.metric("2% settling ≈4τ", f"{fit['settling_time_2pct_s']:.4g} s"); d3.metric("RMSE", f"{fit['rmse_rpm']:.3f} rpm"); d4.metric("R²", "n/a" if fit["r2"] is None else f"{fit['r2']:.5g}")
                df = pd.DataFrame({k:fit[k] for k in ["time_s","commanded_rpm","measured_rpm","predicted_rpm","residual_rpm"]})
                fig = go.Figure(); fig.add_scatter(x=df["time_s"], y=df["commanded_rpm"], mode="lines", name="Command"); fig.add_scatter(x=df["time_s"], y=df["measured_rpm"], mode="lines+markers", name="Measured"); fig.add_scatter(x=df["time_s"], y=df["predicted_rpm"], mode="lines", name="Twin"); fig.update_layout(title="RPM dynamic twin", xaxis_title="Time / s", yaxis_title="RPM"); st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                if st.button("Save dynamic twin dataset", key=f"pl_ut_dyn_save_{profile}"):
                    rec = save_canonical_dataset(project_path, name=f"{dataset.get('name') or 'utube'} RPM dynamic twin", profile=profile, columns={k:df[k].tolist() for k in df.columns}, units={"time_s":"s","commanded_rpm":"rpm","measured_rpm":"rpm","predicted_rpm":"rpm","residual_rpm":"rpm"}, source=str(dataset.get("dataset_id") or ""), notes=f"First-order reduced-order RPM response; tau_s={fit['tau_s']:.9g}.")
                    st.success(f"Saved {rec['dataset_id']}")
                st.caption(fit["boundary"])
    st.caption(UTUBE_TWIN_BOUNDARY)


def render_utube_robust_engineering(st: Any, profile: str) -> None:
    st.markdown("#### U-Tube Robust Design, Adaptive Experiment & Verification")
    tabs = st.tabs(["Robust Design & Pareto", "Adaptive Experiment", "Verification Matrix"])
    with tabs[0]: _robust_design(st, profile)
    with tabs[1]: _adaptive_planner(st, profile)
    with tabs[2]: _verification(st, profile)
    st.caption(BOUNDARY)
    _digital_twin(st, profile)
