"""Advanced physics and engineering tools for the rotating U-tube experiment.

These utilities build on the deterministic U-tube model without changing its
physical equations. They expose dimensionless scaling, operating-state
classification, inverse geometry design, bounded design-space exploration,
local threshold elasticity and experiment scan planning.

Important: dimensionless groups are scaling diagnostics, not replacement
criteria for the full 3-D model. Design recommendations are computational
proposals, not experimental evidence or hardware safety certification.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from physical_lab_utube_experiment import (
    BOUNDARY as UTUBE_BOUNDARY,
    DEFAULT_A_M,
    DEFAULT_RHO,
    DEFAULT_R_IN_M,
    G,
    capacity,
    critical_speed,
    geometry,
    omega,
    threshold,
)

ADVANCED_SCHEMA = "engineering-lab-utube-advanced/v1"

BOUNDARY = (
    "Advanced U-tube engineering tools derive from the existing deterministic 3-D model. "
    "Dimensionless groups summarize competing scales but do not replace the solved geometry. "
    "Inverse-design and design-space candidates are computational proposals only; they do not establish manufacturability, safety, calibration, or experimental validity."
)


def dimensionless_groups(
    n_rpm: float,
    *,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    rho_kg_m3: float = DEFAULT_RHO,
    gamma_mN_m: float = 72.0,
) -> dict[str, float]:
    """Return transparent scaling groups for gravity/rotation/capillarity competition."""
    geom = geometry(rin_m, a_m)
    ell = geom["ell_m"]
    w = float(omega(float(n_rpm)))
    rho = float(rho_kg_m3)
    gamma = float(gamma_mN_m) * 1e-3
    if rho <= 0 or gamma <= 0:
        raise ValueError("rho_kg_m3 and gamma_mN_m must be positive")
    froude_rot = w * w * ell / G
    bond_tube = rho * G * a_m * a_m / gamma
    tangential_speed = w * ell
    weber_rot = rho * tangential_speed * tangential_speed * a_m / gamma
    capillary_length = float(np.sqrt(gamma / (rho * G)))
    return {
        "rotational_froude": float(froude_rot),
        "bond_tube": float(bond_tube),
        "rotational_weber": float(weber_rot),
        "capillary_length_m": capillary_length,
        "ell_over_capillary_length": float(ell / capillary_length),
    }


def operating_state(
    volume_ml: float,
    n_rpm: float,
    *,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    nq: int = 64,
    near_threshold_band_rpm: float = 3.0,
) -> dict[str, Any]:
    """Classify a selected operating point relative to n_c and the finite-volume n_g."""
    nc = critical_speed(rin_m, a_m)
    ng = threshold(volume_ml, rin=rin_m, a=a_m, nq=nq)
    cap_total, cap_curved, cap_legs = capacity(n_rpm, rin=rin_m, a=a_m, nq=nq)
    margin = float(n_rpm - ng)
    if n_rpm < nc:
        regime = "below-angular-bifurcation"
    elif abs(margin) <= abs(float(near_threshold_band_rpm)):
        regime = "near-finite-volume-threshold"
    elif margin < 0:
        regime = "above-angular-bifurcation-below-volume-threshold"
    else:
        regime = "above-finite-volume-threshold"
    return {
        "schema": ADVANCED_SCHEMA,
        "regime": regime,
        "n_rpm": float(n_rpm),
        "critical_speed_rpm": float(nc),
        "threshold_rpm": float(ng),
        "threshold_margin_rpm": margin,
        "capacity_total_ml": float(cap_total),
        "capacity_margin_ml": float(cap_total - volume_ml),
        "capacity_curved_ml": float(cap_curved),
        "capacity_legs_ml": float(cap_legs),
        "boundary": "Regime labels are model-relative operating classifications, not direct observations of connectivity or failure.",
    }


def inverse_geometry_design(
    target_threshold_rpm: float,
    volume_ml: float,
    *,
    solve_for: str = "rin_m",
    bounds: tuple[float, float] = (0.005, 0.060),
    fixed_rin_m: float = DEFAULT_R_IN_M,
    fixed_a_m: float = DEFAULT_A_M,
    nq: int = 48,
) -> dict[str, float]:
    """Solve one geometry parameter so the full model reaches a requested n_g."""
    target = float(target_threshold_rpm)
    low, high = map(float, bounds)
    if not (target > 0 and 0 < low < high):
        raise ValueError("target and bounds must be positive")
    if solve_for not in {"rin_m", "a_m"}:
        raise ValueError("solve_for must be rin_m or a_m")

    def residual(value: float) -> float:
        rin = value if solve_for == "rin_m" else fixed_rin_m
        a = value if solve_for == "a_m" else fixed_a_m
        return threshold(volume_ml, rin=rin, a=a, nq=nq) - target

    f_low, f_high = residual(low), residual(high)
    if f_low == 0:
        root = low
    elif f_high == 0:
        root = high
    elif f_low * f_high > 0:
        raise ValueError("requested target is not bracketed by the supplied geometry bounds")
    else:
        root = float(brentq(residual, low, high, xtol=1e-10))
    rin = root if solve_for == "rin_m" else fixed_rin_m
    a = root if solve_for == "a_m" else fixed_a_m
    achieved = threshold(volume_ml, rin=rin, a=a, nq=nq)
    return {
        "solved_value_m": float(root),
        "R_in_m": float(rin),
        "a_m": float(a),
        "target_threshold_rpm": target,
        "achieved_threshold_rpm": float(achieved),
        "residual_rpm": float(achieved - target),
    }


def threshold_elasticity(
    volume_ml: float,
    *,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    relative_step: float = 1e-3,
    nq: int = 48,
) -> pd.DataFrame:
    """Central-difference local elasticities d ln(n_g) / d ln(x)."""
    base = {"volume_ml": float(volume_ml), "rin_m": float(rin_m), "a_m": float(a_m)}
    if any(v <= 0 for v in base.values()):
        raise ValueError("volume and geometry must be positive")
    h = abs(float(relative_step))
    if not (0 < h < 0.2):
        raise ValueError("relative_step must be in (0, 0.2)")
    rows = []
    for name, x0 in base.items():
        plus = dict(base); minus = dict(base)
        plus[name] = x0 * (1 + h); minus[name] = x0 * (1 - h)
        ng_plus = threshold(plus["volume_ml"], rin=plus["rin_m"], a=plus["a_m"], nq=nq)
        ng_minus = threshold(minus["volume_ml"], rin=minus["rin_m"], a=minus["a_m"], nq=nq)
        derivative = (ng_plus - ng_minus) / (2 * h * x0)
        ng0 = threshold(base["volume_ml"], rin=base["rin_m"], a=base["a_m"], nq=nq)
        elasticity = derivative * x0 / ng0
        rows.append({
            "parameter": name,
            "base_value": x0,
            "threshold_rpm": ng0,
            "d_threshold_dx": float(derivative),
            "elasticity": float(elasticity),
        })
    return pd.DataFrame(rows)


def design_space(
    *,
    volumes_ml: Sequence[float],
    rin_values_m: Sequence[float],
    a_values_m: Sequence[float],
    target_threshold_rpm: float | None = None,
    nq: int = 40,
    max_points: int = 400,
) -> pd.DataFrame:
    """Evaluate a bounded geometry/volume design grid using the full threshold solver."""
    points = len(volumes_ml) * len(rin_values_m) * len(a_values_m)
    if points <= 0 or points > int(max_points):
        raise ValueError(f"design grid must contain 1..{max_points} points")
    rows: list[dict[str, float]] = []
    for volume in volumes_ml:
        for rin in rin_values_m:
            for a in a_values_m:
                ng = threshold(float(volume), rin=float(rin), a=float(a), nq=nq)
                nc = critical_speed(float(rin), float(a))
                row = {
                    "V_mL": float(volume),
                    "R_in_m": float(rin),
                    "a_m": float(a),
                    "critical_speed_rpm": float(nc),
                    "threshold_rpm": float(ng),
                    "threshold_minus_critical_rpm": float(ng - nc),
                }
                if target_threshold_rpm is not None:
                    row["target_error_rpm"] = float(ng - float(target_threshold_rpm))
                    row["abs_target_error_rpm"] = abs(row["target_error_rpm"])
                rows.append(row)
    frame = pd.DataFrame(rows)
    if target_threshold_rpm is not None:
        frame = frame.sort_values("abs_target_error_rpm", kind="stable").reset_index(drop=True)
    return frame


def experiment_scan_plan(
    predicted_threshold_rpm: float,
    *,
    coarse_span_rpm: float = 40.0,
    coarse_step_rpm: float = 10.0,
    fine_span_rpm: float = 8.0,
    fine_step_rpm: float = 2.0,
) -> pd.DataFrame:
    """Generate a deterministic two-resolution rpm scan around a predicted threshold."""
    center = float(predicted_threshold_rpm)
    if center <= 0:
        raise ValueError("predicted threshold must be positive")
    if coarse_step_rpm <= 0 or fine_step_rpm <= 0 or coarse_span_rpm <= 0 or fine_span_rpm <= 0:
        raise ValueError("scan spans and steps must be positive")
    coarse = np.arange(center - coarse_span_rpm, center + coarse_span_rpm + 0.5 * coarse_step_rpm, coarse_step_rpm)
    fine = np.arange(center - fine_span_rpm, center + fine_span_rpm + 0.5 * fine_step_rpm, fine_step_rpm)
    rows = []
    for value in coarse:
        if value > 0:
            rows.append({"n_rpm": float(value), "phase": "coarse-bracket"})
    for value in fine:
        if value > 0:
            rows.append({"n_rpm": float(value), "phase": "fine-threshold"})
    frame = pd.DataFrame(rows).drop_duplicates(subset=["n_rpm"], keep="last").sort_values("n_rpm").reset_index(drop=True)
    frame["offset_from_prediction_rpm"] = frame["n_rpm"] - center
    return frame


def research_questions() -> list[dict[str, str]]:
    return [
        {"domain": "physics", "question": "How do rotation, gravity, finite liquid volume and U-tube geometry reorganize the equilibrium potential landscape and produce a finite-volume threshold?"},
        {"domain": "interface physics", "question": "How do surface tension and contact-angle assumptions modify the free-energy competition between connected and separated configurations?"},
        {"domain": "numerical physics", "question": "How converged are the 3-D capacity and threshold predictions with respect to quadrature and root-solving choices?"},
        {"domain": "engineering design", "question": "Which geometry and operating parameters create a desired threshold while preserving adequate separation from the angular bifurcation?"},
        {"domain": "experimental engineering", "question": "Which parameters and measurements dominate uncertainty, and where should the next experimental samples be placed to reduce ambiguity most efficiently?"},
    ]
