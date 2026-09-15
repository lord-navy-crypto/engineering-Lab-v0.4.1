# Shared Scientific UI Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate a presentation-only shared semantic layer for object identity, context, and independent validation/scientific/provenance/execution status across five representative Engineering Lab workspaces, then stop for real manual testing.

**Architecture:** Add one bundled runtime module, `physical_lab_ui_semantics.py`, containing explicit enums/normalizers and Streamlit render helpers. Callers must pass object types and statuses explicitly; the shared layer never infers scientific truth, validation, provenance quality, or execution state from arbitrary payloads. Integrate the helper into Project Home, Result Inspector, Visual Analytics, Model Coupling, and Pipeline DAG, with a dedicated integrity script/workflow plus existing regression workflows.

**Tech Stack:** Python 3.12, Streamlit-style UI helpers, Plotly-containing existing workspaces, Tauri 2 resource bundle, GitHub Actions, repository validation scripts.

**Spec:** `docs/superpowers/specs/2026-09-15-shared-scientific-ui-semantics-design.md`

## Global Constraints

- Presentation-only: no model solver imports, job execution, project mutation, scientific computation, or schema changes in the shared module.
- Supported explicit object classes: `MEASUREMENT`, `DATASET`, `MODEL`, `RESULT`.
- Independent status axes: Validation, Scientific Status, Provenance, Execution.
- `Execution = SUCCEEDED` must never imply `Validation = PASS`.
- `Provenance = RECORDED` must never imply `Scientific Status = SUPPORTED`.
- Missing values must remain explicit unknown/not-established states.
- Status meaning must always include visible text and a symbol; color cannot be the only carrier.
- Existing scientific-boundary captions remain authoritative and must not be weakened.
- Existing Queue/Start and execution semantics must not change.
- First rollout is limited to Project Home, Result Inspector, Visual Analytics, Model Coupling, and Pipeline DAG.
- New runtime Python module must be listed in `src-tauri/tauri.conf.json`.
- Stop further rollout after this milestone and perform real manual testing before expanding to more workspaces.

---

### Task 1: RED semantic contract and workflow

**Files:**
- Create: `scripts/ui_semantics_validation.py`
- Create: `.github/workflows/ui-semantics-integrity.yml`

**Interfaces:**
- Consumes: repository source files only.
- Produces: a deterministic source/AST validation script that later tasks must satisfy.

- [ ] **Step 1: Write the failing semantic contract**

Create `scripts/ui_semantics_validation.py` with source/AST assertions that require:

```python
REQUIRED_OBJECT_TYPES = {"MEASUREMENT", "DATASET", "MODEL", "RESULT"}
REQUIRED_AXES = {"Validation", "Scientific Status", "Provenance", "Execution"}
FIRST_PHASE_FILES = {
    "physical_lab_project_interop_ui.py",
    "physical_lab_result_inspector_ui.py",
    "physical_lab_visual_analytics_ui.py",
    "physical_lab_model_coupling_ui.py",
    "physical_lab_pipeline_graph_ui.py",
}
```

The validator must fail until all of these are true:

```python
assert SEMANTICS.exists()
assert 'resources/ui/physical_lab_ui_semantics.py' in tauri_text
assert 'render_context_header' in semantics_text
assert 'render_object_card' in semantics_text
assert 'render_status_card' in semantics_text
assert 'normalize_object_type' in semantics_text
assert 'normalize_status_axes' in semantics_text
assert 'SUCCEEDED' in semantics_text and 'PASS' in semantics_text
assert 'RECORDED' in semantics_text and 'SUPPORTED' in semantics_text
```

It must also import the completed module later and assert behavior directly:

```python
axes = normalize_status_axes(execution="SUCCEEDED")
assert axes["validation"] == "NOT ESTABLISHED"
assert axes["scientific"] == "NOT ESTABLISHED"
axes = normalize_status_axes(provenance="RECORDED")
assert axes["scientific"] == "NOT ESTABLISHED"
assert normalize_object_type("RESULT") == "RESULT"
assert normalize_object_type("schema") == "UNKNOWN"
```

Require every first-phase file to import or reference `physical_lab_ui_semantics`. Require textual object-type calls appropriate to each surface: `RESULT` in Result Inspector, `DATASET`/source identity in Visual Analytics, `DATASET` and `MODEL` in Model Coupling, execution status integration in Pipeline DAG, and shared project context/status in Project Home.

- [ ] **Step 2: Add CI workflow**

Create `.github/workflows/ui-semantics-integrity.yml` that triggers on pull requests touching the shared module, five integration files, validator, workflow, or `tauri.conf.json`; install no extra dependency beyond Python; compile the relevant Python files; then run:

```bash
python scripts/ui_semantics_validation.py
```

- [ ] **Step 3: Run RED via pull-request CI**

Expected result: compile may pass, but the new semantic validation step fails because `physical_lab_ui_semantics.py` and integrations do not yet exist.

- [ ] **Step 4: Commit RED**

Commit message:

```text
Add RED shared scientific UI semantics contract
```

---

### Task 2: Shared semantic core and bundle wiring

