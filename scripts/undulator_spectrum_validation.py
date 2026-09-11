#!/usr/bin/env python3
"""Deterministic validation for Physical Lab advanced undulator spectrum studies."""
from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_undulator_spectrum import (  # noqa: E402
    angular_harmonic_map,
    beam_broadened_resonance,
    harmonic_spectrum,
    resonance_energy_eV,
)


def main() -> None:
    period = 0.05
    gamma = 100.0
    K = 0.7

    e1 = resonance_energy_eV(period_m=period, gamma=gamma, K=K, harmonic=1, theta_rad=0.0)
    e3 = resonance_energy_eV(period_m=period, gamma=gamma, K=K, harmonic=3, theta_rad=0.0)
    assert e1 > 0
    assert abs(e3 / e1 - 3.0) < 1e-12

    spectrum = harmonic_spectrum(period_m=period, gamma=gamma, K=K, n_periods=20, harmonics=(1, 2, 3, 5))
    rows = {row["harmonic"]: row for row in spectrum["harmonics"]}
    assert rows[1]["coupling_JJ2"] > 0
    assert rows[2]["coupling_JJ2"] == 0.0
    assert rows[3]["resonance_energy_eV"] > rows[1]["resonance_energy_eV"]
    assert abs(rows[1]["first_zero_relative_half_width"] - 0.05) < 1e-12
    assert max(spectrum["relative_intensity"]) <= 1.0 + 1e-12

    amap = angular_harmonic_map(period_m=period, gamma=gamma, K=K, harmonic=1, theta_max_mrad=2.0, points=51)
    assert abs(amap["on_axis_energy_eV"] - e1) / e1 < 1e-12
    assert amap["minimum_energy_eV"] < amap["on_axis_energy_eV"]
    assert amap["maximum_energy_eV"] <= amap["on_axis_energy_eV"] * (1.0 + 1e-12)

    mono = beam_broadened_resonance(
        period_m=period, gamma=gamma, K=K, harmonic=1,
        relative_energy_spread_rms=0.0, angular_divergence_rms_mrad=0.0,
        samples=5000, seed=11,
    )
    assert mono["relative_rms_linewidth"] < 1e-12

    spread = beam_broadened_resonance(
        period_m=period, gamma=gamma, K=K, harmonic=1,
        relative_energy_spread_rms=1e-3, angular_divergence_rms_mrad=0.0,
        samples=60000, seed=17,
    )
    # E ~ gamma^2 for theta=0, so small relative energy spread maps to ~2*sigma_gamma/gamma.
    expected = 2e-3
    observed = spread["relative_rms_linewidth"]
    assert abs(observed - expected) < 2.0e-4, (observed, expected)

    divergent = beam_broadened_resonance(
        period_m=period, gamma=gamma, K=K, harmonic=1,
        relative_energy_spread_rms=0.0, angular_divergence_rms_mrad=0.20,
        samples=30000, seed=23,
    )
    assert divergent["mean_energy_eV"] < e1
    assert divergent["relative_rms_linewidth"] > 0

    print("Undulator spectrum validation: PASS")
    print(f"- on-axis fundamental: {e1:.6g} eV")
    print(f"- 0.1% electron-energy spread -> photon relative RMS linewidth: {100*observed:.4g}%")
    print(f"- 0.20 mrad divergence mean red-shift: {100*(1-divergent['mean_energy_eV']/e1):.4g}%")
    print("Boundary: resonance/interference and beam-distribution propagation only; no FEL gain, coherent bunch radiation, beamline optics, or detector response.")


if __name__ == "__main__":
    main()
