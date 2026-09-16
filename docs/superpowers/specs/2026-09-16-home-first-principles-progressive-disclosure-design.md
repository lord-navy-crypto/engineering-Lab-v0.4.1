# Engineering Lab Home — First-Principles + Progressive Disclosure Design

**Date:** 2026-09-16  
**Branch:** `feature/native-desktop-reachability`  
**Base:** `feature/shared-scientific-ui-semantics`

## Purpose

Engineering Lab now exposes a broad native capability catalog, including previously hidden and embedded workspaces. The next problem is not raw reachability; it is information architecture. The current Home surface still behaves like an older launcher centered on featured Labs and runtimes, while the product has grown into a complete engineering/scientific workspace with experiments, measurements, modeling, analysis, reliability, reproducibility, and platform tooling.

This design restructures the initial native desktop around two complementary principles:

1. **First-principles design:** start from the user's real intent when opening Engineering Lab, not from the internal module/file structure.
2. **Progressive disclosure:** show the minimum useful decision set first, then reveal deeper tools through task flows, featured families, search, and the full Workbench catalog.

The goal is to keep complete capability reachability without turning Home into a wall of 70+ cards.

## Product invariant

Every user-facing capability must remain reachable from the native desktop, but not every capability must occupy the first screen.

The initial native experience must satisfy:

`user intent → task family → relevant capability → valid host → real interactive workspace`

The complete discovery fallback remains:

`Workbench / global search → any capability → valid host → real interactive workspace`

## First-principles task model

The Home surface is organized around four primary user intents:

1. **Run an Experiment**
   - open a first-class Physics Lab;
   - launch a featured experiment family such as Rotating U-Tube;
   - continue into advanced experiment-planning or uncertainty workspaces.

2. **Measure / Import Data**
   - Data Bridge;
   - Measurement & Calibration Registry;
   - BetterBoard Discovery / Inbox;
   - LabBridge / Experiment Notebook.

3. **Build / Compare Models**
   - Model Builder;
   - ModelSpec DIY;
   - Model Coupling;
   - Run Comparison;
   - Model Campaign;
   - Model Engineering;
   - Pipeline DAG.

4. **Analyze / Validate Results**
   - Result Inspector;
   - Visualization Studio / Visual Analytics;
   - Applied Analysis / Deep Applied Math;
   - Engineering V&V/UQ;
   - Requirements / Reliability / Risk / Evidence / Reproducibility.

These are user-facing task families, not backend classifications. The existing scientific categories remain available in Workbench filters and capability metadata.

## Home hierarchy

Home becomes a progressive four-layer surface.

### Layer 1 — Start Here

A compact hero plus four task-intent cards:

- Run an Experiment
- Measure / Import Data
- Build / Compare Models
- Analyze / Validate Results

Each card shows 2–4 contextually relevant immediate actions, not the entire category. The card itself can open a filtered Workbench view for the full family.

The hero no longer treats `Browse Physics Labs` and `Runtime Center` as the two primary product actions. Runtime and dependency management remain available from navigation and readiness/status surfaces.

### Layer 2 — Continue / Recent

Show recent or active scientific context when available:

- active `.physlab` Project;
- recently opened Lab/capability;
- active or recently completed compute/campaign task;
- latest result snapshot or evidence context.

This layer must degrade cleanly when there is no history: display a concise first-use state rather than empty placeholder chrome.

No history card may imply scientific validation merely because a run completed.

### Layer 3 — Featured Experiment Family

Keep **Rotating U-Tube Research** as the first featured experiment family because it now has a coherent multi-workspace research sequence.

The family visibly includes:

- U-Tube Research Studio
- Physical Model & Data
- Uncertainty
- Advanced Engineering / Experiment Planner
- Robust Design & Digital Twin
- Dynamic Threshold & Hysteresis

This is a featured family, not a hard-coded assumption that U-Tube is the only experiment family. The UI structure must allow additional featured families later without redesigning Home.

