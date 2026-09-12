"""OpenPenguin compatibility adapter for Engineering Lab LabBridge.

Native OpenPenguin LabBridge lives on 127.0.0.1:11436. The existing private
Ollama runtime remains on 127.0.0.1:11435 and is used as a local compatibility
fallback. Engineering Lab remains the scientific record; OpenPenguin output is
advisory and never executes scientific actions.
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from physical_lab_labbridge import AI_SUGGESTION_SCHEMA, finalize_packet, validate_ai_advisory
from physical_lab_local_ai import ask_local_model, discover_local_ai_engines

OPENPENGUIN_NATIVE_BASE = "http://127.0.0.1:11436"
OPENPENGUIN_RUNTIME_BASE = "http://127.0.0.1:11435"
# Compatibility alias retained for existing validation/helpers.
OPENPENGUIN_BASE = OPENPENGUIN_NATIVE_BASE
NATIVE_API_VERSION = "labbridge-openguin-api/v1"
SUPPORTED_NATIVE_API_VERSIONS = {NATIVE_API_VERSION}
REQUIRED_NATIVE_CAPABILITIES = {"labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"}
MAX_NATIVE_RESPONSE_BYTES = 2 * 1024 * 1024


class OpenPenguinAdapterError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = str(category)


def _request_json(path: str, payload: Mapping[str, Any] | None = None, *, timeout: float = 5.0) -> Any:
    if not path.startswith("/"):
        raise ValueError("OpenPenguin adapter path must be absolute")
    url = OPENPENGUIN_NATIVE_BASE + path
    method = "POST" if payload is not None else "GET"
    data = None if payload is None else json.dumps(dict(payload), allow_nan=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(MAX_NATIVE_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise OpenPenguinAdapterError("http", f"OpenPenguin LabBridge API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise OpenPenguinAdapterError("unavailable", f"OpenPenguin LabBridge is unavailable at {OPENPENGUIN_NATIVE_BASE}: {exc.reason}") from exc
    if len(raw) > MAX_NATIVE_RESPONSE_BYTES:
        raise OpenPenguinAdapterError("response-too-large", "OpenPenguin LabBridge response exceeded the local safety limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OpenPenguinAdapterError("invalid-json", "OpenPenguin LabBridge endpoint returned invalid JSON") from exc


def _normalized_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _validate_native_capabilities(payload: Mapping[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    version = str(payload.get("api_version") or "")
    if version not in SUPPORTED_NATIVE_API_VERSIONS:
        errors.append(f"unsupported api_version: {version or 'missing'}")
    capabilities = set(_normalized_list(payload.get("capabilities")))
    missing = sorted(REQUIRED_NATIVE_CAPABILITIES - capabilities)
    if missing:
        errors.append("missing required capabilities: " + ", ".join(missing))
    if not isinstance(payload.get("models"), (list, tuple)):
        errors.append("models must be an array")
    return not errors, errors


def _probe_ollama_compat() -> dict[str, Any] | None:
    engines = discover_local_ai_engines()
    engine = next((e for e in engines if e.get("running") and str(e.get("label") or "").startswith("OpenPenguin")), None)
    if not engine:
        return None
    return {
        "available": True,
        "mode": "ollama-compat",
        "base": str(engine.get("base") or OPENPENGUIN_RUNTIME_BASE),
        "api_version": "ollama-compatible",
        "models": list(engine.get("models") or []),
        "capabilities": ["text-advisory", "labbridge-context-via-chat"],
        "native_probe_error": None,
        "raw": {},
    }


def probe_openguin() -> dict[str, Any]:
    """Prefer OpenPenguin native LabBridge, with local Ollama fallback."""
    native_probe_error: str | None = None
    try:
        payload = _request_json("/labbridge/v1/capabilities", timeout=1.2)
        if isinstance(payload, Mapping):
            valid, errors = _validate_native_capabilities(payload)
            if valid:
                return {
                    "available": True,
                    "mode": "native-labbridge",
                    "base": OPENPENGUIN_NATIVE_BASE,
                    "runtime_base": str(payload.get("runtime_base") or OPENPENGUIN_RUNTIME_BASE),
                    "api_version": str(payload.get("api_version")),
                    "models": _normalized_list(payload.get("models")),
                    "capabilities": _normalized_list(payload.get("capabilities")),
                    "native_probe_error": None,
                    "raw": dict(payload),
                }
            native_probe_error = "; ".join(errors)
        else:
            native_probe_error = "native capabilities response was not an object"
    except Exception as exc:
        native_probe_error = str(exc)

    compat = _probe_ollama_compat()
    if compat:
        compat["native_probe_error"] = native_probe_error
        return compat
    return {
        "available": False,
        "mode": "offline",
        "base": OPENPENGUIN_NATIVE_BASE,
        "runtime_base": OPENPENGUIN_RUNTIME_BASE,
        "api_version": None,
        "models": [],
        "capabilities": [],
        "native_probe_error": native_probe_error,
        "raw": {},
    }


def _normalize_native_suggestion(response: Mapping[str, Any], *, context_packet: Mapping[str, Any], question: str, model: str) -> dict[str, Any] | None:
    if response.get("schema") != AI_SUGGESTION_SCHEMA:
        return None
    packet = dict(response)
    packet["executed"] = False
    source = packet.get("source_app") if isinstance(packet.get("source_app"), Mapping) else {}
    packet["source_app"] = {
        **dict(source),
        "name": "OpenPenguin",
        "role": "local-ai-advisory-layer",
        "model": str(source.get("model") or model),
        "adapter_mode": "native-labbridge",
    }
    refs = [str(x) for x in packet.get("evidence_refs", []) if str(x)]
    context_id = str(context_packet.get("packet_id") or "")
    if context_id and context_id not in refs:
        refs.insert(0, context_id)
    packet["evidence_refs"] = refs
    packet.setdefault("question", question)
    check = validate_ai_advisory(packet)
    return packet if check.get("valid") else None


def _wrap_answer(*, answer: str, context_packet: Mapping[str, Any], question: str, model: str, mode: str, runtime: str, fallback_used: bool, native_error: str | None = None) -> dict[str, Any]:
    return finalize_packet(
        {
            "schema": AI_SUGGESTION_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "ai_suggestion",
            "source_app": {
                "name": "OpenPenguin",
                "role": "local-ai-advisory-layer",
                "model": model,
                "runtime": runtime,
                "adapter_mode": mode,
                "fallback_used": bool(fallback_used),
                "native_error": str(native_error)[:1000] if native_error else None,
            },
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "title": f"OpenPenguin advisory · {question[:80]}",
            "summary": str(answer)[:200000],
            "question": question,
            "evidence_refs": [str(context_packet.get("packet_id") or "")],
            "executed": False,
        },
        prefix="ai-suggestion",
    )


def _compat_advisory(context_packet: Mapping[str, Any], *, question: str, model: str, temperature: float, native_error: str | None) -> dict[str, Any]:
    compat = _probe_ollama_compat()
    if not compat:
        raise OpenPenguinAdapterError("fallback-unavailable", "OpenPenguin native advisory failed and local Ollama fallback is unavailable")
    answer = ask_local_model(str(compat["base"]), model, question, context_packet, temperature=float(temperature))
    if not str(answer).strip():
        raise OpenPenguinAdapterError("empty-response", "OpenPenguin returned an empty advisory")
    return _wrap_answer(
        answer=str(answer), context_packet=context_packet, question=question, model=model,
        mode="ollama-compat", runtime=str(compat["base"]), fallback_used=bool(native_error), native_error=native_error,
    )


def request_advisory(context_packet: Mapping[str, Any], *, question: str, model: str, temperature: float = 0.2) -> dict[str, Any]:
    """Ask OpenPenguin and normalize the response to LabBridge AISuggestion v1."""
    if context_packet.get("schema") != "labbridge.ai-context/v1":
        raise ValueError("OpenPenguin advisory requires labbridge.ai-context/v1")
    question = str(question).strip()
    model = str(model).strip()
    if not question:
        raise ValueError("question is required")
    if not model:
        raise ValueError("model is required")
    if not 0.0 <= float(temperature) <= 2.0:
        raise ValueError("temperature must be within 0..2")

    status = probe_openguin()
    if not status["available"]:
        raise OpenPenguinAdapterError("offline", "OpenPenguin is unavailable")

    if status["mode"] == "native-labbridge":
        native_error: str | None = None
        try:
            response = _request_json(
                "/labbridge/v1/advisory",
                {
                    "api_version": str(status["api_version"]),
                    "context": dict(context_packet),
                    "question": question,
                    "model": model,
                    "temperature": float(temperature),
                    "requested_response_schema": AI_SUGGESTION_SCHEMA,
                },
                timeout=600.0,
            )
            if isinstance(response, Mapping):
                normalized = _normalize_native_suggestion(response, context_packet=context_packet, question=question, model=model)
                if normalized is not None:
                    return normalized
                answer = str(response.get("summary") or response.get("answer") or response.get("response") or "")
                if answer.strip():
                    return _wrap_answer(
                        answer=answer, context_packet=context_packet, question=question, model=model,
                        mode="native-labbridge", runtime=str(response.get("runtime") or status.get("runtime_base") or OPENPENGUIN_RUNTIME_BASE),
                        fallback_used=False,
                    )
                native_error = "native advisory response contained neither a valid AISuggestion nor advisory text"
            else:
                native_error = "native advisory response was not an object"
        except Exception as exc:
            native_error = str(exc)
        return _compat_advisory(context_packet, question=question, model=model, temperature=float(temperature), native_error=native_error)

    return _compat_advisory(
        context_packet, question=question, model=model, temperature=float(temperature),
        native_error=status.get("native_probe_error"),
    )


def native_api_contract() -> dict[str, Any]:
    return {
        "api_version": NATIVE_API_VERSION,
        "supported_api_versions": sorted(SUPPORTED_NATIVE_API_VERSIONS),
        "native_base": OPENPENGUIN_NATIVE_BASE,
        "runtime_fallback_base": OPENPENGUIN_RUNTIME_BASE,
        "required_capabilities": sorted(REQUIRED_NATIVE_CAPABILITIES),
        "endpoints": {
            "GET /labbridge/v1/health": {"response": "service health"},
            "GET /labbridge/v1/capabilities": {
                "response": {"api_version": NATIVE_API_VERSION, "models": ["string"], "capabilities": sorted(REQUIRED_NATIVE_CAPABILITIES)},
            },
            "POST /labbridge/v1/advisory": {
                "request": {
                    "api_version": NATIVE_API_VERSION,
                    "context": "labbridge.ai-context/v1",
                    "question": "string",
                    "model": "string",
                    "temperature": "number",
                    "requested_response_schema": AI_SUGGESTION_SCHEMA,
                },
                "response": "native advisory text or labbridge.ai-suggestion/v1",
            },
        },
        "compatibility": {
            "fallback": f"Ollama-compatible /api/chat on {OPENPENGUIN_RUNTIME_BASE}",
            "native_failure_policy": "fall back locally and preserve the native error in advisory provenance",
        },
        "required_security": [
            "loopback-only native and fallback endpoints",
            "bounded request/response sizes",
            "no automatic execution of ActionProposal",
            "no mutation of Engineering Lab evidence",
        ],
    }
