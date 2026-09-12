"""Interactive deep-science workspaces for Physical Lab."""
from __future__ import annotations

from typing import Any

from physical_lab_deep_science import (
    kerr_shadow_curve,
    lattice_vacf_study,
    numerical_error_atlas,
    solar_symplectic_comparison,
)

SUPPORTED_PROFILES = {"nonlinear-chaos", "oscillation-integration", "numerical-methods"}


def _go():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_kerr_shadow(st: Any) -> None:
    st.markdown("### Kerr black-hole shadow · distant-observer critical curve")
    st.caption(
        "Push the photon-orbit model outward to an observable image-plane quantity: the vacuum capture/escape critical curve seen by a distant observer."
    )
    c1, c2, c3 = st.columns(3)
    spin = c1.slider("Shadow spin a/M", 0.0, 0.998, 0.90, 0.01, key="pl_deep_kerr_shadow_spin")
    inclination = c2.slider("Observer inclination (deg)", 5.0, 90.0, 60.0, 1.0, key="pl_deep_kerr_shadow_inc")
    quality = c3.selectbox("Curve resolution", ["Fast", "Standard", "Deep"], index=1, key="pl_deep_kerr_shadow_quality")
    counts = {"Fast": 360, "Standard": 900, "Deep": 1800}
    key = "pl_deep_kerr_shadow_result"
    if st.button("Trace Kerr shadow critical curve", type="primary", key="pl_deep_kerr_shadow_run"):
        with st.spinner("Resolving spherical-photon critical curve on the distant observer plane..."):
            st.session_state[key] = kerr_shadow_curve(
                spin=float(spin), observer_inclination_deg=float(inclination), samples=counts[quality]
            )
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the shadow study to map spherical photon orbits onto the distant-observer image plane.")
        return
    a, b, c, d = st.columns(4)
    a.metric("Shadow width", f"{result['width_over_M']:.5g} M")
    b.metric("Shadow height", f"{result['height_over_M']:.5g} M")
    c.metric("Horizontal shift", f"{result['horizontal_midpoint_shift_over_M']:.5g} M")
    d.metric("Critical-curve area", f"{result['critical_curve_area_over_M2']:.5g} M²")
    go = _go()
    fig = go.Figure()
    fig.add_scatter(x=result["alpha_over_M"], y=result["beta_over_M"], mode="lines", name="critical curve")
    fig.update_layout(
        title="Kerr vacuum shadow critical curve",
        xaxis_title="α / M",
        yaxis_title="β / M",
        height=590,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig, width="stretch")
    st.caption(result["boundary"])


def _render_solar_symplectic(st: Any) -> None:
    st.markdown("### Solar-system long-horizon integration · DOP853 ↔ velocity-Verlet")
    st.caption(
        "Use an independent fixed-step Newtonian integrator to test long-time conservation structure instead of trusting one adaptive solver alone."
    )
    c1, c2, c3 = st.columns(3)
    duration = c1.select_slider("Duration (years)", options=[12, 20, 40, 80, 120], value=40, key="pl_deep_solar_duration")
    dt = c2.select_slider("Verlet Δt (years)", options=[0.04, 0.02, 0.01, 0.005], value=0.01, key="pl_deep_solar_dt")
    inclination = c3.slider("Jupiter inclination (deg)", 0.0, 30.0, 10.0, 1.0, key="pl_deep_solar_inc")
    key = "pl_deep_solar_symplectic_result"
    if st.button("Run long-horizon solver comparison", type="primary", key="pl_deep_solar_run"):
        with st.spinner("Running Newtonian velocity-Verlet and adaptive DOP853 comparison..."):
            st.session_state[key] = solar_symplectic_comparison(
                duration_years=float(duration), dt_years=float(dt), inclination_jupiter_deg=float(inclination)
            )
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the comparison to inspect conservation drift and final-state divergence between integrators.")
        return
    a, b, c, d = st.columns(4)
    a.metric("Verlet max ΔE/E", f"{result['verlet_max_relative_energy_drift']:.3e}")
    b.metric("Verlet max ΔL/L", f"{result['verlet_max_relative_angular_momentum_drift']:.3e}")
    c.metric("Jupiter final Δr", f"{result['final_jupiter_position_difference_vs_DOP853_AU']:.3e} AU")
    d.metric("Saturn final Δr", f"{result['final_saturn_position_difference_vs_DOP853_AU']:.3e} AU")
    go = _go()
    fig = go.Figure()
    fig.add_scatter(x=result["time_years"], y=result["verlet_relative_energy_error"], mode="lines", name="Verlet |ΔE/E₀|")
    fig.update_layout(title="Long-time Newtonian energy conservation", xaxis_title="Time (years)", yaxis_title="Relative energy error", height=430)
    fig.update_yaxes(type="log")
    st.plotly_chart(fig, width="stretch")
    radii = go.Figure()
    radii.add_scatter(x=result["time_years"], y=result["jupiter_heliocentric_radius_AU"], mode="lines", name="Jupiter")
    radii.add_scatter(x=result["time_years"], y=result["saturn_heliocentric_radius_AU"], mode="lines", name="Saturn")
    radii.update_layout(title="Heliocentric radius under velocity-Verlet", xaxis_title="Time (years)", yaxis_title="Radius (AU)", height=430)
    st.plotly_chart(radii, width="stretch")
    st.caption(result["boundary"])


