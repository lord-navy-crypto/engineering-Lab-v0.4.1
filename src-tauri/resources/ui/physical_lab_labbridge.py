"""LabBridge v1 interoperability core for BetterBoard, Engineering Lab and OpenPenguin.

Authority model:
- BetterBoard is the real-world ingress and produces MeasurementAsset packets.
- Engineering Lab is the scientific computation/evidence core and validates/ingests
  measurement packets into project datasets/provenance.
- OpenPenguin is an advisory local-AI layer. AI suggestions/action proposals are
  evidence-linked records and never execute scientific actions automatically.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now
from physical_lab_lab_journey import append_event, list_events
from physical_lab_project_interop import list_canonical_datasets, save_canonical_dataset
from physical_lab_research_orchestrator import parse_numeric_table

MEASUREMENT_SCHEMA = "labbridge.measurement-asset/v1"
AI_CONTEXT_SCHEMA = "labbridge.ai-context/v1"
AI_SUGGESTION_SCHEMA = "labbridge.ai-suggestion/v1"
ACTION_PROPOSAL_SCHEMA = "labbridge.action-proposal/v1"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return _sha_bytes(raw)


def _packet_stable(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {k: plain(v) for k, v in packet.items() if k not in {"packet_id", "content_sha256"}}


def _packet_digest(packet: Mapping[str, Any]) -> str:
    return _sha_json(_packet_stable(packet))


def finalize_packet(packet: Mapping[str, Any], *, prefix: str) -> dict[str, Any]:
    stable = _packet_stable(packet)
    digest = _sha_json(stable)
    return {**stable, "packet_id": f"{prefix}-{digest[:20]}", "content_sha256": digest}


def validate_measurement_asset(packet: Mapping[str, Any], dataset_bytes: bytes | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("schema") != MEASUREMENT_SCHEMA:
        errors.append(f"schema must be {MEASUREMENT_SCHEMA}")
    if packet.get("packet_type") != "measurement_asset":
        errors.append("packet_type must be measurement_asset")
    source = packet.get("source_app") if isinstance(packet.get("source_app"), Mapping) else {}
    if source.get("name") != "BetterBoard":
        warnings.append("source_app.name is not BetterBoard")
    if source.get("role") != "real-world-ingress":
        errors.append("source_app.role must be real-world-ingress")
    consumer = packet.get("intended_consumer") if isinstance(packet.get("intended_consumer"), Mapping) else {}
    if consumer.get("name") != "Engineering Lab":
        warnings.append("intended consumer is not Engineering Lab")

    dataset = packet.get("dataset") if isinstance(packet.get("dataset"), Mapping) else {}
    if dataset.get("format") not in {"text/csv", "csv"}:
        errors.append("dataset format must be CSV")
    supplied_dataset_sha = str(dataset.get("sha256") or "")
    if len(supplied_dataset_sha) != 64:
        errors.append("dataset.sha256 must be a SHA-256 hex digest")
    if dataset_bytes is not None and supplied_dataset_sha != _sha_bytes(dataset_bytes):
        errors.append("dataset SHA-256 does not match supplied dataset bytes")

    columns = dataset.get("columns") if isinstance(dataset.get("columns"), list) else []
    names = []
    for item in columns:
        if not isinstance(item, Mapping):
            errors.append("dataset.columns entries must be objects")
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            errors.append("every dataset column requires a name")
        names.append(name)
    if not columns:
        errors.append("dataset.columns must not be empty")
    if len(names) != len(set(names)):
        errors.append("dataset column names must be unique")

    digest = _packet_digest(packet)
    supplied_packet_sha = str(packet.get("content_sha256") or "")
    packet_id = str(packet.get("packet_id") or "")
    if supplied_packet_sha != digest:
        errors.append("packet content_sha256 does not match packet content")
    if packet_id != f"measurement-{digest[:20]}":
        errors.append("packet_id does not match packet content fingerprint")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "calculated_content_sha256": digest,
        "boundary": (
            "Structural/integrity validation only. A valid MeasurementAsset does not establish sensor calibration, "
            "traceability, accuracy, or experimental validation."
        ),
    }


def _ingest_root(project_dir: Path) -> Path:
    root = project_dir / "provenance" / "labbridge-ingest"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ingest_measurement_asset(
    project_dir: str | Path,
    *,
    packet: Mapping[str, Any],
    dataset_bytes: bytes,
    profile: str = "measurement-bridge",
    notes: str = "",
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    check = validate_measurement_asset(packet, dataset_bytes)
    if not check["valid"]:
        raise ValueError("invalid LabBridge MeasurementAsset: " + "; ".join(check["errors"]))

    parsed = parse_numeric_table(dataset_bytes, str((packet.get("dataset") or {}).get("path") or "data.csv"))
    packet_columns = list((packet.get("dataset") or {}).get("columns") or [])
    declared_names = [str(row.get("name")) for row in packet_columns if isinstance(row, Mapping)]
    missing = [name for name in declared_names if name not in parsed.get("column_data", {})]
    if missing:
        raise ValueError("measurement CSV is missing declared column(s): " + ", ".join(missing))
    numeric_names = [name for name in declared_names if name in set(parsed.get("numeric_columns") or [])]
    if not numeric_names:
        raise ValueError("measurement asset contains no numeric declared column")
    units = {
        str(row.get("name")): str(row.get("unit") or "")
        for row in packet_columns if isinstance(row, Mapping) and str(row.get("name") or "") in numeric_names
    }
    columns = {name: parsed["column_data"][name] for name in numeric_names}
    acquisition = packet.get("acquisition") if isinstance(packet.get("acquisition"), Mapping) else {}
    device = packet.get("device") if isinstance(packet.get("device"), Mapping) else {}
    dataset = save_canonical_dataset(
        path,
        name=f"BetterBoard · {acquisition.get('recipe_title') or acquisition.get('recipe_id') or 'measurement'}",
        profile=profile,
        columns=columns,
        units=units,
        source=f"LabBridge:{packet.get('packet_id')}",
        notes=str(notes),
    )
    stable = {
        "schema": "engineering-lab-labbridge-ingest-v1",
        "project_id": project["project_id"],
        "source_packet_id": packet.get("packet_id"),
        "source_packet_sha256": packet.get("content_sha256"),
        "source_dataset_sha256": (packet.get("dataset") or {}).get("sha256"),
        "generated_dataset_id": dataset["dataset_id"],
        "generated_dataset_sha256": dataset["sha256"],
        "source_app": plain(packet.get("source_app") or {}),
        "device": plain(device),
        "acquisition": plain(acquisition),
        "primary_observable": packet.get("primary_observable"),
        "imported_at": utc_now(),
    }
    digest = _sha_json(stable)
    provenance = {**stable, "ingest_id": f"labbridge-ingest-{digest[:20]}", "sha256": digest}
    target = _ingest_root(path) / f"{provenance['ingest_id']}.json"
    target.write_text(json.dumps(plain(provenance), indent=2, sort_keys=True), encoding="utf-8")
    event = append_event(
        path,
        event_type="measurement_import",
        source_role="betterboard",
        title=f"Imported BetterBoard measurement · {acquisition.get('recipe_title') or acquisition.get('recipe_id') or packet.get('packet_id')}",
        body="LabBridge MeasurementAsset validated and promoted into an Engineering Lab canonical dataset.",
        evidence_refs=[str(packet.get("packet_id") or ""), dataset["dataset_id"], provenance["ingest_id"]],
        payload={
            "dataset_sha256": dataset["sha256"],
            "source_dataset_sha256": (packet.get("dataset") or {}).get("sha256"),
            "firmware_sha256": device.get("firmware_sha256"),
        },
    )
    return {"dataset": dataset, "provenance": provenance, "journey_event": event, "validation": check}


def build_ai_context_packet(project_dir: str | Path, *, profile: str = "", focus: str = "") -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    datasets = list_canonical_datasets(path)[:30]
    journey = list_events(path, limit=40)
    environment = None
    try:
        from physical_lab_environment_manifest import build_environment_manifest
        environment = build_environment_manifest(extra={"active_profile": profile})
    except Exception:
        environment = None
    stable = {
        "schema": AI_CONTEXT_SCHEMA,
        "bridge_version": "1.0",
        "packet_type": "ai_context",
        "source_app": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
        "intended_consumer": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
        "project": {
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "research_question": project.get("research_question"),
            "profiles": list(project.get("profiles") or []),
            "experiment_count": len(project.get("experiments") or {}),
            "result_count": len(project.get("results") or {}),
        },
        "active_profile": str(profile),
        "focus": str(focus),
        "datasets": [
            {
                "dataset_id": row.get("dataset_id"),
                "name": row.get("name"),
                "profile": row.get("profile"),
                "row_count": row.get("row_count"),
                "units": row.get("units"),
                "sha256": row.get("sha256"),
            }
            for row in datasets
        ],
        "journey_events": [
            {
                "event_id": row.get("event_id"), "sequence": row.get("sequence"),
                "event_type": row.get("event_type"), "source_role": row.get("source_role"),
                "title": row.get("title"), "body": row.get("body"),
                "evidence_refs": row.get("evidence_refs"), "event_sha256": row.get("event_sha256"),
            }
            for row in journey
        ],
        "environment": environment,
        "authority": {
            "measurements": "BetterBoard/registered measurement evidence",
            "scientific_record": "Engineering Lab",
            "ai_output": "advisory only; never authoritative measurement/solver/validation state",
        },
        "boundary": (
            "OpenPenguin may explain evidence and propose next actions. It must not invent measurements, overwrite solver results, "
            "claim validation, or execute an ActionProposal without an explicit human/system approval step."
        ),
    }
    return finalize_packet(stable, prefix="ai-context")


def validate_ai_advisory(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    schema = str(packet.get("schema") or "")
    if schema not in {AI_SUGGESTION_SCHEMA, ACTION_PROPOSAL_SCHEMA}:
        errors.append("unsupported AI advisory schema")
    source = packet.get("source_app") if isinstance(packet.get("source_app"), Mapping) else {}
    if source.get("name") != "OpenPenguin" or source.get("role") != "local-ai-advisory-layer":
        errors.append("AI advisory must identify OpenPenguin as local-ai-advisory-layer")
    if packet.get("executed") is True:
        errors.append("AI advisory packets cannot claim executed=true")
    if not str(packet.get("summary") or packet.get("title") or "").strip():
        errors.append("AI advisory requires a summary/title")
    if schema == ACTION_PROPOSAL_SCHEMA:
        for key in ("target", "rationale", "expected_effect", "falsification_observable"):
            if not str(packet.get(key) or "").strip():
                errors.append(f"ActionProposal requires {key}")
    digest = _packet_digest(packet)
    if str(packet.get("content_sha256") or "") != digest:
        errors.append("AI advisory content_sha256 mismatch")
    prefix = "action-proposal" if schema == ACTION_PROPOSAL_SCHEMA else "ai-suggestion"
    if str(packet.get("packet_id") or "") != f"{prefix}-{digest[:20]}":
        errors.append("AI advisory packet_id mismatch")
    return {"valid": not errors, "errors": errors, "calculated_content_sha256": digest}


def record_ai_advisory(project_dir: str | Path, packet: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    check = validate_ai_advisory(packet)
    if not check["valid"]:
        raise ValueError("invalid OpenPenguin advisory: " + "; ".join(check["errors"]))
    root = path / "provenance" / "ai-proposals"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{packet['packet_id']}.json"
    if not target.exists():
        target.write_text(json.dumps(plain(dict(packet)), indent=2, sort_keys=True), encoding="utf-8")
    event_type = "action_proposal" if packet.get("schema") == ACTION_PROPOSAL_SCHEMA else "ai_suggestion"
    event = append_event(
        path,
        event_type=event_type,
        source_role="openguin",
        title=str(packet.get("title") or packet.get("summary") or packet.get("packet_id")),
        body=str(packet.get("summary") or ""),
        evidence_refs=[str(packet.get("packet_id"))] + [str(x) for x in packet.get("evidence_refs", []) if str(x)],
        payload={"schema": packet.get("schema"), "target": packet.get("target"), "executed": False},
    )
    return {"packet": plain(dict(packet)), "journey_event": event, "validation": check, "executed": False}
