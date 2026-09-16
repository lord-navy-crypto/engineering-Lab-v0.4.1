# Engineering Lab Home — First-Principles + Progressive Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Engineering Lab's native Home around four real user intents, preserve full Workbench reachability, add unified search/launch behavior, and audit all packaged interactive Python UI entry points so hidden user-facing functionality cannot remain unclassified.

**Architecture:** Keep `surfaces.json` and `modules.json` as canonical capability/Lab metadata. Add a small navigation-only `home_layout.json`, extract capability launch/host-resolution logic from `surface_catalog.js` into a shared native launcher, and make Home, Workbench, and global search consume the same metadata and launcher. Add a second-generation AST audit that detects interactive Streamlit functions regardless of naming convention and requires explicit reachability classification.

**Tech Stack:** Tauri 2, vanilla HTML/CSS/JavaScript, Python 3.12 AST tooling, Streamlit, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-home-first-principles-progressive-disclosure-design.md`

## Global Constraints

- Do not change scientific algorithms, model equations, result schemas, validation semantics, provenance semantics, Safe/Full scientific meaning, or queue/execution semantics.
- Opening Home, search, or a capability must never auto-start scientific work.
- `surfaces.json` and `modules.json` remain authoritative for capability/Lab identity, host legality, and launch metadata.
- `home_layout.json` is navigation composition only; it must not duplicate renderer signatures, scientific metadata, or dependency logic.
- Workbench must retain complete native capability reachability.
- Physics Labs must remain limited to true first-class Labs/model launchers.
- Preserve the known Pipeline DAG auto-advance issue as an unfixed separate issue.
- Rotating U-Tube must remain first-class and retain six native experiment-family entries.

---

### Task 1: Add RED Home architecture contract

**Files:**
- Create: `scripts/home_information_architecture_validation.py`
- Modify: `.github/workflows/native-desktop-reachability-integrity.yml`

**Interfaces:**
- Consumes: `web/index.html`, `web/app.js`, `web/surface_catalog.js`, `src-tauri/resources/surfaces.json`, future `src-tauri/resources/home_layout.json`.
- Produces: deterministic failure until four task families, U-Tube family, Explore All, shared launcher, and unified search hooks exist.

- [ ] **Step 1: Write validator requiring Home task families `experiment`, `measure`, `model`, and `analyze`; require every referenced capability id to exist in `surfaces.json`.**
- [ ] **Step 2: Require the U-Tube featured family to contain exactly `utube-studio`, `utube-physical`, `utube-uncertainty`, `utube-advanced`, `utube-robust`, `utube-hysteresis`.**
- [ ] **Step 3: Require Home markup hooks for `homeTaskGrid`, `homeContinueContext`, `homeFeaturedFamilies`, `homeReadiness`, and an `Explore all capabilities` action.**
- [ ] **Step 4: Require Home, Workbench, and search to reference one shared launcher object rather than independent `install_module`/`launch_module` sequences.**
- [ ] **Step 5: Run `python scripts/home_information_architecture_validation.py`; expected RED because `home_layout.json` and new Home hooks do not exist yet.**
- [ ] **Step 6: Add validator to Native Desktop Reachability Integrity workflow and commit the RED contract.**

---

### Task 2: Add canonical Home navigation metadata

**Files:**
- Create: `src-tauri/resources/home_layout.json`
- Modify: `src-tauri/tauri.conf.json`
- Modify: `scripts/prepare.py`

**Interfaces:**
- Produces: `window.__PHYSICAL_LAB_HOME_LAYOUT__` in prepared `dist/app.js` and bundled `home_layout.json` for packaged review/debug use.

- [ ] **Step 1: Create four task-family rows:**
  - `experiment` → `utube-studio`, `utube-physical`, `utube-uncertainty`, plus Labs destination.
  - `measure` → `data-bridge`, `measurement-registry`, `betterboard-discovery`, `labbridge`.
  - `model` → `modelspec-diy`, `model-coupling`, `run-comparison`, `model-campaign`, `model-engineering`, `pipeline-dag`.
  - `analyze` → `result-inspector`, `visualization-studio`, `visual-analytics`, `engineering-vvuq`, `evidence-center`, `reproducibility-pack`.
- [ ] **Step 2: Add `featuredFamilies.rotating-utube` with the six canonical U-Tube ids.**
- [ ] **Step 3: Bundle `home_layout.json` in Tauri and embed it during `scripts/prepare.py`.**
- [ ] **Step 4: Re-run Home validator; expected to advance past metadata checks while shared launcher/Home markup remain RED.**

---

### Task 3: Extract shared native capability launcher

**Files:**
- Create: `web/capability_launcher.js`
- Modify: `web/surface_catalog.js`
- Modify: `scripts/prepare.py`
- Modify: `scripts/home_information_architecture_validation.py`

**Interfaces:**
- Produces global `window.PhysicalLabCapabilityLauncher` with:
  - `refreshStatuses()`
  - `resolveHost(surface)`
  - `prepareAndOpen(surfaceId)`
  - `stopActiveHost()`
  - `surfaceById(id)`
  - `allSurfaces()`
- Consumes existing Tauri commands `module_statuses`, `install_module`, `launch_module`, `stop_module` and existing `labFrame`, `openLabTitle`, `openLabUrl`, `showView('lab')`.

- [ ] **Step 1: Move `GENERIC_HOSTS`, Full-mode surface policy, host readiness resolution, install/prepare, launch, iframe query construction, active-host tracking, and cleanup from Workbench into `capability_launcher.js`.**
- [ ] **Step 2: Make `surface_catalog.js` render/filter only; replace its direct Tauri launch calls with `PhysicalLabCapabilityLauncher.prepareAndOpen(id)`.**
- [ ] **Step 3: Preserve current Workbench behavior and error messages.**
- [ ] **Step 4: Update `prepare.py` to concatenate shared launcher before Workbench code.**
- [ ] **Step 5: Run existing native reachability validator plus Home validator; both must pass launcher-sharing checks before proceeding.**

---

### Task 4: Rebuild Home around first-principles task families

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`

