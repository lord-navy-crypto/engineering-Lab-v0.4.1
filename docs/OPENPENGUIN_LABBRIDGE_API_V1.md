# OpenPenguin LabBridge API v1

This document defines the minimal native adapter that lets OpenPenguin connect to Engineering Lab without changing OpenPenguin's model/runtime core.

## Roles

- BetterBoard: `real-world-ingress`
- Engineering Lab: `scientific-computation-and-evidence-core`
- OpenPenguin: `local-ai-advisory-layer`

OpenPenguin is advisory. It must never silently mutate BetterBoard measurements or Engineering Lab scientific state.

## Base URL

Default local endpoint:

```text
http://127.0.0.1:11435
```

Loopback-only is the recommended default.

## 1. Capability discovery

```http
GET /labbridge/v1/capabilities
```

Response:

```json
{
  "api_version": "labbridge-openguin-api/v1",
  "models": ["model-name"],
  "capabilities": [
    "text-advisory",
    "labbridge.ai-context/v1",
    "labbridge.ai-suggestion/v1"
  ]
}
```

Engineering Lab will prefer this native API when it is available. If this endpoint is absent, it falls back to the existing Ollama-compatible API on the same OpenPenguin runtime.

## 2. Advisory request

```http
POST /labbridge/v1/advisory
Content-Type: application/json
```

Request:

```json
{
  "api_version": "labbridge-openguin-api/v1",
  "context": {
    "schema": "labbridge.ai-context/v1"
  },
  "question": "What is the strongest unresolved uncertainty?",
  "model": "model-name",
  "temperature": 0.2,
  "requested_response_schema": "labbridge.ai-suggestion/v1"
}
```

The full `context` object is an Engineering Lab content-addressed AI Context packet. OpenPenguin should preserve its `packet_id` as an evidence reference in the response.

Preferred response:

```json
{
  "schema": "labbridge.ai-suggestion/v1",
  "bridge_version": "1.0",
  "packet_type": "ai_suggestion",
  "source_app": {
    "name": "OpenPenguin",
    "role": "local-ai-advisory-layer",
    "model": "model-name"
  },
  "intended_consumer": {
    "name": "Engineering Lab",
    "role": "scientific-computation-and-evidence-core"
  },
  "title": "...",
  "summary": "...",
  "question": "...",
  "evidence_refs": ["ai-context-..."],
  "executed": false,
  "packet_id": "ai-suggestion-...",
  "content_sha256": "..."
}
```

If OpenPenguin does not want to implement content-addressing internally, it may initially return:

```json
{"answer": "..."}
```

Engineering Lab will wrap that answer into a valid `labbridge.ai-suggestion/v1` packet.

## 3. Action proposals

A future OpenPenguin implementation may return:

```text
labbridge.action-proposal/v1
```

An ActionProposal must include:

- `target`
- `rationale`
- `expected_effect`
- `falsification_observable`
- `executed: false`

The LabBridge adapter does not execute it. Human/system approval must be a separate Engineering Lab provenance event.

## Security and scientific boundaries

OpenPenguin native LabBridge should preserve these rules:

1. Bind to loopback by default.
2. Bound request and response sizes.
3. Do not execute code supplied in context.
4. Do not mutate measurement, solver, UQ, validation or provenance state.
5. Do not claim an ActionProposal has executed.
6. Do not relabel simulated data as measured data.
7. Do not infer missing units or validation status.
8. Preserve the source AI Context packet ID as evidence provenance.

## Compatibility

OpenPenguin does **not** need to replace its existing Ollama-compatible endpoints.

Recommended architecture:

```text
OpenPenguin model/runtime core
        │
        ├── existing /api/tags + /api/chat
        │
        └── thin /labbridge/v1 adapter
```

Engineering Lab automatically detects the native adapter and otherwise falls back to `/api/chat`.
