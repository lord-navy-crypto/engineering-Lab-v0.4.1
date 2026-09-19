"""Interactive frequency-response workspace for Physical Lab dynamics Labs."""
from __future__ import annotations

from typing import Any

from physical_lab_frequency_response import duffing_frequency_sweep, linear_forced_response_sweep
from physical_lab_ui_system import (
    render_boundary,
    render_section_label,
    render_stage_rail,
    render_workbench_header,
)

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
    render_section_label(
        st,
        "Forced vibration · frequency response",
        "Sweep a viscously damped single-degree-of-freedom oscillator through resonance and compare the RK4 steady-state response with the analytic reference.",
    )
    setup_tab, response_tab, verification_tab = st.tabs([
        "Setup & run", "Response", "Numerical verification"
    ])

    key = "pl_frequency_response_linear_result"

    with setup_tab:
        st.caption("Physical parameters")
        c1, c2, c3 = st.columns(3)
        omega_n = c1.number_input(
            "Natural frequency ωₙ (rad/s)", min_value=0.1, max_value=30.0,
            value=2.0, step=0.1, key="pl_fr_linear_wn",
        )
        zeta = c2.number_input(
            "Damping ratio ζ", min_value=0.0, max_value=1.5,
            value=0.05, step=0.01, key="pl_fr_linear_zeta",
        )
        force = c3.number_input(
            "Force amplitude", min_value=0.0, max_value=20.0,
            value=1.0, step=0.1, key="pl_fr_linear_force",
        )

        st.caption("Sweep definition")
        c4, c5, c6 = st.columns(3)
        start_ratio = c4.number_input(
            "Start frequency ratio ω/ωₙ", min_value=0.1, max_value=3.0,
            value=0.30, step=0.05, key="pl_fr_linear_start",
        )
        stop_ratio = c5.number_input(
            "Stop frequency ratio ω/ωₙ", min_value=0.2, max_value=5.0,
            value=1.60, step=0.05, key="pl_fr_linear_stop",
        )
        quality_name = c6.selectbox(
            "Sweep quality", ["Fast", "Standard", "Deep"], index=1,
            key="pl_fr_linear_quality",
        )

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
                st.success("Sweep complete. Open Response and Numerical verification.")

        st.caption(
            "Standard is the default review mode. Fast is useful for interaction; Deep increases the frequency grid and time-domain sampling workload."
        )

    result = st.session_state.get(key)

    with response_tab:
        if not isinstance(result, dict):
            st.info("Run the sweep in Setup & run to resolve resonance amplitude and phase.")
        else:
            theoretical = result.get("theoretical_resonance_frequency_rad_s")
            a, b, c, d = st.columns(4)
            a.metric("Numerical peak ω", f"{result['numerical_peak_frequency_rad_s']:.5g} rad/s")
            b.metric("Analytic resonance ω", "—" if theoretical is None else f"{float(theoretical):.5g} rad/s")
            c.metric("Max amplitude error", f"{100.0 * float(result['max_amplitude_relative_error']):.4g}%")
            d.metric("Max phase error", f"{float(result['max_phase_absolute_error_rad']):.4g} rad")

            rows = result["rows"]
            go = _plotly()
            amp = go.Figure()
            amp.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["fundamental_amplitude"] for r in rows],
                mode="lines+markers",
                name="RK4 steady-state",
            )
            amp.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["analytic_amplitude"] for r in rows],
                mode="lines",
                name="Analytic reference",
            )
            amp.update_layout(
                title="Forced-response amplitude",
                xaxis_title="Frequency ratio ω/ωₙ",
                yaxis_title="Amplitude",
                height=470,
            )

            phase = go.Figure()
            phase.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["phase_lag_rad"] for r in rows],
                mode="lines+markers",
                name="RK4 phase",
            )
            phase.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["analytic_phase_lag_rad"] for r in rows],
                mode="lines",
                name="Analytic phase",
            )
            phase.update_layout(
                title="Phase lag through resonance",
                xaxis_title="Frequency ratio ω/ωₙ",
                yaxis_title="Phase lag (rad)",
                height=470,
            )

            p1, p2 = st.columns(2)
            p1.plotly_chart(amp, width="stretch")
            p2.plotly_chart(phase, width="stretch")

    with verification_tab:
        if not isinstance(result, dict):
            st.info("The numerical/analytic error audit appears after a completed sweep.")
        else:
            rows = result["rows"]
            go = _plotly()
            error = go.Figure()
            error.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[100.0 * r["amplitude_relative_error"] for r in rows],
                mode="lines+markers",
                name="Amplitude error",
            )
            error.update_layout(
                title="Numerical frequency-response error",
                xaxis_title="Frequency ratio ω/ωₙ",
                yaxis_title="Amplitude relative error (%)",
                height=450,
            )
            st.plotly_chart(error, width="stretch")
            render_boundary(st, str(result["boundary"]))


