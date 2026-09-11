#!/usr/bin/env python3
"""Deterministic unit checks for nominal-vs-seed angular radiation comparison."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_seed_compare.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_seed_compare", MODULE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MODULE}")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

axis = [-0.001, 0.0, 0.001]
valid = [[True, True, True], [True, True, True], [True, True, False]]
nominal = {
    "observables": {"photon_energy_eV": 100.0, "relative_linewidth": 0.01},
    "stokes": {"P_lin": 0.9, "P_circ": 0.1, "polarization_degree": 0.9055385138},
    "angularMap": {
        "theta_x_rad": axis, "theta_y_rad": axis, "valid_mask": valid,
        "fluence_J_m2": [[1,2,1],[2,4,2],[1,2,None]],
        "P_lin": [[.8,.85,.8],[.85,.9,.85],[.8,.85,None]],
        "P_circ": [[.1,.08,.1],[.08,.05,.08],[.1,.08,None]],
        "f_peak_hz": [[10,11,10],[11,12,11],[10,11,None]],
    },
}
seeded = {
    "observables": {"photon_energy_eV": 98.0, "relative_linewidth": 0.013},
    "stokes": {"P_lin": 0.82, "P_circ": 0.16, "polarization_degree": 0.8354633440},
    "angularMap": {
        "theta_x_rad": axis, "theta_y_rad": axis, "valid_mask": valid,
        "fluence_J_m2": [[.8,1.8,.9],[1.7,3.4,1.8],[.9,1.7,None]],
        "P_lin": [[.72,.78,.73],[.78,.82,.79],[.73,.78,None]],
        "P_circ": [[.16,.14,.15],[.14,.12,.14],[.15,.14,None]],
        "f_peak_hz": [[9.8,10.7,9.8],[10.7,11.4,10.8],[9.8,10.7,None]],
    },
}

cmp = core.compare_angular_maps(nominal, seeded)
assert cmp["mutuallyValidPixels"] == 8
assert abs(cmp["scalarDeltas"]["photon_energy_eV"]["delta"] + 2.0) < 1e-12
assert abs(cmp["scalarDeltas"]["P_lin"]["delta"] + 0.08) < 1e-12
assert cmp["mapMetrics"]["fluence_J_m2"]["maxAbsDelta"] > 0.0
assert cmp["mapMetrics"]["P_circ"]["meanDelta"] > 0.0
assert cmp["mapMetrics"]["f_peak_hz"]["maxAbsRelativeDelta"] > 0.0
assert cmp["deltaMaps"]["fluence_J_m2"][2][2] is None
assert "seed only" in cmp["boundary"]

bad = dict(seeded)
bad["angularMap"] = dict(seeded["angularMap"])
bad["angularMap"]["theta_x_rad"] = [-0.002, 0.0, 0.002]
try:
    core.compare_angular_maps(nominal, bad)
except ValueError as exc:
    assert "grids do not match" in str(exc)
else:
    raise AssertionError("mismatched angular grids must fail closed")

print("Radiation seed-map comparison validation: PASS")
print("- mutually valid pixels are intersected rather than filling missing data")
print("- scalar and 2-D radiation deltas preserve their separate physical quantities")
print("- mismatched observer grids fail closed")
print("Boundary: targeted seed diagnosis only; no unsampled worst-case or manufacturing-yield claim.")
