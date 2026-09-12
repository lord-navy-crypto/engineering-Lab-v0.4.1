"""Live local coordinator for BetterBoard -> Engineering Lab -> OpenPenguin.

This module deliberately coordinates existing LabBridge components instead of
inventing another protocol family.

Authority boundaries:
- BetterBoard MeasurementAsset packets are immutable acquisition evidence.
- Engineering Lab remains the scientific system of record.
- OpenPenguin remains advisory only.
- Discovery never auto-ingests a measurement.
- AI output is never recorded unless the caller explicitly requests it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from physical_lab_betterboard_discovery import discover_betterboard_measurements
from physical_lab_betterboard_inbox import inbox_counts, sync_discovery
from physical_lab_labbridge import (
    AI_SUGGESTION_SCHEMA,
    build_ai_context_packet,
    finalize_packet,
    record_ai_advisory,
)
from physical_lab_local_ai import ask_local_model, discover_local_ai_engines

OPENPENGUIN_LABEL = "OpenPenguin private runtime"


def sync_betterboard_link(
    project_dir: str | Path,
    *,
    measurement_root: str | Path | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Refresh local BetterBoard evidence discovery and the Engineering Lab inbox.

    This is intentionally read-only toward BetterBoard. A valid packet becomes
    visible as NEW/known evidence; it is not promoted into a canonical dataset
    until a separate explicit ingest action is performed.
    """
    sessions = discover_betterboard_measurements(
        project_dir,
        root=measurement_root,
        limit=limit,
    )
    inbox = sync_discovery(project_dir, sessions)
    valid_new = []
    for row in sessions:
        if not row.get("labbridge_valid") or row.get("already_ingested"):
            continue
        packet_sha = str(row.get("packet_sha256") or "")
        inbox_row = (inbox.get("packets") or {}).get(packet_sha, {}) if packet_sha else {}
        if str(inbox_row.get("disposition") or "new") == "new":
            valid_new.append(dict(row))
    return {
        "sessions": sessions,
        "valid_new": valid_new,
        "counts": inbox_counts(project_dir),
        "policy": {
            "betterboard_source_read_only": True,
            "auto_ingest": False,
        },
    }


def openpenguin_status() -> dict[str, Any]:
    """Return bounded local runtime status, preferring the private OpenPenguin runtime."""
    engines = discover_local_ai_engines()
    preferred = next((row for row in engines if row.get("label") == OPENPENGUIN_LABEL), None)
    return {
        "openpenguin": preferred or {"label": OPENPENGUIN_LABEL, "running": False, "models": []},
        "local_engines": engines,
    }


def _select_engine(*, allow_ollama_fallback: bool) -> Mapping[str, Any]:
    engines = discover_local_ai_engines()
    preferred = next(
        (row for row in engines if row.get("label") == OPENPENGUIN_LABEL and row.get("running")),
        None,
    )
    if preferred is not None:
        return preferred
    if allow_ollama_fallback:
        fallback = next((row for row in engines if row.get("running")), None)
        if fallback is not None:
            return fallback
    raise RuntimeError("OpenPenguin private runtime is not available on loopback port 11435")


def ask_openguin_about_project(
    project_dir: str | Path,
    *,
    question: str,
    focus: str = "",
    profile: str = "",
    model: str = "",
    temperature: float = 0.2,
    evidence_refs: list[str] | None = None,
    record: bool = False,
    allow_ollama_fallback: bool = False,
) -> dict[str, Any]:
    """Ask OpenPenguin using canonical Engineering Lab LabBridge context.

    Recording is opt-in. Even when recorded, the response is persisted only as an
    ``labbridge.ai-suggestion/v1`` advisory packet and Lab Journey event.
    """
    question = str(question).strip()
    if not question:
        raise ValueError("question is required")

    context = build_ai_context_packet(project_dir, profile=profile, focus=focus)
    engine = _select_engine(allow_ollama_fallback=allow_ollama_fallback)
    models = [str(item) for item in engine.get("models", []) if str(item).strip()]
    selected_model = str(model).strip()
    if selected_model:
        if selected_model not in models:
            raise ValueError("requested model is not installed in the selected local runtime")
    else:
        if not models:
            raise RuntimeError("selected local AI runtime has no installed model")
        selected_model = models[0]

    answer = ask_local_model(
        str(engine.get("base") or ""),
        selected_model,
        question,
        context,
        temperature=float(temperature),
    )
    stable = {
        "schema": AI_SUGGESTION_SCHEMA,
        "bridge_version": "1.0",
        "packet_type": "ai_suggestion",
        "source_app": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
        "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
        "title": "OpenPenguin LabBridge suggestion",
        "summary": answer,
        "question": question,
        "context_packet_id": context.get("packet_id"),
        "context_sha256": context.get("content_sha256"),
        "evidence_refs": list(evidence_refs or []),
        "runtime": {"label": engine.get("label"), "base": engine.get("base"), "model": selected_model},
        "executed": False,
        "scientific_boundary": (
            "OpenPenguin output is advisory. It is not a measurement, solver result, fitted quantity, "
            "uncertainty statement, verification result, or validation claim."
        ),
    }
    packet = finalize_packet(stable, prefix="ai-suggestion")
    recorded = record_ai_advisory(project_dir, packet) if record else None
    return {
        "context": context,
        "suggestion": packet,
        "recorded": recorded,
        "recording_policy": "explicit-opt-in",
    }


def bridge_status(
    project_dir: str | Path,
    *,
    measurement_root: str | Path | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """One non-destructive status pass across all three products."""
    betterboard = sync_betterboard_link(project_dir, measurement_root=measurement_root, limit=limit)
    return {
        "schema": "labbridge.link-status/v1",
        "betterboard": betterboard,
        "openguin": openpenguin_status(),
        "authority": {
            "measurement": "BetterBoard",
            "scientific_record": "Engineering Lab",
            "ai": "OpenPenguin advisory only",
        },
        "automatic_actions": {
            "measurement_ingest": False,
            "ai_recording": False,
            "action_proposal_execution": False,
        },
    }