def _render_duffing(st: Any) -> None:
    render_section_label(
        st,
        "Nonlinear resonance · Duffing continuation",
        "Sweep a hardening Duffing oscillator upward and downward in drive frequency while carrying each final state into the next frequency.",
    )
    setup_tab, response_tab, diagnostics_tab = st.tabs([
        "Setup & run", "Response branches", "Diagnostics"
    ])
    key = "pl_frequency_response_duffing_result"

    with setup_tab:
        st.caption("Physical parameters")
        c1, c2, c3, c4 = st.columns(4)
        omega0 = c1.number_input(
            "Linear ω₀ (rad/s)", min_value=0.1, max_value=20.0,
            value=1.0, step=0.1, key="pl_fr_duffing_w0",
        )
        zeta = c2.number_input(
            "Damping ratio ζ", min_value=0.0, max_value=0.5,
            value=0.05, step=0.01, key="pl_fr_duffing_zeta",
        )
        beta = c3.number_input(
            "Cubic stiffness β", min_value=-5.0, max_value=8.0,
            value=1.0, step=0.1, key="pl_fr_duffing_beta",
        )
        force = c4.number_input(
            "Drive amplitude F", min_value=0.0, max_value=3.0,
            value=0.30, step=0.05, key="pl_fr_duffing_force",
        )

        st.caption("Continuation sweep")
        c5, c6, c7 = st.columns(3)
        start_ratio = c5.number_input(
            "Start ω/ω₀", min_value=0.1, max_value=3.0,
            value=0.70, step=0.05, key="pl_fr_duffing_start",
        )
        stop_ratio = c6.number_input(
            "Stop ω/ω₀", min_value=0.2, max_value=4.0,
            value=1.60, step=0.05, key="pl_fr_duffing_stop",
        )
        quality_name = c7.selectbox(
            "Sweep quality", ["Fast", "Standard", "Deep"], index=1,
            key="pl_fr_duffing_quality",
        )

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
                st.success("Continuation sweep complete. Open Response branches and Diagnostics.")

    result = st.session_state.get(key)

    with response_tab:
        if not isinstance(result, dict):
            st.info("Run the continuation sweep to compare forward and reverse nonlinear response branches.")
        else:
            a, b, c, d = st.columns(4)
            a.metric("Forward peak ω", f"{result['forward_peak_frequency_rad_s']:.5g} rad/s")
            b.metric("Forward peak amplitude", f"{result['forward_peak_amplitude']:.5g}")
            c.metric("Max branch gap", f"{result['max_branch_amplitude_gap']:.5g}")
            d.metric("Gap frequency", f"{result['max_branch_gap_frequency_rad_s']:.5g} rad/s")

            rows = result["rows"]
            go = _plotly()
            response = go.Figure()
            response.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["forward_amplitude"] for r in rows],
                mode="lines+markers",
                name="Forward continuation",
            )
            response.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["reverse_amplitude"] for r in rows],
                mode="lines+markers",
                name="Reverse continuation",
            )
            response.update_layout(
                title="Nonlinear frequency-response branches",
                xaxis_title="Frequency ratio ω/ω₀",
                yaxis_title="Fundamental amplitude",
                height=490,
            )
            st.plotly_chart(response, width="stretch")

    with diagnostics_tab:
        if not isinstance(result, dict):
            st.info("Branch-sensitivity and harmonic-residual diagnostics appear after a completed sweep.")
        else:
            rows = result["rows"]
            go = _plotly()

            gap = go.Figure()
            gap.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["branch_amplitude_gap"] for r in rows],
                mode="lines+markers",
                name="Branch gap",
            )
            gap.update_layout(
                title="Forward/reverse branch sensitivity",
                xaxis_title="Frequency ratio ω/ω₀",
                yaxis_title="|A_forward − A_reverse|",
                height=430,
            )

            residual = go.Figure()
            residual.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["forward_harmonic_residual_rms"] for r in rows],
                mode="lines+markers",
                name="Forward residual",
            )
            residual.add_scatter(
                x=[r["frequency_ratio"] for r in rows],
                y=[r["reverse_harmonic_residual_rms"] for r in rows],
                mode="lines+markers",
                name="Reverse residual",
            )
            residual.update_layout(
                title="Departure from single-harmonic response",
                xaxis_title="Frequency ratio ω/ω₀",
                yaxis_title="Harmonic-fit residual RMS",
                height=430,
            )

            p1, p2 = st.columns(2)
            p1.plotly_chart(gap, width="stretch")
            p2.plotly_chart(residual, width="stretch")
            render_boundary(st, str(result["boundary"]))


def render_frequency_response_workspace(st: Any, profile: str) -> None:
    if profile not in SUPPORTED_PROFILES:
        return

    render_workbench_header(
        st,
        "Frequency Response Studio",
        "A focused frequency-domain workspace. Configure the model, run one sweep, review the primary response, then inspect numerical or nonlinear diagnostics separately.",
        kicker="Dynamics analysis",
    )
    render_stage_rail(st, [
        ("Set parameters", "physical model + sweep"),
        ("Run", "time-domain integration"),
        ("Review", "amplitude + phase"),
        ("Verify", "error / branch diagnostics"),
    ])

    if profile == "oscillation-integration":
        _render_linear(st)
    else:
        _render_duffing(st)
