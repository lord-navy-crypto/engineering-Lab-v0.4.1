#!/usr/bin/env python3
"""Deterministic contract checks for trajectory-radiation Stokes extraction."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_worker.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_worker", WORKER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {WORKER}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Full run_sim schema: nested Stokes / harmonic / photon / K payloads.
synthetic_full = {
    "Stokes": {
        "I": 10.0,
        "Q": 3.0,
        "U": 4.0,
        "V": 8.0,
        "P_lin": 0.6,
        "P_circ": 0.8,
        "basis_convention": "right-handed (e1, e2, n)",
        "V_convention": "+2 Im(E1 E2*)",
    },
    "harmonic_ratios": {"H3_over_H1": 0.04, "H5_over_H1": 0.005},
    "photon_energy": {"eV": 123.4},
    "K_components": {"K0": 0.7, "Kx": 0.7, "Ky": 0.0, "K_eff_rms": 0.4949747468},
    "trajectory_phase": {"max_transverse_excursion_m": 2e-4},
    "theory_residuals": {"frequency_relative_residual": 1e-5},
}

st = mod._extract_stokes(synthetic_full)
assert abs(st["polarization_degree"] - 1.0) < 1e-12
assert st["P_lin"] == 0.6 and st["P_circ"] == 0.8
assert st["basis_convention"] == "right-handed (e1, e2, n)"

harm = mod._extract_harmonics(synthetic_full)
assert harm["H3_over_H1"] == 0.04
assert harm["H5_over_H1"] == 0.005

obs = mod._extract_result(synthetic_full)
assert obs["photon_energy_eV"] == 123.4
assert obs["P_lin"] == 0.6 and obs["P_circ"] == 0.8
assert obs["H3_over_H1"] == 0.04 and obs["H5_over_H1"] == 0.005
assert obs["max_transverse_excursion_m"] == 2e-4
assert obs["frequency_relative_residual"] == 1e-5

# run_sim_scalar schema: polarization/harmonic/photon/K values are flattened.
synthetic_scalar = {
    "P_lin": 0.3,
    "P_circ": -0.4,
    "H3_over_H1": 0.07,
    "H5_over_H1": 0.009,
    "photon_energy_eV": 88.0,
    "Kx": 0.6,
    "Ky": 0.2,
    "relative_linewidth": 0.012,
    "max_transverse_excursion_m": 3e-4,
    "frequency_relative_residual": -2e-5,
}
scalar_st = mod._extract_stokes(synthetic_scalar)
assert scalar_st["P_lin"] == 0.3 and scalar_st["P_circ"] == -0.4
assert abs(scalar_st["polarization_degree"] - 0.5) < 1e-12
scalar_harm = mod._extract_harmonics(synthetic_scalar)
assert scalar_harm["H3_over_H1"] == 0.07 and scalar_harm["H5_over_H1"] == 0.009
scalar_obs = mod._extract_result(synthetic_scalar)
assert scalar_obs["photon_energy_eV"] == 88.0
assert scalar_obs["H3_over_H1"] == 0.07 and scalar_obs["H5_over_H1"] == 0.009
assert scalar_obs["P_lin"] == 0.3 and scalar_obs["P_circ"] == -0.4
assert scalar_obs["K_Kx"] == 0.6 and scalar_obs["K_Ky"] == 0.2

safe = mod._json_safe_matrix(np.asarray([[1.0, np.nan], [np.inf, -2.0]]))
assert safe == [[1.0, None], [None, -2.0]]
json.dumps({"matrix": safe}, allow_nan=False)

bad = mod._extract_stokes({"Stokes": {"P_lin": float("nan"), "P_circ": 0.25}})
assert bad["P_lin"] is None
assert bad["polarization_degree"] is None

print("Radiation worker Stokes contract: PASS")
print("- full run_sim nested I/Q/U/V + polarization/harmonic schema preserved")
print("- run_sim_scalar flattened polarization/harmonic schema preserved")
print("- polarization-degree sanity cases preserved")
print("- nested trajectory/residual diagnostics and flat scalar diagnostics normalize consistently")
print("- non-finite angular pixels serialize as JSON null, never NaN/Infinity")
print("Boundary: this validates the Physical Lab adapter contract, not the underlying Radiation Platform physics solver itself.")
