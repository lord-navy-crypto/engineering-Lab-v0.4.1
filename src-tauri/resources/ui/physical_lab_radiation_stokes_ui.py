"""Trajectory-based angular radiation and Stokes maps for the current RADIA field."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping


def _load_propagation_module():
    try:
        import physical_lab_radia_radiation_propagation as mod
        return mod
    except ModuleNotFoundError:
        import importlib.util
        import sys
        path = Path(__file__).with_name("physical_lab_radia_radiation_propagation.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radia_radiation_propagation", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radia_radiation_propagation", mod)
        spec.loader.exec_module(mod)
        return mod


def render_radiation_stokes_workspace(st: Any, profile: str, namespace: Mapping[str, Any] | None) -> None:
    if profile != "radia-magnet-studio":
        return
    st.markdown("---")
    st.markdown("## Physical Lab · Trajectory Radiation & Stokes Map")
    st.caption(
        "Build the current nominal 3-D RADIA field, propagate one electron with the pinned Radiation Platform, "
        "then recompute far-field fluence, peak frequency and polarization across an observer-angle grid."
    )

    prop = _load_propagation_module()
    status = prop.radiation_platform_status()
    if not status.get("ready"):
        st.info(f"Radiation Platform is not ready: {status.get('detail')}")
        return
    if not prop._full_mode():
        st.info("Switch RADIA Magnet Studio to **Full mode** to generate the 3-D field map required by this study.")
        return
    ns = dict(namespace or {})
    params = dict(ns.get("current_params") or {})
    if not params:
        st.warning("Current RADIA parameters are unavailable.")
        return

    c1, c2, c3, c4 = st.columns(4)
    gamma = c1.number_input("Electron γ", min_value=1.01, value=100.0, step=1.0, key="pl_stokes_gamma")
    nxy = c2.selectbox("RADIA transverse grid", [3, 5, 7], index=1, format_func=lambda n: f"{n} × {n}", key="pl_stokes_nxy")
    zpp = c3.select_slider("RADIA z samples / period", options=[6, 8, 12, 16], value=8, key="pl_stokes_zpp")
    half = c4.number_input("Field half-width (mm)", min_value=0.1, value=2.0, step=0.25, key="pl_stokes_half")

    c5, c6, c7, c8 = st.columns(4)
    grid = c5.select_slider("Angular grid", options=[5, 7, 9, 11, 13], value=7, key="pl_stokes_grid")
    extent = c6.slider("Angular extent (γθ)", 0.5, 5.0, 2.5, 0.25, key="pl_stokes_extent")
    n_obs = c7.select_slider("Observer samples / pixel", options=[600, 900, 1200, 1800], value=900, key="pl_stokes_nobs")
    ppp = c8.select_slider("Trajectory samples / period", options=[32, 48, 64, 96], value=48, key="pl_stokes_ppp")
    distance = st.number_input("Observer distance (m)", min_value=1.0, value=100.0, step=10.0, key="pl_stokes_distance")

    pixels = int(grid) * int(grid)
    st.caption(
        f"This run solves one nominal 3-D field/trajectory, then recomputes {pixels} far-field observer pixels. "
        "Use smaller grids for interactive work; increase only after the map topology is stable."
    )

    if st.button("Run trajectory radiation & Stokes map", type="primary", key="pl_stokes_run"):
        try:
            import numpy as np
            source, python = prop._managed_radiation_paths()
            prop._verify_radiation_source(source)
            x_mm = np.linspace(-float(half), float(half), int(nxy))
            y_mm = x_mm.copy()
            z_mm = prop._z_grid(ns, params, int(zpp))
            nominal_params = dict(params)
            nominal_params["errors_enabled"] = False
            with st.spinner("Solving nominal RADIA field, electron trajectory, and observer-plane radiation…"):
                field = prop._build_and_sample_3d(ns, nominal_params, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
                with tempfile.TemporaryDirectory(prefix="physical-lab-stokes-") as td:
                    tmp = Path(td)
                    map_path = tmp / "nominal.npz"
                    np.savez_compressed(map_path, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=field)
                    result = prop._invoke_radiation_worker(
                        source,
                        python,
                        map_path,
                        {
                            "periodMm": float(params.get("period_mm", 50.0)),
                            "deviceName": str(params.get("device", "radia-field-map")),
                            "gamma": float(gamma),
                            "nPeriods": int(params.get("periods", 20)),
                            "pointsPerPeriod": int(ppp),
                            "observerDistanceM": float(distance),
                            "thetaXMrad": 0.0,
                            "thetaYMrad": 0.0,
                            "includeAngularMap": True,
                            "angularGridPoints": int(grid),
                            "angularExtentGammaTheta": float(extent),
                            "angularObserverSamples": int(n_obs),
                            "sourceLabel": "Physical Lab nominal RADIA field for trajectory Stokes map",
                        },
                        tmp / "result.json",
                    )
            st.session_state["pl_stokes_result"] = result
        except Exception as exc:
            st.error(f"Trajectory radiation map failed: {exc}")

    result = st.session_state.get("pl_stokes_result")
    if not result:
        return

    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go

    obs = dict(result.get("observables") or {})
    stokes = dict(result.get("stokes") or {})
    harmonics = dict(result.get("harmonicRatios") or {})
    angular = result.get("angularMap") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Photon energy", f"{float(obs.get('photon_energy_eV') or 0):.6g} eV")
    c2.metric("P linear", f"{float(stokes.get('P_lin') or 0):.5f}")
    c3.metric("P circular", f"{float(stokes.get('P_circ') or 0):.5f}")
    c4.metric("Polarization degree", f"{float(stokes.get('polarization_degree') or 0):.5f}")

    pol = stokes.get("polarization_degree")
    if pol is not None and float(pol) > 1.0 + 1e-8:
        st.error("Stokes realizability check failed: computed polarization degree exceeds 1.")
    else:
        st.caption("Stokes realizability check: √(P_lin² + P_circ²) ≤ 1 within numerical tolerance.")

    if harmonics:
        st.markdown("#### Trajectory-derived harmonic ratios")
        st.dataframe(pd.DataFrame([harmonics]), width="stretch", hide_index=True)

    if angular:
        theta_x = 1e3 * np.asarray(angular.get("theta_x_rad", []), dtype=float)
        theta_y = 1e3 * np.asarray(angular.get("theta_y_rad", []), dtype=float)

        tabs = st.tabs(["Fluence", "Circular polarization", "Linear polarization", "Peak photon energy"])
        specs = [
            ("fluence_J_m2", "Radiative fluence", "J/m²"),
            ("P_circ", "Circular polarization P_circ", "P_circ"),
            ("P_lin", "Linear polarization P_lin", "P_lin"),
            ("f_peak_hz", "Peak photon energy", "eV"),
        ]
        h_ev_s = 4.135667696e-15
        for tab, (key, title, ztitle) in zip(tabs, specs):
            with tab:
                matrix = np.asarray([[np.nan if x is None else float(x) for x in row] for row in angular.get(key, [])], dtype=float)
                if key == "f_peak_hz":
                    matrix = h_ev_s * matrix
                fig = go.Figure(data=go.Heatmap(x=theta_x, y=theta_y, z=matrix, colorbar={"title": ztitle}))
                fig.update_layout(title=title, xaxis_title="θx (mrad)", yaxis_title="θy (mrad)", height=520)
                st.plotly_chart(fig, width="stretch")

        failures = int(angular.get("failure_count", 0))
        total = int(angular.get("grid_points", 0)) ** 2
        st.caption(
            f"Angular pixels: {total}; failed pixels retained as null: {failures}. "
            f"RMS angular widths: x={float(angular.get('rms_divergence_x_rad') or 0)*1e3:.5g} mrad, "
            f"y={float(angular.get('rms_divergence_y_rad') or 0)*1e3:.5g} mrad."
        )
        st.caption(str(angular.get("boundary") or ""))

    st.download_button(
        "Download trajectory radiation evidence (.json)",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False),
        "physical-lab-trajectory-radiation-stokes.json",
        "application/json",
        key="pl_stokes_download",
    )
    st.caption(str(result.get("boundary") or ""))
