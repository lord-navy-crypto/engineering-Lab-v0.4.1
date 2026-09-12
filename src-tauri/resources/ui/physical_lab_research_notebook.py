"""Evidence-linked Experiment Notebook and Annotation system for Engineering Lab.

Notebook entries and annotations are project assets with stable SHA-256 identities.
Each creation is also appended to Lab Journey so the chronological process and the
structured research artifact remain linked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now
from physical_lab_lab_journey import append_event

NOTE_SCHEMA = "engineering-lab-notebook-entry-v1"
ANNOTATION_SCHEMA = "engineering-lab-annotation-v1"
NOTE_KINDS = {"hypothesis", "observation", "interpretation", "decision", "method", "limitation"}
TARGET_TYPES = {"dataset", "result", "run", "experiment", "plot", "journey-event", "measurement", "workflow", "freeform"}


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _root(project_dir: Path, name: str) -> Path:
    root = project_dir / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != plain(dict(value)):
            raise FileExistsError(f"content-addressed artifact collision: {path}")
        return
    path.write_text(json.dumps(plain(dict(value)), indent=2, sort_keys=True), encoding="utf-8")


def add_notebook_entry(
    project_dir: str | Path,
    *,
    kind: str,
    title: str,
    text: str,
    evidence_refs: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    author_role: str = "human",
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    kind = str(kind).strip()
    if kind not in NOTE_KINDS:
        raise ValueError(f"unsupported notebook kind: {kind}")
    if not str(title).strip() or not str(text).strip():
        raise ValueError("notebook title and text are required")
    stable = {
        "schema": NOTE_SCHEMA,
        "project_id": project["project_id"],
        "created_at": utc_now(),
        "kind": kind,
        "title": str(title).strip(),
        "text": str(text).strip(),
        "evidence_refs": [str(x) for x in (evidence_refs or []) if str(x)],
        "tags": sorted({str(x).strip() for x in (tags or []) if str(x).strip()}),
        "author_role": str(author_role),
    }
    digest = _sha(stable)
    record = {**stable, "entry_id": f"note-{digest[:20]}", "sha256": digest}
    _write_once(_root(path, "notebook") / f"{record['entry_id']}.json", record)
    event_type = kind if kind in {"hypothesis", "observation", "decision"} else "annotation"
    journey = append_event(
        path,
        event_type=event_type,
        source_role="human" if author_role == "human" else "engineering-lab",
        title=f"Notebook · {record['title']}",
        body=record["text"],
        evidence_refs=[record["entry_id"], *record["evidence_refs"]],
        payload={"notebook_kind": kind, "tags": record["tags"], "notebook_sha256": digest},
    )
    return {"entry": record, "journey_event": journey}


def add_annotation(
    project_dir: str | Path,
    *,
    target_type: str,
    target_id: str,
    label: str,
    note: str,
    locator: Mapping[str, Any] | None = None,
    tags: Sequence[str] | None = None,
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    target_type = str(target_type).strip()
    if target_type not in TARGET_TYPES:
        raise ValueError(f"unsupported annotation target type: {target_type}")
    if not str(target_id).strip() or not str(label).strip() or not str(note).strip():
        raise ValueError("annotation target_id, label and note are required")
    stable = {
        "schema": ANNOTATION_SCHEMA,
        "project_id": project["project_id"],
        "created_at": utc_now(),
        "target": {"type": target_type, "id": str(target_id).strip()},
        "label": str(label).strip(),
        "note": str(note).strip(),
        "locator": plain(dict(locator or {})),
        "tags": sorted({str(x).strip() for x in (tags or []) if str(x).strip()}),
    }
    digest = _sha(stable)
    record = {**stable, "annotation_id": f"annotation-{digest[:20]}", "sha256": digest}
    _write_once(_root(path, "annotations") / f"{record['annotation_id']}.json", record)
    journey = append_event(
        path,
        event_type="annotation",
        source_role="human",
        title=f"Annotation · {record['label']}",
        body=record["note"],
        evidence_refs=[record["annotation_id"], str(target_id)],
        payload={"target": record["target"], "locator": record["locator"], "annotation_sha256": digest, "tags": record["tags"]},
    )
    return {"annotation": record, "journey_event": journey}


def _list_records(project_dir: Path, folder: str, schema: str, id_key: str) -> list[dict[str, Any]]:
    projects.open_project(project_dir)
    root = project_dir / folder
    if not root.exists():
        return []
    rows = []
    for file in root.glob("*.json"):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("schema") == schema and value.get(id_key):
            rows.append(value)
    rows.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get(id_key) or "")), reverse=True)
    return rows


def list_notebook_entries(project_dir: str | Path) -> list[dict[str, Any]]:
    return _list_records(Path(project_dir).expanduser().resolve(), "notebook", NOTE_SCHEMA, "entry_id")


def list_annotations(project_dir: str | Path, *, target_id: str | None = None) -> list[dict[str, Any]]:
    rows = _list_records(Path(project_dir).expanduser().resolve(), "annotations", ANNOTATION_SCHEMA, "annotation_id")
    if target_id is not None:
        rows = [r for r in rows if str((r.get("target") or {}).get("id") or "") == str(target_id)]
    return rows


def verify_record(record: Mapping[str, Any]) -> dict[str, Any]:
    schema = record.get("schema")
    if schema == NOTE_SCHEMA:
        excluded = {"entry_id", "sha256"}
        expected_id = "note-"
    elif schema == ANNOTATION_SCHEMA:
        excluded = {"annotation_id", "sha256"}
        expected_id = "annotation-"
    else:
        return {"valid": False, "error": "unsupported research-record schema"}
    stable = {k: plain(v) for k, v in record.items() if k not in excluded}
    digest = _sha(stable)
    identifier = str(record.get("entry_id") or record.get("annotation_id") or "")
    return {
        "valid": str(record.get("sha256") or "") == digest and identifier == f"{expected_id}{digest[:20]}",
        "calculated_sha256": digest,
    }
