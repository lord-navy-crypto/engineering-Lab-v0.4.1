"""Central All Workspaces catalog for Engineering Lab.

This module renders discoverability/navigation only. The canonical surface
inventory and dispatch semantics live in physical_lab_surface_registry.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_surface_registry import (
    SURFACES,
    get_surface,
    launchability,
    render_surface,
    surface_categories,
    surfaces_for_catalog,
)


def _active_project(st: Any) -> Path | None:
    raw = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if (path / "project.json").exists() else None


def _access_label(surface, profile: str, project_path: Path | None) -> str:
    if surface.launch_mode == "route":
        return "Project route"
    if surface.launch_mode == "profile":
        return "Current profile route" if profile in surface.profiles else "Profile-specific"
    ok, _reason = launchability(surface, profile, project_path)
    return "Direct" if ok else "Needs context"


def _route_label(surface) -> str:
    if surface.route_hint:
        return surface.route_hint
    if surface.profiles:
        return ", ".join(surface.profiles)
    return "Open here"


def _open_project_route(st: Any, profile: str, surface_id: str) -> None:
    if surface_id == "utube-studio":
        st.session_state[f"pl_unified_surface_nav_{profile}"] = "Project Workspace"
        st.session_state[f"pl_project_surface_{profile}"] = "U-Tube Research Studio"
        st.rerun()
    st.info("This workspace is already exposed through Project Workspace; use the route shown above.")


def render_all_workspaces(st: Any, profile: str) -> None:
    """Render the canonical catalog and one explicitly selected safe workspace."""
    project_path = _active_project(st)
    catalog = surfaces_for_catalog(profile)

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
        ["All"] + list(surface_categories()),
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
                "Access": _access_label(row, profile, project_path),
                "Where": _route_label(row),
                "Description": row.description,
            }
            for row in filtered
        ],
        hide_index=True,
        width="stretch",
    )

    options = {f"{row.label} · {row.category}": row.surface_id for row in filtered}
    chosen_label = st.selectbox(
        "Workspace",
        list(options),
        key=f"pl_surface_choice_{profile}",
    )
    chosen = get_surface(options[chosen_label])
    if chosen is None:
        st.warning("The selected workspace is no longer registered.")
        return

    st.markdown(f"#### {chosen.label}")
    st.caption(chosen.description)
    ok, reason = launchability(chosen, profile, project_path)

    if chosen.launch_mode == "profile":
        required = ", ".join(chosen.profiles) if chosen.profiles else "native profile"
        if profile in chosen.profiles:
            st.info(
                f"This workspace is available in the current `{profile}` Lab through its native route: "
                f"{chosen.route_hint or 'Engineering V&V/UQ'}. It stays there because it depends on native Lab/namespace state."
            )
        else:
            st.info(
                f"Profile-scoped workspace. Open one of: {required}. Route: "
                f"{chosen.route_hint or 'native Engineering Lab profile'}。"
            )
        return

    if chosen.launch_mode == "route":
        st.info(chosen.route_hint or "Available through Project Workspace.")
        if chosen.surface_id == "utube-studio":
            if st.button("Open U-Tube Research Studio", type="primary", key=f"pl_surface_route_{profile}_{chosen.surface_id}"):
                _open_project_route(st, profile, chosen.surface_id)
        return

    if not ok:
        st.info(reason)
        return

    active_key = f"pl_all_workspaces_active_{profile}"
    c_open, c_clear = st.columns([1, 1])
    if c_open.button("Open workspace", type="primary", key=f"pl_surface_open_{profile}_{chosen.surface_id}"):
        st.session_state[active_key] = chosen.surface_id
        st.rerun()
    if c_clear.button("Close active workspace", key=f"pl_surface_close_{profile}"):
        st.session_state.pop(active_key, None)
        st.rerun()

    active_id = str(st.session_state.get(active_key) or "")
    if active_id:
        active = get_surface(active_id)
        if active is not None:
            st.markdown("---")
            st.markdown(f"### Open: {active.label}")
            render_surface(st, active, profile, project_path)
        else:
            st.session_state.pop(active_key, None)

    st.caption(
        "Catalog visibility is not scientific validation. Opening a workspace does not execute queued work, "
        "change source data, certify a result, or reinterpret model/measurement evidence."
    )
