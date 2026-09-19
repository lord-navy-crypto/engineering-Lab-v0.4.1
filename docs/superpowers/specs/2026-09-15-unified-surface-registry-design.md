# Unified Surface Registry Design

## Goal

Make every existing user-facing Engineering Lab workspace discoverable from a central navigation surface, while keeping pure backend/runtime modules hidden behind the workspaces that use them. Prevent future regressions where a feature is implemented and bundled but has no obvious user entry point.

## Problem

Engineering Lab already ships a large set of UI renderers and domain workspaces. Some are reachable from Project Tools, some are only appended to specific lab profiles through `physical_lab_advanced.py`, and some have no obvious central route. This creates a gap between implemented capability and what a user can actually find.

The existing DMG resource list already bundles most of these modules. The main deficiency is discoverability and route ownership, not packaging.

## User-facing definition

A module is user-facing if it exposes a real interactive renderer/workspace that a researcher is expected to open and operate directly. Examples include U-Tube Research Studio, Visualization Studio, Applied Math, Digital Twin, Engineering Decision, Operations, Quality & Reliability, Risk Economics, Requirements Verification, Kerr, Solar System, Lattice, Radiation, RADIA, Undulator, Run Comparison, Result Inspector, Local AI, and related science/model workspaces.

Pure infrastructure is not promoted to a top-level menu item. Compute engines, job workers, registries, stores, adapters, low-level result contracts, and helper modules remain internal unless they already expose a dedicated interactive workspace.

## Architecture

### 1. Single surface registry

Create `src-tauri/resources/ui/physical_lab_surface_registry.py` as the canonical inventory of user-facing surfaces. Each surface record contains:

- stable `surface_id`
- display label
- category
- short description
- renderer module
- renderer callable
- availability scope (`global`, `project`, or profile-specific)
- optional profile whitelist
- optional argument mode for renderers needing `profile`, `project_path`, or namespace

The registry must be declarative. Adding a new user-facing renderer should require adding one record, not editing several navigation branches.

### 2. Central All Workspaces surface

Extend the project-level surface switcher in `physical_lab_project_interop_ui.py` with `All Workspaces`.

The page groups surfaces into a compact set of categories:

- Experiments & Physics
- Data & Measurement
- Visualization & Analysis
- Modeling & Simulation
- Engineering Decisions & Reliability
- Reproducibility & AI

Each surface appears as a compact discoverable launcher with its label and description. Selecting a launcher renders that workspace in-place through the registry dispatcher.

Existing direct paths remain intact. U-Tube Research Studio keeps its dedicated project-level entry. Existing Project Tools categories remain available. Profile-specific advanced suites remain available in their original labs.

### 3. Visibility rules

Global surfaces are always listed.

Project surfaces are shown when a project is open and receive the canonical `project_path` where required.

Profile-specific surfaces are shown in the central catalog with a scope badge. If a renderer cannot safely run outside its native profile because it depends on the lab namespace, the catalog shows it as available through that named profile and provides the route rather than invoking it incorrectly.

No fake usability: a workspace must not be presented as directly launchable if its renderer requires upstream namespace objects that do not exist on the project surface.

### 4. Surface audit and orphan prevention

Add `scripts/surface_registry_validation.py` and `.github/workflows/surface-registry-integrity.yml`.

The validation checks:

1. Every registry renderer module exists in the source tree.
2. Every registry renderer module is bundled in `src-tauri/tauri.conf.json`.
3. Every direct-launch renderer callable named in the registry exists.
4. The project UI imports and renders the registry-backed All Workspaces surface.
5. Known user-facing UI modules are represented by the registry or explicitly allow-listed as embedded-only/profile-only.
6. Pure infrastructure modules are never required to have menu entries.

The allow-list must be explicit and documented so a newly created `*_ui.py` file cannot silently become an orphan.

### 5. Error handling

Registry dispatch is isolated per workspace. Import or runtime failure in one workspace produces a localized warning naming that workspace and does not crash the rest of the project UI.

Unsupported scope is shown as an informational message rather than attempting a broken import/render call.

### 6. Packaging

`physical_lab_surface_registry.py` and any new UI support file are added to `src-tauri/tauri.conf.json` resources. Existing bundled modules are not duplicated or renamed.

### 7. Scientific boundaries

Navigation changes do not change numerical algorithms, physical models, uncertainty interpretation, validation status, or execution semantics.

Existing boundaries remain intact, including:

- numerical convergence is not physical validation;
- model views are not measurements;
- visualization bands are not automatically uncertainty intervals;
- optimization or Pareto results are not certification;
- regularization/model selection signals are not proof of physical truth;
- AI/advisory outputs do not silently execute experiments or change parameters;
- queueing a Sweep job is distinct from starting execution.

## Initial registry coverage

The registry will include the existing direct user-facing workspaces already found in the repository, including the major families below where a direct renderer exists:

- Project Home / U-Tube Research Studio / Project Tools
- BetterBoard Discovery / LabBridge / Result Inspector
- Visualization Studio / Visual Analytics
- Applied Analysis / Advanced Applied Analysis / Deep Applied Math / Sweep Design Bridge
- ModelSpec DIY / Run Comparison / Model Coupling / Pipeline DAG
- Engineering Decision / Operations Planning / Quality & Reliability / Risk Economics / Requirements Verification
- Digital Twin / Research Orchestrator / Evidence Center / Research Notebook
- Kerr / Solar System / Lattice science workspaces
- Undulator / Radiation analysis workspaces
- RADIA interactive workspaces where they can be called without unsafe namespace assumptions
- Local AI and reproducibility-related surfaces where their callable interface supports project-level launch

Profile-only advanced experiment suites that require upstream lab namespace state remain represented in the registry as profile-scoped routes rather than being incorrectly executed from project scope.

## Non-goals

- Do not rewrite scientific engines.
- Do not flatten every backend module into a menu item.
- Do not remove existing project or profile navigation.
- Do not change schema identifiers or legacy file names just for naming consistency.
- Do not duplicate renderer implementations.

## Success criteria

A researcher opening Engineering Lab can reach the central `All Workspaces` catalog and discover every existing user-facing capability without knowing internal module names. Existing specialist routes still work. CI fails if a new user-facing UI module is added without either registry coverage or an explicit embedded/profile-only classification. The DMG contains every registry dependency needed at runtime.
