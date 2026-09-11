#!/usr/bin/env python3
"""Deterministic checks for manufacturing radiation-quality degradation analysis."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_quality.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_quality", MODULE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MODULE}")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

nominal = {
    "observables": {"relative_linewidth": 0.01, "photon_energy_eV": 100.0, "P_circ": 0.8, "P_lin": 0.5, "polarization_degree": 0.9433981132},
    "stokes": {"P_circ": 0.8, "P_lin": 0.5, "polarization_degree": 0.9433981132},
    "harmonicRatios": {"H3_over_H1": 0.02, "H5_over_H1": 0.005},
}
members = [
    {
        "seed": 10,
        "observables": {"relative_linewidth": 0.011, "photon_energy_eV": 99.8},
        "stokes": {"P_circ": 0.78, "P_lin": 0.51, "polarization_degree": 0.9329523032},
        "harmonicRatios": {"H3_over_H1": 0.022, "H5_over_H1": 0.0055},
    },
    {
        "seed": 11,
        "observables": {"relative_linewidth": 0.015, "photon_energy_eV": 98.0},
        "stokes": {"P_circ": 0.65, "P_lin": 0.45, "polarization_degree": 0.7905694150},
        "harmonicRatios": {"H3_over_H1": 0.035, "H5_over_H1": 0.009},
    },
    {
        "seed": 12,
        "observables": {"relative_linewidth": 0.0105, "photon_energy_eV": 100.2},
        "stokes": {"P_circ": 0.79, "P_lin": 0.49, "polarization_degree": 0.9296235790},
        "harmonicRatios": {"H3_over_H1": 0.021, "H5_over_H1": 0.0052},
    },
]

flat = core.flatten_radiation_quality(nominal)
assert flat["H3_over_H1"] == 0.02
assert flat["P_circ"] == 0.8

summary = core.summarize_radiation_quality(nominal, members)
assert summary["metrics"]["H3_over_H1"]["worstSeedByAbsoluteDelta"] == 11
assert summary["metrics"]["P_circ"]["worstSeedByAbsoluteDelta"] == 11
assert summary["metrics"]["photon_energy_eV"]["worstSeedByAbsoluteDelta"] == 11
assert summary["diagnosticRanking"][0]["seed"] == 11
assert summary["metrics"]["relative_linewidth"]["max"] == 0.015
assert "yield" in summary["boundary"].lower()

print("Radiation quality degradation validation: PASS")
print("- nested worker-v2 Stokes/harmonic records flatten correctly")
print("- worst-seed ranking identifies the deliberately degraded realization")
print("- polarization, harmonic contamination, linewidth and photon-energy deltas remain separate observables")
print("Boundary: the combined deviation score ranks simulated seeds only; it is not a certification or yield metric.")
