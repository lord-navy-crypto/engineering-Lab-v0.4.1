"""Executable acyclic workflow graphs for saved Physical Lab coupling pipelines.

A workflow graph references already-saved, fingerprinted coupling pipelines. It adds
explicit dependencies, deterministic topological ordering, persistent workflow-run
state and readiness-based dispatch through the allow-listed Sweep Executor.

The graph never invents mappings or arbitrary code. Downstream nodes use the packet
stored in their saved coupling pipeline. Therefore an edge expresses execution and
provenance dependency; it does not automatically reinterpret an upstream result as a
new downstream dataset.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now
from physical_lab_model_coupling import PACKET_SCHEMA, list_pipelines, queue_packet
from physical_lab_sweep_executor import read_sweep_job, start_sweep_job

WORKFLOW_SCHEMA = "physical-lab-pipeline-workflow-v1"
RUN_SCHEMA = "physical-lab-pipeline-workflow-run-v1"
MAX_NODES = 32
MAX_EDGES = 128
TERMINAL = {"succeeded", "failed", "cancelled", "blocked"}


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _workflow_dir(project_dir: Path) -> Path:
    p = project_dir / "workflows"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run_dir(project_dir: Path) -> Path:
    p = _workflow_dir(project_dir) / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(plain(dict(value)), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _pipeline_index(project_dir: Path) -> dict[str, dict[str, Any]]:
    return {str(row["pipeline_id"]): row for row in list_pipelines(project_dir)}


def _normalized_edges(nodes: Sequence[str], edges: Sequence[Sequence[str]]) -> list[tuple[str, str]]:
    node_set = set(nodes)
    out: list[tuple[str, str]] = []
    seen = set()
    for raw in edges:
        if len(raw) != 2:
            raise ValueError("each workflow edge must have [source, target]")
        source, target = str(raw[0]), str(raw[1])
        if source == target:
            raise ValueError("workflow self-cycles are not allowed")
        if source not in node_set or target not in node_set:
            raise ValueError("workflow edge references an unknown node")
        pair = (source, target)
        if pair not in seen:
            seen.add(pair); out.append(pair)
    if len(out) > MAX_EDGES:
        raise ValueError(f"workflow exceeds {MAX_EDGES} edges")
    return sorted(out)


def topological_order(nodes: Sequence[str], edges: Sequence[Sequence[str]]) -> list[str]:
    ordered_nodes = [str(x) for x in nodes]
    if not ordered_nodes or len(ordered_nodes) > MAX_NODES or len(set(ordered_nodes)) != len(ordered_nodes):
        raise ValueError(f"workflow requires 1..{MAX_NODES} unique nodes")
    normalized = _normalized_edges(ordered_nodes, edges)
    indegree = {node: 0 for node in ordered_nodes}
    children = {node: [] for node in ordered_nodes}
    for source, target in normalized:
        indegree[target] += 1; children[source].append(target)
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    result: list[str] = []
    while ready:
        node = ready.pop(0); result.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child); ready.sort()
    if len(result) != len(ordered_nodes):
        raise ValueError("workflow contains a cycle")
    return result


def build_workflow(project_dir: str | Path, *, name: str, pipeline_ids: Sequence[str], edges: Sequence[Sequence[str]], notes: str = "") -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    ids = [str(x) for x in pipeline_ids]
    index = _pipeline_index(path)
    missing = [x for x in ids if x not in index]
    if missing:
        raise ValueError("workflow references missing saved pipeline(s): " + ", ".join(missing))
    normalized = _normalized_edges(ids, edges)
    order = topological_order(ids, normalized)
    node_rows = []
    for node_id in order:
        pipeline = index[node_id]
        packet = pipeline.get("packet") or {}
        node_rows.append({
            "node_id": node_id,
            "pipeline_sha256": pipeline.get("sha256"),
            "source_dataset_id": packet.get("source_dataset_id"),
            "source_dataset_sha256": packet.get("source_dataset_sha256"),
            "target_adapter": packet.get("target_adapter"),
            "target_profile": packet.get("target_profile"),
            "packet_sha256": packet.get("packet_sha256"),
        })
    stable = {
        "schema": WORKFLOW_SCHEMA,
        "project_id": project.get("project_id"),
        "name": str(name).strip() or "Pipeline workflow",
        "nodes": node_rows,
        "edges": [[a, b] for a, b in normalized],
        "topological_order": order,
        "notes": str(notes),
    }
    return {
        **stable,
        "workflow_sha256": _sha(stable),
        "boundary": "Acyclic execution/provenance dependencies between saved coupling pipelines. Edges do not automatically convert an upstream result into a downstream dataset; each saved node keeps its own explicit source dataset and mapping.",
    }


def save_workflow(project_dir: str | Path, workflow: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    if workflow.get("schema") != WORKFLOW_SCHEMA:
        raise ValueError("not a Physical Lab pipeline workflow")
    digest = str(workflow.get("workflow_sha256") or _sha({k:v for k,v in workflow.items() if k not in {"workflow_sha256","boundary"}}))
    record = {**plain(dict(workflow)), "workflow_id": f"workflow-{digest[:20]}", "created_at": utc_now()}
    _atomic_json(_workflow_dir(path) / f"{record['workflow_id']}.json", record)
    return record


def list_workflows(project_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    rows = []
    for file in sorted(_workflow_dir(path).glob("workflow-*.json")):
        try: value = json.loads(file.read_text(encoding="utf-8"))
        except Exception: continue
        if isinstance(value, dict) and value.get("schema") == WORKFLOW_SCHEMA:
            rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda r:(str(r.get("created_at") or ""),str(r.get("workflow_id") or "")), reverse=True)
    return rows


def create_workflow_run(project_dir: str | Path, workflow: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    if workflow.get("schema") != WORKFLOW_SCHEMA:
        raise ValueError("not a Physical Lab pipeline workflow")
    run_id = f"wrun-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    state = {
        str(node["node_id"]): {"status":"pending","job_id":None,"error":None}
        for node in workflow.get("nodes") or []
    }
    record = {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "workflow_id": workflow.get("workflow_id"),
        "workflow_sha256": workflow.get("workflow_sha256"),
        "project_id": workflow.get("project_id"),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "pending",
        "nodes": state,
        "boundary": "Workflow dispatch state only. Node success means the allow-listed computation completed, not that a physical model chain was scientifically validated.",
    }
    _atomic_json(_run_dir(path) / f"{run_id}.json", record)
    return record


def _load_run(project_dir: Path, run_id: str) -> dict[str, Any]:
    file = _run_dir(project_dir) / f"{run_id}.json"
    value = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != RUN_SCHEMA:
        raise ValueError("not a Physical Lab workflow run")
    return value


def _parents(workflow: Mapping[str, Any]) -> dict[str, set[str]]:
    ids = [str(node["node_id"]) for node in workflow.get("nodes") or []]
    out = {node:set() for node in ids}
    for source,target in workflow.get("edges") or []:
        out[str(target)].add(str(source))
    return out


def advance_workflow_run(project_dir: str | Path, workflow: Mapping[str, Any], run_id: str, *, auto_start: bool = True) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    run = _load_run(path, run_id)
    if str(run.get("workflow_sha256")) != str(workflow.get("workflow_sha256")):
        raise ValueError("workflow run fingerprint does not match selected workflow")
    pipeline_index = _pipeline_index(path)
    parents = _parents(workflow)
    states = run["nodes"]

    # Refresh already-dispatched jobs.
    for node_id, state in states.items():
        job_id = state.get("job_id")
        if not job_id or state.get("status") not in {"queued","running","interrupted"}:
            continue
        job = read_sweep_job(str(job_id))
        if job is None:
            state.update({"status":"failed","error":"referenced sweep job is missing"}); continue
        status = str(job.get("status") or "unknown")
        state["status"] = status
        state["error"] = job.get("error")

    # Mark nodes downstream of terminal failures as blocked.
    changed = True
    while changed:
        changed = False
        for node_id, state in states.items():
            if state.get("status") != "pending": continue
            parent_states = [states[p].get("status") for p in parents[node_id]]
            if any(s in {"failed","cancelled","blocked"} for s in parent_states):
                state.update({"status":"blocked","error":"one or more prerequisite nodes did not succeed"}); changed = True

    # Dispatch all currently-ready nodes. Independent branches may run concurrently.
    if auto_start:
        for node_id in workflow.get("topological_order") or []:
            state = states[node_id]
            if state.get("status") != "pending": continue
            if not all(states[p].get("status") == "succeeded" for p in parents[node_id]):
                continue
            pipeline = pipeline_index.get(node_id)
            if pipeline is None:
                state.update({"status":"failed","error":"saved coupling pipeline is missing"}); continue
            packet = pipeline.get("packet") or {}
            if packet.get("schema") != PACKET_SCHEMA:
                state.update({"status":"failed","error":"saved pipeline packet is invalid"}); continue
            try:
                job = queue_packet(packet)
                job = start_sweep_job(str(job["id"]))
                state.update({"status":str(job.get("status") or "queued"),"job_id":job.get("id"),"error":None})
            except Exception as exc:
                state.update({"status":"failed","error":f"{type(exc).__name__}: {exc}"})

    statuses = [str(x.get("status") or "unknown") for x in states.values()]
    if statuses and all(x == "succeeded" for x in statuses): overall = "succeeded"
    elif any(x in {"failed","cancelled","blocked"} for x in statuses) and all(x in TERMINAL for x in statuses): overall = "failed"
    elif any(x == "running" for x in statuses): overall = "running"
    elif any(x == "queued" for x in statuses): overall = "queued"
    else: overall = "pending"
    run.update({"status":overall,"updated_at":utc_now(),"nodes":states})
    _atomic_json(_run_dir(path) / f"{run_id}.json", run)
    return run


def list_workflow_runs(project_dir: str | Path, *, workflow_id: str | None = None) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    rows=[]
    for file in sorted(_run_dir(path).glob("wrun-*.json")):
        try: value=json.loads(file.read_text(encoding="utf-8"))
        except Exception: continue
        if not isinstance(value,dict) or value.get("schema")!=RUN_SCHEMA: continue
        if workflow_id and value.get("workflow_id") != workflow_id: continue
        rows.append(value)
    rows.sort(key=lambda r:(str(r.get("created_at") or ""),str(r.get("run_id") or "")), reverse=True)
    return rows
