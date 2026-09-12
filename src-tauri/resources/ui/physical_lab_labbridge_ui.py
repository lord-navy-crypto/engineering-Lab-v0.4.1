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
    c1, c2 = st.columns(2)
    packet_file = c1.file_uploader("LabBridge MeasurementAsset JSON", type=["json"], key=f"pl_labbridge_packet_{profile}")
    data_file = c2.file_uploader("Matching BetterBoard data.csv", type=["csv"], key=f"pl_labbridge_data_{profile}")
    if not packet_file:
        st.info("Export/copy `labbridge_measurement_asset.json` and its referenced `data.csv` from a BetterBoard measurement session.")
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

    notes = st.text_input("Import notes", value="", key=f"pl_labbridge_import_notes_{profile}")
    if st.button("Validate & ingest into Engineering Lab", type="primary", disabled=not (check["valid"] and data_bytes), key=f"pl_labbridge_ingest_{profile}"):
        out = ingest_measurement_asset(project_path, packet=packet, dataset_bytes=data_bytes, profile=profile or "measurement-bridge", notes=notes)
        st.success(f"Imported {out['dataset']['dataset_id']} · BetterBoard source SHA {str((packet.get('dataset') or {}).get('sha256') or '')[:12]}…")
        st.rerun()


def _render_notebook(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Experiment Notebook · evidence-linked research record")
    st.caption(
        "Notebook entries are structured project artifacts, not loose chat text. Hypotheses, observations, interpretations, methods, limitations and decisions can cite fixed dataset/result/run/event IDs; each entry has its own SHA and is mirrored into Lab Journey."
    )
    with st.expander("Write notebook entry", expanded=True):
        kind = st.selectbox("Entry kind", ["hypothesis", "observation", "interpretation", "method", "limitation", "decision"], key=f"pl_note_kind_{profile}")
        title = st.text_input("Notebook title", key=f"pl_note_title_{profile}")
        text = st.text_area("Notebook text", height=150, key=f"pl_note_text_{profile}")
        refs = st.text_input("Evidence refs (comma-separated)", key=f"pl_note_refs_{profile}")
        tags = st.text_input("Tags (comma-separated)", key=f"pl_note_tags_{profile}")
        if st.button("Save notebook entry", type="primary", disabled=not (title.strip() and text.strip()), key=f"pl_note_save_{profile}"):
            out = add_notebook_entry(project_path, kind=kind, title=title, text=text, evidence_refs=_split_refs(refs), tags=_split_refs(tags))
            st.success(f"Saved {out['entry']['entry_id']} · Journey {out['journey_event']['event_id']}")
            st.rerun()

    st.markdown("##### Evidence annotation")
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

    entries = list_notebook_entries(project_path)
    annotations = list_annotations(project_path)
    e1, e2 = st.columns(2)
    e1.metric("Notebook entries", len(entries))
    e2.metric("Annotations", len(annotations))
    if entries:
        st.dataframe([
            {"time": r.get("created_at"), "kind": r.get("kind"), "title": r.get("title"), "evidence": ", ".join(r.get("evidence_refs") or []), "sha256": str(r.get("sha256") or "")[:16], "integrity": "PASS" if verify_record(r)["valid"] else "FAIL"}
            for r in entries[:200]
        ], hide_index=True, width="stretch")
    if annotations:
        st.dataframe([
            {"time": r.get("created_at"), "target": f"{(r.get('target') or {}).get('type')}:{(r.get('target') or {}).get('id')}", "label": r.get("label"), "locator": r.get("locator"), "sha256": str(r.get("sha256") or "")[:16], "integrity": "PASS" if verify_record(r)["valid"] else "FAIL"}
            for r in annotations[:200]
        ], hide_index=True, width="stretch")


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

    with st.expander("Append lightweight timeline event", expanded=False):
        event_type = st.selectbox("Event type", ["observation", "hypothesis", "annotation", "decision"], key=f"pl_journey_type_{profile}")
        title = st.text_input("Title", key=f"pl_journey_title_{profile}")
        body = st.text_area("Research note", height=120, key=f"pl_journey_body_{profile}")
        refs = st.text_input("Evidence refs (comma-separated dataset/result/run/event IDs)", key=f"pl_journey_refs_{profile}")
        if st.button("Append timeline event", disabled=not title.strip(), key=f"pl_journey_append_{profile}"):
            event = append_event(project_path, event_type=event_type, source_role="human", title=title, body=body, evidence_refs=_split_refs(refs), payload={"active_profile": profile})
            st.success(f"Appended {event['event_id']}")
            st.rerun()

    events = list_events(project_path, limit=300)
    if events:
        st.dataframe([
            {"seq": e.get("sequence"), "time": e.get("created_at"), "source": e.get("source_role"), "type": e.get("event_type"), "title": e.get("title"), "evidence": ", ".join(e.get("evidence_refs") or []), "sha256": str(e.get("event_sha256") or "")[:16]}
            for e in reversed(events)
        ], hide_index=True, width="stretch")
        chosen = st.selectbox("Inspect journey event", [e["event_id"] for e in reversed(events)], key=f"pl_journey_pick_{profile}")
        st.json(next(e for e in events if e["event_id"] == chosen))
    else:
        st.caption("No Lab Journey events yet.")


def _render_openguin(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Engineering Lab ↔ OpenPenguin · AI Context Bridge")
    st.caption(
        "Engineering Lab remains the scientific record. OpenPenguin receives bounded structured evidence and may return suggestions/proposals; an AI packet never executes a measurement, solver run, parameter change or validation decision."
    )
    focus = st.text_input("Optional research focus for OpenPenguin", value="", key=f"pl_labbridge_ai_focus_{profile}")
    context = build_ai_context_packet(project_path, profile=profile, focus=focus)
    a, b = st.columns(2)
    a.metric("AI context packet", context["packet_id"][:24])
    b.metric("Context SHA", context["content_sha256"][:16] + "…")
    with st.expander("Structured OpenPenguin context", expanded=False):
        st.json(context)
    st.download_button("Export AI Context Packet", data=json.dumps(context, indent=2, sort_keys=True).encode("utf-8"), file_name=f"{context['packet_id']}.json", mime="application/json", key=f"pl_labbridge_ai_context_download_{profile}")

    st.markdown("##### Record OpenPenguin advisory")
    advisory_file = st.file_uploader("OpenPenguin AISuggestion / ActionProposal JSON", type=["json"], key=f"pl_labbridge_ai_advisory_{profile}")
    if advisory_file:
        try:
            packet = _json_upload(advisory_file)
            check = validate_ai_advisory(packet)
            if check["valid"]:
                st.success("Advisory packet integrity PASS · advisory remains unexecuted.")
            else:
                st.error("; ".join(check["errors"]))
            st.json(packet)
            if st.button("Record advisory in Lab Journey", disabled=not check["valid"], key=f"pl_labbridge_ai_record_{profile}"):
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

    ingest, notebook, journey, ai = st.tabs(["BetterBoard Ingress", "Experiment Notebook", "Lab Journey", "OpenPenguin Bridge"])
    with ingest:
        _render_ingest(st, project_path, profile)
    with notebook:
        _render_notebook(st, project_path, profile)
    with journey:
        _render_journey(st, project_path, profile)
    with ai:
        _render_openguin(st, project_path, profile)
