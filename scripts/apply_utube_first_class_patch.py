#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "src-tauri" / "resources" / "modules.json"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"

UTUBE_MODULE = {
    "kind": "lab",
    "repo": "lord-navy-crypto/engineering-Lab-v0.4.1",
    "branch": "main",
    "bundled": True,
    "entrypoint": "app.py",
    "requirements": "requirements.txt",
    "launcher": None,
    "runtimeRequires": [],
    "pythonRequires": ">=3.10",
    "verifyImports": ["numpy", "scipy", "pandas", "plotly", "streamlit"],
    "supportedArches": ["arm64", "x86_64"],
    "systemRequires": [],
    "runtimeExcludes": [],
    "fragileDependencies": [],
    "safeBackend": "standard",
    "id": "rotating-utube",
    "name": "Rotating U-Tube Research Studio",
    "category": "Fluid Dynamics & Experimental Physics",
    "description": "Rotating U-tube threshold physics, physical/data views, uncertainty, inverse design, experiment planning, robust design/digital twin and dynamic threshold/hysteresis studies.",
    "tags": ["U-Tube", "Fluid dynamics", "Experiment", "Uncertainty"],
    "safeModeNote": "Uses the rotating U-tube model and research UI bundled with this Engineering Lab build; no second solver checkout is downloaded.",
    "fullModeNote": "Same bundled U-tube implementation today. Full mode does not silently substitute a different fluid solver or relabel the reduced-order model as full CFD."
}
UTUBE_SURFACES = {
    "utube-studio", "utube-physical", "utube-uncertainty",
    "utube-advanced", "utube-robust", "utube-hysteresis",
}

modules = json.loads(MODULES.read_text(encoding="utf-8"))
if not isinstance(modules, list):
    raise SystemExit("modules.json must be a list")
existing = [i for i, row in enumerate(modules) if isinstance(row, dict) and row.get("id") == "rotating-utube"]
if len(existing) > 1:
    raise SystemExit("duplicate rotating-utube modules")
if existing:
    modules[existing[0]] = UTUBE_MODULE
else:
    runtime_index = next((i for i, row in enumerate(modules) if isinstance(row, dict) and row.get("kind") == "runtime"), len(modules))
    modules.insert(runtime_index, UTUBE_MODULE)
MODULES.write_text(json.dumps(modules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
if not isinstance(surfaces, list):
    raise SystemExit("surfaces.json must be a list")
seen = set()
for row in surfaces:
    if not isinstance(row, dict):
        continue
    sid = str(row.get("id") or "")
    if sid not in UTUBE_SURFACES:
        continue
    row["profiles"] = ["rotating-utube"]
    row["preferredProfiles"] = ["rotating-utube"]
    seen.add(sid)
missing = sorted(UTUBE_SURFACES - seen)
if missing:
    raise SystemExit("missing U-Tube surfaces: " + ", ".join(missing))
SURFACES.write_text(json.dumps(surfaces, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

print(json.dumps({"rotating_utube_module": True, "utube_surfaces_rehosted": len(seen)}, sort_keys=True))
