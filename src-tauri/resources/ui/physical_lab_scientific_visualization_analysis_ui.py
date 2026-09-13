"""Sensitivity and response-surface views for Engineering Lab Scientific Visualization."""
from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from physical_lab_scientific_visualization import local_sensitivity, response_surface, standardized_sensitivity
from physical_lab_visualization_studio import numeric_columns


def render_sensitivity_surface(st: Any, source: dict[str, Any], profile: str) -> None:
    frame = source["frame"]
    numeric = numeric_columns(frame)
    tab_sens, tab_surface = st.tabs(["Sensitivity", "Response Surface"])
    with tab_sens:
        if len(numeric) < 2:
            st.info("At least two numeric fields are required for sensitivity analysis.")
        else:
            output = st.selectbox("Output / response", numeric, index=min(1, len(numeric)-1), key=f"pl_sv_sens_output_{profile}")
            params = [c for c in numeric if c != output]
            selected = st.multiselect("Candidate parameters", params, default=params[: min(6, len(params))], key=f"pl_sv_sens_params_{profile}")
            if selected:
                screening = standardized_sensitivity(frame, selected, output)
                if screening.empty:
                    st.info("Not enough variation is available for standardized screening.")
                else:
                    fig = px.bar(screening, x="parameter", y="abs_standardized_slope", hover_data=["standardized_slope", "spearman", "n"], title=f"Sensitivity screening → {output}")
                    fig.update_layout(height=500, yaxis_title="|standardized slope|")
                    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
                    st.dataframe(screening, hide_index=True, width="stretch")
            local_parameter = st.selectbox("Local finite-difference parameter", params, key=f"pl_sv_local_param_{profile}")
            try:
                local = local_sensitivity(frame, local_parameter, output)
                fig = px.line(local, x="parameter_center", y="sensitivity", markers=True, title=f"Local Δ{output} / Δ{local_parameter}")
                fig.update_layout(height=480)
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
                st.dataframe(local, hide_index=True, width="stretch")
            except Exception as exc:
                st.caption(f"Local sensitivity unavailable: {exc}")
            st.caption("Sensitivity here is descriptive screening of the available table, not causal attribution or global Sobol analysis.")

    with tab_surface:
        if len(numeric) < 3:
            st.info("At least three numeric fields are required for a 2-D response surface.")
        else:
            c1, c2, c3, c4 = st.columns([1, 1, 1, 0.8])
            x = c1.selectbox("X parameter", numeric, key=f"pl_sv_surface_x_{profile}")
            y_options = [c for c in numeric if c != x]
            y = c2.selectbox("Y parameter", y_options, key=f"pl_sv_surface_y_{profile}")
            z_options = [c for c in numeric if c not in {x, y}]
            z = c3.selectbox("Response Z", z_options, key=f"pl_sv_surface_z_{profile}")
            agg = c4.selectbox("Aggregate", ["mean", "median", "min", "max"], key=f"pl_sv_surface_agg_{profile}")
            try:
                surface = response_surface(frame, x, y, z, agg=agg)
            except Exception as exc:
                st.warning(f"Response surface unavailable: {exc}")
                return
            a, b, c = st.columns(3)
            a.metric("Input rows", surface["rows"])
            b.metric("Grid cells", surface["grid_cells"])
            c.metric("Finite cells", surface["coverage"])
            mode = st.radio("Surface view", ["Heatmap", "Contour", "3D Surface"], horizontal=True, key=f"pl_sv_surface_mode_{profile}")
            if mode == "Heatmap":
                fig = go.Figure(data=go.Heatmap(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z}))
            elif mode == "Contour":
                fig = go.Figure(data=go.Contour(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z}, contours={"showlabels": True}))
            else:
                fig = go.Figure(data=[go.Surface(x=surface["x"], y=surface["y"], z=surface["z"], colorbar={"title": z})])
                fig.update_layout(scene={"xaxis_title": x, "yaxis_title": y, "zaxis_title": z})
            fig.update_layout(title=f"{z} over {x} × {y} · {agg}", height=650)
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})
            coverage = surface["coverage"] / max(surface["grid_cells"], 1)
            if coverage < 1.0:
                st.warning(f"Grid coverage is {coverage:.1%}; missing parameter combinations are not interpolated.")
            st.caption("The response surface aggregates only computed table cells; it does not invent missing combinations or claim physical optimality.")
