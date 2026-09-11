#!/usr/bin/env python3
"""Deterministic checks for local response-surface requirement contours."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_requirements.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_requirements", MOD)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MOD}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# y = x: with upper=0, exactly the x<=0 half of a symmetric odd grid passes.
surface = {
    "metric": "photon_energy_eV",
    "factorA": "field_error_pct",
    "factorB": "gap_asymmetry_mm",
    "coefficients": {
        "intercept": 0.0,
        "linearA": 1.0,
        "linearB": 0.0,
        "quadraticA": 0.0,
        "quadraticB": 0.0,
        "interactionAB": 0.0,
    },
}
out = mod.classify_requirement_surface(surface, upper=0.0, points=81)
assert out["centerStatus"] == "PASS"
assert abs(out["centerValue"]) < 1e-12
assert 0.50 < out["passGridFraction"] < 0.52
assert out["nearestClassificationBoundaryFromCenterCoded"] is not None
assert 0.0 < out["nearestClassificationBoundaryFromCenterCoded"] < 0.04
assert "not probability" in out["boundary"].lower()

# Band requirement around y=x should keep the center and reject both extremes.
band = mod.classify_requirement_surface(surface, lower=-0.25, upper=0.25, points=81)
assert band["centerStatus"] == "PASS"
assert 0.20 < band["passGridFraction"] < 0.30
assert band["passMask"][40][40] is True
assert band["passMask"][40][0] is False
assert band["passMask"][40][-1] is False

# If the whole sampled box passes, there is no in-box classification boundary.
all_pass = mod.classify_requirement_surface(surface, lower=-2.0, upper=2.0, points=41)
assert all_pass["passGridFraction"] == 1.0
assert all_pass["nearestClassificationBoundaryFromCenterCoded"] is None

try:
    mod.classify_requirement_surface(surface, lower=2.0, upper=1.0)
except ValueError as exc:
    assert "lower bound" in str(exc)
else:
    raise AssertionError("inverted bounds must fail closed")

print("Radiation requirement-contour validation: PASS")
print("- lower/upper requirement masks are deterministic")
print("- center status and nearest in-box classification boundary are bounded")
print("- PASS grid fraction is geometric sampled area, not yield")
print("Boundary: local surrogate classification only; no probability or production-yield claim.")