def _render_lattice_vacf(st: Any) -> None:
    st.markdown("### Honeycomb dynamics · VACF & vibrational spectral density")
    st.caption(
        "Complement the existing Bloch dispersion/DOS with a real conservative time trajectory: velocity memory → VACF → finite-cell vibrational spectrum."
    )
    c1, c2, c3, c4 = st.columns(4)
    size = c1.selectbox("Cell size", ["2×2", "3×3", "4×4"], index=1, key="pl_deep_vacf_size")
    layers = c2.select_slider("Layers", options=[1, 2, 3], value=2, key="pl_deep_vacf_layers")
    quality = c3.selectbox("Trajectory depth", ["Fast", "Standard", "Deep"], index=1, key="pl_deep_vacf_quality")
    velocity_scale = c4.number_input("Initial velocity scale", min_value=0.005, max_value=0.15, value=0.03, step=0.005, key="pl_deep_vacf_velocity")
    q = {"Fast": (768, 0.005), "Standard": (2048, 0.004), "Deep": (4096, 0.003)}[quality]
    nxy = int(size.split("×")[0])
    key = "pl_deep_lattice_vacf_result"
    if st.button("Run VACF spectral study", type="primary", key="pl_deep_vacf_run"):
        with st.spinner("Integrating conservative lattice trajectory and estimating velocity spectrum..."):
            st.session_state[key] = lattice_vacf_study(
                nx=nxy, ny=nxy, layers=int(layers), steps=q[0], dt=q[1], velocity_scale=float(velocity_scale)
            )
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the trajectory to derive time-domain velocity memory and its finite-cell spectrum.")
        return
    a, b, c = st.columns(3)
    a.metric("Dominant spectral frequency", f"{result['dominant_frequency_cycles_per_reduced_time']:.5g} cycles/t*")
    zero = result.get("vacf_first_zero_time_reduced")
    b.metric("VACF first zero", "—" if zero is None else f"{float(zero):.5g} t*")
    c.metric("Max energy drift", f"{result['max_relative_energy_drift']:.3e}")
    go = _go()
    vacf = go.Figure()
    vacf.add_scatter(x=result["lag_time_reduced"], y=result["vacf_normalized"], mode="lines", name="normalized VACF")
    vacf.update_layout(title="Velocity autocorrelation", xaxis_title="Lag (reduced time)", yaxis_title="Cᵥ(τ) / Cᵥ(0)", height=430)
    st.plotly_chart(vacf, width="stretch")
    spectrum = go.Figure()
    spectrum.add_scatter(x=result["frequency_cycles_per_reduced_time"], y=result["vibrational_spectral_density_normalized"], mode="lines", name="velocity spectrum")
    spectrum.update_layout(title="Finite-cell vibrational spectral density", xaxis_title="Frequency (cycles / reduced time)", yaxis_title="Normalized spectral density", height=430)
    st.plotly_chart(spectrum, width="stretch")
    st.caption(result["boundary"])


