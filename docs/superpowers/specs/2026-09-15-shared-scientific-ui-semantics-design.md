# Shared Scientific UI Semantics — Design

Date: 2026-09-15
Branch: `feature/shared-scientific-ui-semantics`
Base: `feature/expand-physics-simulation-scenarios` @ `bd2c9d7bef02c47c077e7ea5d32dac10da82c9ae`

## Purpose

Engineering Lab now has many user-facing research surfaces, but object identity, status, validation, provenance, and execution state are presented differently across workspaces. The goal of this change is to introduce one thin, shared presentation layer that makes those semantics consistent without changing scientific algorithms, result schemas, provenance records, model assumptions, or execution behavior.

This first phase is intentionally limited to a testable vertical slice. It will integrate the shared semantics into Project Home, Result Inspector, Visual Analytics, Model Coupling, and Pipeline DAG. The rest of the application remains unchanged until this slice is tested in real use.

## Non-goals

This work will not:
- change scientific computations or model outputs;
- infer validation from successful execution;
- infer scientific trust from the existence of provenance;
- infer object type from arbitrary payload structure;
- redesign every Engineering Lab workspace in one pass;
- replace existing detailed provenance, contract, uncertainty, or validation views;
- change queue/start semantics or trigger computation.

## Core semantics

The shared layer represents two independent concepts: object identity and status axes.

### Object identity

The initial supported object classes are:
- `MEASUREMENT`
- `DATASET`
- `MODEL`
- `RESULT`

Object identity must be passed explicitly by the caller. The shared helper must not guess an object class from field names, schemas, or appearance.

Each object card may display a compact set of caller-supplied metadata such as ID, source, schema, rows, columns, hash, or profile. The shared layer formats these values but does not reinterpret them.

### Independent status axes

The initial shared status card has four axes:

1. `Validation`
   - `PASS`
   - `REVIEW`
   - `FAIL`
   - `NOT ESTABLISHED`

2. `Scientific Status`
   - `SUPPORTED`
   - `REVIEW`
   - `NOT ESTABLISHED`
   - `OUT OF SCOPE`

3. `Provenance`
   - `RECORDED`
   - `PARTIAL`
   - `NOT RECORDED`
   - `UNSPECIFIED`

4. `Execution`
   - `CONFIGURED`
   - `PENDING`
   - `QUEUED`
   - `RUNNING`
   - `SUCCEEDED`
   - `FAILED`
   - `CANCELLED`
   - `INTERRUPTED`
   - `BLOCKED`
   - `NOT APPLICABLE`

These axes are deliberately independent. In particular:
- `Execution = SUCCEEDED` must never imply `Validation = PASS`.
- `Provenance = RECORDED` must never imply `Scientific Status = SUPPORTED`.
- `Validation = PASS` must mean only the validation state explicitly supplied by the caller.
- Missing values must render as an explicit unknown/not-established state rather than being silently promoted.

Every status must be conveyed with visible text and a symbol. Color can be supplemental but cannot be the only carrier of meaning.

## Shared UI module

Create one bundled runtime module, tentatively:

`src-tauri/resources/ui/physical_lab_ui_semantics.py`

Responsibilities:
- validate and normalize explicitly supplied object/status values;
- render a compact context header;
- render an object identity card;
- render the four-axis status card;
- provide stable textual labels/symbols used by participating workspaces.

The module must remain presentation-only. It must not import model solvers, execute jobs, inspect arbitrary payloads to infer scientific meaning, or mutate project records.

Because this is a new runtime Python module, it must be included in the Tauri resource bundle and covered by resource-integrity validation.

## Context header

The shared context header follows this hierarchy:

`PROJECT → WORKSPACE → TASK → SOURCE`

Fields may be omitted only when genuinely unavailable. The header is informational and must not become a second navigation state machine.

