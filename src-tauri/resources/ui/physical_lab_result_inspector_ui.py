"""Unified Result Inspector / Materializer UI for Physical Lab projects."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_ui_semantics import render_context_header, render_object_card, render_status_card
from physical_lab_environment_manifest import build_environment_manifest, list_environment_manifests, save_environment_manifest
from physical_lab_result_contracts import annotate_inventory, find_uncertainty_objects, validate_contract_inventory
from physical_lab_result_inspector import (
    inspect_result,
    list_materializations,
    load_project_result,
    load_sweep_point,
    materialize_result,
    numerical_sanity_report,
)


RESULT_WORKSPACES = ["Inspect Result", "Materialize Dataset", "Environment"]


def _source_selector(st: Any, project_path: Path, profile: str):
    doc = projects.open_project(project_path)
    project_results = dict(doc.get("results") or {})
    from physical_lab_sweep_executor import list_sweep_jobs, read_sweep_result
    sweep_jobs = [j for j in list_sweep_jobs(limit=100) if j.get("status") == "succeeded"]
    choices = []
    if project_results:
        choices.append("Project compute result")
    if sweep_jobs:
        choices.append("Sweep campaign point")
    if not choices:
        st.info("No completed project compute result or sweep result is available yet.")
        return None
    source_kind = st.radio("Result source", choices, horizontal=True, key=f"pl_result_source_kind_{profile}")
    if source_kind == "Project compute result":
        job_ids = list(project_results)
        job_id = st.selectbox("Project job", job_ids, key=f"pl_result_project_job_{profile}")
        result, identity = load_project_result(project_path, job_id)
        return result, identity

    job_ids = [str(j["id"]) for j in sweep_jobs]
    job_id = st.selectbox("Sweep job", job_ids, key=f"pl_result_sweep_job_{profile}")
    result = read_sweep_result(job_id) or {}
    points = list(result.get("points") or [])
    valid = [i for i,p in enumerate(points) if isinstance(p,dict) and p.get("status") == "succeeded" and isinstance(p.get("result"),dict)]
    if not valid:
        st.warning("Selected sweep has no successful point with a full result payload.")
        return None
    point_index = st.selectbox(
        "Sweep point", valid,
        format_func=lambda i: f"point {i} · design_index={points[i].get('design_index')} · cached={points[i].get('cached')}",
        key=f"pl_result_sweep_point_{profile}",
    )
    payload, identity = load_sweep_point(job_id, int(point_index))
    return payload, identity


def _build_inspection(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    inspection = inspect_result(result)
    contract = annotate_inventory(result.get("schema"), inspection["inventory"])
    conformance = validate_contract_inventory(result.get("schema"), inspection["inventory"])
    inspection = {**inspection, "inventory": contract["inventory"], "contract": contract, "contract_conformance": conformance}
    sanity = numerical_sanity_report(result)
    explicit_uncertainty = find_uncertainty_objects(result)
    return inspection, sanity, explicit_uncertainty


def _schema_parent(path: str) -> str | None:
    text = str(path or "").strip()
    if not text or text == "$":
        return None
    if text.endswith("]"):
        bracket = text.rfind("[")
        if bracket > 0:
            return text[:bracket] or "$"
    dot = text.rfind(".")
    if dot > 0:
        return text[:dot]
    return "$"


def _schema_label(path: str) -> str:
    text = str(path or "")
    if text == "$":
        return "$"
    if text.endswith("]"):
        bracket = text.rfind("[")
        if bracket >= 0:
            return text[bracket:]
    return text.rsplit(".", 1)[-1]


def _schema_tree_layout(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build deterministic structural tree metadata from the existing inventory only."""
    rows: list[dict[str, Any]] = []
    for order, item in enumerate(inventory):
        path = str(item.get("path") or "")
        if not path:
            continue
        parent = _schema_parent(path)
        depth = 0
        cursor = parent
        seen: set[str] = set()
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            depth += 1
            cursor = _schema_parent(cursor)
        rows.append(
            {
                "path": path,
                "parent": parent,
                "depth": depth,
                "order": order,
                "label": _schema_label(path),
                "kind": item.get("kind"),
                "role": item.get("role"),
                "unit": item.get("unit"),
                "shape": item.get("shape"),
            }
        )
    return rows


