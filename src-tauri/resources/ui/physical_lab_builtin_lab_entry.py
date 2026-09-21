"""Entry point for first-class Physical Lab models bundled with the desktop app.

The scientific implementations live in the packaged Physical Lab UI/model
modules.  This host only routes one dedicated launcher card to the already
validated model workspace, its refinement evidence, and the shared Project /
Evidence surface.  It deliberately does not duplicate solver equations.
"""
from __future__ import annotations

import os

import streamlit as st

PROFILE = os.environ.get("PHYSICAL_LAB_UI_PROFILE", "").strip()

LABS = {
    "kerr-geodesics": ("Kerr Black Hole Geodesics", "Relativity & Astrophysics"),
    "solar-system-dynamics": ("Sun–Jupiter–Saturn Dynamics", "Computational Astrophysics"),
    "honeycomb-lattice": ("Multilayer Honeycomb Lattice", "Materials & Condensed Matter"),
    "utube-rotation": ("Rotating U-Tube Research Studio", "Engineering Physics & Fluid Experiment"),
}

if PROFILE not in LABS:
    raise RuntimeError(f"Unknown bundled Physical Lab profile: {PROFILE!r}")

TITLE, CATEGORY = LABS[PROFILE]
st.set_page_config(page_title=f"Physical Lab · {TITLE}", layout="wide")
# The model workspace renders the visible title/hierarchy through the shared UI
# system. Keep the launcher entry deliberately quiet to avoid duplicate headers.

if PROFILE == "kerr-geodesics":
    from physical_lab_kerr_ui import render_kerr_geodesic_workspace
    from physical_lab_kerr_platform_ui import render_kerr_platform_workspace
    from physical_lab_new_model_refinements import KERR_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    # The model's internal computational profile remains nonlinear-chaos for
    # backwards-compatible Compute Engine / campaign records.  The launcher ID
    # is intentionally independent and first-class.
    render_kerr_geodesic_workspace(st, PROFILE)
    render_kerr_platform_workspace(st, PROFILE)
    render_new_model_refinement_for_variant(st, KERR_VARIANT)
elif PROFILE == "solar-system-dynamics":
    from physical_lab_solar_system_ui import render_solar_system_workspace
    from physical_lab_new_model_refinements import SOLAR_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    render_solar_system_workspace(st, PROFILE)
    render_new_model_refinement_for_variant(st, SOLAR_VARIANT)
elif PROFILE == "honeycomb-lattice":
    from physical_lab_lattice_ui import render_lattice_workspace
    from physical_lab_new_model_refinements import LATTICE_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    render_lattice_workspace(st, PROFILE)
    render_new_model_refinement_for_variant(st, LATTICE_VARIANT)
else:
    st.markdown("## Rotating U-Tube Research Studio")
    st.caption(
        "Full Streamlit workshop for the rotating U-tube experiment. Model-only studies work immediately; "
        "Project-backed data comparison activates when an Engineering Lab Project is selected."
    )
    workspace = st.radio(
        "U-Tube workspace",
        ["Physical Model & Data", "Uncertainty & Validation", "Advanced Design", "Hysteresis & Dynamics", "Robust Design & Digital Twin"],
        horizontal=True,
        key="pl_utube_standalone_workspace",
    )
    if workspace == "Physical Model & Data":
        from physical_lab_utube_experiment_ui import render_utube_experiment
        render_utube_experiment(st, PROFILE)
    elif workspace == "Uncertainty & Validation":
        from physical_lab_utube_uncertainty_ui import render_utube_uncertainty
        render_utube_uncertainty(st, PROFILE)
    elif workspace == "Advanced Design":
        from physical_lab_utube_advanced_ui import render_utube_advanced
        render_utube_advanced(st, PROFILE)
    elif workspace == "Hysteresis & Dynamics":
        from physical_lab_utube_hysteresis_ui import render_utube_hysteresis
        render_utube_hysteresis(st, PROFILE)
    else:
        from physical_lab_utube_robust_ui import render_utube_robust_engineering
        render_utube_robust_engineering(st, PROFILE)

# sitecustomize installs the Evidence Center wrapper around this function before
# Streamlit executes the entry point, so a single call exposes the same canonical
# .physlab Project + nine-view Evidence Center used by the external Labs.
try:
    from physical_lab_project_kernel import render_project_workspace

    render_project_workspace(st, PROFILE, {})
except Exception as exc:
    st.warning(f"Physical Lab Project / Evidence surface could not load: {exc}")

st.caption(
    "Scientific boundary: these are computational model workspaces. Their numerical "
    "checks and evidence records do not by themselves establish experimental validation, "
    "astrophysical truth, calibrated material properties, safety approval, or certification."
)
