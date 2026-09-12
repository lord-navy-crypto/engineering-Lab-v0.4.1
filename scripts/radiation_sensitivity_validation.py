#!/usr/bin/env python3
"""Deterministic checks for finite one-factor radiation sensitivity summaries."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_sensitivity.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_sensitivity", MOD)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MOD}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

nominal = {
    "observables": {
        "photon_energy_eV": 100.0,
        "relative_linewidth": 0.01,
        "P_lin": 0.95,
        "P_circ": 0.02,
        "H3_over_H1": 0.03,
    }
}
records = {
    "field_error_pct": [
        {"observables": {"photon_energy_eV": 98.0, "relative_linewidth": 0.012, "P_lin": 0.93, "P_circ": 0.02, "H3_over_H1": 0.04}},
        {"observables": {"photon_energy_eV": 102.0, "relative_linewidth": 0.013, "P_lin": 0.92, "P_circ": 0.01, "H3_over_H1": 0.05}},
    ],
    "angle_error_deg": [
        {"observables": {"photon_energy_eV": 99.8, "relative_linewidth": 0.011, "P_lin": 0.80, "P_circ": 0.15, "H3_over_H1": 0.031}},
        {"observables": {"photon_energy_eV": 100.2, "relative_linewidth": 0.0115, "P_lin": 0.82, "P_circ": 0.14, "H3_over_H1": 0.032}},
    ],
}
magnitudes = {"field_error_pct": 1.0, "angle_error_deg": 0.2}
summary = mod.summarize_one_factor_records(nominal, records, magnitudes)
rows = summary["rows"]
assert rows, "expected non-empty sensitivity rows"

lookup = {(row["error"], row["metric"]): row for row in rows}
field_energy = lookup[("field_error_pct", "photon_energy_eV")]
assert abs(field_energy["meanSignedDelta"]) < 1e-12
assert abs(field_energy["medianAbsDelta"] - 2.0) < 1e-12
assert abs(field_energy["medianAbsDeltaPerInputUnit"] - 2.0) < 1e-12

angle_plin = lookup[("angle_error_deg", "P_lin")]
assert angle_plin["medianAbsDelta"] > lookup[("field_error_pct", "P_lin")]["medianAbsDelta"]
assert summary["leadersByMetric"]["P_lin"]["error"] == "angle_error_deg"
assert summary["leadersByMetric"]["photon_energy_eV"]["error"] == "field_error_pct"
assert "interaction" in summary["boundary"].lower()

print("Radiation OFAT sensitivity validation: PASS")
print("- metric-local attribution preserved; no cross-metric global score")
print("- signed, absolute, and per-input-unit deltas are deterministic")
print("- leader selection is specific to each physical observable")
print("Boundary: finite OFAT screening only; interaction/global sensitivity is intentionally not inferred.")
