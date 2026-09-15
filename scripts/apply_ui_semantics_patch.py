#!/usr/bin/env python3
"""One-time exact patch for Shared Scientific UI Semantics integration.

This script is intentionally strict: every replacement must match exactly once or
it aborts without committing production changes.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Project Home: shared context plus deliberately non-promoted status axes.
path = UI / "physical_lab_project_interop_ui.py"
replace_once(
    path,
    "import physical_lab_project_kernel as projects\nfrom physical_lab_project_interop import (",
    "import physical_lab_project_kernel as projects\n"
    "from physical_lab_ui_semantics import render_context_header, render_status_card\n"
    "from physical_lab_project_interop import (",
    "project interop import",
)
replace_once(
    path,
    "    datasets = list_canonical_datasets(project_path)\n\n"
    "    st.markdown(f\"## 🧭 {summary.get('name') or project_path.stem}\")",
    "    datasets = list_canonical_datasets(project_path)\n\n"
    "    project_label = str(summary.get(\"name\") or project_path.stem)\n"
    "    render_context_header(st, project=project_label, workspace=\"Project Home\")\n"
    "    render_status_card(\n"
    "        st,\n"
    "        validation=\"NOT ESTABLISHED\",\n"
    "        scientific=\"NOT ESTABLISHED\",\n"
    "        provenance=\"UNSPECIFIED\",\n"
    "        execution=\"NOT APPLICABLE\",\n"
    "    )\n\n"
    "    st.markdown(f\"## 🧭 {summary.get('name') or project_path.stem}\")",
    "project home semantic header",
)

# Result Inspector: explicit RESULT identity and four independent axes.
path = UI / "physical_lab_result_inspector_ui.py"
replace_once(
    path,
    "import physical_lab_project_kernel as projects\nfrom physical_lab_environment_manifest import",
    "import physical_lab_project_kernel as projects\n"
    "from physical_lab_ui_semantics import render_context_header, render_object_card, render_status_card\n"
    "from physical_lab_environment_manifest import",
    "result inspector import",
)
replace_once(
    path,
    "    inspection, sanity, _uncertainty = prepared\n\n"
    "    a,b,c = st.columns(3)",
    "    inspection, sanity, _uncertainty = prepared\n\n"
    "    source_name = str(identity.get(\"job_id\") or identity.get(\"sweep_job_id\") or identity.get(\"result_id\") or \"persisted result\")\n"
    "    render_context_header(\n"
    "        st,\n"
    "        project=project_path.stem,\n"
    "        workspace=\"Result Inspector\",\n"
    "        task=workspace,\n"
    "        source=source_name,\n"
    "    )\n"
    "    if workspace == \"Inspect Result\":\n"
    "        render_object_card(\n"
    "            st,\n"
    "            object_type=\"RESULT\",\n"
    "            title=source_name,\n"
    "            metadata={\n"
    "                \"schema\": result.get(\"schema\") or \"untyped\",\n"
    "                \"fields\": inspection.get(\"field_count\"),\n"
    "                \"sha256\": inspection.get(\"result_sha256\"),\n"
    "            },\n"
    "        )\n"
    "        conformance_status = str((inspection.get(\"contract_conformance\") or {}).get(\"status\") or \"NOT ESTABLISHED\")\n"
    "        provenance_state = \"RECORDED\" if identity and inspection.get(\"result_sha256\") else (\"PARTIAL\" if identity or inspection.get(\"result_sha256\") else \"UNSPECIFIED\")\n"
    "        render_status_card(\n"
    "            st,\n"
    "            validation=conformance_status,\n"
    "            scientific=\"NOT ESTABLISHED\",\n"
    "            provenance=provenance_state,\n"
    "            execution=str(identity.get(\"status\") or \"NOT APPLICABLE\"),\n"
    "        )\n\n"
    "    a,b,c = st.columns(3)",
    "result inspector semantic summary",
)

# Visual Analytics: explicit caller mapping from existing source kind to object class.
path = UI / "physical_lab_visual_analytics_ui.py"
replace_once(
    path,
    "import physical_lab_project_kernel as projects\nfrom physical_lab_project_interop import list_canonical_datasets",
    "import physical_lab_project_kernel as projects\n"
    "from physical_lab_ui_semantics import render_context_header, render_object_card\n"
    "from physical_lab_project_interop import list_canonical_datasets",
    "visual analytics import",
)
replace_once(
    path,
    "    source = next(s for s in sources if s[\"id\"] == chosen)\n"
    "    a, b, c = st.columns(3)",
    "    source = next(s for s in sources if s[\"id\"] == chosen)\n"
    "    source_object_type = {\"dataset\": \"DATASET\", \"result\": \"RESULT\", \"sweep\": \"RESULT\"}.get(str(source.get(\"kind\") or \"\").lower(), \"UNKNOWN\")\n"
    "    render_context_header(\n"
    "        st,\n"
    "        project=project_path.stem,\n"
    "        workspace=\"Visual Analytics\",\n"
    "        task=\"Selection & Linked Views\",\n"
    "        source=str(source.get(\"label\") or source.get(\"id\") or \"source\"),\n"
    "    )\n"
    "    render_object_card(\n"
    "        st,\n"
    "        object_type=source_object_type,\n"
    "        title=str(source.get(\"label\") or source.get(\"id\") or \"source\"),\n"
    "        metadata={\n"
    "            \"source_id\": source.get(\"id\"),\n"
    "            \"rows\": len(source.get(\"frame\") or []),\n"
    "            **dict(source.get(\"identity\") or {}),\n"
    "        },\n"
    "    )\n"
    "    a, b, c = st.columns(3)",
    "visual analytics source semantics",
)

# Model Coupling: DATASET and MODEL identity remain distinct; queue is only execution state.
path = UI / "physical_lab_model_coupling_ui.py"
replace_once(
    path,
    "import physical_lab_project_kernel as projects\nfrom physical_lab_project_interop import list_canonical_datasets",
    "import physical_lab_project_kernel as projects\n"
    "from physical_lab_ui_semantics import render_context_header, render_object_card, render_status_card\n"
    "from physical_lab_project_interop import list_canonical_datasets",
    "model coupling import",
)
replace_once(
    path,
    "    if not isinstance(packet, dict):\n"
    "        packet = None\n\n"
    "    if task == \"Configure Mapping\":",
    "    if not isinstance(packet, dict):\n"
    "        packet = None\n\n"
    "    render_context_header(st, project=project_path.stem, workspace=\"Model Coupling\", task=task)\n"
    "    if packet:\n"
    "        render_object_card(\n"
    "            st,\n"
    "            object_type=\"DATASET\",\n"
    "            title=str(packet.get(\"source_dataset_id\") or \"source dataset\"),\n"
    "            metadata={\"sha256\": packet.get(\"source_dataset_sha256\")},\n"
    "        )\n"
    "        render_object_card(\n"
    "            st,\n"
    "            object_type=\"MODEL\",\n"
    "            title=str(packet.get(\"target_adapter\") or \"downstream model\"),\n"
    "            metadata={\"profile\": packet.get(\"target_profile\"), \"packet_sha256\": packet.get(\"packet_sha256\")},\n"
    "        )\n"
    "        queued_state = st.session_state.get(_queued_key(profile))\n"
    "        execution_state = \"NOT APPLICABLE\"\n"
    "        if isinstance(queued_state, dict) and str(queued_state.get(\"packet_sha256\") or \"\") == str(packet.get(\"packet_sha256\") or \"\"):\n"
    "            execution_state = \"PENDING\" if queued_state.get(\"execution_started\") else \"QUEUED\"\n"
    "        render_status_card(\n"
    "            st,\n"
    "            validation=\"NOT ESTABLISHED\",\n"
    "            scientific=\"NOT ESTABLISHED\",\n"
    "            provenance=\"PARTIAL\",\n"
    "            execution=execution_state,\n"
    "        )\n\n"
    "    if task == \"Configure Mapping\":",
    "model coupling semantic cards",
)

# Pipeline DAG: shared context and compact execution axis; graph remains authoritative.
path = UI / "physical_lab_pipeline_graph_ui.py"
replace_once(
    path,
    "import physical_lab_project_kernel as projects\nfrom physical_lab_model_coupling import list_pipelines",
    "import physical_lab_project_kernel as projects\n"
    "from physical_lab_ui_semantics import render_context_header, render_status_card\n"
    "from physical_lab_model_coupling import list_pipelines",
    "pipeline graph import",
)
replace_once(
    path,
    "    st.markdown(\"#### Pipeline Graph / DAG\")\n"
    "    st.caption(\"Compose saved coupling pipelines into an acyclic dependency graph. Edges control execution readiness; each node retains its own explicit dataset-to-parameter mapping.\")",
    "    st.markdown(\"#### Pipeline Graph / DAG\")\n"
    "    st.caption(\"Compose saved coupling pipelines into an acyclic dependency graph. Edges control execution readiness; each node retains its own explicit dataset-to-parameter mapping.\")\n"
    "    render_context_header(st, project=path.stem, workspace=\"Pipeline DAG\", task=\"Workflow Graph\")",
    "pipeline graph context",
)
replace_once(
    path,
    "    run=advance_workflow_run(path,wf,run_id,auto_start=True)\n"
    "    st.metric(\"Workflow status\",str(run.get(\"status\") or \"—\"))",
    "    run=advance_workflow_run(path,wf,run_id,auto_start=True)\n"
    "    st.metric(\"Workflow status\",str(run.get(\"status\") or \"—\"))\n"
    "    render_status_card(\n"
    "        st,\n"
    "        validation=\"NOT ESTABLISHED\",\n"
    "        scientific=\"NOT ESTABLISHED\",\n"
    "        provenance=\"RECORDED\",\n"
    "        execution=str(run.get(\"status\") or \"NOT APPLICABLE\"),\n"
    "    )",
    "pipeline graph execution semantics",
)

# Bundle the new runtime helper.
path = ROOT / "src-tauri" / "tauri.conf.json"
replace_once(
    path,
    '      "resources/ui/physical_lab_surface_registry.py": "ui/physical_lab_surface_registry.py",\n',
    '      "resources/ui/physical_lab_surface_registry.py": "ui/physical_lab_surface_registry.py",\n'
    '      "resources/ui/physical_lab_ui_semantics.py": "ui/physical_lab_ui_semantics.py",\n',
    "tauri semantics resource",
)

print("Applied shared scientific UI semantics patch successfully.")
