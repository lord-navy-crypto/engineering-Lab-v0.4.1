"""UI for bounded two-factor radiation response surfaces."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


def _load_core():
    try:
        import physical_lab_radiation_response_surface as core
        return core
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radiation_response_surface.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_response_surface", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        core = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_response_surface", core)
        spec.loader.exec_module(core)
        return core


def _load_requirements():
    try:
        import physical_lab_radiation_requirements as mod
        return mod
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radiation_requirements.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_requirements", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_requirements", mod)
        spec.loader.exec_module(mod)
        return mod


def render_radiation_response_surface_workspace(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio" or not namespace:
        return
    core = _load_core()
    params = dict(namespace.get("current_params") or {})
    active = [k for k in core.ERROR_KEYS if abs(float(params.get(k, 0.0) or 0.0)) > 0.0]
    if len(active) < 2:
        return

    st.markdown("---")
    st.markdown("### Local Manufacturing-Error → Radiation Response Surface")
    st.caption(
        "Two-factor bounded quadratic surrogate. Coded levels -1/0/+1 mean 0%, 50%, and 100% of the currently configured error magnitude. The same fixed seed is used at all 9 design points."
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        factor_a = st.selectbox("Factor A", active, index=0, key="pl_rad_rs_a")
    with c2:
        options_b = [x for x in active if x != factor_a]
        factor_b = st.selectbox("Factor B", options_b, index=0, key="pl_rad_rs_b")
    with c3:
        gamma = st.number_input("Response-surface electron γ", min_value=2.0, max_value=100000.0, value=200.0, step=10.0, key="pl_rad_rs_gamma")
    with c4:
        seed = st.number_input("Response-surface seed", min_value=0, max_value=100000000, value=51001, step=1, key="pl_rad_rs_seed")

    if st.button("Run 3×3 radiation response surface", key="pl_run_rad_response_surface", type="secondary"):
        try:
            with st.spinner("Running 9 fixed-seed RADIA → radiation design points..."):
                result = core.run_two_factor_response_surface(
                    namespace,
                    factor_a=factor_a,
                    factor_b=factor_b,
                    seed=int(seed),
                    gamma=float(gamma),
                    transverse_points=3,
                    z_samples_per_period=8,
                    tracking_points_per_period=24,
                )
            st.session_state["pl_rad_response_surface_result"] = result
        except Exception as exc:
            st.error(f"Radiation response-surface modeling failed: {exc}")

    result = st.session_state.get("pl_rad_response_surface_result")
    if not result:
        return

    import pandas as pd
    import plotly.graph_objects as go

    surfaces = (result.get("summary") or {}).get("surfaces") or {}
    if not surfaces:
        st.warning("No finite observables were available for quadratic fitting.")
        return

    overview = []
    for metric_name, surface_row in surfaces.items():
        coeff = surface_row.get("coefficients") or {}
        fit = surface_row.get("fit") or {}
        overview.append({
            "metric": metric_name,
            "R2": fit.get("r2"),
            "RMSE": fit.get("rmse"),
            "linearA": coeff.get("linearA"),
            "linearB": coeff.get("linearB"),
            "quadraticA": coeff.get("quadraticA"),
            "quadraticB": coeff.get("quadraticB"),
            "interactionAB": coeff.get("interactionAB"),
        })
    st.dataframe(pd.DataFrame(overview), width="stretch", hide_index=True)

    metric = st.selectbox("Response-surface observable", sorted(surfaces.keys()), key="pl_rad_rs_metric")
    surface = surfaces[metric]
    grid = core.prediction_grid(surface, points=31)
    fig = go.Figure(data=go.Contour(
        x=grid["codedA"], y=grid["codedB"], z=grid["predicted"], contours_coloring="heatmap"
    ))
    pts = surface.get("points") or []
    fig.add_scatter(
        x=[p["codedA"] for p in pts], y=[p["codedB"] for p in pts],
        mode="markers", name="9 simulated design points",
    )
    fig.update_layout(
        title=f"Local quadratic response surface → {metric}",
        xaxis_title=f"coded {result.get('factorA')}  (-1=0×, 0=0.5×, +1=1× configured magnitude)",
        yaxis_title=f"coded {result.get('factorB')}  (-1=0×, 0=0.5×, +1=1× configured magnitude)",
        height=560,
    )
    st.plotly_chart(fig, width="stretch")

    coeff = surface.get("coefficients") or {}
    fit = surface.get("fit") or {}
    st.json({"coefficients": coeff, "fitDiagnostics": fit}, expanded=False)
    st.caption(result.get("boundary", ""))

    st.markdown("#### Local Requirement / Constraint Contour")
    st.caption(
        "Classify this same local surrogate against explicit engineering bounds. PASS area is geometric area in the sampled tolerance box only—not manufacturing yield."
    )
    req = _load_requirements()
    vals = [float(p["value"]) for p in (surface.get("points") or []) if p.get("value") is not None]
    default_min = min(vals) if vals else 0.0
    default_max = max(vals) if vals else 1.0
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        use_lower = st.checkbox("Use lower bound", value=False, key="pl_rad_req_use_lower")
        lower = st.number_input("Lower requirement", value=float(default_min), key="pl_rad_req_lower")
    with rc2:
        use_upper = st.checkbox("Use upper bound", value=True, key="pl_rad_req_use_upper")
        upper = st.number_input("Upper requirement", value=float(default_max), key="pl_rad_req_upper")
    with rc3:
        grid_points = st.selectbox("Requirement grid", [41, 81, 121], index=1, key="pl_rad_req_grid")

    if use_lower or use_upper:
        try:
            contour = req.classify_requirement_surface(
                surface,
                lower=float(lower) if use_lower else None,
                upper=float(upper) if use_upper else None,
                points=int(grid_points),
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Center status", contour["centerStatus"])
            m2.metric("PASS grid area", f"{100.0*contour['passGridFraction']:.1f}%")
            nearest = contour.get("nearestClassificationBoundaryFromCenterCoded")
            m3.metric("Nearest boundary (coded)", "none in box" if nearest is None else f"{nearest:.3f}")

            pass_fig = go.Figure(data=go.Contour(
                x=contour["codedA"], y=contour["codedB"], z=contour["margin"],
                contours=dict(start=0.0, end=0.0, size=1.0, coloring="heatmap", showlabels=True),
                colorbar=dict(title="requirement margin"),
            ))
            pass_fig.add_scatter(
                x=[p["codedA"] for p in pts], y=[p["codedB"] for p in pts],
                mode="markers", name="simulated design points",
            )
            pass_fig.update_layout(
                title=f"Local requirement margin → {metric}  (zero contour = PASS/REVIEW boundary)",
                xaxis_title=f"coded {result.get('factorA')}",
                yaxis_title=f"coded {result.get('factorB')}",
                height=560,
            )
            st.plotly_chart(pass_fig, width="stretch")
            st.caption(contour.get("boundary", ""))
        except Exception as exc:
            st.warning(f"Requirement contour could not be formed: {exc}")
