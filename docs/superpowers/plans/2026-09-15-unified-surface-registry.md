# Unified Surface Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every existing user-facing Engineering Lab workspace discoverable from a central All Workspaces surface and prevent future UI renderers from becoming invisible/orphaned.

**Architecture:** Add a declarative surface registry that classifies direct-launch, embedded-only, and profile-only user-facing surfaces. Project-level navigation renders the catalog and dispatches safe direct-launch workspaces without duplicating existing renderer implementations. CI validates registry coverage, renderer existence, DMG bundling, central routing, and explicit classification of every known `physical_lab_*_ui.py` module.

**Tech Stack:** Python 3, Streamlit, Tauri resource bundling, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-unified-surface-registry-design.md`

## Global Constraints

- Do not change scientific algorithms, numerical semantics, validation meaning, queue/start boundaries, or model assumptions.
- Preserve existing specialist routes and profile-specific advanced suites.
- Never expose pure infrastructure as meaningless menu items.
- A direct-launch surface must have a callable that can safely run from project scope.
- A profile-only/embedded-only surface must still be discoverable and explicitly classified.
- New registry/runtime files must be bundled in `src-tauri/tauri.conf.json`.
- CI must fail when a new user-facing `physical_lab_*_ui.py` module is neither registered nor explicitly classified.

---

### Task 1: Add registry validation RED test

**Files:**
- Create: `scripts/surface_registry_validation.py`
- Create: `.github/workflows/surface-registry-integrity.yml`

**Interfaces:**
- Consumes: repository source tree and `src-tauri/tauri.conf.json`
- Produces: deterministic validation for registry existence, catalog wiring, bundle coverage, renderer existence, and UI-module classification

- [ ] **Step 1:** Write validation that fails because `physical_lab_surface_registry.py` and `All Workspaces` do not yet exist.
- [ ] **Step 2:** Add GitHub Actions workflow running Python compile plus the validation script.
- [ ] **Step 3:** Confirm current feature branch is RED only on the new surface-registry assertions.

### Task 2: Implement canonical surface registry

**Files:**
- Create: `src-tauri/resources/ui/physical_lab_surface_registry.py`
- Modify: `src-tauri/tauri.conf.json`

**Interfaces:**
- Produces: `SURFACES`, `EMBEDDED_UI_MODULES`, `get_surface(surface_id)`, `surface_categories()`, `surfaces_for_catalog(profile)`, `render_surface(st, surface, profile, project_path=None)`

- [ ] **Step 1:** Define explicit records for existing direct-launch workspaces already proven safe from project scope.
- [ ] **Step 2:** Add direct-launch records for Engineering Decision, Operations Planning, Quality & Reliability, Risk Economics, Requirements Verification, Digital Twin, Research Orchestrator, Evidence Center, and other safe renderer APIs confirmed by source inspection.
- [ ] **Step 3:** Classify profile-only and embedded-only user-facing UI modules explicitly instead of pretending they can safely launch without required namespace state.
- [ ] **Step 4:** Add registry module to Tauri resources.
- [ ] **Step 5:** Run compile/validation; registry assertions should advance while project-catalog assertion remains RED.

### Task 3: Add All Workspaces catalog and dispatcher

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_project_interop_ui.py`

**Interfaces:**
- Consumes: registry APIs from Task 2
- Produces: `All Workspaces` project surface and safe in-place launcher

- [ ] **Step 1:** Add `All Workspaces` to `PROJECT_SURFACES`.
- [ ] **Step 2:** Render grouped categories with workspace label, concise description, scope badge, and explicit launch/select action.
- [ ] **Step 3:** For direct-launch surfaces, invoke registry dispatcher only after explicit selection.
- [ ] **Step 4:** For profile-only surfaces, show the required profile/route rather than attempting an unsafe render.
- [ ] **Step 5:** Keep existing Project Home, U-Tube Studio, and Project Tools unchanged and reachable.
- [ ] **Step 6:** Run validation and compile; central wiring assertions should become GREEN.

### Task 4: Close user-facing coverage gaps

**Files:**
- Modify: `src-tauri/resources/ui/physical_lab_surface_registry.py`
- Modify only if required by real callable signatures: affected `physical_lab_*_ui.py` modules

**Interfaces:**
- Consumes: all bundled `physical_lab_*_ui.py` modules
- Produces: explicit registry or embedded/profile classification for each user-facing UI module

- [ ] **Step 1:** Audit all bundled UI modules against registry/classification.
- [ ] **Step 2:** Add missing safe direct-launch surfaces where a project-scope callable exists.
- [ ] **Step 3:** Mark remaining renderer modules embedded-only/profile-only with a human-readable route note and reason.
- [ ] **Step 4:** Ensure no pure backend module is incorrectly promoted.
- [ ] **Step 5:** Run validation until orphan count is zero.

### Task 5: Regression protection and final verification

**Files:**
- Modify as required: existing integrity scripts only when old exact-call assertions legitimately need the new surface route

**Interfaces:**
- Produces: green Surface Registry Integrity plus existing Source Integrity and project/U-Tube routing integrity

- [ ] **Step 1:** Run Surface Registry Integrity.
- [ ] **Step 2:** Run Source Integrity.
- [ ] **Step 3:** Run U-Tube Research Studio Entry Integrity / project surface routing checks.
- [ ] **Step 4:** Inspect failures and update only stale structural assertions; do not weaken scientific/execution boundaries.
- [ ] **Step 5:** Verify PR diff contains no unrelated files and no orphan UI modules.
- [ ] **Step 6:** Squash merge only after all required checks are green.