**Files:**
- Create: `src-tauri/resources/ui/physical_lab_ui_semantics.py`
- Modify: `src-tauri/tauri.conf.json`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Produces:

```python
normalize_object_type(value: str) -> str
normalize_status_axes(*, validation: str | None = None, scientific: str | None = None,
                      provenance: str | None = None, execution: str | None = None) -> dict[str, str]
render_context_header(st: Any, *, project: str | None = None, workspace: str | None = None,
                      task: str | None = None, source: str | None = None) -> None
render_object_card(st: Any, *, object_type: str, title: str, metadata: dict[str, Any] | None = None) -> None
render_status_card(st: Any, *, validation: str | None = None, scientific: str | None = None,
                   provenance: str | None = None, execution: str | None = None) -> None
```

- [ ] **Step 1: Implement strict normalization**

Use stable maps such as:

```python
OBJECT_TYPES = {"MEASUREMENT", "DATASET", "MODEL", "RESULT"}
VALIDATION = {"PASS", "REVIEW", "FAIL", "NOT ESTABLISHED"}
SCIENTIFIC = {"SUPPORTED", "REVIEW", "NOT ESTABLISHED", "OUT OF SCOPE"}
PROVENANCE = {"RECORDED", "PARTIAL", "NOT RECORDED", "UNSPECIFIED"}
EXECUTION = {"CONFIGURED", "PENDING", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "BLOCKED", "NOT APPLICABLE"}
```

Unknown object types return `UNKNOWN`; unknown/missing statuses return each axis's explicit unknown value, never a nearby positive state.

- [ ] **Step 2: Implement text+symbol render helpers**

Use a stable status-symbol map and always render `symbol + label`. Do not encode meaning by color alone. `render_context_header` should render only caller-provided hierarchy components and must not write session state.

- [ ] **Step 3: Bundle the module**

Add:

```json
"resources/ui/physical_lab_ui_semantics.py": "ui/physical_lab_ui_semantics.py"
```

to the Tauri resource mapping.

- [ ] **Step 4: Run semantic validator**

Expected: core behavior assertions pass; integration assertions remain RED.

- [ ] **Step 5: Commit**

Commit message:

```text
Add shared scientific UI semantics core
```

---

### Task 3: Project Home integration

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_project_interop_ui.py`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Consumes: `render_context_header`, `render_status_card`.
- Produces: project-level semantic context without changing project counts or navigation.

- [ ] **Step 1: Extend RED assertions for Project Home**

Require `_render_project_home` to call `render_context_header` and `render_status_card`, while retaining the existing sentence that indexed counts do not imply scientific validation.

- [ ] **Step 2: Run validator and confirm Project Home-specific failure**

Expected: failure specifically names missing shared calls in `physical_lab_project_interop_ui.py`.

- [ ] **Step 3: Integrate shared context/status**

Import:

```python
from physical_lab_ui_semantics import render_context_header, render_status_card
```

In `_render_project_home`, render `PROJECT → Project Home` using the actual project name/ID already loaded. For status, pass explicit values only; do not derive validation from counts. Use `validation="NOT ESTABLISHED"`, `scientific="NOT ESTABLISHED"`, provenance only if the existing project metadata explicitly supports it, and execution only as an aggregate presentation when an existing job status is explicitly available.

- [ ] **Step 4: Run validator**

Expected: Project Home assertions pass.

- [ ] **Step 5: Commit**

Commit message:

```text
Use shared semantics on Project Home
```

---

### Task 4: Result Inspector integration

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_result_inspector_ui.py`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Consumes: `render_context_header`, `render_object_card`, `render_status_card`.
- Produces: explicit `RESULT` identity/status summary above existing schema/provenance/detail views.

- [ ] **Step 1: Add RED assertions**

Require Result Inspector to render an explicit `RESULT` object card and context header in `Inspect Result`. Require status values to be caller-derived from explicit existing contract/provenance/execution fields, not guessed by shared helpers.

- [ ] **Step 2: Run RED**

Expected: missing shared calls in Result Inspector.

- [ ] **Step 3: Integrate without changing inspection logic**

After `_build_inspection`, call the shared helpers. Use identity fields and `inspection.get("result_sha256")` as metadata. Map contract-conformance values conservatively: only an explicit existing pass-like conformance may be passed as `PASS`; otherwise `REVIEW`, `FAIL`, or `NOT ESTABLISHED`. Provenance is `RECORDED` only when explicit source identity/result hash evidence exists. Execution is taken from identity only if explicitly recorded; otherwise pass `NOT APPLICABLE`.

Keep `_render_schema_tree`, `_render_provenance_chain`, uncertainty, materialization, and environment sections unchanged.

- [ ] **Step 4: Run validator plus existing Result Inspector workflow**

Expected: semantic validator and Result Inspector integrity pass.

- [ ] **Step 5: Commit**

Commit message:

```text
Add semantic summary to Result Inspector
```

---

