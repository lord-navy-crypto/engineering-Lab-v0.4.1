"""Append-only Lab Journey event log for Engineering Lab projects.

The journey records research-process events across BetterBoard, Engineering Lab,
OpenPenguin and the human researcher. Events form a local SHA-256 hash chain so
later edits/reordering can be detected. This is provenance evidence, not external
notarization: a filesystem owner could rewrite the whole chain.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now

EVENT_SCHEMA = "engineering-lab-journey-event-v1"
INDEX_SCHEMA = "engineering-lab-journey-index-v1"
ALLOWED_EVENT_TYPES = {
    "measurement_import", "dataset_materialization", "experiment_run",
    "annotation", "observation", "hypothesis", "ai_suggestion",
    "action_proposal", "decision", "system",
}
ALLOWED_SOURCE_ROLES = {"betterboard", "engineering-lab", "openguin", "human"}


def _sha_json(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _root(project_dir: Path) -> Path:
    root = project_dir / "journey"
    (root / "events").mkdir(parents=True, exist_ok=True)
    return root


def _index_path(project_dir: Path) -> Path:
    return _root(project_dir) / "index.json"


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(plain(dict(value)), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_index(project_dir: Path, project_id: str) -> dict[str, Any]:
    path = _index_path(project_dir)
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("schema") == INDEX_SCHEMA and value.get("project_id") == project_id:
                return value
        except Exception:
            pass
    return {
        "schema": INDEX_SCHEMA,
        "project_id": project_id,
        "event_count": 0,
        "head_sha256": None,
        "events": [],
    }


def append_event(
    project_dir: str | Path,
    *,
    event_type: str,
    source_role: str,
    title: str,
    body: str = "",
    evidence_refs: Sequence[str] | None = None,
    payload: Mapping[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    event_type = str(event_type).strip()
    source_role = str(source_role).strip()
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"unsupported journey event type: {event_type}")
    if source_role not in ALLOWED_SOURCE_ROLES:
        raise ValueError(f"unsupported journey source role: {source_role}")
    if not str(title).strip():
        raise ValueError("journey event title is required")

    index = _load_index(path, str(project["project_id"]))
    sequence = int(index.get("event_count") or 0) + 1
    previous = index.get("head_sha256")
    stable = {
        "schema": EVENT_SCHEMA,
        "project_id": project["project_id"],
        "sequence": sequence,
        "created_at": created_at or utc_now(),
        "event_type": event_type,
        "source_role": source_role,
        "title": str(title).strip(),
        "body": str(body),
        "evidence_refs": [str(x) for x in (evidence_refs or []) if str(x)],
        "payload": plain(dict(payload or {})),
        "previous_event_sha256": previous,
    }
    digest = _sha_json(stable)
    event = {
        **stable,
        "event_id": f"journey-{sequence:06d}-{digest[:16]}",
        "event_sha256": digest,
        "boundary": (
            "Research-process provenance. Hash chaining detects edits/reordering after capture, "
            "but this local log is not externally notarized and does not certify scientific validity."
        ),
    }
    rel = Path("events") / f"{sequence:06d}-{digest[:16]}.json"
    target = _root(path) / rel
    if target.exists():
        raise FileExistsError(target)
    _atomic_json(target, event)

    events = list(index.get("events") or [])
    events.append(rel.as_posix())
    new_index = {
        "schema": INDEX_SCHEMA,
        "project_id": project["project_id"],
        "event_count": sequence,
        "head_sha256": digest,
        "events": events,
    }
    _atomic_json(_index_path(path), new_index)
    return event


def list_events(project_dir: str | Path, *, limit: int = 500) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    index = _load_index(path, str(project["project_id"]))
    rows: list[dict[str, Any]] = []
    for rel in list(index.get("events") or [])[-max(1, min(int(limit), 5000)):]:
        file = _root(path) / str(rel)
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("schema") == EVENT_SCHEMA:
            rows.append(value)
    return rows


def verify_journey(project_dir: str | Path) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    index = _load_index(path, str(project["project_id"]))
    issues: list[dict[str, Any]] = []
    previous = None
    verified = 0
    for expected_sequence, rel in enumerate(list(index.get("events") or []), start=1):
        file = _root(path) / str(rel)
        try:
            event = json.loads(file.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append({"code": "EVENT_UNREADABLE", "path": str(rel), "message": str(exc)})
            continue
        supplied = str(event.get("event_sha256") or "")
        stable = {k: v for k, v in event.items() if k not in {"event_id", "event_sha256", "boundary"}}
        calculated = _sha_json(stable)
        if supplied != calculated:
            issues.append({"code": "EVENT_HASH_MISMATCH", "path": str(rel), "message": "event content hash mismatch"})
        if int(event.get("sequence") or -1) != expected_sequence:
            issues.append({"code": "SEQUENCE_MISMATCH", "path": str(rel), "message": "event sequence is not contiguous"})
        if event.get("previous_event_sha256") != previous:
            issues.append({"code": "CHAIN_LINK_MISMATCH", "path": str(rel), "message": "previous-event hash does not match chain head"})
        previous = supplied
        verified += 1
    if int(index.get("event_count") or 0) != len(index.get("events") or []):
        issues.append({"code": "INDEX_COUNT_MISMATCH", "message": "index event_count does not match event list"})
    if (index.get("head_sha256") or None) != previous:
        issues.append({"code": "INDEX_HEAD_MISMATCH", "message": "index head hash does not match final event"})
    return {
        "valid": not issues,
        "verified_events": verified,
        "head_sha256": previous,
        "issues": issues,
        "boundary": "Local integrity verification only; not external notarization or scientific validation.",
    }
