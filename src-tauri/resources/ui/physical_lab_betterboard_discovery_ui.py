"""Engineering Lab UI for local BetterBoard measurement discovery and evidence inbox."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_betterboard_discovery import (
    default_betterboard_measurement_root,
    discover_betterboard_measurements,
    load_discovered_measurement,
)
from physical_lab_betterboard_inbox import inbox_counts, load_inbox, set_disposition, sync_discovery
from physical_lab_labbridge import ingest_measurement_asset


def render_betterboard_discovery(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to discover BetterBoard measurement sessions.")
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("#### BetterBoard Evidence Inbox")
    st.caption(
        "Scans the local BetterBoard measurement directory on this machine. BetterBoard remains read-only from this view; Engineering Lab stores only project-local inbox disposition and scientific ingest provenance."
    )
    default_root = str(default_betterboard_measurement_root())
    root_text = st.text_input("BetterBoard measurement root", value=default_root, key=f"pl_bb_discovery_root_{profile}")
    limit = st.slider("Sessions to inspect", 10, 200, 60, 10, key=f"pl_bb_discovery_limit_{profile}")

    try:
        sessions = discover_betterboard_measurements(project_path, root=root_text, limit=limit)
        sync_discovery(project_path, sessions)
        inbox = load_inbox(project_path)
        counts = inbox_counts(project_path)
    except Exception as exc:
        st.error(f"BetterBoard discovery failed: {exc}")
        return

    if not sessions:
        st.info("No BetterBoard measurement sessions with data.csv + metadata.json were found under this root.")
        return

    ready = sum(1 for s in sessions if s.get("labbridge_valid"))
    legacy = sum(1 for s in sessions if not s.get("labbridge_ready"))
    a, b, c, d, e = st.columns(5)
    a.metric("Discovered", len(sessions))
    b.metric("LabBridge valid", ready)
    c.metric("NEW", counts.get("new", 0))
    d.metric("Ingested", counts.get("ingested", 0))
    e.metric("Legacy-only", legacy)

    inbox_packets = inbox.get("packets") if isinstance(inbox.get("packets"), dict) else {}
    st.dataframe([
        {
            "created": row.get("created_at_utc"),
            "recipe": row.get("recipe_title") or row.get("recipe_id"),
            "board": row.get("board_profile"),
            "samples": row.get("sample_count"),
            "packet": "valid" if row.get("labbridge_valid") else ("invalid" if row.get("labbridge_ready") else "legacy-only"),
            "inbox": (inbox_packets.get(str(row.get("packet_sha256") or "")) or {}).get("disposition", "—"),
            "data_sha": str(row.get("data_sha256") or "")[:12],
            "session": row.get("session_name"),
        }
        for row in sessions
    ], hide_index=True, width="stretch")

    labels = [
        f"{row.get('created_at_utc') or row.get('session_name')} · {row.get('recipe_title') or row.get('recipe_id') or 'measurement'} · {row.get('session_name')}"
        for row in sessions
    ]
    selected_label = st.selectbox("Inspect discovered session", labels, key=f"pl_bb_discovery_pick_{profile}")
    row = sessions[labels.index(selected_label)]
    packet_sha = str(row.get("packet_sha256") or "")
    inbox_entry = inbox_packets.get(packet_sha) if isinstance(inbox_packets.get(packet_sha), dict) else {}

    x1, x2, x3 = st.columns(3)
    x1.metric("Inbox state", str(inbox_entry.get("disposition") or "—").upper())
    x2.metric("Packet SHA", packet_sha[:14] if packet_sha else "—")
    x3.metric("Source status", "INGESTED" if row.get("already_ingested") else "PENDING")

    with st.expander("Session / packet details", expanded=False):
        st.json({k: v for k, v in row.items() if k not in {"validation_errors", "validation_warnings"}})
        if inbox_entry:
            st.markdown("**Project-local inbox record**")
            st.json(inbox_entry)
    if row.get("validation_errors"):
        st.error("; ".join(row["validation_errors"]))
    if row.get("validation_warnings"):
        st.warning("; ".join(row["validation_warnings"]))

    if not row.get("labbridge_ready"):
        st.warning(
            "This is a legacy BetterBoard measurement session. Generate `labbridge_measurement_asset.json` with the BetterBoard LabBridge v1 exporter or re-save it from a LabBridge-enabled BetterBoard build before scientific ingest."
        )
        return
    if not row.get("labbridge_valid"):
        st.error("The LabBridge packet is present but failed integrity validation; ingest is disabled.")
        return
    if row.get("already_ingested"):
        st.success("This exact source packet SHA has already been ingested into the active Engineering Lab project.")
        return

    note = st.text_input("Inbox note", value=str(inbox_entry.get("note") or ""), key=f"pl_bb_inbox_note_{profile}")
    i1, i2, i3 = st.columns(3)
    if i1.button("Acknowledge", key=f"pl_bb_ack_{profile}"):
        set_disposition(project_path, packet_sha, "acknowledged", note=note)
        st.rerun()
    if i2.button("Ignore for this project", key=f"pl_bb_ignore_{profile}"):
        set_disposition(project_path, packet_sha, "ignored", note=note)
        st.rerun()
    notes = st.text_input("Scientific ingest notes", value="Auto-discovered from local BetterBoard measurement store.", key=f"pl_bb_discovery_notes_{profile}")
    if i3.button("Ingest evidence", type="primary", key=f"pl_bb_discovery_ingest_{profile}"):
        try:
            packet, data = load_discovered_measurement(row)
            out = ingest_measurement_asset(
                project_path,
                packet=packet,
                dataset_bytes=data,
                profile=profile or "betterboard-ingress",
                notes=notes,
            )
            set_disposition(project_path, packet_sha, "ingested", note=note)
        except Exception as exc:
            st.error(f"Ingest failed: {exc}")
            return
        st.success(f"Imported {out['dataset']['dataset_id']} · Journey {out['journey_event']['event_id']}")
        st.rerun()