def _render_schema_tree(st: Any, inventory: list[dict[str, Any]], profile: str) -> None:
    st.markdown("#### Schema map")
    layout = _schema_tree_layout(inventory)
    if not layout:
        st.info("No structural inventory is available for a schema map.")
        return

    # Preserve inventory order vertically and use structural depth horizontally.
    positions = {row["path"]: (float(row["depth"]), float(-idx)) for idx, row in enumerate(layout)}
    fig = go.Figure()
    for row in layout:
        parent = row["parent"]
        if parent not in positions:
            continue
        x0, y0 = positions[parent]
        x1, y1 = positions[row["path"]]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                hoverinfo="skip",
                showlegend=False,
            )
        )

    x_values = []
    y_values = []
    labels = []
    hover = []
    for row in layout:
        x, y = positions[row["path"]]
        x_values.append(x)
        y_values.append(y)
        labels.append(row["label"])
        hover.append(
            "<br>".join(
                [
                    f"Path: {row['path']}",
                    f"Kind: {row.get('kind') or 'unspecified'}",
                    f"Role: {row.get('role') or 'unclassified'}",
                    f"Unit: {row.get('unit') or 'unspecified'}",
                    f"Shape: {row.get('shape') if row.get('shape') is not None else 'unspecified'}",
                ]
            )
        )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers+text",
            text=labels,
            textposition="middle right",
            hovertext=hover,
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=max(380, min(920, 150 + 28 * len(layout))),
        xaxis={"title": "Structural depth", "dtick": 1, "zeroline": False},
        yaxis={"visible": False},
        margin={"l": 25, "r": 170, "t": 20, "b": 45},
        hovermode="closest",
    )
    st.plotly_chart(fig, width="stretch", key=f"pl_result_schema_map_{profile}")
    st.caption(
        "Structural view of the existing result inventory. Paths, roles, units and shapes are displayed only when already present; "
        "unregistered scientific meaning is not inferred."
    )


def _identity_summary(identity: dict[str, Any]) -> tuple[str, str]:
    preferred = (
        "job_id",
        "sweep_job_id",
        "result_id",
        "dataset_id",
        "point_index",
        "design_index",
        "id",
    )
    parts = []
    for key in preferred:
        if key in identity and identity.get(key) is not None:
            parts.append(f"{key}={identity.get(key)}")
    if not parts:
        for key in sorted(identity)[:4]:
            value = identity.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                parts.append(f"{key}={value}")
    label = parts[0] if parts else "source identity"
    detail = "<br>".join(parts) if parts else "No compact scalar identity fields available"
    return label, detail


