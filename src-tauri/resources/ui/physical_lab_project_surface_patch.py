"""Mount the shared Project and unified workspace surfaces after every managed Lab UI.

The individual upstream Labs remain unchanged. This wrapper extends Engineering
Lab's shared advanced renderer so all managed Lab profiles expose the canonical
Project Kernel plus a visible top-level navigator for Project Workspace and the
registry-backed All Workspaces catalog. During the compatibility period it also
performs one non-destructive legacy desktop-workspace sync per Streamlit session
when session state is available.
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
                                "Engineering Lab imported legacy workspace evidence into the canonical Project Kernel "
                                f"({bridge.get('created', 0)} project(s), {bridge.get('measurements_imported', 0)} measurement(s))."
                            )
                        except Exception:
                            pass
                except Exception as bridge_exc:
                    session_state[LEGACY_SYNC_SESSION_KEY] = {"errors": [{"error": str(bridge_exc)}]}
                    st.warning(f"Legacy .physlab compatibility sync could not complete: {bridge_exc}")

            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, profile, namespace)

            # The compact .physlab Project panel above owns project selection and
            # metadata. The navigator below owns discoverable user-facing workspaces.
            st.markdown("---")
            navigator = st.radio(
                "Engineering Lab navigator",
                ["Project Workspace", "All Workspaces"],
                horizontal=True,
                key=f"pl_unified_surface_nav_{profile}",
            )

            if navigator == "Project Workspace":
                from physical_lab_project_interop_ui import render_project_interop
                render_project_interop(st, profile)
            else:
                from physical_lab_surface_registry import SURFACES  # canonical inventory marker
                from physical_lab_surface_catalog import render_all_workspaces
                _ = SURFACES
                render_all_workspaces(st, profile)
        except Exception as exc:
            try:
                import streamlit as st
                st.warning(f"Engineering Lab Project / workspace surface could not load: {exc}")
            except Exception:
                pass

    advanced.render_advanced_experiments = wrapped
    advanced._physical_lab_project_surface_patched = True
