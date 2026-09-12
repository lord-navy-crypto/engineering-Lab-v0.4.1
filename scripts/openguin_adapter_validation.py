#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_openguin_adapter as adapter
    from physical_lab_labbridge import finalize_packet, validate_ai_advisory

    context = finalize_packet({
        "schema": "labbridge.ai-context/v1",
        "bridge_version": "1.0",
        "packet_type": "ai_context",
        "source_app": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
        "intended_consumer": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
        "project": {"project_id": "validation-project"},
        "datasets": [],
        "journey_events": [],
        "authority": {"scientific_record": "Engineering Lab", "ai_output": "advisory only"},
        "boundary": "validation fixture",
    }, prefix="ai-context")

    contract = adapter.native_api_contract()
    require(contract["api_version"] == "labbridge-openguin-api/v1", "wrong native API version")
    require("GET /labbridge/v1/capabilities" in contract["endpoints"], "capabilities endpoint missing")
    require("POST /labbridge/v1/advisory" in contract["endpoints"], "advisory endpoint missing")

    original_probe = adapter.probe_openguin
    original_ask = adapter.ask_local_model
    original_request = adapter._request_json
    try:
        adapter.probe_openguin = lambda: {
            "available": True,
            "mode": "ollama-compat",
            "base": adapter.OPENPENGUIN_BASE,
            "api_version": "ollama-compatible",
            "models": ["fixture-model"],
            "capabilities": ["text-advisory"],
            "raw": {},
        }
        adapter.ask_local_model = lambda base, model, question, context, temperature=0.2: "Fallback advisory answer"
        fallback = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(fallback["schema"] == "labbridge.ai-suggestion/v1", "fallback schema mismatch")
        require(fallback["executed"] is False, "fallback suggestion claimed execution")
        require(fallback["source_app"]["name"] == "OpenPenguin", "fallback source authority mismatch")
        require(context["packet_id"] in fallback["evidence_refs"], "fallback lost AI context provenance")
        require(validate_ai_advisory(fallback)["valid"], "fallback packet failed LabBridge validation")

        adapter.probe_openguin = lambda: {
            "available": True,
            "mode": "native-labbridge",
            "base": adapter.OPENPENGUIN_BASE,
            "api_version": adapter.NATIVE_API_VERSION,
            "models": ["fixture-model"],
            "capabilities": ["labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"],
            "raw": {},
        }
        native_packet = finalize_packet({
            "schema": "labbridge.ai-suggestion/v1",
            "bridge_version": "1.0",
            "packet_type": "ai_suggestion",
            "source_app": {"name": "OpenPenguin", "role": "local-ai-advisory-layer", "model": "fixture-model"},
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "title": "Native fixture",
            "summary": "Native advisory answer",
            "question": "What next?",
            "evidence_refs": [context["packet_id"]],
            "executed": False,
        }, prefix="ai-suggestion")
        adapter._request_json = lambda path, payload=None, timeout=5.0: native_packet
        native = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(native["packet_id"] == native_packet["packet_id"], "native packet identity changed")
        require(native["executed"] is False, "native suggestion claimed execution")
        require(validate_ai_advisory(native)["valid"], "native packet failed LabBridge validation")
    finally:
        adapter.probe_openguin = original_probe
        adapter.ask_local_model = original_ask
        adapter._request_json = original_request

    print("PASS: OpenPenguin LabBridge native/fallback adapter contract and advisory boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
