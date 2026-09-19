"""Preserve the shared .physlab Project/Evidence capability for every managed Lab.

Seven profiles expose Project & Evidence explicitly through
Research Workbench → Engineering → Research.  For those profiles this patch
keeps only the non-destructive legacy-workspace synchronization behavior and
does not append a duplicate Project UI below the workbench.

The three bundled first-class Labs (Kerr, Solar System, Honeycomb Lattice) do
not use the shared Research Workbench, so this patch continues to mount their
Project/Evidence surface after the Lab UI.
"""
from __future__ import annotations

import os

SUPPORTED_PROFILES = {
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "kerr-geodesics",
    "solar-system-dynamics",
    "honeycomb-lattice",
    "radiation-platform",
    "radia-magnet-studio",
}

# These profiles already expose the canonical Project Kernel through
# Engineering → Research.  Keep compatibility sync, but never render a second
# Project/Evidence surface at the bottom of the page.
WORKBENCH_PROJECT_PROFILES = {
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radiation-platform",
    "radia-magnet-studio",
}

# These bundled Labs do not use the shared Research Workbench and therefore
# still need the compatibility mount to expose Project/Evidence.
STANDALONE_PROJECT_PROFILES = SUPPORTED_PROFILES - WORKBENCH_PROJECT_PROFILES

LEGACY_SYNC_SESSION_KEY = "_pl_legacy_workspace_bridge_v1"


def install() -> None:
    try:
        import physical_lab_advanced as advanced
    except Exception:
        return
    if getattr(advanced, "_physical_lab_project_surface_patched", False):
        return
    original = advanced.render_advanced_experiments

    def wrapped(namespace):
        original(namespace)
        profile = os.environ.get("PHYSICAL_LAB_UI_PROFILE", "").strip()
        if profile not in SUPPORTED_PROFILES:
            return
        try:
            import streamlit as st
            session_state = getattr(st, "session_state", None)
            if session_state is not None and LEGACY_SYNC_SESSION_KEY not in session_state:
                try:
                    from physical_lab_project_unification import synchronize_legacy_workspaces
                    bridge = synchronize_legacy_workspaces()
                    session_state[LEGACY_SYNC_SESSION_KEY] = bridge
                    if bridge.get("created") or bridge.get("measurements_imported"):
                        try:
                            st.toast(
                                "Physical Lab imported legacy workspace evidence into the canonical Project Kernel "
                                f"({bridge.get('created', 0)} project(s), {bridge.get('measurements_imported', 0)} measurement(s))."
                            )
                        except Exception:
                            pass
                except Exception as bridge_exc:
                    session_state[LEGACY_SYNC_SESSION_KEY] = {"errors": [{"error": str(bridge_exc)}]}
                    st.warning(f"Legacy .physlab compatibility sync could not complete: {bridge_exc}")
            if profile in WORKBENCH_PROJECT_PROFILES:
                return
            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, profile, namespace)
        except Exception as exc:
            try:
                import streamlit as st
                st.warning(f"Physical Lab Project / Evidence surface could not load: {exc}")
            except Exception:
                pass

    advanced.render_advanced_experiments = wrapped
    advanced._physical_lab_project_surface_patched = True
