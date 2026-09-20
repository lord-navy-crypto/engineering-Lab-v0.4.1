#!/usr/bin/env python3
from pathlib import Path

app = Path("web/app.js").read_text(encoding="utf-8")
html = Path("web/index.html").read_text(encoding="utf-8")
utube = Path("web/utube-native.js").read_text(encoding="utf-8")
native = Path("web/native-experiments.js").read_text(encoding="utf-8")
css = Path("web/styles.css").read_text(encoding="utf-8")

experiment_ids = [
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radia-magnet-studio",
    "radiation-platform",
    "kerr-geodesics",
    "solar-system-dynamics",
    "honeycomb-lattice",
    "utube-studio",
    "kerr-shadow",
    "undulator-spectrum",
    "frequency-response",
]
assert len(experiment_ids) == 14

for experiment_id in experiment_ids:
    assert f"id:'{experiment_id}'" in native, f"missing native experiment registry entry: {experiment_id}"

for marker in (
    "function nativeExperimentCardFor(",
    "function nativeModuleCard(",
    "function openNativeExperiment(",
    "function renderNativeExperimentShell(",
):
    assert marker in native, f"missing native experiment implementation marker: {marker}"

for marker in (
    "utube:['utubeView'",
    "experiment:['nativeExperimentView'",
    "nativeModuleCard(m)",
    "nativeExtraExperimentCards()",
    "bindNativeExperimentShell();",
):
    assert marker in app, f"missing app-shell marker: {marker}"

assert 'id="nativeExperimentView"' in html
assert 'id="utubeView"' in html
assert '<script src="utube-native.js"></script>' in html
assert '<script src="native-experiments.js"></script>' in html
assert "Native experiment workspace — U-Tube migration" in css


for view_id in ("nativeExperimentView", "utubeView"):
    start = html.index(f'id="{view_id}"')
    end = html.find('<section id=', start + 10)
    segment = html[start:] if end < 0 else html[start:end]
    for label in ("Setup", "Tools & Analysis", "Results", "Verification"):
        assert label in segment, f"{view_id} missing professional {label} navigation"
    assert ">Advanced<" not in segment, f"{view_id} still exposes a separate Advanced tab"

shared_start = html.index('id="nativeExperimentView"')
shared_end = html.find('<section id=', shared_start + 10)
shared = html[shared_start:shared_end]
for forbidden_ui in (
    "Application workspace · no iframe",
    "serverless native execution",
    "Native experiment data flow",
    "Migration boundary",
    "Native shell",
):
    assert forbidden_ui not in shared, f"developer-facing UI leaked into experiment workspace: {forbidden_ui}"

ut_start = html.index('id="utubeView"')
ut_end = html.find('<section id=', ut_start + 10)
ut_segment = html[ut_start:ut_end]
for forbidden_ui in ("No iframe", "No localhost", "NATIVE WORKSPACE"):
    assert forbidden_ui not in ut_segment, f"developer-facing U-Tube UI leaked: {forbidden_ui}"

assert 'id="nativeExperimentRun"' in shared
assert 'id="utRun"' in ut_segment
assert 'data-native-exp-panel="setup"' in shared
assert 'data-native-exp-panel="results"' in shared
assert 'data-native-exp-panel="verification"' in shared
assert 'data-utube-panel="setup"' in ut_segment
assert 'data-utube-panel="results"' in ut_segment
assert 'data-utube-panel="verification"' in ut_segment

for view_id in ("nativeExperimentView", "utubeView"):
    start = html.index(f'id="{view_id}"')
    end = html.find('<section id=', start + 10)
    segment = html[start:] if end < 0 else html[start:end]
    assert "<iframe" not in segment, f"{view_id} still embeds iframe"
    for forbidden_src in (
        'src="http://localhost',
        "src='http://localhost",
        'src="http://127.0.0.1',
        "src='http://127.0.0.1",
    ):
        assert forbidden_src not in segment, f"{view_id} embeds local web source: {forbidden_src}"

utube_open = utube[utube.index("function openNativeUtube"):utube.index("function readUtubeInputs")]
native_open = native[native.index("function openNativeExperiment"):native.index("function renderNativeExperimentShell")]
for block_name, block in (("U-Tube", utube_open), ("shared native experiments", native_open)):
    for forbidden in ("launch_module", "labFrame", "iframe", "http://localhost", "http://127.0.0.1"):
        assert forbidden not in block, f"{block_name} open path contains forbidden legacy marker: {forbidden}"

guard = "if(typeof nativeExperimentSpec==='function'&&nativeExperimentSpec(id)){openNativeExperiment(id);return}"
assert guard in app, "openModule does not guard native experiments before legacy server launch"

