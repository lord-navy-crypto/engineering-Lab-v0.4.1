"""UI for Physical Lab saved-pipeline DAG construction and execution."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_model_coupling import list_pipelines
from physical_lab_pipeline_graph import (
    advance_workflow_run,
    build_workflow,
    create_workflow_run,
    list_workflow_runs,
    list_workflows,
    save_workflow,
    topological_order,
)


def _pipeline_label(p: dict[str, Any]) -> str:
    packet = p.get("packet") or {}
    return f"{p.get('name')} · {packet.get('target_adapter')} · {str(p.get('pipeline_id'))[-8:]}"


def render_pipeline_graph(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open a Physical Lab project first."); return
    path = Path(active)
    pipelines = list_pipelines(path)
    if not pipelines:
        st.info("Save at least one Model Coupling pipeline before building a workflow graph."); return

    st.markdown("#### Pipeline Graph / DAG")
    st.caption("Compose saved coupling pipelines into an acyclic dependency graph. Edges control execution readiness; each node retains its own explicit dataset-to-parameter mapping.")
    by_id = {str(p["pipeline_id"]): p for p in pipelines}
    ids = list(by_id)
    selected = st.multiselect(
        "Workflow nodes",
        ids,
        default=ids[:min(3,len(ids))],
        format_func=lambda x: _pipeline_label(by_id[x]),
        key=f"pl_dag_nodes_{profile}",
    )
    if not selected:
        return

    st.markdown("##### Dependencies")
    max_edges = min(8, max(1, len(selected)*(len(selected)-1)//2))
    edge_count = int(st.number_input("Edge count", min_value=0, max_value=max_edges, value=min(max(0,len(selected)-1),max_edges), step=1, key=f"pl_dag_edge_count_{profile}"))
    edges=[]
    for i in range(edge_count):
        c1,c2=st.columns(2)
        source=c1.selectbox(f"Edge {i+1} source",selected,index=min(i,len(selected)-1),format_func=lambda x:_pipeline_label(by_id[x]),key=f"pl_dag_src_{profile}_{i}")
        target_options=[x for x in selected if x!=source]
        target=c2.selectbox(f"Edge {i+1} target",target_options,index=min(i,len(target_options)-1),format_func=lambda x:_pipeline_label(by_id[x]),key=f"pl_dag_dst_{profile}_{i}")
        edges.append([source,target])

    try:
        order=topological_order(selected,edges)
        st.success("Acyclic graph · topological order valid")
        st.dataframe([
            {"order":i+1,"pipeline_id":node,"pipeline":by_id[node].get("name"),"target_adapter":(by_id[node].get("packet") or {}).get("target_adapter")}
            for i,node in enumerate(order)
        ],hide_index=True,width="stretch")
    except Exception as exc:
        st.error(f"Invalid graph: {exc}"); return

    c1,c2=st.columns(2)
    name=c1.text_input("Workflow name",value="Coupled model workflow",key=f"pl_dag_name_{profile}")
    notes=c2.text_input("Workflow notes",value="",key=f"pl_dag_notes_{profile}")
    if st.button("Save workflow graph",type="primary",key=f"pl_dag_save_{profile}"):
        wf=build_workflow(path,name=name,pipeline_ids=selected,edges=edges,notes=notes)
        rec=save_workflow(path,wf)
        st.success(f"Saved {rec['workflow_id']} · {rec['workflow_sha256'][:12]}…")
        st.rerun()

    workflows=list_workflows(path)
    if not workflows:
        return
    st.markdown("##### Saved workflows")
    wf_ids=[str(w["workflow_id"]) for w in workflows]
    chosen=st.selectbox("Workflow",wf_ids,format_func=lambda x:next(w.get("name") for w in workflows if w["workflow_id"]==x),key=f"pl_dag_workflow_{profile}")
    wf=next(w for w in workflows if w["workflow_id"]==chosen)
    st.caption(f"{len(wf.get('nodes') or [])} nodes · {len(wf.get('edges') or [])} edges · sha256 {str(wf.get('workflow_sha256'))[:16]}…")

    a,b=st.columns(2)
    if a.button("Create & start workflow run",type="primary",key=f"pl_dag_run_{profile}"):
        run=create_workflow_run(path,wf)
        run=advance_workflow_run(path,wf,str(run["run_id"]),auto_start=True)
        st.session_state[f"pl_dag_active_run_{profile}"]=run["run_id"]
        st.rerun()
    if b.button("Refresh / advance workflow",key=f"pl_dag_refresh_{profile}"):
        st.rerun()

    runs=list_workflow_runs(path,workflow_id=chosen)
    if not runs:
        return
    run_ids=[str(r["run_id"]) for r in runs]
    active_run=st.session_state.get(f"pl_dag_active_run_{profile}")
    idx=run_ids.index(active_run) if active_run in run_ids else 0
    run_id=st.selectbox("Workflow run",run_ids,index=idx,key=f"pl_dag_run_pick_{profile}")
    run=advance_workflow_run(path,wf,run_id,auto_start=True)
    st.metric("Workflow status",str(run.get("status") or "—"))
    rows=[]
    for position,node_id in enumerate(wf.get("topological_order") or []):
        state=(run.get("nodes") or {}).get(node_id) or {}
        p=by_id.get(node_id,{})
        rows.append({
            "order":position+1,
            "pipeline":p.get("name") or node_id,
            "status":state.get("status"),
            "job_id":state.get("job_id"),
            "error":state.get("error"),
        })
    st.dataframe(rows,hide_index=True,width="stretch")
    st.caption(str(run.get("boundary") or wf.get("boundary") or ""))
