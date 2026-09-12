"""Live local coordinator for BetterBoard -> Engineering Lab -> OpenPenguin.

This module coordinates the canonical LabBridge components. It intentionally does
not introduce another transport or schema family.

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
from physical_lab_openguin_adapter import OPENPENGUIN_BASE, probe_openguin, request_advisory


def sync_betterboard_link(
    project_dir: str | Path,
    *,
    measurement_root: str | Path | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Refresh local BetterBoard evidence discovery and the Engineering Lab inbox.

    This is read-only toward BetterBoard. A valid packet becomes visible as NEW or
    known evidence; canonical dataset ingest remains a separate explicit action.
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
    """Return the normalized OpenPenguin LabBridge capability record."""
    return probe_openguin()


def _external_ollama_fallback() -> Mapping[str, Any]:
    """Resolve a non-OpenPenguin loopback runtime only when the caller opted in."""
    for engine in discover_local_ai_engines():
        label = str(engine.get("label") or "")
        if engine.get("running") and not label.startswith("OpenPenguin"):
            return engine
    raise RuntimeError("No explicit external Ollama fallback is available")


def _fallback_advisory(
    context: Mapping[str, Any],
    *,
    question: str,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    engine = _external_ollama_fallback()
    models = [str(item) for item in engine.get("models", []) if str(item).strip()]
    selected_model = str(model).strip() or (models[0] if models else "")
    if not selected_model:
        raise RuntimeError("external Ollama fallback has no installed model")
    if models and selected_model not in models:
        raise ValueError("requested model is not installed in the external Ollama fallback")
    answer = ask_local_model(
        str(engine.get("base") or ""),
        selected_model,
        question,
        context,
        temperature=float(temperature),
    )
    return finalize_packet(
        {
            "schema": AI_SUGGESTION_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "ai_suggestion",
            "source_app": {
                "name": "External Ollama",
                "role": "local-ai-advisory-fallback",
                "model": selected_model,
                "runtime": str(engine.get("base") or ""),
            },
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "title": f"External local advisory · {question[:80]}",
            "summary": answer[:200000],
            "question": question,
            "evidence_refs": [str(context.get("packet_id") or "")],
            "executed": False,
            "scientific_boundary": "Fallback AI output is advisory only and cannot mutate Engineering Lab evidence or execute an experiment.",
        },
        prefix="ai-suggestion",
    )


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
    """Ask OpenPenguin using canonical Engineering Lab AIContext.

    The dedicated OpenPenguin adapter is authoritative for runtime negotiation: it
    prefers the native LabBridge API and falls back to OpenPenguin's current
    Ollama-compatible loopback surface at 127.0.0.1:11435. External Ollama is used
    only when ``allow_ollama_fallback`` is explicitly enabled.

    Recording is opt-in; recorded output remains an AISuggestion/Lab Journey event,
    never a measurement or solver result.
    """
    question = str(question).strip()
    if not question:
        raise ValueError("question is required")

    context = build_ai_context_packet(project_dir, profile=profile, focus=focus)
    status = probe_openguin()
    if status.get("available"):
        models = [str(item) for item in status.get("models", []) if str(item).strip()]
        selected_model = str(model).strip() or (models[0] if models else "")
        if not selected_model:
            raise RuntimeError("OpenPenguin is available but reports no installed model")
        if models and selected_model not in models:
            raise ValueError("requested model is not installed in OpenPenguin")
        packet = request_advisory(
            context,
            question=question,
            model=selected_model,
            temperature=float(temperature),
        )
        runtime = {
            "provider": "OpenPenguin",
            "mode": status.get("mode"),
            "base": status.get("base") or OPENPENGUIN_BASE,
            "model": selected_model,
        }
    elif allow_ollama_fallback:
        packet = _fallback_advisory(
            context,
            question=question,
            model=model,
            temperature=float(temperature),
        )
        runtime = {"provider": "external-ollama-fallback"}
    else:
        raise RuntimeError("OpenPenguin private runtime is unavailable; external Ollama fallback was not authorized")

    if evidence_refs:
        refs = list(packet.get("evidence_refs") or [])
        refs.extend(str(ref) for ref in evidence_refs if str(ref).strip())
        packet["evidence_refs"] = list(dict.fromkeys(refs))[:200]
        packet = finalize_packet(
            {key: value for key, value in packet.items() if key not in {"packet_id", "content_sha256"}},
            prefix="ai-suggestion",
        )

    packet["executed"] = False
    recorded = record_ai_advisory(project_dir, packet) if record else None
    return {
        "context": context,
        "suggestion": packet,
        "runtime": runtime,
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
