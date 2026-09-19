#!/usr/bin/env python3
"""Repository-wide reachability audit for Engineering Lab UI capabilities.

The earlier refactor checks protected known routes. This audit works in the
opposite direction: every public render_* entrypoint in a Physical Lab *_ui.py
module must be referenced by another bundled UI module. That catches experiment
implementations that still exist on disk but have silently become unreachable.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"

files = sorted(UI.glob("physical_lab_*.py"))
texts = {p: p.read_text(encoding="utf-8") for p in files}

public_renderers: list[tuple[Path, str]] = []
for path, text in texts.items():
    if not path.name.endswith("_ui.py"):
        continue
    for match in re.finditer(r"^def\s+(render_[A-Za-z0-9_]+)\s*\(", text, re.M):
        public_renderers.append((path, match.group(1)))

orphans: list[tuple[str, str]] = []
references: dict[str, list[str]] = {}
for owner, renderer in public_renderers:
    hits = []
    pattern = re.compile(rf"\b{re.escape(renderer)}\b")
    for path, text in texts.items():
        if path == owner:
            continue
        if pattern.search(text):
            hits.append(path.name)
    references[renderer] = hits
    if not hits:
        orphans.append((owner.name, renderer))

print(f"Engineering Lab public UI renderer inventory: {len(public_renderers)}")
for owner, renderer in public_renderers:
    hits = references[renderer]
    print(f"- {renderer} [{owner.name}] -> {', '.join(hits) if hits else 'UNREFERENCED'}")

if orphans:
    print("\nORPHAN / UNREACHABLE UI RENDERERS:")
    for owner, renderer in orphans:
        print(f"- {renderer} in {owner}")
    raise SystemExit(
        "Engineering Lab capability reachability audit FAILED: "
        f"{len(orphans)} public UI renderer(s) have no route from another bundled UI module."
    )

print("Engineering Lab capability reachability audit: PASS")
print("- every public *_ui.py render entrypoint is referenced outside its own module")
print("- existing-on-disk but navigation-orphaned experiment surfaces are CI-detectable")
