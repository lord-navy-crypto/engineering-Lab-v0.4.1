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

    require(adapter.OPENPENGUIN_NATIVE_BASE == "http://127.0.0.1:11436", "native LabBridge port must be 11436")
    require(adapter.OPENPENGUIN_RUNTIME_BASE == "http://127.0.0.1:11435", "private Ollama fallback port must be 11435")

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
    require(contract["native_base"].endswith(":11436"), "contract native port mismatch")
    require(contract["runtime_fallback_base"].endswith(":11435"), "contract fallback port mismatch")
    require("GET /labbridge/v1/health" in contract["endpoints"], "health endpoint missing")
    require("GET /labbridge/v1/capabilities" in contract["endpoints"], "capabilities endpoint missing")
    require("POST /labbridge/v1/advisory" in contract["endpoints"], "advisory endpoint missing")
    require("labbridge.ai-context/v1" in contract["required_capabilities"], "AI context capability missing")
    require("labbridge.ai-suggestion/v1" in contract["required_capabilities"], "AI suggestion capability missing")

    valid_caps = {
        "api_version": adapter.NATIVE_API_VERSION,
        "runtime_base": adapter.OPENPENGUIN_RUNTIME_BASE,
        "models": ["fixture-model"],
        "capabilities": ["labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"],
    }
    ok, errors = adapter._validate_native_capabilities(valid_caps)
    require(ok and not errors, f"valid native capabilities rejected: {errors}")
    bad_ok, bad_errors = adapter._validate_native_capabilities({
        "api_version": "labbridge-openguin-api/v999",
        "models": ["fixture-model"],
        "capabilities": ["labbridge.ai-context/v1"],
    })
    require(not bad_ok, "unsupported native API version was accepted")
    require(any("unsupported api_version" in e for e in bad_errors), "version negotiation error missing")
    require(any("missing required capabilities" in e for e in bad_errors), "capability negotiation error missing")

    original_probe = adapter.probe_openguin
    original_compat_probe = adapter._probe_ollama_compat
    original_ask = adapter.ask_local_model
    original_request = adapter._request_json
    try:
        compat_status = {
            "available": True,
            "mode": "ollama-compat",
            "base": adapter.OPENPENGUIN_RUNTIME_BASE,
            "api_version": "ollama-compatible",
            "models": ["fixture-model"],
            "capabilities": ["text-advisory"],
            "native_probe_error": "native endpoint unavailable",
            "raw": {},
        }
        adapter.probe_openguin = lambda: dict(compat_status)
        adapter._probe_ollama_compat = lambda: dict(compat_status)
        adapter.ask_local_model = lambda base, model, question, context, temperature=0.2: "Fallback advisory answer"
        fallback = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(fallback["schema"] == "labbridge.ai-suggestion/v1", "fallback schema mismatch")
        require(fallback["executed"] is False, "fallback suggestion claimed execution")
        require(fallback["source_app"]["adapter_mode"] == "ollama-compat", "fallback mode provenance missing")
        require(fallback["source_app"]["runtime"].endswith(":11435"), "fallback advisory used wrong runtime port")
        require(fallback["source_app"]["fallback_used"] is True, "fallback provenance did not record downgrade")
        require(context["packet_id"] in fallback["evidence_refs"], "fallback lost AI context provenance")
        require(validate_ai_advisory(fallback)["valid"], "fallback packet failed LabBridge validation")

        native_status = {
            "available": True,
            "mode": "native-labbridge",
            "base": adapter.OPENPENGUIN_NATIVE_BASE,
            "runtime_base": adapter.OPENPENGUIN_RUNTIME_BASE,
            "api_version": adapter.NATIVE_API_VERSION,
            "models": ["fixture-model"],
            "capabilities": ["labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"],
            "native_probe_error": None,
            "raw": {},
        }
        adapter.probe_openguin = lambda: dict(native_status)
        adapter._request_json = lambda path, payload=None, timeout=5.0: {
            "api_version": adapter.NATIVE_API_VERSION,
            "schema": "openguin.labbridge-advisory-response/v1",
            "answer": "Native advisory answer",
            "model": "fixture-model",
            "runtime": "private-ollama-11435",
            "context_packet_id": context["packet_id"],
            "executed": False,
        }
        native = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(native["schema"] == "labbridge.ai-suggestion/v1", "native text response was not normalized")
        require(native["source_app"]["adapter_mode"] == "native-labbridge", "native mode provenance missing")
        require(native["source_app"]["fallback_used"] is False, "native response incorrectly marked fallback")
        require(native["executed"] is False, "native suggestion claimed execution")
        require(context["packet_id"] in native["evidence_refs"], "native response lost context provenance")
        require(validate_ai_advisory(native)["valid"], "native packet failed LabBridge validation")

        adapter.probe_openguin = lambda: dict(native_status)
        adapter._request_json = lambda path, payload=None, timeout=5.0: (_ for _ in ()).throw(adapter.OpenPenguinAdapterError("http", "fixture native 503"))
        adapter._probe_ollama_compat = lambda: dict(compat_status)
        adapter.ask_local_model = lambda base, model, question, context, temperature=0.2: "Recovered through compatibility mode"
        recovered = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(recovered["source_app"]["adapter_mode"] == "ollama-compat", "native failure did not downgrade")
        require(recovered["source_app"]["runtime"].endswith(":11435"), "recovered advisory used wrong fallback port")
        require(recovered["source_app"]["fallback_used"] is True, "native failure downgrade not recorded")
        require("fixture native 503" in str(recovered["source_app"].get("native_error")), "native failure reason was not preserved")
        require(recovered["executed"] is False, "recovered advisory claimed execution")
        require(validate_ai_advisory(recovered)["valid"], "recovered packet failed LabBridge validation")
    finally:
        adapter.probe_openguin = original_probe
        adapter._probe_ollama_compat = original_compat_probe
        adapter.ask_local_model = original_ask
        adapter._request_json = original_request

    print("PASS: OpenPenguin 11436 native bridge, 11435 fallback, version negotiation and advisory boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
