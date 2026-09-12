#!/usr/bin/env python3
"""Deterministic validation for stochastic scaling and lattice localization studies."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_model_depth_v import (
    random_walk_diffusion_return_study,
    qmc_dimension_sensitivity,
    lattice_defect_localization_study,
)

rw = random_walk_diffusion_return_study(walkers=8000, steps=800, seed=20260911, checkpoints=(10,20,50,100,200,400,800))
assert 0.88 < rw["msd_loglog_slope"] < 1.12, rw["msd_loglog_slope"]
assert 0.20 < rw["effective_diffusion_coefficient_2d"] < 0.30, rw["effective_diffusion_coefficient_2d"]
assert 0.0 < rw["returned_fraction_by_horizon"] < 1.0

q = qmc_dimension_sensitivity(dimensions=(2,4,8), power=8, replicates=4, seed=20260911)
assert len(q["rows"]) == 3
for row in q["rows"]:
    for key in ("mc_median_abs_error","qmc_median_abs_error","median_improvement_factor","scrambled_sobol_discrepancy_probe"):
        assert math.isfinite(float(row[key])) and float(row[key]) >= 0.0, (key,row[key])

loc = lattice_defect_localization_study(nx=2, ny=2, layers=1, defect_mode="mass", defect_mass_multiplier=6.0)
assert loc["negative_eigenvalue_magnitude_max"] < 1e-5, loc["negative_eigenvalue_magnitude_max"]
assert len(loc["pristine_modes"]) == len(loc["defect_modes"])
for row in loc["defect_modes"]:
    assert 0.0 < row["participation_ratio_fraction"] <= 1.000001
    assert 0.0 <= row["defect_overlap_fraction"] <= 1.000001
assert loc["largest_defect_overlap_mode"]["defect_overlap_fraction"] > 0.25

print("Model Depth V validation: PASS")
print(f"- random-walk MSD slope: {rw['msd_loglog_slope']:.4f}")
print(f"- effective 2-D diffusion coefficient: {rw['effective_diffusion_coefficient_2d']:.4f}")
print(f"- max defect-mode overlap: {loc['largest_defect_overlap_mode']['defect_overlap_fraction']:.4f}")
print("Boundary: finite stochastic ensembles and reduced-unit finite-supercell localization only.")
