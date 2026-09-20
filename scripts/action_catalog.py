#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASELINE_REF = "3ba329c5c127120706dab2f3b2a4abe8cbcdec2a"

CONTROL_TYPES = {
    "button", "download_button", "link_button", "form_submit_button",
    "selectbox", "radio", "segmented_control", "pills", "multiselect",
    "slider", "select_slider", "number_input", "text_input", "text_area",
    "file_uploader", "checkbox", "toggle", "tabs", "expander", "popover",
    "date_input", "time_input", "color_picker", "chat_input",
}

MANUAL_MODULE_SURFACES = {
    "physical_lab_project_interop_ui": "data-bridge",
    "physical_lab_utube_robust_ui": "utube-advanced",
    "physical_lab_utube_hysteresis_ui": "utube-advanced",
    "physical_lab_model_depth_iv_ui": "model-depth",
    "physical_lab_model_depth_v_ui": "model-depth",
    "physical_lab_model_depth_vi_ui": "model-depth",
    "physical_lab_model_depth_vii_ui": "model-depth",
    "physical_lab_model_depth_viii_ui": "model-depth",
    "physical_lab_model_depth_ix_ui": "model-depth",
    "physical_lab_radiation_interactions_ui": "radiation-stokes",
    "physical_lab_radiation_response_surface_ui": "radiation-quality",
    "physical_lab_advanced": "run-vault",
    "physical_lab_local_ai": "local-ai",
    "physical_lab_radia_adapter": "radia-forward",
    "physical_lab_radia_tolerance": "radia-tolerance",
    "physical_lab_radia_radiation_propagation": "radia-radiation-propagation",
}

EXTRA_MODULES = {
    "physical_lab_advanced",
    "physical_lab_local_ai",
    "physical_lab_radia_adapter",
    "physical_lab_radia_tolerance",
    "physical_lab_radia_radiation_propagation",
}

# Visual/workflow labels may evolve without deleting the underlying action.
# Keep pre-redesign action identities resolvable to their current, clearer tab names.
LEGACY_ACTION_ALIASES = {
    ("physical_lab_kerr_ui", "tab", "Single orbit"): "1 · Run — Single orbit",
    ("physical_lab_kerr_ui", "tab", "Massive ↔ photon"): "2 · Comparison — Massive ↔ photon",
    ("physical_lab_kerr_ui", "tab", "Spin sweep"): "3 · Analysis — Spin sweep",
    ("physical_lab_kerr_ui", "tab", "Numerical verification"): "4 · Verification — Numerical audit",
    ("physical_lab_solar_system_ui", "tab", "Setup & run"): "1 · Setup & run",
    ("physical_lab_solar_system_ui", "tab", "Results"): "2 · Results",
    ("physical_lab_solar_system_ui", "tab", "Sensitivity audit"): "3 · Verification — Sensitivity audit",
    ("physical_lab_solar_system_ui", "tab", "Advanced tools"): "4 · Analysis — Advanced tools",
    ("physical_lab_lattice_ui", "tab", "Setup & run"): "1 · Setup & run",
    ("physical_lab_lattice_ui", "tab", "Dynamics results"): "2 · Results — Dynamics",
    ("physical_lab_lattice_ui", "tab", "Modes & phonons"): "3 · Analysis — Modes & phonons",
    ("physical_lab_lattice_ui", "tab", "Advanced tools"): "4 · Verification & advanced tools",
}