print("Native experiment workspace validation: PASS (14/14 registered)")

assert 'id="nativeExperimentTools"' in html
assert 'data-native-exp-panel="advanced"' not in html
assert 'data-native-exp-tab="advanced"' not in html
assert 'data-native-exp-panel="tools"' in html
assert 'data-utube-panel="advanced"' not in html
assert 'data-utube-tab="advanced"' not in html
assert 'data-utube-panel="tools"' in html
assert 'id="nativeExperimentParameterCount"' in html
assert 'id="nativeExperimentToolMetrics"' in html
assert 'id="nativeExperimentVerificationMetrics"' in html
assert 'id="utVerificationMetrics"' in html
assert "const advanced=NATIVE_ADVANCED_PARAMETER_SCHEMAS[spec.id]||[]" in native
assert "const fields=[...primary,...advanced]" in native
assert "renderNativeParameterSections" in native
assert "bindProfessionalParameterControls" in native
assert "data-param-range" in native
assert "renderNativeToolResult" in native
assert "renderNativeVerificationResult" in native
tool_runner = native[native.index("async function runNativeExperimentTool"):native.index("async function runNativeVerificationTool")]
assert 'data-native-exp-tab="results"' not in tool_runner, "analysis tool still forces navigation to Results"
assert "renderNativeToolResult(payload)" in tool_runner
assert "contextResult=nativeExperimentResult" in tool_runner
assert "bindUtubeProfessionalSliders" in utube
assert "runUtubeVerificationTool" in utube
print("Professional experiment workspace validation: PASS setup+advanced merged, sliders linked, tool/primary/verification outputs separated")
for tool_marker in ("refinement","ftle","phonon-dispersion","phonon-dos","beam-broadening","duffing"):
    assert tool_marker in native, f"missing restored native tool marker: {tool_marker}"
for tool_marker in ("operating-state","elasticity","scan-plan","uncertainty"):
    assert tool_marker in html, f"missing restored U-Tube tool marker: {tool_marker}"

registry = Path("src-tauri/resources/ui/physical_lab_surface_registry.py").read_text(encoding="utf-8")
canonical_surface_ids = [
    "utube-studio",
    "utube-physical",
    "utube-uncertainty",
    "utube-advanced",
    "data-bridge",
    "measurement-registry",
    "betterboard-discovery",
    "betterboard-inbox",
    "labbridge",
    "research-notebook",
    "result-inspector",
    "research-orchestrator",
    "visualization-studio",
    "visual-analytics",
    "applied-analysis",
    "advanced-applied-analysis",
    "deep-applied-math",
    "sweep-design-bridge",
    "science-analysis",
    "science-protocol",
    "modelspec-diy",
    "run-comparison",
    "model-coupling",
    "pipeline-dag",
    "digital-twin",
    "engineering-decisions",
    "operations-planning",
    "quality-reliability",
    "risk-economics",
    "requirements-verification",
    "evidence-center",
    "reproducibility-pack",
    "local-ai",
    "run-vault",
    "openguin-advisory",
    "engineering-vvuq",
    "kerr-geodesics",
    "kerr-platform",
    "kerr-shadow",
    "solar-system",
    "lattice-dynamics",
    "deep-science",
    "remaining-science",
    "frequency-response",
    "new-model-refinement",
    "model-depth",
    "undulator-spectrum",
    "radiation-stokes",
    "radiation-quality",
    "radiation-seed-compare",
    "radia-forward",
    "radia-tolerance",
    "radia-radiation-propagation",
]
surface_block = registry[registry.index("SURFACES:"):registry.index("EMBEDDED_UI_MODULES")]
for surface_id in canonical_surface_ids:
    assert f'"{surface_id}"' in surface_block, f"canonical surface disappeared from registry: {surface_id}"
assert len(canonical_surface_ids) == 53
assert "surfaces_for_catalog(profile)" in Path("src-tauri/resources/ui/physical_lab_project_surface_patch.py").read_text(encoding="utf-8")
assert "Full Original Workspace" in native
assert "openFullOriginalWorkspace(" in native
assert 'id="utOpenFullOriginal"' in html
print("Zero-loss full capability catalog validation: PASS 53/53 registry surfaces")

import json
import re

