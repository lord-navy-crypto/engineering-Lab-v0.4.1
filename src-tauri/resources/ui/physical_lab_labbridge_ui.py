"""Engineering Lab UI for BetterBoard LabBridge, Lab Journey and OpenPenguin packets."""
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


def _json_upload(uploaded: Any) -> dict[str, Any]:
    raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded.read()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON packet must be an object")
    return value


def _render_ingest(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### BetterBoard → Engineering Lab · Measurement Bridge")
    st.caption(
        "BetterBoard is the real-world ingress. Engineering Lab validates the MeasurementAsset integrity before "
        "promoting numeric channels into the scientific project record. Calibration/traceability remain separate evidence."
    )
    c1, c2 = st.columns(2)
    packet_file = c1.file_uploader(
        "LabBridge MeasurementAsset JSON",
        type=["json"],
        key=f"pl_labbridge_packet_{profile}",
    )
    data_file = c2.file_uploader(
        "Matching BetterBoard data.csv",
        type=["csv"],
        key=f"pl_labbridge_data_{profile}",
    )
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
    b_role = ((packet.get("source_app") or {}).get("role") if isinstance(packet.get("source_app"), dict) else None)
    c.metric("Source role", str(b_role or "unknown"))
    d.metric("Rows", str((packet.get("dataset") or {}).get("rows") or "—"))
    if check["errors"]:
        st.error("; ".join(check["errors"]))
    if check["warnings"]:
        st.warning("; ".join(check["warnings"]))

    with st.expander("MeasurementAsset details", expanded=False):
        st.json(packet)
        st.caption(check["boundary"])

    notes = st.text_input("Import notes", value="", key=f"pl_labbridge_import_notes_{profile}")
    if st.button(
        "Validate & ingest into Engineering Lab",
        type="primary",
        disabled=not (check["valid"] and data_bytes),
        key=f"pl_labbridge_ingest_{profile}",
    ):
        out = ingest_measurement_asset(
            project_path,
            packet=packet,
            dataset_bytes=data_bytes,
            profile=profile or "measurement-bridge",
            notes=notes,
        )
        st.success(
            f"Imported {out['dataset']['dataset_id']} · BetterBoard source SHA {str((packet.get('dataset') or {}).get('sha256') or '')[:12]}…"
        )
        st.rerun()


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

    with st.expander("Add human research event", expanded=False):
        event_type = st.selectbox(
            "Event type",
            ["observation", "hypothesis", "annotation", "decision"],
            key=f"pl_journey_type_{profile}",
        )
        title = st.text_input("Title", key=f"pl_journey_title_{profile}")
        body = st.text_area("Research note", height=120, key=f"pl_journey_body_{profile}")
        refs = st.text_input(
            "Evidence refs (comma-separated dataset/result/run/event IDs)",
            key=f"pl_journey_refs_{profile}",
        )
        if st.button("Append research event", disabled=not title.strip(), key=f"pl_journey_append_{profile}"):
            event = append_event(
                project_path,
                event_type=event_type,
                source_role="human",
                title=title,
                body=body,
                evidence_refs=[x.strip() for x in refs.split(",") if x.strip()],
                payload={"active_profile": profile},
            )
            st.success(f"Appended {event['event_id']}")
            st.rerun()

    events = list_events(project_path, limit=200)
    if events:
        st.dataframe([
            {
                "seq": e.get("sequence"),
                "time": e.get("created_at"),
                "source": e.get("source_role"),
                "type": e.get("event_type"),
                "title": e.get("title"),
                "evidence": ", ".join(e.get("evidence_refs") or []),
                "sha256": str(e.get("event_sha256") or "")[:16],
            }
            for e in reversed(events)
        ], hide_index=True, width="stretch")
        chosen = st.selectbox(
            "Inspect journey event",
            [e["event_id"] for e in reversed(events)],
            key=f"pl_journey_pick_{profile}",
        )
        event = next(e for e in events if e["event_id"] == chosen)
        st.json(event)
    else:
        st.caption("No Lab Journey events yet.")


def _render_openguin(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Engineering Lab ↔ OpenPenguin · AI Context Bridge")
    st.caption(
        "Engineering Lab remains the scientific record. OpenPenguin receives bounded structured evidence and may return "
        "suggestions/proposals; an AI packet never executes a measurement, solver run, parameter change or validation decision."
    )
    focus = st.text_input(
        "Optional research focus for OpenPenguin",
        value="",
        key=f"pl_labbridge_ai_focus_{profile}",
    )
    context = build_ai_context_packet(project_path, profile=profile, focus=focus)
    a, b = st.columns(2)
    a.metric("AI context packet", context["packet_id"][:24])
    b.metric("Context SHA", context["content_sha256"][:16] + "…")
    with st.expander("Structured OpenPenguin context", expanded=False):
        st.json(context)
    st.download_button(
        "Export AI Context Packet",
        data=json.dumps(context, indent=2, sort_keys=True).encode("utf-8"),
        file_name=f"{context['packet_id']}.json",
        mime="application/json",
        key=f"pl_labbridge_ai_context_download_{profile}",
    )

    st.markdown("##### Record OpenPenguin advisory")
    advisory_file = st.file_uploader(
        "OpenPenguin AISuggestion / ActionProposal JSON",
        type=["json"],
        key=f"pl_labbridge_ai_advisory_{profile}",
    )
    if advisory_file:
        try:
            packet = _json_upload(advisory_file)
            check = validate_ai_advisory(packet)
            if check["valid"]:
                st.success("Advisory packet integrity PASS · advisory remains unexecuted.")
            else:
                st.error("; ".join(check["errors"]))
            st.json(packet)
            if st.button(
                "Record advisory in Lab Journey",
                disabled=not check["valid"],
                key=f"pl_labbridge_ai_record_{profile}",
            ):
                out = record_ai_advisory(project_path, packet)
                st.success(f"Recorded {out['journey_event']['event_id']} · executed=false")
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read advisory packet: {exc}")


def render_labbridge(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use LabBridge and Lab Journey.")
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    ingest, journey, ai = st.tabs(["BetterBoard Ingress", "Lab Journey", "OpenPenguin Bridge"])
    with ingest:
        _render_ingest(st, project_path, profile)
    with journey:
        _render_journey(st, project_path, profile)
    with ai:
        _render_openguin(st, project_path, profile)
