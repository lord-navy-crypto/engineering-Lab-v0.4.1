"""Interactive advanced undulator spectrum studies for Physical Lab."""
from __future__ import annotations

from typing import Any

from physical_lab_undulator_spectrum import (
    angular_harmonic_map,
    beam_broadened_resonance,
    harmonic_spectrum,
)


def _plotly():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def render_undulator_spectrum_workspace(st: Any, namespace: dict | None = None) -> None:
    st.markdown("---")
    st.markdown("## Physical Lab · Undulator Spectrum & Beam Broadening Studio")
    st.caption(
        "Fast physics studies that complement the pinned RADIA → trajectory → radiation solver: "
        "finite-N harmonic structure, off-axis resonance red-shift, and beam energy-spread/divergence broadening."
    )

    params = dict((namespace or {}).get("current_params") or {})
    default_period_mm = float(params.get("period_mm", 50.0) or 50.0)

    c1, c2, c3, c4 = st.columns(4)
    period_mm = c1.number_input("Undulator period λu (mm)", min_value=0.1, value=default_period_mm, step=0.5, key="pl_us_period")
    gamma = c2.number_input("Electron γ", min_value=1.01, value=100.0, step=1.0, key="pl_us_gamma")
    K = c3.number_input("Planar K", min_value=0.0, value=0.70, step=0.05, key="pl_us_k")
    periods = c4.number_input("Periods N", min_value=2, max_value=1000, value=int(params.get("periods", 20) or 20), step=1, key="pl_us_n")

    tab1, tab2, tab3 = st.tabs(["Harmonic spectrum", "Off-axis map", "Beam broadening"])
    go = _plotly()

    with tab1:
        a1, a2 = st.columns(2)
        theta = a1.number_input("Observation angle θ (mrad)", value=0.0, step=0.05, key="pl_us_theta")
        harmonic_text = a2.text_input("Harmonics", "1,3,5,7", key="pl_us_harmonics")
        if st.button("Run harmonic spectrum", type="primary", key="pl_us_run_spectrum"):
            try:
                hs = [int(x.strip()) for x in harmonic_text.split(",") if x.strip()]
                st.session_state["pl_us_spectrum"] = harmonic_spectrum(
                    period_m=float(period_mm) * 1e-3,
                    gamma=float(gamma), K=float(K), n_periods=int(periods),
                    theta_mrad=float(theta), harmonics=hs,
                )
            except Exception as exc:
                st.error(str(exc))
        result = st.session_state.get("pl_us_spectrum")
        if isinstance(result, dict):
            fig = go.Figure()
            fig.add_scatter(x=result["energy_eV"], y=result["relative_intensity"], mode="lines", name="finite-N spectrum")
            for row in result["harmonics"]:
                if row["coupling_JJ2"] > 0:
                    fig.add_vline(x=row["resonance_energy_eV"], line_dash="dash")
            fig.update_layout(title="Finite-N planar-undulator harmonic structure", xaxis_title="Photon energy (eV)", yaxis_title="Relative intensity", height=470)
            st.plotly_chart(fig, width="stretch")
            st.dataframe(result["harmonics"], width="stretch", hide_index=True)
            st.caption(result["boundary"])

    with tab2:
        b1, b2, b3 = st.columns(3)
        harmonic = b1.selectbox("Harmonic", [1, 3, 5, 7], key="pl_us_map_h")
        theta_max = b2.number_input("Map half-angle (mrad)", min_value=0.05, value=3.0, step=0.25, key="pl_us_map_tmax")
        points = b3.select_slider("Map grid", options=[31, 51, 81, 121], value=81, key="pl_us_map_points")
        if st.button("Run angular resonance map", key="pl_us_run_map"):
            try:
                st.session_state["pl_us_map"] = angular_harmonic_map(
                    period_m=float(period_mm) * 1e-3, gamma=float(gamma), K=float(K),
                    harmonic=int(harmonic), theta_max_mrad=float(theta_max), points=int(points),
                )
            except Exception as exc:
                st.error(str(exc))
        amap = st.session_state.get("pl_us_map")
        if isinstance(amap, dict):
            heat = go.Figure(data=go.Heatmap(
                x=amap["theta_axis_mrad"], y=amap["theta_axis_mrad"], z=amap["resonance_energy_eV"], colorbar={"title": "eV"}
            ))
            heat.update_layout(title="Resonance energy across observer angle", xaxis_title="θx (mrad)", yaxis_title="θy (mrad)", height=560)
            st.plotly_chart(heat, width="stretch")
            c1m, c2m = st.columns(2)
            c1m.metric("On-axis energy", f"{amap['on_axis_energy_eV']:.6g} eV")
            c2m.metric("Minimum map energy", f"{amap['minimum_energy_eV']:.6g} eV")
            st.caption(amap["boundary"])

    with tab3:
        d1, d2, d3 = st.columns(3)
        spread = d1.number_input("Relative energy spread σγ/γ", min_value=0.0, value=0.001, step=0.0001, format="%.5f", key="pl_us_spread")
        divergence = d2.number_input("Angular divergence RMS (mrad)", min_value=0.0, value=0.05, step=0.01, key="pl_us_div")
        sample_count = d3.select_slider("Monte Carlo samples", options=[5000, 10000, 30000, 60000], value=30000, key="pl_us_mc")
        if st.button("Run beam-broadened resonance", key="pl_us_run_beam"):
            try:
                st.session_state["pl_us_beam"] = beam_broadened_resonance(
                    period_m=float(period_mm) * 1e-3, gamma=float(gamma), K=float(K),
                    harmonic=1, relative_energy_spread_rms=float(spread),
                    angular_divergence_rms_mrad=float(divergence), samples=int(sample_count),
                )
            except Exception as exc:
                st.error(str(exc))
        beam = st.session_state.get("pl_us_beam")
        if isinstance(beam, dict):
            fig = go.Figure()
            fig.add_bar(x=beam["bin_center_eV"], y=beam["density"], name="sampled resonance density")
            fig.add_vline(x=beam["nominal_energy_eV"], line_dash="dash", annotation_text="nominal")
            fig.update_layout(title="Resonance-energy broadening from beam spread", xaxis_title="Photon energy (eV)", yaxis_title="Density", height=470)
            st.plotly_chart(fig, width="stretch")
            m1, m2, m3 = st.columns(3)
            m1.metric("Relative RMS linewidth", f"{100*beam['relative_rms_linewidth']:.4g}%")
            m2.metric("P05", f"{beam['p05_eV']:.6g} eV")
            m3.metric("P95", f"{beam['p95_eV']:.6g} eV")
            st.caption(beam["boundary"])
