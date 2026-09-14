"""Project-backed dynamic-threshold and hysteresis UI for the rotating U-tube."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets, save_canonical_dataset
from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M
from physical_lab_utube_hysteresis import BOUNDARY, analyze_hysteresis_sweeps, rate_sweep_prediction


def _frame(dataset: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame({str(k): list(v) for k, v in (dataset.get("columns") or {}).items()})


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(c) for c in frame.columns if pd.to_numeric(frame[c], errors="coerce").notna().sum() >= 3]


def _rate_list(text: str) -> list[float]:
    values = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    if not values or any((not np.isfinite(x) or x < 0) for x in values):
        raise ValueError("ramp rates must be finite, non-negative and comma separated")
    return values


def render_utube_hysteresis(st: Any, profile: str) -> None:
    st.markdown("---")
    st.markdown("#### U-Tube Dynamic Threshold & Hysteresis")
    st.caption(
        "Analyze paired spin-up / spin-down threshold measurements with a transparent reduced-order model: "
        "loop half-width = H + |dn/dt|·τ. Loop-center agreement with the static 3-D threshold is reported separately."
    )

    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    tab_fit, tab_predict = st.tabs(["Measured ramp hysteresis", "Rate-envelope prediction"])

    with tab_fit:
        if not active or not (Path(active) / "project.json").exists():
            st.info("Open an Engineering Lab Project and promote ramp measurements through Data Bridge to fit hysteresis evidence.")
        else:
            project_path = Path(active)
            datasets = list_canonical_datasets(project_path)
            if not datasets:
                st.info("No canonical datasets are available in the current Project.")
            else:
                labels = [f"{d.get('name') or d['dataset_id']} · {d['dataset_id']}" for d in datasets]
                selected = st.selectbox("Ramp dataset", labels, key=f"pl_ut_hys_dataset_{profile}")
                dataset = datasets[labels.index(selected)]
                frame = _frame(dataset)
                numeric = _numeric_columns(frame)
                if len(numeric) < 4:
                    st.warning("The selected dataset needs at least four numeric columns: volume, ramp rate, up threshold and down threshold.")
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    vcol = c1.selectbox("Volume / mL", numeric, key=f"pl_ut_hys_v_{profile}")
                    rcol = c2.selectbox("|dn/dt| / rpm s⁻¹", numeric, index=min(1, len(numeric)-1), key=f"pl_ut_hys_rate_{profile}")
                    upcol = c3.selectbox("Spin-up threshold / rpm", numeric, index=min(2, len(numeric)-1), key=f"pl_ut_hys_up_{profile}")
                    downcol = c4.selectbox("Spin-down threshold / rpm", numeric, index=min(3, len(numeric)-1), key=f"pl_ut_hys_down_{profile}")
                    g1, g2, g3 = st.columns(3)
                    rin = float(g1.number_input("R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_hys_rin_{profile}"))
                    a = float(g2.number_input("a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_hys_a_{profile}"))
                    nq = int(g3.number_input("Quadrature order", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_hys_nq_{profile}"))

                    if st.button("Fit dynamic threshold model", type="primary", key=f"pl_ut_hys_fit_{profile}"):
                        try:
                            result = analyze_hysteresis_sweeps(
                                frame[vcol], frame[rcol], frame[upcol], frame[downcol],
                                rin_m=rin, a_m=a, nq=nq,
                            )
                            st.session_state[f"pl_ut_hys_result_{profile}"] = (result, dataset)
                        except Exception as exc:
                            st.error(str(exc))

                    saved = st.session_state.get(f"pl_ut_hys_result_{profile}")
                    if saved:
                        result, source_dataset = saved
                        fit = result["fit"]
                        rf = result["frame"]
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Empirical H", f"{fit['quasi_static_halfwidth_rpm']:.3f} rpm")
                        m2.metric("Rate-lag τ", f"{fit['response_tau_s']:.4g} s")
                        m3.metric("Half-width RMSE", f"{fit['halfwidth_rmse_rpm']:.3f} rpm")
                        m4.metric("Center ↔ static RMSE", f"{fit['center_model_rmse_rpm']:.3f} rpm")

                        threshold_fig = go.Figure()
                        threshold_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["up_threshold_rpm"], mode="markers", name="Observed spin-up")
                        threshold_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["down_threshold_rpm"], mode="markers", name="Observed spin-down")
                        threshold_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["predicted_up_from_center_rpm"], mode="markers", name="Reduced-order up")
                        threshold_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["predicted_down_from_center_rpm"], mode="markers", name="Reduced-order down")
                        threshold_fig.update_layout(title="Measured dynamic thresholds vs ramp rate", xaxis_title="|dn/dt| / rpm s⁻¹", yaxis_title="Threshold / rpm")
                        st.plotly_chart(threshold_fig, width="stretch", config={"displaylogo": False})

                        width_fig = go.Figure()
                        width_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["loop_halfwidth_rpm"], mode="markers", name="Observed half-width")
                        width_fig.add_scatter(x=rf["ramp_rate_rpm_s"], y=rf["predicted_halfwidth_rpm"], mode="lines+markers", name="H + rate·τ")
                        width_fig.update_layout(title="Rate dependence of loop half-width", xaxis_title="|dn/dt| / rpm s⁻¹", yaxis_title="Half-width / rpm")
                        st.plotly_chart(width_fig, width="stretch", config={"displaylogo": False})

                        center_fig = go.Figure()
                        center_fig.add_scatter(x=rf["V_mL"], y=rf["loop_center_rpm"], mode="markers", name="Observed loop center")
                        center_fig.add_scatter(x=rf["V_mL"], y=rf["model_static_threshold_rpm"], mode="markers", name="3-D static n_g")
                        center_fig.update_layout(title="Loop center vs static 3-D threshold", xaxis_title="Volume / mL", yaxis_title="RPM")
                        st.plotly_chart(center_fig, width="stretch", config={"displaylogo": False})
                        st.dataframe(rf, hide_index=True, width="stretch")

                        if st.button("Save hysteresis analysis dataset", key=f"pl_ut_hys_save_{profile}"):
                            rec = save_canonical_dataset(
                                project_path,
                                name=f"{source_dataset.get('name') or 'utube'} dynamic-threshold analysis",
                                profile=profile,
                                columns={k: rf[k].tolist() for k in rf.columns},
                                units={
                                    "V_mL": "mL", "ramp_rate_rpm_s": "rpm/s", "up_threshold_rpm": "rpm",
                                    "down_threshold_rpm": "rpm", "loop_center_rpm": "rpm", "loop_halfwidth_rpm": "rpm",
                                    "loop_width_rpm": "rpm", "model_static_threshold_rpm": "rpm", "center_minus_model_rpm": "rpm",
                                    "predicted_halfwidth_rpm": "rpm", "halfwidth_residual_rpm": "rpm",
                                    "predicted_up_from_center_rpm": "rpm", "predicted_down_from_center_rpm": "rpm",
                                },
                                source=str(source_dataset.get("dataset_id") or ""),
                                notes=(
                                    f"Reduced-order dynamic-threshold fit: H={fit['quasi_static_halfwidth_rpm']:.9g} rpm; "
                                    f"tau={fit['response_tau_s']:.9g} s. These are empirical apparatus-level descriptors."
                                ),
                            )
                            st.success(f"Saved {rec['dataset_id']} · sha256 {rec['sha256'][:12]}…")
                        st.caption(result["boundary"])

    with tab_predict:
        c1, c2, c3, c4 = st.columns(4)
        volume = float(c1.number_input("Prediction V / mL", min_value=0.01, value=3.0, key=f"pl_ut_hys_pred_v_{profile}"))
        half = float(c2.number_input("Empirical H / rpm", min_value=0.0, value=2.0, step=0.25, key=f"pl_ut_hys_pred_h_{profile}"))
        tau = float(c3.number_input("Rate-lag τ / s", min_value=0.0, value=0.8, step=0.1, key=f"pl_ut_hys_pred_tau_{profile}"))
        rates_text = c4.text_input("Ramp rates / rpm s⁻¹", value="0,1,2,5,10", key=f"pl_ut_hys_pred_rates_{profile}")
        p1, p2, p3 = st.columns(3)
        rin = float(p1.number_input("Prediction R_in / m", min_value=0.001, value=DEFAULT_R_IN_M, format="%.6f", key=f"pl_ut_hys_pred_rin_{profile}"))
        a = float(p2.number_input("Prediction a / m", min_value=0.001, value=DEFAULT_A_M, format="%.6f", key=f"pl_ut_hys_pred_a_{profile}"))
        nq = int(p3.number_input("Prediction nq", min_value=12, max_value=128, value=48, step=4, key=f"pl_ut_hys_pred_nq_{profile}"))
        try:
            envelope = rate_sweep_prediction(
                volume, _rate_list(rates_text), response_tau_s=tau,
                quasi_static_halfwidth_rpm=half, rin_m=rin, a_m=a, nq=nq,
            )
            fig = go.Figure()
            fig.add_scatter(x=envelope["ramp_rate_rpm_s"], y=envelope["up_threshold_rpm"], mode="lines+markers", name="Predicted spin-up")
            fig.add_scatter(x=envelope["ramp_rate_rpm_s"], y=envelope["down_threshold_rpm"], mode="lines+markers", name="Predicted spin-down")
            fig.add_scatter(x=envelope["ramp_rate_rpm_s"], y=envelope["static_threshold_rpm"], mode="lines", name="Static 3-D n_g")
            fig.update_layout(title="Reduced-order dynamic threshold envelope", xaxis_title="|dn/dt| / rpm s⁻¹", yaxis_title="Threshold / rpm")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(envelope, hide_index=True, width="stretch")
            st.caption("At zero ramp rate, the model retains only the empirical ±H branch offset. Rate dependence adds |dn/dt|·τ symmetrically around the static threshold.")
        except Exception as exc:
            st.warning(f"Rate-envelope prediction unavailable: {exc}")

    st.caption(BOUNDARY)
