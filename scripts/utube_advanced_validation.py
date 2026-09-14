#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_utube_advanced as a
    import physical_lab_utube_experiment as u
    import physical_lab_utube_robust_ui as r

    groups = a.dimensionless_groups(260.0)
    for key in ["rotational_froude", "bond_tube", "rotational_weber", "capillary_length_m", "ell_over_capillary_length"]:
        require(key in groups and groups[key] > 0, f"missing/invalid dimensionless diagnostic: {key}")

    ng = u.threshold(3.0, nq=40)
    below = a.operating_state(3.0, ng - 15.0, nq=40)
    near = a.operating_state(3.0, ng, nq=40)
    above = a.operating_state(3.0, ng + 15.0, nq=40)
    require(near["regime"] == "near-finite-volume-threshold", "threshold regime classification failed")
    require(below["threshold_margin_rpm"] < 0 and above["threshold_margin_rpm"] > 0, "threshold margin sign failed")

    inv = a.inverse_geometry_design(ng, 3.0, solve_for="rin_m", bounds=(0.010, 0.025), nq=40)
    require(abs(inv["achieved_threshold_rpm"] - ng) < 1e-6, "inverse geometry did not reproduce target threshold")

    elasticity = a.threshold_elasticity(3.0, nq=40)
    require(set(elasticity["parameter"]) == {"volume_ml", "rin_m", "a_m"}, "elasticity parameter set changed")
    require(elasticity["elasticity"].notna().all(), "elasticity contains invalid values")

    grid = a.design_space(volumes_ml=[2.0, 3.0], rin_values_m=[0.013, 0.017], a_values_m=[0.0065, 0.0080], target_threshold_rpm=250.0, nq=32)
    require(len(grid) == 8, "design-space row count mismatch")
    require("abs_target_error_rpm" in grid.columns, "target design ranking missing")
    require(grid["abs_target_error_rpm"].is_monotonic_increasing, "design-space ranking is not stable")

    robust = a.robust_design_space(volumes_ml=[2.8, 3.2], rin_values_m=[0.0145, 0.0155], a_values_m=[0.0072, 0.0078], volume_tolerance_ml=0.05, rin_tolerance_m=0.0001, a_tolerance_m=0.0001, target_threshold_rpm=250.0, nq=24)
    require(len(robust) == 8, "robust-design nominal row count mismatch")
    require((robust["corner_count"] == 8).all(), "robust-design corner count changed")
    require((robust["threshold_span_rpm"] >= 0).all(), "robust threshold span cannot be negative")
    require(np.isfinite(robust["separation_floor_rpm"]).all(), "robust separation floor contains non-finite values")
    require(np.isfinite(robust["worst_abs_target_error_rpm"]).all(), "worst target error contains non-finite values")

    pareto = a.pareto_robust_design(robust)
    require("pareto" in pareto.columns, "Pareto membership column missing")
    require(bool(pareto["pareto"].any()), "robust design must expose at least one non-dominated candidate")
    require(len(pareto) == len(robust), "Pareto marking changed source row count")

    plan = a.experiment_scan_plan(250.0, coarse_span_rpm=20.0, coarse_step_rpm=10.0, fine_span_rpm=4.0, fine_step_rpm=2.0)
    require(len(plan) > 5, "experiment scan plan too small")
    require(set(plan["phase"]) == {"coarse-bracket", "fine-threshold"}, "scan phases missing")
    require(plan["n_rpm"].is_monotonic_increasing, "scan plan is not ordered")

    adaptive = a.adaptive_threshold_plan([{"n_rpm": 240.0, "state": "below"}, {"n_rpm": 260.0, "state": "above"}], 250.0, target_bracket_rpm=2.0)
    require(adaptive["status"] == "empirical-bracket-refinement", "adaptive planner did not detect a valid wide bracket")
    require(adaptive["next_measurements_rpm"] == [250.0], "adaptive planner did not bisect the empirical bracket")
    reached = a.adaptive_threshold_plan([{"n_rpm": 249.0, "state": "below"}, {"n_rpm": 250.0, "state": "above"}], 250.0, target_bracket_rpm=2.0)
    require(reached["status"] == "target-bracket-reached", "adaptive planner did not stop at requested bracket width")
    require(reached["next_measurements_rpm"] == [], "adaptive planner should not invent another point after target bracket is reached")

    matrix = a.verification_requirements(target_threshold_rpm=250.0, threshold_tolerance_rpm=5.0, minimum_separation_rpm=10.0, maximum_numerical_change_rpm=0.25)
    require(len(matrix) == 4, "verification template count changed")
    require(set(matrix["requirement_id"]) == {"UTUBE-REQ-THRESHOLD", "UTUBE-REQ-SEPARATION", "UTUBE-REQ-NUMERICS", "UTUBE-REQ-VALIDATION"}, "verification requirement IDs changed")
    require(matrix["statement"].str.contains("shall", case=False).all(), "common Requirements layer requires normative 'shall' statements")
    require(set(matrix["verification_method"]).issubset({"analysis", "test", "inspection", "demonstration"}), "unsupported verification method emitted")
    require(matrix["verification_activity"].str.len().gt(0).all(), "verification activity missing")
    require(matrix["success_criteria"].str.len().gt(0).all(), "verification success criteria missing")

    # Threshold digital twin should reproduce a self-generated noiseless model series.
    volumes = [2.2, 2.8, 3.4, 4.0]
    observed = [u.threshold(v, nq=32) for v in volumes]
    twin = r.compare_threshold_twin(volumes, observed, nq=32)
    require(len(twin["frame"]) == len(volumes), "threshold twin row count mismatch")
    require(twin["metrics"]["rmse_rpm"] < 1e-9, "self-consistent threshold twin should have near-zero residual")
    require(abs(twin["metrics"]["affine_scale"] - 1.0) < 1e-9, "self-consistent affine discrepancy scale should be one")
    require(abs(twin["metrics"]["affine_offset_rpm"]) < 1e-8, "self-consistent affine discrepancy offset should be zero")
    suggestions = r.suggest_threshold_remeasurements(twin, count=2)
    require(len(suggestions) == 2, "threshold twin should expose bounded remeasurement priorities")
    require(all("V_mL" in item and "priority_score" in item for item in suggestions), "remeasurement priority contract changed")

    # Recover a known first-order apparatus lag from synthetic command/measurement data.
    time_s = np.linspace(0.0, 12.0, 121)
    command = np.where(time_s < 2.0, 100.0, np.where(time_s < 7.0, 280.0, 180.0))
    true_tau = 1.35
    measured = r.first_order_rpm_response(time_s, command, true_tau, initial_rpm=100.0)
    lag = r.fit_first_order_rpm_lag(time_s, command, measured, tau_bounds_s=(0.2, 5.0), grid_points=800)
    require(abs(lag["tau_s"] - true_tau) / true_tau < 0.02, "dynamic twin failed to recover synthetic time constant")
    require(lag["rmse_rpm"] < 0.5, "dynamic twin synthetic RMSE unexpectedly large")
    require(lag["r2"] is not None and lag["r2"] > 0.999, "dynamic twin synthetic fit quality unexpectedly low")
    require(abs(lag["settling_time_2pct_s"] - 4.0 * lag["tau_s"]) < 1e-12, "settling-time diagnostic changed")
    require("not be interpreted as viscosity" in lag["boundary"].lower(), "dynamic twin evidence boundary weakened")
    require("not viscosity" in r.UTUBE_TWIN_BOUNDARY.lower(), "U-tube twin boundary weakened")

    questions = a.research_questions()
    require(any(q["domain"] == "physics" for q in questions), "physics research question missing")
    require(any(q["domain"] == "engineering design" for q in questions), "engineering research question missing")
    require("computational proposals" in a.BOUNDARY, "engineering evidence boundary weakened")
    require("requirement compliance" in a.BOUNDARY, "requirements boundary weakened")
    require("Numerical convergence" in u.BOUNDARY, "base U-tube boundary unexpectedly changed")

    print("PASS: U-tube advanced physics, robust design, verification, threshold twin and reduced-order RPM dynamics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
