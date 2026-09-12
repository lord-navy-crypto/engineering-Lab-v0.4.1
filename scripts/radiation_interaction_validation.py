#!/usr/bin/env python3
"""Deterministic checks for pairwise manufacturing-error interaction summaries."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_radiation_interactions.py"
spec = importlib.util.spec_from_file_location("physical_lab_radiation_interactions", MOD)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {MOD}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Additive photon energy: interaction must vanish exactly.
# Non-additive P_lin: AB contains an extra -0.05 interaction.
records = [{
    "pair": ["field_error_pct", "angle_error_deg"],
    "seed": 42,
    "states": {
        "nominal": {"observables": {"photon_energy_eV": 100.0, "P_lin": 0.95}},
        "A": {"observables": {"photon_energy_eV": 98.0, "P_lin": 0.92}},
        "B": {"observables": {"photon_energy_eV": 99.0, "P_lin": 0.85}},
        "AB": {"observables": {"photon_energy_eV": 97.0, "P_lin": 0.77}},
    },
}]
summary = mod.summarize_pair_records(records, metrics=("photon_energy_eV", "P_lin"))
rows = {(r["metric"]): r for r in summary["rows"]}
assert abs(rows["photon_energy_eV"]["interactionResidual"]) < 1e-12
assert abs(rows["photon_energy_eV"]["combinedDelta"] + 3.0) < 1e-12
assert abs(rows["P_lin"]["interactionResidual"] + 0.05) < 1e-12
assert rows["P_lin"]["interactionToMainScale"] > 0.0
assert summary["leadersByMetric"]["P_lin"]["errorA"] == "field_error_pct"
assert summary["leadersByMetric"]["P_lin"]["errorB"] == "angle_error_deg"
assert "higher-order" in summary["boundary"].lower()

# Two seeds aggregate with median |interaction| rather than conflating main effects.
records2 = records + [{
    "pair": ["field_error_pct", "angle_error_deg"],
    "seed": 43,
    "states": {
        "nominal": {"observables": {"P_lin": 1.0}},
        "A": {"observables": {"P_lin": 0.9}},
        "B": {"observables": {"P_lin": 0.8}},
        "AB": {"observables": {"P_lin": 0.62}},
    },
}]
summary2 = mod.summarize_pair_records(records2, metrics=("P_lin",))
g = summary2["grouped"][0]
assert g["count"] == 2
assert g["medianAbsInteractionResidual"] > 0.0

print("Radiation pairwise interaction validation: PASS")
print("- additive main effects yield zero second-order contrast")
print("- non-additive AB response produces the expected interaction residual")
print("- pairwise interaction is kept separate from main-effect magnitude")
print("Boundary: local two-factor screening only; no Sobol/global or higher-order sensitivity claim.")
