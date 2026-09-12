"""Persistent run snapshots for longitudinal staleness detection.

A snapshot freezes the result/contract/environment/source fingerprints observed at a
specific point in the project history. Later software versions can compare that frozen
record against current contracts and environments without rewriting the old evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now

SNAPSHOT_RECORD_SCHEMA = "physical-lab-persisted-run-snapshot-v1"


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value))[:100]


def _root(project_dir: Path) -> Path:
    path = project_dir / "run-snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_run_snapshot(project_dir: str | Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    run_id = str(snapshot.get("run_id") or "").strip()
    result_sha = str(snapshot.get("result_sha256") or "").strip()
    snapshot_sha = str(snapshot.get("snapshot_sha256") or "").strip()
    if not run_id or not result_sha or not snapshot_sha:
        raise ValueError("snapshot requires run_id, result_sha256 and snapshot_sha256")
    stable = {
        "schema": SNAPSHOT_RECORD_SCHEMA,
        "project_id": project.get("project_id"),
        "run_id": run_id,
        "result_sha256": result_sha,
        "snapshot_sha256": snapshot_sha,
        "snapshot": plain(dict(snapshot)),
    }
    digest = _sha(stable)
    record = {
        **stable,
        "record_sha256": digest,
        "captured_at": utc_now(),
        "boundary": "Frozen provenance/comparison snapshot. It preserves the metadata visible when captured and must not be rewritten to match later software state.",
    }
    target = _root(path) / f"{_safe(run_id)}-{result_sha[:12]}-{digest[:12]}.json"
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("record_sha256") == digest:
                return existing
        except Exception:
            pass
    target.write_text(json.dumps(plain(record), indent=2, sort_keys=True), encoding="utf-8")
    return record


def list_run_snapshots(project_dir: str | Path, *, run_id: str | None = None) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    rows = []
    root = _root(path)
    for file in root.glob("*.json"):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(value, dict) or value.get("schema") != SNAPSHOT_RECORD_SCHEMA:
            continue
        if run_id is not None and str(value.get("run_id") or "") != str(run_id):
            continue
        rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda r: str(r.get("captured_at") or ""), reverse=True)
    return rows


def earliest_snapshot_for_result(project_dir: str | Path, *, run_id: str, result_sha256: str) -> dict[str, Any] | None:
    matches = [
        row for row in list_run_snapshots(project_dir, run_id=run_id)
        if str(row.get("result_sha256") or "") == str(result_sha256)
    ]
    if not matches:
        return None
    matches.sort(key=lambda r: str(r.get("captured_at") or ""))
    snap = matches[0].get("snapshot")
    return dict(snap) if isinstance(snap, Mapping) else None


def freeze_if_missing(project_dir: str | Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    existing = earliest_snapshot_for_result(
        project_dir,
        run_id=str(snapshot.get("run_id") or ""),
        result_sha256=str(snapshot.get("result_sha256") or ""),
    )
    if existing is not None:
        return existing
    record = save_run_snapshot(project_dir, snapshot)
    return dict(record["snapshot"])