### Layer 4 — Platform Readiness + Explore All

A compact system-readiness row summarizes:

- Python runtime
- relevant fragile engines / Full-mode readiness
- active Project state
- queued/running task count

This layer gives status without turning Home into Runtime Center.

A clear **Explore all capabilities** action enters Workbench.

## Workbench role

Workbench remains the canonical exhaustive capability map.

It must continue to provide:

- complete native capability count;
- full text search;
- category filters;
- access-mode badges;
- host/readiness information;
- `Prepare & Open` launch behavior;
- featured U-Tube family;
- Core Engineering Platform grouping.

Home links into filtered Workbench states rather than duplicating the entire catalog.

## Physics Labs role

Physics Labs is narrowed semantically to actual first-class Lab/model launchers.

It may include:

- existing standard Labs;
- Kerr;
- Solar System;
- Honeycomb Lattice;
- Rotating U-Tube Research Studio;
- future true Labs.

It must not become a dumping ground for analysis, reliability, evidence, project, or orchestration tools.

## Global search / command discovery

The existing top search behavior is expanded into a unified native discovery layer.

Search must match:

- Lab names;
- capability labels;
- capability IDs;
- category names;
- profile names;
- route hints;
- common descriptive keywords.

Search results must distinguish:

- Lab
- Capability
- Project / data surface
- Runtime / dependency destination

The search result action should navigate or launch directly, preserving the same host preparation and deep-link path as Workbench.

No separate second launcher implementation is allowed; Home, Workbench, and global search must share canonical capability metadata and launcher behavior.

## Hidden-interaction audit v2

The previous audit covered Surface Registry rows, embedded UI modules, and public `render_*` entry points. The next audit expands to interactive UI code regardless of naming convention.

### Interaction signatures to scan

For packaged `physical_lab_*.py` modules, detect functions containing user-interaction calls such as:

- `st.button`
- `st.form`
- `st.form_submit_button`
- `st.tabs`
- `st.selectbox`
- `st.multiselect`
- `st.radio`
- `st.checkbox`
- `st.slider`
- `st.number_input`
- `st.text_input`
- `st.text_area`
- `st.file_uploader`
- `st.data_editor`
- `st.download_button`
- `st.expander`

The audit is structural, not semantic proof. Every detected interactive function must be classified explicitly.

### Valid classifications

- `native-surface` — merits independent native discovery.
- `child-capability` — user-facing child exposed through a parent family/workspace and optionally independently in Workbench.
- `aggregate` — composes other already-exposed capabilities.
- `prerequisite-flow` — project/data/setup selector that is intentionally entered through another capability.
- `helper` — small interactive helper that does not constitute an independent task surface.
- `legacy` — retained compatibility UI whose current canonical replacement is exposed.
- `intentionally-internal` — interactive engineering/debug control intentionally excluded from ordinary user discovery; requires an explicit rationale.

No interactive function may remain unclassified.

## Reachability audit v2 contract

CI must fail when:

- an interactive function is discovered but has no classification;
- a `native-surface` classification has no native manifest row;
- a `child-capability` has no valid exposed parent or native row;
- an `aggregate`, `prerequisite-flow`, or `legacy` entry references a nonexistent exposed capability;
- an `intentionally-internal` classification lacks a non-empty rationale;
- a native surface target module is not shipped in the Tauri bundle;
- Home references a capability ID not present in the canonical native catalog;
- Workbench and Home use divergent launch logic.

The audit must report deterministic counts for discovered interactive functions by classification and uncovered entries.

## Home data model

Add a small native home-layout metadata layer that references canonical capability IDs rather than copying renderer details.

Recommended shape:

