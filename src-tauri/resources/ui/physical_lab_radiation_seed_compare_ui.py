"""UI for targeted nominal-vs-manufacturing-seed angular radiation comparison."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping


def _load(name: str, filename: str):
    try:
        return __import__(name)
    except ModuleNotFoundError:
        path = Path(__file__).with_name(filename)
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(name, mod)
        spec.loader.exec_module(mod)
        return mod


def render_seed_radiation_comparison(st: Any, profile: str, namespace: Mapping[str, Any] | None) -> None:
    if profile != "radia-magnet-studio":
        return
    propagation_result = st.session_state.get("pl_rrp_result")
    if not propagation_result:
        return

    quality = _load("physical_lab_radiation_quality", "physical_lab_radiation_quality.py")
    compare = _load("physical_lab_radiation_seed_compare", "physical_lab_radiation_seed_compare.py")
    prop = _load("physical_lab_radia_radiation_propagation", "physical_lab_radia_radiation_propagation.py")
    try:
        qsummary = quality.summarize_radiation_quality(
            propagation_result.get("nominal") or {}, propagation_result.get("members") or []
        )
    except Exception:
        return
    ranked = qsummary.get("diagnosticRanking") or []
    seeds = [int(row["seed"]) for row in ranked if row.get("seed") is not None]
    if not seeds:
        return

    st.markdown("---")
    st.markdown("## Physical Lab · Nominal vs Selected Manufacturing Seed Radiation Map")
    st.caption(
        "After the scalar manufacturing ensemble identifies a seed of interest, rebuild only that seed and the nominal device, "
        "then run the full trajectory-based angular radiation solver for a spatial diagnosis."
    )
    default_seed = seeds[0]
    seed = st.selectbox("Manufacturing seed", seeds, index=0, key="pl_seed_map_seed")
    if seed == default_seed:
        st.caption("The default is the highest diagnostic-deviation seed among the currently propagated realizations.")

    grid_info = propagation_result.get("grid") or {}
    physics = propagation_result.get("physicsInputs") or {}
    c1, c2, c3, c4 = st.columns(4)
    nxy = c1.selectbox("RADIA transverse grid", [3, 5, 7], index=1, format_func=lambda n: f"{n} × {n}", key="pl_seed_map_nxy")
    half = c2.number_input("Field half-width (mm)", min_value=0.1, value=float(grid_info.get("transverseHalfWidthMm", 2.0)), step=0.25, key="pl_seed_map_half")
    zpp = c3.select_slider("RADIA z samples / period", options=[6, 8, 12, 16], value=int(grid_info.get("zSamplesPerPeriodRequested", 8)) if int(grid_info.get("zSamplesPerPeriodRequested", 8)) in [6,8,12,16] else 8, key="pl_seed_map_zpp")
    gamma = c4.number_input("Electron γ", min_value=1.01, value=float(physics.get("gamma", 100.0)), step=1.0, key="pl_seed_map_gamma")

    c5, c6, c7, c8 = st.columns(4)
    grid = c5.select_slider("Angular grid", options=[5, 7, 9, 11], value=5, key="pl_seed_map_grid")
    extent = c6.slider("Angular extent (γθ)", 0.5, 4.0, 1.5, 0.25, key="pl_seed_map_extent")
    nobs = c7.select_slider("Observer samples / pixel", options=[400, 600, 900, 1200], value=400, key="pl_seed_map_nobs")
    ppp = c8.select_slider("Trajectory samples / period", options=[32, 48, 64], value=int(physics.get("pointsPerPeriod", 48)) if int(physics.get("pointsPerPeriod", 48)) in [32,48,64] else 48, key="pl_seed_map_ppp")
    distance = st.number_input("Observer distance (m)", min_value=1.0, value=float(physics.get("observerDistanceM", 100.0)), step=10.0, key="pl_seed_map_distance")

    if st.button("Run nominal ↔ selected-seed angular comparison", type="primary", key="pl_seed_map_run"):
        try:
            with st.spinner("Rebuilding nominal and selected RADIA manufacturing fields and running two full trajectory-radiation maps…"):
                result = compare.run_seed_map_comparison(
                    dict(namespace or {}), prop,
                    seed=int(seed),
                    transverse_half_width_mm=float(half),
                    transverse_points=int(nxy),
                    z_samples_per_period=int(zpp),
                    gamma=float(gamma),
                    observer_distance_m=float(distance),
                    tracking_points_per_period=int(ppp),
                    angular_grid_points=int(grid),
                    angular_extent_gamma_theta=float(extent),
                    angular_observer_samples=int(nobs),
                )
            st.session_state["pl_seed_map_result"] = result
        except Exception as exc:
            st.error(f"Targeted radiation-map comparison failed: {exc}")

    result = st.session_state.get("pl_seed_map_result")
    if not result or int(result.get("seed", -1)) != int(seed):
        return

    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go

    cmp = result["comparison"]
    scalar_rows = []
    for metric, row in cmp.get("scalarDeltas", {}).items():
        scalar_rows.append({"observable": metric, **row})
    if scalar_rows:
        st.markdown("#### On-axis / scalar radiation changes")
        st.dataframe(pd.DataFrame(scalar_rows), width="stretch", hide_index=True)

    metric_rows = []
    for metric, row in cmp.get("mapMetrics", {}).items():
        metric_rows.append({"map": metric, **row})
    if metric_rows:
        st.markdown("#### Angular-map difference diagnostics")
        st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)

    theta_x = 1e3 * np.asarray(cmp.get("theta_x_rad", []), dtype=float)
    theta_y = 1e3 * np.asarray(cmp.get("theta_y_rad", []), dtype=float)
    tabs = st.tabs(["Δ fluence", "Δ P linear", "Δ P circular", "Δ peak photon energy"])
    specs = [
        ("fluence_J_m2", "Seed − nominal radiative fluence", "J/m²"),
        ("P_lin", "Seed − nominal P_lin", "ΔP_lin"),
        ("P_circ", "Seed − nominal P_circ", "ΔP_circ"),
        ("f_peak_hz", "Seed − nominal peak photon energy", "eV"),
    ]
    h_ev_s = 4.135667696e-15
    for tab, (key, title, ztitle) in zip(tabs, specs):
        with tab:
            matrix = np.asarray([[np.nan if x is None else float(x) for x in row] for row in cmp.get("deltaMaps", {}).get(key, [])], dtype=float)
            if key == "f_peak_hz":
                matrix *= h_ev_s
            fig = go.Figure(data=go.Heatmap(x=theta_x, y=theta_y, z=matrix, colorbar={"title": ztitle}))
            fig.update_layout(title=title, xaxis_title="θx (mrad)", yaxis_title="θy (mrad)", height=500)
            st.plotly_chart(fig, width="stretch")

    st.download_button(
        "Download nominal-vs-seed radiation comparison (.json)",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False),
        f"physical-lab-radiation-seed-{int(seed)}-comparison.json",
        "application/json",
        key="pl_seed_map_download",
    )
    st.caption(cmp.get("boundary", ""))