def _render_numeric_atlas(st: Any) -> None:
    st.markdown("### Numerical Error Atlas · mechanism-by-mechanism exploration")
    st.caption(
        "Expand beyond Taylor error. The studies remain separate because cancellation, step-size collapse, accumulation, quantization, overflow, and aliasing have different causes and independent variables."
    )
    key = "pl_deep_numeric_atlas_result"
    if st.button("Run numerical-error atlas", type="primary", key="pl_deep_numeric_run"):
        with st.spinner("Running independent finite-precision and discretization studies..."):
            st.session_state[key] = numerical_error_atlas()
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the atlas to compare several independent numerical-failure mechanisms against explicit references.")
        return
    summary = result["summary"]
    a, b, c, d = st.columns(4)
    a.metric("Best central-difference h", f"{summary['best_float64_central_h']:.2e}")
    b.metric("float32 h-collapse cases", str(summary["float32_step_collapse_cases"]))
    c.metric("Trapz observed order", f"{summary['trapezoid_observed_order']:.4g}")
    d.metric("Aliasing frequency error", f"{summary['alias_frequency_error_Hz']:.4g} Hz")
    studies = result["studies"]
    go = _go()
    derivative = go.Figure()
    derivative.add_scatter(x=[r["h"] for r in studies["finite_difference_step_size"]], y=[r["forward_abs_error_float64"] for r in studies["finite_difference_step_size"]], mode="lines+markers", name="Forward")
    derivative.add_scatter(x=[r["h"] for r in studies["finite_difference_step_size"]], y=[r["central_abs_error_float64"] for r in studies["finite_difference_step_size"]], mode="lines+markers", name="Central")
    derivative.update_layout(title="Differentiation: truncation ↔ roundoff tradeoff", xaxis_title="h", yaxis_title="Absolute error", height=430)
    derivative.update_xaxes(type="log", autorange="reversed"); derivative.update_yaxes(type="log")
    st.plotly_chart(derivative, width="stretch")

    cancellation = go.Figure()
    positive = [r for r in studies["catastrophic_cancellation"] if r["x"] > 0]
    cancellation.add_scatter(x=[r["x"] for r in positive], y=[max(r["raw_abs_error"], 1e-30) for r in positive], mode="lines+markers", name="Raw sqrt(1+x)-1")
    cancellation.add_scatter(x=[r["x"] for r in positive], y=[max(r["stable_abs_error"], 1e-30) for r in positive], mode="lines+markers", name="Stable rationalized form")
    cancellation.update_layout(title="Catastrophic cancellation", xaxis_title="x", yaxis_title="Absolute error", height=430)
    cancellation.update_xaxes(type="log", autorange="reversed"); cancellation.update_yaxes(type="log")
    st.plotly_chart(cancellation, width="stretch")

    summation = go.Figure()
    summation.add_scatter(x=[r["count"] for r in studies["float32_accumulation"]], y=[r["naive_abs_error"] for r in studies["float32_accumulation"]], mode="lines+markers", name="Naive float32")
    summation.add_scatter(x=[r["count"] for r in studies["float32_accumulation"]], y=[r["kahan_abs_error"] for r in studies["float32_accumulation"]], mode="lines+markers", name="Kahan float32")
    summation.update_layout(title="Accumulation error growth", xaxis_title="Additions", yaxis_title="Absolute error", height=430)
    summation.update_xaxes(type="log"); summation.update_yaxes(type="log")
    st.plotly_chart(summation, width="stretch")
    st.dataframe(studies["int16_overflow_and_saturation"], width="stretch", hide_index=True)
    st.caption(result["boundary"])


def render_deep_science_workspace(st: Any, profile: str) -> None:
    if profile not in SUPPORTED_PROFILES:
        return
    st.markdown("---")
    st.markdown("## Physical Lab · Deep Science Studio")
    st.caption(
        "Strengthen the scientific model itself: add a new observable, an independent integration path, a trajectory-derived spectrum, or a new numerical-error mechanism—not another generic evidence wrapper."
    )
    if profile == "nonlinear-chaos":
        shadow_tab, solar_tab = st.tabs(["Kerr shadow", "Solar-system integrators"])
        with shadow_tab:
            _render_kerr_shadow(st)
        with solar_tab:
            _render_solar_symplectic(st)
    elif profile == "oscillation-integration":
        _render_lattice_vacf(st)
    elif profile == "numerical-methods":
        _render_numeric_atlas(st)
