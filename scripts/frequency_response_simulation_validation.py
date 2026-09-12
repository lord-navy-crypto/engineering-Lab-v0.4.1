#!/usr/bin/env python3
"""Deterministic validation for Physical Lab frequency-response simulations."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_frequency_response import (  # noqa: E402
    duffing_frequency_sweep,
    linear_forced_response_sweep,
)


def main() -> int:
    # Linear forced oscillator: the time-domain RK4 sweep should reproduce the
    # independent analytic steady-state transfer function over and through resonance.
    linear = linear_forced_response_sweep(
        omega_n=2.0,
        zeta=0.08,
        force_amplitude=0.7,
        frequency_start=0.8,
        frequency_stop=3.0,
        frequency_points=13,
        settle_cycles=18,
        observe_cycles=6,
        points_per_cycle=64,
    )
    assert linear["profile"] == "oscillation-integration"
    assert linear["scenario"] == "linear-forced-frequency-response"
    assert len(linear["rows"]) == 13
    assert float(linear["max_amplitude_relative_error"]) < 0.01
    assert float(linear["max_phase_absolute_error_rad"]) < 0.01
    theoretical = float(linear["theoretical_resonance_frequency_rad_s"])
    numerical_peak = float(linear["numerical_peak_frequency_rad_s"])
    grid_spacing = (3.0 - 0.8) / 12.0
    assert abs(numerical_peak - theoretical) <= 1.25 * grid_spacing
    for row in linear["rows"]:
        assert float(row["fundamental_amplitude"]) >= 0.0
        assert math.isfinite(float(row["harmonic_residual_rms"]))
        assert math.isfinite(float(row["phase_lag_rad"]))

    # Hardening Duffing oscillator: continuation must produce a resolved nonlinear
    # response curve and, for this deterministic test case, a strong branch-sensitive
    # region. This checks simulation behavior, not a universal hysteresis claim.
    duffing = duffing_frequency_sweep(
        omega_0=1.0,
        zeta=0.05,
        cubic_stiffness=1.0,
        force_amplitude=0.30,
        frequency_start=0.75,
        frequency_stop=1.60,
        frequency_points=15,
        settle_cycles=25,
        observe_cycles=6,
        points_per_cycle=48,
    )
    assert duffing["profile"] == "nonlinear-chaos"
    assert duffing["scenario"] == "duffing-nonlinear-frequency-response"
    assert len(duffing["rows"]) == 15
    assert float(duffing["forward_response_amplitude_span"]) > 0.5
    assert float(duffing["max_branch_amplitude_gap"]) > 0.25
    gap_frequency = float(duffing["max_branch_gap_frequency_rad_s"])
    assert 0.75 <= gap_frequency <= 1.60
    for row in duffing["rows"]:
        for field in (
            "forward_amplitude",
            "reverse_amplitude",
            "branch_amplitude_gap",
            "forward_harmonic_residual_rms",
            "reverse_harmonic_residual_rms",
            "forward_poincare_spread",
            "reverse_poincare_spread",
        ):
            value = float(row[field])
            assert math.isfinite(value) and value >= 0.0

    # Determinism is part of the model contract: repeated bounded sweeps with the
    # same inputs should not move the reported branch-gap metric.
    repeat = duffing_frequency_sweep(
        omega_0=1.0,
        zeta=0.05,
        cubic_stiffness=1.0,
        force_amplitude=0.30,
        frequency_start=0.75,
        frequency_stop=1.60,
        frequency_points=15,
        settle_cycles=25,
        observe_cycles=6,
        points_per_cycle=48,
    )
    assert abs(float(repeat["max_branch_amplitude_gap"]) - float(duffing["max_branch_amplitude_gap"])) < 1e-12

    print("Frequency-response simulation validation: PASS")
    print(
        f"- linear analytic agreement: max amplitude error={linear['max_amplitude_relative_error']:.3g}, "
        f"max phase error={linear['max_phase_absolute_error_rad']:.3g} rad"
    )
    print(
        f"- Duffing branch sensitivity: max gap={duffing['max_branch_amplitude_gap']:.4g} "
        f"at omega={duffing['max_branch_gap_frequency_rad_s']:.4g} rad/s"
    )
    print(
        "Boundary: numerical resonance and continuation evidence only; no experimental validation, "
        "complete bifurcation proof, or hardware hysteresis claim."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
