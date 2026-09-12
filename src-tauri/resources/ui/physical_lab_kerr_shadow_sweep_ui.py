"""Interactive Kerr shadow morphology sweep for Physical Lab."""
from __future__ import annotations

from typing import Any

from physical_lab_kerr_shadow_sweep import kerr_shadow_morphology_sweep


def _go():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def render_kerr_shadow_morphology_workspace(st: Any, profile: str) -> None:
    if profile != "nonlinear-chaos":
        return
    st.markdown("---")
    st.markdown("## Kerr Shadow Morphology Lab")
    st.caption(
        "Move beyond one black-hole shadow: sweep spacetime spin and observer inclination, then compare displacement, size, area, and shape distortion of the vacuum capture boundary."
    )
    c1, c2 = st.columns(2)
    depth = c1.selectbox("Sweep depth", ["Fast", "Standard", "Deep"], index=1, key="pl_kerr_shadow_sweep_depth")
    inclinations_text = c2.text_input("Observer inclinations (deg)", "20,40,60,80", key="pl_kerr_shadow_sweep_incs")
    presets = {
        "Fast": ([0.0, 0.5, 0.8, 0.95], 220),
        "Standard": ([0.0, 0.3, 0.6, 0.8, 0.9, 0.98], 360),
        "Deep": ([0.0, 0.2, 0.4, 0.6, 0.75, 0.85, 0.92, 0.97, 0.99], 600),
    }
    key = "pl_kerr_shadow_morphology_result"
    if st.button("Run Kerr shadow morphology sweep", type="primary", key="pl_kerr_shadow_sweep_run"):
        try:
            inclinations = [float(value.strip()) for value in str(inclinations_text).split(",") if value.strip()]
            spins, samples = presets[depth]
            with st.spinner("Sweeping Kerr spin and observer inclination across vacuum critical curves..."):
                st.session_state[key] = kerr_shadow_morphology_sweep(
                    spins=spins, inclinations_deg=inclinations, curve_samples=samples
                )
        except Exception as exc:
            st.error(str(exc))
    result = st.session_state.get(key)
    if not isinstance(result, dict):
        st.info("Run the sweep to see which shadow observables are mostly spin-driven, observer-driven, or jointly dependent.")
        return

    a, b = st.columns(2)
    a.metric("Largest |horizontal shift|", f"{result['max_abs_horizontal_shift_over_M']:.5g} M")
    b.metric("Largest |signed flattening|", f"{100.0 * result['max_abs_signed_flattening']:.4g}%")
    rows = result["rows"]
    go = _go()
    shift = go.Figure()
    distortion = go.Figure()
    area = go.Figure()
    for inclination in result["inclinations_deg"]:
        subset = [row for row in rows if row["observer_inclination_deg"] == inclination]
        shift.add_scatter(
            x=[row["spin_a_over_M"] for row in subset],
            y=[row["horizontal_shift_over_M"] for row in subset],
            mode="lines+markers", name=f"i={inclination:g}°",
        )
        distortion.add_scatter(
            x=[row["spin_a_over_M"] for row in subset],
            y=[100.0 * row["signed_flattening"] for row in subset],
            mode="lines+markers", name=f"i={inclination:g}°",
        )
        area.add_scatter(
            x=[row["spin_a_over_M"] for row in subset],
            y=[row["area_over_M2"] for row in subset],
            mode="lines+markers", name=f"i={inclination:g}°",
        )
    shift.update_layout(title="Frame-dragging imprint on shadow displacement", xaxis_title="Spin a/M", yaxis_title="Horizontal midpoint shift α/M", height=430)
    distortion.update_layout(title="Shadow shape distortion", xaxis_title="Spin a/M", yaxis_title="Signed (width−height)/mean diameter (%)", height=430)
    area.update_layout(title="Critical-curve area", xaxis_title="Spin a/M", yaxis_title="Area / M²", height=430)
    st.plotly_chart(shift, width="stretch")
    left, right = st.columns(2)
    left.plotly_chart(distortion, width="stretch")
    right.plotly_chart(area, width="stretch")
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(result["boundary"])