**Interfaces:**
- Consumes: `window.__PHYSICAL_LAB_HOME_LAYOUT__`, `window.__PHYSICAL_LAB_SURFACES__`, `PhysicalLabCapabilityLauncher`, existing project/task/result state.
- Produces Home sections:
  - `#homeTaskGrid`
  - `#homeContinueContext`
  - `#homeFeaturedFamilies`
  - `#homeReadiness`

- [ ] **Step 1: Replace old Home hero emphasis on Browse Labs / Runtime Center with four task-intent cards.**
- [ ] **Step 2: Each task card exposes 2–4 immediate actions and a `View all` action that opens Workbench with a task-appropriate filter/search state.**
- [ ] **Step 3: Add Continue/Recent context using existing active Project, recent Lab/capability state, task count, and latest result snapshot when available; provide concise first-use copy otherwise.**
- [ ] **Step 4: Render Rotating U-Tube as a featured family on Home using `home_layout.json`, not hard-coded renderer data.**
- [ ] **Step 5: Add compact readiness strip for Python, fragile-engine readiness, active Project, and active task count.**
- [ ] **Step 6: Add `Explore all capabilities` action that activates Workbench.**
- [ ] **Step 7: Apply responsive visual hierarchy: four intent cards → continue context → featured family → readiness/explore; keep advanced host/profile metadata out of Home.**
- [ ] **Step 8: Run Home validator and native reachability validator.**

---

### Task 5: Upgrade global search into unified discovery

**Files:**
- Modify: `web/app.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`

**Interfaces:**
- Consumes `modules`, canonical surfaces, categories, profiles, route hints, capability launcher.
- Produces unified search result groups for `Lab`, `Capability`, `Project/Data`, and `Runtime/Dependency` destinations.

