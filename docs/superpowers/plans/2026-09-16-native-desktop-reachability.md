# Native Desktop Reachability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every user-facing Engineering Lab surface and embedded child capability discoverable and launchable from the initial native Tauri desktop.

**Architecture:** Add a native `surfaces.json` manifest consumed by Rust and the desktop Workbench; carry a capability id through `launch_module` into the managed Streamlit process; install a dedicated deep-link entry patch that renders the real existing workspace/route/embedded UI. CI cross-checks Python registry coverage, embedded UI coverage, native manifest wiring and desktop launch wiring.

**Tech Stack:** Tauri/Rust, vanilla HTML/CSS/JavaScript, Python/Streamlit, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-native-desktop-reachability-design.md`

## Global Constraints

- Do not change scientific algorithms, model outputs, result schemas, provenance meaning or validation meaning.
- Opening a workspace must not auto-start queued jobs or broaden execution semantics.
- Existing Safe/Full module semantics remain authoritative.
- User-facing profile-specific capability may launch only in a declared legal host profile.
- Project-dependent renderers must use the canonical Project Kernel active project; never invent a project path.
- Preserve the known Pipeline DAG auto-advance issue as an unfixed separate issue.
- Desktop reachability is not scientific validation.

---

### Task 1: Add RED native reachability contract

**Files:**
- Create: `scripts/native_desktop_reachability_validation.py`
- Create: `.github/workflows/native-desktop-reachability-integrity.yml`

**Interfaces:**
- Consumes: `physical_lab_surface_registry.SURFACES`, `EMBEDDED_UI_MODULES`, `web/index.html`, `web/surface_catalog.js`, `src-tauri/resources/surfaces.json`, `src-tauri/src/lib.rs`, `src-tauri/resources/ui/sitecustomize.py`, `src-tauri/tauri.conf.json`.
- Produces: deterministic pass/fail contract and JSON summary counts.

- [ ] **Step 1: Write validator before any production manifest/UI code.**

The validator loads the Python registry dynamically, expects `surfaces.json`, checks unique ids/categories/host profiles/targets, checks every registry surface and embedded module has native coverage, and checks required native wiring markers.

- [ ] **Step 2: Run `python scripts/native_desktop_reachability_validation.py`.**

Expected RED result: fail because `src-tauri/resources/surfaces.json` and native Workbench wiring do not yet exist.

- [ ] **Step 3: Add workflow invoking `py_compile` plus the validator.**

- [ ] **Step 4: Commit the RED contract.**

---

### Task 2: Add canonical native surface manifest

**Files:**
- Create: `src-tauri/resources/surfaces.json`

**Interfaces:**
- Produces rows with fields `id`, `label`, `category`, `description`, `sourceSurfaceId`, `kind`, `launchMode`, `profiles`, `preferredProfiles`, `targetModule`, `targetCallable`, `argumentMode`, `routeTarget`, `routeHint`.

- [ ] **Step 1: Copy all Python Surface Registry rows into native metadata without changing their semantics.**
- [ ] **Step 2: Add explicit native child rows for every `EMBEDDED_UI_MODULES` member.**
- [ ] **Step 3: Give every row a deterministic legal host list. Profile-independent rows use generic host preference `numerical-methods`, `oscillation-integration`, `nonlinear-chaos`.**
- [ ] **Step 4: Re-run validator.**

Expected result: coverage checks advance; desktop/Rust/deep-link wiring remains RED.

---

### Task 3: Expose surface catalog and deep-link through Tauri

**Files:**
- Modify: `src-tauri/src/lib.rs`

**Interfaces:**
- Add serializable `SurfaceSpec` matching `surfaces.json`.
- Add `surface_specs() -> Result<Vec<SurfaceSpec>, String>`.
- Add `#[tauri::command] fn list_surface_catalog() -> Result<Vec<SurfaceSpec>, String>`.
- Extend `launch_module(..., mode: Option<String>, surface_id: Option<String>)`.
- When starting a standard Streamlit Lab and `surface_id` is present, export `PHYSICAL_LAB_INITIAL_SURFACE`.
- Register `list_surface_catalog` in `generate_handler!`.

- [ ] **Step 1: Add the minimal Rust structs/parser/command required by the validator.**
- [ ] **Step 2: Extend the launch command without changing existing calls that omit `surfaceId`.**
- [ ] **Step 3: Run `cargo check --manifest-path src-tauri/Cargo.toml`.**
- [ ] **Step 4: Re-run reachability validator.**
- [ ] **Step 5: Commit.**