```json
{
  "taskFamilies": [
    {
      "id": "experiment",
      "label": "Run an Experiment",
      "featured": ["utube-studio", "utube-physical", "utube-uncertainty"],
      "filterCategory": "Experiments & Physics"
    }
  ],
  "featuredFamilies": [
    {
      "id": "rotating-utube",
      "surfaceIds": [
        "utube-studio",
        "utube-physical",
        "utube-uncertainty",
        "utube-advanced",
        "utube-robust",
        "utube-hysteresis"
      ]
    }
  ]
}
```

This metadata contains navigation composition only. It does not duplicate scientific, renderer, profile, or readiness definitions from `surfaces.json` / `modules.json`.

## Shared native launcher

Refactor the current Workbench-specific launch path into a shared native capability-launch service/module consumed by:

- Workbench cards;
- Home task-family shortcuts;
- Featured experiment cards;
- global search results.

The shared launcher owns:

- host resolution;
- Safe/Full selection;
- readiness refresh;
- install/prepare behavior;
- launch call;
- iframe deep-link construction;
- active host cleanup on return;
- consistent error messages.

This prevents three copies of host/launch logic from drifting apart.

## Visual hierarchy and density

The design should feel like an engineering/scientific cockpit, not a marketplace catalog.

Principles:

- use hierarchy and grouping before decoration;
- one dominant primary action per card;
- preserve status badges but reduce redundant metadata on Home;
- prefer concise descriptions and progressive expansion;
- keep advanced/profile/dependency detail in Workbench or destination views;
- make interactive cards readable at 1080 px minimum window width and responsive below that;
- keep keyboard focus, touch targets, and contrast accessible;
- avoid hiding the only action behind hover;
- no scientific status color may imply evidence beyond its defined axis.

## Error handling

Home and search navigation must fail visibly and locally:

- unknown capability ID → native error toast/card and no launch;
- no legal host → explicit capability/host message;
- missing project prerequisite → open the canonical project-selection flow;
- Full-mode dependency unavailable → send user to Dependency Center or show the existing repair path;
- renderer failure → preserve logs and show the existing diagnostic message; do not silently fall back to a scientifically different surface.

## Scientific and execution boundaries

This redesign is navigation and information architecture only. It must not change:

- model equations;
- numerical algorithms;
- validation semantics;
- provenance semantics;
- result schemas;
- Safe/Full scientific meaning;
- queue/execution semantics;
- the known Pipeline DAG auto-advance behavior.

Opening Home, search results, or a capability must never auto-start scientific work.

## Testing strategy

Use TDD for every implementation slice.

Required automated checks include:

1. **Home information architecture validation**
   - four task families exist;
   - every referenced capability exists;
   - U-Tube six-entry family is intact;
   - Explore All routes to Workbench.

2. **Interactive-entry audit v2**
   - scan packaged UI Python AST;
   - require complete classification;
   - validate parent/native references.

3. **Shared launcher contract**
   - Workbench, Home, and search consume the same launcher;
   - no duplicate host-resolution implementation remains.

4. **Native reachability regression**
   - existing native reachability validator remains green;
   - bundle coverage remains green;
   - first-class U-Tube validation remains green.

5. **Existing integrity suites**
   - Surface Registry;
   - UI Semantics;
   - Source Integrity;
   - Result Inspector;
   - Visual Analytics / Visualization Studio;
   - Model Coupling;
   - Pipeline Graph;
   - U-Tube Advanced / Uncertainty / Hysteresis;
   - Full-mode Acceptance.

6. **Desktop build**
   - `npm run desktop:build` must complete successfully before manual acceptance.

## Manual acceptance checkpoint

The redesign is ready for user inspection only when:

- Home opens with the four task-intent families rather than the old two-button Lab/runtime framing;
- active/recent context degrades cleanly on first use;
- Rotating U-Tube remains a visible featured family with all six entries;
- Explore All opens the complete Workbench;
- global search can discover both Labs and capabilities;
- every interactive Python UI function is classified by audit v2;
- no `native-surface` or `child-capability` classification is unreachable;
- all relevant CI is green;
- the desktop app builds successfully.

At that point, the user performs visual/manual acceptance before any merge.