### Task 5: Visual Analytics integration

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_visual_analytics_ui.py`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Consumes: context/object helpers.
- Produces: explicit source identity without treating selection state as scientific status.

- [ ] **Step 1: Add RED assertions**

Require Visual Analytics to call `render_context_header` and `render_object_card` for the selected source. Assert the shared status card is not fed selection/lasso state as validation/scientific status.

- [ ] **Step 2: Run RED**

Expected: Visual Analytics integration failure only.

- [ ] **Step 3: Integrate source identity**

Use existing source metadata/caller knowledge to explicitly choose `MEASUREMENT`, `DATASET`, or `RESULT`; if the source kind is not known, pass `UNKNOWN` rather than inspecting arbitrary columns to guess. Include source ID/name/profile/hash/rows as available metadata. Preserve linked-view selection behavior exactly.

- [ ] **Step 4: Run semantic + Visual Analytics integrity workflows**

Expected: both pass.

- [ ] **Step 5: Commit**

Commit message:

```text
Expose source semantics in Visual Analytics
```

---

### Task 6: Model Coupling integration

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_model_coupling_ui.py`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Consumes: context/object/status helpers.
- Produces: `DATASET` source card, `MODEL` target card, and queue/start execution summary.

- [ ] **Step 1: Add RED assertions**

Require explicit `DATASET` and `MODEL` object cards and execution-axis use. Assert existing language about compatibility, causality, calibration validity, and model suitability remains in source.

- [ ] **Step 2: Run RED**

Expected: coupling-specific semantic assertions fail.

- [ ] **Step 3: Integrate cards/status**

Use the selected canonical dataset as `DATASET`; use target profile/model adapter as `MODEL`. Queue state maps only to execution. Do not set Validation or Scientific Status from packet creation, packet SHA, queue success, or execution success. Keep explicit Queue and Start helper separation unchanged.

- [ ] **Step 4: Run semantic + Model Coupling integrity workflows**

Expected: both pass.

- [ ] **Step 5: Commit**

Commit message:

```text
Use shared semantics in Model Coupling
```

---

### Task 7: Pipeline DAG integration

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_pipeline_graph_ui.py`
- Test: `scripts/ui_semantics_validation.py`

**Interfaces:**
- Consumes: `render_context_header`, `render_status_card`, stable execution labels/symbols.
- Produces: shared compact run/node execution summary while preserving existing DAG rendering.

- [ ] **Step 1: Add RED assertions**

Require shared context/status calls and stable execution vocabulary. Preserve existing graph boundary that readiness/provenance edges are not physical data transfer.

- [ ] **Step 2: Run RED**

Expected: Pipeline DAG-specific integration failure.

- [ ] **Step 3: Integrate compact summary**

Pass only explicit workflow/node execution state to the shared execution axis. Leave graph node shapes, edges, detailed run graph, and read-only semantics unchanged. Do not map graph success to validation/scientific support.

- [ ] **Step 4: Run semantic + Pipeline Graph integrity workflows**

Expected: both pass.

- [ ] **Step 5: Commit**

Commit message:

```text
Align Pipeline DAG execution semantics
```

---

### Task 8: Full regression gate and testing handoff

**Files:**
- Modify only if an existing test has an obsolete exact-string/AST assumption that conflicts with the approved shared semantic layer; do not weaken scientific/execution assertions.

**Interfaces:**
- Produces: a merge-ready first-phase vertical slice and explicit manual-test stop point.

- [ ] **Step 1: Run dedicated semantic workflow**

Expected: `UI Semantics Integrity` success on latest head.

- [ ] **Step 2: Run/check relevant regressions on latest head**

Require success for:

```text
Source Integrity
Surface Registry Integrity
Result Inspector Integrity
Visual Analytics Integrity
Model Coupling Integrity
Pipeline Graph Integrity
Project Interop Integrity
```

Any additionally triggered workspace workflow must also be green before merge.

- [ ] **Step 3: Verify PR head/mergeability**

Fetch PR metadata and confirm CI corresponds to the current head SHA.

- [ ] **Step 4: Squash merge**

Use expected-head SHA protection. Suggested title:

```text
Unify scientific UI semantics across core workspaces
```

- [ ] **Step 5: Stop feature expansion and begin real manual testing**

Manual test checklist:

```text
1. Open Project Home: context hierarchy is readable; counts do not look like validation.
2. Open Result Inspector: RESULT identity, four-axis status, schema map, provenance chain agree and do not overclaim.
3. Open Visual Analytics: source identity is clear; selecting/lassoing points changes linked views only, not scientific status.
4. Open Model Coupling: DATASET and MODEL are visually distinct; Queue is not Start; success does not imply compatibility/validation.
5. Open Pipeline DAG: execution status uses the same vocabulary; graph edges still read as readiness/provenance, not physical transfer.
6. Check unknown/missing states: show explicit NOT ESTABLISHED/UNSPECIFIED/NOT APPLICABLE rather than positive defaults.
7. Check accessibility: status text and symbols remain understandable without relying on color.
```

Do not expand the shared layer to U-Tube, Sweep, Science Analysis, Evidence Center, Requirements/Verification, or Quality/Reliability until this manual test produces concrete feedback.
