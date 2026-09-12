#!/usr/bin/env python3
"""Deterministic validation for the bounded quadratic radiation response surface."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_response_surface.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_response_surface", MOD)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MOD}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Exact synthetic quadratic: coefficients must be recovered to numerical precision.
# y = 10 + 2x - 3z + 4x^2 + 5z^2 + 6xz
records = []
for x in (-1.0, 0.0, 1.0):
    for z in (-1.0, 0.0, 1.0):
        y = 10.0 + 2.0*x - 3.0*z + 4.0*x*x + 5.0*z*z + 6.0*x*z
        records.append({"codedA": x, "codedB": z, "observables": {"photon_energy_eV": y}})

surface = mod.fit_metric_surface(records, "photon_energy_eV", factor_a="field_error_pct", factor_b="gap_asymmetry_mm")
c = surface["coefficients"]
expected = {
    "intercept": 10.0,
    "linearA": 2.0,
    "linearB": -3.0,
    "quadraticA": 4.0,
    "quadraticB": 5.0,
    "interactionAB": 6.0,
}
for key, value in expected.items():
    assert abs(c[key] - value) < 1e-10, (key, c[key], value)
assert surface["fit"]["rank"] == 6
assert surface["fit"]["r2"] > 1.0 - 1e-12
assert surface["fit"]["rmse"] < 1e-10
assert abs(mod.predict_quadratic(c, 0.25, -0.5) - (10 + 2*.25 - 3*(-.5) + 4*.25**2 + 5*.5**2 + 6*.25*(-.5))) < 1e-10

grid = mod.prediction_grid(surface, points=21)
assert len(grid["codedA"]) == 21 and len(grid["codedB"]) == 21
assert len(grid["predicted"]) == 21 and all(len(row) == 21 for row in grid["predicted"])

summary = mod.summarize_response_surfaces(records, factor_a="field_error_pct", factor_b="gap_asymmetry_mm", metrics=("photon_energy_eV",))
assert "photon_energy_eV" in summary["surfaces"]
assert "do not extrapolate" in summary["boundary"].lower()
assert mod.LEVEL_TO_SCALE[-1.0] == 0.0
assert mod.LEVEL_TO_SCALE[0.0] == 0.5
assert mod.LEVEL_TO_SCALE[1.0] == 1.0

print("Radiation response-surface validation: PASS")
print("- exact linear, curvature, and interaction coefficients recovered")
print("- coded -1/0/+1 map to 0/0.5/1.0 of configured error magnitude")
print("- fit diagnostics and bounded prediction grid are deterministic")
print("Boundary: local surrogate only; R2 is fit quality, not physical validation or extrapolation authority.")
