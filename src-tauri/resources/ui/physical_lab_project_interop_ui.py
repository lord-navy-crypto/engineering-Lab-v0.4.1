"""UI for Engineering Lab project data, LabBridge, results, visualization, coupling, workflows and reproducibility."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_project_interop import (
    build_reproducibility_pack,
    dataset_csv_bytes,
    list_canonical_datasets,
    save_canonical_dataset,
)


PROJECT_TOOL_GROUPS = [
    "Data & LabBridge",
    "Visualize & Analyze",
    "Model & Workflow",
    "Reproducibility",
]


def _render_utube_research_studio(st: Any, profile: str) -> None:
    """Expose the U-Tube workspaces at project level instead of burying them in Applied Math."""
    st.markdown("### 🧪 U-Tube Research Studio")
    st.caption(
        "Direct access to the rotating U-tube model, research-data visualization, uncertainty tools, "
        "robust design, digital twin, hysteresis analysis and verification controls."
    )
    workspace = st.radio(
        "Open workspace",
        ["Physical Model & Data", "Uncertainty", "Advanced Engineering & Twin"],
        horizontal=True,
        key=f"pl_utube_studio_workspace_{profile}",
    )
    if workspace == "Physical Model & Data":
        st.info("Use Physical View / Threshold Map / Theory ↔ Experiment for model visualization, or DOE / Sweep for computational campaigns.")
        try:
            from physical_lab_utube_experiment_ui import render_utube_experiment
            render_utube_experiment(st, profile)
        except Exception as exc:
            st.warning(f"U-Tube Physical Model & Data could not load: {exc}")
    elif workspace == "Uncertainty":
        st.info("Explore model-input uncertainty and threshold sensitivity without treating visualization bands as measured uncertainty.")
        try:
            from physical_lab_utube_uncertainty_ui import render_utube_uncertainty
            render_utube_uncertainty(st, profile)
        except Exception as exc:
            st.warning(f"U-Tube Uncertainty workspace could not load: {exc}")
    else:
        st.info("Open DIY Data View for your own research columns, or use robust design, digital twin, hysteresis and verification tools below.")
        try:
            from physical_lab_utube_advanced_ui import render_utube_advanced
            render_utube_advanced(st, profile)
        except Exception as exc:
            st.warning(f"U-Tube Advanced Engineering & Twin could not load: {exc}")


def _render_data_bridge(st: Any, profile: str, project_path: Path) -> None:
    parsed = st.session_state.get(f"pl_orch_table_{profile}")
    if parsed:
        st.markdown("#### Promote current numeric table")
        numeric = list(parsed.get("numeric_columns") or [])
        selected = st.multiselect("Columns", numeric, default=numeric, key=f"pl_bridge_cols_{profile}")
        c1, c2 = st.columns(2)
        name = c1.text_input("Dataset name", value=f"{profile}-dataset", key=f"pl_bridge_name_{profile}")
        notes = c2.text_input("Notes", value="", key=f"pl_bridge_notes_{profile}")
        unit_text = st.text_input("Units (optional, comma-separated column=unit)", value="", key=f"pl_bridge_units_{profile}")
        units = {}
        for part in unit_text.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                units[k.strip()] = v.strip()
        if st.button("Promote table to project dataset", type="primary", disabled=not selected, key=f"pl_bridge_save_{profile}"):
            cols = {k: parsed["column_data"][k] for k in selected}
            rec = save_canonical_dataset(
                project_path,
                name=name,
                profile=profile,
                columns=cols,
                units=units,
                source=str(parsed.get("filename") or ""),
                notes=notes,
            )
            st.success(f"Saved {rec['dataset_id']} · sha256 {rec['sha256'][:12]}…")
            st.rerun()
    else:
        st.info("Parse a CSV/TSV in Research Orchestrator first to promote it into a reusable project dataset.")

    datasets = list_canonical_datasets(project_path)
    if datasets:
        st.markdown("#### Project datasets")
        st.dataframe([
            {
                "id": d.get("dataset_id"),
                "name": d.get("name"),
                "source_profile": d.get("profile"),
                "rows": d.get("row_count"),
                "columns": len(d.get("columns") or {}),
                "sha256": str(d.get("sha256") or "")[:16],
            }
            for d in datasets
        ], hide_index=True, width="stretch")
        ids = [d["dataset_id"] for d in datasets]
        chosen = st.selectbox("Inspect / export dataset", ids, key=f"pl_bridge_pick_{profile}")
        dataset = next(d for d in datasets if d["dataset_id"] == chosen)
        st.json({k: v for k, v in dataset.items() if k not in {"columns", "file_path"}})
        st.dataframe([
            {k: (dataset["columns"][k][i] if i < len(dataset["columns"][k]) else None) for k in dataset["columns"]}
            for i in range(min(int(dataset.get("row_count") or 0), 100))
        ], hide_index=True, width="stretch")
        st.download_button(
            "Download canonical dataset CSV",
            data=dataset_csv_bytes(dataset),
            file_name=f"{dataset.get('name', 'dataset')}.csv",
            mime="text/csv",
            key=f"pl_bridge_download_{profile}_{chosen}",
        )
    else:
        st.caption("No canonical project datasets yet.")


def _render_data_group(st: Any, profile: str, project_path: Path) -> None:
    st.caption("Bring data in, inspect project datasets/results, and connect real-world measurements before deeper analysis.")
    tool = st.radio(
        "Data tool",
        ["Data Bridge", "BetterBoard Discovery", "LabBridge / Journey", "Result Inspector"],
        horizontal=True,
        key=f"pl_project_data_tool_{profile}",
    )
    if tool == "Data Bridge":
        _render_data_bridge(st, profile, project_path)
    elif tool == "BetterBoard Discovery":
        try:
            from physical_lab_betterboard_discovery_ui import render_betterboard_discovery
            render_betterboard_discovery(st, profile)
        except Exception as exc:
            st.warning(f"BetterBoard local discovery could not load: {exc}")
    elif tool == "LabBridge / Journey":
        try:
            from physical_lab_labbridge_ui import render_labbridge
            render_labbridge(st, profile)
        except Exception as exc:
            st.warning(f"LabBridge / Lab Journey could not load: {exc}")
    else:
        try:
            from physical_lab_result_inspector_ui import render_result_inspector
            render_result_inspector(st, profile)
        except Exception as exc:
            st.warning(f"Unified Result Inspector/Materializer could not load: {exc}")


def _render_analysis_group(st: Any, profile: str, project_path: Path) -> None:
    st.caption("Choose visualization, uncertainty-aware analytics, applied mathematics, or science-focused trade-off analysis.")
    tool = st.radio(
        "Analysis tool",
        ["Visualization Studio", "Visual Analytics", "Applied Math & Statistics", "Science Analysis"],
        horizontal=True,
        key=f"pl_project_analysis_tool_{profile}",
    )
    if tool == "Visualization Studio":
        try:
            from physical_lab_visualization_studio_ui import render_visualization_studio
            render_visualization_studio(st, profile)
        except Exception as exc:
            st.warning(f"Visualization Studio could not load: {exc}")
    elif tool == "Visual Analytics":
        try:
            from physical_lab_visual_analytics_ui import render_visual_analytics
            render_visual_analytics(st, profile)
        except Exception as exc:
            st.warning(f"Visual Analytics Workbench could not load: {exc}")
    elif tool == "Applied Math & Statistics":
        try:
            from physical_lab_applied_analysis_ui import render_applied_analysis
            render_applied_analysis(st, profile)
            from physical_lab_applied_analysis_advanced_ui import render_applied_analysis_advanced
            render_applied_analysis_advanced(st, profile)
            from physical_lab_applied_math_deep_ui import render_applied_math_deep
            render_applied_math_deep(st, profile)
            from physical_lab_sweep_design_bridge_ui import render_sweep_design_bridge
            render_sweep_design_bridge(st, profile)
        except Exception as exc:
            st.warning(f"Applied Mathematics & Statistics could not load: {exc}")
    else:
        try:
            from physical_lab_tradeoff_analysis_ui import render_tradeoff_analysis
            render_tradeoff_analysis(st, profile)
            from physical_lab_science_protocol_ui import render_science_protocol_ui
            render_science_protocol_ui(st, profile, project_path)
        except Exception as exc:
            st.warning(f"Science Analysis workspace could not load: {exc}")


def _render_model_group(st: Any, profile: str) -> None:
    st.caption("Build bounded model controls, compare runs, connect models, and inspect workflow dependencies.")
    tool = st.radio(
        "Model / workflow tool",
        ["ModelSpec DIY", "Run Comparison", "Model Coupling", "Pipeline DAG"],
        horizontal=True,
        key=f"pl_project_model_tool_{profile}",
    )
    if tool == "ModelSpec DIY":
        try:
            from physical_lab_modelspec_diy_ui import render_modelspec_diy
            render_modelspec_diy(st, profile)
        except Exception as exc:
            st.warning(f"ModelSpec DIY workspace could not load: {exc}")
    elif tool == "Run Comparison":
        try:
            from physical_lab_run_comparison_ui import render_run_comparison
            render_run_comparison(st, profile)
        except Exception as exc:
            st.warning(f"Run Comparison / Staleness Dashboard could not load: {exc}")
    elif tool == "Model Coupling":
        try:
            from physical_lab_model_coupling_ui import render_model_coupling
            render_model_coupling(st, profile)
        except Exception as exc:
            st.warning(f"Model-to-Model Coupling could not load: {exc}")
    else:
        try:
            from physical_lab_pipeline_graph_ui import render_pipeline_graph
            render_pipeline_graph(st, profile)
        except Exception as exc:
            st.warning(f"Pipeline DAG could not load: {exc}")


def _render_reproducibility_group(st: Any, profile: str, project_path: Path) -> None:
    st.markdown("#### Portable reproducibility package")
    st.caption("Package project evidence and analysis artifacts after you are satisfied with the current project state.")
    include_assets = st.checkbox("Include raw measurement assets up to 8 MB each", value=False, key=f"pl_repro_assets_{profile}")
    st.caption(
        "Default pack includes measurement/calibration metadata, experiments, result references, LabBridge provenance, Lab Journey events, "
        "Experiment Notebook/annotations, project datasets, result materializations, software environments, saved coupling pipelines/workflows, "
        "frozen run snapshots, visualization recipes, visual-analytics dashboards, applied-analysis artifacts, science-analysis recipes/summaries, and a generated project report."
    )
    if st.button("Build reproducibility ZIP", type="primary", key=f"pl_repro_build_{profile}"):
        st.session_state[f"pl_repro_pack_{profile}"] = build_reproducibility_pack(
            project_path,
            include_measurement_assets=include_assets,
        )
    pack = st.session_state.get(f"pl_repro_pack_{profile}")
    if pack:
        a, b, c = st.columns(3)
        a.metric("Pack files", pack["file_count"])
        b.metric("ZIP size", f"{pack['size_bytes']/1024:.1f} KiB")
        c.metric("ZIP sha256", pack["zip_sha256"][:16] + "…")
        if pack["manifest"].get("omitted"):
            st.warning(f"Omitted {len(pack['manifest']['omitted'])} oversized file(s); inspect manifest for details.")
        st.download_button(
            "Download reproducibility pack",
            data=pack["bytes"],
            file_name=pack["filename"],
            mime="application/zip",
            key=f"pl_repro_download_{profile}",
        )
        st.json({k: v for k, v in pack["manifest"].items() if k != "files"})
        st.caption(pack["boundary"])


def render_project_interop(st: Any, profile: str) -> None:
    selector_key = f"pl_project_select_{profile}"
    if str(st.session_state.get(selector_key) or "") == "Create new project":
        return
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("---")
    _render_utube_research_studio(st, profile)
    st.markdown("---")
    with st.expander("🧰 Engineering Lab · Project Tools", expanded=True):
        st.caption(
            "Choose a task family, then one tool. Only that tool is rendered, keeping the workspace readable and avoiding unrelated module initialization on every rerun."
        )
        tool_group = st.radio(
            "What do you want to do?",
            PROJECT_TOOL_GROUPS,
            horizontal=True,
            key=f"pl_project_tool_group_{profile}",
        )
        st.markdown("---")
        if tool_group == "Data & LabBridge":
            _render_data_group(st, profile, project_path)
        elif tool_group == "Visualize & Analyze":
            _render_analysis_group(st, profile, project_path)
        elif tool_group == "Model & Workflow":
            _render_model_group(st, profile)
        else:
            _render_reproducibility_group(st, profile, project_path)
