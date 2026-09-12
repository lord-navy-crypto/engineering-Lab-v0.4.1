"""Unified Result Inspector / Materializer UI for Physical Lab projects."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
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
        "Sweep point",
        valid,
        format_func=lambda i: f"point {i} · design_index={points[i].get('design_index')} · cached={points[i].get('cached')}",
        key=f"pl_result_sweep_point_{profile}",
    )
    payload, identity = load_sweep_point(job_id, int(point_index))
    return payload, identity


def _render_inspection(st: Any, result: dict[str,Any], identity: dict[str,Any], profile: str) -> tuple[dict[str,Any],dict[str,Any]]:
    inspection = inspect_result(result)
    sanity = numerical_sanity_report(result)
    a,b,c,d = st.columns(4)
    a.metric("Result schema", str(result.get("schema") or "untyped"))
    b.metric("Fields", inspection["field_count"])
    c.metric("Sanity", sanity["status"])
    d.metric("Result sha256", inspection["result_sha256"][:12]+"…")
    st.caption("Sanity is numerical/structural only. It is deliberately separate from model validation, experimental validation and uncertainty coverage.")

    if sanity["status"] == "FAIL":
        st.error("Numerical sanity checks found at least one hard inconsistency.")
    elif sanity["status"] == "REVIEW":
        st.warning("Numerical sanity checks found one or more items that should be reviewed.")
    else:
        st.success("No configured numerical/structural sanity inconsistency was detected.")
    if sanity["checks"]:
        st.dataframe(sanity["checks"], hide_index=True, width="stretch")

    st.markdown("#### Unified field inventory")
    role_filter = st.multiselect(
        "Field roles",
        ["observable","uncertainty","numerical-quality","scientific-boundary"],
        default=["observable","uncertainty","numerical-quality"],
        key=f"pl_result_roles_{profile}",
    )
    rows = [r for r in inspection["inventory"] if r.get("role") in role_filter]
    st.dataframe(rows[:500], hide_index=True, width="stretch")
    with st.expander("Source identity / provenance seed", expanded=False):
        st.json(identity)
    st.caption(inspection["boundary"])
    return inspection, sanity


def _render_materializer(st: Any, project_path: Path, result: dict[str,Any], identity: dict[str,Any], inspection: dict[str,Any], profile: str) -> None:
    st.markdown("#### Result Extractor / Materializer")
    st.caption(
        "Select explicit numeric fields and extraction rules. Result → dataset derivation is stored as a separate provenance activity; no physical meaning or uncertainty semantics are inferred automatically."
    )
    numeric = [r for r in inspection["inventory"] if r.get("kind") in {"scalar","vector","matrix"} and r.get("path") != "$"]
    paths = [str(r["path"]) for r in numeric]
    selected = st.multiselect("Fields to materialize", paths, default=paths[:min(2,len(paths))], max_selections=8, key=f"pl_result_extract_paths_{profile}")
    rules=[]
    lookup={str(r["path"]):r for r in numeric}
    for i,path in enumerate(selected):
        info=lookup[path]; kind=str(info.get("kind"))
        reducers=["series","mean","min","max","first","last","index"] if kind=="vector" else (["mean","min","max","first","last","index"] if kind=="matrix" else ["series","mean","first","last"])
        c1,c2,c3,c4=st.columns([2.2,1.2,1.5,1.0])
        c1.caption(path)
        reducer=c2.selectbox("Reducer",reducers,key=f"pl_result_reduce_{profile}_{i}")
        default_name=path.split(".")[-1].replace(" ","_")
        column=c3.text_input("Dataset column",value=default_name,key=f"pl_result_col_{profile}_{i}")
        unit=c4.text_input("Unit",value="",key=f"pl_result_unit_{profile}_{i}")
        index=0
        if reducer=="index":
            index=int(st.number_input("Index",value=0,step=1,key=f"pl_result_index_{profile}_{i}"))
        rules.append({"path":path,"reducer":reducer,"column_name":column,"unit":unit,"index":index})
    c1,c2=st.columns(2)
    name=c1.text_input("Materialized dataset name",value=f"{profile}-result",key=f"pl_result_materialize_name_{profile}")
    notes=c2.text_input("Materialization notes",value="",key=f"pl_result_materialize_notes_{profile}")
    if st.button("Materialize selected result fields",type="primary",disabled=not rules,key=f"pl_result_materialize_{profile}"):
        out=materialize_result(project_path,result=result,source_identity=identity,name=name,profile=profile,rules=rules,notes=notes)
        st.success(
            f"Created {out['dataset']['dataset_id']} · materialization {out['provenance']['materialization_id']} · dataset sha256 {out['dataset']['sha256'][:12]}…"
        )
        st.rerun()

    mats=list_materializations(project_path)
    if mats:
        st.markdown("#### Materialization provenance")
        st.dataframe([
            {
                "id":m.get("materialization_id"),
                "source":(m.get("source_entity") or {}).get("id"),
                "dataset":(m.get("generated_entity") or {}).get("id"),
                "rules":len((m.get("activity") or {}).get("rules") or []),
                "sha256":str(m.get("sha256") or "")[:16],
            }
            for m in mats[:100]
        ],hide_index=True,width="stretch")


def render_result_inspector(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open a Physical Lab project to inspect and materialize persisted results.")
        return
    project_path=Path(active)
    selected=_source_selector(st,project_path,profile)
    if not selected:
        return
    result,identity=selected
    inspection,_sanity=_render_inspection(st,result,identity,profile)
    _render_materializer(st,project_path,result,identity,inspection,profile)
