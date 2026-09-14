"""Allow-listed Sweep Executor adapter for the rotating U-tube model.

The adapter exposes deterministic model parameters as finite numeric inputs so DOE,
Morris, response surfaces and sensitivity workflows can reuse the normal Engineering
Lab sweep infrastructure.  It does not read measurements and does not claim validation.
"""
from __future__ import annotations

import math
from typing import Any

import physical_lab_utube_experiment as utube

BOUNDARY = (
    "Finite deterministic U-tube model evaluation. Sweep outputs are computational "
    "predictions, not measurements, calibration, validation, causality or optimality."
)


def utube_rotation_sweep(
    volume_ml: float = 3.0,
    n_rpm: float = 260.0,
    rin_m: float = utube.DEFAULT_R_IN_M,
    a_m: float = utube.DEFAULT_A_M,
    rho_kg_m3: float = utube.DEFAULT_RHO,
    gamma_mN_m: float = 54.54,
    theta_deg: float = 48.9,
    nq: float = 84.0,
) -> dict[str, Any]:
    """Evaluate one bounded U-tube model point for Sweep Executor.

    All arguments are numeric because the Sweep Executor deliberately supports only
    finite scalar parameters.  ``nq`` is rounded to the nearest integer and bounded
    to a practical quadrature range.
    """
    volume_ml = float(volume_ml)
    n_rpm = float(n_rpm)
    rin_m = float(rin_m)
    a_m = float(a_m)
    rho_kg_m3 = float(rho_kg_m3)
    gamma_mN_m = float(gamma_mN_m)
    theta_deg = float(theta_deg)
    nq_i = int(round(float(nq)))
    if not all(math.isfinite(x) for x in (volume_ml, n_rpm, rin_m, a_m, rho_kg_m3, gamma_mN_m, theta_deg)):
        raise ValueError("U-tube sweep inputs must be finite")
    if volume_ml <= 0 or n_rpm <= 0 or rin_m <= 0 or a_m <= 0 or rho_kg_m3 <= 0 or gamma_mN_m <= 0:
        raise ValueError("U-tube sweep physical inputs must be positive")
    if not 12 <= nq_i <= 256:
        raise ValueError("nq must round to an integer within 12..256")

    nc = utube.critical_speed(rin_m, a_m)
    ng = utube.threshold(volume_ml, rin_m, a_m, nq_i)
    cap_total, cap_arc, cap_legs = utube.capacity(n_rpm, rin_m, a_m, nq_i)
    geom = utube.geometry(rin_m, a_m)

    prediction: dict[str, Any] = {
        "critical_speed_rpm": nc,
        "threshold_rpm": ng,
        "threshold_margin_rpm": n_rpm - ng,
        "capacity_total_ml": cap_total,
        "capacity_curved_ml": cap_arc,
        "capacity_legs_ml": cap_legs,
        "capacity_margin_ml": cap_total - volume_ml,
        "geometry": geom,
        "quadrature_order": nq_i,
    }

    # The free-energy local expansion is only defined above the angular bifurcation.
    if n_rpm > nc:
        coeff = utube.local_coefficients(n_rpm, rin_m, a_m, rho_kg_m3)
        surface = utube.surface_coefficient(gamma_mN_m, theta_deg)
        a_bulk = 1.0 - 2.0 ** (-0.5)
        a_surf = 2.0 ** (1.0 / 3.0) - 1.0
        vstar_ml = float((a_surf * surface / (a_bulk * coeff["K_mL"])) ** (6.0 / 5.0))
        delta_f_j = float(-a_bulk * coeff["K_mL"] * volume_ml**1.5 + a_surf * surface * volume_ml ** (2.0 / 3.0))
        prediction["free_energy"] = {
            "K_J_mL32": coeff["K_mL"],
            "surface_J_mL23": surface,
            "theta_model_deg": coeff["theta_m_deg"],
            "vstar_ml": vstar_ml,
            "delta_f_j": delta_f_j,
        }
    else:
        prediction["free_energy_available"] = False

    return {
        "schema": "engineering-lab-utube-sweep-result/v1",
        "inputs": {
            "volume_ml": volume_ml,
            "n_rpm": n_rpm,
            "rin_m": rin_m,
            "a_m": a_m,
            "rho_kg_m3": rho_kg_m3,
            "gamma_mN_m": gamma_mN_m,
            "theta_deg": theta_deg,
            "nq": nq_i,
        },
        "prediction": prediction,
        "boundary": BOUNDARY,
    }
