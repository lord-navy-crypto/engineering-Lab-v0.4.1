"""Native desktop deep-link entry for Engineering Lab user-facing capabilities.

This module is navigation-only. It never changes scientific algorithms, validation
meaning, provenance meaning, or queued/execution semantics.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
from pathlib import Path
from typing import Any, Mapping

SESSION_KEY = "_pl_native_surface_consumed_v1"


def _catalog_path() -> Path:
    # resources/ui/<this file> -> resources/surfaces.json
    return Path(__file__).resolve().parents[1] / "surfaces.json"


def _catalog() -> dict[str, dict[str, Any]]:
    try:
        rows = json.loads(_catalog_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}
    return {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}


def _active_project(st: Any) -> Path | None:
    try:
        import physical_lab_project_kernel as projects
        raw = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "").strip()
    except Exception:
        return None
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if (path / "project.json").is_file() else None


def _project_required(st: Any, profile: str, namespace: Mapping[str, Any] | None) -> Path | None:
    path = _active_project(st)
    if path is not None:
        return path
    st.info("This workspace needs an active .physlab Project. Select or create one below; no project is created automatically.")
    try:
        from physical_lab_project_kernel import render_project_workspace
        render_project_workspace(st, profile, namespace or {})
    except Exception as exc:
        st.warning(f"Project selector could not load: {exc}")
    return None


def _artifact_refs(project_path: Path) -> list[str]:
    try:
        import physical_lab_surface_registry as registry
        return registry.artifact_refs(project_path)
    except Exception:
        return []


def _invoke_renderer(
    st: Any,
    row: Mapping[str, Any],
    profile: str,
    namespace: Mapping[str, Any] | None,
) -> None:
    module_name = str(row.get("targetModule") or "")
    callable_name = str(row.get("targetCallable") or "")
    if not module_name or not callable_name:
        st.warning("This capability does not have a direct renderer target.")
        return
    module = importlib.import_module(module_name)
    renderer = getattr(module, callable_name)
    mode = str(row.get("argumentMode") or "st_profile")

    if mode == "st_profile_namespace":
        renderer(st, profile, namespace or {})
        return
    if mode == "st_namespace":
        renderer(st, namespace or {})
        return
    if mode == "st_profile_project":
        project = _project_required(st, profile, namespace)
        if project is not None:
            renderer(st, profile, project)
        return
    if mode == "st_project_profile":
        project = _project_required(st, profile, namespace)
        if project is not None:
            renderer(st, project, profile)
        return
    if mode == "st_project_profile_refs":
        project = _project_required(st, profile, namespace)
        if project is not None:
            renderer(st, project, profile, _artifact_refs(project))
        return

    # Most registry rows are (st, profile). A few native RADIA workspaces predate
    # that convention and are (st, namespace) or (st, profile, namespace). Detect
    # those signatures rather than fabricating profile/namespace state.
    try:
        params = list(inspect.signature(renderer).parameters.values())
        names = [p.name.lower() for p in params]
    except Exception:
        names = []
    if len(names) >= 3 and names[2] in {"namespace", "ns"}:
        renderer(st, profile, namespace or {})
    elif len(names) >= 2 and names[1] in {"namespace", "ns"}:
        renderer(st, namespace or {})
    else:
        renderer(st, profile)


def _render_route(
    st: Any,
    route: str,
    profile: str,
    namespace: Mapping[str, Any] | None,
) -> None:
    import physical_lab_project_interop_ui as interop

    if route == "project-workspace":
        interop.render_project_interop(st, profile)
        return
    if route == "utube-studio":
        interop._render_utube_research_studio(st, profile)
        return
    if route == "betterboard-inbox":
        from physical_lab_betterboard_discovery_ui import render_betterboard_discovery
        render_betterboard_discovery(st, profile)
        return
    if route in {"research-notebook", "openguin-advisory"}:
        from physical_lab_labbridge_ui import render_labbridge
        render_labbridge(st, profile)
        return

    project = _project_required(st, profile, namespace)
    if project is None:
        return
    if route == "data-bridge":
        interop._render_data_bridge(st, profile, project)
    elif route == "reproducibility-pack":
        interop._render_reproducibility_group(st, profile, project)
    elif route == "measurement-registry":
        # Measurement/calibration records are owned by the canonical Project Kernel.
        try:
            from physical_lab_project_kernel import render_project_workspace
            render_project_workspace(st, profile, namespace or {})
        except Exception as exc:
            st.warning(f"Measurement & Calibration Registry could not load: {exc}")
    else:
        st.warning(f"Unsupported native route target: {route}")


def render_requested_surface(
    st: Any,
    namespace: Mapping[str, Any] | None,
    profile: str,
    capability_id: str,
) -> None:
    rows = _catalog()
    row = rows.get(str(capability_id))
    if row is None:
        st.warning(f"Desktop-requested capability is not registered: {capability_id}")
        return

    legal_profiles = tuple(str(x) for x in (row.get("profiles") or []) if str(x))
    if legal_profiles and profile not in legal_profiles:
        st.warning(
            f"{row.get('label') or capability_id} requires one of: {', '.join(legal_profiles)}. "
            f"The current host profile is {profile}."
        )
        return

    st.markdown("---")
    st.markdown(f"## 🧭 Desktop Requested Workspace · {row.get('label') or capability_id}")
    st.caption(
        "Opened directly from the Engineering Lab native Workbench. Desktop reachability does not imply scientific validation, "
        "and opening this page does not start queued work."
    )

    mode = str(row.get("argumentMode") or "st_profile")
    launch_mode = str(row.get("launchMode") or "direct")
    if mode == "native_route" or launch_mode == "route":
        _render_route(st, str(row.get("routeTarget") or ""), profile, namespace)
    else:
        _invoke_renderer(st, row, profile, namespace)


def install() -> None:
    try:
        import physical_lab_advanced as advanced
    except Exception:
        return
    if getattr(advanced, "_physical_lab_native_surface_entry_patched", False):
        return
    original = advanced.render_advanced_experiments

    def wrapped(namespace):
        original(namespace)
        requested = os.environ.get("PHYSICAL_LAB_INITIAL_SURFACE", "").strip()
        if not requested:
            return
        profile = os.environ.get("PHYSICAL_LAB_UI_PROFILE", "").strip()
        try:
            import streamlit as st
            state = getattr(st, "session_state", None)
            token = f"{profile}:{requested}"
            # Consume the desktop request once per session while keeping the
            # rendered workspace persistent across ordinary Streamlit reruns.
            if state is not None:
                state.setdefault(SESSION_KEY, token)
                active = str(state.get(SESSION_KEY) or token)
            else:
                active = token
            _, active_id = active.split(":", 1) if ":" in active else (profile, requested)
            render_requested_surface(st, namespace, profile, active_id)
        except Exception as exc:
            try:
                import streamlit as st
                st.warning(f"Desktop requested workspace could not load: {exc}")
            except Exception:
                pass

    advanced.render_advanced_experiments = wrapped
    advanced._physical_lab_native_surface_entry_patched = True