def _render_provenance_chain(st: Any, identity: dict[str, Any], inspection: dict[str, Any], profile: str) -> None:
    st.markdown("#### Provenance chain")
    source_label, source_detail = _identity_summary(identity)
    contract = inspection.get("contract") or {}
    conformance = inspection.get("contract_conformance") or {}
    nodes = [
        {
            "label": "Source",
            "detail": source_detail,
            "subtitle": source_label,
        },
        {
            "label": "Persisted result",
            "detail": f"sha256={inspection.get('result_sha256') or 'unavailable'}",
            "subtitle": f"fields={inspection.get('field_count', '—')}",
        },
        {
            "label": "Contract inspection",
            "detail": (
                f"registered={bool(contract.get('registered'))}<br>"
                f"conformance={conformance.get('status') or 'UNSPECIFIED'}"
            ),
            "subtitle": str(conformance.get("status") or "UNSPECIFIED"),
        },
        {
            "label": "Inspector view",
            "detail": "read-only representation of persisted result evidence",
            "subtitle": "READ-ONLY",
        },
    ]

    fig = go.Figure()
    for idx in range(len(nodes) - 1):
        fig.add_trace(
            go.Scatter(
                x=[idx, idx + 1],
                y=[0, 0],
                mode="lines",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=list(range(len(nodes))),
            y=[0] * len(nodes),
            mode="markers+text",
            text=[f"{node['label']}<br>{node['subtitle']}" for node in nodes],
            textposition="top center",
            hovertext=[node["detail"] for node in nodes],
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=270,
        xaxis={"visible": False, "range": [-0.25, len(nodes) - 0.75]},
        yaxis={"visible": False, "range": [-0.5, 0.6]},
        margin={"l": 25, "r": 25, "t": 65, "b": 20},
        hovermode="closest",
    )
    st.plotly_chart(fig, width="stretch", key=f"pl_result_provenance_chain_{profile}")
    st.caption(
        "Read-only lineage view built from the persisted source identity, result hash, and contract inspection already available to Result Inspector. "
        "It does not modify the result or certify correctness, validation, independence, or provenance completeness."
    )


def _render_inspection(st: Any, result: dict[str,Any], identity: dict[str,Any], profile: str, prepared: tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]] | None = None) -> tuple[dict[str,Any],dict[str,Any]]:
    inspection, sanity, explicit_uncertainty = prepared or _build_inspection(result)
    contract = inspection["contract"]
    conformance = inspection["contract_conformance"]

    a,b,c,d,e = st.columns(5)
    a.metric("Result schema", str(result.get("schema") or "untyped"))
    b.metric("Fields", inspection["field_count"])
    c.metric("Sanity", sanity["status"])
    d.metric("Contract", conformance["status"])
    e.metric("Result sha256", inspection["result_sha256"][:12]+"…")
    st.caption("Numerical sanity, schema conformance, uncertainty reporting and physical validation are separate evidence layers.")

    if sanity["status"] == "FAIL":
        st.error("Numerical sanity checks found at least one hard inconsistency.")
    elif sanity["status"] == "REVIEW":
        st.warning("Numerical sanity checks found one or more items that should be reviewed.")
    else:
        st.success("No configured numerical/structural sanity inconsistency was detected.")
    if sanity["checks"]:
        with st.expander("Numerical sanity checks", expanded=(sanity["status"] != "PASS")):
            st.dataframe(sanity["checks"], hide_index=True, width="stretch")

    _render_schema_tree(st, inspection["inventory"], profile)
    _render_provenance_chain(st, identity, inspection, profile)

    with st.expander("Result schema contract", expanded=(conformance["status"] != "PASS")):
        if contract["registered"]:
            st.success(f"Registered contract · matched {contract['matched_fields']} explicit field definition(s).")
            if conformance["issues"]:
                st.dataframe(conformance["issues"], hide_index=True, width="stretch")
            with st.expander("Contract metadata", expanded=False):
                st.json(contract["contract"])
        else:
            st.info("This result schema is not registered. Structural inspection remains available, but quantity/unit/shape metadata will not be guessed.")

    st.markdown("#### Unified field inventory")
    all_roles = sorted({str(r.get("role") or "unclassified") for r in inspection["inventory"]})
    default_roles = [x for x in all_roles if x not in {"scientific-boundary"}]
    role_filter = st.multiselect("Field roles", all_roles, default=default_roles, key=f"pl_result_roles_{profile}")
    rows = [r for r in inspection["inventory"] if r.get("role") in role_filter]
    st.dataframe(rows[:500], hide_index=True, width="stretch")

    with st.expander("Explicit uncertainty objects", expanded=False):
        if explicit_uncertainty:
            st.dataframe([
                {
                    "path": row["path"],
                    "valid": row["validation"]["valid"],
                    "estimate": row["value"].get("estimate"),
                    "standard_uncertainty": row["value"].get("standard_uncertainty"),
                    "coverage_factor": row["value"].get("coverage_factor"),
                    "coverage_probability": row["value"].get("coverage_probability"),
                    "method": row["value"].get("method"),
                    "unit": row["value"].get("unit"),
                }
                for row in explicit_uncertainty
            ], hide_index=True, width="stretch")
        else:
            st.caption("No explicit Physical Lab uncertainty object is embedded in this result. Error/residual fields are not treated as uncertainty by default.")

    with st.expander("Source identity / provenance seed", expanded=False):
        st.json(identity)
    st.caption(contract["boundary"])
    return inspection, sanity


def _render_materializer(st: Any, project_path: Path, result: dict[str,Any], identity: dict[str,Any], inspection: dict[str,Any], profile: str) -> None:
    st.markdown("#### Result Extractor / Materializer")
    st.caption("Select explicit numeric fields and extraction rules. Result → dataset derivation is stored as a separate provenance activity; no physical meaning or uncertainty semantics are inferred automatically.")
    numeric = [r for r in inspection["inventory"] if r.get("kind") in {"scalar","vector","matrix"} and r.get("path") != "$"]
    paths = [str(r["path"]) for r in numeric]
    selected = st.multiselect("Fields to materialize", paths, default=paths[:min(2,len(paths))], max_selections=8, key=f"pl_result_extract_paths_{profile}")
    rules=[]; lookup={str(r["path"]):r for r in numeric}
    for i,path in enumerate(selected):
        info=lookup[path]; kind=str(info.get("kind"))
        reducers=["series","mean","min","max","first","last","index"] if kind=="vector" else (["mean","min","max","first","last","index"] if kind=="matrix" else ["series","mean","first","last"])
        with st.container(border=True):
            st.caption(path)
            c1,c2,c3=st.columns([1.0,1.5,1.0])
            reducer=c1.selectbox("Reducer",reducers,key=f"pl_result_reduce_{profile}_{i}")
            default_name=path.split(".")[-1].replace(" ","_")
            column=c2.text_input("Dataset column",value=default_name,key=f"pl_result_col_{profile}_{i}")
            contract_unit=str(info.get("unit") or "")
            unit=c3.text_input("Unit",value=contract_unit,key=f"pl_result_unit_{profile}_{i}")
            index=0
            if reducer=="index": index=int(st.number_input("Index",value=0,step=1,key=f"pl_result_index_{profile}_{i}"))
            rules.append({"path":path,"reducer":reducer,"column_name":column,"unit":unit,"index":index})
    c1,c2=st.columns(2)
    name=c1.text_input("Materialized dataset name",value=f"{profile}-result",key=f"pl_result_materialize_name_{profile}")
    notes=c2.text_input("Materialization notes",value="",key=f"pl_result_materialize_notes_{profile}")
    if st.button("Materialize selected result fields",type="primary",disabled=not rules,key=f"pl_result_materialize_{profile}"):
        out=materialize_result(project_path,result=result,source_identity=identity,name=name,profile=profile,rules=rules,notes=notes)
        st.success(f"Created {out['dataset']['dataset_id']} · materialization {out['provenance']['materialization_id']} · dataset sha256 {out['dataset']['sha256'][:12]}…")
        st.rerun()

    mats=list_materializations(project_path)
    if mats:
        with st.expander("Materialization provenance", expanded=False):
            st.dataframe([
                {"id":m.get("materialization_id"),"source":(m.get("source_entity") or {}).get("id"),"dataset":(m.get("generated_entity") or {}).get("id"),"rules":len((m.get("activity") or {}).get("rules") or []),"sha256":str(m.get("sha256") or "")[:16]}
                for m in mats[:100]
            ],hide_index=True,width="stretch")


