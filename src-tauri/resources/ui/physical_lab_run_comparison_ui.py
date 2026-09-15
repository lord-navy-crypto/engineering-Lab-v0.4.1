"""Run comparison and result staleness dashboard for Physical Lab projects."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

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
            if job.get("status") != "succeeded":
                continue
            full = read_sweep_result(str(job.get("id"))) or {}
            for i, point in enumerate(full.get("points") or []):
                if not isinstance(point, dict) or point.get("status") != "succeeded" or not isinstance(point.get("result"), dict):
                    continue
                rows.append({"key": f"sweep::{job['id']}::{i}", "label": f"Sweep · {job.get('adapter')} · {job['id']} · point {i}", "kind": "sweep", "job_id": str(job["id"]), "point_index": int(i)})
    except Exception:
        pass
    return rows


def _snapshot(option: dict[str, Any], project_path: Path) -> dict[str, Any]:
    current = project_run_snapshot(project_path, option["job_id"]) if option["kind"] == "project" else sweep_point_snapshot(option["job_id"], int(option["point_index"]))
    return freeze_if_missing(project_path, current)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _render_staleness(st: Any, title: str, report: dict[str, Any]) -> None:
    status = str(report.get("status") or "UNKNOWN")
    if status == "STALE":
        st.error(f"{title}: STALE")
    elif status == "REVIEW":
        st.warning(f"{title}: REVIEW")
    else:
        st.success(f"{title}: CURRENT")
    reasons = report.get("reasons") or []
    if reasons:
        st.dataframe(reasons, hide_index=True, width="stretch")


def _render_overview(st: Any, snap_a: dict[str, Any], snap_b: dict[str, Any], comparison: dict[str, Any]) -> None:
    parameter_rows = comparison.get("parameter_differences") or []
    metric_rows = comparison.get("metric_differences") or []
    runtime_a = _finite_number((comparison.get("runtime") or {}).get("a"))
    runtime_b = _finite_number((comparison.get("runtime") or {}).get("b"))

    m1, m2, m3 = st.columns(3)
    m1.metric("Changed parameters", len(parameter_rows))
    m2.metric("Common scalar metrics", len(metric_rows))
    if runtime_a is not None and runtime_b is not None:
        m3.metric("Runtime B − A", f"{runtime_b - runtime_a:.6g} s", delta=f"{(runtime_b - runtime_a):.6g} s")
    else:
        m3.metric("Runtime comparison", "unavailable")

    st.markdown("#### Run identity")
    st.dataframe(
        [
            {
                "run": "A",
                "id": snap_a.get("run_id"),
                "source": snap_a.get("source_kind"),
                "profile": snap_a.get("profile"),
                "schema": snap_a.get("result_schema"),
                "experiment_sha256": snap_a.get("experiment_sha256"),
                "source_commit": snap_a.get("source_commit"),
                "environment_sha256": snap_a.get("environment_sha256"),
                "result_sha256": snap_a.get("result_sha256"),
                "runtime_s": snap_a.get("runtime_s"),
                "sanity": (snap_a.get("sanity") or {}).get("status"),
            },
            {
                "run": "B",
                "id": snap_b.get("run_id"),
                "source": snap_b.get("source_kind"),
                "profile": snap_b.get("profile"),
                "schema": snap_b.get("result_schema"),
                "experiment_sha256": snap_b.get("experiment_sha256"),
                "source_commit": snap_b.get("source_commit"),
                "environment_sha256": snap_b.get("environment_sha256"),
                "result_sha256": snap_b.get("result_sha256"),
                "runtime_s": snap_b.get("runtime_s"),
                "sanity": (snap_b.get("sanity") or {}).get("status"),
            },
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(str(comparison.get("boundary") or ""))


def _render_parameter_delta(st: Any, rows: list[dict[str, Any]], profile: str) -> None:
    if not rows:
        st.success("No parameter differences found in the captured parameter mappings.")
        return

    display_rows: list[dict[str, Any]] = []
    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        a = _finite_number(row.get("a"))
        b = _finite_number(row.get("b"))
        relative_change = None if a is None or b is None or abs(a) <= 1e-30 else (b - a) / abs(a)
        enriched = {**row, "relative_change": relative_change}
        display_rows.append(enriched)
        if relative_change is not None and math.isfinite(relative_change):
            chart_rows.append(enriched)

    if chart_rows:
        chart_rows = sorted(chart_rows, key=lambda row: abs(float(row["relative_change"])), reverse=True)[:40]
        fig = go.Figure(
            go.Bar(
                x=[100.0 * float(row["relative_change"]) for row in chart_rows],
                y=[str(row.get("field") or "") for row in chart_rows],
                orientation="h",
                customdata=[[row.get("a"), row.get("b")] for row in chart_rows],
                hovertemplate="%{y}<br>A=%{customdata[0]}<br>B=%{customdata[1]}<br>relative change=%{x:.4g}%<extra></extra>",
                name="B − A relative to |A|",
            )
        )
        fig.add_vline(x=0, line_width=1)
        fig.update_layout(
            title="Numeric parameter change · (B − A) / |A|",
            xaxis_title="Relative change (%)",
            yaxis_title="Parameter",
            height=max(380, 34 * len(chart_rows) + 160),
            margin={"l": 20, "r": 20, "t": 60, "b": 40},
        )
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False}, key=f"pl_compare_parameter_delta_{profile}")
    else:
        st.info("Changed parameters are non-numeric or have a zero/unknown Run A reference, so a relative-change chart would be undefined.")

    st.dataframe(display_rows, hide_index=True, width="stretch")
    st.caption("The parameter chart is a display-only within-field relative change. Raw values from fields with different units or scales are not compared against one another; a visible change does not establish causality or scientific importance.")


def _render_metric_delta(st: Any, rows: list[dict[str, Any]], profile: str) -> None:
    if not rows:
        st.info("No common finite scalar metrics were available for direct numeric delta comparison.")
        return

    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        relative_delta = _finite_number(row.get("relative_delta"))
        if relative_delta is not None:
            chart_rows.append({**row, "relative_delta": relative_delta})

    if chart_rows:
        chart_rows = sorted(chart_rows, key=lambda row: abs(float(row["relative_delta"])), reverse=True)[:50]
        fig = go.Figure(
            go.Bar(
                x=[100.0 * float(row["relative_delta"]) for row in chart_rows],
                y=[str(row.get("metric") or "") for row in chart_rows],
                orientation="h",
                customdata=[[row.get("a"), row.get("b"), row.get("delta_b_minus_a")] for row in chart_rows],
                hovertemplate="%{y}<br>A=%{customdata[0]:.6g}<br>B=%{customdata[1]:.6g}<br>B−A=%{customdata[2]:.6g}<br>relative delta=%{x:.4g}%<extra></extra>",
                name="Metric relative delta",
            )
        )
        fig.add_vline(x=0, line_width=1)
        fig.update_layout(
            title="Scalar metric relative delta · existing comparison engine",
            xaxis_title="Relative delta (%)",
            yaxis_title="Metric",
            height=max(400, 32 * len(chart_rows) + 170),
            margin={"l": 20, "r": 20, "t": 60, "b": 40},
        )
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False}, key=f"pl_compare_metric_delta_{profile}")
    else:
        st.info("Common scalar metrics exist, but their relative deltas are undefined because the Run A reference is zero or unavailable.")

    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption("Metric deltas are descriptive numeric differences from the comparison engine. They do not imply statistical significance, causal attribution, experimental equivalence, or model validation.")


def _render_quality_provenance(
    st: Any,
    snap_a: dict[str, Any],
    snap_b: dict[str, Any],
    comparison: dict[str, Any],
    current_env: dict[str, Any],
) -> None:
    st.markdown("#### Numerical quality and explicit uncertainty")
    q1, q2 = st.columns(2)
    with q1:
        st.markdown("##### Run A")
        st.json((comparison.get("sanity") or {}).get("a"))
        uq = (comparison.get("uncertainty") or {}).get("a") or []
        st.json(uq) if uq else st.caption("No explicit uncertainty object.")
    with q2:
        st.markdown("##### Run B")
        st.json((comparison.get("sanity") or {}).get("b"))
        uq = (comparison.get("uncertainty") or {}).get("b") or []
        st.json(uq) if uq else st.caption("No explicit uncertainty object.")

    st.markdown("#### Provenance / staleness")
    s1, s2 = st.columns(2)
    with s1:
        _render_staleness(st, "Run A", (comparison.get("staleness") or {}).get("a") or {})
    with s2:
        _render_staleness(st, "Run B", (comparison.get("staleness") or {}).get("b") or {})

    st.dataframe(
        [
            {
                "run": "A",
                "source_commit": snap_a.get("source_commit"),
                "environment_sha256": snap_a.get("environment_sha256"),
                "contract_sha256": snap_a.get("contract_sha256"),
                "snapshot_sha256": snap_a.get("snapshot_sha256"),
            },
            {
                "run": "B",
                "source_commit": snap_b.get("source_commit"),
                "environment_sha256": snap_b.get("environment_sha256"),
                "contract_sha256": snap_b.get("contract_sha256"),
                "snapshot_sha256": snap_b.get("snapshot_sha256"),
            },
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Current environment reference", expanded=False):
        st.json(current_env)
    st.caption("Staleness indicates provenance/version drift only. It is not evidence that an older numerical result is physically or mathematically wrong.")


def render_run_comparison(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open a project to compare persisted runs.")
        return
    project_path = Path(active)
    options = _run_options(project_path)
    if len(options) < 2:
        st.info("At least two completed project/sweep results are needed for run comparison.")
        return

    st.caption("Compare parameters, scalar metrics, numerical sanity, explicit uncertainty, software environment and provenance. The first comparison freezes a historical run snapshot for later staleness detection; comparability labels are evidence warnings, not significance tests.")
    by_key = {row["key"]: row for row in options}
    keys = list(by_key)
    c1, c2 = st.columns(2)
    key_a = c1.selectbox("Run A", keys, index=0, format_func=lambda k: by_key[k]["label"], key=f"pl_compare_a_{profile}")
    key_b = c2.selectbox("Run B", keys, index=1 if len(keys) > 1 else 0, format_func=lambda k: by_key[k]["label"], key=f"pl_compare_b_{profile}")
    if key_a == key_b:
        st.warning("Choose two different runs.")
        return
    try:
        snap_a = _snapshot(by_key[key_a], project_path)
        snap_b = _snapshot(by_key[key_b], project_path)
    except Exception as exc:
        st.warning(f"Could not load/freeze selected run snapshots: {exc}")
        return

    current_env = build_environment_manifest(extra={"active_profile": profile})
    comparison = compare_runs(snap_a, snap_b, current_environment=current_env)
    a, b, c, d = st.columns(4)
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

    view = st.radio(
        "Comparison view",
        ["Overview", "Parameter Delta", "Metric Delta", "Quality + Provenance"],
        horizontal=True,
        key=f"pl_compare_view_{profile}",
    )
    if view == "Overview":
        _render_overview(st, snap_a, snap_b, comparison)
    elif view == "Parameter Delta":
        _render_parameter_delta(st, comparison.get("parameter_differences") or [], profile)
    elif view == "Metric Delta":
        _render_metric_delta(st, comparison.get("metric_differences") or [], profile)
    else:
        _render_quality_provenance(st, snap_a, snap_b, comparison, current_env)

    with st.expander("Comparison fingerprint / frozen evidence", expanded=False):
        st.json(
            {
                "comparison_sha256": comparison["comparison_sha256"],
                "snapshot_a_sha256": snap_a.get("snapshot_sha256"),
                "snapshot_b_sha256": snap_b.get("snapshot_sha256"),
            }
        )
