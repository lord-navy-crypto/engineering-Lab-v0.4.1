"""Interactive frequency-response workspace for Physical Lab dynamics Labs."""
from __future__ import annotations

from typing import Any

from physical_lab_frequency_response import duffing_frequency_sweep, linear_forced_response_sweep

SUPPORTED_PROFILES = {"nonlinear-chaos", "oscillation-integration"}


def _plotly():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _quality(name: str) -> dict[str, int]:
    return {
        "Fast": {"points": 13, "settle": 16, "observe": 5, "ppc": 48},
        "Standard": {"points": 21, "settle": 26, "observe": 7, "ppc": 64},
        "Deep": {"points": 31, "settle": 40, "observe": 10, "ppc": 84},
    }[name]


def _render_linear(st: Any) -> None:
    st.markdown("### Forced vibration · frequency response")
    st.caption(
        "Sweep a viscously damped single-degree-of-freedom oscillator through resonance. "
        "The time-domain RK4 result is independently compared with the analytic steady-state amplitude and phase."
    )
    c1, c2, c3, c4 = st.columns(4)
    omega_n = c1.number_input("Natural frequency ωₙ (rad/s)", min_value=0.1, max_value=30.0, value=2.0, step=0.1, key="pl_fr_linear_wn")
    zeta = c2.number_input("Damping ratio ζ", min_value=0.0, max_value=1.5, value=0.05, step=0.01, key="pl_fr_linear_zeta")
    force = c3.number_input("Force amplitude", min_value=0.0, max_value=20.0, value=1.0, step=0.1, key="pl_fr_linear_force")
    quality_name = c4.selectbox("Sweep quality", ["Fast", "Standard", "Deep"], index=1, key="pl_fr_linear_quality")
    c5, c6 = st.columns(2)
    start_ratio = c5.number_input("Start frequency ratio ω/ωₙ", min_value=0.1, max_value=3.0, value=0.30, step=0.05, key="pl_fr_linear_start")
    stop_ratio = c6.number_input("Stop frequency ratio ω/ωₙ", min_value=0.2, max_value=5.0, value=1.60, step=0.05, key="pl_fr_linear_stop")
    key = "pl_frequency_response_linear_result"
    if st.button("Run forced-response sweep", type="primary", key="pl_fr_linear_run"):
        if float(stop_ratio) <= float(start_ratio):
            st.error("Stop frequency ratio must be greater than start frequency ratio.")
        else:
            q = _quality(quality_name)
            with st.spinner("Integrating forced response across the frequency grid..."):
                st.session_state[key] = linear_forced_response_sweep(
                    omega_n=float(omega_n),
                    zeta=float(zeta),
                    force_amplitude=float(force),
                    frequency_start=float(start_ratio) * float(omega_n),
                    frequency_stop=float(stop_ratio) * float(omega_n),
                    frequency_points=q["points"],
                    settle_cycles=q["settle"],
                    observe_cycles=q["observe"],
                    points_per_cycle=q["ppc"],
                )
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the sweep to resolve resonance, phase lag, and numerical-vs-analytic frequency-response error.")
        return

    a, b, c, d = st.columns(4)
    a.metric("Numerical peak ω", f"{result['numerical_peak_frequency_rad_s']:.5g} rad/s")
    theoretical = result.get("theoretical_resonance_frequency_rad_s")
    b.metric("Analytic resonance ω", "—" if theoretical is None else f"{float(theoretical):.5g} rad/s")
    c.metric("Max amplitude error", f"{100.0 * float(result['max_amplitude_relative_error']):.4g}%")
    d.metric("Max phase error", f"{float(result['max_phase_absolute_error_rad']):.4g} rad")

    rows = result["rows"]
    go = _plotly()
    amp = go.Figure()
    amp.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["fundamental_amplitude"] for r in rows], mode="lines+markers", name="RK4 steady-state")
    amp.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["analytic_amplitude"] for r in rows], mode="lines", name="Analytic reference")
    amp.update_layout(title="Forced-response amplitude", xaxis_title="Frequency ratio ω/ωₙ", yaxis_title="Amplitude", height=460)
    st.plotly_chart(amp, width="stretch")

    phase = go.Figure()
    phase.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["phase_lag_rad"] for r in rows], mode="lines+markers", name="RK4 phase")
    phase.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["analytic_phase_lag_rad"] for r in rows], mode="lines", name="Analytic phase")
    phase.update_layout(title="Phase lag through resonance", xaxis_title="Frequency ratio ω/ωₙ", yaxis_title="Phase lag (rad)", height=430)
    st.plotly_chart(phase, width="stretch")

    error = go.Figure()
    error.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[100.0 * r["amplitude_relative_error"] for r in rows], mode="lines+markers", name="Amplitude error")
    error.update_layout(title="Numerical frequency-response error", xaxis_title="Frequency ratio ω/ωₙ", yaxis_title="Amplitude relative error (%)", height=400)
    st.plotly_chart(error, width="stretch")
    st.caption(result["boundary"])