def _load_registry(root: Path):
    path = root / "src-tauri" / "resources" / "ui" / "physical_lab_surface_registry.py"
    spec = importlib.util.spec_from_file_location("physical_lab_surface_registry_action_catalog", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load physical_lab_surface_registry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _node_label(node: ast.AST, source: str) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = " ".join(node.value.split()).strip()
        return [value] if value else []
    if isinstance(node, ast.JoinedStr):
        text = ast.get_source_segment(source, node) or ast.unparse(node)
        text = " ".join(text.split()).strip()
        return [text] if text else []
    if isinstance(node, (ast.List, ast.Tuple)):
        out: list[str] = []
        for item in node.elts:
            out.extend(_node_label(item, source))
        return out
    return []


def extract_controls(source: str, module_name: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        control_type = node.func.attr
        if control_type not in CONTROL_TYPES:
            continue
        labels: list[str] = []
        if node.args:
            labels.extend(_node_label(node.args[0], source))
        if not labels:
            for kw in node.keywords:
                if kw.arg in {"label", "placeholder"}:
                    labels.extend(_node_label(kw.value, source))
                    if labels:
                        break
        for label in labels:
            if not label:
                continue
            normalized_type = "tab" if control_type == "tabs" else control_type
            rows.append({
                "module": module_name,
                "control_type": normalized_type,
                "label": label,
                "line": int(getattr(node, "lineno", 0) or 0),
            })
    return rows


def _git_show(root: Path, ref: str, relative_path: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "show", f"{ref}:{relative_path}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    except Exception:
        return None


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row["module"]), str(row["control_type"]), str(row["label"]))


def build_action_catalog(root: Path, baseline_ref: str = BASELINE_REF) -> dict[str, Any]:
    registry = _load_registry(root)
    ui_root = root / "src-tauri" / "resources" / "ui"

    module_to_surface: dict[str, str] = {}
    surface_labels: dict[str, str] = {}
    for row in registry.SURFACES:
        surface_labels[str(row.surface_id)] = str(row.label)
        if row.module:
            module_to_surface.setdefault(str(row.module), str(row.surface_id))
    module_to_surface.update(MANUAL_MODULE_SURFACES)

    modules = set(str(x) for x in registry.CLASSIFIED_UI_MODULES)
    modules.update(str(row.module) for row in registry.SURFACES if row.module)
    modules.update(EXTRA_MODULES)

    current: list[dict[str, Any]] = []
    baseline: list[dict[str, Any]] = []
    baseline_available = False

    for module_name in sorted(modules):
        path = ui_root / f"{module_name}.py"
        if path.is_file():
            current.extend(extract_controls(path.read_text(encoding="utf-8"), module_name))
        rel = str(path.relative_to(root))
        old_source = _git_show(root, baseline_ref, rel)
        if old_source is not None:
            baseline_available = True
            baseline.extend(extract_controls(old_source, module_name))

    current_by_key = {_key(row): row for row in current}
    baseline_by_key = {_key(row): row for row in baseline}

    # Treat a renamed workflow tab as the same preserved action when an explicit
    # legacy alias points to a current control in the same module/type.
    resolved_aliases: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for legacy_key, current_label in LEGACY_ACTION_ALIASES.items():
        target_key = (legacy_key[0], legacy_key[1], current_label)
        if legacy_key in baseline_by_key and target_key in current_by_key:
            alias_row = dict(current_by_key[target_key])
            alias_row["label"] = legacy_key[2]
            alias_row["aliased_to"] = current_label
            current_by_key.setdefault(legacy_key, alias_row)
            resolved_aliases[legacy_key] = target_key

    missing_from_current = [
        row for key, row in sorted(baseline_by_key.items())
        if key not in current_by_key
    ]

    union_keys = sorted(set(current_by_key) | set(baseline_by_key))
    actions: list[dict[str, Any]] = []
    unmapped_modules: set[str] = set()
    for key in union_keys:
        row = current_by_key.get(key) or baseline_by_key[key]
        module_name = str(row["module"])
        surface_id = module_to_surface.get(module_name)
        if not surface_id:
            unmapped_modules.add(module_name)
            continue
        digest = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:18]
        actions.append({
            "action_id": f"action-{digest}",
            "label": row["label"],
            "control_type": row["control_type"],
            "surface_id": surface_id,
            "surface_label": surface_labels.get(surface_id, surface_id),
            "module": module_name,
            "line": int(row.get("line") or 0),
            "baseline_action": key in baseline_by_key,
            "current_action": key in current_by_key,
            "aliased_to": (current_by_key.get(key) or {}).get("aliased_to"),
        })

    return {
        "schema": "engineering-lab-action-catalog-v1",
        "baseline_ref": baseline_ref,
        "baseline_available": baseline_available,
        "baseline_action_count": len(baseline_by_key),
        "current_action_count": len(current_by_key),
        "catalog_action_count": len(actions),
        "missing_from_current": missing_from_current,
        "resolved_alias_count": len(resolved_aliases),
        "unmapped_modules": sorted(unmapped_modules),
        "actions": actions,
    }


def write_action_catalog_js(root: Path, output: Path, *, strict_baseline: bool = False) -> dict[str, Any]:
    catalog = build_action_catalog(root)
    if strict_baseline and not catalog["baseline_available"]:
        raise RuntimeError(f"baseline commit {BASELINE_REF} is unavailable")
    if catalog["missing_from_current"]:
        sample = ", ".join(
            f"{row['module']}::{row['control_type']}::{row['label']}"
            for row in catalog["missing_from_current"][:12]
        )
        raise RuntimeError(f"legacy action parity failure: {len(catalog['missing_from_current'])} missing; {sample}")
    if catalog["unmapped_modules"]:
        raise RuntimeError("action catalog has unmapped modules: " + ", ".join(catalog["unmapped_modules"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    action_json = json.dumps(catalog["actions"], ensure_ascii=False, separators=(",", ":"))
    parity_json = json.dumps(
        {k: v for k, v in catalog.items() if k != "actions"},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    output.write_text(
        "window.ENGINEERING_ACTION_CATALOG=Object.freeze(" + action_json + ");\n"
        "window.ENGINEERING_ACTION_PARITY=Object.freeze(" + parity_json + ");\n",
        encoding="utf-8",
    )
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/action-catalog.js")
    parser.add_argument("--strict-baseline", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog = write_action_catalog_js(root, root / args.output, strict_baseline=args.strict_baseline)
    print(
        "Action-level zero-loss catalog: "
        f"baseline={catalog['baseline_action_count']} "
        f"current={catalog['current_action_count']} "
        f"catalog={catalog['catalog_action_count']} "
        f"missing={len(catalog['missing_from_current'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
