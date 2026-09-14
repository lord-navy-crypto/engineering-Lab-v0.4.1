"""Advanced physics and engineering tools for the rotating U-tube experiment.

These utilities build on the deterministic U-tube model without changing its
physical equations. They expose dimensionless scaling, operating-state
classification, inverse geometry design, bounded design-space exploration,
local threshold elasticity, tolerance-aware robust design, Pareto screening,
adaptive experiment planning and verification requirement templates.

Important: dimensionless groups are scaling diagnostics, not replacement
criteria for the full 3-D model. Design recommendations are computational
proposals, not experimental evidence or hardware safety certification.
"""
from __future__ import annotations

import itertools
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from physical_lab_tradeoff_analysis import pareto_frontier
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
ROBUST_DESIGN_SCHEMA = "engineering-lab-utube-robust-design/v1"
ADAPTIVE_PLAN_SCHEMA = "engineering-lab-utube-adaptive-threshold-plan/v1"
VERIFICATION_TEMPLATE_SCHEMA = "engineering-lab-utube-verification-template/v1"

BOUNDARY = (
    "Advanced U-tube engineering tools derive from the existing deterministic 3-D model. "
    "Dimensionless groups summarize competing scales but do not replace the solved geometry. "
    "Inverse-design, robust-design, Pareto and experiment-planning candidates are computational proposals only; "
    "they do not establish manufacturability, safety, calibration, experimental validity, requirement compliance or certification."
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


def _tolerance_values(nominal: float, tolerance: float) -> list[float]:
    nominal = float(nominal)
    tolerance = abs(float(tolerance))
    values = [nominal] if tolerance == 0 else [nominal - tolerance, nominal + tolerance]
    if any((not np.isfinite(v) or v <= 0) for v in values):
        raise ValueError("tolerance envelope must remain finite and positive")
    return values


def robust_design_space(
    *,
    volumes_ml: Sequence[float],
    rin_values_m: Sequence[float],
    a_values_m: Sequence[float],
    volume_tolerance_ml: float = 0.05,
    rin_tolerance_m: float = 0.0002,
    a_tolerance_m: float = 0.0001,
    target_threshold_rpm: float | None = None,
    nq: int = 32,
    max_points: int = 120,
) -> pd.DataFrame:
    """Evaluate deterministic tolerance corners around each nominal U-tube design.

    This is a bounded worst-case screening calculation. It is not a probability
    distribution, process-capability study, or complete manufacturing tolerance model.
    """
    points = len(volumes_ml) * len(rin_values_m) * len(a_values_m)
    if points <= 0 or points > int(max_points):
        raise ValueError(f"robust design grid must contain 1..{max_points} nominal points")
    tolerances = [float(volume_tolerance_ml), float(rin_tolerance_m), float(a_tolerance_m)]
    if any((not np.isfinite(v) or v < 0) for v in tolerances):
        raise ValueError("tolerances must be finite and non-negative")
    target = None if target_threshold_rpm is None else float(target_threshold_rpm)
    if target is not None and (not np.isfinite(target) or target <= 0):
        raise ValueError("target_threshold_rpm must be positive when supplied")

    rows: list[dict[str, Any]] = []
    for volume, rin, a in itertools.product(volumes_ml, rin_values_m, a_values_m):
        volume = float(volume); rin = float(rin); a = float(a)
        if min(volume, rin, a) <= 0:
            raise ValueError("nominal volume and geometry values must be positive")
        nominal_ng = float(threshold(volume, rin=rin, a=a, nq=nq))
        nominal_nc = float(critical_speed(rin, a))
        threshold_values: list[float] = []
        separation_values: list[float] = []
        for v_case, r_case, a_case in itertools.product(
            _tolerance_values(volume, volume_tolerance_ml),
            _tolerance_values(rin, rin_tolerance_m),
            _tolerance_values(a, a_tolerance_m),
        ):
            ng = float(threshold(v_case, rin=r_case, a=a_case, nq=nq))
            nc = float(critical_speed(r_case, a_case))
            threshold_values.append(ng)
            separation_values.append(ng - nc)
        arr = np.asarray(threshold_values, dtype=float)
        row: dict[str, Any] = {
            "schema": ROBUST_DESIGN_SCHEMA,
            "V_mL": volume,
            "R_in_m": rin,
            "a_m": a,
            "nominal_threshold_rpm": nominal_ng,
            "nominal_critical_speed_rpm": nominal_nc,
            "nominal_separation_rpm": nominal_ng - nominal_nc,
            "threshold_min_rpm": float(arr.min()),
            "threshold_max_rpm": float(arr.max()),
            "threshold_mean_corner_rpm": float(arr.mean()),
            "threshold_span_rpm": float(arr.max() - arr.min()),
            "separation_floor_rpm": float(min(separation_values)),
            "corner_count": int(len(arr)),
            "volume_tolerance_ml": abs(float(volume_tolerance_ml)),
            "rin_tolerance_m": abs(float(rin_tolerance_m)),
            "a_tolerance_m": abs(float(a_tolerance_m)),
        }
        if target is not None:
            row["nominal_abs_target_error_rpm"] = abs(nominal_ng - target)
            row["worst_abs_target_error_rpm"] = float(max(abs(x - target) for x in threshold_values))
        rows.append(row)
    out = pd.DataFrame(rows)
    sort_columns = [c for c in ["worst_abs_target_error_rpm", "threshold_span_rpm"] if c in out.columns]
    if sort_columns:
        out = out.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    return out


def pareto_robust_design(
    frame: pd.DataFrame,
    *,
    x: str = "worst_abs_target_error_rpm",
    x_goal: str = "min",
    y: str = "threshold_span_rpm",
    y_goal: str = "min",
) -> pd.DataFrame:
    """Mark non-dominated robust-design candidates using the common Trade-off engine."""
    if frame.empty:
        return frame.assign(pareto=pd.Series(dtype=bool))
    frontier = pareto_frontier(frame, x=x, x_goal=x_goal, y=y, y_goal=y_goal)
    marked = frame.copy().reset_index(drop=True)
    marked["pareto"] = False
    indices = [int(i) for i in frontier.loc[frontier["pareto"], "source_index"].tolist()]
    valid = [i for i in indices if 0 <= i < len(marked)]
    if valid:
        marked.loc[valid, "pareto"] = True
    return marked


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


def adaptive_threshold_plan(
    observations: Sequence[Mapping[str, Any]],
    predicted_threshold_rpm: float,
    *,
    target_bracket_rpm: float = 2.0,
    exploration_step_rpm: float = 5.0,
) -> dict[str, Any]:
    """Propose the next threshold measurement from explicit below/above observations.

    ``below`` means the observed state remained below the chosen transition criterion;
    ``above`` means it was above that criterion. The bracket is empirical bookkeeping,
    not a confidence interval or hardware safety bound.
    """
    predicted = float(predicted_threshold_rpm)
    resolution = float(target_bracket_rpm)
    step = float(exploration_step_rpm)
    if not np.isfinite(predicted) or predicted <= 0:
        raise ValueError("predicted_threshold_rpm must be positive")
    if not np.isfinite(resolution) or resolution <= 0 or not np.isfinite(step) or step <= 0:
        raise ValueError("target bracket and exploration step must be positive")
    below: list[float] = []
    above: list[float] = []
    observed: list[float] = []
    for item in observations:
        speed = float(item.get("n_rpm"))
        state = str(item.get("state") or "").strip().lower()
        if not np.isfinite(speed) or speed <= 0:
            raise ValueError("observed n_rpm values must be finite and positive")
        if state not in {"below", "above"}:
            raise ValueError("observation state must be 'below' or 'above'")
        observed.append(speed)
        (below if state == "below" else above).append(speed)

    lo = max(below) if below else None
    hi = min(above) if above else None
    status = "model-guided-exploration"
    next_points: list[float] = []
    bracket_width = None
    if lo is not None and hi is not None and lo < hi:
        bracket_width = hi - lo
        if bracket_width <= resolution:
            status = "target-bracket-reached"
        else:
            status = "empirical-bracket-refinement"
            next_points = [0.5 * (lo + hi)]
    elif lo is not None and hi is not None and lo >= hi:
        status = "inconsistent-observations"
    elif lo is not None:
        candidate = predicted if predicted > lo else lo + step
        next_points = [candidate]
    elif hi is not None:
        candidate = predicted if predicted < hi else max(1e-9, hi - step)
        next_points = [candidate]
    else:
        next_points = [predicted]

    deduped: list[float] = []
    for value in next_points:
        if all(abs(value - seen) > 1e-9 for seen in observed) and all(abs(value - seen) > 1e-9 for seen in deduped):
            deduped.append(float(value))
    return {
        "schema": ADAPTIVE_PLAN_SCHEMA,
        "status": status,
        "predicted_threshold_rpm": predicted,
        "empirical_lower_rpm": lo,
        "empirical_upper_rpm": hi,
        "empirical_bracket_width_rpm": bracket_width,
        "target_bracket_rpm": resolution,
        "next_measurements_rpm": deduped,
        "observation_count": len(observed),
        "boundary": (
            "Adaptive threshold planning uses declared below/above observations to refine an empirical bracket. "
            "The bracket is not a statistical confidence interval, a safety limit, or proof of the model threshold."
        ),
    }


def verification_requirements(
    *,
    target_threshold_rpm: float = 250.0,
    threshold_tolerance_rpm: float = 5.0,
    minimum_separation_rpm: float = 10.0,
    maximum_numerical_change_rpm: float = 0.25,
) -> pd.DataFrame:
    """Return registerable U-tube requirement templates for the common verification layer."""
    target = float(target_threshold_rpm)
    tol = abs(float(threshold_tolerance_rpm))
    separation = float(minimum_separation_rpm)
    numerical = abs(float(maximum_numerical_change_rpm))
    if target <= 0 or tol <= 0 or separation < 0 or numerical <= 0:
        raise ValueError("verification requirement limits are invalid")
    rows = [
        {
            "schema": VERIFICATION_TEMPLATE_SCHEMA,
            "requirement_id": "UTUBE-REQ-THRESHOLD",
            "statement": f"The selected U-tube design shall achieve a predicted finite-volume threshold within ±{tol:g} rpm of the {target:g} rpm target.",
            "verification_method": "analysis",
            "verification_activity": "Evaluate the deterministic 3-D finite-volume threshold model at the selected design point.",
            "success_criteria": f"abs(n_g - {target:g} rpm) <= {tol:g} rpm",
            "rationale": "Controls target placement of the finite-volume threshold in the declared model.",
        },
        {
            "schema": VERIFICATION_TEMPLATE_SCHEMA,
            "requirement_id": "UTUBE-REQ-SEPARATION",
            "statement": f"The selected U-tube design shall preserve at least {separation:g} rpm separation between n_g and the angular bifurcation n_c across the declared tolerance envelope.",
            "verification_method": "analysis",
            "verification_activity": "Evaluate n_g - n_c at all deterministic tolerance-corner cases used by robust design screening.",
            "success_criteria": f"min_corner(n_g - n_c) >= {separation:g} rpm",
            "rationale": "Prevents target-threshold tuning from silently collapsing the two distinct model thresholds.",
        },
        {
            "schema": VERIFICATION_TEMPLATE_SCHEMA,
            "requirement_id": "UTUBE-REQ-NUMERICS",
            "statement": f"The U-tube threshold computation shall demonstrate adjacent quadrature-order change no greater than {numerical:g} rpm over the declared verification orders.",
            "verification_method": "analysis",
            "verification_activity": "Run the existing quadrature convergence study and compare adjacent-order n_g predictions.",
            "success_criteria": f"max(abs(delta n_g between adjacent declared orders)) <= {numerical:g} rpm",
            "rationale": "Separates numerical convergence evidence from physical validation evidence.",
        },
        {
            "schema": VERIFICATION_TEMPLATE_SCHEMA,
            "requirement_id": "UTUBE-REQ-VALIDATION",
            "statement": "The project shall retain an explicit theory-to-experiment threshold comparison with residuals before any project review treats the model as experimentally supported.",
            "verification_method": "test",
            "verification_activity": "Compare measured threshold brackets against model n_g predictions and retain residual evidence in the Project.",
            "success_criteria": "A project evidence item contains paired theory/experiment threshold values and explicit residuals; acceptance limits remain project-defined.",
            "rationale": "Prevents numerical verification or design-space screening from being substituted for experimental validation.",
        },
    ]
    return pd.DataFrame(rows)


def research_questions() -> list[dict[str, str]]:
    return [
        {"domain": "physics", "question": "How do rotation, gravity, finite liquid volume and U-tube geometry reorganize the equilibrium potential landscape and produce a finite-volume threshold?"},
        {"domain": "interface physics", "question": "How do surface tension and contact-angle assumptions modify the free-energy competition between connected and separated configurations?"},
        {"domain": "numerical physics", "question": "How converged are the 3-D capacity and threshold predictions with respect to quadrature and root-solving choices?"},
        {"domain": "engineering design", "question": "Which geometry and operating parameters create a desired threshold while preserving adequate separation from the angular bifurcation?"},
        {"domain": "experimental engineering", "question": "Which parameters and measurements dominate uncertainty, and where should the next experimental samples be placed to reduce ambiguity most efficiently?"},
    ]
