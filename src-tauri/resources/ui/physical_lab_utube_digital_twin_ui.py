"""Project-backed digital-twin UI for the rotating U-tube experiment."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets, save_canonical_dataset
from physical_lab_utube_digital_twin import (
    BOUNDARY,
    compare_threshold_series,
    fit_first_order_rpm_lag,
    suggest_threshold_remeasurements,
)
from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M


def _dataset_frame(dataset: dict) -> pd.DataFrame:
    columns = dataset.get("columns") or {}
    return pd.DataFrame({str(k): list(v) for k, v in columns.items()})


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    out = []
    for name in frame.columns:
        if pd.to_numeric(frame[name], errors="coerce").notna().sum() >= 2:
            out.append(str(name))
    return out


def render_utube_digital_twin(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use the U-tube digital twin with persistent experiment data.")
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("---")
    st.markdown("#### U-Tube Measurement Digital Twin")
    st.caption(
        "Connect canonical project datasets to the 3-D threshold model and a reduced-order RPM response model. "
        "Use Measurement & Calibration Evidence / Data Bridge upstream; this workspace does not silently infer units or calibration status."
    )
    datasets = list_canonical_datasets(project_path)
    if not datasets:
        st.info("No canonical project datasets are available yet. Promote a numeric measurement table through Data Bridge first.")
        st.caption(BOUNDARY)
        return

    labels = [f"{d.get('name') or d['dataset_id']} · {d['dataset_id']}" for d in datasets]
    label = st.selectbox("Project dataset", labels, key=f"pl_ut_dt_dataset_{profile}")
    dataset = datasets[labels.index(label)]
    frame = _dataset_frame(dataset)
    numeric = _numeric_columns(frame)
    if len(numeric) < 2:
        st.warning("Selected dataset needs at least two numeric columns.")
        return

    st.caption(
        f"Rows: {len(frame)} · source profile: {dataset.get('profile') or 'unspecified'} · "
        f"sha256: {str(dataset.get('sha256') or '')[:16]}…"
    )
    tab_threshold, tab_dynamic = st.tabs(["Threshold twin", "RPM dynamic twin"])

    with tab_threshold:
        st.markdown("##### Observed threshold ↔ 3-D model")
        c1, c2 = st.columns(2)
        volume_col = c1.selectbox("Volume column / mL", numeric, key=f"pl_ut_dt_vcol_{profile}")
        observed_col = c2.selectbox("Observed threshold column / rpm", numeric, index=min(1, len(numeric)-1), key=f"pl_ut_dt_ngcol_{profile}")
        g1, g2, g3 = st.columns(3)
        rin = float(g1.number_input("R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_dt_rin_{profile}"))
        a = float(g2.number_input("a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_dt_a_{profile}"))
        nq = int(g3.number_input("Quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_dt_nq_{profile}"))

        if st.button("Run threshold digital twin", type="primary", key=f"pl_ut_dt_threshold_go_{profile}"):
            try:
                twin = compare_threshold_series(frame[volume_col], frame[observed_col], rin_m=rin, a_m=a, nq=nq)
                st.session_state[f"pl_ut_dt_threshold_result_{profile}"] = (twin, dataset, volume_col, observed_col)
            except Exception as exc:
                st.error(str(exc))

        saved = st.session_state.get(f"pl_ut_dt_threshold_result_{profile}")
        if saved:
            twin, source_dataset, saved_v, saved_obs = saved
            result = twin["frame"]
            metrics = twin["metrics"]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("RMSE", f"{metrics['rmse_rpm']:.3f} rpm")
            m2.metric("Bias", f"{metrics['bias_rpm']:.3f} rpm")
            m3.metric("Max |residual|", f"{metrics['max_abs_residual_rpm']:.3f} rpm")
            m4.metric("Affine scale", f"{metrics['affine_scale']:.5g}")

            fig = go.Figure()
            fig.add_scatter(x=result["V_mL"], y=result["observed_threshold_rpm"], mode="markers+lines", name="Observed")
            fig.add_scatter(x=result["V_mL"], y=result["model_threshold_rpm"], mode="markers+lines", name="3-D model")
            fig.update_layout(title="Threshold digital twin", xaxis_title="Volume / mL", yaxis_title="Threshold / rpm")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

            residual_fig = go.Figure()
            residual_fig.add_scatter(x=result["V_mL"], y=result["residual_rpm"], mode="markers+lines", name="Observed − model")
            residual_fig.add_hline(y=0.0)
            residual_fig.update_layout(title="Threshold residual", xaxis_title="Volume / mL", yaxis_title="Residual / rpm")
            st.plotly_chart(residual_fig, width="stretch", config={"displaylogo": False})
            st.dataframe(result, hide_index=True, width="stretch")

            try:
                suggestions = suggest_threshold_remeasurements(twin, count=min(3, len(result))) if len(result) >= 3 else []
                if suggestions:
                    st.markdown("##### Residual-guided remeasurement priorities")
                    st.dataframe(pd.DataFrame(suggestions), hide_index=True, width="stretch")
                    st.caption("Priority is a residual/gradient heuristic from the shared Digital Twin core; it is not expected information gain.")
            except Exception as exc:
                st.caption(f"Remeasurement priority unavailable: {exc}")

            if st.button("Save threshold twin dataset", key=f"pl_ut_dt_threshold_save_{profile}"):
                rec = save_canonical_dataset(
                    project_path,
                    name=f"{source_dataset.get('name') or 'utube'} threshold twin",
                    profile=profile,
                    columns={k: result[k].tolist() for k in result.columns},
                    units={"V_mL": "mL", "observed_threshold_rpm": "rpm", "model_threshold_rpm": "rpm", "residual_rpm": "rpm", "abs_residual_rpm": "rpm"},
                    source=str(source_dataset.get("dataset_id") or ""),
                    notes="Derived U-tube threshold digital-twin comparison; see source dataset for measurement provenance.",
                )
                st.success(f"Saved {rec['dataset_id']} · sha256 {rec['sha256'][:12]}…")
            st.caption(twin["boundary"])

    with tab_dynamic:
        st.markdown("##### Commanded RPM → measured RPM reduced-order response")
        if len(numeric) < 3:
            st.info("Dynamic fitting needs numeric time, commanded-RPM and measured-RPM columns.")
        else:
            c1, c2, c3 = st.columns(3)
            time_col = c1.selectbox("Time column / s", numeric, key=f"pl_ut_dt_tcol_{profile}")
            command_col = c2.selectbox("Commanded RPM column", numeric, index=min(1, len(numeric)-1), key=f"pl_ut_dt_cmdcol_{profile}")
            measured_col = c3.selectbox("Measured RPM column", numeric, index=min(2, len(numeric)-1), key=f"pl_ut_dt_meascol_{profile}")
            b1, b2 = st.columns(2)
            tau_lo = float(b1.number_input("τ lower bound / s", min_value=0.001, value=0.02, key=f"pl_ut_dt_tlo_{profile}"))
            tau_hi = float(b2.number_input("τ upper bound / s", min_value=0.002, value=30.0, key=f"pl_ut_dt_thi_{profile}"))
            if st.button("Fit RPM response", type="primary", key=f"pl_ut_dt_dyn_go_{profile}"):
                try:
                    fit = fit_first_order_rpm_lag(frame[time_col], frame[command_col], frame[measured_col], tau_bounds_s=(tau_lo, tau_hi))
                    st.session_state[f"pl_ut_dt_dyn_result_{profile}"] = (fit, dataset)
                except Exception as exc:
                    st.error(str(exc))

            saved_dynamic = st.session_state.get(f"pl_ut_dt_dyn_result_{profile}")
            if saved_dynamic:
                fit, source_dataset = saved_dynamic
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("τ", f"{fit['tau_s']:.4g} s")
                d2.metric("2% settling ≈ 4τ", f"{fit['settling_time_2pct_s']:.4g} s")
                d3.metric("RMSE", f"{fit['rmse_rpm']:.3f} rpm")
                d4.metric("R²", "n/a" if fit["r2"] is None else f"{fit['r2']:.5g}")
                dyn = pd.DataFrame({
                    "time_s": fit["time_s"],
                    "commanded_rpm": fit["commanded_rpm"],
                    "measured_rpm": fit["measured_rpm"],
                    "predicted_rpm": fit["predicted_rpm"],
                    "residual_rpm": fit["residual_rpm"],
                })
                fig = go.Figure()
                fig.add_scatter(x=dyn["time_s"], y=dyn["commanded_rpm"], mode="lines", name="Command")
                fig.add_scatter(x=dyn["time_s"], y=dyn["measured_rpm"], mode="lines+markers", name="Measured")
                fig.add_scatter(x=dyn["time_s"], y=dyn["predicted_rpm"], mode="lines", name="First-order twin")
                fig.update_layout(title="RPM dynamic twin", xaxis_title="Time / s", yaxis_title="RPM")
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                st.dataframe(dyn, hide_index=True, width="stretch")
                if st.button("Save dynamic twin dataset", key=f"pl_ut_dt_dyn_save_{profile}"):
                    rec = save_canonical_dataset(
                        project_path,
                        name=f"{source_dataset.get('name') or 'utube'} RPM dynamic twin",
                        profile=profile,
                        columns={k: dyn[k].tolist() for k in dyn.columns},
                        units={"time_s": "s", "commanded_rpm": "rpm", "measured_rpm": "rpm", "predicted_rpm": "rpm", "residual_rpm": "rpm"},
                        source=str(source_dataset.get("dataset_id") or ""),
                        notes=f"First-order reduced-order RPM response fit; tau_s={fit['tau_s']:.9g}.",
                    )
                    st.success(f"Saved {rec['dataset_id']} · sha256 {rec['sha256'][:12]}…")
                st.caption(fit["boundary"])

    st.caption(BOUNDARY)
