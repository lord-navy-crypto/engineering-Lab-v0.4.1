#!/usr/bin/env python3
"""Require every native surface renderer module to ship in the Tauri bundle."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
TAURI = ROOT / "src-tauri" / "tauri.conf.json"


def main() -> None:
    rows = json.loads(SURFACES.read_text(encoding="utf-8"))
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

    required_data = {
        "resources/surfaces.json": "surfaces.json",
    }
    for source, dest in required_data.items():
        if resources.get(source) != dest:
            raise AssertionError(f"required native reachability resource missing: {source} -> {dest}")

    print(json.dumps({
        "native_surface_rows": len(rows),
        "unique_renderer_modules": len(target_modules),
        "unbundled_renderer_modules": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
