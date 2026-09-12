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


def render_model_coupling(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return
    datasets = list_canonical_datasets(project_path)
    st.markdown("### Model-to-Model Coupling")
    st.caption(
        "Map explicit project-dataset statistics into parameters of an allow-listed downstream model. "
        "Every reduction, unit conversion and affine transform is recorded; no arbitrary expressions are executed."
    )
    if not datasets:
        st.info("Create a canonical project dataset first in Data Bridge.")
        return

    dataset_ids = [d["dataset_id"] for d in datasets]
    selected_dataset = st.selectbox("Source canonical dataset", dataset_ids, key=f"pl_couple_dataset_{profile}")
    dataset = next(d for d in datasets if d["dataset_id"] == selected_dataset)
    st.caption(f"{dataset.get('name')} · source profile={dataset.get('profile')} · sha256 {str(dataset.get('sha256') or '')[:16]}…")

    catalog = adapter_catalog()
    adapter_ids = [row["id"] for row in catalog]
    labels = {row["id"]: row["label"] for row in catalog}
    adapter_id = st.selectbox("Downstream adapter", adapter_ids, format_func=lambda x: f"{labels[x]} · {x}", key=f"pl_couple_adapter_{profile}")
    spec = next(row for row in catalog if row["id"] == adapter_id)
    target_profile = st.selectbox("Downstream profile", spec["profiles"], key=f"pl_couple_target_profile_{profile}")
    params = adapter_parameters(adapter_id)
    param_names = [row["name"] for row in params]
    columns = list(dataset.get("columns") or {})

    mapping_count = int(st.number_input("Mappings", min_value=1, max_value=min(8, max(1, len(param_names))), value=min(2, max(1, len(param_names))), step=1, key=f"pl_couple_count_{profile}"))
    mappings = []
    st.markdown("#### Explicit mappings")
    for i in range(mapping_count):
        c1,c2,c3 = st.columns([1.2,1,1.2])
        source = c1.selectbox("Source column", columns, key=f"pl_couple_src_{profile}_{i}")
        reducer = c2.selectbox("Reducer", list(REDUCERS), key=f"pl_couple_red_{profile}_{i}")
        target = c3.selectbox("Target parameter", param_names, index=min(i, len(param_names)-1), key=f"pl_couple_tgt_{profile}_{i}")
        row_index = 0
        if reducer == "row":
            row_index = int(st.number_input("Finite-value row index", value=0, step=1, key=f"pl_couple_row_{profile}_{i}"))
        source_default = str((dataset.get("units") or {}).get(source) or "")
        u1,u2,a,b = st.columns(4)
        source_unit = u1.text_input("Source unit", value=source_default, key=f"pl_couple_su_{profile}_{i}")
        target_unit = u2.text_input("Target unit", value=source_default, key=f"pl_couple_tu_{profile}_{i}")
        scale = float(a.number_input("Scale a", value=1.0, key=f"pl_couple_scale_{profile}_{i}"))
        offset = float(b.number_input("Offset b", value=0.0, key=f"pl_couple_offset_{profile}_{i}"))
        # Blank both fields means no unit conversion.
        if not source_unit and not target_unit:
            pass
        elif bool(source_unit) != bool(target_unit):
            st.warning(f"Mapping {i+1}: specify both source and target unit, or leave both blank.")
        mappings.append({
            "source_column": source,
            "reducer": reducer,
            "row_index": row_index,
            "source_unit": source_unit,
            "target_unit": target_unit,
            "scale": scale,
            "offset": offset,
            "target_parameter": target,
        })

    if st.button("Build parameter packet", type="primary", key=f"pl_couple_build_{profile}"):
        st.session_state[f"pl_couple_packet_{profile}"] = build_parameter_packet(
            dataset, adapter_id=adapter_id, target_profile=target_profile, mappings=mappings
        )
    packet = st.session_state.get(f"pl_couple_packet_{profile}")
    if packet:
        st.markdown("#### Parameter packet preview")
        st.dataframe([
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
        ], hide_index=True, width="stretch")
        st.json({"target_adapter": packet.get("target_adapter"), "target_profile": packet.get("target_profile"), "parameters": packet.get("parameters"), "packet_sha256": packet.get("packet_sha256")})
        st.caption(packet.get("boundary", ""))
        c1,c2 = st.columns(2)
        pipeline_name = c1.text_input("Pipeline name", value=f"{dataset.get('name')} → {labels.get(packet.get('target_adapter'), packet.get('target_adapter'))}", key=f"pl_couple_name_{profile}")
        notes = c2.text_input("Pipeline notes", value="", key=f"pl_couple_notes_{profile}")
        a,b = st.columns(2)
        if a.button("Save coupling pipeline", key=f"pl_couple_save_{profile}"):
            rec = save_pipeline(project_path, name=pipeline_name, packet=packet, notes=notes)
            st.success(f"Saved {rec['pipeline_id']} · sha256 {rec['sha256'][:12]}…")
            st.rerun()
        if b.button("Queue & start downstream model", key=f"pl_couple_run_{profile}"):
            job = queue_packet(packet)
            start_sweep_job(job["id"])
            st.session_state[f"pl_orch_active_job_{packet['target_profile']}"] = job["id"]
            st.success(f"Started downstream sweep job {job['id']} for {packet['target_profile']}.")

    pipelines = list_pipelines(project_path)
    if pipelines:
        st.markdown("#### Saved coupling provenance")
        st.dataframe([
            {
                "pipeline_id": p.get("pipeline_id"),
                "name": p.get("name"),
                "source_dataset": (p.get("packet") or {}).get("source_dataset_id"),
                "target": (p.get("packet") or {}).get("target_adapter"),
                "target_profile": (p.get("packet") or {}).get("target_profile"),
                "sha256": str(p.get("sha256") or "")[:16],
            }
            for p in pipelines
        ], hide_index=True, width="stretch")
