#!/usr/bin/env python3
"""Deterministic checks for Physical Lab deep-science simulation extensions."""
from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_deep_science import (  # noqa: E402
    kerr_shadow_curve,
    lattice_vacf_study,
    measured_series_numerics,
    numerical_error_atlas,
    solar_symplectic_comparison,
)


def main() -> int:
    # Kerr: Schwarzschild shadow is a circle of radius sqrt(27) M.
    schwarz = kerr_shadow_curve(spin=0.0, observer_inclination_deg=60.0, samples=720)
    expected_radius = math.sqrt(27.0)
    assert abs(float(schwarz["width_over_M"]) - 2.0 * expected_radius) < 2e-3
    assert abs(float(schwarz["height_over_M"]) - 2.0 * expected_radius) < 2e-3
    assert abs(float(schwarz["horizontal_midpoint_shift_over_M"])) < 2e-3
    expected_area = math.pi * expected_radius**2
    assert abs(float(schwarz["critical_curve_area_over_M2"]) / expected_area - 1.0) < 2e-3

    # Rotating Kerr critical curve remains finite and becomes horizontally displaced/asymmetric.
    rotating = kerr_shadow_curve(spin=0.9, observer_inclination_deg=60.0, samples=700)
    assert len(rotating["alpha_over_M"]) > 100
    assert 8.0 < float(rotating["width_over_M"]) < 12.0
    assert 8.0 < float(rotating["height_over_M"]) < 12.0
    assert abs(float(rotating["horizontal_midpoint_shift_over_M"])) > 0.25
    assert float(rotating["critical_curve_area_over_M2"]) > 50.0

    # Numerical atlas: independent mechanisms must show their characteristic behavior.
    atlas = numerical_error_atlas()
    summary = atlas["summary"]
    assert int(summary["float32_step_collapse_cases"]) >= 1
    assert 1.8 <= float(summary["trapezoid_observed_order"]) <= 2.2
    assert float(summary["final_kahan_sum_abs_error"]) <= float(summary["final_naive_sum_abs_error"])
    assert float(summary["smallest_x_stable_cancellation_error"]) <= float(summary["smallest_x_raw_cancellation_error"])
    assert float(summary["alias_frequency_error_Hz"]) < 0.2
    assert float(summary["max_q15_abs_error"]) <= 1.0 / 32768.0 + 1e-12

    # BetterBoard-style measured-series numerics: irregular timestamps stay explicit.
    n = 1000
    increments = 0.01 + 0.0008 * np.sin(np.arange(n - 1) * 0.17)
    t = np.concatenate(([0.0], np.cumsum(increments)))
    y = np.sin(1.7 * t) + 0.05 * np.cos(0.3 * t)
    measured = measured_series_numerics(t, y, downsample_factors=(2, 4, 8))
    assert measured["sample_count"] == n
    assert float(measured["jitter_p95_abs_s"]) > 0.0
    assert len(measured["downsampling"]) == 3
    derivative = np.asarray([np.nan if value is None else value for value in measured["irregular_three_point_derivative"]], dtype=float)
    analytic = 1.7 * np.cos(1.7 * t) - 0.015 * np.sin(0.3 * t)
    mask = np.isfinite(derivative)
    assert math.sqrt(float(np.mean((derivative[mask] - analytic[mask]) ** 2))) < 0.01

    # Solar system: short independent fixed-step Newtonian comparison remains conservative/bounded.
    solar = solar_symplectic_comparison(duration_years=12.0, dt_years=0.02, reference_samples=500)
    assert float(solar["verlet_max_relative_energy_drift"]) < 5e-4
    assert float(solar["verlet_max_relative_angular_momentum_drift"]) < 1e-10
    assert float(solar["final_jupiter_position_difference_vs_DOP853_AU"]) < 0.15
    assert float(solar["final_saturn_position_difference_vs_DOP853_AU"]) < 0.15

    # Honeycomb: conservative microtrajectory produces normalized VACF/spectrum with bounded drift.
    lattice = lattice_vacf_study(nx=2, ny=2, layers=1, steps=512, dt=0.003, velocity_scale=0.015)
    vacf = np.asarray(lattice["vacf_normalized"], dtype=float)
    freq = np.asarray(lattice["frequency_cycles_per_reduced_time"], dtype=float)
    density = np.asarray(lattice["vibrational_spectral_density_normalized"], dtype=float)
    assert abs(float(vacf[0]) - 1.0) < 1e-12
    assert np.all(np.isfinite(vacf)) and np.all(np.isfinite(density))
    assert float(lattice["dominant_frequency_cycles_per_reduced_time"]) > 0.0
    area = float(np.trapezoid(density, freq))
    assert abs(area - 1.0) < 2e-3
    assert float(lattice["max_relative_energy_drift"]) < 5e-3

    print("Deep-science validation: PASS")
    print(f"- Kerr a=0.9 shadow shift: {rotating['horizontal_midpoint_shift_over_M']:.6g} M")
    print(f"- Solar Verlet max energy drift: {solar['verlet_max_relative_energy_drift']:.3e}")
    print(f"- Honeycomb VACF dominant frequency: {lattice['dominant_frequency_cycles_per_reduced_time']:.6g} cycles/t*")
    print(f"- Numeric atlas float32 step-collapse cases: {summary['float32_step_collapse_cases']}")
    print("Boundary: computational verification/diagnostics only; no telescope image, ephemeris validation, calibrated molecular spectrum, or measurement ground-truth claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
