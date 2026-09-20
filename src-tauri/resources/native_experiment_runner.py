#!/usr/bin/env python3
"""Serverless native experiment adapters for Engineering Lab.

stdin: JSON object of parameters.
stdout: exactly one JSON result object.
No HTTP server, Streamlit, browser, or iframe is involved.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))

import numpy as np

SCHEMA = "engineering-lab-native-experiment-result/v1"
HC_EV_M = 1.2398419843320026e-6
E_REST_GEV = 0.00051099895


def f(p: dict[str, Any], name: str, default: float, lo: float | None = None, hi: float | None = None) -> float:
    try:
        value = float(p.get(name, default))
    except (TypeError, ValueError):
        value = float(default)
    if not math.isfinite(value):
        value = float(default)
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def i(p: dict[str, Any], name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        value = int(float(p.get(name, default)))
    except (TypeError, ValueError):
        value = int(default)
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def b(p: dict[str, Any], name: str, default: bool = False) -> bool:
    value = p.get(name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def ds(values: Any, limit: int = 900) -> list[float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size <= limit:
        return [float(x) for x in arr]
    idx = np.linspace(0, arr.size - 1, limit).astype(int)
    return [float(x) for x in arr[idx]]


def xy_series(
    series_id: str,
    label: str,
    x: Any,
    y: Any,
    *,
    x_label: str,
    y_label: str,
    chart: str = "line",
) -> dict[str, Any]:
    xa = np.asarray(x, dtype=float).reshape(-1)
    ya = np.asarray(y, dtype=float).reshape(-1)
    n = min(len(xa), len(ya))
    xa, ya = xa[:n], ya[:n]
    mask = np.isfinite(xa) & np.isfinite(ya)
    xa, ya = xa[mask], ya[mask]
    if len(xa) > 900:
        idx = np.linspace(0, len(xa) - 1, 900).astype(int)
        xa, ya = xa[idx], ya[idx]
    return {
        "id": series_id,
        "label": label,
        "chart": chart,
        "xLabel": x_label,
        "yLabel": y_label,
        "x": [float(v) for v in xa],
        "y": [float(v) for v in ya],
    }


def clean(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def result(experiment_id: str, backend: str, parameters: dict[str, Any], metrics: dict[str, Any], series: list[dict[str, Any]], boundary: str, tables: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return clean({
        "schema": SCHEMA,
        "experimentId": experiment_id,
        "backend": backend,
        "parameters": parameters,
        "metrics": metrics,
        "series": series,
        "tables": tables or [],
        "boundary": boundary,
    })


def numerical_methods(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from numerical_lab.core import Method, ReferenceBackend, scan_sine, summarize_scan
    method = Method(str(p.get("method", "range_reduced")))
    dtype = str(p.get("dtype", "float64"))
    backend = ReferenceBackend(str(p.get("referenceBackend", "mpmath")))
    digits = i(p, "referencePrecisionDigits", 80, 20, 200)
    tol = f(p, "toleranceMultiplier", 8.0, 0.1, 1000.0)
    max_terms = i(p, "maxTerms", 120, 1, 500)
    x_min = f(p, "xMin", -8.0, -100.0, 100.0)
    x_max = f(p, "xMax", 8.0, -100.0, 100.0)
    if x_max <= x_min:
        raise ValueError("x maximum must exceed x minimum")
    points = i(p, "points", 401, 21, 5001)
    x_values = np.linspace(x_min, x_max, points)
    out = scan_sine(
        x_values, method=method, dtype=dtype, tolerance_multiplier=tol,
        max_terms=max_terms, reference_backend=backend,
        reference_precision_digits=digits,
    )
    summary = summarize_scan(out)
    rows = []
    keys = list(out)
    for idx in range(points):
        row = {}
        for key in keys:
            value = np.asarray(out[key], dtype=object)[idx]
            row[key] = clean(value)
        rows.append(row)
    return result(
        "numerical-methods",
        "pinned-numerical_lab.scan_sine",
        {
            "method": method.value, "dtype": dtype, "referenceBackend": backend.value,
            "referencePrecisionDigits": digits, "toleranceMultiplier": tol,
            "maxTerms": max_terms, "xMin": x_min, "xMax": x_max, "points": points,
        },
        {k: clean(v) for k, v in summary.items()},
        [
            xy_series("approximation", "Taylor approximation", out["x"], out["approximation"], x_label="x (rad)", y_label="sin(x)"),
            xy_series("reference", "reference", out["x"], out["reference"], x_label="x (rad)", y_label="sin(x)"),
            xy_series("absolute-error", "absolute error", out["x"], out["absolute_error"], x_label="x (rad)", y_label="absolute error"),
            xy_series("normalized-error", "normalized error", out["x"], out["normalized_error"], x_label="x (rad)", y_label="error / allowed error"),
            xy_series("terms-used", "terms used", out["x"], out["terms_used"], x_label="x (rad)", y_label="terms"),
            xy_series("cancellation", "cancellation ratio", out["x"], out["cancellation_ratio"], x_label="x (rad)", y_label="cancellation ratio"),
        ],
        "Pinned Numerical Error Analysis Studio core. Reliability combines stopping, reference accuracy and cancellation diagnostics; a converged Taylor term alone is not sufficient evidence of numerical accuracy.",
        [{"id":"scan","label":"Complete parameter scan","rows":rows}],
    )

def ising_monte_carlo(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from ising_lab.core import IsingParams, simulate
    params = IsingParams(
        size=i(p, "size", 24, 4, 256),
        coupling=f(p, "coupling", 1.0, -10.0, 10.0),
        field=f(p, "field", 0.0, -10.0, 10.0),
        temperature=f(p, "temperature", 2.269, 0.01, 20.0),
        dimension=i(p, "dimension", 2, 1, 2),
    )
    method = str(p.get("scanMethod", "wolff"))
    out = simulate(
        params, method=method,
        equilibration_sweeps=i(p, "equilibrationSweeps", 400, 0, 100000),
        measurement_sweeps=i(p, "measurementSweeps", 800, 1, 100000),
        measure_every=i(p, "measureEvery", 1, 1, 1000),
        initial=str(p.get("initialCondition", "random")),
        seed=i(p, "seed", 2026, 0, 2147483647),
        record_every=i(p, "recordEvery", 10, 1, 1000),
    )
    scalar = {k: clean(v) for k,v in out.items() if isinstance(v,(str,int,float,bool,np.integer,np.floating))}
    work = np.asarray(out["trajectory_work_units"],dtype=float)
    energy = np.asarray(out["trajectory_energy"],dtype=float)
    mag = np.asarray(out["trajectory_magnetization"],dtype=float)
    final = np.asarray(out["final_config"])
    return result(
        "ising-monte-carlo",
        "pinned-ising_lab.simulate",
        clean({
            "dimension": params.dimension, "size": params.size, "coupling": params.coupling,
            "field": params.field, "temperature": params.temperature, "method": method,
            "equilibrationSweeps": p.get("equilibrationSweeps",400),
            "measurementSweeps": p.get("measurementSweeps",800),
            "measureEvery": p.get("measureEvery",1),
            "initialCondition": p.get("initialCondition","random"),
            "seed": p.get("seed",2026),
        }),
        scalar,
        [
            xy_series("energy","energy per site",work,energy,x_label="work units",y_label="E/N"),
            xy_series("magnetization","magnetization per site",work,mag,x_label="work units",y_label="M/N"),
        ],
        "Pinned Ising Monte Carlo Lab core. Finite-size, equilibration, autocorrelation, update-method compatibility and effective sample size must be considered before interpreting thermodynamic behavior.",
        [{"id":"final-config","label":"Final lattice configuration","rows":[{"shape":list(final.shape),"meanSpin":float(np.mean(final)),"minSpin":int(np.min(final)),"maxSpin":int(np.max(final))}]}],
    )

def random_walk(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from rw_mc_studio.random_walk import simulate_endpoints, summarize_endpoints, simulate_trajectory, theoretical_msd, theoretical_mean_radius
    dim = i(p, "dimension", 2, 1, 50)
    steps = i(p, "steps", 1000, 1, 1000000)
    walkers = i(p, "walkers", 10000, 1, 1000000)
    seed = i(p, "seed", 12345, 0, 2147483647)
    model = str(p.get("stepModel", "fixed"))
    if model == "uniform":
        p1 = f(p, "uniformA", 0.5, 0.0, 100.0)
        p2 = f(p, "uniformB", 1.5, 0.0001, 100.0)
        if p2 <= p1: raise ValueError("Uniform upper bound must exceed lower bound")
    else:
        p1 = f(p, "fixedStep", 1.0, 0.0001, 100.0); p2 = None
    endpoints, meta = simulate_endpoints(dim,steps,walkers,model,p1,p2,seed=seed,return_metadata=True)
    summary = summarize_endpoints(endpoints)
    traj = simulate_trajectory(dim,min(steps,i(p,"trajectorySteps",500,1,100000)),model,p1,p2,seed=seed+1)
    radii=np.linalg.norm(endpoints,axis=1)
    series=[
        xy_series("radius-samples","endpoint radius",range(len(radii)),radii,x_label="walker",y_label="radius"),
    ]
    if dim>=2:
        series.append(xy_series("trajectory","sample trajectory",traj[:,0],traj[:,1],x_label="x",y_label="y",chart="scatter"))
    return result(
        "random-walk-monte-carlo",
        "pinned-rw_mc_studio.simulate_endpoints",
        {"dimension":dim,"steps":steps,"walkers":walkers,"seed":seed,"stepModel":model,"p1":p1,"p2":p2},
        {
            **{k:clean(v) for k,v in summary.items() if isinstance(v,(str,int,float,bool,np.integer,np.floating))},
            "theoreticalMSD": theoretical_msd(steps,model,p1,p2),
            "theoreticalMeanRadius": theoretical_mean_radius(dim,steps,model,p1,p2),
            "engine": meta.get("engine"),
        },
        series,
        "Pinned Random Walk and Monte Carlo Simulation Studio core. Ensemble confidence intervals describe finite Monte Carlo sampling; they do not validate the pseudorandom generator or asymptotic formulas outside their assumptions.",
        [{"id":"endpoint-summary","label":"Endpoint summary","rows":[clean(summary)]}],
    )

def _rk4(rhs, state: np.ndarray, t: float, dt: float) -> np.ndarray:
    k1 = np.asarray(rhs(t, state), float)
    k2 = np.asarray(rhs(t + 0.5 * dt, state + 0.5 * dt * k1), float)
    k3 = np.asarray(rhs(t + 0.5 * dt, state + 0.5 * dt * k2), float)
    k4 = np.asarray(rhs(t + dt, state + dt * k3), float)
    return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0


def nonlinear_chaos(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from chaos_lab.core import DoublePendulumParams, simulate_double_pendulum, double_pendulum_energy, double_pendulum_cartesian
    params=DoublePendulumParams(
        mass1=f(p,"mass1",1.0,.01,100.0), mass2=f(p,"mass2",1.0,.01,100.0),
        length1=f(p,"length1",1.0,.01,100.0), length2=f(p,"length2",1.0,.01,100.0),
        gravity=f(p,"gravity",9.81,.01,100.0), damping=f(p,"damping",.05,0.0,20.0),
    )
    initial=np.asarray([
        f(p,"theta1",1.2,-2*math.pi,2*math.pi), f(p,"omega1",0.0,-100.0,100.0),
        f(p,"theta2",1.0,-2*math.pi,2*math.pi), f(p,"omega2",0.0,-100.0,100.0),
    ])
    duration=f(p,"duration",40.0,.1,1000.0); dt=f(p,"dt",.005,1e-5,1.0)
    times,states=simulate_double_pendulum(initial,params,duration=duration,dt=dt)
    energy=double_pendulum_energy(states,params); cart=double_pendulum_cartesian(states,params)
    drift=float(np.max(np.abs(energy-energy[0]))/max(abs(float(energy[0])),np.finfo(float).tiny))
    return result(
        "nonlinear-chaos",
        "pinned-chaos_lab.simulate_double_pendulum",
        clean({"mass1":params.mass1,"mass2":params.mass2,"length1":params.length1,"length2":params.length2,"gravity":params.gravity,"damping":params.damping,"initial":initial,"duration":duration,"dt":dt}),
        {"relativeEnergyDrift":drift,"samples":len(times),"finalTheta1":float(states[-1,0]),"finalTheta2":float(states[-1,2])},
        [
            xy_series("theta1","theta1",times,states[:,0],x_label="time",y_label="angle (rad)"),
            xy_series("theta2","theta2",times,states[:,2],x_label="time",y_label="angle (rad)"),
            xy_series("phase1","upper-arm phase",states[:,0],states[:,1],x_label="theta1",y_label="omega1",chart="scatter"),
            xy_series("energy","total mechanical energy",times,energy,x_label="time",y_label="energy"),
        ],
        "Pinned Nonlinear Dynamics & Chaos Lab double-pendulum core. Apparent irregularity, flip maps and finite-time Lyapunov estimates require timestep/convergence checks before being interpreted as chaos evidence.",
        [{"id":"cartesian-endpoint","label":"Final Cartesian state","rows":[{"x1":float(cart["x1"][-1]),"y1":float(cart["y1"][-1]),"x2":float(cart["x2"][-1]),"y2":float(cart["y2"][-1])}]}],
    )

def oscillation(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from oscillation_lab.core import OscillatorParams, simulate_fixed, linear_energy, energy_balance_diagnostic
    params=OscillatorParams(
        mass=f(p,"mass",1.0,.001,1000.0),
        omega0=f(p,"omega0",2*math.pi,.001,1000.0),
        gamma=f(p,"gamma",.1,0.0,100.0),
        force_amplitude=f(p,"force",1.0,0.0,1000.0),
        force_frequency=f(p,"driveOmega",6.0,0.0,1000.0),
    )
    initial=np.asarray([f(p,"x0",1.0,-1000.0,1000.0),f(p,"v0",0.0,-1000.0,1000.0)])
    duration=f(p,"duration",20.0,.01,10000.0); dt=f(p,"dt",.01,1e-6,10.0)
    method=str(p.get("method","rk4"))
    out=simulate_fixed(initial,params,duration=duration,dt=dt,method=method)
    times=np.asarray(out["time"]); states=np.asarray(out["state"])
    energy=linear_energy(states,params); balance=energy_balance_diagnostic(times,states,params)
    return result(
        "oscillation-integration",
        "pinned-oscillation_lab.simulate_fixed",
        clean({"mass":params.mass,"omega0":params.omega0,"gamma":params.gamma,"forceAmplitude":params.force_amplitude,"driveOmega":params.force_frequency,"initial":initial,"duration":duration,"dt":dt,"method":method}),
        {"actualDt":float(out["actual_dt"]),"samples":len(times),"maxAbsDisplacement":float(np.max(np.abs(states[:,0]))),"maxRelativeEnergyBalanceResidual":float(balance["max_relative_balance_residual"])},
        [
            xy_series("displacement","displacement",times,states[:,0],x_label="time (s)",y_label="u (m)"),
            xy_series("velocity","velocity",times,states[:,1],x_label="time (s)",y_label="v (m/s)"),
            xy_series("phase","phase portrait",states[:,0],states[:,1],x_label="u (m)",y_label="v (m/s)",chart="scatter"),
            xy_series("energy","mechanical energy",times,energy,x_label="time (s)",y_label="E"),
            xy_series("balance-residual","energy balance residual",times,balance["balance_residual"],x_label="time (s)",y_label="energy residual"),
        ],
        "Pinned Oscillation & Numerical Integration Lab core. Energy conservation is meaningful only for conservative configurations; damped or driven cases must be interpreted through the energy-power balance.",
    )

def radia_magnet(p: dict[str, Any], mode: str) -> dict[str, Any]:
    period_mm = f(p, "periodMm", 50.0, 1.0, 1000.0)
    periods = i(p, "periods", 20, 1, 500)
    device = str(p.get("device", "Planar"))
    if device not in {"Planar", "Helical", "Elliptical", "APPLE-II", "Wiggler"}:
        device = "Planar"

    params = {
        "device": device,
        "period_mm": period_mm,
        "periods": periods,
        "gap_mm": f(p, "gapMm", 12.0, 0.5, 100.0),
        "blocks_per_period": i(p, "blocksPerPeriod", 4, 4, 16),
        "block_width_mm": f(p, "blockWidthMm", 10.0, 0.1, 100.0),
        "block_height_mm": f(p, "blockHeightMm", 10.0, 0.1, 100.0),
        "longitudinal_fill": f(p, "longitudinalFill", 0.90, 0.50, 0.99),
        "br_t": f(p, "brT", 1.20, 0.01, 3.0),
        "material_mode": str(p.get("materialMode", "Fixed remanence")),
        "mu_parallel": f(p, "muParallel", 1.05, 1.0, 3.0),
        "mu_perpendicular": f(p, "muPerpendicular", 1.05, 1.0, 3.0),
        "segmentation": (i(p, "segmentation", 1, 1, 3),) * 3,
        "ellipticity": f(p, "ellipticity", 0.5, 0.0, 1.0),
        "apple_phase_deg": f(p, "applePhaseDeg", 90.0, -180.0, 180.0),
        "apple_shift_mode": str(p.get("appleShiftMode", "Antiparallel")),
        "errors_enabled": b(p, "errorsEnabled", False),
        "field_error_pct": f(p, "fieldErrorPct", 1.0, 0.0, 25.0),
        "longitudinal_error_mm": f(p, "longitudinalErrorMm", 0.05, 0.0, 10.0),
        "transverse_error_mm": f(p, "transverseErrorMm", 0.05, 0.0, 10.0),
        "angle_error_deg": f(p, "angleErrorDeg", 0.5, 0.0, 10.0),
        "gap_asymmetry_mm": f(p, "gapAsymmetryMm", 0.0, -10.0, 10.0),
        "bank_imbalance_pct": f(p, "bankImbalancePct", 0.0, -25.0, 25.0),
        "error_seed": i(p, "errorSeed", 12345, 0, 100000000),
        "target_b0_enabled": b(p, "targetB0Enabled", False),
        "target_b0_t": f(p, "targetB0T", 0.15, 0.001, 20.0),
        "b0_definition": str(p.get("b0Definition", "Central-period peak B⊥")),
    }
    settings = {
        "axis_samples": i(p, "axisSamples", 1000, 100, 4000),
        "field_margin_periods": f(p, "fieldMarginPeriods", 1.0, 0.0, 10.0),
        "electron_energy_GeV": f(p, "electronEnergyGeV", 3.0, 0.01, 1000.0),
        "relax": b(p, "relax", False),
        "precision": f(p, "precision", 1e-4, 1e-7, 1e-2),
        "max_iter": i(p, "maxIter", 1000, 1, 10000),
        "calculate_2d": b(p, "calculate2d", True),
        "calculate_3d": b(p, "calculate3d", True),
        "transverse_half_width_mm": f(p, "transverseHalfWidthMm", 5.0, 0.1, 100.0),
        "geometry_limit": i(p, "geometryLimit", 600, 100, 1200),
        "compare_ideal": b(p, "compareIdeal", True),
    }

    if mode != "full":
        reference_b0 = params["target_b0_t"] if params["target_b0_enabled"] else 0.15
        samples = settings["axis_samples"]
        z = np.linspace(-period_mm, period_mm, samples)
        by = reference_b0 * np.sin(2 * math.pi * z / period_mm)
        k = 0.934 * reference_b0 * (period_mm / 10.0)
        configured_errors = {key: params[key] for key in (
            "field_error_pct","longitudinal_error_mm","transverse_error_mm",
            "angle_error_deg","gap_asymmetry_mm","bank_imbalance_pct","error_seed"
        )}
        return result(
            "radia-magnet-studio",
            "native-analytic-safe",
            {**clean(params), **clean(settings), "requestedMode": mode},
            {
                "undulatorKReference": k,
                "magneticLengthM": period_mm / 1000 * periods,
                "referencePeakFieldT": reference_b0,
                "manufacturingErrorsConfigured": bool(params["errors_enabled"]),
            },
            [xy_series("field", "safe-mode ideal reference B_y", z, by, x_label="z (mm)", y_label="B_y (T)")],
            "Safe mode preserves the complete pinned RADIA setup state but computes only an ideal analytical reference. Manufacturing errors, finite geometry, material relaxation, target-B0 calibration, 2-D/3-D field maps and realized field metrics require Full mode.",
            [{"id":"configured-errors","label":"Configured manufacturing-error state","rows":[configured_errors]}],
        )

    from radia_support import load_radia
    from devices.factory import build_device
    from solver.pipeline import solve_model, sample_on_axis, sample_slice_xz, sample_slice_yz, sample_3d
    from analysis.metrics import analyze, compare_metrics, classify_k
    from analysis.geometry_bounds import union_field_range
    from calibration.target_b0 import calibrate_br

    rad = load_radia()
    try:
        if hasattr(rad, "UtiDelAll"):
            rad.UtiDelAll()

        full_params = dict(params)
        calibration_history = []
        if params["target_b0_enabled"]:
            calibrated_br, calibration_history = calibrate_br(
                rad, device, full_params, params["target_b0_t"],
                mode=params["b0_definition"], relax=settings["relax"],
                precision=settings["precision"], max_iter=settings["max_iter"],
            )
            full_params["br_t"] = float(calibrated_br)
            if hasattr(rad, "UtiDelAll"):
                rad.UtiDelAll()

        ideal_model = None
        if params["errors_enabled"] and settings["compare_ideal"]:
            p_ideal = dict(full_params)
            p_ideal["errors_enabled"] = False
            ideal_model = build_device(rad, device, p_ideal)

        model = build_device(rad, device, full_params)
        ideal_relax = None
        if ideal_model is not None:
            ideal_relax = solve_model(
                rad, ideal_model, relax=settings["relax"],
                precision=settings["precision"], max_iter=settings["max_iter"], method=4,
            )
        relaxation = solve_model(
            rad, model, relax=settings["relax"],
            precision=settings["precision"], max_iter=settings["max_iter"], method=4,
        )

        range_models = [model] + ([ideal_model] if ideal_model is not None else [])
        z_lo, z_hi = union_field_range(range_models, period_mm, settings["field_margin_periods"])
        z = np.linspace(float(z_lo), float(z_hi), settings["axis_samples"])
        B = np.asarray(sample_on_axis(rad, model["obj"], z), dtype=float)
        metrics = analyze(z, B, period_mm, settings["electron_energy_GeV"])

        Bideal = None
        ideal_metrics = None
        comparison = None
        if ideal_model is not None:
            Bideal = np.asarray(sample_on_axis(rad, ideal_model["obj"], z), dtype=float)
            ideal_metrics = analyze(z, Bideal, period_mm, settings["electron_energy_GeV"])
            comparison = compare_metrics(ideal_metrics, metrics)

        series = [
            xy_series("Bx","B_x",z,B[:,0],x_label="z (mm)",y_label="B_x (T)"),
            xy_series("By","B_y",z,B[:,1],x_label="z (mm)",y_label="B_y (T)"),
            xy_series("Bz","B_z",z,B[:,2],x_label="z (mm)",y_label="B_z (T)"),
        ]
        if Bideal is not None:
            series.append(xy_series("By-ideal","ideal B_y",z,Bideal[:,1],x_label="z (mm)",y_label="B_y (T)"))

        tables = []
        if calibration_history:
            tables.append({"id":"b0-calibration","label":"Target-B0 calibration history","rows":clean(calibration_history)})
        if comparison is not None:
            rows=[]
            if isinstance(comparison, dict):
                for key,value in comparison.items():
                    rows.append({"metric":key,"difference":clean(value)})
            tables.append({"id":"ideal-error-comparison","label":"Ideal vs manufacturing-error comparison","rows":rows})

        if settings["calculate_2d"]:
            transverse = np.linspace(-settings["transverse_half_width_mm"], settings["transverse_half_width_mm"], 31)
            z2 = np.linspace(float(z_lo), float(z_hi), min(181, max(61, settings["axis_samples"] // 5)))
            if abs(float(metrics.get("By_peak_T",0.0))) >= abs(float(metrics.get("Bx_peak_T",0.0))):
                slice_data = np.asarray(sample_slice_xz(rad, model["obj"], transverse, z2, 0.0), dtype=float)
                plane = "XZ"
            else:
                slice_data = np.asarray(sample_slice_yz(rad, model["obj"], transverse, z2, 0.0), dtype=float)
                plane = "YZ"
            tables.append({"id":"field-slice","label":"2-D field slice metadata","rows":[{"plane":plane,"transversePoints":len(transverse),"zPoints":len(z2),"shape":list(slice_data.shape)}]})

        if settings["calculate_3d"]:
            x3=np.linspace(-settings["transverse_half_width_mm"],settings["transverse_half_width_mm"],5)
            y3=x3.copy(); z3=np.linspace(float(z_lo),float(z_hi),17)
            field3=np.asarray(sample_3d(rad,model["obj"],x3,y3,z3),dtype=float)
            tables.append({"id":"field-3d","label":"Sparse 3-D field map metadata","rows":[{"nx":len(x3),"ny":len(y3),"nz":len(z3),"shape":list(field3.shape)}]})

        scalar_metrics={}
        for key,value in metrics.items():
            if isinstance(value,(int,float,np.integer,np.floating)) and np.isfinite(float(value)):
                scalar_metrics[key]=float(value)
        scalar_metrics.update({
            "generatedBlocks": len(model.get("blocks") or []),
            "fieldRangeMinMm": float(z_lo),
            "fieldRangeMaxMm": float(z_hi),
            "magneticRegime": classify_k(float(metrics.get("K_peak",0.0))),
            "usedBrT": float(full_params["br_t"]),
            "manufacturingErrorsEnabled": bool(params["errors_enabled"]),
            "idealComparisonComputed": bool(comparison is not None),
        })
        if isinstance(relaxation, dict):
            for key,value in relaxation.items():
                if isinstance(value,(int,float,bool,str)):
                    scalar_metrics[f"relaxation_{key}"]=value
        if isinstance(ideal_relax, dict):
            scalar_metrics["idealRelaxationAvailable"]=True

        return result(
            "radia-magnet-studio",
            "pinned-radia-magnet-studio-full-core",
            {**clean(full_params), **clean(settings), "requestedMode": mode},
            scalar_metrics,
            series,
            "Full mode directly reuses the pinned RADIA Magnet Studio build_device, target-B0 calibration, solve_model, geometry-derived field range, field sampling and analyze cores. Manufacturing-error results are realized RADIA fields, not an analytical surrogate.",
            tables,
        )
    finally:
        try:
            if hasattr(rad, "UtiDelAll"):
                rad.UtiDelAll()
        except Exception:
            pass



def radiation_platform(p: dict[str, Any], mode: str) -> dict[str, Any]:
    period_mm = f(p, "periodMm", 50.0, 1.0, 1000.0)
    K = f(p, "K", 0.7003, 0.0, 50.0)
    energy_gev = f(p, "energyGeV", 3.0, 0.001, 1000.0)
    use_gamma = b(p, "useGamma", False)
    gamma = f(p, "gamma", energy_gev / E_REST_GEV, 1.01, 1e7) if use_gamma or "gamma" in p else energy_gev / E_REST_GEV
    harmonic = i(p, "harmonic", 1, 1, 99)
    periods = i(p, "periods", 20, 2, 500)
    period_m = period_mm / 1000.0
    observer_distance = f(p, "observerDistanceM", 100.0, 1.0, 10000.0)
    theta_x_mrad = f(p, "thetaXMrad", f(p, "observationAngleMrad", 0.0, -20.0, 20.0), -20.0, 20.0)
    theta_y_mrad = f(p, "thetaYMrad", 0.0, -20.0, 20.0)
    tracking_ppp = i(p, "trackingPointsPerPeriod", i(p, "trajectoryPointsPerPeriod", 64, 16, 256), 16, 256)

    if mode != "full":
        observation_mrad = math.hypot(theta_x_mrad, theta_y_mrad)
        extent_gamma_theta = f(p, "angularExtentGammaTheta", 2.5, 0.5, 5.0)
        theta_span_mrad = max(0.25, extent_gamma_theta / gamma * 1000.0)
        theta = np.linspace(max(0.0, observation_mrad - theta_span_mrad), observation_mrad + theta_span_mrad, 201)
        theta_rad = theta / 1000.0
        lam = period_m * (1 + K * K / 2 + (gamma * theta_rad) ** 2) / (2 * gamma * gamma * harmonic)
        photon = HC_EV_M / lam
        obs_lam = period_m * (1 + K * K / 2 + (gamma * observation_mrad / 1000.0) ** 2) / (2 * gamma * gamma * harmonic)
        center = float(HC_EV_M / obs_lam)
        ef = np.linspace(center * 0.82, center * 1.18, 801)
        detune = periods * (ef / center - 1.0)
        intensity = np.sinc(detune) ** 2
        return result(
            "radiation-platform",
            "native-analytic-resonance-safe",
            {
                "periodMm": period_mm, "K": K, "energyGeV": energy_gev, "gamma": gamma,
                "harmonic": harmonic, "periods": periods, "thetaXMrad": theta_x_mrad,
                "thetaYMrad": theta_y_mrad, "observerDistanceM": observer_distance,
                "fieldModel": str(p.get("fieldModel", "analytic")), "requestedMode": mode,
            },
            {
                "lorentzGamma": gamma,
                "observationPhotonEnergyEV": center,
                "observationWavelengthNm": HC_EV_M / center * 1e9,
                "finiteNRelativeWidth": 1.0 / periods,
            },
            [
                xy_series("angle", "resonance energy vs angle", theta, photon, x_label="observation angle (mrad)", y_label="photon energy (eV)"),
                xy_series("spectrum", "finite-N resonance envelope", ef, intensity, x_label="photon energy (eV)", y_label="relative intensity"),
            ],
            "Safe mode is the ideal planar-undulator resonance/interference reference only. The complete configured RADIA field model, manufacturing-error model, Lorentz trajectory and retarded radiation solver are executed only in Full mode.",
        )

    import undulator_v11_radia_integrated_v9 as v11

    field_model = str(p.get("fieldModel", "radia_generated"))
    device_preset = str(p.get("devicePreset", "helical"))
    stage1_result = p.get("stage1Result")
    stage1_parameters = {}
    if isinstance(stage1_result, dict) and stage1_result.get("experimentId") == "radia-magnet-studio":
        candidate = stage1_result.get("parameters")
        if isinstance(candidate, dict):
            stage1_parameters = dict(candidate)
            field_model = "radia_generated"
            device_map = {
                "Planar": "planar", "Helical": "helical", "Elliptical": "elliptical",
                "APPLE-II": "apple2", "Wiggler": "wiggler",
            }
            mapped = device_map.get(str(stage1_parameters.get("device") or ""))
            if mapped:
                device_preset = mapped
            period_mm = float(stage1_parameters.get("period_mm", stage1_parameters.get("periodMm", period_mm)))
            period_m = period_mm / 1000.0
            periods = int(stage1_parameters.get("periods", periods))

    if device_preset not in set(v11.list_device_presets()):
        raise ValueError(f"Unknown Radiation Platform device preset: {device_preset}")
    if field_model == "radia_csv":
        raise ValueError("RADIA CSV mode requires an explicitly imported field-map file. Use the Original Data Bridge/import workflow first, or choose RADIA generated 3D field / analytic field.")

    error_mode = str(p.get("errorMode", "Selected errors"))
    switches = {
        "field_amplitude": b(p, "errField", True),
        "longitudinal_position": b(p, "errLongitudinal", True),
        "transverse_position": b(p, "errTransverse", True),
        "magnetization_angle": b(p, "errAngle", True),
        "gap_asymmetry": b(p, "errGap", True),
        "bank_strength_imbalance": b(p, "errBank", True),
    }
    if error_mode == "All errors":
        switches = {key: True for key in switches}
    elif error_mode == "Ideal (no errors)":
        switches = {key: False for key in switches}

    error_config = {
        "field_amplitude": {"enabled": switches["field_amplitude"], "rms_fraction": f(p, "fieldSigmaPct", 0.2, 0.0, 25.0) / 100.0},
        "longitudinal_position": {"enabled": switches["longitudinal_position"], "rms_m": f(p, "longitudinalSigmaUm", 20.0, 0.0, 10000.0) * 1e-6},
        "transverse_position": {"enabled": switches["transverse_position"], "rms_m": f(p, "transverseSigmaUm", 10.0, 0.0, 10000.0) * 1e-6},
        "magnetization_angle": {"enabled": switches["magnetization_angle"], "rms_rad": f(p, "angleSigmaMrad", 0.5, 0.0, 1000.0) * 1e-3},
        "gap_asymmetry": {"enabled": switches["gap_asymmetry"], "rms_m": f(p, "gapAsymmetryUm", 10.0, 0.0, 10000.0) * 1e-6},
        "bank_strength_imbalance": {"enabled": switches["bank_strength_imbalance"], "rms_fraction": f(p, "bankSigmaPct", 0.1, 0.0, 25.0) / 100.0},
    }

    if field_model == "radia_generated":
        preset = v11.get_device_preset(device_preset)
        manual_target = f(p, "manualTargetB0T", 0.15, 0.001, 20.0)
        if str(p.get("generatedTargetMode", "Preset default")) == "Manual B0":
            target_b0 = manual_target
        elif preset.get("wiggler_K") is not None:
            target_b0 = v11.B0_from_K(float(preset["wiggler_K"]), period_m)
        else:
            target_b0 = float(getattr(v11, "RADIA_TARGET_B0_T", 0.15))
        radia_options = {
            "lambda_u_m": period_m,
            "target_B0_T": target_b0,
            "gap_m": f(p, "radiaGapMm", 12.0, 0.5, 100.0) * 1e-3,
            "block_width_m": f(p, "radiaBlockWidthMm", 10.0, 0.1, 100.0) * 1e-3,
            "block_height_m": f(p, "radiaBlockHeightMm", 15.0, 0.1, 100.0) * 1e-3,
            "x_half_m": f(p, "radiaMapHalfMm", 3.0, 0.2, 100.0) * 1e-3,
            "y_half_m": f(p, "radiaMapHalfMm", 3.0, 0.2, 100.0) * 1e-3,
            "nx": i(p, "radiaMapNxy", 7, 3, 11),
            "ny": i(p, "radiaMapNxy", 7, 3, 11),
            "samples_per_period": i(p, "radiaSamplesPerPeriod", 24, 8, 64),
            "field_margin_periods": f(p, "radiaFieldMarginPeriods", 1.0, 0.0, 10.0),
            "error_config": error_config,
            "error_seed": i(p, "manufacturingSeed", 20260820, 0, 100000000),
            "material_mode": str(p.get("radiaMaterialMode", "Fixed remanence")),
            "mu_parallel": f(p, "radiaMuParallel", 1.05, 1.0, 3.0),
            "mu_perpendicular": f(p, "radiaMuPerpendicular", 1.05, 1.0, 3.0),
            "segmentation": (i(p, "radiaSegmentation", 1, 1, 3),) * 3,
            "ellipticity": f(p, "radiaEllipticity", 0.5, 0.0, 1.0),
            "apple_phase_deg": f(p, "radiaApplePhaseDeg", 90.0, -180.0, 180.0),
            "apple_shift_mode": str(p.get("radiaAppleShiftMode", "Antiparallel")),
        }
        if stage1_parameters:
            radia_options.update({
                "lambda_u_m": float(stage1_parameters.get("period_mm", period_mm)) * 1e-3,
                "gap_m": float(stage1_parameters.get("gap_mm", radia_options["gap_m"] * 1e3)) * 1e-3,
                "block_width_m": float(stage1_parameters.get("block_width_mm", radia_options["block_width_m"] * 1e3)) * 1e-3,
                "block_height_m": float(stage1_parameters.get("block_height_mm", radia_options["block_height_m"] * 1e3)) * 1e-3,
                "x_half_m": float(stage1_parameters.get("transverse_half_width_mm", radia_options["x_half_m"] * 1e3)) * 1e-3,
                "y_half_m": float(stage1_parameters.get("transverse_half_width_mm", radia_options["y_half_m"] * 1e3)) * 1e-3,
                "field_margin_periods": float(stage1_parameters.get("field_margin_periods", radia_options["field_margin_periods"])),
                "error_seed": int(stage1_parameters.get("error_seed", radia_options["error_seed"])),
                "material_mode": str(stage1_parameters.get("material_mode", radia_options["material_mode"])),
                "mu_parallel": float(stage1_parameters.get("mu_parallel", radia_options["mu_parallel"])),
                "mu_perpendicular": float(stage1_parameters.get("mu_perpendicular", radia_options["mu_perpendicular"])),
                "segmentation": tuple(stage1_parameters.get("segmentation", radia_options["segmentation"])),
                "ellipticity": float(stage1_parameters.get("ellipticity", radia_options["ellipticity"])),
                "apple_phase_deg": float(stage1_parameters.get("apple_phase_deg", radia_options["apple_phase_deg"])),
                "apple_shift_mode": str(stage1_parameters.get("apple_shift_mode", radia_options["apple_shift_mode"])),
            })
            switches = {
                "field_amplitude": bool(stage1_parameters.get("errors_enabled", False)),
                "longitudinal_position": bool(stage1_parameters.get("errors_enabled", False)),
                "transverse_position": bool(stage1_parameters.get("errors_enabled", False)),
                "magnetization_angle": bool(stage1_parameters.get("errors_enabled", False)),
                "gap_asymmetry": bool(stage1_parameters.get("errors_enabled", False)),
                "bank_strength_imbalance": bool(stage1_parameters.get("errors_enabled", False)),
            }
            radia_options["error_config"] = {
                "field_amplitude": {"enabled": switches["field_amplitude"], "rms_fraction": float(stage1_parameters.get("field_error_pct", 0.0)) / 100.0},
                "longitudinal_position": {"enabled": switches["longitudinal_position"], "rms_m": float(stage1_parameters.get("longitudinal_error_mm", 0.0)) * 1e-3},
                "transverse_position": {"enabled": switches["transverse_position"], "rms_m": float(stage1_parameters.get("transverse_error_mm", 0.0)) * 1e-3},
                "magnetization_angle": {"enabled": switches["magnetization_angle"], "rms_rad": math.radians(float(stage1_parameters.get("angle_error_deg", 0.0)))},
                "gap_asymmetry": {"enabled": switches["gap_asymmetry"], "rms_m": abs(float(stage1_parameters.get("gap_asymmetry_mm", 0.0))) * 1e-3},
                "bank_strength_imbalance": {"enabled": switches["bank_strength_imbalance"], "rms_fraction": abs(float(stage1_parameters.get("bank_imbalance_pct", 0.0))) / 100.0},
            }
            if stage1_parameters.get("target_b0_enabled"):
                radia_options["target_B0_T"] = float(stage1_parameters.get("target_b0_t", radia_options["target_B0_T"]))
        und = v11.make_default_undulator(
            preset=device_preset,
            field_model="radia_generated",
            n_periods=periods,
            error_switches=switches,
            radia_options=radia_options,
        )
    else:
        und = v11.make_default_undulator(
            preset=device_preset,
            field_model="analytic",
            n_periods=periods,
            analytic_h3=f(p, "analyticH3", 0.0, -0.5, 0.5),
            analytic_h5=f(p, "analyticH5", 0.0, -0.5, 0.5),
        )
        if hasattr(und, "B0") and K >= 0:
            try:
                und.B0 = v11.B0_from_K(K, float(und.lambda_u))
            except Exception:
                pass

    theta_x = theta_x_mrad * 1e-3
    theta_y = theta_y_mrad * 1e-3
    observer = np.array([
        observer_distance * math.tan(theta_x),
        observer_distance * math.tan(theta_y),
        observer_distance,
    ], dtype=float)
    span = v11.simulation_span_for_device(gamma, und, n_periods=periods)
    n_base = v11.samples_for_periods(
        periods,
        pts_per_period=tracking_ppp,
        min_pts=max(1000, periods * tracking_ppp),
        max_pts=max(4000, periods * tracking_ppp + 1),
    )
    full = v11.run_sim_scalar(
        und, None, span, observer,
        n_base=n_base, gamma0_input=gamma,
    )
    if not isinstance(full, dict):
        raise RuntimeError("Pinned Radiation Platform full solver returned no valid result for this configuration.")

    metrics = {}
    for key, value in full.items():
        if isinstance(value, (bool, str)):
            metrics[key] = value
        elif isinstance(value, (int, float, np.integer, np.floating)):
            try:
                if np.isfinite(float(value)):
                    metrics[key] = float(value)
            except Exception:
                pass

    inputs = {
        "fieldModel": field_model,
        "devicePreset": device_preset,
        "periodMm": period_mm,
        "K": K,
        "gamma": gamma,
        "periods": periods,
        "observerDistanceM": observer_distance,
        "thetaXMrad": theta_x_mrad,
        "thetaYMrad": theta_y_mrad,
        "trackingPointsPerPeriod": tracking_ppp,
        "errorMode": error_mode,
        "errorSwitches": switches,
        "errorConfig": error_config,
        "requestedMode": mode,
        "stage1Source": "Latest native RADIA run" if stage1_parameters else "Current Radiation setup",
    }
    if field_model == "radia_generated":
        inputs["radiaOptions"] = radia_options

    series = []
    if b(p, "showSingleDevicePreview", False) and hasattr(und, "z_grid") and hasattr(und, "_by_arr"):
        try:
            ix = int(np.argmin(np.abs(np.asarray(und.x_grid, dtype=float))))
            iy = int(np.argmin(np.abs(np.asarray(und.y_grid, dtype=float))))
            z_axis = np.asarray(und.z_grid, dtype=float)
            by_axis = np.asarray(und._by_arr[ix, iy, :], dtype=float)
            series.append(xy_series("stage1-z-field", "single-device z-axis B_y preview", z_axis, by_axis, x_label="z (m)", y_label="B_y (T)"))
        except Exception:
            pass

    tables = [
        {
            "id": "full-solver-summary",
            "label": "Pinned V11/RADIA full-solver observables",
            "rows": [{key: clean(value) for key, value in full.items() if not isinstance(value, (np.ndarray, list, tuple, dict))}],
        },
        {
            "id": "error-configuration",
            "label": "Manufacturing error configuration",
            "rows": [{"error": key, **clean(value)} for key, value in error_config.items()],
        },
    ]
    return result(
        "radiation-platform",
        "pinned-radiation-platform-full-core",
        clean(inputs),
        metrics,
        series,
        "Full mode directly reuses the pinned Radiation Platform field-device builder, Lorentz trajectory integration, retarded Liénard-Wiechert observer signal, spectrum/Stokes analysis, trajectory/phase diagnostics, energy accounting and radiation observables. RADIA-generated mode additionally uses the pinned strict 3-D RADIA field-map backend with the configured manufacturing-error model.",
        tables,
    )



def kerr_geodesics(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_kerr_geodesics import KerrOrbitConfig, integrate_case, result_summary, oblate_xyz
    particle = str(p.get("particleType", "massive")).lower()
    cfg = KerrOrbitConfig(
        spin=f(p, "spin", 0.7, 0.0, 0.995),
        inclination_deg=f(p, "inclinationDeg", 25.0, 0.0, 89.0),
        particle_type="photon" if particle == "photon" else "massive",
        periapsis=f(p, "periapsis", 6.5, 2.1, 80.0),
        apoapsis=f(p, "apoapsis", 10.0, 2.2, 150.0),
        lam_max=f(p, "lambdaMax", 16.0, 1.0, 80.0),
        samples=i(p, "samples", 1000, 200, 4000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        horizon_pad=f(p, "horizonPad", 1e-4, 1e-8, 0.1),
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    lam = np.asarray(out["lambda"])
    state = np.asarray(out["state"])
    r = state[1]; theta = state[2]; phi = state[3]
    ox, oy, oz = oblate_xyz(r, theta, phi, cfg.spin)
    return result(
        "kerr-geodesics",
        "physical_lab_kerr_geodesics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("radius", "Boyer-Lindquist radius", lam, r, x_label="Mino parameter λ", y_label="r/M"),
            xy_series("orbit", "oblate x-y trajectory", ox, oy, x_label="x/M", y_label="y/M", chart="scatter"),
            xy_series("polar", "polar angle", lam, np.degrees(theta), x_label="Mino parameter λ", y_label="θ (deg)"),
        ],
        "Kerr geodesic benchmark in geometric units G=c=M=1 using the existing Physical Lab Carter-Mino integrator. Integrability, solver residuals and horizon guards remain part of the interpretation boundary.",
    )


def solar_system(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_solar_system_dynamics import SolarSystemConfig, integrate_case, result_summary
    cfg = SolarSystemConfig(
        duration_years=f(p, "durationYears", 30.0, 0.05, 200.0),
        samples=i(p, "samples", 900, 100, 5000),
        inclination_jupiter_deg=f(p, "inclinationDeg", 10.0, 0.0, 60.0),
        saturn_inclination_factor=f(p, "saturnInclinationFactor", 0.25, 0.0, 1.0),
        saturn_backreaction=b(p, "saturnBackreaction", True),
        solar_1pn=b(p, "solar1pn", False),
        velocity_cross=b(p, "velocityCross", False),
        radial_drag=b(p, "radialDrag", False),
        velocity_cross_strength=f(p, "velocityCrossStrength", 1e-4, 0.0, 1e-2),
        radial_drag_strength=f(p, "radialDragStrength", 1e-8, 0.0, 1e-5),
        omega_z_per_year=f(p, "omegaZPerYear", 0.1, 0.0, 10.0),
        rtol=f(p, "rtol", 1e-10, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-12, 1e-15, 1e-7),
        max_step_years=f(p, "maxStepYears", 0.04, 0.0001, 1.0),
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    t = np.asarray(out["time_years"])
    pos = np.asarray(out["positions_AU"])
    diag = out["diagnostics"]
    relj = pos[:, 1] - pos[:, 0]
    rels = pos[:, 2] - pos[:, 0]
    return result(
        "solar-system-dynamics",
        "physical_lab_solar_system_dynamics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("jupiter-orbit", "Jupiter heliocentric path", relj[:, 0], relj[:, 1], x_label="x (AU)", y_label="y (AU)", chart="scatter"),
            xy_series("saturn-orbit", "Saturn heliocentric path", rels[:, 0], rels[:, 1], x_label="x (AU)", y_label="y (AU)", chart="scatter"),
            xy_series("period-ratio", "Saturn/Jupiter period ratio", t, diag["period_ratio_saturn_over_jupiter"], x_label="time (yr)", y_label="T_S/T_J"),
            xy_series("separation", "Jupiter-Saturn separation", t, diag["jupiter_saturn_separation_AU"], x_label="time (yr)", y_label="separation (AU)"),
        ],
        "Barycentric point-mass Sun-Jupiter-Saturn dynamics. The optional solar 1PN term is a bounded central-Sun approximation rather than a complete EIH N-body 1PN model.",
    )


def honeycomb_lattice(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_lattice_dynamics import LatticeConfig, integrate_case, result_summary
    cfg = LatticeConfig(
        nx=i(p, "nx", 3, 2, 10),
        ny=i(p, "ny", 3, 2, 10),
        layers=i(p, "layers", 2, 1, 5),
        stacking=str(p.get("stacking", "ABA")).upper() if str(p.get("stacking", "ABA")).upper() in {"AA", "ABA", "ABC"} else "ABA",
        bond_length=f(p, "bondLength", 1.0, 0.05, 20.0),
        layer_spacing=f(p, "layerSpacing", 0.35, 0.01, 10.0),
        strain_x=f(p, "strainX", 0.0, -0.25, 0.25),
        mass=f(p, "mass", 1.0, 1e-6, 1e6),
        k_in=f(p, "kIn", 10.0, 1e-6, 1e6),
        alpha=f(p, "alpha", 2.0, 0.0, 1e4),
        k_inter=f(p, "kInter", 3.0, 1e-6, 1e6),
        beta_inter=f(p, "betaInter", 1.0, 0.0, 1e4),
        damping=f(p, "damping", 0.02, 0.0, 10.0),
        interlayer_damping=f(p, "interlayerDamping", 0.01, 0.0, 10.0),
        defect_mode=str(p.get("defectMode", "none")) if str(p.get("defectMode", "none")) in {"none","mass","weak-bond","line-weak-bond"} else "none",
        defect_mass_multiplier=f(p, "defectMassMultiplier", 2.0, 0.0, 100.0),
        defect_bond_scale=f(p, "defectBondScale", 0.4, 0.0, 10.0),
        drive_mode=str(p.get("driveMode", "sin")) if str(p.get("driveMode", "sin")) in {"none","sin","pulse","beat","chirp"} else "sin",
        drive_amplitude=f(p, "driveAmplitude", 0.08, 0.0, 10.0),
        drive_frequency=f(p, "driveFrequency", 1.0, 0.0, 100.0),
        uniform_force_x=f(p, "uniformForceX", 0.0, -100.0, 100.0),
        stochastic_mode=b(p, "stochasticMode", False),
        temperature_reduced=f(p, "temperatureReduced", 0.0, 0.0, 100.0),
        seed=i(p, "seed", 12345, 0, 2147483647),
        initial_displacement=f(p, "initialDisplacement", 0.01, 0.0, 10.0),
        duration=f(p, "duration", 8.0, 1.0, 200.0),
        samples=i(p, "samples", 420, 64, 20000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        max_step=f(p, "maxStep", 0.03, 0.0001, 1.0),
        langevin_dt=f(p, "langevinDt", 0.005, 1e-5, 0.2),
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    t = np.asarray(out["time"])
    analysis = out["analysis"]
    disp = np.asarray(analysis["displacement"])
    site = 0
    return result(
        "honeycomb-lattice",
        "physical_lab_lattice_dynamics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("site-y", "site-0 y displacement", t, disp[:, site, 1], x_label="time", y_label="u_y"),
            xy_series("energy", "total energy", t, analysis["total_energy"], x_label="time", y_label="E"),
            xy_series("anisotropy", "velocity anisotropy", t, analysis["anisotropy"], x_label="time", y_label="anisotropy"),
            xy_series("layer-ke", "top-layer kinetic energy", t, np.asarray(analysis["layer_kinetic_energy"])[:, -1], x_label="time", y_label="K_layer"),
        ],
        summary["scientific_boundary"],
    )


def utube(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_utube_experiment import critical_speed, threshold, capacity, DEFAULT_R_IN_M, DEFAULT_A_M
    volume = f(p, "volumeMl", 3.0, 0.05, 30.0)
    rpm = f(p, "rpm", 260.0, 1.0, 1000.0)
    rin = f(p, "rinMm", DEFAULT_R_IN_M * 1000, 1.0, 100.0) / 1000.0
    radius = f(p, "radiusMm", DEFAULT_A_M * 1000, 0.1, 50.0) / 1000.0
    nq = i(p, "nq", 48, 12, 128)
    nc = critical_speed(rin, radius)
    ng = threshold(volume, rin=rin, a=radius, nq=nq)
    total, arc, legs = capacity(rpm, rin=rin, a=radius, nq=nq)
    vols = np.linspace(max(0.2, 0.35 * volume), max(6.0, 1.75 * volume), 25)
    thresholds = [threshold(float(v), rin=rin, a=radius, nq=nq) for v in vols]
    return result(
        "utube-studio",
        "physical_lab_utube_experiment",
        {"volumeMl": volume, "rpm": rpm, "rinMm": rin * 1000, "radiusMm": radius * 1000, "nq": nq},
        {"criticalSpeedRpm": nc, "thresholdRpm": ng, "operatingMarginRpm": rpm - ng, "capacityTotalMl": total, "capacityArcMl": arc, "capacityLegsMl": legs},
        [xy_series("threshold", "n_g(V)", vols, thresholds, x_label="volume (mL)", y_label="threshold (rpm)")],
        "Existing deterministic U-tube 3-D-potential model. Numerical convergence does not establish physical validity and theory/measurement agreement is validation evidence rather than proof.",
    )


def kerr_shadow(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_kerr_shadow_sweep import kerr_shadow_morphology_sweep
    spin = f(p, "spin", 0.9, 0.0, 0.98)
    inc = f(p, "inclinationDeg", 60.0, 0.5, 90.0)
    sweep = kerr_shadow_morphology_sweep(spins=[0.0, spin], inclinations_deg=[inc], curve_samples=i(p, "curveSamples", 320, 120, 1200))
    rows = sweep["rows"]
    x = [r["spin_a_over_M"] for r in rows]
    return result(
        "kerr-shadow",
        "physical_lab_kerr_shadow_sweep",
        {"spin": spin, "inclinationDeg": inc},
        {"maxAbsHorizontalShiftOverM": sweep["max_abs_horizontal_shift_over_M"], "maxAbsSignedFlattening": sweep["max_abs_signed_flattening"]},
        [
            xy_series("shift", "horizontal shift", x, [r["horizontal_shift_over_M"] for r in rows], x_label="spin a/M", y_label="shift / M"),
            xy_series("flattening", "signed flattening", x, [r["signed_flattening"] for r in rows], x_label="spin a/M", y_label="flattening"),
            xy_series("diameter", "mean diameter", x, [r["mean_diameter_over_M"] for r in rows], x_label="spin a/M", y_label="diameter / M"),
        ],
        sweep["boundary"],
        [{"id": "morphology", "label": "Morphology cases", "rows": rows}],
    )


def undulator_spectrum(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_undulator_spectrum import harmonic_spectrum, angular_harmonic_map, resonance_energy_eV
    period_m = f(p, "periodMm", 50.0, 1.0, 1000.0) / 1000.0
    gamma = f(p, "gamma", 6000.0, 2.0, 1e7)
    K = f(p, "K", 0.7, 0.0, 20.0)
    periods = i(p, "periods", 20, 2, 500)
    harmonic = i(p, "harmonic", 1, 1, 15)
    observation_angle = f(p, "observationAngleMrad", 0.0, 0.0, 20.0)
    raw_harmonics = str(p.get("harmonicsText", "1,3,5,7"))
    harmonics = []
    for token in raw_harmonics.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = int(token)
        except Exception:
            continue
        if value > 0 and value % 2 == 1 and value not in harmonics:
            harmonics.append(value)
    if not harmonics:
        harmonics = [1, 3, 5, 7]
    harmonics = tuple(harmonics[:12])
    spec = harmonic_spectrum(period_m=period_m, gamma=gamma, K=K, n_periods=periods, theta_mrad=observation_angle, harmonics=harmonics, points=1200)
    amap = angular_harmonic_map(
        period_m=period_m, gamma=gamma, K=K, harmonic=harmonic,
        theta_max_mrad=f(p, "thetaMaxMrad", 1.0, 0.05, 20.0),
        points=i(p, "angularPoints", 61, 21, 181),
    )
    axis = np.asarray(amap["theta_axis_mrad"])
    center_line = np.asarray(amap["resonance_energy_eV"])[len(axis)//2]
    selected_energy = resonance_energy_eV(period_m=period_m, gamma=gamma, K=K, harmonic=harmonic, theta_rad=observation_angle / 1000.0)
    return result(
        "undulator-spectrum",
        "physical_lab_undulator_spectrum",
        {
            "periodMm": period_m * 1000, "gamma": gamma, "K": K, "periods": periods,
            "harmonic": harmonic, "harmonics": list(harmonics), "observationAngleMrad": observation_angle,
            "thetaMaxMrad": f(p, "thetaMaxMrad", 1.0, 0.05, 20.0),
            "angularPoints": i(p, "angularPoints", 61, 21, 181),
        },
        {
            "onAxisEnergyEV": amap["on_axis_energy_eV"],
            "selectedObservationEnergyEV": selected_energy,
            "edgeEnergyEV": amap["edge_energy_eV"],
            "minimumEnergyEV": amap["minimum_energy_eV"],
            "maximumEnergyEV": amap["maximum_energy_eV"],
        },
        [
            xy_series("spectrum", "harmonic spectrum", spec["energy_eV"], spec["relative_intensity"], x_label="photon energy (eV)", y_label="relative intensity"),
            xy_series("angle-cut", "angular resonance cut", axis, center_line, x_label="θ_x (mrad)", y_label="resonance energy (eV)"),
        ],
        spec["boundary"] + " " + amap["boundary"],
        [{"id": "harmonics", "label": "Harmonic centers", "rows": spec["harmonics"]}],
    )



def _sweep_quality(name: str, *, nonlinear: bool = False) -> dict[str, int]:
    key = str(name or "Standard").strip().lower()
    if nonlinear:
        table = {
            "fast": {"points": 13, "settle": 22, "observe": 5, "ppc": 48},
            "standard": {"points": 21, "settle": 35, "observe": 8, "ppc": 60},
            "deep": {"points": 31, "settle": 50, "observe": 10, "ppc": 84},
        }
    else:
        table = {
            "fast": {"points": 13, "settle": 16, "observe": 5, "ppc": 48},
            "standard": {"points": 21, "settle": 26, "observe": 7, "ppc": 64},
            "deep": {"points": 31, "settle": 40, "observe": 10, "ppc": 84},
        }
    return table.get(key, table["standard"])


def frequency_response(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_frequency_response import linear_forced_response_sweep
    omega_n = f(p, "omegaN", 2.0, 0.1, 30.0)
    start_ratio = f(p, "linearStartRatio", 0.30, 0.1, 3.0)
    stop_ratio = f(p, "linearStopRatio", 1.60, 0.2, 5.0)
    if stop_ratio <= start_ratio:
        raise ValueError("Linear stop frequency ratio must exceed start ratio")
    quality = _sweep_quality(str(p.get("linearSweepQuality", "Standard")))
    out = linear_forced_response_sweep(
        omega_n=omega_n,
        zeta=f(p, "zeta", 0.05, 0.0, 1.5),
        force_amplitude=f(p, "force", 1.0, 0.0, 20.0),
        frequency_start=start_ratio * omega_n,
        frequency_stop=stop_ratio * omega_n,
        frequency_points=quality["points"],
        settle_cycles=quality["settle"],
        observe_cycles=quality["observe"],
        points_per_cycle=quality["ppc"],
    )
    rows = out["rows"]
    omega = [r["omega_rad_s"] for r in rows]
    return result(
        "frequency-response",
        "physical_lab_frequency_response.linear_forced_response_sweep",
        {**out["inputs"], "startRatio": start_ratio, "stopRatio": stop_ratio, "sweepQuality": str(p.get("linearSweepQuality", "Standard"))},
        {
            "numericalPeakFrequencyRadS": out["numerical_peak_frequency_rad_s"],
            "numericalPeakAmplitude": out["numerical_peak_amplitude"],
            "theoreticalResonanceFrequencyRadS": out["theoretical_resonance_frequency_rad_s"],
            "maxAmplitudeRelativeError": out["max_amplitude_relative_error"],
            "maxPhaseAbsoluteErrorRad": out["max_phase_absolute_error_rad"],
        },
        [
            xy_series("numerical-amplitude", "numerical amplitude", omega, [r["fundamental_amplitude"] for r in rows], x_label="ω (rad/s)", y_label="amplitude"),
            xy_series("analytic-amplitude", "analytic amplitude", omega, [r["analytic_amplitude"] for r in rows], x_label="ω (rad/s)", y_label="amplitude"),
            xy_series("phase", "phase lag", omega, [r["phase_lag_rad"] for r in rows], x_label="ω (rad/s)", y_label="phase lag (rad)"),
            xy_series("amplitude-error", "amplitude relative error", omega, [r["amplitude_relative_error"] for r in rows], x_label="ω (rad/s)", y_label="relative error"),
        ],
        out["boundary"],
        [{"id": "frequency-rows", "label": "Frequency sweep", "rows": rows}],
    )



def _kerr_config_from_params(p: dict[str, Any]):
    from physical_lab_kerr_geodesics import KerrOrbitConfig
    particle = str(p.get("particleType", "massive")).lower()
    return KerrOrbitConfig(
        spin=f(p, "spin", 0.7, 0.0, 0.995),
        inclination_deg=f(p, "inclinationDeg", 25.0, 0.0, 89.0),
        particle_type="photon" if particle == "photon" else "massive",
        periapsis=f(p, "periapsis", 6.5, 2.1, 80.0),
        apoapsis=f(p, "apoapsis", 10.0, 2.2, 150.0),
        lam_max=f(p, "lambdaMax", 16.0, 1.0, 80.0),
        samples=i(p, "samples", 1000, 200, 4000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        horizon_pad=f(p, "horizonPad", 1e-4, 1e-8, 0.1),
    )


def _solar_config_from_params(p: dict[str, Any]):
    from physical_lab_solar_system_dynamics import SolarSystemConfig
    return SolarSystemConfig(
        duration_years=f(p, "durationYears", 30.0, 0.05, 1000.0),
        samples=i(p, "samples", 900, 100, 50000),
        inclination_jupiter_deg=f(p, "inclinationDeg", 10.0, 0.0, 60.0),
        saturn_inclination_factor=f(p, "saturnInclinationFactor", 0.25, 0.0, 1.0),
        saturn_backreaction=b(p, "saturnBackreaction", True),
        solar_1pn=b(p, "solar1pn", False),
        velocity_cross=b(p, "velocityCross", False),
        radial_drag=b(p, "radialDrag", False),
        velocity_cross_strength=f(p, "velocityCrossStrength", 1e-4, 0.0, 1e-2),
        radial_drag_strength=f(p, "radialDragStrength", 1e-8, 0.0, 1e-5),
        omega_z_per_year=f(p, "omegaZPerYear", 0.1, 0.0, 10.0),
        rtol=f(p, "rtol", 1e-10, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-12, 1e-15, 1e-7),
        max_step_years=f(p, "maxStepYears", 0.04, 0.0001, 1.0),
    )


def _lattice_config_from_params(p: dict[str, Any]):
    from physical_lab_lattice_dynamics import LatticeConfig
    stacking=str(p.get("stacking", "ABA")).upper()
    defect=str(p.get("defectMode", "none"))
    drive=str(p.get("driveMode", "sin"))
    return LatticeConfig(
        nx=i(p, "nx", 3, 2, 10), ny=i(p, "ny", 3, 2, 10), layers=i(p, "layers", 2, 1, 5),
        stacking=stacking if stacking in {"AA","ABA","ABC"} else "ABA",
        bond_length=f(p, "bondLength", 1.0, 0.05, 20.0),
        layer_spacing=f(p, "layerSpacing", 0.35, 0.01, 10.0),
        strain_x=f(p, "strainX", 0.0, -0.25, 0.25),
        mass=f(p, "mass", 1.0, 1e-6, 1e6), k_in=f(p, "kIn", 10.0, 1e-6, 1e6),
        alpha=f(p, "alpha", 2.0, 0.0, 1e4), k_inter=f(p, "kInter", 3.0, 1e-6, 1e6),
        beta_inter=f(p, "betaInter", 1.0, 0.0, 1e4),
        damping=f(p, "damping", 0.02, 0.0, 10.0), interlayer_damping=f(p, "interlayerDamping", 0.01, 0.0, 10.0),
        defect_mode=defect if defect in {"none","mass","weak-bond","line-weak-bond"} else "none",
        defect_mass_multiplier=f(p, "defectMassMultiplier", 2.0, 0.0, 100.0),
        defect_bond_scale=f(p, "defectBondScale", 0.4, 0.0, 10.0),
        drive_mode=drive if drive in {"none","sin","pulse","beat","chirp"} else "sin",
        drive_amplitude=f(p, "driveAmplitude", 0.08, 0.0, 10.0),
        drive_frequency=f(p, "driveFrequency", 1.0, 0.0, 100.0),
        uniform_force_x=f(p, "uniformForceX", 0.0, -100.0, 100.0),
        stochastic_mode=b(p, "stochasticMode", False), temperature_reduced=f(p, "temperatureReduced", 0.0, 0.0, 100.0),
        seed=i(p, "seed", 12345, 0, 2147483647), initial_displacement=f(p, "initialDisplacement", 0.01, 0.0, 10.0),
        duration=f(p, "duration", 8.0, 1.0, 200.0), samples=i(p, "samples", 420, 64, 20000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5), atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        max_step=f(p, "maxStep", 0.03, 0.0001, 1.0), langevin_dt=f(p, "langevinDt", 0.005, 1e-5, 0.2),
    )



def _context_result(p: dict[str, Any]) -> dict[str, Any]:
    value = p.get("contextResult")
    if not isinstance(value, dict):
        raise ValueError("Run the experiment first so this analysis tool has a current structured result.")
    return value


def _first_numeric_series(context: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    for series in context.get("series") or []:
        if not isinstance(series, dict):
            continue
        x = np.asarray(series.get("x") or [], dtype=float).reshape(-1)
        y = np.asarray(series.get("y") or [], dtype=float).reshape(-1)
        n = min(len(x), len(y))
        if n >= 3:
            x, y = x[:n], y[:n]
            mask = np.isfinite(x) & np.isfinite(y)
            if int(np.count_nonzero(mask)) >= 3:
                return x[mask], y[mask], series
    raise ValueError("The current result has no numeric x/y series with at least three finite points.")



def _result_frame_and_numeric_columns(context: dict[str, Any]):
    from physical_lab_visualization_studio import result_frame, numeric_columns
    frame = result_frame(context)
    columns = numeric_columns(frame)
    return frame, columns


def _varying_numeric_columns(frame, columns):
    import pandas as pd
    out = []
    for col in columns:
        values = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(values) >= 3 and int(values.nunique()) >= 2:
            out.append(col)
    return out


def run_global_analysis_tool(experiment_id: str, tool: str, p: dict[str, Any]) -> dict[str, Any]:
    context = _context_result(p)

    if tool in {"visualization-summary", "visualization-transform", "local-sensitivity", "elasticity-sensitivity", "standardized-sensitivity"}:
        import pandas as pd
        from physical_lab_visualization_studio import summary as visualization_summary, transform as visualization_transform
        from physical_lab_visual_analytics import local_sensitivity, elasticity_sensitivity, standardized_sensitivity
        frame, columns = _result_frame_and_numeric_columns(context)
        usable = [c for c in columns if c != "index"]
        if not usable:
            usable = list(columns)
        if tool == "visualization-summary":
            rows = visualization_summary(frame, columns)
            return result(experiment_id, "physical_lab_visualization_studio.summary", p,
                          {"rowCount": len(frame), "numericColumnCount": len(columns), "summaryFieldCount": len(rows)},
                          [], "Descriptive statistics summarize finite numeric fields in the current structured result; they do not add scientific validation.",
                          [{"id":"visual-summary","label":"Visualization summary","rows":rows}])
        if tool == "visualization-transform":
            chosen = usable[:min(4, len(usable))]
            mode = str(p.get("transformMode", "z-score"))
            if mode not in {"z-score","min-max","absolute","none"}:
                mode = "z-score"
            out = visualization_transform(frame, chosen, mode)
            series = []
            x = np.arange(len(out), dtype=float)
            for col in chosen:
                y = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=float)
                mask = np.isfinite(y)
                if int(np.count_nonzero(mask)) >= 2:
                    series.append(xy_series(f"transform-{col}", f"{col} · {mode}", x[mask], y[mask], x_label="row", y_label=col))
            return result(experiment_id, "physical_lab_visualization_studio.transform", p,
                          {"rowCount": len(out), "transformedColumns": len(chosen), "mode": mode},
                          series, "Transforms are visualization/analysis conveniences applied to a copy of the current result table; source results are not modified.",
                          [{"id":"transformed-preview","label":"Transformed result preview","rows":out.head(200).to_dict(orient="records")}])
        if len(usable) < 2:
            raise ValueError("Sensitivity analysis needs at least two varying numeric result fields.")
        parameter, output = usable[0], usable[1]
        if tool == "local-sensitivity":
            out = local_sensitivity(frame, parameter, output)
            rows = out.to_dict(orient="records")
            return result(experiment_id, "physical_lab_visual_analytics.local_sensitivity", p,
                          {"segments": len(rows), "parameter": parameter, "output": output},
                          [xy_series("local-sensitivity","local sensitivity",out["parameter_center"],out["sensitivity"],x_label=parameter,y_label=f"d({output})/d({parameter})")],
                          "Finite-difference local sensitivity is descriptive for the selected result fields and depends on the sampled parameter spacing.",
                          [{"id":"local-sensitivity","label":"Local sensitivity","rows":rows}])
        if tool == "elasticity-sensitivity":
            out = elasticity_sensitivity(frame, parameter, output)
            rows = out.to_dict(orient="records")
            finite = pd.to_numeric(out["elasticity"], errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
            return result(experiment_id, "physical_lab_visual_analytics.elasticity_sensitivity", p,
                          {"segments": len(rows), "parameter": parameter, "output": output, "maxAbsElasticity": float(finite.abs().max()) if len(finite) else None},
                          [xy_series("elasticity","elasticity sensitivity",out["parameter_center"],out["elasticity"],x_label=parameter,y_label="elasticity")],
                          "Elasticity is a local normalized sensitivity and is undefined where the output center is zero.",
                          [{"id":"elasticity","label":"Elasticity sensitivity","rows":rows}])
        varying = []
        for col in usable:
            values = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(values) >= 3 and int(values.nunique()) >= 2:
                varying.append(col)
        if len(varying) < 2:
            raise ValueError("Standardized sensitivity needs at least two varying numeric result fields.")
        parameter_candidates = varying[:-1]
        output = varying[-1]
        out = standardized_sensitivity(frame, parameter_candidates, output)
        rows = out.to_dict(orient="records")
        if not rows:
            raise ValueError("Standardized sensitivity found no fields with enough finite variation.")
        return result(experiment_id, "physical_lab_visual_analytics.standardized_sensitivity", p,
                      {"parameterCount": len(rows), "output": output, "largestAbsSlope": float(out["abs_standardized_slope"].max())},
                      [xy_series("standardized-sensitivity","standardized sensitivity",range(len(rows)),out["standardized_slope"],x_label="parameter rank",y_label="standardized slope")],
                      "Standardized slopes and Spearman coefficients summarize association in the current finite result table; they do not imply causation.",
                      [{"id":"standardized-sensitivity","label":"Standardized sensitivity","rows":rows}])

    if tool in {"polynomial-regression","monte-carlo-propagation","doe-design","parameter-estimation","polynomial-cv","pca-svd","conditioning-diagnostics","tikhonov","tsvd","correlation-matrix","pareto-frontier","robust-sensitivity","run-comparison","morris-design"}:
        import pandas as pd
        frame, columns = _result_frame_and_numeric_columns(context)
        varying = _varying_numeric_columns(frame, [c for c in columns if c != "index"])
        if tool == "monte-carlo-propagation":
            from physical_lab_applied_analysis import monte_carlo_propagation
            means=[0.0,1.0,2.0]; stds=[0.1,0.2,0.15]; coeff=[1.0,-0.5,0.25]
            out=monte_carlo_propagation(means=means,standard_uncertainties=stds,coefficients=coeff,samples=i(p,"monteCarloSamples",2000,100,20000),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis.monte_carlo_propagation",p,{"mean":out["mean"],"standardDeviation":out["standard_deviation"],"median":out["median"],"samples":out["samples"]},[xy_series("mc-distribution","Monte Carlo distribution",range(len(out["distribution"])),out["distribution"],x_label="sample",y_label="output")],out["boundary"])
        if tool == "doe-design":
            from physical_lab_applied_analysis import design_experiment
            factors=[{"name":"factor_a","low":-1.0,"high":1.0},{"name":"factor_b","low":0.0,"high":2.0}]
            out=design_experiment(factors,method=str(p.get("doeMethod","latin-hypercube")),samples=i(p,"doeSamples",24,2,256),seed=i(p,"analysisSeed",0,0,2147483647))
            design=out["design"]
            return result(experiment_id,"physical_lab_applied_analysis.design_experiment",p,{"rowCount":out["row_count"],"method":out["method"],"factorCount":len(out["factors"])},[],out["boundary"],[{"id":"doe-design","label":"DOE design","rows":design.to_dict(orient="records")}])
        if tool == "morris-design":
            from physical_lab_applied_analysis_advanced import morris_design
            factors=[{"name":"factor_a","low":-1.0,"high":1.0},{"name":"factor_b","low":0.0,"high":2.0}]
            out=morris_design(factors,trajectories=i(p,"morrisTrajectories",6,2,100),levels=i(p,"morrisLevels",6,4,20),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis_advanced.morris_design",p,{"rows":len(out["rows"]),"trajectories":out["trajectories"],"levels":out["levels"]},[],out["boundary"],[{"id":"morris-design","label":"Morris screening design","rows":out["rows"]}])
        if len(varying) < 2:
            raise ValueError(f"{tool} needs at least two varying numeric result fields.")
        xcol, ycol = varying[0], varying[-1]
        if tool == "polynomial-regression":
            from physical_lab_applied_analysis import polynomial_regression
            out=polynomial_regression(frame,xcol,ycol,degree=i(p,"polynomialDegree",2,1,6))
            diag=out["diagnostics"]
            return result(experiment_id,"physical_lab_applied_analysis.polynomial_regression",p,{"degree":out["degree"],"rSquared":out["r2"],"rmse":out["rmse"],"rank":out["rank"]},[xy_series("poly-observed","observed",diag[xcol],diag["observed"],x_label=xcol,y_label=ycol,chart="scatter"),xy_series("poly-fit","polynomial fit",diag[xcol],diag["predicted"],x_label=xcol,y_label=ycol)],out["boundary"],[{"id":"coefficients","label":"Polynomial coefficients","rows":out["coefficients"]}])
        if tool == "parameter-estimation":
            from physical_lab_applied_analysis import estimate_parameters
            out=estimate_parameters(frame,xcol,ycol,model=str(p.get("parameterModel","linear")))
            diag=out["diagnostics"]
            return result(experiment_id,"physical_lab_applied_analysis.estimate_parameters",p,{"model":out["model"],"rmse":out["rmse"],"mae":out["mae"],"n":out["n"]},[xy_series("parameter-observed","observed",diag[xcol],diag["observed"],x_label=xcol,y_label=ycol,chart="scatter"),xy_series("parameter-fit","estimated model",diag[xcol],diag["predicted"],x_label=xcol,y_label=ycol)],out["boundary"],[{"id":"parameters","label":"Estimated parameters","rows":out["parameters"]}])
        if tool == "polynomial-cv":
            from physical_lab_applied_analysis_advanced import cross_validate_polynomials
            out=cross_validate_polynomials(frame,xcol,ycol,degrees=(1,2,3),folds=min(5,max(2,len(frame)//4)),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis_advanced.cross_validate_polynomials",p,{"modelsCompared":len(out),"bestDegree":int(out.iloc[0]["degree"]) if len(out) else None,"bestCvRmse":float(out.iloc[0]["cv_rmse_mean"]) if len(out) else None},[], "Cross-validation compares predictive error among the specified polynomial families; it does not establish physical model truth.",[{"id":"polynomial-cv","label":"Polynomial cross-validation","rows":out.to_dict(orient="records")}])
        if tool == "pca-svd":
            from physical_lab_applied_math_deep import pca_svd
            chosen=varying[:min(4,len(varying))]
            out=pca_svd(frame,chosen,standardize=True,max_components=min(3,len(chosen)))
            return result(experiment_id,"physical_lab_applied_math_deep.pca_svd",p,{"rows":out["rows"],"effectiveRank":out["effective_rank"],"componentCount":len(out["explained_variance_ratio"])},[xy_series("pca-variance","explained variance",range(1,len(out["explained_variance_ratio"])+1),out["explained_variance_ratio"],x_label="component",y_label="explained variance ratio")],out["boundary"],[{"id":"pca-loadings","label":"PCA loadings","rows":out["loadings"].to_dict(orient="records")}])
        if tool == "conditioning-diagnostics":
            from physical_lab_applied_math_deep import conditioning_diagnostics
            chosen=varying[:min(4,len(varying))]
            out=conditioning_diagnostics(frame,chosen,center=True,standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.conditioning_diagnostics",p,{"rank":out["rank"],"columnCount":out["column_count"],"fullColumnRank":out["full_column_rank"],"conditionNumber":out["condition_number"]},[xy_series("singular-values","singular values",range(1,len(out["singular_values"])+1),out["singular_values"],x_label="index",y_label="singular value")],out["boundary"])
        predictors=varying[:-1][:min(3,len(varying)-1)]
        response=varying[-1]
        if tool == "tikhonov":
            from physical_lab_applied_math_deep import tikhonov_regression
            out=tikhonov_regression(frame,predictors,response,regularization=f(p,"regularization",1e-3,0.0,1e6),standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.tikhonov_regression",p,{"rmse":out["rmse"],"mae":out["mae"],"dataResidualNorm":out["data_residual_norm"],"regularizationNorm":out["regularization_norm"]},[],out["boundary"],[{"id":"tikhonov-coefficients","label":"Tikhonov coefficients","rows":out["coefficients"]},{"id":"tikhonov-diagnostics","label":"Tikhonov diagnostics","rows":out["diagnostics"].to_dict(orient="records")}])
        if tool == "tsvd":
            from physical_lab_applied_math_deep import truncated_svd_regression
            rank=max(1,min(len(predictors),i(p,"tsvdRank",1,1,10)))
            out=truncated_svd_regression(frame,predictors,response,rank=rank,standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.truncated_svd_regression",p,{"rank":out["rank"],"maxRank":out["max_rank"],"rmse":out["rmse"],"dataResidualNorm":out["data_residual_norm"],"solutionNorm":out["solution_norm"]},[],out["boundary"],[{"id":"tsvd-coefficients","label":"TSVD coefficients","rows":out["coefficients"]},{"id":"tsvd-diagnostics","label":"TSVD diagnostics","rows":out["diagnostics"].to_dict(orient="records")}])
        if tool == "correlation-matrix":
            from physical_lab_tradeoff_analysis import correlation_matrix
            chosen=varying[:min(6,len(varying))]
            out=correlation_matrix(frame,chosen,method=str(p.get("correlationMethod","pearson")))
            rows=[{"field":idx,**{str(c):float(v) if pd.notna(v) else None for c,v in row.items()}} for idx,row in out.to_dict(orient="index").items()]
            return result(experiment_id,"physical_lab_tradeoff_analysis.correlation_matrix",p,{"fieldCount":len(chosen),"method":str(p.get("correlationMethod","pearson"))},[],"Correlation summarizes pairwise association in the current finite result table and does not imply causation.",[{"id":"correlation","label":"Correlation matrix","rows":rows}])
        if tool == "pareto-frontier":
            from physical_lab_tradeoff_analysis import pareto_frontier
            out=pareto_frontier(frame,x=xcol,x_goal="min",y=ycol,y_goal="max")
            return result(experiment_id,"physical_lab_tradeoff_analysis.pareto_frontier",p,{"points":len(out),"paretoPoints":int(out["pareto"].sum()) if "pareto" in out else 0,"xObjective":xcol,"yObjective":ycol},[xy_series("pareto-points","Pareto objective points",out[xcol],out[ycol],x_label=xcol,y_label=ycol,chart="scatter")],"Pareto membership depends on the selected objectives and directions; it is not a universal ranking.",[{"id":"pareto","label":"Pareto frontier","rows":out.to_dict(orient="records")}])
        if tool == "robust-sensitivity":
            from physical_lab_tradeoff_analysis import robust_sensitivity_summary
            out=robust_sensitivity_summary(frame,predictors,response)
            return result(experiment_id,"physical_lab_tradeoff_analysis.robust_sensitivity_summary",p,{"parameters":len(out),"response":response},[],"Robust sensitivity combines several descriptive diagnostics without creating a synthetic master score.",[{"id":"robust-sensitivity","label":"Robust sensitivity summary","rows":out.to_dict(orient="records")}])
        if tool == "run-comparison":
            from physical_lab_research_orchestrator import compare_numeric_runs
            rows=frame[varying[:min(5,len(varying))]].dropna().head(8).to_dict(orient="records")
            out=compare_numeric_runs(rows,baseline_index=0)
            return result(experiment_id,"physical_lab_research_orchestrator.compare_numeric_runs",p,{"runs":len(out["rows"]),"sharedMetrics":len(out["shared_metrics"]),"baselineIndex":out["baseline_index"]},[],out["boundary"],[{"id":"run-comparison","label":"Run comparison","rows":out["rows"]}])

    if tool == "result-inspector":
        from physical_lab_result_inspector import inspect_result, numerical_sanity_report
        inspection = inspect_result(context)
        sanity = numerical_sanity_report(context)
        inventory = inspection.get("inventory") or []
        checks = sanity.get("checks") or []
        metrics = {
            "fieldCount": len(inventory),
            "numericFieldCount": sum(1 for row in inventory if row.get("classification") in {"scalar", "vector", "matrix"}),
            "sanityCheckCount": len(checks),
            "warningCount": sum(1 for row in checks if str(row.get("severity")).lower() in {"warning", "error"}),
        }
        tables = [
            {"id": "schema-inventory", "label": "Result schema inventory", "rows": inventory[:250]},
            {"id": "sanity-checks", "label": "Numerical sanity checks", "rows": checks[:250]},
        ]
        return result(experiment_id, "physical_lab_result_inspector", p, metrics, [],
                      "Structural inspection and numerical sanity checks summarize the current result contract; they do not independently validate the underlying physical model.", tables)

    if tool == "bootstrap":
        from physical_lab_applied_analysis import bootstrap_statistic
        x, y, series = _first_numeric_series(context)
        out = bootstrap_statistic(
            y,
            statistic=str(p.get("bootstrapStatistic", "mean")),
            resamples=i(p, "bootstrapResamples", 1500, 100, 20000),
            confidence=f(p, "bootstrapConfidence", 0.95, 0.5, 0.999),
            seed=i(p, "analysisSeed", 0, 0, 2147483647),
        )
        interval = out.get("interval") or [None, None]
        metrics = {
            "estimate": out.get("estimate"),
            "confidenceLow": interval[0] if len(interval) > 0 else None,
            "confidenceHigh": interval[1] if len(interval) > 1 else None,
            "standardError": out.get("bootstrap_standard_error"),
            "sampleCount": out.get("n", len(y)),
            "resamples": out.get("resamples"),
        }
        return result(experiment_id, "physical_lab_applied_analysis.bootstrap_statistic", p, metrics, [],
                      "Bootstrap uncertainty here is conditional on the selected finite result series and resampling protocol; it does not include omitted model-form or measurement uncertainty.")

    if tool in {"regression", "robust-regression"}:
        import pandas as pd
        x, y, series = _first_numeric_series(context)
        frame = pd.DataFrame({"x": x, "y": y})
        if tool == "regression":
            from physical_lab_applied_analysis import regression_diagnostics
            out = regression_diagnostics(frame, ["x"], "y", include_intercept=True)
            coeff_rows = out.get("coefficients") or []
            coeff = {str(row.get("term")): row.get("estimate") for row in coeff_rows if isinstance(row, dict)}
            metrics = {
                "rSquared": out.get("r2"),
                "adjustedRSquared": out.get("adjusted_r2"),
                "rmse": out.get("rmse"),
                "mae": out.get("mae"),
                "conditionNumber": out.get("condition_number"),
                "intercept": coeff.get("intercept"),
                "slope": coeff.get("x"),
            }
            series_out = [xy_series("fit-data", str(series.get("label") or "data"), x, y, x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y"), chart="scatter")]
            diagnostics = out.get("diagnostics")
            if diagnostics is not None and hasattr(diagnostics, "columns") and "predicted" in diagnostics.columns:
                series_out.append(xy_series("linear-fit", "linear fit", x, diagnostics["predicted"].to_numpy(dtype=float), x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y")))
            tables = [{"id":"coefficients","label":"Regression coefficients","rows":coeff_rows}]
            if diagnostics is not None and hasattr(diagnostics, "to_dict"):
                tables.append({"id":"diagnostics","label":"Regression diagnostics","rows":diagnostics.to_dict(orient="records")})
            return result(experiment_id, "physical_lab_applied_analysis.regression_diagnostics", p, metrics, series_out,
                          out.get("boundary") or "Ordinary least-squares diagnostics summarize the selected current result series; residual structure and model assumptions still require interpretation.", tables)
        from physical_lab_applied_analysis_advanced import robust_regression_huber
        out = robust_regression_huber(frame, ["x"], "y", delta=f(p, "huberDelta", 1.345, 0.1, 20.0))
        coeff_rows = out.get("coefficients") or []
        coeff = {str(row.get("term")): row.get("estimate") for row in coeff_rows if isinstance(row, dict)}
        metrics = {
            "intercept": coeff.get("intercept"),
            "slope": coeff.get("x"),
            "rmse": out.get("rmse"),
            "mae": out.get("mae"),
            "downweightedFraction": out.get("downweighted_fraction"),
            "iterations": out.get("iterations"),
            "converged": out.get("converged"),
        }
        diagnostics = out.get("diagnostics")
        series_out = [xy_series("robust-data", str(series.get("label") or "data"), x, y, x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y"), chart="scatter")]
        if diagnostics is not None and hasattr(diagnostics, "columns") and "predicted" in diagnostics.columns:
            series_out.append(xy_series("robust-fit", "Huber fit", x, diagnostics["predicted"].to_numpy(dtype=float), x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y")))
        tables = [{"id":"coefficients","label":"Huber coefficients","rows":coeff_rows}]
        if diagnostics is not None and hasattr(diagnostics, "to_dict"):
            tables.append({"id":"diagnostics","label":"Huber diagnostics","rows":diagnostics.to_dict(orient="records")})
        return result(experiment_id, "physical_lab_applied_analysis_advanced.robust_regression_huber", p, metrics,
                      series_out, out.get("boundary") or "Huber regression is a robust descriptive fit for the selected result series; it does not establish the correct physical functional form.", tables)

    if tool == "convergence-diagnostics":
        from physical_lab_research_orchestrator import convergence_diagnostics
        x, y, series = _first_numeric_series(context)
        if len(y) < 4:
            raise ValueError("Convergence diagnostics need at least four finite points.")
        reference = float(y[-1])
        error = np.abs(y - reference)
        resolution = np.arange(1, len(y) + 1, dtype=float)
        usable = error > max(1e-15, np.finfo(float).eps)
        if int(np.count_nonzero(usable)) < 3:
            usable = np.ones_like(error, dtype=bool)
            error = np.maximum(error, 1e-15)
        out = convergence_diagnostics(resolution[usable], error[usable])
        metrics = {
            "observedOrder": out.get("observed_order"),
            "loglogRSquared": out.get("loglog_r2"),
            "errorModelPrefactor": out.get("error_model_prefactor"),
            "finestResolution": out.get("finest_resolution"),
            "finestError": out.get("finest_error"),
            "referenceValue": reference,
        }
        return result(experiment_id, "physical_lab_research_orchestrator.convergence_diagnostics", p, metrics,
                      [xy_series("convergence-error", "distance from final sample", resolution, error, x_label="sample index", y_label="absolute difference")],
                      "This convenience diagnostic treats the final series value as a reference and sample index as a resolution proxy. Use an explicit refinement study when the x-axis is not a true numerical resolution parameter.")

    raise ValueError(f"Unsupported global analysis tool: {tool}")


def run_experiment_tool(experiment_id: str, tool: str, p: dict[str, Any], mode: str) -> dict[str, Any]:
    if tool in {"result-inspector", "bootstrap", "regression", "robust-regression", "convergence-diagnostics", "visualization-summary", "visualization-transform", "local-sensitivity", "elasticity-sensitivity", "standardized-sensitivity", "polynomial-regression", "monte-carlo-propagation", "doe-design", "parameter-estimation", "polynomial-cv", "pca-svd", "conditioning-diagnostics", "tikhonov", "tsvd", "correlation-matrix", "pareto-frontier", "robust-sensitivity", "run-comparison", "morris-design"}:
        return run_global_analysis_tool(experiment_id, tool, p)
    if experiment_id == "numerical-methods" and tool in {"parameter-scan","single-point-convergence","method-comparison","compliance"}:
        from numerical_lab.core import Method, ReferenceBackend, scan_sine, summarize_scan, sine_taylor, convergence_scan, machine_epsilon
        method=Method(str(p.get("method","range_reduced"))); dtype=str(p.get("dtype","float64"))
        backend=ReferenceBackend(str(p.get("referenceBackend","mpmath"))); digits=i(p,"referencePrecisionDigits",80,20,200)
        tol=f(p,"toleranceMultiplier",8.0,.1,1000.0); max_terms=i(p,"maxTerms",120,1,500)
        if tool=="parameter-scan":
            return numerical_methods(p,mode)
        if tool=="single-point-convergence":
            x=f(p,"singleX",1.5,-100.0,100.0); terms=i(p,"convergenceTerms",60,2,300)
            single=sine_taylor(x,method=method,dtype=dtype,tolerance_multiplier=tol,max_terms=max_terms,reference_backend=backend,reference_precision_digits=digits)
            conv=convergence_scan(x,method=method,dtype=dtype,max_terms=terms,reference_backend=backend,reference_precision_digits=digits)
            return result(experiment_id,"pinned-numerical_lab.single-point",p,{
                "approximation":single.value,"reference":single.reference,"absoluteError":single.absolute_error,
                "normalizedError":single.normalized_error,"termsUsed":single.terms_used,"lastTerm":single.last_term,
                "cancellationRatio":single.cancellation_ratio,"ulpError":single.ulp_error,
                "stoppingCriterionMet":single.stopping_criterion_met,"accuracyPassed":single.accuracy_passed,
                "numericallyReliable":single.numerically_reliable,"falseConvergence":single.false_convergence,
            },[
                xy_series("absolute-error","absolute error",conv["terms"],conv["absolute_error"],x_label="Taylor terms",y_label="absolute error"),
                xy_series("last-term","last Taylor term",conv["terms"],np.abs(conv["last_term"]),x_label="Taylor terms",y_label="|last term|"),
            ],"Pinned scalar Taylor evaluation and convergence study using the configured arithmetic/reference engine.",[{"id":"convergence","label":"Complete convergence data","rows":[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in conv.items()} for idx in range(len(conv["terms"]))]}])
        if tool=="method-comparison":
            x=np.linspace(f(p,"xMin",-8.0,-100,100),f(p,"xMax",8.0,-100,100),i(p,"points",401,21,5001))
            reduced=scan_sine(x,method=Method.RANGE_REDUCED,dtype=dtype,tolerance_multiplier=tol,max_terms=max_terms,reference_backend=backend,reference_precision_digits=digits)
            raw=scan_sine(x,method=Method.RAW,dtype=dtype,tolerance_multiplier=tol,max_terms=max_terms,reference_backend=backend,reference_precision_digits=digits)
            sr=summarize_scan(reduced); sw=summarize_scan(raw)
            rows=[{"method":"range_reduced",**clean(sr)},{"method":"raw",**clean(sw)}]
            return result(experiment_id,"pinned-numerical_lab.method-comparison",p,{
                "rangeReducedMaxError":sr["maximum_absolute_error"],"rawMaxError":sw["maximum_absolute_error"],
                "rangeReducedFalseConvergence":sr["false_convergence_count"],"rawFalseConvergence":sw["false_convergence_count"],
            },[
                xy_series("reduced-error","range-reduced absolute error",x,reduced["absolute_error"],x_label="x (rad)",y_label="absolute error"),
                xy_series("raw-error","raw Taylor absolute error",x,raw["absolute_error"],x_label="x (rad)",y_label="absolute error"),
            ],"Same scan/reference settings for raw and range-reduced Taylor evaluation.",[{"id":"comparison","label":"Method comparison","rows":rows}])
        xs=np.asarray([-80,-20,-math.pi,-1,0,1,math.pi,20,80],dtype=float)
        checks=scan_sine(xs,method=method,dtype=dtype,tolerance_multiplier=tol,max_terms=max_terms,reference_backend=backend,reference_precision_digits=digits)
        rows=[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in checks.items()} for idx in range(len(xs))]
        return result(experiment_id,"pinned-numerical_lab.validation",p,{
            "machineEpsilon":machine_epsilon(dtype),"validationPoints":len(xs),
            "reliabilityRate":float(np.mean(checks["numerically_reliable"])),
            "falseConvergenceCount":int(np.sum(checks["false_convergence"])),
        },[xy_series("validation-error","validation absolute error",xs,checks["absolute_error"],x_label="x (rad)",y_label="absolute error")],
        "Built-in numerical compliance samples representative small and cancellation-prone arguments; it is evidence for this implementation/configuration, not a proof over all real inputs.",[{"id":"validation","label":"Validation points","rows":rows}])

    if experiment_id == "ising-monte-carlo" and tool in {"method-comparison","equilibration","multi-chain","scan-1d","scan-2d","finite-size","snapshot","compliance"}:
        from ising_lab.core import IsingParams, simulate, method_comparison, multi_chain_convergence, thermodynamic_scan, finite_size_scan, exact_observables, notebook_temperature_grid, all_plus_energy
        params=IsingParams(size=i(p,"size",24,4,256),coupling=f(p,"coupling",1.0,-10,10),field=f(p,"field",0.0,-10,10),temperature=f(p,"temperature",2.269,.01,20),dimension=i(p,"dimension",2,1,2))
        seed=i(p,"seed",2026,0,2147483647); method=str(p.get("scanMethod","wolff")); measure_every=i(p,"measureEvery",1,1,1000)
        if tool=="method-comparison":
            out=method_comparison(params,equilibration_sweeps=i(p,"comparisonEquilibration",300,0,100000),measurement_sweeps=i(p,"comparisonMeasurement",600,1,100000),measure_every=measure_every,seed=seed)
            rows=[]; series=[]
            for name,data in out.items():
                if name=="analytic": rows.append({"method":"analytic",**{k:clean(v) for k,v in data.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))}}); continue
                rows.append({"method":name,**{k:clean(v) for k,v in data.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))}})
                series.append(xy_series(name+"-energy",name+" energy",data["trajectory_work_units"],data["trajectory_energy"],x_label="work units",y_label="E/N"))
            return result(experiment_id,"pinned-ising_lab.method_comparison",p,{"methods":len(out)-1},series,"Pinned four-method comparison plus independent exact reference where available.",[{"id":"methods","label":"Method metrics","rows":rows}])
        if tool=="equilibration":
            out=simulate(params,method=method,equilibration_sweeps=0,measurement_sweeps=i(p,"diagnosticCycles",1000,10,100000),measure_every=1,seed=seed,record_every=i(p,"recordEvery",10,1,1000))
            from ising_lab.core import equilibration_diagnostics
            diag=equilibration_diagnostics(np.asarray(out["trajectory_energy"]),int(out["record_stride"]))
            return result(experiment_id,"pinned-ising_lab.equilibration",p,{**{k:clean(v) for k,v in diag.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))}},[
                xy_series("eq-energy","energy per site",out["trajectory_work_units"],out["trajectory_energy"],x_label="work units",y_label="E/N"),
                xy_series("eq-mag","magnetization per site",out["trajectory_work_units"],out["trajectory_magnetization"],x_label="work units",y_label="M/N"),
            ],"Plateau and autocorrelation diagnostics support equilibration assessment but do not prove global mixing.",[{"id":"equilibration-diagnostics","label":"Equilibration diagnostics","rows":[clean(diag)]}])
        if tool=="multi-chain":
            out=multi_chain_convergence(params,method=method,equilibration_sweeps=i(p,"equilibrationSweeps",400,0,100000),measurement_sweeps=i(p,"measurementSweeps",800,1,100000),measure_every=measure_every,seed=seed)
            return result(experiment_id,"pinned-ising_lab.multi_chain_convergence",p,{"rhatEnergy":out["rhat_energy"],"rhatAbsMagnetization":out["rhat_abs_magnetization"],"samplesPerChain":out["samples_per_chain"]},[],str(out["interpretation"]),[{"id":"chains","label":"Multi-chain diagnostics","rows":clean(out["chains"])}])
        if tool in {"scan-1d","scan-2d"}:
            dim=1 if tool=="scan-1d" else 2
            current=IsingParams(size=params.size,coupling=params.coupling,field=params.field,temperature=params.temperature,dimension=dim)
            if b(p,"useNotebookMesh",False) and dim==2:
                temps=np.asarray(notebook_temperature_grid(),dtype=float)
            else:
                temps=np.linspace(f(p,"tMin",1.0,.01,20),f(p,"tMax",4.0,.02,20),i(p,"scanPoints",21,3,201))
            out=thermodynamic_scan(temps,current,method=method,equilibration_sweeps=i(p,"equilibrationSweeps",400,0,100000),measurement_sweeps=i(p,"measurementSweeps",800,1,100000),measure_every=measure_every,seed=seed)
            rows=[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items()} for idx in range(len(temps))]
            return result(experiment_id,"pinned-ising_lab.thermodynamic_scan",p,{"dimension":dim,"points":len(temps)},[
                xy_series("scan-energy","energy per site",out["temperature"],out["energy_per_site"],x_label="T",y_label="E/N"),
                xy_series("scan-mag","|M|/N",out["temperature"],out["mean_abs_magnetization"],x_label="T",y_label="|M|/N"),
                xy_series("scan-heat","specific heat",out["temperature"],out["specific_heat"],x_label="T",y_label="C"),
                xy_series("scan-susc","susceptibility",out["temperature"],out["susceptibility_standard"],x_label="T",y_label="chi"),
            ],"Finite-temperature Monte Carlo scan with exact/reference columns supplied by the pinned Ising core.",[{"id":"temperature-scan","label":"Thermodynamic scan","rows":rows}])
        if tool=="finite-size":
            sizes=[]
            for token in str(p.get("latticeSizes","8,12,16,24,32")).split(","):
                token=token.strip()
                if token: sizes.append(int(token))
            out=finite_size_scan(np.asarray(sizes,dtype=int),params,method=method,equilibration_sweeps=i(p,"equilibrationSweeps",400,0,100000),measurement_sweeps=i(p,"measurementSweeps",800,1,100000),measure_every=measure_every,seed=seed)
            rows=[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items()} for idx in range(len(out["size"]))]
            return result(experiment_id,"pinned-ising_lab.finite_size_scan",p,{"sizes":len(rows)},[
                xy_series("finite-mag","|M|/N",out["size"],out["mean_abs_magnetization"],x_label="N",y_label="|M|/N"),
                xy_series("finite-energy","E/N",out["size"],out["energy_per_site"],x_label="N",y_label="E/N"),
            ],"Finite-size scan is not a thermodynamic-limit extrapolation unless a justified scaling model is applied.",[{"id":"finite-size","label":"Finite-size scan","rows":rows}])
        if tool=="snapshot":
            out=simulate(params,method=method,equilibration_sweeps=i(p,"snapshotSweeps",200,0,100000),measurement_sweeps=1,measure_every=1,initial=str(p.get("initialCondition","random")),seed=seed,record_every=max(1,i(p,"recordEvery",10,1,1000)))
            cfg=np.asarray(out["final_config"])
            rows=[{"row":idx,"spins":" ".join(str(int(v)) for v in np.asarray(row).ravel())} for idx,row in enumerate(cfg if cfg.ndim>1 else [cfg])]
            return result(experiment_id,"pinned-ising_lab.snapshot",p,{"shape":list(cfg.shape),"magnetizationPerSite":float(np.mean(cfg))},[],"Single finite seeded lattice realization.",[{"id":"snapshot","label":"Lattice snapshot","rows":rows}])
        exact=exact_observables(params)
        plus=all_plus_energy(params)
        return result(experiment_id,"pinned-ising_lab.compliance",p,{
            "exactEnergyPerSite":clean(exact.get("energy_per_site")),"exactMagnetization":clean(exact.get("magnetization")),"allPlusEnergy":clean(plus),
        },[],"Pinned exact/reference compliance values for the configured finite model.",[{"id":"exact-reference","label":"Exact/reference observables","rows":[clean(exact)]}])

    if experiment_id == "random-walk-monte-carlo" and tool in {"ensemble","trajectory","parameter-scan","repeated-mc","convergence-scan","high-d-mc","qmc","theory-volume","return-probability","first-passage","grid-vs-mc","reproducibility","validate-preset"}:
        from rw_mc_studio.random_walk import simulate_endpoints, summarize_endpoints, simulate_trajectory, return_probability
        from rw_mc_studio.scans import random_walk_scan, mc_convergence_scan
        from rw_mc_studio.monte_carlo import repeated_circle_trials, nd_ball_volume_mc, theoretical_nd_ball_volume, grid_circle_area, grid_sphere_volume, circle_area_mc
        from rw_mc_studio.advanced import repeated_scrambled_qmc, first_passage_1d, multi_seed_random_walk
        seed=i(p,"seed",12345,0,2147483647); dim=i(p,"dimension",2,1,50); steps=i(p,"steps",1000,1,1000000); walkers=i(p,"walkers",10000,1,1000000)
        model=str(p.get("stepModel","fixed")); pa=f(p,"fixedStep",1.0,.0001,100.0) if model=="fixed" else f(p,"uniformA",.5,0,100); pb=None if model=="fixed" else f(p,"uniformB",1.5,.0001,100)
        if tool=="ensemble":
            return random_walk(p,mode)
        if tool=="trajectory":
            tr=simulate_trajectory(dim,i(p,"trajectorySteps",500,1,100000),model,pa,pb,seed=seed)
            series=[xy_series("trajectory-x","x coordinate",range(len(tr)),tr[:,0],x_label="step",y_label="x")]
            if dim>=2: series.append(xy_series("trajectory-xy","trajectory",tr[:,0],tr[:,1],x_label="x",y_label="y",chart="scatter"))
            return result(experiment_id,"pinned-rw_mc_studio.simulate_trajectory",p,{"steps":len(tr)-1,"dimension":dim},series,"One seeded trajectory; ensemble claims require repeated independent walkers.")
        if tool=="parameter-scan":
            vals=[float(x.strip()) for x in str(p.get("scanValues","100,300,1000,3000")).split(",") if x.strip()]
            base_model=str(p.get("baseStepModel","fixed")); p1=f(p,"baseFixedStep",1,.0001,100) if base_model=="fixed" else f(p,"baseUniformA",.5,0,100); p2=None if base_model=="fixed" else f(p,"baseUniformB",1.5,.0001,100)
            frame=random_walk_scan(vals,scan_variable=str(p.get("scanVariable","n_steps")),dim=i(p,"baseDimension",2,1,50),n_steps=i(p,"baseSteps",1000,1,1000000),n_walkers=i(p,"baseWalkers",10000,1,1000000),model=base_model,p1=p1,p2=p2,seed=seed)
            rows=frame.to_dict(orient="records"); axis=str(p.get("scanVariable","n_steps"))
            return result(experiment_id,"pinned-rw_mc_studio.random_walk_scan",p,{"points":len(rows)},[xy_series("scan-msd","MSD",frame[axis],frame["msd"],x_label=axis,y_label="MSD")], "Pinned batch parameter scan.",[{"id":"scan","label":"Random-walk parameter scan","rows":rows}])
        if tool=="repeated-mc":
            out=repeated_circle_trials(i(p,"samplesPerTrial",10000,10,10000000),i(p,"independentTrials",100,2,10000),seed)
            return result(experiment_id,"pinned-rw_mc_studio.repeated_circle_trials",p,{k:clean(v) for k,v in out.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))},[],"Repeated unit-disk Monte Carlo estimates quantify run-to-run sampling variation.",[{"id":"repeated-mc","label":"Repeated Monte Carlo summary","rows":[clean(out)]}])
        if tool=="convergence-scan":
            vals=[int(float(x.strip())) for x in str(p.get("sampleCounts","100,300,1000,3000,10000")).split(",") if x.strip()]
            frame=mc_convergence_scan(vals,n_trials=i(p,"trialsPerCount",50,2,1000),seed=seed)
            return result(experiment_id,"pinned-rw_mc_studio.mc_convergence_scan",p,{"points":len(frame)},[xy_series("mc-rmse","RMSE",frame["n_samples"],frame["rmse"],x_label="samples",y_label="RMSE")],"Monte Carlo convergence across independent trial counts.",[{"id":"convergence","label":"MC convergence","rows":frame.to_dict(orient="records")}])
        if tool=="high-d-mc":
            out=nd_ball_volume_mc(dim,i(p,"pseudoRandomSamples",100000,100,10000000),seed=seed)
            return result(experiment_id,"pinned-rw_mc_studio.nd_ball_volume_mc",p,{**{k:clean(v) for k,v in out.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))},"theoreticalVolume":theoretical_nd_ball_volume(dim)},[],"Pseudo-random Monte Carlo estimate of the unit d-ball volume.",[{"id":"high-d","label":"High-dimensional MC","rows":[clean(out)]}])
        if tool=="qmc":
            out=repeated_scrambled_qmc(dim,power=i(p,"qmcPower",14,4,24),n_replicates=i(p,"qmcScrambles",8,2,128),seed=seed)
            rows=out.get("replicates") if isinstance(out,dict) else None
            if not isinstance(rows,list): rows=[clean(out)]
            return result(experiment_id,"pinned-rw_mc_studio.repeated_scrambled_qmc",p,{k:clean(v) for k,v in out.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))},[],"Repeated scrambled Sobol QMC provides randomized-QMC uncertainty evidence, not deterministic error bounds.",[{"id":"qmc","label":"Repeated QMC","rows":clean(rows)}])
        if tool=="theory-volume":
            dims=np.arange(1,51); vols=[theoretical_nd_ball_volume(int(d)) for d in dims]
            return result(experiment_id,"pinned-rw_mc_studio.theoretical_nd_ball_volume",p,{"dimensions":50},[xy_series("volume-curve","unit d-ball volume",dims,vols,x_label="dimension",y_label="volume")],"Exact unit d-ball volume formula.",[{"id":"volume-curve","label":"Theoretical volumes","rows":[{"dimension":int(d),"volume":float(v)} for d,v in zip(dims,vols)]}])
        if tool=="return-probability":
            out=return_probability(dim,max_steps=i(p,"horizon",5000,1,1000000),n_trials=i(p,"independentTrajectories",1000,1,100000),seed=seed)
            return result(experiment_id,"pinned-rw_mc_studio.return_probability",p,{k:clean(v) for k,v in out.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))},[],"Finite-horizon return probability; non-return by H is censoring, not proof of transience.",[{"id":"return","label":"Return probability","rows":[clean(out)]}])
        if tool=="first-passage":
            out=first_passage_1d(i(p,"boundaryMagnitude",10,1,10000),n_trials=i(p,"trials",5000,1,1000000),max_steps=i(p,"maxSteps",100000,1,10000000),seed=seed)
            times=np.asarray(out.get("hit_times",[]),dtype=float)
            series=[xy_series("hit-times","first-passage hit times",range(len(times)),times,x_label="hit index",y_label="steps")] if len(times) else []
            return result(experiment_id,"pinned-rw_mc_studio.first_passage_1d",p,{k:clean(v) for k,v in out.items() if isinstance(v,(int,float,str,bool,np.integer,np.floating))},series,"Finite-horizon first-passage experiment with right/left absorbing boundaries.",[{"id":"first-passage","label":"First-passage summary","rows":[{k:clean(v) for k,v in out.items() if k!="hit_times"}]}])
        if tool=="grid-vs-mc":
            k2=i(p,"grid2d",500,10,5000); k3=i(p,"grid3d",100,5,1000)
            grid2=grid_circle_area(k2); grid3=grid_sphere_volume(k3)
            mc2=circle_area_mc(k2*k2,seed=seed); mc3=nd_ball_volume_mc(3,k3**3,seed=seed+1)
            rows=[{"method":"2D midpoint grid","estimate":clean(grid2),"evaluations":k2*k2},{"method":"2D MC","estimate":clean(mc2.get("estimate",mc2.get("mean_estimate"))),"evaluations":k2*k2},{"method":"3D midpoint grid","estimate":clean(grid3),"evaluations":k3**3},{"method":"3D MC","estimate":clean(mc3.get("estimate",mc3.get("mean_estimate"))),"evaluations":k3**3}]
            return result(experiment_id,"pinned-rw_mc_studio.grid-vs-mc",p,{"comparisons":4},[],"Equal-evaluation-count comparison between deterministic midpoint grids and Monte Carlo.",[{"id":"grid-vs-mc","label":"Grid vs Monte Carlo","rows":rows}])
        if tool=="reproducibility":
            seeds=[seed+j for j in range(i(p,"independentSeeds",8,2,128))]
            audit_model=str(p.get("auditStepModel","fixed")); ap1=f(p,"fixedStep",1,.0001,100) if audit_model=="fixed" else f(p,"uniformA",.5,0,100); ap2=None if audit_model=="fixed" else f(p,"uniformB",1.5,.0001,100)
            out=multi_seed_random_walk(dim,i(p,"multiSeedSteps",1000,1,1000000),i(p,"walkersPerSeed",5000,1,1000000),seeds,audit_model,ap1,ap2)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else clean(out if isinstance(out,list) else [out])
            return result(experiment_id,"pinned-rw_mc_studio.multi_seed_random_walk",p,{"seeds":len(seeds)},[],"Multi-seed reproducibility audit quantifies seed-to-seed variation.",[{"id":"reproducibility","label":"Reproducibility audit","rows":rows}])
        from rw_mc_studio.presets import loads_preset
        out=loads_preset(str(p.get("presetJson","{}")))
        return result(experiment_id,"pinned-rw_mc_studio.loads_preset",p,{"valid":True,"schemaVersion":out.get("schema_version",3)},[],"Preset parser validates schema/required fields only; it does not execute the configuration.",[{"id":"preset","label":"Validated preset","rows":[clean(out)]}])

    if experiment_id == "nonlinear-chaos" and tool in {"driven-scan","kapitza-scan","double-trajectory","mass-response","lyapunov","lyapunov-convergence","flip-map","compliance"}:
        from chaos_lab.core import DoublePendulumParams, driven_poincare_scan, kapitza_stability_scan, simulate_double_pendulum, double_pendulum_energy, double_pendulum_cartesian, double_pendulum_mass_response, lyapunov_benettin, lyapunov_convergence_scan, flip_time_map, step_convergence_diagnostic
        params=DoublePendulumParams(mass1=f(p,"mass1",1,.01,100),mass2=f(p,"mass2",1,.01,100),length1=f(p,"length1",1,.01,100),length2=f(p,"length2",1,.01,100),gravity=f(p,"gravity",9.81,.01,100),damping=f(p,"damping",.05,0,20))
        initial=np.asarray([f(p,"theta1",1.2,-2*math.pi,2*math.pi),f(p,"omega1",0,-100,100),f(p,"theta2",1,-2*math.pi,2*math.pi),f(p,"omega2",0,-100,100)])
        if tool=="driven-scan":
            amps=np.linspace(f(p,"driveMin",.2,0,10),f(p,"driveMax",1.5,0,10),i(p,"amplitudeScanPoints",25,3,201))
            out=driven_poincare_scan(amps,gamma=f(p,"damping",.05,0,20),omega0=1.0,drive_frequency=f(p,"driveFrequency",.65,.01,100),theta0=float(initial[0]),omega_initial=float(initial[1]),periods=i(p,"drivePeriods",500,10,5000),discard_periods=i(p,"discardPeriods",200,0,4000),steps_per_period=i(p,"rk4StepsPerPeriod",120,20,1000))
            return result(experiment_id,"pinned-chaos_lab.driven_poincare_scan",p,{"samples":len(out["theta"])},[xy_series("poincare","Poincare samples",out["theta"],out["omega"],x_label="theta",y_label="omega",chart="scatter")],"Pinned driven-pendulum Poincare amplitude scan.",[{"id":"poincare","label":"Poincare samples","rows":[{"driveAmplitude":float(a),"theta":float(t),"omega":float(w)} for a,t,w in zip(out["drive_amplitude"],out["theta"],out["omega"])]}])
        if tool=="kapitza-scan":
            amps=np.linspace(0,f(p,"kapitzaMaxAmplitude",.3,0,10),i(p,"amplitudeScanPoints",25,3,201))
            out=kapitza_stability_scan(amps,gravity=params.gravity,length=params.length1,drive_frequency=f(p,"driveFrequency",40,.01,100),damping=f(p,"damping",.08,0,20),periods=i(p,"kapitzaTotalPeriods",240,10,5000),discard_periods=i(p,"kapitzaDiscardedPeriods",160,0,4000),steps_per_period=i(p,"rk4StepsPerPeriod",120,20,1000))
            return result(experiment_id,"pinned-chaos_lab.kapitza_stability_scan",p,{"samples":len(out["theta"])},[xy_series("kapitza","sampled angle",out["drive_amplitude"],out["theta"],x_label="pivot amplitude",y_label="theta",chart="scatter")],"Pinned Kapitza stabilization scan.",[])
        if tool=="double-trajectory":
            return nonlinear_chaos(p,mode)
        if tool=="mass-response":
            masses=np.linspace(f(p,"mass1Min",.5,.01,100),f(p,"mass1Max",2,.01,100),i(p,"massScanPoints",21,3,201))
            out=double_pendulum_mass_response(masses,params,initial_state=initial,duration=f(p,"massScanDuration",20,.1,1000),dt=f(p,"massScanDt",.01,1e-5,1))
            return result(experiment_id,"pinned-chaos_lab.double_pendulum_mass_response",p,{"points":len(out["mass1"])},[
                xy_series("mass-response","peak |theta2|",out["mass1"],out["peak_abs_theta2"],x_label="m1",y_label="peak |theta2|")
            ],"Pinned upper-mass response scan.",[{"id":"mass-response","label":"Mass response","rows":[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items()} for idx in range(len(out["mass1"]))]}])
        if tool=="lyapunov":
            out=lyapunov_benettin(initial,params,duration=f(p,"lyapunovDuration",40,.1,1000),dt=f(p,"lyapunovDt",.005,1e-5,1))
            return result(experiment_id,"pinned-chaos_lab.lyapunov_benettin",p,{"estimate":out["estimate"],"actualDt":out["actual_dt"]},[
                xy_series("lyap-cumulative","cumulative exponent",out["time"],out["cumulative_exponent"],x_label="time",y_label="lambda"),
                xy_series("lyap-local","local exponent",out["time"],out["local_exponent"],x_label="time",y_label="lambda local"),
            ],"Finite-time Benettin estimate with periodic renormalization; timestep sensitivity is required before interpretation.")
        if tool=="lyapunov-convergence":
            base=f(p,"lyapunovDt",.005,1e-5,1); dts=np.asarray([base*2,base,base/2])
            out=lyapunov_convergence_scan(dts,initial,params,duration=f(p,"lyapunovDuration",40,.1,1000))
            return result(experiment_id,"pinned-chaos_lab.lyapunov_convergence_scan",p,{"finestEstimate":out["finest_dt_estimate"],"relativeSpread":out["relative_spread"]},[xy_series("lyap-dt","Lyapunov estimate",out["actual_dt"],out["estimate"],x_label="dt",y_label="lambda")],"Timestep-sensitivity study for the finite-time Lyapunov estimate.",[{"id":"lyapunov-convergence","label":"Lyapunov convergence","rows":[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items() if isinstance(v,np.ndarray)} for idx in range(len(out["dt"]))]}])
        if tool=="flip-map":
            grid=i(p,"flipGrid",25,5,101); axis=np.linspace(-math.pi,math.pi,grid)
            zero_damped=DoublePendulumParams(params.mass1,params.mass2,params.length1,params.length2,params.gravity,0.0)
            out=flip_time_map(axis,axis,zero_damped,t_max=f(p,"flipMaxTime",60,.1,1000),dt=f(p,"flipDt",.02,.0001,1))
            finite=np.asarray(out["flip_time"]); frac=float(np.isfinite(finite).mean())
            return result(experiment_id,"pinned-chaos_lab.flip_time_map",p,{"grid":grid,"finiteFlipFraction":frac},[],"First-flip time map on the configured initial-angle grid.",[{"id":"flip-map","label":"Flip map","rows":[{"theta1":float(a),"theta2":float(bv),"flipTime":clean(finite[ii,jj])} for ii,a in enumerate(axis) for jj,bv in enumerate(axis)]}])
        zero_damped=DoublePendulumParams(params.mass1,params.mass2,params.length1,params.length2,params.gravity,0.0)
        diag=step_convergence_diagnostic(initial,zero_damped,duration=min(5.0,f(p,"duration",40,.1,1000)),dt=f(p,"dt",.005,1e-5,1))
        return result(experiment_id,"pinned-chaos_lab.step_convergence_diagnostic",p,clean(diag),[],"Pinned dt-versus-dt/2 state/energy compliance check.",[{"id":"compliance","label":"Compliance diagnostics","rows":[clean(diag)]}])

    if experiment_id == "oscillation-integration" and tool in {"method-comparison","timestep-scan","damping-regimes","resonance-scan","beat-analysis","nonlinear-amplitude","compliance"}:
        from oscillation_lab.core import OscillatorParams, Method, method_comparison, convergence_scan, analytic_free_response, resonance_scan, simulate_fixed, nonlinear_period_scan, energy_balance_diagnostic
        params=OscillatorParams(mass=f(p,"mass",1,.001,1000),omega0=f(p,"omega0",2*math.pi,.001,1000),gamma=f(p,"gamma",.1,0,100),force_amplitude=f(p,"force",1,0,1000),force_frequency=f(p,"driveOmega",6,0,1000))
        initial=np.asarray([f(p,"x0",1,-1000,1000),f(p,"v0",0,-1000,1000)])
        duration=f(p,"duration",20,.01,10000); dt=f(p,"dt",.01,1e-6,10)
        if tool=="method-comparison":
            out=method_comparison(initial,params,duration=duration,dt=dt); rows=[]; series=[]
            ref_key="analytic" if "analytic" in out else "dop853"; ref=np.asarray(out[ref_key]["state"])
            for name,data in out.items():
                st=np.asarray(data["state"]); tm=np.asarray(data["time"]); err=np.linalg.norm(st-np.asarray(out[ref_key]["state"]),axis=1) if st.shape==ref.shape else np.asarray([])
                rows.append({"method":name,"samples":len(tm),"actualDt":clean(data.get("actual_dt")),"maxStateError":float(np.max(err)) if len(err) else None})
                series.append(xy_series(name,name+" displacement",tm,st[:,0],x_label="time",y_label="u"))
            return result(experiment_id,"pinned-oscillation_lab.method_comparison",p,{"methods":len(rows),"reference":ref_key},series,"Pinned fixed-step methods compared with analytic/adaptive reference where applicable.",[{"id":"method-comparison","label":"Method comparison","rows":rows}])
        if tool=="timestep-scan":
            if params.force_amplitude!=0: params=OscillatorParams(params.mass,params.omega0,params.gamma,0.0,params.force_frequency)
            vals=np.geomspace(f(p,"dtMax",.1,1e-6,10),f(p,"dtMin",.001,1e-6,10),i(p,"scanPoints",9,3,101))
            out=convergence_scan(vals,initial,params,duration=duration,method=str(p.get("method","rk4")))
            rows=[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items() if isinstance(v,np.ndarray)} for idx in range(len(out["actual_dt"]))]
            return result(experiment_id,"pinned-oscillation_lab.convergence_scan",p,{"observedOrder":out["observed_order"]},[
                xy_series("convergence","maximum state error",out["actual_dt"],out["maximum_state_error"],x_label="actual dt",y_label="max state error")
            ],"Exact free-response convergence scan; forcing is disabled for this diagnostic.",[{"id":"convergence","label":"Timestep convergence","rows":rows}])
        if tool=="damping-regimes":
            times=np.linspace(0,max(duration,5*2*math.pi/params.omega0),1500); critical=2*params.omega0
            rows=[]; series=[]
            for name,gamma in {"Underdamped":.1*critical,"Critical":critical,"Overdamped":2.4*critical}.items():
                pp=OscillatorParams(params.mass,params.omega0,gamma,0.0,params.force_frequency); states=analytic_free_response(times,initial,pp)
                rows.append({"regime":name,"gamma":gamma}); series.append(xy_series(name,name,times,states[:,0],x_label="time",y_label="u"))
            return result(experiment_id,"pinned-oscillation_lab.analytic_free_response",p,{"regimes":3},series,"Analytic free-response damping regimes with identical initial conditions.",[{"id":"damping","label":"Damping regimes","rows":rows}])
        if tool=="resonance-scan":
            rp=OscillatorParams(params.mass,params.omega0,f(p,"resonanceGamma",.1,.000001,100),f(p,"resonanceForce",1,.000001,1000),params.force_frequency)
            freq=np.linspace(f(p,"omegaRatioMin",.2,.01,10)*params.omega0,f(p,"omegaRatioMax",2,.02,10)*params.omega0,i(p,"frequencyScanPoints",61,5,501))
            out=resonance_scan(freq,rp,initial_state=initial)
            return result(experiment_id,"pinned-oscillation_lab.resonance_scan",p,{"points":len(freq),"peakRatio":float(out["frequency_ratio"][int(np.argmax(out["numerical_amplitude"]))])},[
                xy_series("resonance-num","numerical amplitude",out["frequency_ratio"],out["numerical_amplitude"],x_label="Omega/omega0",y_label="amplitude"),
                xy_series("resonance-analytic","analytic amplitude",out["frequency_ratio"],out["analytic_amplitude"],x_label="Omega/omega0",y_label="amplitude"),
            ],"Pinned driven resonance scan; numerical settling must be checked via remaining-free-transient diagnostic.",[{"id":"resonance","label":"Resonance scan","rows":[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items()} for idx in range(len(freq))]}])
        if tool=="beat-analysis":
            bp=OscillatorParams(params.mass,params.omega0,0.0,max(f(p,"resonanceForce",1,.000001,1000),.001),params.force_frequency)
            out=simulate_fixed(initial,bp,duration=max(duration,30.0),dt=min(dt,.01),method=Method.RK4)
            delta=abs(bp.omega0-bp.force_frequency)
            return result(experiment_id,"pinned-oscillation_lab.beat-analysis",p,{"beatFrequencyHz":delta/(2*math.pi),"beatPeriod":None if delta==0 else 2*math.pi/delta},[xy_series("beat","driven response",out["time"],np.asarray(out["state"])[:,0],x_label="time",y_label="u")],"Near-resonant conservative beat analysis.")
        if tool=="nonlinear-amplitude":
            amps=np.linspace(.02,f(p,"maxInitialAngle",2.5,.01,3.13),i(p,"amplitudeScanPoints",31,5,301))
            out=nonlinear_period_scan(amps,params.omega0)
            return result(experiment_id,"pinned-oscillation_lab.nonlinear_period_scan",p,{"points":len(amps),"largestPeriodRatio":float(np.max(out["period_ratio"]))},[
                xy_series("nonlinear-period","exact nonlinear period",out["initial_amplitude"],out["exact_nonlinear_period"],x_label="theta0",y_label="period"),
                xy_series("numerical-period","numerical period",out["initial_amplitude"],out["numerical_period"],x_label="theta0",y_label="period"),
            ],"Pinned nonlinear pendulum period scan against elliptic-integral reference.",[{"id":"nonlinear","label":"Nonlinear period scan","rows":[{k:clean(np.asarray(v,dtype=object)[idx]) for k,v in out.items()} for idx in range(len(amps))]}])
        conservative=OscillatorParams(params.mass,params.omega0,0.0,0.0,params.force_frequency)
        out=simulate_fixed(initial,conservative,duration=min(duration,20.0),dt=dt,method=Method.RK4)
        diag=energy_balance_diagnostic(np.asarray(out["time"]),np.asarray(out["state"]),conservative)
        return result(experiment_id,"pinned-oscillation_lab.energy_balance_diagnostic",p,{"maxRelativeBalanceResidual":diag["max_relative_balance_residual"]},[
            xy_series("balance","energy-balance residual",out["time"],diag["balance_residual"],x_label="time",y_label="residual")
        ],"Pinned conservative energy-balance compliance diagnostic.")

    if experiment_id == "kerr-geodesics" and tool in {"refinement","comparison","spin-sweep"}:
        if tool == "comparison":
            from physical_lab_kerr_geodesics import KerrOrbitConfig, integrate_case, result_summary
            spin=f(p,"comparisonSpin",.6,0.0,.98); incl=f(p,"comparisonInclinationDeg",60.0,0.0,80.0)
            massive=integrate_case(KerrOrbitConfig(spin=spin,inclination_deg=incl,particle_type="massive",periapsis=6.5,apoapsis=10.0,lam_max=10.0,samples=1500))
            photon=integrate_case(KerrOrbitConfig(spin=spin,inclination_deg=incl,particle_type="photon",lam_max=3.0,samples=1000))
            ms=result_summary(massive); ps=result_summary(photon)
            rows=[{"particle":"massive",**ms},{"particle":"photon",**ps}]
            return result(experiment_id,"physical_lab_kerr_geodesics.integrate_case comparison",p,{"massiveResidual":ms["first_integral_residual_max"],"photonResidual":ps["first_integral_residual_max"]},[],"Massive/photon comparison uses independent Mino-time spans; compare geometry and invariants rather than synchronized physical time.",[{"id":"comparison","label":"Massive ↔ photon comparison","rows":rows}])
        if tool == "spin-sweep":
            from physical_lab_kerr_geodesics import KerrOrbitConfig, integrate_case, result_summary
            particle=str(p.get("sweepParticle","massive")).lower()
            if particle not in {"massive","photon"}: particle="massive"
            incl=f(p,"sweepInclinationDeg",60.0,0.0,80.0)
            values=[]
            for token in str(p.get("sweepSpinsText","0,0.15,0.30,0.45,0.60,0.75,0.90")).split(","):
                token=token.strip()
                if not token: continue
                value=float(token)
                if value < 0 or value >= 1: raise ValueError("Kerr sweep spins must be in [0,1)")
                if value not in values: values.append(value)
            if not values: raise ValueError("Enter at least one Kerr spin for the sweep")
            rows=[]
            for spin in sorted(values):
                cfg=KerrOrbitConfig(spin=spin,inclination_deg=incl,particle_type=particle,periapsis=6.5,apoapsis=10.0,lam_max=8.0 if particle=="massive" else 2.5,samples=900)
                rows.append(result_summary(integrate_case(cfg)))
            return result(experiment_id,"physical_lab_kerr_geodesics spin sweep",p,{"cases":len(rows),"particle":particle},[xy_series("r-min","r min",[r["spin"] for r in rows],[r["r_min"] for r in rows],x_label="a/M",y_label="r/M"),xy_series("r-max","r max",[r["spin"] for r in rows],[r["r_max"] for r in rows],x_label="a/M",y_label="r/M")],"Bounded Kerr spin sweep reuses the original integrate_case/result_summary core.",[{"id":"spin-sweep","label":"Kerr spin sweep","rows":rows}])

        from physical_lab_kerr_geodesics import run_refinement_pair
        out = run_refinement_pair(_kerr_config_from_params(p))
        tight = out["tight"]
        keys = list(out["absolute_deltas"].keys())
        return result(experiment_id, "physical_lab_kerr_geodesics.run_refinement_pair", p, {
            "tightResidual": out["tight_residual"],
            **{f"delta_{k}": v for k, v in out["absolute_deltas"].items()},
        }, [xy_series("refinement-deltas","absolute refinement deltas",range(len(keys)),[out["absolute_deltas"][k] for k in keys],x_label="diagnostic index",y_label="absolute delta")],
        "Loose-versus-tight numerical refinement check for the same Kerr configuration.", [{"id":"tight","label":"Tight result","rows":[tight]}])

    if experiment_id == "solar-system-dynamics" and tool in {"refinement","ftle"}:
        cfg = _solar_config_from_params(p)
        if tool == "refinement":
            from physical_lab_solar_system_dynamics import run_refinement_pair
            out = run_refinement_pair(cfg)
            keys=list(out["relative_changes"].keys())
            return result(experiment_id,"physical_lab_solar_system_dynamics.run_refinement_pair",p,{
                "maxRelativeChange":out["max_relative_change"], **{f"relative_{k}":v for k,v in out["relative_changes"].items()}
            },[xy_series("refinement","relative refinement changes",range(len(keys)),[out["relative_changes"][k] for k in keys],x_label="diagnostic index",y_label="relative change")],
            "Loose-versus-tight integration refinement for the bounded Solar-System model.")
        from physical_lab_solar_system_dynamics import finite_time_lyapunov_indicator
        out=finite_time_lyapunov_indicator(cfg,d0=f(p,"ftleD0",1e-8,1e-12,1e-3),segment_years=f(p,"ftleSegmentYears",2.0,0.05,20.0),max_years=f(p,"ftleMaxYears",30.0,0.1,200.0))
        return result(experiment_id,"physical_lab_solar_system_dynamics.finite_time_lyapunov_indicator",p,{
            "finiteTimeRatePerYear":out["finite_time_rate_per_year"],"elapsedYears":out["elapsed_years"],"renormalizations":out["renormalizations"]
        },[xy_series("ftle-separation","pre-renormalization separation",out["times_years"],out["pre_renormalization_separation"],x_label="time (yr)",y_label="phase-space separation")],out["boundary"])

    if experiment_id == "honeycomb-lattice" and tool in {"normal-modes","phonon-dispersion","phonon-dos"}:
        cfg=_lattice_config_from_params(p)
        if tool=="normal-modes":
            from physical_lab_lattice_dynamics import build_lattice, normal_modes
            out=normal_modes(build_lattice(cfg)); freq=out["frequencies_cycles_per_time"]
            return result(experiment_id,"physical_lab_lattice_dynamics.normal_modes",p,{
                "zeroModeCount":out["zero_mode_count"],"negativeEigenvalueCount":out["negative_eigenvalue_count"],"mostNegativeEigenvalue":out["most_negative_eigenvalue"]
            },[xy_series("modes","normal-mode frequencies",range(len(freq)),freq,x_label="mode index",y_label="frequency")],out["boundary"])
        from physical_lab_lattice_phonons import phonon_dispersion, phonon_dos
        if tool=="phonon-dos":
            out=phonon_dos(cfg,q_grid=i(p,"phononQGrid",12,4,80),bins=i(p,"phononBins",80,16,240))
            return result(experiment_id,"physical_lab_lattice_phonons.phonon_dos",p,{
                "sampleCount":out["sample_count"],"branchCount":out["branch_count"],"normalizationError":out["normalization_error"],"frequencyMin":out["frequency_min"],"frequencyMax":out["frequency_max"]
            },[xy_series("dos","phonon DOS",out["frequency_centers"],out["density"],x_label="frequency",y_label="density")],out["boundary"])
        out=phonon_dispersion(cfg,points_per_segment=i(p,"phononPointsPerSegment",24,8,100))
        coord=np.asarray(out["path_coordinate"]); freqs=np.asarray(out["frequencies_cycles_per_time"])
        series=[xy_series(f"branch-{j}",f"branch {j}",coord,freqs[:,j],x_label="high-symmetry path",y_label="frequency") for j in range(freqs.shape[1])]
        return result(experiment_id,"physical_lab_lattice_phonons.phonon_dispersion",p,{
            "branchCount":out["branch_count"],"gammaZeroModeCount":out["gamma_zero_mode_count"],"hermiticityResidualMax":out["hermiticity_residual_max"],"negativeEigenvalueMagnitudeMax":out["negative_eigenvalue_magnitude_max"]
        },series,out["boundary"])

    if experiment_id == "undulator-spectrum" and tool in {"angular-map","beam-broadening"}:
        from physical_lab_undulator_spectrum import angular_harmonic_map, beam_broadened_resonance
        period=f(p,"periodMm",50.0,1.0,1000.0)/1000.0; gamma=f(p,"gamma",6000.0,2.0,1e7); K=f(p,"K",0.7,0.0,20.0); harmonic=i(p,"harmonic",1,1,15)
        if tool=="angular-map":
            out=angular_harmonic_map(period_m=period,gamma=gamma,K=K,harmonic=harmonic,theta_max_mrad=f(p,"thetaMaxMrad",1.0,.05,10.0),points=i(p,"angularPoints",61,21,181))
            axis=np.asarray(out["theta_axis_mrad"]); grid=np.asarray(out["resonance_energy_eV"]); cut=grid[len(axis)//2]
            return result(experiment_id,"physical_lab_undulator_spectrum.angular_harmonic_map",p,{
                "onAxisEnergyEV":out["on_axis_energy_eV"],"edgeEnergyEV":out["edge_energy_eV"],"minimumEnergyEV":out["minimum_energy_eV"],"maximumEnergyEV":out["maximum_energy_eV"]
            },[xy_series("angular-cut","central angular cut",axis,cut,x_label="theta_x (mrad)",y_label="resonance energy (eV)")],out["boundary"])
        out=beam_broadened_resonance(period_m=period,gamma=gamma,K=K,harmonic=harmonic,relative_energy_spread_rms=f(p,"relativeEnergySpreadRms",1e-3,0.0,.2),angular_divergence_rms_mrad=f(p,"angularDivergenceRmsMrad",.05,0.0,10.0),samples=i(p,"beamSamples",12000,2000,200000),seed=i(p,"beamSeed",20260911,0,2147483647),bins=i(p,"beamBins",120,40,500))
        return result(experiment_id,"physical_lab_undulator_spectrum.beam_broadened_resonance",p,{
            "nominalEnergyEV":out["nominal_energy_eV"],"meanEnergyEV":out["mean_energy_eV"],"medianEnergyEV":out["median_energy_eV"],"rmsEnergySpreadEV":out["rms_energy_spread_eV"],"relativeRmsLinewidth":out["relative_rms_linewidth"],"p05EV":out["p05_eV"],"p95EV":out["p95_eV"]
        },[xy_series("beam-broadening","beam-broadened resonance",out["bin_center_eV"],out["density"],x_label="photon energy (eV)",y_label="density")],out["boundary"])

    if experiment_id == "frequency-response" and tool == "duffing":
        from physical_lab_frequency_response import duffing_frequency_sweep
        omega0=f(p,"omega0",1.0,.1,20.0)
        start_ratio=f(p,"duffingStartRatio",.7,.1,3.0); stop_ratio=f(p,"duffingStopRatio",1.6,.2,5.0)
        if stop_ratio <= start_ratio: raise ValueError("Duffing stop frequency ratio must exceed start ratio")
        q=_sweep_quality(str(p.get("duffingSweepQuality","Standard")),nonlinear=True)
        out=duffing_frequency_sweep(omega_0=omega0,zeta=f(p,"zeta",.05,0.0,1.5),cubic_stiffness=f(p,"cubicStiffness",1.0,0.0,50.0),force_amplitude=f(p,"force",.3,0.0,20.0),frequency_start=start_ratio*omega0,frequency_stop=stop_ratio*omega0,frequency_points=q["points"],settle_cycles=q["settle"],observe_cycles=q["observe"],points_per_cycle=q["ppc"])
        rows=out["rows"]; omega=[r["omega_rad_s"] for r in rows]
        return result(experiment_id,"physical_lab_frequency_response.duffing_frequency_sweep",p,{
            "forwardPeakFrequencyRadS":out["forward_peak_frequency_rad_s"],"forwardPeakAmplitude":out["forward_peak_amplitude"],"reversePeakFrequencyRadS":out["reverse_peak_frequency_rad_s"],"reversePeakAmplitude":out["reverse_peak_amplitude"],"maxBranchAmplitudeGap":out["max_branch_amplitude_gap"]
        },[
            xy_series("duffing-forward","forward amplitude",omega,[r["forward_amplitude"] for r in rows],x_label="omega (rad/s)",y_label="amplitude"),
            xy_series("duffing-reverse","reverse amplitude",omega,[r["reverse_amplitude"] for r in rows],x_label="omega (rad/s)",y_label="amplitude")
        ],out["boundary"],[{"id":"duffing","label":"Duffing sweep","rows":rows}])

    if experiment_id == "utube-studio" and tool in {"operating-state","elasticity","scan-plan","uncertainty","dimensionless-groups","inverse-geometry","design-space","robust-design","adaptive-plan","verification-requirements","research-questions","uncertainty-budget","hysteresis-analysis","rate-sweep","digital-twin-calibration","digital-twin-field","beam-phase-space"}:
        volume=f(p,"volumeMl",3.0,.05,30.0); rpm=f(p,"rpm",260.0,1.0,1000.0); rin=f(p,"rinMm",15.12,1.0,100.0)/1000.0; radius=f(p,"radiusMm",7.48,.1,50.0)/1000.0; nq=i(p,"nq",48,12,128)
        if tool=="dimensionless-groups":
            from physical_lab_utube_advanced import dimensionless_groups
            out=dimensionless_groups(rpm,rin_m=rin,a_m=radius,rho_kg_m3=f(p,"rhoKgM3",997.8,100.0,5000.0),gamma_mN_m=f(p,"gammaMnM",72.0,1.0,500.0))
            return result(experiment_id,"physical_lab_utube_advanced.dimensionless_groups",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[],str(out.get("boundary") or "Dimensionless groups summarize the nominated operating point."),[{"id":"dimensionless","label":"Dimensionless groups","rows":[out]}])
        if tool=="inverse-geometry":
            from physical_lab_utube_advanced import inverse_geometry_design
            out=inverse_geometry_design(f(p,"targetThresholdRpm",250.0,1.0,1000.0),volume,solve_for=str(p.get("solveFor","rin_m")))
            return result(experiment_id,"physical_lab_utube_advanced.inverse_geometry_design",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[],str(out.get("boundary") or "Inverse geometry design is model-based."),[{"id":"inverse-geometry","label":"Inverse geometry design","rows":[out]}])
        if tool=="design-space":
            from physical_lab_utube_advanced import design_space
            vols=np.linspace(max(.05,volume-.5),volume+.5,3); rins=np.linspace(max(.001,rin-.001),rin+.001,3); radii=np.linspace(max(.0005,radius-.0005),radius+.0005,3)
            frame=design_space(volumes_ml=vols,rin_values_m=rins,a_values_m=radii,target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0),nq=nq,max_points=100)
            return result(experiment_id,"physical_lab_utube_advanced.design_space",p,{"designPoints":len(frame)},[],"Design-space screening is a bounded model study, not manufacturing qualification.",[{"id":"design-space","label":"Design space","rows":frame.to_dict(orient="records")}])
        if tool=="robust-design":
            from physical_lab_utube_advanced import robust_design_space, pareto_robust_design
            vols=np.linspace(max(.05,volume-.3),volume+.3,3); rins=np.linspace(max(.001,rin-.0005),rin+.0005,3); radii=np.linspace(max(.0005,radius-.00025),radius+.00025,3)
            frame=robust_design_space(volumes_ml=vols,rin_values_m=rins,a_values_m=radii,target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0),nq=max(12,min(nq,32)),max_points=80)
            pareto=pareto_robust_design(frame)
            return result(experiment_id,"physical_lab_utube_advanced.robust_design_space",p,{"designPoints":len(frame),"paretoPoints":len(pareto)},[],"Robust/Pareto screening compares modeled tolerance sensitivity and does not certify a design.",[{"id":"robust-design","label":"Robust design space","rows":frame.to_dict(orient="records")},{"id":"pareto","label":"Pareto robust designs","rows":pareto.to_dict(orient="records")}])
        if tool=="adaptive-plan":
            from physical_lab_utube_advanced import adaptive_threshold_plan
            target=f(p,"targetThresholdRpm",250.0,1.0,1000.0)
            out=adaptive_threshold_plan([{"n_rpm":target-5,"state":"below"},{"n_rpm":target+5,"state":"above"}],target)
            rows=out if isinstance(out,list) else [out]
            return result(experiment_id,"physical_lab_utube_advanced.adaptive_threshold_plan",p,{"planItems":len(rows)},[],"Adaptive planning proposes bounded next measurements; it does not execute hardware.",[{"id":"adaptive-plan","label":"Adaptive threshold plan","rows":rows}])
        if tool=="verification-requirements":
            from physical_lab_utube_advanced import verification_requirements
            rows=verification_requirements(target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0))
            if isinstance(rows,dict): rows=[rows]
            return result(experiment_id,"physical_lab_utube_advanced.verification_requirements",p,{"requirements":len(rows)},[],"Verification requirements are explicit planning criteria, not certification.",[{"id":"verification-requirements","label":"Verification requirements","rows":rows}])
        if tool=="research-questions":
            from physical_lab_utube_advanced import research_questions
            rows=research_questions()
            if rows and isinstance(rows[0],str): rows=[{"question":x} for x in rows]
            return result(experiment_id,"physical_lab_utube_advanced.research_questions",p,{"questions":len(rows)},[],"Research questions organize investigation and are not conclusions.",[{"id":"research-questions","label":"Research questions","rows":rows}])
        if tool=="uncertainty-budget":
            from physical_lab_utube_uncertainty import local_uncertainty_budget
            means={"volume_ml":volume,"n_rpm":rpm,"rin_m":rin,"a_m":radius,"rho_kg_m3":f(p,"rhoKgM3",997.8,100.0,5000.0),"gamma_mN_m":f(p,"gammaMnM",72.0,1.0,500.0),"theta_deg":f(p,"thetaDeg",0.0,-180.0,180.0)}
            std={"volume_ml":f(p,"uVolumeMl",.05,0.0,10.0),"n_rpm":f(p,"uRpm",1.0,0.0,100.0),"rin_m":f(p,"uRinMm",.2,0.0,10.0)/1000.0,"a_m":f(p,"uRadiusMm",.1,0.0,10.0)/1000.0}
            out=local_uncertainty_budget(means,std,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_uncertainty.local_uncertainty_budget",p,{"budgetTerms":len(rows)},[],"Local uncertainty budgets linearize the model around the nominated operating point.",[{"id":"uncertainty-budget","label":"Local uncertainty budget","rows":rows}])
        if tool=="hysteresis-analysis":
            from physical_lab_utube_hysteresis import analyze_hysteresis_sweeps
            target=f(p,"targetThresholdRpm",250.0,1.0,1000.0)
            out=analyze_hysteresis_sweeps([volume]*3,[1.0,2.0,4.0],[target+1,target+2,target+4],[target-1,target-2,target-4],rin_m=rin,a_m=radius,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_hysteresis.analyze_hysteresis_sweeps",p,{"rows":len(rows)},[],"Hysteresis analysis is reduced-order and does not replace CFD or additional measurements.",[{"id":"hysteresis-analysis","label":"Hysteresis sweep analysis","rows":rows}])
        if tool=="rate-sweep":
            from physical_lab_utube_hysteresis import rate_sweep_prediction
            out=rate_sweep_prediction(volume,[0.5,1.0,2.0,4.0],response_tau_s=f(p,"responseTau",.2,0.0,1000.0),quasi_static_halfwidth_rpm=f(p,"quasiStaticHalfwidth",1.0,0.0,1000.0),rin_m=rin,a_m=radius,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_hysteresis.rate_sweep_prediction",p,{"rows":len(rows)},[],"Rate-sweep predictions are reduced-order dynamic estimates.",[{"id":"rate-sweep","label":"Rate sweep prediction","rows":rows}])
        if tool=="digital-twin-calibration":
            from physical_lab_digital_twin import fit_linear_calibration, apply_linear_calibration
            raw=[0.0,1.0,2.0,3.0]; ref=[0.1,1.05,2.05,3.1]; fit=fit_linear_calibration(raw,ref); out=fit.to_dict(); calibrated=apply_linear_calibration(raw,float(fit.slope),float(fit.offset))
            return result(experiment_id,"physical_lab_digital_twin.fit_linear_calibration",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[xy_series("calibration","calibrated",raw,calibrated,x_label="raw",y_label="calibrated")],"Calibration diagnostics quantify only the supplied reference relationship.",[{"id":"calibration","label":"Calibration fit","rows":[out]}])
        if tool=="digital-twin-field":
            from physical_lab_digital_twin import compare_field_series, fit_model_affine, suggest_residual_measurement_points
            x=[0,1,2,3,4]; measured=[0.0,1.1,1.9,3.05,3.9]; model=[0.0,1.0,2.0,3.0,4.0]
            comp_obj=compare_field_series(x,measured,model); fit_obj=fit_model_affine(measured,model); suggestions=suggest_residual_measurement_points(x,measured,model)
            comp=comp_obj.to_dict(); fit=fit_obj.to_dict()
            metrics={**{k:v for k,v in comp.items() if isinstance(v,(int,float,str,bool))},**{f"fit_{k}":v for k,v in fit.items() if isinstance(v,(int,float,str,bool))}}
            rows=suggestions if isinstance(suggestions,list) else [suggestions]
            return result(experiment_id,"physical_lab_digital_twin.compare_field_series",p,metrics,[xy_series("measured-field","measured",x,measured,x_label="position",y_label="field"),xy_series("model-field","model",x,model,x_label="position",y_label="field")],"Digital-twin field comparison is diagnostic and does not prove model validity.",[{"id":"residual-points","label":"Suggested residual measurement points","rows":rows}])
        if tool=="beam-phase-space":
            from physical_lab_digital_twin import analyze_beam_phase_space
            x=[-2e-3,-1e-3,0.0,1e-3,2e-3]; px=[-1e-4,-4e-5,0,5e-5,1.1e-4]; y=[-1e-3,-.5e-3,0,.5e-3,1e-3]; py=[-6e-5,-3e-5,0,3e-5,6e-5]
            out_obj=analyze_beam_phase_space(x,px,y,py,beta_gamma=f(p,"betaGamma",1.0,1e-12,1e6)); out=out_obj.to_dict()
            metrics={k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))}
            metrics.update({f"x_{k}":v for k,v in out.get("x_plane",{}).items() if isinstance(v,(int,float,str,bool))})
            metrics.update({f"y_{k}":v for k,v in out.get("y_plane",{}).items() if isinstance(v,(int,float,str,bool))})
            return result(experiment_id,"physical_lab_digital_twin.analyze_beam_phase_space",p,metrics,[],"Phase-space statistics summarize supplied samples and do not establish beamline validity.",[{"id":"beam-phase-space","label":"Beam phase-space statistics","rows":[out]}])
        if tool=="operating-state":
            from physical_lab_utube_advanced import operating_state
            out=operating_state(volume,rpm,rin_m=rin,a_m=radius,nq=nq,near_threshold_band_rpm=f(p,"nearThresholdBandRpm",3.0,.1,50.0))
            return result(experiment_id,"physical_lab_utube_advanced.operating_state",p,out,[] ,out["boundary"])
        if tool=="elasticity":
            from physical_lab_utube_advanced import threshold_elasticity
            frame=threshold_elasticity(volume,rin_m=rin,a_m=radius,relative_step=f(p,"elasticityStep",1e-3,1e-5,.1),nq=nq); rows=frame.to_dict(orient="records")
            return result(experiment_id,"physical_lab_utube_advanced.threshold_elasticity",p,{"maxAbsElasticity":max(abs(float(r["elasticity"])) for r in rows)},[xy_series("elasticity","threshold elasticity",range(len(rows)),[r["elasticity"] for r in rows],x_label="parameter index",y_label="elasticity")],"Local central-difference sensitivity of threshold to volume and geometry.",[{"id":"elasticity","label":"Elasticity","rows":rows}])
        if tool=="scan-plan":
            from physical_lab_utube_experiment import threshold
            from physical_lab_utube_advanced import experiment_scan_plan
            ng=threshold(volume,rin=rin,a=radius,nq=nq); frame=experiment_scan_plan(ng,coarse_span_rpm=f(p,"coarseSpanRpm",40.0,1.0,200.0),coarse_step_rpm=f(p,"coarseStepRpm",10.0,.1,100.0),fine_span_rpm=f(p,"fineSpanRpm",8.0,.5,100.0),fine_step_rpm=f(p,"fineStepRpm",2.0,.1,50.0)); rows=frame.to_dict(orient="records")
            return result(experiment_id,"physical_lab_utube_advanced.experiment_scan_plan",p,{"predictedThresholdRpm":ng,"plannedPoints":len(rows)},[xy_series("scan-plan","planned rpm points",range(len(rows)),[r["n_rpm"] for r in rows],x_label="step",y_label="rpm")],"Deterministic two-resolution experimental scan plan around the model threshold.",[{"id":"scan-plan","label":"Scan plan","rows":rows}])
        from physical_lab_utube_uncertainty import propagate_uncertainty
        means={"volume_ml":volume,"n_rpm":rpm,"rin_m":rin,"a_m":radius,"rho_kg_m3":f(p,"rhoKgM3",997.8,100.0,5000.0),"gamma_mN_m":f(p,"gammaMnM",72.0,1.0,500.0),"theta_deg":f(p,"thetaDeg",0.0,-180.0,180.0)}
        std={"volume_ml":f(p,"uVolumeMl",.05,0.0,10.0),"n_rpm":f(p,"uRpm",1.0,0.0,100.0),"rin_m":f(p,"uRinMm",.2,0.0,10.0)/1000.0,"a_m":f(p,"uRadiusMm",.1,0.0,10.0)/1000.0,"rho_kg_m3":f(p,"uRho",1.0,0.0,100.0),"gamma_mN_m":f(p,"uGamma",1.0,0.0,100.0),"theta_deg":f(p,"uThetaDeg",1.0,0.0,90.0)}
        out=propagate_uncertainty(means,std,samples=i(p,"uncertaintySamples",300,50,5000),seed=i(p,"uncertaintySeed",0,0,2147483647),nq=nq); ng=out["outputs"]["n_g_rpm"]; rec=out["records"]
        vals=[r.get("n_g_rpm") for r in rec if r.get("n_g_rpm") is not None]
        return result(experiment_id,"physical_lab_utube_uncertainty.propagate_uncertainty",p,{"samplesSucceeded":out["samples_succeeded"],"samplesFailed":out["samples_failed"],"thresholdMeanRpm":ng.get("mean"),"thresholdStdRpm":ng.get("std"),"thresholdP05Rpm":ng.get("p05"),"thresholdP95Rpm":ng.get("p95")},[xy_series("uncertainty","threshold samples",range(len(vals)),vals,x_label="sample",y_label="n_g (rpm)")],out["boundary"])

    raise ValueError(f"Unsupported tool '{tool}' for experiment '{experiment_id}'")


HANDLERS = {
    "numerical-methods": numerical_methods,
    "ising-monte-carlo": ising_monte_carlo,
    "random-walk-monte-carlo": random_walk,
    "nonlinear-chaos": nonlinear_chaos,
    "oscillation-integration": oscillation,
    "radia-magnet-studio": radia_magnet,
    "radiation-platform": radiation_platform,
    "kerr-geodesics": kerr_geodesics,
    "solar-system-dynamics": solar_system,
    "honeycomb-lattice": honeycomb_lattice,
    "utube-studio": utube,
    "kerr-shadow": kerr_shadow,
    "undulator-spectrum": undulator_spectrum,
    "frequency-response": frequency_response,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, choices=sorted(HANDLERS))
    parser.add_argument("--mode", default="safe", choices=("safe", "full"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.read().strip()
        parameters = json.loads(raw) if raw else {}
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a JSON object")
        tool = str(parameters.pop("__tool", "") or "").strip()
        payload = run_experiment_tool(args.experiment, tool, parameters, args.mode) if tool else HANDLERS[args.experiment](parameters, args.mode)
        sys.stdout.write(json.dumps(clean(payload), separators=(",", ":"), allow_nan=False))
        return 0
    except Exception as exc:
        error = {"schema": SCHEMA, "experimentId": args.experiment, "error": str(exc), "errorType": exc.__class__.__name__}
        sys.stdout.write(json.dumps(error, separators=(",", ":"), allow_nan=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
