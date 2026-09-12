"""OpenPenguin adapter for Engineering Lab LabBridge.

The adapter deliberately keeps OpenPenguin's model/runtime implementation behind a
small compatibility surface. It prefers a native LabBridge API when available and
falls back to the existing Ollama-compatible loopback API at 127.0.0.1:11435.

Engineering Lab remains the scientific record. OpenPenguin responses are advisory;
this adapter never applies parameter changes, starts experiments, or mutates
measurement/solver state.
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from physical_lab_labbridge import AI_SUGGESTION_SCHEMA, finalize_packet, validate_ai_advisory
from physical_lab_local_ai import ask_local_model, discover_local_ai_engines

OPENPENGUIN_BASE = "http://127.0.0.1:11435"
NATIVE_API_VERSION = "labbridge-openguin-api/v1"
SUPPORTED_NATIVE_API_VERSIONS = {NATIVE_API_VERSION}
REQUIRED_NATIVE_CAPABILITIES = {"labbridge.ai-context/v1", "labbridge.ai-suggestion/v1"}
MAX_NATIVE_RESPONSE_BYTES = 2 * 1024 * 1024


class OpenPenguinAdapterError(RuntimeError):
    """Normalized adapter failure with a stable category for UI/provenance."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = str(category)


def _request_json(path: str, payload: Mapping[str, Any] | None = None, *, timeout: float = 5.0) -> Any:
    if not path.startswith("/"):
        raise ValueError("OpenPenguin adapter path must be absolute")
    url = OPENPENGUIN_BASE + path
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
        raise OpenPenguinAdapterError("unavailable", f"OpenPenguin is unavailable at {OPENPENGUIN_BASE}: {exc.reason}") from exc
    if len(raw) > MAX_NATIVE_RESPONSE_BYTES:
        raise OpenPenguinAdapterError("response-too-large", "OpenPenguin LabBridge response exceeded the local safety limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OpenPenguinAdapterError("invalid-json", "OpenPenguin LabBridge endpoint returned invalid JSON") from exc


def _normalized_models(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _normalized_capabilities(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _validate_native_capabilities(payload: Mapping[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    version = str(payload.get("api_version") or "")
    if version not in SUPPORTED_NATIVE_API_VERSIONS:
        errors.append(f"unsupported api_version: {version or 'missing'}")
    capabilities = set(_normalized_capabilities(payload.get("capabilities")))
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
        "base": str(engine.get("base") or OPENPENGUIN_BASE),
        "api_version": "ollama-compatible",
        "models": list(engine.get("models") or []),
        "capabilities": ["text-advisory", "labbridge-context-via-chat"],
        "native_probe_error": None,
        "raw": {},
    }


def probe_openguin() -> dict[str, Any]:
    """Return one normalized OpenPenguin capability record.

    Native LabBridge discovery is preferred. A malformed/unsupported native
    capabilities response does not break compatibility: the adapter records the
    reason and falls back to the existing Ollama-compatible runtime when available.
    """
    native_probe_error: str | None = None
    try:
        payload = _request_json("/labbridge/v1/capabilities", timeout=1.2)
        if isinstance(payload, Mapping):
            valid, errors = _validate_native_capabilities(payload)
            if valid:
                return {
                    "available": True,
                    "mode": "native-labbridge",
                    "base": OPENPENGUIN_BASE,
                    "api_version": str(payload.get("api_version")),
                    "models": _normalized_models(payload.get("models")),
                    "capabilities": _normalized_capabilities(payload.get("capabilities")),
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
        "base": OPENPENGUIN_BASE,
        "api_version": None,
        "models": [],
        "capabilities": [],
        "native_probe_error": native_probe_error,
        "raw": {},
    }


def _normalize_native_suggestion(
    response: Mapping[str, Any],
    *,
    context_packet: Mapping[str, Any],
    question: str,
    model: str,
) -> dict[str, Any] | None:
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
    if not str(packet.get("question") or "").strip():
        packet["question"] = question
    check = validate_ai_advisory(packet)
    return packet if check.get("valid") else None


def _compat_advisory(
    context_packet: Mapping[str, Any],
    *,
    question: str,
    model: str,
    temperature: float,
    native_error: str | None,
) -> dict[str, Any]:
    compat = _probe_ollama_compat()
    if not compat:
        raise OpenPenguinAdapterError("fallback-unavailable", "OpenPenguin native advisory failed and Ollama-compatible fallback is unavailable")
    answer = ask_local_model(
        str(compat["base"]),
        model,
        question,
        context_packet,
        temperature=float(temperature),
    )
    if not answer.strip():
        raise OpenPenguinAdapterError("empty-response", "OpenPenguin returned an empty advisory")
    return finalize_packet(
        {
            "schema": AI_SUGGESTION_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "ai_suggestion",
            "source_app": {
                "name": "OpenPenguin",
                "role": "local-ai-advisory-layer",
                "model": model,
                "runtime": str(compat["base"]),
                "adapter_mode": "ollama-compat",
                "fallback_used": bool(native_error),
                "native_error": (str(native_error)[:1000] if native_error else None),
            },
            "intended_consumer": {
                "name": "Engineering Lab",
                "role": "scientific-computation-and-evidence-core",
            },
            "title": f"OpenPenguin advisory · {question[:80]}",
            "summary": answer[:200000],
            "question": question,
            "evidence_refs": [str(context_packet.get("packet_id") or "")],
            "executed": False,
        },
        prefix="ai-suggestion",
    )


def request_advisory(
    context_packet: Mapping[str, Any],
    *,
    question: str,
    model: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Ask OpenPenguin and normalize the result to LabBridge AISuggestion v1.

    Native LabBridge is preferred. If the native advisory endpoint fails during a
    rolling upgrade, Engineering Lab safely falls back to the existing local
    Ollama-compatible endpoint. The fallback reason is preserved in provenance.
    """
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
        raise OpenPenguinAdapterError("offline", "OpenPenguin private runtime is unavailable")

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
                normalized = _normalize_native_suggestion(
                    response,
                    context_packet=context_packet,
                    question=question,
                    model=model,
                )
                if normalized is not None:
                    return normalized
                answer = str(response.get("summary") or response.get("answer") or response.get("response") or "")
                if answer.strip():
                    return finalize_packet(
                        {
                            "schema": AI_SUGGESTION_SCHEMA,
                            "bridge_version": "1.0",
                            "packet_type": "ai_suggestion",
                            "source_app": {
                                "name": "OpenPenguin",
                                "role": "local-ai-advisory-layer",
                                "model": model,
                                "runtime": str(status["base"]),
                                "adapter_mode": "native-labbridge",
                                "fallback_used": False,
                            },
                            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
                            "title": f"OpenPenguin advisory · {question[:80]}",
                            "summary": answer[:200000],
                            "question": question,
                            "evidence_refs": [str(context_packet.get("packet_id") or "")],
                            "executed": False,
                        },
                        prefix="ai-suggestion",
                    )
                native_error = "native advisory response contained neither a valid AISuggestion nor advisory text"
            else:
                native_error = "native advisory response was not an object"
        except Exception as exc:
            native_error = str(exc)
        return _compat_advisory(
            context_packet,
            question=question,
            model=model,
            temperature=float(temperature),
            native_error=native_error,
        )

    return _compat_advisory(
        context_packet,
        question=question,
        model=model,
        temperature=float(temperature),
        native_error=status.get("native_probe_error"),
    )


def native_api_contract() -> dict[str, Any]:
    """Machine-readable minimum contract for an OpenPenguin-native adapter."""
    return {
        "api_version": NATIVE_API_VERSION,
        "supported_api_versions": sorted(SUPPORTED_NATIVE_API_VERSIONS),
        "base": OPENPENGUIN_BASE,
        "required_capabilities": sorted(REQUIRED_NATIVE_CAPABILITIES),
        "endpoints": {
            "GET /labbridge/v1/capabilities": {
                "response": {
                    "api_version": NATIVE_API_VERSION,
                    "models": ["string"],
                    "capabilities": sorted(REQUIRED_NATIVE_CAPABILITIES),
                },
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
                "response": AI_SUGGESTION_SCHEMA,
            },
        },
        "compatibility": {
            "fallback": "Ollama-compatible /api/chat on 127.0.0.1:11435",
            "native_failure_policy": "fall back locally and preserve the native error in advisory provenance",
        },
        "required_security": [
            "loopback-only by default",
            "bounded request/response sizes",
            "no automatic execution of ActionProposal",
            "no mutation of Engineering Lab evidence",
        ],
    }
