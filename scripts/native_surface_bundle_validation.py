#!/usr/bin/env python3
"""Require every effective native surface renderer module to ship in the Tauri bundle."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
ADAPTERS = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_native_workbench_adapters.py"
TAURI = ROOT / "src-tauri" / "tauri.conf.json"


def effective_rows() -> list[dict]:
    rows = json.loads(SURFACES.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("_bundle_native_adapters", ADAPTERS)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load native surface extensions")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    merge = getattr(module, "merge_native_surface_rows", None)
    return merge(rows) if callable(merge) else rows


def main() -> None:
    rows = effective_rows()
    config = json.loads(TAURI.read_text(encoding="utf-8"))
    resources = config.get("bundle", {}).get("resources", {})
    if not isinstance(resources, dict):
        raise AssertionError("Tauri bundle.resources must be a mapping")

    missing: list[str] = []
    target_modules: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        module = str(row.get("targetModule") or "").strip()
        if not module:
            continue
        target_modules.add(module)
        source_key = f"resources/ui/{module}.py"
        expected_dest = f"ui/{module}.py"
        if resources.get(source_key) != expected_dest:
            missing.append(f"{row.get('id')}: {source_key} -> {expected_dest}")

    if missing:
        raise AssertionError("native renderer modules missing from Tauri bundle:\n  - " + "\n  - ".join(sorted(set(missing))))

    if resources.get("resources/surfaces.json") != "surfaces.json":
        raise AssertionError("required native reachability resource missing: resources/surfaces.json -> surfaces.json")
    if resources.get("resources/ui/physical_lab_native_workbench_adapters.py") != "ui/physical_lab_native_workbench_adapters.py":
        raise AssertionError("native surface extension/adapters module is not bundled")

    print(json.dumps({
        "native_surface_rows": len(rows),
        "unique_renderer_modules": len(target_modules),
        "unbundled_renderer_modules": 0,
        "effective_surface_catalog": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
