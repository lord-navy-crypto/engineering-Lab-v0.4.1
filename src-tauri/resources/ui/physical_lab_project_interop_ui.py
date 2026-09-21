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

PROJECT_SURFACES = [
    "Project Home",
    "U-Tube Research Studio",
    "Project Tools",
]


def _render_project_home(st: Any, profile: str, project_path: Path) -> None:
    """Compact project landing page with status and obvious next actions."""
    doc = projects.open_project(project_path)
    summary = projects.project_summary(project_path)
    datasets = list_canonical_datasets(project_path)

    st.markdown(f"## 🧭 {summary.get('name') or project_path.stem}")
    question = str(summary.get("research_question") or "").strip()
    if question:
        st.markdown(f"**Research question:** {question}")
    else:
        st.info("No research question is set yet. Add one in the .physlab Project panel to keep analysis anchored to a clear question.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Experiments", int(summary.get("experiment_count") or 0))
    m2.metric("Jobs", int(summary.get("job_count") or 0))
    m3.metric("Results", int(summary.get("result_count") or 0))
    m4.metric("Datasets", len(datasets))
    m5.metric("Profiles", len(summary.get("profiles") or []))

    updated = str(summary.get("updated_at") or "")
    project_id = str(summary.get("project_id") or "")
    st.caption(
        f"Project ID: {project_id or '—'} · Updated: {updated or '—'} · "
        "Counts describe indexed project records; they do not imply scientific validation."
    )

    statuses = dict(summary.get("job_statuses") or {})
    if statuses:
        st.markdown("#### Compute status")
        cols = st.columns(min(5, max(1, len(statuses))))
        for idx, (status, count) in enumerate(sorted(statuses.items())):
            cols[idx % len(cols)].metric(str(status).replace("_", " ").title(), int(count or 0))

    st.markdown("#### Start here")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🧪 U-Tube research**")
        st.caption("Open model visualization, uncertainty, DIY data comparison, robust design, digital twin and hysteresis tools.")
        if st.button("Open U-Tube Studio", type="primary", width="stretch", key=f"pl_home_utube_{profile}"):
            st.session_state[f"pl_project_surface_{profile}"] = "U-Tube Research Studio"
            st.rerun()
    with c2:
        st.markdown("**📊 Data & analysis**")
        st.caption("Bring in measurements, inspect results, visualize data, run applied analysis, and compare runs.")
        if st.button("Open Project Tools", width="stretch", key=f"pl_home_tools_{profile}"):
            st.session_state[f"pl_project_surface_{profile}"] = "Project Tools"
            st.rerun()
    with c3:
        st.markdown("**📦 Reproducibility**")
        st.caption("Package project metadata, datasets, analysis artifacts, environment evidence and reports into a portable ZIP.")
        if st.button("Open Reproducibility", width="stretch", key=f"pl_home_repro_{profile}"):
            st.session_state[f"pl_project_surface_{profile}"] = "Project Tools"
            st.session_state[f"pl_project_tool_group_{profile}"] = "Reproducibility"
            st.rerun()

    description = str(doc.get("description") or "").strip()
    profiles = [str(x) for x in (summary.get("profiles") or [])]
    with st.expander("Project details", expanded=False):
        st.write(description or "No project description yet.")
        st.caption("Profiles: " + (", ".join(profiles) if profiles else "—"))
        if datasets:
            st.markdown("**Recent project datasets**")
            st.dataframe([
                {
                    "name": d.get("name"),
                    "rows": d.get("row_count"),
                    "columns": len(d.get("columns") or {}),
                    "profile": d.get("profile"),
                }
                for d in datasets[-5:]
            ], hide_index=True, width="stretch")


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


def _render_all_project_tools_flat(st: Any, profile: str, project_path: Path) -> None:
    """Restore the September-12 one-layer tool access while keeping newer tools available."""
    tools = [
        ("Data Bridge", lambda: _render_data_bridge(st, profile, project_path)),
        ("BetterBoard Discovery", lambda: __import__("physical_lab_betterboard_discovery_ui").render_betterboard_discovery(st, profile)),
        ("LabBridge / Journey", lambda: __import__("physical_lab_labbridge_ui").render_labbridge(st, profile)),
        ("Result Inspector", lambda: __import__("physical_lab_result_inspector_ui").render_result_inspector(st, profile)),
        ("Run Comparison", lambda: __import__("physical_lab_run_comparison_ui").render_run_comparison(st, profile)),
        ("Model Coupling", lambda: __import__("physical_lab_model_coupling_ui").render_model_coupling(st, profile)),
        ("Pipeline DAG", lambda: __import__("physical_lab_pipeline_graph_ui").render_pipeline_graph(st, profile)),
        ("Reproducibility Pack", lambda: _render_reproducibility_group(st, profile, project_path)),
        ("Visualization Studio", lambda: __import__("physical_lab_visualization_studio_ui").render_visualization_studio(st, profile)),
        ("Visual Analytics", lambda: __import__("physical_lab_visual_analytics_ui").render_visual_analytics(st, profile)),
        ("Applied Math & Statistics", lambda: (
            __import__("physical_lab_applied_analysis_ui").render_applied_analysis(st, profile),
            __import__("physical_lab_applied_analysis_advanced_ui").render_applied_analysis_advanced(st, profile),
            __import__("physical_lab_applied_math_deep_ui").render_applied_math_deep(st, profile),
            __import__("physical_lab_sweep_design_bridge_ui").render_sweep_design_bridge(st, profile),
        )),
        ("Science Analysis", lambda: (
            __import__("physical_lab_tradeoff_analysis_ui").render_tradeoff_analysis(st, profile),
            __import__("physical_lab_science_protocol_ui").render_science_protocol_ui(st, profile, project_path),
        )),
        ("ModelSpec DIY", lambda: __import__("physical_lab_modelspec_diy_ui").render_modelspec_diy(st, profile)),
    ]
    st.markdown("#### Full Capability · one-layer access")
    st.caption(
        "Restored discoverability: the September-12 direct Project tools and later analysis/model tools are available here "
        "without first choosing a tool family."
    )
    labels = [name for name, _renderer in tools]
    selected = st.selectbox("Project tool", labels, key=f"pl_project_flat_tool_{profile}")
    renderer = next(renderer for name, renderer in tools if name == selected)
    st.markdown("---")
    try:
        renderer()
    except Exception as exc:
        st.warning(f"{selected} could not load: {exc}")


def _render_project_tools(st: Any, profile: str, project_path: Path) -> None:
    st.markdown("### 🧰 Project Tools")
    access = st.radio(
        "Tool access",
        ["Full Capability · one layer", "Organized groups"],
        horizontal=True,
        key=f"pl_project_access_mode_{profile}",
        help="Full Capability restores the older direct-access layout; Organized groups keeps the newer compact navigation."
    )
    if access == "Full Capability · one layer":
        _render_all_project_tools_flat(st, profile, project_path)
        return

    st.caption(
        "Choose a task family, then one tool. This organized mode keeps the workspace compact; switch to Full Capability for one-layer access."
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
    surface = st.radio(
        "Project workspace",
        PROJECT_SURFACES,
        horizontal=True,
        key=f"pl_project_surface_{profile}",
    )
    st.markdown("---")
    if surface == "Project Home":
        _render_project_home(st, profile, project_path)
    elif surface == "U-Tube Research Studio":
        _render_utube_research_studio(st, profile)
    else:
        _render_project_tools(st, profile, project_path)