Examples:
- Project Home: `PROJECT → Project Home`
- Result Inspector: `PROJECT → Result Inspector → Inspect Result → persisted result`
- Visual Analytics: `PROJECT → Visual Analytics → Selection & Linked Views → canonical dataset`
- Model Coupling: `PROJECT → Model Coupling → Review Packet → canonical dataset`
- Pipeline DAG: `PROJECT → Pipeline DAG → Run Graph → workflow run`

## First-phase integrations

### Project Home

Add the shared context header and a project-level status summary. Existing counts remain unchanged. The page must continue to say that indexed counts do not imply scientific validation.

### Result Inspector

Use the shared object card for the selected `RESULT` and shared status axes for explicit contract/sanity/provenance/execution information already available in the current inspection path. Existing detailed schema map, provenance chain, uncertainty, contract, and materialization sections remain authoritative and unchanged.

No new validation inference is allowed. If execution status is unavailable in the selected result identity, it must be shown as `NOT APPLICABLE` or omitted according to the explicit caller decision, not guessed.

### Visual Analytics

Use the shared context header and object card for the selected source. The source's type must come from existing source metadata/caller mapping. Linked-view selection state is not a scientific status and must not be placed on the validation axis.

### Model Coupling

Use a `DATASET` source card and a `MODEL` target card where appropriate. Queue state is shown only on the execution axis. Existing language that mapping does not establish compatibility, causality, calibration validity, or model suitability remains unchanged.

### Pipeline DAG

Reuse the same execution vocabulary and symbols for node/run states where possible. The DAG remains the detailed execution visualization; the shared status card is only a compact summary. Readiness/provenance edges must still not be described as physical data transfer.

## Error and unknown-state handling

The shared helper must fail closed semantically:
- unknown object type: render `UNKNOWN` only if the caller explicitly passes an unsupported value, and surface a warning in development/test validation;
- unknown status value: do not map it to the nearest 'good' state;
- missing validation/scientific/provenance status: render explicit not-established/unspecified text;
- missing execution status: use caller-specified `NOT APPLICABLE` or omit it when the surface has no execution concept.

No exception in the shared presentation layer should trigger model execution or project mutation.

## Accessibility and visual rules

- Status meaning must be readable without color.
- Symbols and text are always shown together.
- Avoid red/green-only semantics.
- Object class labels are uppercase and stable.
- Hashes may be truncated visually but underlying exact values remain available in detailed views.
- Scientific-boundary captions remain in their owning workspaces; the shared module does not replace them.

## Testing strategy

Add a dedicated semantic integrity test and workflow. The test must verify at minimum:

- supported object types and labels are stable;
- `SUCCEEDED` cannot produce or imply `PASS` validation;
- `RECORDED` provenance cannot produce or imply `SUPPORTED` scientific status;
- missing statuses remain explicit unknown/not-established states;
- object type is caller-supplied and not inferred from payload fields;
- status symbols always accompany text labels;
- the five first-phase workspaces import/use the shared layer;
- the shared runtime module is bundled in `tauri.conf.json`;
- existing workspace-specific integrity tests remain green.

TDD sequence:
1. add RED semantic contract + CI workflow;
2. implement shared semantics module;
3. integrate Project Home;
4. integrate Result Inspector;
5. integrate Visual Analytics;
6. integrate Model Coupling;
7. integrate Pipeline DAG;
8. run dedicated and existing regression workflows before merge.

## Testable milestone / temporary testing stop point

The project is ready for a temporary manual testing pause when all of the following are true:

- the shared semantics module is bundled and validated;
- all five first-phase workspaces use it successfully;
- dedicated semantic integrity CI is green;
- Surface Registry and Source Integrity are green;
- the relevant existing workspace workflows remain green;
- no scientific or execution semantics were broadened by the presentation layer.

At that point, further rollout should pause until real usage feedback is collected. The next phase should be driven by observed confusion or friction, not by mechanically converting every page.

## Rollout after testing

If the first-phase manual test is successful, the same layer can later be extended to U-Tube, Research Orchestrator/Sweep, Science Analysis, Evidence Center, Requirements/Verification, Quality & Reliability, and other project/profile surfaces. That second rollout is explicitly outside the first implementation milestone.
