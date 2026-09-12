"""OpenPenguin shared-infrastructure adapter for Engineering Lab.

Preference order:
1. OpenPenguin generic infrastructure API on 127.0.0.1:11436 (/v1/*).
2. Legacy Engineering Lab LabBridge compatibility API on the same port.
3. OpenPenguin private Ollama runtime on 127.0.0.1:11435.

Engineering Lab remains the scientific system of record. OpenPenguin is advisory only.
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
OPENPENGUIN_BASE = OPENPENGUIN_NATIVE_BASE
GENERIC_API_VERSION = "openguin-local-api/v1"
LEGACY_API_VERSION = "labbridge-openguin-api/v1"
ENGINEERING_CONTEXT_SCHEMA = "labbridge.ai-context/v1"
MAX_NATIVE_RESPONSE_BYTES = 2 * 1024 * 1024


class OpenPenguinAdapterError(RuntimeError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = str(category)


def _request_json(path: str, payload: Mapping[str, Any] | None = None, *, timeout: float = 5.0) -> Any:
    if not path.startswith("/"):
        raise ValueError("OpenPenguin adapter path must be absolute")
    method = "POST" if payload is not None else "GET"
    data = None if payload is None else json.dumps(dict(payload), allow_nan=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(OPENPENGUIN_NATIVE_BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(MAX_NATIVE_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise OpenPenguinAdapterError("http", f"OpenPenguin returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise OpenPenguinAdapterError("unavailable", f"OpenPenguin unavailable at {OPENPENGUIN_NATIVE_BASE}: {exc.reason}") from exc
    if len(raw) > MAX_NATIVE_RESPONSE_BYTES:
        raise OpenPenguinAdapterError("response-too-large", "OpenPenguin response exceeded local safety limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OpenPenguinAdapterError("invalid-json", "OpenPenguin returned invalid JSON") from exc


def _normalized_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _probe_generic() -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = _request_json("/v1/capabilities", timeout=1.2)
        if not isinstance(payload, Mapping):
            return None, "generic capabilities response was not an object"
        if str(payload.get("api_version") or "") != GENERIC_API_VERSION:
            return None, f"unsupported generic api_version: {payload.get('api_version')!r}"
        accepted = set(_normalized_list(payload.get("accepted_context_schemas")))
        if ENGINEERING_CONTEXT_SCHEMA not in accepted:
            return None, "generic infrastructure does not accept Engineering Lab context"
        return {
            "available": True,
            "mode": "openguin-infrastructure-v2",
            "base": OPENPENGUIN_NATIVE_BASE,
            "runtime_base": str(payload.get("runtime_base") or OPENPENGUIN_RUNTIME_BASE),
            "api_version": GENERIC_API_VERSION,
            "models": _normalized_list(payload.get("models")),
            "loaded_models": _normalized_list(payload.get("loaded_models")),
            "capabilities": _normalized_list(payload.get("capabilities")),
            "raw": dict(payload),
        }, None
    except Exception as exc:
        return None, str(exc)


def _probe_legacy() -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = _request_json("/labbridge/v1/capabilities", timeout=1.2)
        if not isinstance(payload, Mapping):
            return None, "legacy capabilities response was not an object"
        if str(payload.get("api_version") or "") != LEGACY_API_VERSION:
            return None, f"unsupported legacy api_version: {payload.get('api_version')!r}"
        capabilities = set(_normalized_list(payload.get("capabilities")))
        if ENGINEERING_CONTEXT_SCHEMA not in capabilities:
            return None, "legacy LabBridge missing Engineering Lab context capability"
        return {
            "available": True,
            "mode": "native-labbridge-legacy",
            "base": OPENPENGUIN_NATIVE_BASE,
            "runtime_base": str(payload.get("runtime_base") or OPENPENGUIN_RUNTIME_BASE),
            "api_version": LEGACY_API_VERSION,
            "models": _normalized_list(payload.get("models")),
            "loaded_models": _normalized_list(payload.get("loaded_models")),
            "capabilities": _normalized_list(payload.get("capabilities")),
            "raw": dict(payload),
        }, None
    except Exception as exc:
        return None, str(exc)


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
        "loaded_models": [],
        "capabilities": ["text-advisory", "labbridge-context-via-chat"],
        "raw": {},
    }


def probe_openguin() -> dict[str, Any]:
    generic, generic_error = _probe_generic()
    if generic:
        generic["generic_probe_error"] = None
        generic["legacy_probe_error"] = None
        return generic
    legacy, legacy_error = _probe_legacy()
    if legacy:
        legacy["generic_probe_error"] = generic_error
        legacy["legacy_probe_error"] = None
        return legacy
    compat = _probe_ollama_compat()
    if compat:
        compat["generic_probe_error"] = generic_error
        compat["legacy_probe_error"] = legacy_error
        return compat
    return {
        "available": False,
        "mode": "offline",
        "base": OPENPENGUIN_NATIVE_BASE,
        "runtime_base": OPENPENGUIN_RUNTIME_BASE,
        "api_version": None,
        "models": [],
        "loaded_models": [],
        "capabilities": [],
        "generic_probe_error": generic_error,
        "legacy_probe_error": legacy_error,
        "raw": {},
    }


def infrastructure_status() -> dict[str, Any]:
    try:
        value = _request_json("/v1/status", timeout=1.5)
        return dict(value) if isinstance(value, Mapping) else {"available": False}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def infrastructure_policies() -> dict[str, Any]:
    try:
        value = _request_json("/v1/policies", timeout=1.5)
        return dict(value) if isinstance(value, Mapping) else {"available": False, "policies": []}
    except Exception as exc:
        return {"available": False, "policies": [], "error": str(exc)}


def _wrap_answer(*, answer: str, context_packet: Mapping[str, Any], question: str, model: str, mode: str, runtime: str, fallback_used: bool, upstream: Mapping[str, Any] | None = None, native_error: str | None = None) -> dict[str, Any]:
    upstream = dict(upstream or {})
    return finalize_packet(
        {
            "schema": AI_SUGGESTION_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "ai_suggestion",
            "source_app": {
                "name": "OpenPenguin",
                "role": "local-ai-advisory-layer",
                "model": str(upstream.get("model") or model),
                "runtime": str(upstream.get("runtime") or runtime),
                "adapter_mode": mode,
                "fallback_used": bool(fallback_used),
                "native_error": str(native_error)[:1000] if native_error else None,
                "request_id": upstream.get("request_id"),
                "policy_id": upstream.get("policy_id"),
                "model_route": upstream.get("model_route"),
                "elapsed_ms": upstream.get("elapsed_ms"),
                "client": upstream.get("client"),
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
    if not model or model.lower() == "auto":
        models = list(compat.get("models") or [])
        if not models:
            raise OpenPenguinAdapterError("no-model", "OpenPenguin fallback has no installed model")
        model = str(models[0])
    answer = ask_local_model(str(compat["base"]), model, question, context_packet, temperature=float(temperature))
    if not str(answer).strip():
        raise OpenPenguinAdapterError("empty-response", "OpenPenguin returned an empty advisory")
    return _wrap_answer(answer=str(answer), context_packet=context_packet, question=question, model=model, mode="ollama-compat", runtime=str(compat["base"]), fallback_used=bool(native_error), native_error=native_error)


def request_advisory(context_packet: Mapping[str, Any], *, question: str, model: str = "auto", temperature: float = 0.2, timeout_ms: int | None = None) -> dict[str, Any]:
    if context_packet.get("schema") != ENGINEERING_CONTEXT_SCHEMA:
        raise ValueError("OpenPenguin advisory requires labbridge.ai-context/v1")
    question = str(question).strip()
    model = str(model or "auto").strip() or "auto"
    if not question:
        raise ValueError("question is required")
    if not 0.0 <= float(temperature) <= 2.0:
        raise ValueError("temperature must be within 0..2")

    status = probe_openguin()
    if not status["available"]:
        raise OpenPenguinAdapterError("offline", "OpenPenguin is unavailable")

    errors: list[str] = []
    if status["mode"] == "openguin-infrastructure-v2":
        payload: dict[str, Any] = {
            "api_version": GENERIC_API_VERSION,
            "client": {"app_id": "engineering-lab", "app_version": "0.10.0"},
            "context": dict(context_packet),
            "question": question,
            "model": model,
            "temperature": float(temperature),
        }
        if timeout_ms is not None:
            payload["timeout_ms"] = int(timeout_ms)
        try:
            response = _request_json("/v1/advisory", payload, timeout=max(10.0, (int(timeout_ms or 600000) / 1000.0) + 5.0))
            if isinstance(response, Mapping):
                answer = str(response.get("answer") or response.get("summary") or "")
                if answer.strip():
                    return _wrap_answer(answer=answer, context_packet=context_packet, question=question, model=model, mode="openguin-infrastructure-v2", runtime=str(response.get("runtime") or OPENPENGUIN_RUNTIME_BASE), fallback_used=False, upstream=response)
            errors.append("generic infrastructure returned no advisory text")
        except Exception as exc:
            errors.append(f"generic: {exc}")

    if status["mode"] in {"openguin-infrastructure-v2", "native-labbridge-legacy"}:
        try:
            legacy_model = model
            if legacy_model.lower() == "auto":
                candidates = list(status.get("loaded_models") or status.get("models") or [])
                legacy_model = str(candidates[0]) if candidates else "auto"
            response = _request_json(
                "/labbridge/v1/advisory",
                {
                    "api_version": LEGACY_API_VERSION,
                    "context": dict(context_packet),
                    "question": question,
                    "model": legacy_model,
                    "temperature": float(temperature),
                    "requested_response_schema": AI_SUGGESTION_SCHEMA,
                },
                timeout=605.0,
            )
            if isinstance(response, Mapping):
                answer = str(response.get("answer") or response.get("summary") or response.get("response") or "")
                if answer.strip():
                    return _wrap_answer(answer=answer, context_packet=context_packet, question=question, model=legacy_model, mode="native-labbridge-legacy", runtime=str(response.get("runtime") or OPENPENGUIN_RUNTIME_BASE), fallback_used=bool(errors), upstream=response, native_error="; ".join(errors) if errors else None)
            errors.append("legacy LabBridge returned no advisory text")
        except Exception as exc:
            errors.append(f"legacy: {exc}")

    return _compat_advisory(context_packet, question=question, model=model, temperature=float(temperature), native_error="; ".join(errors) or status.get("generic_probe_error") or status.get("legacy_probe_error"))


def native_api_contract() -> dict[str, Any]:
    return {
        "generic_api_version": GENERIC_API_VERSION,
        "legacy_api_version": LEGACY_API_VERSION,
        "native_base": OPENPENGUIN_NATIVE_BASE,
        "runtime_fallback_base": OPENPENGUIN_RUNTIME_BASE,
        "preferred_endpoints": ["GET /v1/health", "GET /v1/status", "GET /v1/policies", "GET /v1/capabilities", "POST /v1/advisory"],
        "legacy_endpoints": ["GET /labbridge/v1/health", "GET /labbridge/v1/capabilities", "POST /labbridge/v1/advisory"],
        "client_identity": {"app_id": "engineering-lab", "app_version": "0.10.0"},
        "context_schema": ENGINEERING_CONTEXT_SCHEMA,
        "fallback": f"Ollama-compatible /api/chat on {OPENPENGUIN_RUNTIME_BASE}",
        "required_security": ["loopback-only", "bounded request/response", "executed=false", "mutation_authority=false", "Engineering Lab remains scientific authority"],
    }
