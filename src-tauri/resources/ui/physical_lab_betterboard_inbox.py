"""Project-local BetterBoard evidence inbox state.

Inbox state never mutates BetterBoard measurement directories. It stores only local
Engineering Lab dispositions keyed by the immutable LabBridge packet SHA.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now

INBOX_SCHEMA = "engineering-lab-betterboard-inbox-v1"
DISPOSITIONS = {"new", "acknowledged", "ignored", "ingested"}


def _path(project_dir: Path) -> Path:
    root = project_dir / "provenance" / "betterboard-inbox"
    root.mkdir(parents=True, exist_ok=True)
    return root / "inbox.json"


def load_inbox(project_dir: str | Path) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    target = _path(path)
    if not target.exists():
        return {"schema": INBOX_SCHEMA, "project_id": project["project_id"], "packets": {}}
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        value = {}
    if not isinstance(value, dict) or value.get("schema") != INBOX_SCHEMA:
        return {"schema": INBOX_SCHEMA, "project_id": project["project_id"], "packets": {}}
    packets = value.get("packets") if isinstance(value.get("packets"), dict) else {}
    return {"schema": INBOX_SCHEMA, "project_id": project["project_id"], "packets": packets}


def save_inbox(project_dir: str | Path, inbox: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    packets = inbox.get("packets") if isinstance(inbox.get("packets"), Mapping) else {}
    record = {"schema": INBOX_SCHEMA, "project_id": project["project_id"], "updated_at": utc_now(), "packets": plain(dict(packets))}
    target = _path(path)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return record


def sync_discovery(project_dir: str | Path, sessions: list[Mapping[str, Any]]) -> dict[str, Any]:
    inbox = load_inbox(project_dir)
    packets = dict(inbox.get("packets") or {})
    now = utc_now()
    for row in sessions:
        sha = str(row.get("packet_sha256") or "").strip()
        if not sha:
            continue
        current = packets.get(sha) if isinstance(packets.get(sha), dict) else {}
        disposition = "ingested" if row.get("already_ingested") else str(current.get("disposition") or "new")
        if disposition not in DISPOSITIONS:
            disposition = "new"
        packets[sha] = {
            "packet_sha256": sha,
            "packet_id": str(row.get("packet_id") or current.get("packet_id") or ""),
            "session_name": str(row.get("session_name") or current.get("session_name") or ""),
            "recipe_title": str(row.get("recipe_title") or current.get("recipe_title") or ""),
            "created_at_utc": str(row.get("created_at_utc") or current.get("created_at_utc") or ""),
            "first_seen_at": str(current.get("first_seen_at") or now),
            "last_seen_at": now,
            "labbridge_valid": bool(row.get("labbridge_valid")),
            "disposition": disposition,
            "note": str(current.get("note") or ""),
        }
    inbox["packets"] = packets
    return save_inbox(project_dir, inbox)


def set_disposition(project_dir: str | Path, packet_sha256: str, disposition: str, *, note: str = "") -> dict[str, Any]:
    disposition = str(disposition).strip().lower()
    if disposition not in DISPOSITIONS:
        raise ValueError(f"unsupported BetterBoard inbox disposition: {disposition}")
    sha = str(packet_sha256).strip()
    if not sha:
        raise ValueError("packet_sha256 is required")
    inbox = load_inbox(project_dir)
    packets = dict(inbox.get("packets") or {})
    current = packets.get(sha) if isinstance(packets.get(sha), dict) else {"packet_sha256": sha, "first_seen_at": utc_now()}
    current.update({"disposition": disposition, "note": str(note).strip(), "updated_at": utc_now()})
    packets[sha] = current
    inbox["packets"] = packets
    save_inbox(project_dir, inbox)
    return current


def inbox_counts(project_dir: str | Path) -> dict[str, int]:
    packets = (load_inbox(project_dir).get("packets") or {}).values()
    counts = {key: 0 for key in DISPOSITIONS}
    for row in packets:
        if isinstance(row, Mapping):
            key = str(row.get("disposition") or "new")
            if key in counts:
                counts[key] += 1
    counts["total"] = sum(counts.values())
    return counts
