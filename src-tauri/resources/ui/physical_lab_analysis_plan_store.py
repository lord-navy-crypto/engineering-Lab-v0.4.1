"""Content-addressed provenance for OpenPenguin scientific analysis plans.

Stored plans are advisory records only. Saving a plan records what OpenPenguin proposed;
it does not execute a capability and does not turn AI output into scientific evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from physical_lab_science_protocol import ANALYSIS_PLAN_SCHEMA, validate_analysis_plan

PLAN_RECORD_SCHEMA = "engineering-lab-ai-analysis-plan-record-v1"


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return str(value)


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(_plain(dict(value)), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def analysis_plan_record(*, plan: Mapping[str, Any], context_packet: Mapping[str, Any]) -> dict[str, Any]:
    check = validate_analysis_plan(plan, context=context_packet)
    if not check["valid"]:
        raise ValueError("invalid analysis plan: " + "; ".join(check["errors"]))
    scientific = context_packet.get("scientific_context") if isinstance(context_packet.get("scientific_context"), Mapping) else {}
    active = scientific.get("active_object") if isinstance(scientific.get("active_object"), Mapping) else None
    stable = {
        "schema": PLAN_RECORD_SCHEMA,
        "plan_schema": ANALYSIS_PLAN_SCHEMA,
        "source_context_packet_id": str(context_packet.get("packet_id") or ""),
        "source_context_sha256": str(context_packet.get("content_sha256") or ""),
        "active_object": _plain(active),
        "plan": _plain(dict(plan)),
        "authority": {
            "record_type": "OpenPenguin advisory provenance",
            "scientific_evidence": False,
            "executed": False,
            "mutation_authority": False,
        },
        "boundary": "This record preserves an AI-proposed analysis plan for auditability. Recording it does not execute any capability or create scientific evidence.",
    }
    digest = _digest(stable)
    return {**stable, "plan_record_id": f"ai-plan-{digest[:20]}", "sha256": digest}


def save_analysis_plan(project_path: str | Path, *, plan: Mapping[str, Any], context_packet: Mapping[str, Any]) -> dict[str, Any]:
    project = Path(project_path).expanduser().resolve()
    if not (project / "project.json").exists():
        raise ValueError("Engineering Lab project is required")
    record = analysis_plan_record(plan=plan, context_packet=context_packet)
    root = project / "provenance" / "ai-analysis-plans"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{record['plan_record_id']}.json"
    if not target.exists():
        target.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return {**record, "path": str(target)}


def verify_analysis_plan_record(record: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if record.get("schema") != PLAN_RECORD_SCHEMA:
        errors.append(f"schema must be {PLAN_RECORD_SCHEMA}")
    authority = record.get("authority") if isinstance(record.get("authority"), Mapping) else {}
    if authority.get("scientific_evidence") is not False:
        errors.append("AI analysis-plan record cannot claim scientific_evidence=true")
    if authority.get("executed") is not False:
        errors.append("AI analysis-plan record cannot claim executed=true")
    if authority.get("mutation_authority") is not False:
        errors.append("AI analysis-plan record cannot claim mutation authority")
    stable = {str(k): _plain(v) for k, v in record.items() if k not in {"plan_record_id", "sha256", "path"}}
    digest = _digest(stable)
    if str(record.get("sha256") or "") != digest:
        errors.append("analysis-plan record sha256 mismatch")
    if str(record.get("plan_record_id") or "") != f"ai-plan-{digest[:20]}":
        errors.append("analysis-plan record ID mismatch")
    return {"valid": not errors, "errors": errors, "calculated_sha256": digest}