def _render_environment(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Software / Environment Manifest")
    current = build_environment_manifest(extra={"active_profile": profile})
    a,b,c = st.columns(3)
    a.metric("Python", str((current.get("python") or {}).get("version") or "—"))
    b.metric("Source commit", str((current.get("physical_lab") or {}).get("source_commit") or "unavailable")[:14])
    c.metric("Environment sha256", current["environment_sha256"][:12]+"…")
    with st.expander("Current environment details", expanded=False): st.json(current)
    if st.button("Save environment snapshot to project", key=f"pl_env_save_{profile}"):
        rec=save_environment_manifest(project_path,extra={"active_profile":profile})
        st.success(f"Saved environment {rec['environment_sha256'][:16]}…")
        st.rerun()
    rows=list_environment_manifests(project_path)
    if rows:
        st.dataframe([
            {"captured_at":r.get("captured_at"),"sha256":str(r.get("environment_sha256") or "")[:16],"python":(r.get("python") or {}).get("version"),"source_commit":(r.get("physical_lab") or {}).get("source_commit"),"solver_backend":(r.get("physical_lab") or {}).get("solver_backend")}
            for r in rows[:50]
        ],hide_index=True,width="stretch")
    st.caption(current["boundary"])


def render_result_inspector(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open a Physical Lab project to inspect and materialize persisted results.")
        return
    project_path=Path(active)
    st.markdown("### Result Inspector")
    st.caption("Inspect a result first, materialize selected fields only when needed, or capture the software environment separately.")
    workspace = st.radio(
        "Result workflow",
        RESULT_WORKSPACES,
        horizontal=True,
        key=f"pl_result_workspace_{profile}",
    )

    if workspace == "Environment":
        _render_environment(st,project_path,profile)
        return

    selected=_source_selector(st,project_path,profile)
    if not selected:
        return
    result,identity=selected
    prepared = _build_inspection(result)
    inspection, sanity, _uncertainty = prepared

    source_name = str(identity.get("job_id") or identity.get("sweep_job_id") or identity.get("result_id") or "persisted result")
    render_context_header(
        st,
        project=project_path.stem,
        workspace="Result Inspector",
        task=workspace,
        source=source_name,
    )
    if workspace == "Inspect Result":
        render_object_card(
            st,
            object_type="RESULT",
            title=source_name,
            metadata={
                "schema": result.get("schema") or "untyped",
                "fields": inspection.get("field_count"),
                "sha256": inspection.get("result_sha256"),
            },
        )
        conformance_status = str((inspection.get("contract_conformance") or {}).get("status") or "NOT ESTABLISHED")
        provenance_state = "RECORDED" if identity and inspection.get("result_sha256") else ("PARTIAL" if identity or inspection.get("result_sha256") else "UNSPECIFIED")
        render_status_card(
            st,
            validation=conformance_status,
            scientific="NOT ESTABLISHED",
            provenance=provenance_state,
            execution=str(identity.get("status") or "NOT APPLICABLE"),
        )

    a,b,c = st.columns(3)
    a.metric("Selected schema", str(result.get("schema") or "untyped"))
    b.metric("Fields", inspection["field_count"])
    c.metric("Sanity", sanity["status"])

    if workspace == "Inspect Result":
        _render_inspection(st,result,identity,profile,prepared=prepared)
        return

    st.info("Materialization creates a new derived dataset and provenance record; it does not modify the source result.")
    _render_materializer(st,project_path,result,identity,inspection,profile)
