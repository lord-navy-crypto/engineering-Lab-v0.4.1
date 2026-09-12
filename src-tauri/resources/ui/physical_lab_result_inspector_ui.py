"""Unified Result Inspector / Materializer UI for Physical Lab projects."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
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


def _render_inspection(st: Any, result: dict[str,Any], identity: dict[str,Any], profile: str) -> tuple[dict[str,Any],dict[str,Any]]:
    inspection = inspect_result(result)
    contract = annotate_inventory(result.get("schema"), inspection["inventory"])
    conformance = validate_contract_inventory(result.get("schema"), inspection["inventory"])
    inspection = {**inspection, "inventory": contract["inventory"], "contract": contract, "contract_conformance": conformance}
    sanity = numerical_sanity_report(result)
    explicit_uncertainty = find_uncertainty_objects(result)

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
        st.dataframe(sanity["checks"], hide_index=True, width="stretch")

    st.markdown("#### Result schema contract")
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

    st.markdown("#### Explicit uncertainty objects")
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
        c1,c2,c3,c4=st.columns([2.2,1.2,1.5,1.0])
        c1.caption(path)
        reducer=c2.selectbox("Reducer",reducers,key=f"pl_result_reduce_{profile}_{i}")
        default_name=path.split(".")[-1].replace(" ","_")
        column=c3.text_input("Dataset column",value=default_name,key=f"pl_result_col_{profile}_{i}")
        contract_unit=str(info.get("unit") or "")
        unit=c4.text_input("Unit",value=contract_unit,key=f"pl_result_unit_{profile}_{i}")
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
        st.markdown("#### Materialization provenance")
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
    selected=_source_selector(st,project_path,profile)
    if selected:
        result,identity=selected
        inspection,_sanity=_render_inspection(st,result,identity,profile)
        _render_materializer(st,project_path,result,identity,inspection,profile)
    _render_environment(st,project_path,profile)
