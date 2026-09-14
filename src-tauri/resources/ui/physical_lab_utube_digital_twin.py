"""U-tube digital-twin helpers built on Engineering Lab's shared measurement core.

The threshold twin compares observed finite-volume break thresholds with the
existing 3-D U-tube model. The dynamic helper identifies a first-order RPM lag
from commanded and measured speed histories. The lag constant is a reduced-order
apparatus response descriptor; it is not viscosity or a full fluid-dynamics fit.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from physical_lab_digital_twin import fit_model_affine, suggest_residual_measurement_points
from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M, threshold

THRESHOLD_TWIN_SCHEMA = "engineering-lab-utube-threshold-twin/v1"
DYNAMIC_TWIN_SCHEMA = "engineering-lab-utube-rpm-lag/v1"

BOUNDARY = (
    "U-tube digital-twin results are model-to-measurement comparisons within the declared dataset conventions. "
    "Threshold residuals do not by themselves validate the physical model. The fitted RPM time constant is a first-order reduced-order apparatus descriptor, "
    "not viscosity, contact-angle hysteresis, motor safety margin or a complete Navier-Stokes identification."
)


def _finite_threshold_rows(volumes: Iterable[float], observed_rpm: Iterable[float]) -> list[tuple[float, float]]:
    rows: list[tuple[float, float]] = []
    for v, n in zip(volumes, observed_rpm):
        try:
            v = float(v); n = float(n)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and math.isfinite(n) and v > 0 and n > 0:
            rows.append((v, n))
    if len(rows) < 2:
        raise ValueError("at least two finite positive volume/threshold observations are required")
    return rows


def compare_threshold_series(
    volumes_ml: Iterable[float],
    observed_threshold_rpm: Iterable[float],
    *,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    nq: int = 48,
) -> dict:
    rows = _finite_threshold_rows(volumes_ml, observed_threshold_rpm)
    records = []
    for volume, observed in rows:
        modeled = float(threshold(volume, rin=float(rin_m), a=float(a_m), nq=int(nq)))
        records.append({
            "V_mL": volume,
            "observed_threshold_rpm": observed,
            "model_threshold_rpm": modeled,
            "residual_rpm": observed - modeled,
            "abs_residual_rpm": abs(observed - modeled),
        })
    frame = pd.DataFrame(records).sort_values("V_mL", kind="stable").reset_index(drop=True)
    residual = frame["residual_rpm"].to_numpy(float)
    rmse = float(np.sqrt(np.mean(residual * residual)))
    mae = float(np.mean(np.abs(residual)))
    bias = float(np.mean(residual))
    fit = fit_model_affine(frame["observed_threshold_rpm"], frame["model_threshold_rpm"])
    return {
        "schema": THRESHOLD_TWIN_SCHEMA,
        "frame": frame,
        "metrics": {
            "n": int(len(frame)),
            "rmse_rpm": rmse,
            "mae_rpm": mae,
            "bias_rpm": bias,
            "max_abs_residual_rpm": float(np.max(np.abs(residual))),
            "affine_scale": float(fit.scale),
            "affine_offset_rpm": float(fit.offset),
            "affine_rmse_before_rpm": float(fit.rmse_before),
            "affine_rmse_after_rpm": float(fit.rmse_after),
        },
        "geometry": {"R_in_m": float(rin_m), "a_m": float(a_m), "quadrature_order": int(nq)},
        "boundary": "Affine discrepancy is descriptive correction only; it is not physical parameter inference or validation evidence by itself.",
    }


def suggest_threshold_remeasurements(twin: dict, *, count: int = 3, minimum_spacing_fraction: float = 0.08) -> list[dict[str, float]]:
    frame = twin.get("frame")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("threshold twin result does not contain a comparison frame")
    suggestions = suggest_residual_measurement_points(
        frame["V_mL"], frame["observed_threshold_rpm"], frame["model_threshold_rpm"],
        count=count, minimum_spacing_fraction=minimum_spacing_fraction,
    )
    return [{"V_mL": float(row["position"]), "residual_rpm": float(row["residual"]), "priority_score": float(row["score"])} for row in suggestions]


def first_order_rpm_response(time_s: Iterable[float], commanded_rpm: Iterable[float], tau_s: float, *, initial_rpm: float | None = None) -> list[float]:
    t = np.asarray(list(time_s), dtype=float)
    u = np.asarray(list(commanded_rpm), dtype=float)
    if len(t) != len(u) or len(t) < 2:
        raise ValueError("time and commanded RPM must contain at least two paired samples")
    if not np.isfinite(t).all() or not np.isfinite(u).all() or np.any(np.diff(t) <= 0):
        raise ValueError("time must be finite and strictly increasing; commanded RPM must be finite")
    tau = float(tau_s)
    if not math.isfinite(tau) or tau <= 0:
        raise ValueError("tau_s must be positive and finite")
    y = np.empty_like(u)
    y[0] = float(u[0] if initial_rpm is None else initial_rpm)
    for i in range(1, len(u)):
        dt = float(t[i] - t[i - 1])
        alpha = math.exp(-dt / tau)
        y[i] = u[i - 1] + (y[i - 1] - u[i - 1]) * alpha
    return y.tolist()


def fit_first_order_rpm_lag(
    time_s: Iterable[float],
    commanded_rpm: Iterable[float],
    measured_rpm: Iterable[float],
    *,
    tau_bounds_s: tuple[float, float] = (0.02, 30.0),
    grid_points: int = 240,
) -> dict:
    rows = []
    for t, u, y in zip(time_s, commanded_rpm, measured_rpm):
        try:
            t = float(t); u = float(u); y = float(y)
        except (TypeError, ValueError):
            continue
        if math.isfinite(t) and math.isfinite(u) and math.isfinite(y):
            rows.append((t, u, y))
    if len(rows) < 4:
        raise ValueError("at least four finite time/command/measured samples are required")
    rows.sort(key=lambda x: x[0])
    t = np.asarray([r[0] for r in rows], dtype=float)
    u = np.asarray([r[1] for r in rows], dtype=float)
    y = np.asarray([r[2] for r in rows], dtype=float)
    if np.any(np.diff(t) <= 0):
        raise ValueError("time values must be unique and strictly increasing")
    lo, hi = map(float, tau_bounds_s)
    if not (0 < lo < hi):
        raise ValueError("tau bounds must satisfy 0 < lower < upper")
    points = int(grid_points)
    if points < 20 or points > 4000:
        raise ValueError("grid_points must be in 20..4000")
    taus = np.geomspace(lo, hi, points)
    best = None
    initial = float(y[0])
    for tau in taus:
        pred = np.asarray(first_order_rpm_response(t, u, float(tau), initial_rpm=initial), dtype=float)
        residual = y - pred
        rmse = float(np.sqrt(np.mean(residual * residual)))
        if best is None or rmse < best[0]:
            best = (rmse, float(tau), pred, residual)
    assert best is not None
    rmse, tau, pred, residual = best
    mean_y = float(np.mean(y))
    sst = float(np.sum((y - mean_y) ** 2))
    sse = float(np.sum(residual * residual))
    return {
        "schema": DYNAMIC_TWIN_SCHEMA,
        "tau_s": tau,
        "rmse_rpm": rmse,
        "mae_rpm": float(np.mean(np.abs(residual))),
        "bias_rpm": float(np.mean(residual)),
        "r2": None if sst <= 1e-15 else float(1.0 - sse / sst),
        "time_s": t.tolist(),
        "commanded_rpm": u.tolist(),
        "measured_rpm": y.tolist(),
        "predicted_rpm": pred.tolist(),
        "residual_rpm": residual.tolist(),
        "settling_time_2pct_s": float(4.0 * tau),
        "boundary": "First-order reduced-order fit only. Tau summarizes observed command-to-speed lag and must not be interpreted as viscosity or a hardware safety constant.",
    }