parity_path = Path("src-tauri/resources/native_capability_parity.json")
assert parity_path.is_file(), "missing native capability parity manifest"
parity = json.loads(parity_path.read_text(encoding="utf-8"))
assert parity.get("schema") == "engineering-lab-capability-parity-v1"
assert parity.get("surface_count") == 53
manifest_rows = parity.get("capabilities") or []
manifest_ids = [str(row.get("surface_id") or "") for row in manifest_rows]
assert len(manifest_ids) == len(set(manifest_ids)) == 53, "parity manifest must contain 53 unique surface ids"
registry_text = Path("src-tauri/resources/ui/physical_lab_surface_registry.py").read_text(encoding="utf-8")
registry_block = registry_text[registry_text.index("SURFACES:"):registry_text.index("EMBEDDED_UI_MODULES")]
registry_ids = re.findall(r'_s\(\s*"([^"]+)"', registry_block)
assert len(registry_ids) == len(set(registry_ids)) == 53, f"expected 53 unique registry surfaces, got {len(registry_ids)}"
assert set(manifest_ids) == set(registry_ids), f"parity manifest mismatch: missing={sorted(set(registry_ids)-set(manifest_ids))}, extra={sorted(set(manifest_ids)-set(registry_ids))}"
allowed_states = {"native-primary", "native-partial", "compatibility-preserved"}
for row in manifest_rows:
    assert row.get("migration_state") in allowed_states, row
    assert row.get("zero_loss_required") is True, row
    assert str(row.get("guaranteed_access") or "").strip(), row
print("Capability parity manifest validation: PASS 53/53 exact registry match")

assert 'data-view="capabilities"' in html
assert 'id="capabilitiesView"' in html
assert 'id="capabilityGrid"' in html
assert 'ENGINEERING_CAPABILITIES' in native
assert 'openCapabilitySurface' in native
assert 'pl_surface=' in native
assert native.count('"id":') >= 53 or native.count("'id':") >= 53
project_patch = Path("src-tauri/resources/ui/physical_lab_project_surface_patch.py").read_text(encoding="utf-8")
engineering_ui = Path("src-tauri/resources/ui/physical_lab_engineering.py").read_text(encoding="utf-8")
advanced_ui = Path("src-tauri/resources/ui/physical_lab_advanced.py").read_text(encoding="utf-8")
assert 'st.query_params.get("pl_surface")' in project_patch
assert '_apply_surface_deeplink' in engineering_ui
assert 'workbench_routes' in advanced_ui
print("Direct visible capability catalog validation: PASS main UI + deep-link routing")


from action_catalog import build_action_catalog

action_catalog = build_action_catalog(Path("."))
assert action_catalog["baseline_available"], "pre-redesign action baseline is unavailable; CI must use full git history"
assert action_catalog["baseline_action_count"] >= 250, action_catalog["baseline_action_count"]
assert action_catalog["catalog_action_count"] >= action_catalog["baseline_action_count"]
assert not action_catalog["missing_from_current"], (
    "pre-redesign actions missing from current source: " +
    ", ".join(
        f"{row['module']}::{row['control_type']}::{row['label']}"
        for row in action_catalog["missing_from_current"][:20]
    )
)
assert not action_catalog["unmapped_modules"], action_catalog["unmapped_modules"]
assert Path("dist/action-catalog.js").is_file()
action_js = Path("dist/action-catalog.js").read_text(encoding="utf-8")
assert "ENGINEERING_ACTION_CATALOG" in action_js
assert "ENGINEERING_ACTION_PARITY" in action_js
assert 'data-view="actions"' in html
assert 'id="actionsView"' in html
assert 'id="actionGroups"' in html
assert 'id="actionGrid"' not in html
assert "renderActionCatalog" in native
assert "pl_action=" in native
assert 'st.query_params.get("pl_action")' in project_patch
print(
    "Action-level zero-loss validation: PASS "
    f"baseline={action_catalog['baseline_action_count']} "
    f"current={action_catalog['current_action_count']} "
    f"catalog={action_catalog['catalog_action_count']} "
    "missing=0"
)

assert 'id="actionWorkspaceView"' in html
assert "openActionWorkspace" in native
assert "openSelectedActionExact" in native
assert "ACTION_NATIVE_VIEW_ROUTES" in native
assert "ACTION_NATIVE_UTUBE_SURFACES" in native
print("Unified native action workspace validation: PASS")

assert "ACTION_NATIVE_UTUBE_TOOL_MAP" in native
for action_label in (
    "Run uncertainty propagation",
    "Compute local uncertainty budget",
    "Solve inverse geometry",
    "Evaluate design space",
    "Fit calibration",
    "Compare field series",
    "Analyze phase space",
):
    assert action_label in native, action_label
print("Exact native legacy-action routing validation: PASS")

assert 'id="actionStageNav"' in html
assert 'id="actionGroups"' in html
assert "ACTION_WORKFLOW_STAGES" in native
assert "action-capability-group" in native
assert "native-tool-group" in native
assert "actionCard(" not in native
assert len(action_catalog["actions"]) == 1232, len(action_catalog["actions"])
print("Workflow-first action visualization validation: PASS 1232 actions preserved, grouped instead of flattened")