- [ ] **Step 1: Replace Home/Labs-only search behavior with a unified search index built from modules + surfaces + key native destinations.**
- [ ] **Step 2: Capability matches must call the shared launcher; Lab matches use existing Lab open/install behavior; native destination matches use `showView(...)`.**
- [ ] **Step 3: Match label, id, category, profiles, routeHint, and descriptive keywords.**
- [ ] **Step 4: Ensure keyboard/touch accessible results and no hover-only actions.**
- [ ] **Step 5: Extend Home validator to require search → shared launcher wiring and run tests.**

---

### Task 6: Add Hidden Interaction Audit v2 RED contract

**Files:**
- Create: `scripts/interactive_entry_reachability_validation.py`
- Create: `src-tauri/resources/interactive_entry_classification.json`
- Modify: `.github/workflows/native-desktop-reachability-integrity.yml`

**Interfaces:**
- Detects packaged `physical_lab_*.py` functions containing Streamlit interaction calls including `button`, `form`, `form_submit_button`, `tabs`, `selectbox`, `multiselect`, `radio`, `checkbox`, `slider`, `number_input`, `text_input`, `text_area`, `file_uploader`, `data_editor`, `download_button`, `expander`.
- Valid classes: `native-surface`, `child-capability`, `aggregate`, `prerequisite-flow`, `helper`, `legacy`, `intentionally-internal`.

- [ ] **Step 1: Write AST detector that records `module.function` and interaction-call types.**
- [ ] **Step 2: Run with an initially empty classification file; expected RED listing every unclassified interactive function.**
- [ ] **Step 3: Add workflow step after existing render-entry audit.**
- [ ] **Step 4: Commit RED audit before adding classifications.**

---

### Task 7: Classify and expose newly discovered interactive surfaces

**Files:**
- Modify: `src-tauri/resources/interactive_entry_classification.json`
- Modify as required: `src-tauri/resources/surfaces.json`
- Modify as required: `src-tauri/resources/ui/physical_lab_native_workbench_adapters.py`
- Modify as required: `src-tauri/tauri.conf.json`
- Modify as required: `web/surface_catalog.js`

**Interfaces:**
- Every detected interactive function receives one explicit classification and valid native/parent/rationale reference.

- [ ] **Step 1: Review actual source for every RED audit result before classifying it.**
- [ ] **Step 2: Promote genuine independent user tasks to `native-surface` with canonical manifest rows.**
- [ ] **Step 3: Mark embedded but meaningful tools `child-capability` and ensure their exposed parent/native row exists.**
- [ ] **Step 4: Classify setup selectors as `prerequisite-flow`, composition shells as `aggregate`, tiny controls as `helper`, compatibility wrappers as `legacy`, and developer/debug-only controls as `intentionally-internal` with non-empty rationale.**
- [ ] **Step 5: For any promoted surface, add adapter/bundle wiring and Workbench discovery; do not create dead buttons for prerequisite-dependent children.**
- [ ] **Step 6: Re-run interactive audit until `unclassified_interactive_functions = 0`.**

---

### Task 8: Regression, build, and manual acceptance checkpoint

**Files:**
- Modify only when tests expose real defects.

- [ ] **Step 1: Run `python scripts/home_information_architecture_validation.py`.**
- [ ] **Step 2: Run `python scripts/interactive_entry_reachability_validation.py`.**
- [ ] **Step 3: Run `python scripts/native_desktop_reachability_validation.py`.**
- [ ] **Step 4: Run `python scripts/render_entry_reachability_validation.py`.**
- [ ] **Step 5: Run `python scripts/native_surface_bundle_validation.py` and `python scripts/utube_first_class_lab_validation.py`.**
- [ ] **Step 6: Run Surface Registry, UI Semantics, Source Integrity, Result Inspector, Visualization Studio/Visual Analytics, Model Coupling, Pipeline Graph, U-Tube Advanced/Uncertainty/Hysteresis, and Full-mode Acceptance workflows on the final head.**
- [ ] **Step 7: Run `npm run desktop:build`; require exit 0.**
- [ ] **Step 8: Stop at manual acceptance. Provide the user the exact final head SHA and force-overwrite `/Applications/Engineering Lab.app` command; do not merge PR #90 without explicit instruction.**
