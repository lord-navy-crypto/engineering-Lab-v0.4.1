#!/usr/bin/env python3
"""Audit packaged public render_* entry points against native desktop reachability."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
CATALOG_PATH = ROOT / "src-tauri" / "resources" / "surfaces.json"
ADAPTERS_PATH = UI_ROOT / "physical_lab_native_workbench_adapters.py"
CLASSIFICATION_PATH = ROOT / "src-tauri" / "resources" / "render_entry_classification.json"
VALID_CLASSES = {"native", "dependent-child", "aggregate", "legacy", "router", "helper"}


def public_renderers(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("render_")
        and not node.name.startswith("render__")
    ]


def effective_rows() -> list[dict]:
    rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("_render_audit_native_adapters", ADAPTERS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load native surface extensions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    merge = getattr(module, "merge_native_surface_rows", None)
    return merge(rows) if callable(merge) else rows


def main() -> None:
    rows = effective_rows()
    classes = json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    surface_ids = {str(row.get("id") or "") for row in rows if isinstance(row, dict)}
    targets = {
        (str(row.get("targetModule") or ""), str(row.get("targetCallable") or ""))
        for row in rows
        if isinstance(row, dict) and row.get("targetModule") and row.get("targetCallable")
    }
    classified = {
        (str(row.get("module") or ""), str(row.get("callable") or "")): row
        for row in classes
        if isinstance(row, dict)
    }

    discovered: list[tuple[str, str]] = []
    for path in sorted(UI_ROOT.glob("physical_lab_*.py")):
        module = path.stem
        for name in public_renderers(path):
            discovered.append((module, name))

    directly_targeted = set(discovered) & targets
    missing_classification = sorted(pair for pair in discovered if pair not in targets and pair not in classified)
    if missing_classification:
        formatted = "\n".join(f"  - {module}.{name}" for module, name in missing_classification)
        raise AssertionError("public render_* entry points lack reachability classification:\n" + formatted)

    stale = sorted(pair for pair in classified if pair not in discovered)
    if stale:
        formatted = "\n".join(f"  - {module}.{name}" for module, name in stale)
        raise AssertionError("render entry classification contains stale/nonexistent entries:\n" + formatted)

    missing_native: list[str] = []
    bad_covered_by: list[str] = []
    class_counts: dict[str, int] = {}
    for pair, row in classified.items():
        classification = str(row.get("classification") or "")
        if classification not in VALID_CLASSES:
            raise AssertionError(f"invalid render classification for {pair[0]}.{pair[1]}: {classification!r}")
        class_counts[classification] = class_counts.get(classification, 0) + 1
        if classification == "native":
            surface_id = str(row.get("surfaceId") or "")
            if not surface_id or surface_id not in surface_ids:
                missing_native.append(f"{pair[0]}.{pair[1]} -> {surface_id or '<missing surfaceId>'}")
        if classification in {"dependent-child", "aggregate", "legacy"}:
            covered = str(row.get("coveredBy") or "")
            if not covered or covered not in surface_ids:
                bad_covered_by.append(f"{pair[0]}.{pair[1]} -> {covered or '<missing coveredBy>'}")

    if missing_native:
        raise AssertionError("user-facing render entries missing native Workbench surfaces:\n  - " + "\n  - ".join(missing_native))
    if bad_covered_by:
        raise AssertionError("dependent/aggregate render entries lack a valid exposed parent surface:\n  - " + "\n  - ".join(bad_covered_by))

    print(json.dumps({
        "public_render_entries": len(discovered),
        "catalog_render_targets": len(targets),
        "directly_targeted_render_entries": len(directly_targeted),
        "classified_non_target_entries": len(classified),
        "classification_counts": class_counts,
        "effective_surface_rows": len(rows),
        "unclassified_render_entries": 0,
        "missing_native_render_surfaces": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
