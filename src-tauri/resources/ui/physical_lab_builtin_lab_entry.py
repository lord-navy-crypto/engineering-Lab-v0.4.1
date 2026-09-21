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
    kerr_workspace = st.radio(
        "Kerr workspace",
        ["Geodesic Dynamics", "Experiment / Compute", "Refinement", "Project & Evidence"],
        horizontal=True,
        key="pl_kerr_first_class_workspace",
    )
    if kerr_workspace == "Geodesic Dynamics":
        from physical_lab_kerr_ui import render_kerr_geodesic_workspace
        render_kerr_geodesic_workspace(st, PROFILE)
    elif kerr_workspace == "Experiment / Compute":
        from physical_lab_kerr_platform_ui import render_kerr_platform_workspace
        render_kerr_platform_workspace(st, PROFILE)
    elif kerr_workspace == "Refinement":
        from physical_lab_new_model_refinements import KERR_VARIANT
        from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant
        render_new_model_refinement_for_variant(st, KERR_VARIANT)
    else:
        try:
            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, PROFILE, {})
        except Exception as exc:
            st.warning(f"Kerr Project / Evidence surface could not load: {exc}")
elif PROFILE == "solar-system-dynamics":
    solar_workspace = st.radio(
        "Solar-system workspace",
        ["Orbital Dynamics", "Refinement & Resonance", "Project & Evidence"],
        horizontal=True,
        key="pl_solar_first_class_workspace",
    )
    if solar_workspace == "Orbital Dynamics":
        from physical_lab_solar_system_ui import render_solar_system_workspace
        render_solar_system_workspace(st, PROFILE)
    elif solar_workspace == "Refinement & Resonance":
        from physical_lab_new_model_refinements import SOLAR_VARIANT
        from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant
        render_new_model_refinement_for_variant(st, SOLAR_VARIANT)
    else:
        try:
            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, PROFILE, {})
        except Exception as exc:
            st.warning(f"Solar Project / Evidence surface could not load: {exc}")
elif PROFILE == "honeycomb-lattice":
    lattice_workspace = st.radio(
        "Lattice workspace",
        ["Dynamics & Phonons", "Refinement", "Project & Evidence"],
        horizontal=True,
        key="pl_lattice_first_class_workspace",
    )
    if lattice_workspace == "Dynamics & Phonons":
        from physical_lab_lattice_ui import render_lattice_workspace
        render_lattice_workspace(st, PROFILE)
    elif lattice_workspace == "Refinement":
        from physical_lab_new_model_refinements import LATTICE_VARIANT
        from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant
        render_new_model_refinement_for_variant(st, LATTICE_VARIANT)
    else:
        try:
            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, PROFILE, {})
        except Exception as exc:
            st.warning(f"Lattice Project / Evidence surface could not load: {exc}")
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

# U-Tube keeps the canonical Project surface mounted because its measurement-backed
# tools can consume project datasets while model-only tools remain standalone.
# Kerr, Solar and Lattice expose Project & Evidence explicitly in their top-level
# workspace selector above to avoid duplicate panels.
if PROFILE == "utube-rotation":
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
