"""UI for eighth-wave signal-processing and empirical system-identification studies."""
from __future__ import annotations
from typing import Any

from physical_lab_model_depth_viii import chirp_frf_experiment, spectral_leakage_study


def _plotly():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_chirp_frf(st: Any) -> None:
    st.markdown("### Experimental-style system ID · Welch FRF and coherence")
    st.caption("Start from measured-like input/output time series, estimate spectra and coherence, then compare H1/H2 with a known SDOF reference.")
    c1,c2,c3,c4 = st.columns(4)
    k = float(c1.number_input("True stiffness k", 1.0, 100.0, 18.0, 1.0, key="pl_viii_k"))
    c = float(c2.number_input("True damping c", 0.0, 10.0, 0.7, 0.1, key="pl_viii_c"))
    noise = float(c3.number_input("Output noise σ", 0.0, 0.05, 0.002, 0.001, format="%.3f", key="pl_viii_noise"))
    nperseg = int(c4.selectbox("Welch segment length", [256,512,1024,2048], index=2, key="pl_viii_nperseg"))
    window = st.selectbox("Window", ["hann","boxcar"], key="pl_viii_window")
    if st.button("Run chirp FRF experiment", type="primary", key="pl_viii_run"):
        with st.spinner("Simulating chirp response and estimating Welch spectra / FRFs..."):
            st.session_state["pl_viii_frf"] = chirp_frf_experiment(stiffness=k, damping=c, output_noise_std=noise, nperseg=nperseg, window=window)
    r = st.session_state.get("pl_viii_frf")
    if not r:
        return
    import numpy as np
    f = np.asarray(r["frequency_hz"], dtype=float)
    h1 = np.asarray(r["H1"]["real"], dtype=float) + 1j*np.asarray(r["H1"]["imag"], dtype=float)
    h2 = np.asarray(r["H2"]["real"], dtype=float) + 1j*np.asarray(r["H2"]["imag"], dtype=float)
    href = np.asarray(r["reference_H"]["real"], dtype=float) + 1j*np.asarray(r["reference_H"]["imag"], dtype=float)
    coh = np.asarray(r["coherence"], dtype=float)
    band = (f >= r["chirp_band_hz"][0]) & (f <= r["chirp_band_hz"][1])
    median_coh = float(np.median(coh[band])) if np.any(band) else float("nan")
    a,b,cmet,d = st.columns(4)
    a.metric("Natural frequency", f"{r['truth']['natural_frequency_hz']:.4g} Hz")
    b.metric("Median band coherence", f"{median_coh:.3f}")
    cmet.metric("H1 median |Δmag|", "—" if r['H1_error']['median_magnitude_error_db'] is None else f"{r['H1_error']['median_magnitude_error_db']:.3g} dB")
    d.metric("H1 median |Δphase|", "—" if r['H1_error']['median_phase_error_deg'] is None else f"{r['H1_error']['median_phase_error_deg']:.3g}°")
    go = _plotly()
    mag = go.Figure()
    mag.add_scatter(x=f, y=np.abs(href), mode="lines", name="Reference |H|")
    mag.add_scatter(x=f, y=np.abs(h1), mode="lines", name="H1")
    mag.add_scatter(x=f, y=np.abs(h2), mode="lines", name="H2")
    mag.update_layout(title="Empirical transfer-function magnitude", xaxis_title="Frequency (Hz)", yaxis_title="|H|", height=450)
    st.plotly_chart(mag, width="stretch")
    co = go.Figure(); co.add_scatter(x=f, y=coh, mode="lines", name="γ²")
    co.add_hline(y=0.5, line_dash="dash")
    co.update_layout(title="Magnitude-squared coherence", xaxis_title="Frequency (Hz)", yaxis_title="γ²", yaxis_range=[0,1.02], height=400)
    st.plotly_chart(co, width="stretch")
    phase = go.Figure()
    phase.add_scatter(x=f, y=np.angle(href, deg=True), mode="lines", name="Reference")
    phase.add_scatter(x=f, y=np.angle(h1, deg=True), mode="lines", name="H1")
    phase.add_scatter(x=f, y=np.angle(h2, deg=True), mode="lines", name="H2")
    phase.update_layout(title="Empirical FRF phase", xaxis_title="Frequency (Hz)", yaxis_title="Phase (deg)", height=420)
    st.plotly_chart(phase, width="stretch")
    st.caption(r["boundary"])


def _render_leakage(st: Any) -> None:
    st.markdown("### Windowing · finite-record leakage")
    c1,c2=st.columns(2)
    tone=float(c1.number_input("Off-bin tone (Hz)",1.0,50.0,10.37,0.01,key="pl_viii_tone"))
    samples=int(c2.selectbox("Record samples",[512,1024,2048,4096],index=1,key="pl_viii_leak_n"))
    if st.button("Compare window leakage", key="pl_viii_leak_run"):
        st.session_state["pl_viii_leak"] = spectral_leakage_study(samples=samples,tone_hz=tone)
    r=st.session_state.get("pl_viii_leak")
    if not r:return
    st.dataframe(r["rows"],hide_index=True,width="stretch")
    st.caption(r["boundary"])


def render_model_depth_viii_workspace(st: Any, profile: str) -> None:
    if profile not in {"oscillation-integration","numerical-methods"}:
        return
    st.markdown("---")
    st.markdown("## Physical Lab · Model Depth VIII")
    tabs=st.tabs(["Chirp FRF / coherence","Window / leakage"])
    with tabs[0]: _render_chirp_frf(st)
    with tabs[1]: _render_leakage(st)
