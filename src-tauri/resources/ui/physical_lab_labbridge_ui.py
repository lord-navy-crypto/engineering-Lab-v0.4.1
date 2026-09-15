"""Engineering Lab UI for BetterBoard LabBridge, Experiment Notebook, Lab Journey and OpenPenguin packets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_lab_journey import append_event, list_events, verify_journey
from physical_lab_labbridge import (
    build_ai_context_packet,
    ingest_measurement_asset,
    record_ai_advisory,
    validate_ai_advisory,
    validate_measurement_asset,
)
from physical_lab_openguin_adapter import native_api_contract, probe_openguin, request_advisory
from physical_lab_research_notebook import (
    add_annotation,
    add_notebook_entry,
    list_annotations,
    list_notebook_entries,
    verify_record,
)


def _json_upload(uploaded: Any) -> dict[str, Any]:
    raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON packet must be an object")
    return value


def _split_refs(text: str) -> list[str]:
    return [x.strip() for x in str(text).split(",") if x.strip()]


def _render_ingest(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### BetterBoard → Engineering Lab · Measurement Bridge")
    st.caption(
        "BetterBoard is the real-world ingress. Engineering Lab validates the MeasurementAsset integrity before "
        "promoting numeric channels into the scientific project record. Calibration/traceability remain separate evidence."
    )
    task = st.radio(
        "Ingress task",
        ["Select Files", "Validate", "Ingest"],
        horizontal=True,
        key=f"pl_ingress_task_{profile}",
    )

    c1, c2 = st.columns(2)
    packet_file = c1.file_uploader("LabBridge MeasurementAsset JSON", type=["json"], key=f"pl_labbridge_packet_{profile}")
    data_file = c2.file_uploader("Matching BetterBoard data.csv", type=["csv"], key=f"pl_labbridge_data_{profile}")

    if task == "Select Files":
        a, b = st.columns(2)
        a.metric("MeasurementAsset", "READY" if packet_file else "MISSING")
        b.metric("data.csv", "READY" if data_file else "MISSING")
        if not packet_file or not data_file:
            st.info("Select both `labbridge_measurement_asset.json` and its referenced `data.csv` from the same BetterBoard measurement session.")
        else:
            st.success("Both files are selected. Open Validate before ingesting them into the scientific project record.")
        return

    if not packet_file:
        st.info("Select a BetterBoard `labbridge_measurement_asset.json` in Select Files first.")
        return
    try:
        packet = _json_upload(packet_file)
        data_bytes = data_file.getvalue() if data_file else None
        check = validate_measurement_asset(packet, data_bytes)
    except Exception as exc:
        st.error(f"Could not parse LabBridge packet: {exc}")
        return

    a, b, c, d = st.columns(4)
    a.metric("Packet", str(packet.get("packet_id") or "invalid")[:22])
    b.metric("Integrity", "PASS" if check["valid"] else "FAIL")
    source_role = ((packet.get("source_app") or {}).get("role") if isinstance(packet.get("source_app"), dict) else None)
    c.metric("Source role", str(source_role or "unknown"))
    d.metric("Rows", str((packet.get("dataset") or {}).get("rows") or "—"))
    if check["errors"]:
        st.error("; ".join(check["errors"]))
    if check["warnings"]:
        st.warning("; ".join(check["warnings"]))
    with st.expander("MeasurementAsset details", expanded=False):
        st.json(packet)
        st.caption(check["boundary"])

    if task == "Validate":
        if not data_bytes:
            st.warning("The MeasurementAsset can be parsed, but the matching `data.csv` is still required before ingest.")
        elif check["valid"]:
            st.success("MeasurementAsset integrity PASS. Open Ingest when you are ready to write this dataset into the active Engineering Lab project.")
        else:
            st.error("Validation must pass before this measurement can be ingested.")
        return

    notes = st.text_input("Import notes", value="", key=f"pl_labbridge_import_notes_{profile}")
    if not data_bytes:
        st.warning("Matching BetterBoard `data.csv` is required for ingest.")
    if not check["valid"]:
        st.error("Ingest is disabled because MeasurementAsset integrity did not pass.")
    if st.button("Ingest into Engineering Lab", type="primary", disabled=not (check["valid"] and data_bytes), key=f"pl_labbridge_ingest_{profile}"):
        out = ingest_measurement_asset(project_path, packet=packet, dataset_bytes=data_bytes, profile=profile or "measurement-bridge", notes=notes)
        st.success(f"Imported {out['dataset']['dataset_id']} · BetterBoard source SHA {str((packet.get('dataset') or {}).get('sha256') or '')[:12]}…")
        st.rerun()


def _render_notebook(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Experiment Notebook · evidence-linked research record")
    st.caption(
        "Notebook entries are structured project artifacts, not loose chat text. Hypotheses, observations, interpretations, methods, limitations and decisions can cite fixed dataset/result/run/event IDs; each entry has its own SHA and is mirrored into Lab Journey."
    )
    task = st.radio(
        "Notebook task",
        ["Write Entry", "Annotate Evidence", "Browse Records"],
        horizontal=True,
        key=f"pl_notebook_task_{profile}",
    )

    if task == "Write Entry":
        kind = st.selectbox("Entry kind", ["hypothesis", "observation", "interpretation", "method", "limitation", "decision"], key=f"pl_note_kind_{profile}")
        title = st.text_input("Notebook title", key=f"pl_note_title_{profile}")
        text = st.text_area("Notebook text", height=150, key=f"pl_note_text_{profile}")
        refs = st.text_input("Evidence refs (comma-separated)", key=f"pl_note_refs_{profile}")
        tags = st.text_input("Tags (comma-separated)", key=f"pl_note_tags_{profile}")
        if st.button("Save notebook entry", type="primary", disabled=not (title.strip() and text.strip()), key=f"pl_note_save_{profile}"):
            out = add_notebook_entry(project_path, kind=kind, title=title, text=text, evidence_refs=_split_refs(refs), tags=_split_refs(tags))
            st.success(f"Saved {out['entry']['entry_id']} · Journey {out['journey_event']['event_id']}")
            st.rerun()
        return

    if task == "Annotate Evidence":
        c1, c2 = st.columns(2)
        target_type = c1.selectbox("Target type", ["dataset", "result", "run", "experiment", "plot", "journey-event", "measurement", "workflow", "freeform"], key=f"pl_ann_target_type_{profile}")
        target_id = c2.text_input("Target evidence ID", key=f"pl_ann_target_id_{profile}")
        label = st.text_input("Annotation label", key=f"pl_ann_label_{profile}")
        note = st.text_area("Annotation note", height=100, key=f"pl_ann_note_{profile}")
        loc1, loc2 = st.columns(2)
        locator_key = loc1.text_input("Optional locator key", value="", help="Examples: x, time_s, frequency_hz, row, region", key=f"pl_ann_locator_key_{profile}")
        locator_value = loc2.text_input("Optional locator value", value="", key=f"pl_ann_locator_value_{profile}")
        ann_tags = st.text_input("Annotation tags", value="", key=f"pl_ann_tags_{profile}")
        locator = {locator_key.strip(): locator_value.strip()} if locator_key.strip() else {}
        if st.button("Attach annotation", disabled=not (target_id.strip() and label.strip() and note.strip()), key=f"pl_ann_save_{profile}"):
            out = add_annotation(project_path, target_type=target_type, target_id=target_id, label=label, note=note, locator=locator, tags=_split_refs(ann_tags))
            st.success(f"Saved {out['annotation']['annotation_id']} · Journey {out['journey_event']['event_id']}")
            st.rerun()
        return

    entries = list_notebook_entries(project_path)
    annotations = list_annotations(project_path)
    e1, e2 = st.columns(2)
    e1.metric("Notebook entries", len(entries))
    e2.metric("Annotations", len(annotations))
    record_type = st.radio("Record type", ["Notebook entries", "Annotations"], horizontal=True, key=f"pl_notebook_browse_kind_{profile}")
    if record_type == "Notebook entries":
        if entries:
            st.dataframe([
                {"time": r.get("created_at"), "kind": r.get("kind"), "title": r.get("title"), "evidence": ", ".join(r.get("evidence_refs") or []), "sha256": str(r.get("sha256") or "")[:16], "integrity": "PASS" if verify_record(r)["valid"] else "FAIL"}
                for r in entries[:200]
            ], hide_index=True, width="stretch")
        else:
            st.caption("No notebook entries yet.")
    else:
        if annotations:
            st.dataframe([
                {"time": r.get("created_at"), "target": f"{(r.get('target') or {}).get('type')}:{(r.get('target') or {}).get('id')}", "label": r.get("label"), "locator": r.get("locator"), "sha256": str(r.get("sha256") or "")[:16], "integrity": "PASS" if verify_record(r)["valid"] else "FAIL"}
                for r in annotations[:200]
            ], hide_index=True, width="stretch")
        else:
            st.caption("No evidence annotations yet.")


def _render_journey(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Lab Journey · append-only research timeline")
    check = verify_journey(project_path)
    a, b, c = st.columns(3)
    a.metric("Chain", "PASS" if check["valid"] else "FAIL")
    b.metric("Events", check["verified_events"])
    c.metric("Head SHA", (check.get("head_sha256") or "—")[:14])
    if check["issues"]:
        st.error("Journey integrity issues detected.")
        st.dataframe(check["issues"], hide_index=True, width="stretch")
    st.caption(check["boundary"])

    task = st.radio(
        "Journey task",
        ["Timeline", "Append Event", "Inspect Event"],
        horizontal=True,
        key=f"pl_journey_task_{profile}",
    )
    events = list_events(project_path, limit=300)

    if task == "Append Event":
        event_type = st.selectbox("Event type", ["observation", "hypothesis", "annotation", "decision"], key=f"pl_journey_type_{profile}")
        title = st.text_input("Title", key=f"pl_journey_title_{profile}")
        body = st.text_area("Research note", height=120, key=f"pl_journey_body_{profile}")
        refs = st.text_input("Evidence refs (comma-separated dataset/result/run/event IDs)", key=f"pl_journey_refs_{profile}")
        if st.button("Append timeline event", type="primary", disabled=not title.strip(), key=f"pl_journey_append_{profile}"):
            event = append_event(project_path, event_type=event_type, source_role="human", title=title, body=body, evidence_refs=_split_refs(refs), payload={"active_profile": profile})
            st.success(f"Appended {event['event_id']}")
            st.rerun()
        return

    if not events:
        st.caption("No Lab Journey events yet.")
        return

    ordered = list(reversed(events))
    if task == "Timeline":
        st.dataframe([
            {"seq": e.get("sequence"), "time": e.get("created_at"), "source": e.get("source_role"), "type": e.get("event_type"), "title": e.get("title"), "evidence": ", ".join(e.get("evidence_refs") or []), "sha256": str(e.get("event_sha256") or "")[:16]}
            for e in ordered
        ], hide_index=True, width="stretch")
        return

    chosen = st.selectbox("Inspect journey event", [e["event_id"] for e in ordered], key=f"pl_journey_pick_{profile}")
    st.json(next(e for e in events if e["event_id"] == chosen))


def _render_openguin(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Engineering Lab ↔ OpenPenguin · AI Context Bridge")
    st.caption(
        "Engineering Lab remains the scientific record. OpenPenguin receives bounded structured evidence and may return suggestions/proposals; an AI packet never executes a measurement, solver run, parameter change or validation decision."
    )
    task = st.radio(
        "OpenPenguin task",
        ["Context & Status", "Ask OpenPenguin", "Review Advisory", "Import Advisory"],
        horizontal=True,
        key=f"pl_openguin_task_{profile}",
    )

    if task in {"Context & Status", "Ask OpenPenguin"}:
        focus = st.text_input("Optional research focus for OpenPenguin", value="", key=f"pl_labbridge_ai_focus_{profile}")
        context = build_ai_context_packet(project_path, profile=profile, focus=focus)
        status = probe_openguin()
        a, b, c, d = st.columns(4)
        a.metric("AI context packet", context["packet_id"][:24])
        b.metric("Context SHA", context["content_sha256"][:16] + "…")
        c.metric("OpenPenguin", "ONLINE" if status["available"] else "OFFLINE")
        d.metric("Adapter", status["mode"])

        if task == "Context & Status":
            with st.expander("Structured OpenPenguin context", expanded=False):
                st.json(context)
            with st.expander("OpenPenguin LabBridge API contract", expanded=False):
                st.json(native_api_contract())
                st.caption("Native LabBridge is preferred when available; Engineering Lab falls back to the existing Ollama-compatible OpenPenguin endpoint without changing scientific semantics.")
            st.download_button("Export AI Context Packet", data=json.dumps(context, indent=2, sort_keys=True).encode("utf-8"), file_name=f"{context['packet_id']}.json", mime="application/json", key=f"pl_labbridge_ai_context_download_{profile}")
            return

        if not status["available"]:
            st.info("OpenPenguin private runtime is not currently available at 127.0.0.1:11435. Use Context & Status to export a file-based AI Context packet.")
            return
        if status["mode"] == "native-labbridge":
            st.success("OpenPenguin native LabBridge API detected.")
        else:
            st.caption("OpenPenguin is running in Ollama-compatible fallback mode. No OpenPenguin core rewrite is required; adding the native LabBridge endpoints later will be detected automatically.")
        models = list(status.get("models") or [])
        if not models:
            st.warning("OpenPenguin runtime is reachable but reports no installed model.")
            return
        c1, c2 = st.columns([2, 1])
        model = c1.selectbox("OpenPenguin model", models, key=f"pl_labbridge_op_model_{profile}")
        temperature = c2.slider("Advisory creativity", 0.0, 0.8, 0.2, 0.05, key=f"pl_labbridge_op_temp_{profile}")
        question = st.text_area(
            "Research question for OpenPenguin",
            value="Explain the strongest evidence in this project, identify the largest remaining uncertainty, and suggest one falsifiable next experiment.",
            height=120,
            key=f"pl_labbridge_op_question_{profile}",
        )
        if st.button("Ask OpenPenguin · read-only", type="primary", disabled=not question.strip(), key=f"pl_labbridge_op_ask_{profile}"):
            try:
                suggestion = request_advisory(context, question=question, model=model, temperature=temperature)
                st.session_state[f"pl_labbridge_op_packet_{profile}"] = suggestion
                st.success("Advisory received. Open Review Advisory to inspect or record it.")
            except Exception as exc:
                st.error(f"OpenPenguin request failed: {exc}")
        return

    if task == "Review Advisory":
        suggestion = st.session_state.get(f"pl_labbridge_op_packet_{profile}")
        if not isinstance(suggestion, dict) or not suggestion.get("summary"):
            st.info("No current OpenPenguin advisory in this session. Use Ask OpenPenguin first.")
            return
        st.markdown("**OpenPenguin advisory**")
        st.write(suggestion["summary"])
        st.caption(f"AISuggestion packet {suggestion.get('packet_id')} · executed={bool(suggestion.get('executed'))}")
        with st.expander("Advisory packet", expanded=False):
            st.json(suggestion)
        if st.button("Record this advisory in Lab Journey", type="primary", key=f"pl_labbridge_op_record_{profile}"):
            try:
                out = record_ai_advisory(project_path, suggestion)
            except Exception as exc:
                st.error(f"Could not record OpenPenguin advisory: {exc}")
            else:
                st.success(f"Recorded {out['journey_event']['event_id']} · no action executed")
                st.rerun()
        return

    advisory_file = st.file_uploader("OpenPenguin AISuggestion / ActionProposal JSON", type=["json"], key=f"pl_labbridge_ai_advisory_{profile}")
    if not advisory_file:
        st.info("Choose an OpenPenguin AISuggestion or ActionProposal JSON packet to validate it before recording.")
        return
    try:
        packet = _json_upload(advisory_file)
        check = validate_ai_advisory(packet)
        if check["valid"]:
            st.success("Advisory packet integrity PASS · advisory remains unexecuted.")
        else:
            st.error("; ".join(check["errors"]))
        with st.expander("Imported advisory packet", expanded=False):
            st.json(packet)
        if st.button("Record imported advisory in Lab Journey", type="primary", disabled=not check["valid"], key=f"pl_labbridge_ai_record_{profile}"):
            out = record_ai_advisory(project_path, packet)
            st.success(f"Recorded {out['journey_event']['event_id']} · executed=false")
            st.rerun()
    except Exception as exc:
        st.error(f"Could not read advisory packet: {exc}")


def render_labbridge(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use LabBridge, Experiment Notebook and Lab Journey.")
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("### LabBridge & Research Record")
    st.caption("Choose one task at a time. BetterBoard import, notebook editing, timeline verification and OpenPenguin advisory tools are independent workspaces and only the selected workspace is rendered.")
    workspace = st.radio(
        "LabBridge workspace",
        ["BetterBoard Ingress", "Experiment Notebook", "Lab Journey", "OpenPenguin Bridge"],
        horizontal=True,
        key=f"pl_labbridge_workspace_{profile}",
    )
    if workspace == "BetterBoard Ingress":
        _render_ingest(st, project_path, profile)
    elif workspace == "Experiment Notebook":
        _render_notebook(st, project_path, profile)
    elif workspace == "Lab Journey":
        _render_journey(st, project_path, profile)
    else:
        _render_openguin(st, project_path, profile)