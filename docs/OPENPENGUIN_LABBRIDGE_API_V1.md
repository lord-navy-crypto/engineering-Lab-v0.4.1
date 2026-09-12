# OpenPenguin LabBridge API v1

This document defines the native OpenPenguin adapter used by Engineering Lab without changing OpenPenguin's model/runtime core.

## Roles

- BetterBoard: `real-world-ingress`
- Engineering Lab: `scientific-computation-and-evidence-core`
- OpenPenguin: `local-ai-advisory-layer`

OpenPenguin is advisory. It must never silently mutate BetterBoard measurements or Engineering Lab scientific state.

## Port ownership

```text
http://127.0.0.1:11436  OpenPenguin native LabBridge API
http://127.0.0.1:11435  OpenPenguin private Ollama runtime / compatibility fallback
```

The separation is deliberate: port 11435 remains Ollama-compatible, while port 11436 belongs to the OpenPenguin application-level bridge.

## 1. Health

```http
GET http://127.0.0.1:11436/labbridge/v1/health
```

This reports the native bridge service itself and does not imply that a model is loaded.

## 2. Capability discovery

```http
GET http://127.0.0.1:11436/labbridge/v1/capabilities
```

Response includes:

```json
{
  "api_version": "labbridge-openguin-api/v1",
  "service": "OpenPenguin LabBridge",
  "runtime_base": "http://127.0.0.1:11435",
  "models": ["model-name"],
  "capabilities": [
    "text-advisory",
    "labbridge.ai-context/v1",
    "labbridge.ai-suggestion/v1",
    "read-only-scientific-advisory"
  ],
  "advisory_only": true
}
```

Engineering Lab accepts native mode only when the API version is supported, `models` is an array, and required capabilities include both `labbridge.ai-context/v1` and `labbridge.ai-suggestion/v1`.

If discovery is missing, malformed, unsupported, or incomplete, Engineering Lab falls back to the existing local Ollama-compatible runtime on port 11435 when available.

## 3. Advisory request

```http
POST http://127.0.0.1:11436/labbridge/v1/advisory
Content-Type: application/json
```

Request:

```json
{
  "api_version": "labbridge-openguin-api/v1",
  "context": {
    "schema": "labbridge.ai-context/v1",
    "packet_id": "ai-context-..."
  },
  "question": "What is the strongest unresolved uncertainty?",
  "model": "model-name",
  "temperature": 0.2,
  "requested_response_schema": "labbridge.ai-suggestion/v1"
}
```

OpenPenguin validates version, context schema, request size, question size, model name, temperature and response-schema request before forwarding a bounded advisory prompt to its private Ollama runtime on port 11435.

The current native implementation may return bounded advisory text plus model/runtime metadata rather than calculating the final content-addressed packet itself. Engineering Lab then wraps the response into canonical `labbridge.ai-suggestion/v1` using the same packet hashing implementation used throughout the project. This avoids duplicate canonical-JSON/SHA implementations across Rust and Python.

## 4. Rolling-upgrade compatibility

Native LabBridge is a preferred path, not a single point of failure.

```text
Stage 0: OpenPenguin private /api/tags + /api/chat on 11435
Stage 1: native GET /labbridge/v1/capabilities on 11436
Stage 2: native POST /labbridge/v1/advisory on 11436
```

If native discovery or advisory fails, Engineering Lab may downgrade locally to `http://127.0.0.1:11435/api/chat`. The resulting AISuggestion records `adapter_mode`, `fallback_used`, and a bounded `native_error` so the downgrade is visible in provenance.

A native failure must never trigger a cloud fallback automatically.

## 5. Action proposals

A future OpenPenguin implementation may produce `labbridge.action-proposal/v1`, but the bridge does not execute it. Approval must be a separate Engineering Lab provenance event before any new experiment manifest is created.

An ActionProposal remains `executed: false` at this layer.

## Security and scientific boundaries

1. Native and compatibility endpoints remain loopback-only by default.
2. Request and response sizes are bounded.
3. Context is evidence, not executable code.
4. OpenPenguin does not mutate measurement, solver, UQ, validation or provenance state.
5. OpenPenguin does not claim that an ActionProposal executed.
6. OpenPenguin does not relabel simulated data as measured data.
7. OpenPenguin does not infer missing units, calibration or validation status.
8. Engineering Lab preserves the source AI Context packet ID in advisory provenance.
9. Compatibility fallback remains local to port 11435.
10. API version and capabilities are explicit rather than inferred.

## Compatibility architecture

```text
OpenPenguin.app
    │
    ├── native LabBridge API · 127.0.0.1:11436
    │       ├── /health
    │       ├── /capabilities
    │       └── /advisory
    │
    └── private Ollama · 127.0.0.1:11435
            ├── /api/tags
            └── /api/chat
```

Engineering Lab prefers 11436 and safely falls back to 11435 when required.
