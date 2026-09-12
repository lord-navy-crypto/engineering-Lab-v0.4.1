"""Local BetterBoard measurement discovery for Engineering Lab.

This module is deliberately local-only. It scans the BetterBoard measurement root
on the same machine, verifies LabBridge MeasurementAsset/data fingerprints, and
reports whether a source packet has already been ingested into the active project.
It does not start hardware acquisition or modify BetterBoard sessions.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from physical_lab_experiment_kernel import plain
from physical_lab_labbridge import validate_measurement_asset

DEFAULT_RELATIVE_ROOT = Path("Documents") / "BetterBoard" / "measurements"
MAX_DISCOVERY_SESSIONS = 300


def default_betterboard_measurement_root() -> Path:
    override = os.environ.get("BETTERBOARD_MEASUREMENT_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / DEFAULT_RELATIVE_ROOT).resolve()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _ingested_source_hashes(project_dir: Path) -> set[str]:
    root = project_dir / "provenance" / "labbridge-ingest"
    if not root.is_dir():
        return set()
    output: set[str] = set()
    for path in root.glob("*.json"):
        value = _load_json(path)
        if not value:
            continue
        sha = str(value.get("source_packet_sha256") or "").strip()
        if sha:
            output.add(sha)
    return output


def discover_betterboard_measurements(
    project_dir: str | Path,
    *,
    root: str | Path | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    project_path = Path(project_dir).expanduser().resolve()
    measurement_root = Path(root).expanduser().resolve() if root else default_betterboard_measurement_root()
    limit = max(1, min(int(limit), MAX_DISCOVERY_SESSIONS))
    if not measurement_root.is_dir():
        return []

    ingested = _ingested_source_hashes(project_path)
    candidates = [p for p in measurement_root.iterdir() if p.is_dir()]
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)

    rows: list[dict[str, Any]] = []
    for session in candidates[:limit]:
        data_path = session / "data.csv"
        metadata_path = session / "metadata.json"
        packet_path = session / "labbridge_measurement_asset.json"
        legacy_bridge = session / "physical_lab_bridge.json"
        if not data_path.is_file() or not metadata_path.is_file():
            continue

        metadata = _load_json(metadata_path) or {}
        packet = _load_json(packet_path) if packet_path.is_file() else None
        data_bytes = None
        data_sha = ""
        try:
            data_bytes = data_path.read_bytes()
            data_sha = _sha_bytes(data_bytes)
        except Exception:
            pass

        validation: dict[str, Any] | None = None
        packet_sha = ""
        if packet:
            try:
                validation = validate_measurement_asset(packet, data_bytes)
            except Exception as exc:
                validation = {"valid": False, "errors": [str(exc)], "warnings": []}
            packet_sha = str(packet.get("content_sha256") or "")

        rows.append({
            "session_dir": str(session),
            "session_name": session.name,
            "created_at_utc": str(metadata.get("created_at_utc") or ""),
            "recipe_id": str(metadata.get("recipe_id") or ""),
            "recipe_title": str(metadata.get("recipe_title") or ""),
            "board_profile": str(metadata.get("board_profile") or ""),
            "sample_count": int(metadata.get("sample_count") or 0),
            "data_path": str(data_path),
            "metadata_path": str(metadata_path),
            "packet_path": str(packet_path) if packet_path.is_file() else "",
            "legacy_bridge_path": str(legacy_bridge) if legacy_bridge.is_file() else "",
            "labbridge_ready": bool(packet),
            "labbridge_valid": bool(validation and validation.get("valid")),
            "validation_errors": list((validation or {}).get("errors") or []),
            "validation_warnings": list((validation or {}).get("warnings") or []),
            "packet_id": str((packet or {}).get("packet_id") or ""),
            "packet_sha256": packet_sha,
            "data_sha256": data_sha,
            "already_ingested": bool(packet_sha and packet_sha in ingested),
        })
    return rows


def load_discovered_measurement(session: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
    packet_path = Path(str(session.get("packet_path") or "")).expanduser().resolve()
    data_path = Path(str(session.get("data_path") or "")).expanduser().resolve()
    if not packet_path.is_file():
        raise FileNotFoundError("discovered BetterBoard session has no LabBridge MeasurementAsset packet")
    if not data_path.is_file():
        raise FileNotFoundError("discovered BetterBoard session has no data.csv")
    packet = _load_json(packet_path)
    if packet is None:
        raise ValueError("LabBridge MeasurementAsset JSON is invalid")
    data = data_path.read_bytes()
    check = validate_measurement_asset(packet, data)
    if not check.get("valid"):
        raise ValueError("LabBridge MeasurementAsset failed validation: " + "; ".join(check.get("errors") or []))
    return plain(packet), data
