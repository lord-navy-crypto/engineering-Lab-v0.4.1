#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

import physical_lab_project_kernel as projects
from physical_lab_project_interop import save_canonical_dataset, build_reproducibility_pack
from physical_lab_model_coupling import build_parameter_packet, save_pipeline
import physical_lab_pipeline_graph as graph


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = td
        project_path, _ = projects.create_project("DAG Validation", research_question="Can saved model couplings execute as an acyclic dependency graph?")
        dataset = save_canonical_dataset(
            project_path,
            name="workflow inputs",
            profile="numerical-methods",
            columns={"mass":[1.0,1.0],"damping":[0.5,0.7],"diffusivity":[0.2,0.2],"speed":[1.0,1.0]},
            source="synthetic",
        )
        p_pid = save_pipeline(project_path, name="PID stage", packet=build_parameter_packet(
            dataset, adapter_id="pid-step", target_profile="oscillation-integration",
            mappings=[
                {"source_column":"mass","reducer":"mean","target_parameter":"mass"},
                {"source_column":"damping","reducer":"mean","target_parameter":"damping"},
            ],
        ))
        p_heat = save_pipeline(project_path, name="Heat stage", packet=build_parameter_packet(
            dataset, adapter_id="heat-1d", target_profile="numerical-methods",
            mappings=[{"source_column":"diffusivity","reducer":"mean","target_parameter":"diffusivity"}],
        ))
        p_wave = save_pipeline(project_path, name="Wave stage", packet=build_parameter_packet(
            dataset, adapter_id="wave-1d", target_profile="numerical-methods",
            mappings=[{"source_column":"speed","reducer":"mean","target_parameter":"wave_speed"}],
        ))
        a,b,c = p_pid["pipeline_id"], p_heat["pipeline_id"], p_wave["pipeline_id"]
        wf = graph.build_workflow(project_path, name="branch then join", pipeline_ids=[a,b,c], edges=[[a,c],[b,c]])
        saved = graph.save_workflow(project_path, wf)
        assert set(saved["topological_order"][:2]) == {a,b}
        assert saved["topological_order"][-1] == c

        cycle_failed = False
        try:
            graph.topological_order([a,b,c], [[a,b],[b,c],[c,a]])
        except ValueError:
            cycle_failed = True
        assert cycle_failed, "cycle must fail closed"

        # Replace external process dispatch with deterministic fake lifecycle.
        fake_status: dict[str,str] = {}
        counter = {"n":0}
        def fake_queue(_packet):
            counter["n"] += 1
            job_id = f"fake-job-{counter['n']}"
            fake_status[job_id] = "queued"
            return {"id":job_id,"status":"queued"}
        def fake_start(job_id):
            fake_status[job_id] = "running"
            return {"id":job_id,"status":"running","error":None}
        def fake_read(job_id):
            return {"id":job_id,"status":fake_status[job_id],"error":None}
        graph.queue_packet = fake_queue
        graph.start_sweep_job = fake_start
        graph.read_sweep_job = fake_read

        run = graph.create_workflow_run(project_path, saved)
        run = graph.advance_workflow_run(project_path, saved, run["run_id"], auto_start=True)
        states = run["nodes"]
        assert states[a]["status"] == "running" and states[b]["status"] == "running"
        assert states[c]["status"] == "pending" and states[c]["job_id"] is None
        assert counter["n"] == 2

        fake_status[states[a]["job_id"]] = "succeeded"
        fake_status[states[b]["job_id"]] = "succeeded"
        run = graph.advance_workflow_run(project_path, saved, run["run_id"], auto_start=True)
        states = run["nodes"]
        assert states[c]["status"] == "running" and counter["n"] == 3

        fake_status[states[c]["job_id"]] = "succeeded"
        run = graph.advance_workflow_run(project_path, saved, run["run_id"], auto_start=True)
        assert run["status"] == "succeeded", run

        pack = build_reproducibility_pack(project_path)
        paths = {row["path"] for row in pack["manifest"]["files"]}
        assert any(x.startswith("workflows/workflow-") for x in paths), paths
        assert any(x.startswith("workflows/runs/wrun-") for x in paths), paths

        print("PASS: pipeline DAG cycle rejection, branch readiness, join dispatch, run persistence, and pack inclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
