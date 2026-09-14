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

    require(adapter.OPENPENGUIN_NATIVE_BASE == "http://127.0.0.1:11436", "native infrastructure port must be 11436")
    require(adapter.OPENPENGUIN_RUNTIME_BASE == "http://127.0.0.1:11435", "private runtime fallback port must be 11435")
    require(adapter.GENERIC_API_VERSION == "openguin-local-api/v1", "generic API version mismatch")
    require(adapter.LEGACY_API_VERSION == "labbridge-openguin-api/v1", "legacy API version mismatch")

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
    science_context = finalize_packet({
        **{k: v for k, v in context.items() if k not in {"packet_id", "content_sha256"}},
        "scientific_context": {
            "schema": adapter.SCIENTIFIC_CONTEXT_SCHEMA,
            "active_object": {"source_id": "sweep:fixture", "kind": "sweep"},
            "capabilities": [{"capability_id": "morris-effects"}],
            "interpretation_constraints": ["mu* is screening only"],
            "authority": {"execution": False, "mutation_authority": False},
        },
    }, prefix="ai-context")

    contract = adapter.native_api_contract()
    require(contract["generic_api_version"] == adapter.GENERIC_API_VERSION, "generic contract mismatch")
    require(contract["legacy_api_version"] == adapter.LEGACY_API_VERSION, "legacy contract mismatch")
    require("GET /v1/status" in contract["preferred_endpoints"], "infrastructure status endpoint missing")
    require("GET /v1/policies" in contract["preferred_endpoints"], "policy registry endpoint missing")
    require("POST /v1/advisory" in contract["preferred_endpoints"], "generic advisory endpoint missing")
    require(contract["client_identity"]["app_id"] == "engineering-lab", "Engineering Lab client identity missing")
    require(contract["nested_scientific_context_schema"] == adapter.SCIENTIFIC_CONTEXT_SCHEMA, "scientific context contract missing")
    require(contract["analysis_plan_response_schema"] == adapter.ANALYSIS_PLAN_SCHEMA, "analysis plan contract missing")
    require(adapter._requested_response_schema(context, "ordinary explanation") == "", "ordinary advisory requested structured plan unexpectedly")
    plan_question = f"Return ONLY JSON matching {adapter.ANALYSIS_PLAN_SCHEMA}."
    require(adapter._requested_response_schema(science_context, plan_question) == adapter.ANALYSIS_PLAN_SCHEMA, "science plan response schema was not negotiated")

    original_probe = adapter.probe_openguin
    original_compat_probe = adapter._probe_ollama_compat
    original_ask = adapter.ask_local_model
    original_request = adapter._request_json
    try:
        generic_status = {
            "available": True,
            "mode": "openguin-infrastructure-v2",
            "base": adapter.OPENPENGUIN_NATIVE_BASE,
            "runtime_base": adapter.OPENPENGUIN_RUNTIME_BASE,
            "api_version": adapter.GENERIC_API_VERSION,
            "models": ["fixture-model"],
            "loaded_models": ["fixture-model"],
            "capabilities": ["labbridge.ai-context/v1", adapter.SCIENTIFIC_CONTEXT_SCHEMA, adapter.ANALYSIS_PLAN_SCHEMA, "auto-model-routing", "context-policy-registry"],
            "raw": {},
        }
        captured = {}
        adapter.probe_openguin = lambda: dict(generic_status)
        def generic_request(path, payload=None, timeout=5.0):
            captured["path"] = path
            captured["payload"] = dict(payload or {})
            return {
                "api_version": adapter.GENERIC_API_VERSION,
                "schema": "openguin.local-advisory-response/v1",
                "request_id": "opg-fixture",
                "answer": "Generic infrastructure advisory",
                "model": "fixture-model",
                "model_route": "loaded-first",
                "runtime": "private-ollama-11435",
                "policy_id": "engineering-lab-evidence/v1",
                "client": {"app_id": "engineering-lab"},
                "elapsed_ms": 12,
                "executed": False,
                "mutation_authority": False,
            }
        adapter._request_json = generic_request
        generic = adapter.request_advisory(context, question="What next?", model="auto")
        require(captured["path"] == "/v1/advisory", "Engineering Lab did not prefer generic infrastructure")
        require(captured["payload"]["client"]["app_id"] == "engineering-lab", "client identity not sent")
        require(captured["payload"]["model"] == "auto", "model:auto was not forwarded")
        require("requested_response_schema" not in captured["payload"], "ordinary generic advisory should not force a response schema")
        require(generic["source_app"]["adapter_mode"] == "openguin-infrastructure-v2", "generic mode provenance missing")
        require(generic["source_app"]["request_id"] == "opg-fixture", "request tracing metadata missing")
        require(generic["source_app"]["policy_id"] == "engineering-lab-evidence/v1", "policy metadata missing")
        require(generic["executed"] is False, "generic advisory claimed execution")
        require(validate_ai_advisory(generic)["valid"], "generic packet failed LabBridge validation")

        adapter.request_advisory(science_context, question=plan_question, model="auto")
        require(captured["payload"].get("requested_response_schema") == adapter.ANALYSIS_PLAN_SCHEMA, "generic science plan did not send requested_response_schema")
        require(captured["payload"]["context"]["scientific_context"]["schema"] == adapter.SCIENTIFIC_CONTEXT_SCHEMA, "scientific context was not forwarded")

        legacy_status = {
            "available": True,
            "mode": "native-labbridge-legacy",
            "base": adapter.OPENPENGUIN_NATIVE_BASE,
            "runtime_base": adapter.OPENPENGUIN_RUNTIME_BASE,
            "api_version": adapter.LEGACY_API_VERSION,
            "models": ["fixture-model"],
            "loaded_models": [],
            "capabilities": ["labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"],
            "raw": {},
        }
        adapter.probe_openguin = lambda: dict(legacy_status)
        legacy_captured = {}
        def legacy_request(path, payload=None, timeout=5.0):
            legacy_captured["payload"] = dict(payload or {})
            return {
                "api_version": adapter.LEGACY_API_VERSION,
                "schema": "openguin.local-advisory-response/v1",
                "answer": "Legacy advisory",
                "model": "fixture-model",
                "runtime": "private-ollama-11435",
                "executed": False,
            }
        adapter._request_json = legacy_request
        legacy = adapter.request_advisory(context, question="What next?", model="fixture-model")
        require(legacy["source_app"]["adapter_mode"] == "native-labbridge-legacy", "legacy compatibility path failed")
        require(legacy["executed"] is False, "legacy advisory claimed execution")
        adapter.request_advisory(science_context, question=plan_question, model="fixture-model")
        require(legacy_captured["payload"].get("requested_response_schema") == adapter.ANALYSIS_PLAN_SCHEMA, "legacy science plan did not negotiate response schema")

        compat_status = {
            "available": True,
            "mode": "ollama-compat",
            "base": adapter.OPENPENGUIN_RUNTIME_BASE,
            "api_version": "ollama-compatible",
            "models": ["fixture-model"],
            "loaded_models": [],
            "capabilities": ["text-advisory"],
            "generic_probe_error": "fixture generic failure",
            "legacy_probe_error": "fixture legacy failure",
            "raw": {},
        }
        adapter.probe_openguin = lambda: dict(compat_status)
        adapter._probe_ollama_compat = lambda: dict(compat_status)
        adapter.ask_local_model = lambda base, model, question, context, temperature=0.2: "Fallback advisory"
        fallback = adapter.request_advisory(context, question="What next?", model="auto")
        require(fallback["source_app"]["adapter_mode"] == "ollama-compat", "private runtime fallback failed")
        require(fallback["source_app"]["runtime"].endswith(":11435"), "fallback used wrong runtime port")
        require(fallback["executed"] is False, "fallback advisory claimed execution")
        require(validate_ai_advisory(fallback)["valid"], "fallback packet failed LabBridge validation")
    finally:
        adapter.probe_openguin = original_probe
        adapter._probe_ollama_compat = original_compat_probe
        adapter.ask_local_model = original_ask
        adapter._request_json = original_request

    print("PASS: Engineering Lab negotiates OpenPenguin scientific plan schemas while preserving legacy and 11435 fallbacks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
