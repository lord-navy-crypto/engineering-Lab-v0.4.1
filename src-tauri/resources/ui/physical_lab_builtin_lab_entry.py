"""Entry point for first-class Physical Lab models bundled with the desktop app.

The scientific implementations live in the packaged Physical Lab UI/model
modules. This host only routes one dedicated launcher card to the already
validated model workspace, its refinement evidence, and the shared Project /
Evidence surface. It deliberately does not duplicate solver equations.
"""
from __future__ import annotations

import os

import streamlit as st

PROFILE = os.environ.get("PHYSICAL_LAB_UI_PROFILE", "").strip()

LABS = {
    "kerr-geodesics": ("Kerr Black Hole Geodesics", "Relativity & Astrophysics"),
    "solar-system-dynamics": ("Sun–Jupiter–Saturn Dynamics", "Computational Astrophysics"),
    "honeycomb-lattice": ("Multilayer Honeycomb Lattice", "Materials & Condensed Matter"),
    "rotating-utube": ("Rotating U-Tube Research Studio", "Fluid Dynamics & Experimental Physics"),
}

if PROFILE not in LABS:
    raise RuntimeError(f"Unknown bundled Physical Lab profile: {PROFILE!r}")

TITLE, CATEGORY = LABS[PROFILE]
st.set_page_config(page_title=f"Physical Lab · {TITLE}", layout="wide")
st.title(TITLE)
st.caption(
    f"First-class bundled Physical Lab · {CATEGORY}. The launcher uses the model "
    "implementation shipped with this Physical Lab build rather than downloading "
    "or maintaining a second solver copy."
)


def _requested_surface() -> str:
    try:
        value = st.query_params.get("surface", "")
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        return str(value or "").strip()
    except Exception:
        try:
            values = st.experimental_get_query_params().get("surface", [])
            return str(values[0] if values else "").strip()
        except Exception:
            return ""


REQUESTED_SURFACE = _requested_surface()
if REQUESTED_SURFACE:
    # Workbench deep-links must stay focused even when their preferred host is a
    # first-class bundled Lab. The shared dispatcher renders the real target and
    # preserves project/namespace prerequisites rather than duplicating UI here.
    from physical_lab_native_surface_entry import render_requested_surface

    render_requested_surface(st, {}, PROFILE, REQUESTED_SURFACE)
elif PROFILE == "kerr-geodesics":
    from physical_lab_kerr_ui import render_kerr_geodesic_workspace
    from physical_lab_kerr_platform_ui import render_kerr_platform_workspace
    from physical_lab_new_model_refinements import KERR_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    # The model's internal computational profile remains nonlinear-chaos for
    # backwards-compatible Compute Engine / campaign records. The launcher ID
    # is intentionally independent and first-class.
    render_kerr_geodesic_workspace(st, "nonlinear-chaos")
    render_kerr_platform_workspace(st, "nonlinear-chaos")
    render_new_model_refinement_for_variant(st, KERR_VARIANT)
elif PROFILE == "solar-system-dynamics":
    from physical_lab_solar_system_ui import render_solar_system_workspace
    from physical_lab_new_model_refinements import SOLAR_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    render_solar_system_workspace(st, "nonlinear-chaos")
    render_new_model_refinement_for_variant(st, SOLAR_VARIANT)
elif PROFILE == "honeycomb-lattice":
    from physical_lab_lattice_ui import render_lattice_workspace
    from physical_lab_new_model_refinements import LATTICE_VARIANT
    from physical_lab_new_model_refinement_ui import render_new_model_refinement_for_variant

    render_lattice_workspace(st, "oscillation-integration")
    render_new_model_refinement_for_variant(st, LATTICE_VARIANT)
elif PROFILE == "rotating-utube":
    from physical_lab_utube_experiment_ui import render_utube_experiment
    from physical_lab_utube_uncertainty_ui import render_utube_uncertainty
    from physical_lab_utube_advanced_ui import render_utube_advanced

    st.info(
        "U-Tube research sequence: physical model/data → uncertainty → advanced physics and experiment planning → "
        "robust design/digital twin → dynamic threshold/hysteresis. The Advanced workspace owns the final two child studies, "
        "so they are not rendered a second time here."
    )
    render_utube_experiment(st, PROFILE)
    render_utube_uncertainty(st, PROFILE)
    render_utube_advanced(st, PROFILE)

# sitecustomize installs the Evidence Center wrapper around this function before
# Streamlit executes the entry point. For focused Workbench deep-links, avoid
# appending a second unrelated project surface below the requested workspace.
if not REQUESTED_SURFACE:
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
