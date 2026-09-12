#!/usr/bin/env python3
"""Deterministic validation for Kerr shadow morphology sweeps."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_kerr_shadow_sweep import kerr_shadow_morphology_sweep  # noqa: E402


def main() -> int:
    result = kerr_shadow_morphology_sweep(
        spins=(0.0, 0.5, 0.9, 0.98),
        inclinations_deg=(20.0, 60.0, 80.0),
        curve_samples=260,
    )
    rows = result["rows"]
    assert len(rows) == 12
    schwarz = [row for row in rows if row["spin_a_over_M"] == 0.0]
    assert len(schwarz) == 3
    # Schwarzschild is observer-isotropic and unshifted.
    for row in schwarz:
        assert abs(float(row["horizontal_shift_over_M"])) < 3e-3
        assert abs(float(row["signed_flattening"])) < 3e-3
    high_spin = [row for row in rows if row["spin_a_over_M"] == 0.98]
    edge = max(high_spin, key=lambda row: row["observer_inclination_deg"])
    low_inc = min(high_spin, key=lambda row: row["observer_inclination_deg"])
    assert abs(float(edge["horizontal_shift_over_M"])) > 1.0
    assert abs(float(edge["signed_flattening"])) > abs(float(low_inc["signed_flattening"]))
    assert float(result["max_abs_horizontal_shift_over_M"]) > 1.0
    assert float(result["max_abs_signed_flattening"]) > 0.01
    print("Kerr shadow morphology validation: PASS")
    print(f"- max |shift| = {result['max_abs_horizontal_shift_over_M']:.6g} M")
    print(f"- max |flattening| = {100.0 * result['max_abs_signed_flattening']:.5g}%")
    print("Boundary: vacuum capture critical curves only; no brightness or observational parameter inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
