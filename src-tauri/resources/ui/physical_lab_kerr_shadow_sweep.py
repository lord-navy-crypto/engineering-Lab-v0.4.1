"""Parameter sweeps for Kerr shadow morphology.

This module builds on the bounded vacuum critical-curve calculation in
``physical_lab_deep_science``.  It studies how observer inclination and Kerr spin
change image-plane morphology without introducing accretion/emission physics.
"""
from __future__ import annotations

from typing import Any, Iterable

from physical_lab_deep_science import kerr_shadow_curve


def kerr_shadow_morphology_sweep(
    *,
    spins: Iterable[float] = (0.0, 0.3, 0.6, 0.8, 0.9, 0.98),
    inclinations_deg: Iterable[float] = (20.0, 40.0, 60.0, 80.0),
    curve_samples: int = 320,
) -> dict[str, Any]:
    spin_values = sorted({round(float(value), 8) for value in spins})
    inclination_values = sorted({round(float(value), 8) for value in inclinations_deg})
    if not spin_values or not inclination_values:
        raise ValueError("spin and inclination grids must be non-empty")
    if min(spin_values) < 0.0 or max(spin_values) >= 1.0:
        raise ValueError("spin grid must satisfy 0 <= a/M < 1")
    if min(inclination_values) < 0.5 or max(inclination_values) > 90.0:
        raise ValueError("inclination grid must be within [0.5, 90] degrees")
    rows: list[dict[str, float]] = []
    for inclination in inclination_values:
        for spin in spin_values:
            curve = kerr_shadow_curve(
                spin=spin,
                observer_inclination_deg=inclination,
                samples=int(curve_samples),
            )
            width = float(curve["width_over_M"])
            height = float(curve["height_over_M"])
            mean_diameter = 0.5 * (width + height)
            flattening = (width - height) / max(mean_diameter, 1e-15)
            rows.append({
                "spin_a_over_M": spin,
                "observer_inclination_deg": inclination,
                "width_over_M": width,
                "height_over_M": height,
                "mean_diameter_over_M": mean_diameter,
                "horizontal_shift_over_M": float(curve["horizontal_midpoint_shift_over_M"]),
                "signed_flattening": flattening,
                "area_over_M2": float(curve["critical_curve_area_over_M2"]),
            })
    reference = next(
        row for row in rows
        if row["spin_a_over_M"] == min(spin_values)
        and row["observer_inclination_deg"] == min(inclination_values)
    )
    maximum_shift = max(rows, key=lambda row: abs(row["horizontal_shift_over_M"]))
    maximum_distortion = max(rows, key=lambda row: abs(row["signed_flattening"]))
    return {
        "schema": "physical-lab-kerr-shadow-morphology-sweep-v1",
        "spins": spin_values,
        "inclinations_deg": inclination_values,
        "rows": rows,
        "max_abs_horizontal_shift_over_M": abs(maximum_shift["horizontal_shift_over_M"]),
        "max_shift_case": maximum_shift,
        "max_abs_signed_flattening": abs(maximum_distortion["signed_flattening"]),
        "max_distortion_case": maximum_distortion,
        "reference_case": reference,
        "boundary": (
            "Vacuum Kerr distant-observer critical-curve morphology only. Changes with spin and inclination describe the mathematical capture boundary, "
            "not brightness, photon-ring intensity, accretion morphology, telescope resolution, or a parameter inference from observations."
        ),
    }