def _render_duffing(st: Any) -> None:
    st.markdown("### Nonlinear resonance · Duffing continuation")
    st.caption(
        "Sweep a hardening Duffing oscillator upward and downward in drive frequency while carrying each final state into the next frequency. "
        "The comparison exposes branch-sensitive response that independent zero-state runs can miss."
    )
    c1, c2, c3, c4 = st.columns(4)
    zeta = c1.number_input("Damping ratio ζ", min_value=0.0, max_value=0.5, value=0.05, step=0.01, key="pl_fr_duffing_zeta")
    beta = c2.number_input("Cubic stiffness β", min_value=-5.0, max_value=8.0, value=1.0, step=0.1, key="pl_fr_duffing_beta")
    force = c3.number_input("Drive amplitude F", min_value=0.0, max_value=3.0, value=0.30, step=0.05, key="pl_fr_duffing_force")
    quality_name = c4.selectbox("Sweep quality", ["Fast", "Standard", "Deep"], index=1, key="pl_fr_duffing_quality")
    c5, c6, c7 = st.columns(3)
    omega0 = c5.number_input("Linear ω₀ (rad/s)", min_value=0.1, max_value=20.0, value=1.0, step=0.1, key="pl_fr_duffing_w0")
    start_ratio = c6.number_input("Start ω/ω₀", min_value=0.1, max_value=3.0, value=0.70, step=0.05, key="pl_fr_duffing_start")
    stop_ratio = c7.number_input("Stop ω/ω₀", min_value=0.2, max_value=4.0, value=1.60, step=0.05, key="pl_fr_duffing_stop")
    key = "pl_frequency_response_duffing_result"
    if st.button("Run nonlinear continuation sweep", type="primary", key="pl_fr_duffing_run"):
        if float(stop_ratio) <= float(start_ratio):
            st.error("Stop frequency ratio must be greater than start frequency ratio.")
        else:
            q = _quality(quality_name)
            with st.spinner("Integrating forward and reverse nonlinear frequency sweeps..."):
                st.session_state[key] = duffing_frequency_sweep(
                    omega_0=float(omega0),
                    zeta=float(zeta),
                    cubic_stiffness=float(beta),
                    force_amplitude=float(force),
                    frequency_start=float(start_ratio) * float(omega0),
                    frequency_stop=float(stop_ratio) * float(omega0),
                    frequency_points=q["points"],
                    settle_cycles=max(q["settle"], 24),
                    observe_cycles=q["observe"],
                    points_per_cycle=q["ppc"],
                )
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the continuation sweep to compare forward/reverse nonlinear response branches.")
        return

    a, b, c, d = st.columns(4)
    a.metric("Forward peak ω", f"{result['forward_peak_frequency_rad_s']:.5g} rad/s")
    b.metric("Forward peak amplitude", f"{result['forward_peak_amplitude']:.5g}")
    c.metric("Max branch gap", f"{result['max_branch_amplitude_gap']:.5g}")
    d.metric("Gap frequency", f"{result['max_branch_gap_frequency_rad_s']:.5g} rad/s")

    rows = result["rows"]
    go = _plotly()
    response = go.Figure()
    response.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["forward_amplitude"] for r in rows], mode="lines+markers", name="Forward continuation")
    response.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["reverse_amplitude"] for r in rows], mode="lines+markers", name="Reverse continuation")
    response.update_layout(title="Nonlinear frequency-response branches", xaxis_title="Frequency ratio ω/ω₀", yaxis_title="Fundamental amplitude", height=470)
    st.plotly_chart(response, width="stretch")

    gap = go.Figure()
    gap.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["branch_amplitude_gap"] for r in rows], mode="lines+markers", name="Branch gap")
    gap.update_layout(title="Forward/reverse branch sensitivity", xaxis_title="Frequency ratio ω/ω₀", yaxis_title="|A_forward − A_reverse|", height=410)
    st.plotly_chart(gap, width="stretch")

    residual = go.Figure()
    residual.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["forward_harmonic_residual_rms"] for r in rows], mode="lines+markers", name="Forward non-harmonic residual")
    residual.add_scatter(x=[r["frequency_ratio"] for r in rows], y=[r["reverse_harmonic_residual_rms"] for r in rows], mode="lines+markers", name="Reverse non-harmonic residual")
    residual.update_layout(title="Departure from single-harmonic response", xaxis_title="Frequency ratio ω/ω₀", yaxis_title="Harmonic-fit residual RMS", height=410)
    st.plotly_chart(residual, width="stretch")
    st.caption(result["boundary"])


def render_frequency_response_workspace(st: Any, profile: str) -> None:
    if profile not in SUPPORTED_PROFILES:
        return
    st.markdown("---")
    st.markdown("## Physical Lab · Frequency Response Studio")
    st.caption(
        "Core simulation extension for the physics-first Dynamics Labs. It adds frequency-domain studies while preserving the original time-domain, convergence, Lyapunov, energy-work, and model-specific analyses."
    )
    if profile == "oscillation-integration":
        _render_linear(st)
    else:
        _render_duffing(st)
