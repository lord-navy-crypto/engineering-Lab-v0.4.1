"""UI for explicit canonical-dataset -> model-parameter coupling."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_project_interop import list_canonical_datasets
from physical_lab_model_coupling import (
    REDUCERS,
    adapter_catalog,
    adapter_parameters,
    build_parameter_packet,
    list_pipelines,
    queue_packet,
    save_pipeline,
)
from physical_lab_sweep_executor import start_sweep_job


def _queued_key(profile: str) -> str:
    return f"pl_couple_queued_job_{profile}"


def _queue_downstream_model(st: Any, profile: str, packet: dict[str, Any]) -> dict[str, Any]:
    """Create a queued downstream job without starting execution."""
    job = queue_packet(packet)
    state = {
        "job_id": str(job["id"]),
        "target_profile": str(packet.get("target_profile") or ""),
        "packet_sha256": str(packet.get("packet_sha256") or ""),
        "execution_started": False,
    }
    st.session_state[_queued_key(profile)] = state
    return state


def _start_queued_downstream_model(st: Any, profile: str, packet: dict[str, Any]) -> dict[str, Any]:
    """Start only the queued job that belongs to the currently reviewed packet."""
    state = st.session_state.get(_queued_key(profile))
    if not isinstance(state, dict) or not state.get("job_id"):
        raise ValueError("Queue this parameter packet before starting downstream execution.")
    packet_sha = str(packet.get("packet_sha256") or "")
    if str(state.get("packet_sha256") or "") != packet_sha:
        raise ValueError("The queued job belongs to a different parameter packet. Queue the current packet again before starting.")
    if bool(state.get("execution_started")):
        raise ValueError("This queued downstream job has already been started.")

    job_id = str(state["job_id"])
    start_sweep_job(job_id)
    next_state = {**state, "execution_started": True}
    st.session_state[_queued_key(profile)] = next_state
    st.session_state[f"pl_orch_active_job_{packet['target_profile']}"] = job_id
    return next_state


def _mapping_stage_labels(row: dict[str, Any]) -> list[str]:
    conversion = row.get("conversion")
    if isinstance(conversion, dict):
        unit_label = f"{conversion.get('from') or '—'} → {conversion.get('to') or '—'}"
    else:
        unit_label = "no unit conversion"
    scale = float(row.get("scale", 1.0))
    offset = float(row.get("offset", 0.0))
    affine = f"{scale:g}×x {offset:+g}"
    reducer = str(row.get("reducer") or "mean")
    if reducer == "row" and row.get("row_index") is not None:
        reducer = f"row[{row.get('row_index')}]"
    return [
        str(row.get("source_column") or "source"),
        reducer,
        unit_label,
        affine,
        str(row.get("target_parameter") or "target"),
    ]


def _render_mapping_flow(st: Any, packet: dict[str, Any], *, key: str) -> None:
    """Visualize recorded mapping stages without adding new transformation semantics."""
    import plotly.graph_objects as go

    rows = list(packet.get("mappings") or [])
    if not rows:
        st.info("This parameter packet has no mapping rows to visualize.")
        return

    stage_names = ["Source", "Reducer", "Unit conversion", "Affine transform", "Target"]
    fig = go.Figure()
    for idx, row in enumerate(rows):
        y = len(rows) - 1 - idx
        labels = _mapping_stage_labels(row)
        raw = row.get("raw_value")
        converted = row.get("converted_value")
        final = row.get("value")
        hover = [
            f"Source column: {labels[0]}<br>Raw value: {raw}",
            f"Reducer: {labels[1]}<br>Reduced value: {raw}",
            f"Unit step: {labels[2]}<br>Converted value: {converted}",
            f"Affine: {labels[3]}<br>Final value: {final}",
            f"Target parameter: {labels[4]}<br>Final value: {final}",
        ]
        fig.add_trace(
            go.Scatter(
                x=list(range(5)),
                y=[y] * 5,
                mode="lines+markers+text",
                text=labels,
                textposition="top center",
                hovertext=hover,
                hoverinfo="text",
                name=f"Mapping {idx + 1}",
                showlegend=False,
                cliponaxis=False,
            )
        )

    fig.update_layout(
        title="Recorded dataset → parameter mapping flow",
        xaxis={"tickmode": "array", "tickvals": list(range(5)), "ticktext": stage_names, "range": [-0.3, 4.3]},
        yaxis={"visible": False, "range": [-0.6, max(0.6, len(rows) - 0.25)]},
        height=max(340, 150 + 105 * len(rows)),
        margin={"l": 30, "r": 30, "t": 70, "b": 60},
        hovermode="closest",
    )
    st.plotly_chart(fig, width="stretch", key=key)
    st.caption(
        "Visual flow of the transformations already recorded in this packet. It does not infer physical compatibility, "
        "causality, calibration validity, model-form suitability, or scientific validation."
    )


def _packet_preview(st: Any, packet: dict[str, Any]) -> None:
    st.dataframe(
        [
            {
                "target": row.get("target_parameter"),
                "value": row.get("value"),
                "source": row.get("source_column"),
                "reducer": row.get("reducer"),
                "raw": row.get("raw_value"),
                "converted": row.get("converted_value"),
                "conversion": row.get("conversion"),
                "scale": row.get("scale"),
                "offset": row.get("offset"),
            }
            for row in packet.get("mappings") or []
        ],
        hide_index=True,
        width="stretch",
    )
    st.json(
        {
            "source_dataset_id": packet.get("source_dataset_id"),
            "source_dataset_sha256": packet.get("source_dataset_sha256"),
            "target_adapter": packet.get("target_adapter"),
            "target_profile": packet.get("target_profile"),
            "parameters": packet.get("parameters"),
            "packet_sha256": packet.get("packet_sha256"),
        }
    )
    st.caption(str(packet.get("boundary") or ""))


def _render_configure(st: Any, profile: str, datasets: list[dict[str, Any]]) -> None:
    dataset_ids = [d["dataset_id"] for d in datasets]
    selected_dataset = st.selectbox("Source canonical dataset", dataset_ids, key=f"pl_couple_dataset_{profile}")
    dataset = next(d for d in datasets if d["dataset_id"] == selected_dataset)
    st.caption(
        f"{dataset.get('name')} · source profile={dataset.get('profile')} · "
        f"sha256 {str(dataset.get('sha256') or '')[:16]}…"
    )

    catalog = adapter_catalog()
    adapter_ids = [row["id"] for row in catalog]
    labels = {row["id"]: row["label"] for row in catalog}
    adapter_id = st.selectbox(
        "Downstream adapter",
        adapter_ids,
        format_func=lambda x: f"{labels[x]} · {x}",
        key=f"pl_couple_adapter_{profile}",
    )
    spec = next(row for row in catalog if row["id"] == adapter_id)
    target_profile = st.selectbox(
        "Downstream profile",
        spec["profiles"],
        key=f"pl_couple_target_profile_{profile}",
    )
    params = adapter_parameters(adapter_id)
    param_names = [row["name"] for row in params]
    columns = list(dataset.get("columns") or {})

    mapping_count = int(
        st.number_input(
            "Mappings",
            min_value=1,
            max_value=min(8, max(1, len(param_names))),
            value=min(2, max(1, len(param_names))),
            step=1,
            key=f"pl_couple_count_{profile}",
        )
    )
    mappings = []
    st.markdown("#### Explicit mappings")
    for i in range(mapping_count):
        st.markdown(f"**Mapping {i + 1}**")
        c1, c2, c3 = st.columns([1.2, 1, 1.2])
        source = c1.selectbox("Source column", columns, key=f"pl_couple_src_{profile}_{i}")
        reducer = c2.selectbox("Reducer", list(REDUCERS), key=f"pl_couple_red_{profile}_{i}")
        target = c3.selectbox(
            "Target parameter",
            param_names,
            index=min(i, len(param_names) - 1),
            key=f"pl_couple_tgt_{profile}_{i}",
        )
        row_index = 0
        if reducer == "row":
            row_index = int(
                st.number_input(
                    "Finite-value row index",
                    value=0,
                    step=1,
                    key=f"pl_couple_row_{profile}_{i}",
                )
            )
        source_default = str((dataset.get("units") or {}).get(source) or "")
        u1, u2, a, b = st.columns(4)
        source_unit = u1.text_input("Source unit", value=source_default, key=f"pl_couple_su_{profile}_{i}")
        target_unit = u2.text_input("Target unit", value=source_default, key=f"pl_couple_tu_{profile}_{i}")
        scale = float(a.number_input("Scale a", value=1.0, key=f"pl_couple_scale_{profile}_{i}"))
        offset = float(b.number_input("Offset b", value=0.0, key=f"pl_couple_offset_{profile}_{i}"))
        if bool(source_unit) != bool(target_unit):
            st.warning(f"Mapping {i + 1}: specify both source and target unit, or leave both blank.")
        mappings.append(
            {
                "source_column": source,
                "reducer": reducer,
                "row_index": row_index,
                "source_unit": source_unit,
                "target_unit": target_unit,
                "scale": scale,
                "offset": offset,
                "target_parameter": target,
            }
        )

    st.caption(
        "Build only creates a deterministic parameter packet. It does not save a pipeline, queue a job, or start execution."
    )
    if st.button("Build parameter packet", type="primary", key=f"pl_couple_build_{profile}"):
        packet = build_parameter_packet(
            dataset,
            adapter_id=adapter_id,
            target_profile=target_profile,
            mappings=mappings,
        )
        st.session_state[f"pl_couple_packet_{profile}"] = packet
        # A rebuilt packet invalidates the meaning of any previously queued job.
        st.session_state.pop(_queued_key(profile), None)
        st.success(f"Built parameter packet {str(packet.get('packet_sha256') or '')[:12]}…. Review it before saving or executing.")


def _render_review(st: Any, profile: str, packet: dict[str, Any] | None) -> None:
    if not packet:
        st.info("Build a parameter packet in Configure Mapping first.")
        return
    st.markdown("#### Mapping flow")
    _render_mapping_flow(st, packet, key=f"pl_couple_flow_{profile}")
    st.markdown("#### Parameter packet preview")
    _packet_preview(st, packet)


def _render_save_execute(st: Any, profile: str, project_path: Path, packet: dict[str, Any] | None) -> None:
    if not packet:
        st.info("Build and review a parameter packet before saving or executing it.")
        return

    packet_sha = str(packet.get("packet_sha256") or "")
    st.markdown("#### Current parameter packet")
    a, b, c = st.columns(3)
    a.metric("Target adapter", str(packet.get("target_adapter") or "—"))
    b.metric("Target profile", str(packet.get("target_profile") or "—"))
    c.metric("Packet SHA", packet_sha[:12] + ("…" if packet_sha else ""))

    pipeline_name = st.text_input(
        "Pipeline name",
        value=f"{packet.get('source_dataset_id') or 'dataset'} → {packet.get('target_adapter') or 'model'}",
        key=f"pl_couple_name_{profile}",
    )
    notes = st.text_input("Pipeline notes", value="", key=f"pl_couple_notes_{profile}")

    st.markdown("##### 1. Save provenance (optional)")
    st.caption("Saving records the mapping provenance only. It does not queue or execute the downstream model.")
    if st.button("Save coupling pipeline", key=f"pl_couple_save_{profile}"):
        rec = save_pipeline(project_path, name=pipeline_name, packet=packet, notes=notes)
        st.success(f"Saved {rec['pipeline_id']} · sha256 {rec['sha256'][:12]}…")

    st.markdown("##### 2. Queue downstream model")
    st.caption("Queueing creates a sweep job in QUEUED state. It does not start execution.")
    if st.button("Queue downstream model", type="primary", key=f"pl_couple_queue_{profile}"):
        state = _queue_downstream_model(st, profile, packet)
        st.success(f"Queued downstream job {state['job_id']}. Execution has not started.")

    queued = st.session_state.get(_queued_key(profile))
    if isinstance(queued, dict):
        if str(queued.get("packet_sha256") or "") != packet_sha:
            st.warning("The stored queued job belongs to an older parameter packet. Queue the current packet before starting.")
        else:
            state_label = "STARTED" if queued.get("execution_started") else "QUEUED · NOT STARTED"
            q1, q2, q3 = st.columns(3)
            q1.metric("Job", str(queued.get("job_id") or "—"))
            q2.metric("Execution", state_label)
            q3.metric("Target", str(queued.get("target_profile") or "—"))

    st.markdown("##### 3. Explicitly start queued model")
    can_start = (
        isinstance(queued, dict)
        and bool(queued.get("job_id"))
        and str(queued.get("packet_sha256") or "") == packet_sha
        and not bool(queued.get("execution_started"))
    )
    st.caption("Only this explicit action starts downstream computation.")
    if st.button(
        "Start queued downstream model",
        disabled=not can_start,
        key=f"pl_couple_start_{profile}",
    ):
        try:
            state = _start_queued_downstream_model(st, profile, packet)
            st.success(f"Started downstream sweep job {state['job_id']} for {state['target_profile']}.")
        except Exception as exc:
            st.error(str(exc))


def _render_provenance(st: Any, project_path: Path) -> None:
    pipelines = list_pipelines(project_path)
    if not pipelines:
        st.info("No saved coupling pipelines yet. Saving a pipeline records provenance but does not execute it.")
        return
    st.dataframe(
        [
            {
                "pipeline_id": p.get("pipeline_id"),
                "name": p.get("name"),
                "source_dataset": (p.get("packet") or {}).get("source_dataset_id"),
                "source_sha256": str((p.get("packet") or {}).get("source_dataset_sha256") or "")[:16],
                "target": (p.get("packet") or {}).get("target_adapter"),
                "target_profile": (p.get("packet") or {}).get("target_profile"),
                "packet_sha256": str((p.get("packet") or {}).get("packet_sha256") or "")[:16],
                "sha256": str(p.get("sha256") or "")[:16],
            }
            for p in pipelines
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Saved coupling provenance records how values were transported. It does not certify physical compatibility, calibration validity, or model suitability."
    )


def render_model_coupling(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("### Model-to-Model Coupling")
    st.caption(
        "Map explicit project-dataset statistics into parameters of an allow-listed downstream model. "
        "Every reduction, unit conversion and affine transform is recorded; no arbitrary expressions are executed."
    )

    task = st.radio(
        "Coupling task",
        ["Configure Mapping", "Review Packet", "Save / Execute", "Provenance"],
        horizontal=True,
        key=f"pl_couple_task_{profile}",
    )

    datasets = list_canonical_datasets(project_path)
    packet = st.session_state.get(f"pl_couple_packet_{profile}")
    if not isinstance(packet, dict):
        packet = None

    if task == "Configure Mapping":
        if not datasets:
            st.info("Create a canonical project dataset first in Data Bridge.")
            return
        _render_configure(st, profile, datasets)
    elif task == "Review Packet":
        _render_review(st, profile, packet)
    elif task == "Save / Execute":
        _render_save_execute(st, profile, project_path, packet)
    else:
        _render_provenance(st, project_path)
