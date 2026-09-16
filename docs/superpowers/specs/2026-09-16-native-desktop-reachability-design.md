# Native Desktop Reachability — Design

**Date:** 2026-09-16  
**Branch:** `feature/native-desktop-reachability`  
**Base:** `feature/shared-scientific-ui-semantics`

## Purpose

Engineering Lab already contains a large registry of user-facing workspaces plus additional embedded child UIs. Today many of those capabilities are only discoverable after the user already knows which Lab/profile/project route to enter. This design makes every user-facing capability discoverable from the native Tauri desktop and gives it a deterministic launch path.

The desktop must become the canonical discovery surface. Internal Streamlit catalogs remain useful, but they are no longer the only place where advanced capabilities can be found.

## Core requirement

Every user-facing capability must satisfy the full reachability chain:

`native desktop card → canonical capability id → valid host profile → launch/deep-link target → rendered interactive workspace`

A capability is not considered desktop-reachable merely because a Python file exists, a Surface Registry row exists, or a route hint names where the user could manually search for it.

## Scope

The first complete native catalog covers:

1. Every `Surface` in `physical_lab_surface_registry.py`.
2. Every intentionally embedded user-facing `*_ui.py` module currently classified by `EMBEDDED_UI_MODULES`.
3. The existing project-level and profile-level routes needed to render those capabilities.
4. Search, category filtering, access/host information and one-click prepare/open behavior in the Tauri shell.
5. CI that compares the Python Surface Registry, embedded UI classification and native desktop catalog.

Pure backend helpers, solver internals, schema utilities and non-user-facing support modules are not promoted into buttons.

## Native catalog

Add a canonical native manifest at:

`src-tauri/resources/surfaces.json`

Each entry has:

- `id`: stable desktop capability id.
- `label`: user-facing name.
- `category`: one of the existing Surface Registry categories.
- `description`: concise capability description.
- `sourceSurfaceId`: matching Python Surface Registry id when one exists.
- `kind`: `surface` or `embedded`.
- `launchMode`: `direct`, `profile`, `route`, or `embedded`.
- `profiles`: legal host profiles. Empty means the generic host preference list may be used.
- `preferredProfiles`: deterministic host order when more than one profile can carry the capability.
- `targetModule`: Python module to render when direct rendering is possible.
- `targetCallable`: renderer callable when direct rendering is possible.
- `argumentMode`: `st_profile`, `st_profile_project`, `st_project_profile`, `st_project_profile_refs`, or `native_route`.
- `routeTarget`: explicit route id for route/embedded wrappers when needed.
- `routeHint`: human-readable fallback context.

The manifest is desktop navigation metadata only. It must not change scientific algorithms, validation meaning, provenance meaning or execution semantics.

## Desktop UI

Add a native sidebar entry named **Workbench** and a full `capabilitiesView` containing:

- total capability count,
- category counts,
- text search,
- category filter,
- cards for every manifest entry,
- badges for direct/profile/route/embedded access,
- host profile information,
- a single `Prepare & Open` action.

The Workbench must be visible from initial app launch without opening a Physics Lab first.

## Launch behavior

A desktop capability launcher resolves a legal host profile in this order:

1. an already-ready profile from `preferredProfiles`,
2. an already-ready profile from `profiles`,
3. the first legal preferred/profile host, which is prepared through the existing `install_module` path,
4. generic host fallback for profile-independent direct/route surfaces: `numerical-methods`, then `oscillation-integration`, then `nonlinear-chaos`.

The launcher then calls the existing `launch_module` command with an optional `surfaceId` deep-link. The module launch keeps existing Safe/Full semantics; Workbench defaults to Safe unless a surface explicitly requires Full mode. No capability launch may silently broaden execution semantics.

`launch_module` exports `PHYSICAL_LAB_INITIAL_SURFACE=<capability id>` into the managed Streamlit process. Existing launch callers that omit `surfaceId` continue to behave exactly as before.

## Streamlit deep-link entry

Add `physical_lab_native_surface_entry.py`, installed through `sitecustomize.py` after the existing project/surface patches.

It wraps the shared advanced renderer and consumes `PHYSICAL_LAB_INITIAL_SURFACE` once per Streamlit session. The wrapper:

- validates the capability id against `surfaces.json` / Python registry metadata;
- renders a visible Desktop Requested Workspace header;
- for `direct` capabilities, invokes the registered renderer with the exact declared argument convention;
- for `profile` capabilities, verifies that the current profile is legal before invoking the renderer;
- for `route` capabilities, renders the real existing route/tool instead of only displaying instructions;
- for `embedded` capabilities, invokes the real embedded renderer or its parent route;
- never invents a project path; project-dependent workspaces display/select the canonical Project Kernel state;
- never executes jobs simply because a page was opened.

## Route targets

Route wrappers are explicit and finite. Initial route ids include:

- `utube-studio`
- `data-bridge`
- `measurement-registry`
- `betterboard-inbox`
- `research-notebook`
- `reproducibility-pack`
- `openguin-advisory`
- `project-workspace`

They delegate to existing Project Interop / LabBridge / Project Kernel UI functions. Route wrappers do not duplicate scientific logic.

## Embedded child capabilities

Embedded user-facing modules must no longer mean invisible. At minimum the native catalog exposes:

- Project Workspace / Interop
- U-Tube Robust Design & Digital Twin
- U-Tube Dynamic Threshold & Hysteresis
- Model Depth IV
- Model Depth V
- Model Depth VI
- Model Depth VII
- Model Depth VIII
- Model Depth IX
- Radiation Interactions
- Radiation Response Surface

Each remains scientifically owned by its existing module. The desktop only provides reachability.

## Scientific and execution boundaries

This work must preserve all existing boundaries, including:

- execution success does not imply validation;
- queue state does not imply execution;
- provenance presence does not imply scientific support;
- model views are not measurements;
- visualization bands are not uncertainty unless explicitly defined as such;
- tolerance corners are not probability/yield/process capability;
- requirements registration is not evidence/compliance/certification;
- opening a capability must not auto-start a queued workflow or mutate project evidence.

The known Pipeline DAG auto-advance behavior is outside this feature and must not be represented as fixed.

## CI reachability contract

Add `scripts/native_desktop_reachability_validation.py` and `.github/workflows/native-desktop-reachability-integrity.yml`.

The validator must fail when:

- a Python Surface Registry id has no native catalog row;
- an embedded UI module has no native child-capability row;
- a native catalog id is duplicated;
- a catalog category is unknown;
- a profile capability has no legal host profile;
- a direct/profile/embedded direct-render target module/callable does not exist;
- a route capability has no supported route target;
- `web/index.html` lacks the Workbench sidebar/view/script wiring;
- `web/surface_catalog.js` lacks list, filter and prepare/open wiring;
- `src-tauri/src/lib.rs` does not expose `list_surface_catalog` and optional surface deep-link environment wiring;
- `sitecustomize.py` does not install the native surface entry patch;
- `tauri.conf.json` does not bundle the new runtime resources.

The validator prints counts for registry surfaces, embedded children, native rows and uncovered capabilities.

## Manual acceptance stop point

The branch is ready for a broad manual test only when:

- every registered surface is in the native Workbench;
- every embedded user-facing UI module has a native child capability;
- cards are searchable and filterable;
- Prepare & Open can resolve or prepare a host Lab;
- deep-linked direct/profile/route/embedded examples render real controls;
- Native Desktop Reachability CI, Surface Registry CI, UI Semantics CI and Source Integrity CI are green;
- the desktop build succeeds.

Only after that should we visually tune grouping, labels and density based on real use.