---

### Task 4: Add Streamlit native deep-link entry

**Files:**
- Create: `src-tauri/resources/ui/physical_lab_native_surface_entry.py`
- Modify: `src-tauri/resources/ui/sitecustomize.py`
- Modify: `src-tauri/tauri.conf.json`

**Interfaces:**
- `install()` wraps `physical_lab_advanced.render_advanced_experiments` after existing project/surface patches.
- Reads `PHYSICAL_LAB_INITIAL_SURFACE` once per session.
- `render_requested_surface(st, namespace, profile, capability_id)` renders direct/profile/route/embedded targets.
- Route helpers delegate to existing Project Interop, Project Kernel, BetterBoard/LabBridge and reproducibility UIs.

- [ ] **Step 1: Add the entry module with an explicit capability-to-target loader based on `surfaces.json`.**
- [ ] **Step 2: For renderer argument modes call the existing callable with exactly the declared argument order.**
- [ ] **Step 3: For project-dependent targets, show Project Kernel/project selection when no active project exists rather than creating fake state.**
- [ ] **Step 4: Add explicit route target functions for all route rows.**
- [ ] **Step 5: Install the patch from `sitecustomize.py` and bundle it in `tauri.conf.json`.**
- [ ] **Step 6: Run `python -m py_compile` on the new module plus `sitecustomize.py` and rerun the reachability validator.**
- [ ] **Step 7: Commit.**

---

### Task 5: Add native Workbench UI

**Files:**
- Create: `web/surface_catalog.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`

**Interfaces:**
- Native sidebar `data-view="capabilities"`.
- `capabilitiesView` with summary, search, category filters and card grid.
- `surface_catalog.js` calls `list_surface_catalog`, resolves host readiness from `module_statuses`, calls `install_module` when needed, then calls `launch_module` with `{moduleId, mode:'safe', surfaceId}`.
- Uses existing `labFrame`, `openLabTitle`, `openLabUrl` and global `showView('lab')` to present the actual workspace.

- [ ] **Step 1: Add sidebar and Workbench view markup plus `surface_catalog.js` script include.**
- [ ] **Step 2: Render every catalog row with category/access/host badges and `Prepare & Open`.**
- [ ] **Step 3: Add search/category filtering and visible counts.**
- [ ] **Step 4: Implement deterministic host resolution and install-then-launch behavior.**
- [ ] **Step 5: Ensure Workbench-launched server is stopped when the embedded Lab view closes.**
- [ ] **Step 6: Add responsive card/filter styles without changing scientific meaning.**
- [ ] **Step 7: Re-run reachability validator.**
- [ ] **Step 8: Commit.**

---

### Task 6: Verify representative capability families

**Files:**
- Modify only if verification exposes wiring defects.

**Interfaces:** representative deep-link ids:
- direct: `visual-analytics`, `model-coupling`, `result-inspector`
- route: `utube-studio`, `data-bridge`, `reproducibility-pack`
- profile: `kerr-geodesics`, `undulator-spectrum`, `radia-forward`
- embedded: `utube-robust`, `utube-hysteresis`, `model-depth-iv`, `radiation-response-surface`

- [ ] **Step 1: Run native reachability validator.**
- [ ] **Step 2: Run `python scripts/surface_registry_validation.py`.**
- [ ] **Step 3: Run `python scripts/ui_semantics_validation.py`.**
- [ ] **Step 4: Run relevant U-Tube, Result Inspector, Visual Analytics, Model Coupling, Pipeline and source-integrity validators.**
- [ ] **Step 5: Run `cargo check --manifest-path src-tauri/Cargo.toml`.**
- [ ] **Step 6: Run `npm run desktop:build`.**
- [ ] **Step 7: Inspect GitHub Actions for fresh branch/PR runs before claiming readiness.**

---

### Task 7: Open reviewable PR and manual-test checkpoint

**Files:** documentation only if test findings require notes.

- [ ] **Step 1: Compare branch against `feature/shared-scientific-ui-semantics` and review changed files.**
- [ ] **Step 2: Create PR summarizing manifest coverage, native Workbench behavior, deep-link architecture and preserved boundaries.**
- [ ] **Step 3: Wait for fresh CI conclusions; fix any failures before claiming green.**
- [ ] **Step 4: Stop at manual-testing checkpoint instead of mechanically redesigning workspace internals.**
