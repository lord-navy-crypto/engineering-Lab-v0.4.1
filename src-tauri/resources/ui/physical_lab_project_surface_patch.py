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
from pathlib import Path

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

# Profiles with the modern Research Workbench already expose Project/Evidence
# under Engineering → Research.  The compatibility layer must not append a
# second project panel automatically for these profiles.
WORKBENCH_PROJECT_PROFILES = {
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radiation-platform",
    "radia-magnet-studio",
}
STANDALONE_PROJECT_PROFILES = SUPPORTED_PROFILES - WORKBENCH_PROJECT_PROFILES

LEGACY_SYNC_SESSION_KEY = "_pl_legacy_workspace_bridge_v1"


def _active_project(st, projects) -> Path | None:
    raw = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if (path / "project.json").exists() else None


def _access_label(surface, profile: str, project_path: Path | None, registry) -> str:
    if surface.launch_mode == "route":
        return "Project route"
    if surface.launch_mode == "profile":
        return "Current profile route" if profile in surface.profiles else "Profile-specific"
    ok, _reason = registry.launchability(surface, profile, project_path)
    return "Direct" if ok else "Needs context"


def _render_all_workspaces(st, profile: str) -> None:
    import physical_lab_project_kernel as projects
    import physical_lab_surface_registry as registry

    project_path = _active_project(st, projects)
    catalog = registry.surfaces_for_catalog(profile)

    st.markdown("### 🧭 All Workspaces")
    st.caption(
        "Every user-facing Engineering Lab capability is listed here. Direct workspaces can be opened in place; "
        "profile-scoped workspaces stay visible with their native route instead of being silently hidden."
    )

    direct_count = sum(1 for row in catalog if row.launch_mode == "direct")
    profile_count = sum(1 for row in catalog if row.launch_mode == "profile")
    route_count = sum(1 for row in catalog if row.launch_mode == "route")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Workspaces", len(catalog))
    c2.metric("Direct", direct_count)
    c3.metric("Profile-scoped", profile_count)
    c4.metric("Project routes", route_count)

    a, b = st.columns([2, 1])
    query = a.text_input(
        "Find a workspace",
        value="",
        placeholder="U-Tube, reliability, Kerr, radiation, visualization…",
        key=f"pl_surface_search_{profile}",
    ).strip().lower()
    category = b.selectbox(
        "Category",
        ["All"] + list(registry.surface_categories()),
        key=f"pl_surface_category_{profile}",
    )

    filtered = []
    for row in catalog:
        if category != "All" and row.category != category:
            continue
        haystack = " ".join((row.label, row.description, row.category, row.route_hint, " ".join(row.profiles))).lower()
        if query and query not in haystack:
            continue
        filtered.append(row)

    if not filtered:
        st.info("No workspaces match the current search/filter.")
        return

    st.dataframe(
        [
            {
                "Workspace": row.label,
                "Category": row.category,
                "Access": _access_label(row, profile, project_path, registry),
                "Where": row.route_hint or (", ".join(row.profiles) if row.profiles else "Open here"),
                "Description": row.description,
            }
            for row in filtered
        ],
        hide_index=True,
        width="stretch",
    )

    options = {f"{row.label} · {row.category}": row.surface_id for row in filtered}
    target_surface = str(st.query_params.get("pl_surface") or "").strip()
    target_action = str(st.query_params.get("pl_action") or "").strip()
    option_labels = list(options)
    target_label = next((label for label, sid in options.items() if sid == target_surface), None)
    if target_label and st.session_state.get(f"pl_surface_deeplink_seen_{profile}") != target_surface:
        st.session_state[f"pl_surface_choice_{profile}"] = target_label
        st.session_state[f"pl_surface_deeplink_seen_{profile}"] = target_surface
        target_row = registry.get_surface(target_surface)
        if target_row is not None and target_row.launch_mode == "direct":
            st.session_state[f"pl_all_workspaces_active_{profile}"] = target_surface
    chosen_label = st.selectbox("Workspace", option_labels, key=f"pl_surface_choice_{profile}")
    chosen = registry.get_surface(options[chosen_label])
    if chosen is None:
        st.warning("The selected workspace is no longer registered.")
        return

    st.markdown(f"#### {chosen.label}")
    st.caption(chosen.description)
    if target_action and target_surface == chosen.surface_id:
        st.info(f"Target tool/action: **{target_action}** — this is the preserved pre-redesign control to use in the workspace below.")
    ok, reason = registry.launchability(chosen, profile, project_path)

    if chosen.launch_mode == "profile":
        required = ", ".join(chosen.profiles) if chosen.profiles else "native profile"
        if target_surface == chosen.surface_id:
            st.success(f"Opened capability target: {chosen.label}")
        if profile in chosen.profiles:
            st.info(
                f"Available in the current `{profile}` Lab through its native route: "
                f"{chosen.route_hint or 'Engineering V&V/UQ'}. It stays there because it depends on native Lab/namespace state."
            )
        else:
            st.info(
                f"Profile-scoped workspace. Open one of: {required}. Route: "
                f"{chosen.route_hint or 'native Engineering Lab profile'}."
            )
        return

    if chosen.launch_mode == "route":
        if target_surface == chosen.surface_id:
            st.success(f"Opened capability target: {chosen.label}")
        st.info(chosen.route_hint or "Available through Project Workspace.")
        if chosen.surface_id == "utube-studio" and st.button(
            "Open U-Tube Research Studio",
            type="primary",
            key=f"pl_surface_route_{profile}_{chosen.surface_id}",
        ):
            st.session_state[f"pl_unified_surface_nav_{profile}"] = "Project Workspace"
            st.session_state[f"pl_project_surface_{profile}"] = "U-Tube Research Studio"
            st.rerun()
        return

    if not ok:
        st.info(reason)
        return

    active_key = f"pl_all_workspaces_active_{profile}"
    c_open, c_clear = st.columns(2)
    if c_open.button("Open workspace", type="primary", key=f"pl_surface_open_{profile}_{chosen.surface_id}"):
        st.session_state[active_key] = chosen.surface_id
        st.rerun()
    if c_clear.button("Close active workspace", key=f"pl_surface_close_{profile}"):
        st.session_state.pop(active_key, None)
        st.rerun()

    active_id = str(st.session_state.get(active_key) or "")
    if active_id:
        active = registry.get_surface(active_id)
        if active is not None:
            st.markdown("---")
            st.markdown(f"### Open: {active.label}")
            registry.render_surface(st, active, profile, project_path)
        else:
            st.session_state.pop(active_key, None)

    st.caption(
        "Catalog visibility is not scientific validation. Opening a workspace does not execute queued work, "
        "change source data, certify a result, or reinterpret model/measurement evidence."
    )


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

            # Bundled standalone Labs still need the compatibility Project/Evidence
            # mount. Modern Research Workbench profiles already own that surface
            # under Engineering → Research, so do not duplicate it automatically.
            if profile in STANDALONE_PROJECT_PROFILES:
                from physical_lab_project_kernel import render_project_workspace
                render_project_workspace(st, profile, namespace)

            # Keep every restored Engineering Club / analysis surface discoverable.
            # Workbench profiles default to All Workspaces so the compatibility
            # layer does not look like a duplicate Project panel; selecting a
            # project-routed surface (for example U-Tube Research Studio) switches
            # this state explicitly to Project Workspace.
            st.markdown("---")
            nav_key = f"pl_unified_surface_nav_{profile}"
            if nav_key not in st.session_state:
                st.session_state[nav_key] = (
                    "All Workspaces" if profile in WORKBENCH_PROJECT_PROFILES else "Project Workspace"
                )
            navigator = st.radio(
                "Engineering Lab navigator",
                ["Project Workspace", "All Workspaces"],
                horizontal=True,
                key=nav_key,
            )

            if navigator == "Project Workspace":
                from physical_lab_project_interop_ui import render_project_interop
                render_project_interop(st, profile)
            else:
                import physical_lab_surface_registry as registry
                _ = registry.SURFACES  # canonical inventory marker for wiring validation
                _render_all_workspaces(st, profile)
        except Exception as exc:
            try:
                import streamlit as st
                st.warning(f"Engineering Lab Project / workspace surface could not load: {exc}")
            except Exception:
                pass

    advanced.render_advanced_experiments = wrapped
    advanced._physical_lab_project_surface_patched = True
