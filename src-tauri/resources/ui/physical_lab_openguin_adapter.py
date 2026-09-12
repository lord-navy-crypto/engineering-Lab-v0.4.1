"""OpenPenguin adapter for Engineering Lab LabBridge.

This module deliberately keeps OpenPenguin's model/runtime implementation behind a
small compatibility surface. It prefers a future native LabBridge API when present,
while retaining the existing Ollama-compatible loopback API at 127.0.0.1:11435.

Engineering Lab remains the scientific record. OpenPenguin responses are advisory
and this adapter never applies parameter changes, starts experiments, or mutates
measurement/solver state.
"""
from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from physical_lab_labbridge import AI_SUGGESTION_SCHEMA, finalize_packet
from physical_lab_local_ai import ask_local_model, discover_local_ai_engines

OPENPENGUIN_BASE = "http://127.0.0.1:11435"
NATIVE_API_VERSION = "labbridge-openguin-api/v1"
MAX_NATIVE_RESPONSE_BYTES = 2 * 1024 * 1024


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
        raise RuntimeError(f"OpenPenguin LabBridge API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenPenguin is unavailable at {OPENPENGUIN_BASE}: {exc.reason}") from exc
    if len(raw) > MAX_NATIVE_RESPONSE_BYTES:
        raise RuntimeError("OpenPenguin LabBridge response exceeded the local safety limit")
    return json.loads(raw.decode("utf-8"))


def probe_openguin() -> dict[str, Any]:
    """Return one normalized OpenPenguin capability record.

    Native LabBridge discovery is preferred. If OpenPenguin currently exposes only
    the existing Ollama-compatible API, the adapter returns compatibility mode.
    """
    try:
        payload = _request_json("/labbridge/v1/capabilities", timeout=1.2)
        if isinstance(payload, Mapping) and payload.get("api_version") == NATIVE_API_VERSION:
            return {
                "available": True,
                "mode": "native-labbridge",
                "base": OPENPENGUIN_BASE,
                "api_version": NATIVE_API_VERSION,
                "models": sorted({str(x) for x in payload.get("models", []) if str(x)}),
                "capabilities": sorted({str(x) for x in payload.get("capabilities", []) if str(x)}),
                "raw": dict(payload),
            }
    except Exception:
        pass

    engines = discover_local_ai_engines()
    engine = next((e for e in engines if e.get("running") and str(e.get("label") or "").startswith("OpenPenguin")), None)
    if engine:
        return {
            "available": True,
            "mode": "ollama-compat",
            "base": str(engine.get("base") or OPENPENGUIN_BASE),
            "api_version": "ollama-compatible",
            "models": list(engine.get("models") or []),
            "capabilities": ["text-advisory", "labbridge-context-via-chat"],
            "raw": {},
        }
    return {
        "available": False,
        "mode": "offline",
        "base": OPENPENGUIN_BASE,
        "api_version": None,
        "models": [],
        "capabilities": [],
        "raw": {},
    }


def request_advisory(
    context_packet: Mapping[str, Any],
    *,
    question: str,
    model: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Ask OpenPenguin and normalize the result to LabBridge AISuggestion v1."""
    if context_packet.get("schema") != "labbridge.ai-context/v1":
        raise ValueError("OpenPenguin advisory requires labbridge.ai-context/v1")
    question = str(question).strip()
    model = str(model).strip()
    if not question:
        raise ValueError("question is required")
    if not model:
        raise ValueError("model is required")

    status = probe_openguin()
    if not status["available"]:
        raise RuntimeError("OpenPenguin private runtime is unavailable")

    answer = ""
    if status["mode"] == "native-labbridge":
        response = _request_json(
            "/labbridge/v1/advisory",
            {
                "api_version": NATIVE_API_VERSION,
                "context": dict(context_packet),
                "question": question,
                "model": model,
                "temperature": float(temperature),
                "requested_response_schema": AI_SUGGESTION_SCHEMA,
            },
            timeout=600.0,
        )
        if isinstance(response, Mapping):
            if response.get("schema") == AI_SUGGESTION_SCHEMA:
                packet = dict(response)
                packet["executed"] = False
                return packet
            answer = str(response.get("summary") or response.get("answer") or response.get("response") or "")
    else:
        answer = ask_local_model(
            str(status["base"]),
            model,
            question,
            context_packet,
            temperature=float(temperature),
        )

    if not answer.strip():
        raise RuntimeError("OpenPenguin returned an empty advisory")
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
                "adapter_mode": status["mode"],
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


def native_api_contract() -> dict[str, Any]:
    """Machine-readable minimum contract for a future OpenPenguin-native adapter."""
    return {
        "api_version": NATIVE_API_VERSION,
        "base": OPENPENGUIN_BASE,
        "endpoints": {
            "GET /labbridge/v1/capabilities": {
                "response": {"api_version": NATIVE_API_VERSION, "models": ["string"], "capabilities": ["string"]},
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
        "required_security": [
            "loopback-only by default",
            "bounded request/response sizes",
            "no automatic execution of ActionProposal",
            "no mutation of Engineering Lab evidence",
        ],
    }
