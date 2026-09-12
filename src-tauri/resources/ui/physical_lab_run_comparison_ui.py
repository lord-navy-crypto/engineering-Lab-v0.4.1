"""Run comparison and result staleness dashboard for Physical Lab projects."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_environment_manifest import build_environment_manifest
from physical_lab_run_comparison import compare_runs, project_run_snapshot, sweep_point_snapshot
from physical_lab_run_snapshot_store import freeze_if_missing


def _run_options(project_path: Path) -> list[dict[str, Any]]:
    doc = projects.open_project(project_path)
    rows: list[dict[str, Any]] = []
    for job_id, entry in (doc.get("results") or {}).items():
        if not isinstance(entry, dict):
            continue
        rows.append({"key": f"project::{job_id}", "label": f"Project · {job_id}", "kind": "project", "job_id": str(job_id)})
    try:
        from physical_lab_sweep_executor import list_sweep_jobs, read_sweep_result
        for job in list_sweep_jobs(limit=100):
            if job.get("status") != "succeeded": continue
            full = read_sweep_result(str(job.get("id"))) or {}
            for i, point in enumerate(full.get("points") or []):
                if not isinstance(point, dict) or point.get("status") != "succeeded" or not isinstance(point.get("result"), dict): continue
                rows.append({"key": f"sweep::{job['id']}::{i}", "label": f"Sweep · {job.get('adapter')} · {job['id']} · point {i}", "kind": "sweep", "job_id": str(job["id"]), "point_index": int(i)})
    except Exception:
        pass
    return rows


def _snapshot(option: dict[str, Any], project_path: Path) -> dict[str, Any]:
    current = project_run_snapshot(project_path, option["job_id"]) if option["kind"] == "project" else sweep_point_snapshot(option["job_id"], int(option["point_index"]))
    return freeze_if_missing(project_path, current)


def _render_staleness(st: Any, title: str, report: dict[str, Any]) -> None:
    status = str(report.get("status") or "UNKNOWN")
    if status == "STALE": st.error(f"{title}: STALE")
    elif status == "REVIEW": st.warning(f"{title}: REVIEW")
    else: st.success(f"{title}: CURRENT")
    reasons = report.get("reasons") or []
    if reasons: st.dataframe(reasons, hide_index=True, width="stretch")


def render_run_comparison(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open a project to compare persisted runs."); return
    project_path = Path(active)
    options = _run_options(project_path)
    if len(options) < 2:
        st.info("At least two completed project/sweep results are needed for run comparison."); return

    st.caption("Compare parameters, scalar metrics, numerical sanity, explicit uncertainty, software environment and provenance. The first comparison freezes a historical run snapshot for later staleness detection; comparability labels are evidence warnings, not significance tests.")
    by_key = {row["key"]: row for row in options}; keys = list(by_key)
    c1, c2 = st.columns(2)
    key_a = c1.selectbox("Run A", keys, index=0, format_func=lambda k: by_key[k]["label"], key=f"pl_compare_a_{profile}")
    key_b = c2.selectbox("Run B", keys, index=1 if len(keys)>1 else 0, format_func=lambda k: by_key[k]["label"], key=f"pl_compare_b_{profile}")
    if key_a == key_b:
        st.warning("Choose two different runs."); return
    try:
        snap_a = _snapshot(by_key[key_a], project_path); snap_b = _snapshot(by_key[key_b], project_path)
    except Exception as exc:
        st.warning(f"Could not load/freeze selected run snapshots: {exc}"); return

    current_env = build_environment_manifest(extra={"active_profile": profile})
    comparison = compare_runs(snap_a, snap_b, current_environment=current_env)
    a,b,c,d = st.columns(4)
    a.metric("Comparability", comparison["comparability"])
    b.metric("Same schema", "yes" if comparison["same_result_schema"] else "no")
    c.metric("Same contract", "yes" if comparison["same_contract"] else "no")
    d.metric("Same environment", "yes" if comparison["same_environment"] else "no/unknown")
    if comparison["comparability"] == "INCOMPATIBLE-SCHEMA":
        st.error("Result schemas differ. Numeric deltas below are exploratory only and should not be interpreted as like-for-like model outputs.")
    elif comparison["comparability"] in {"REVIEW-CONTRACT", "COMPARABLE-WITH-ENV-DRIFT"}:
        st.warning("Runs require provenance review before treating differences as like-for-like scientific changes.")
    elif comparison["comparability"] == "DIFFERENT-INPUTS":
        st.info("Runs share a result schema/contract but were generated from different scientific input fingerprints.")
    else:
        st.success("No configured schema/contract/environment incompatibility blocks direct structural comparison.")

    tab_summary, tab_params, tab_metrics, tab_quality, tab_stale = st.tabs(["Summary", "Parameters", "Metrics", "Quality & UQ", "Staleness / Environment"])
    with tab_summary:
        st.dataframe([
            {"run":"A","id":snap_a.get("run_id"),"source":snap_a.get("source_kind"),"profile":snap_a.get("profile"),"schema":snap_a.get("result_schema"),"experiment_sha256":snap_a.get("experiment_sha256"),"source_commit":snap_a.get("source_commit"),"environment_sha256":snap_a.get("environment_sha256"),"result_sha256":snap_a.get("result_sha256"),"runtime_s":snap_a.get("runtime_s"),"sanity":(snap_a.get("sanity") or {}).get("status")},
            {"run":"B","id":snap_b.get("run_id"),"source":snap_b.get("source_kind"),"profile":snap_b.get("profile"),"schema":snap_b.get("result_schema"),"experiment_sha256":snap_b.get("experiment_sha256"),"source_commit":snap_b.get("source_commit"),"environment_sha256":snap_b.get("environment_sha256"),"result_sha256":snap_b.get("result_sha256"),"runtime_s":snap_b.get("runtime_s"),"sanity":(snap_b.get("sanity") or {}).get("status")},
        ], hide_index=True, width="stretch"); st.caption(comparison["boundary"])
    with tab_params:
        rows = comparison.get("parameter_differences") or []
        st.dataframe(rows, hide_index=True, width="stretch") if rows else st.success("No parameter differences found in the captured parameter mappings.")
    with tab_metrics:
        rows = comparison.get("metric_differences") or []
        st.dataframe(rows, hide_index=True, width="stretch") if rows else st.info("No common finite scalar metrics were available for direct numeric delta comparison.")
    with tab_quality:
        q1,q2 = st.columns(2)
        with q1:
            st.markdown("#### Run A"); st.json(comparison["sanity"]["a"]); uq=comparison["uncertainty"]["a"]; st.json(uq) if uq else st.caption("No explicit uncertainty object.")
        with q2:
            st.markdown("#### Run B"); st.json(comparison["sanity"]["b"]); uq=comparison["uncertainty"]["b"]; st.json(uq) if uq else st.caption("No explicit uncertainty object.")
    with tab_stale:
        s1,s2 = st.columns(2)
        with s1: _render_staleness(st,"Run A",comparison["staleness"]["a"])
        with s2: _render_staleness(st,"Run B",comparison["staleness"]["b"])
        st.markdown("#### Current environment reference"); st.json(current_env)
    with st.expander("Comparison fingerprint / frozen evidence", expanded=False):
        st.json({"comparison_sha256":comparison["comparison_sha256"],"snapshot_a_sha256":snap_a.get("snapshot_sha256"),"snapshot_b_sha256":snap_b.get("snapshot_sha256")})
