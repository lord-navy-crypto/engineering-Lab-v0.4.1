"""Reduced-order dynamic-threshold and hysteresis analysis for the rotating U-tube.

This module deliberately sits above the deterministic 3-D equilibrium model.  It
models observed commanded-speed break/reconnect thresholds during monotonic RPM
ramps as an empirical branch offset plus a first-order rate lag.  It does *not*
claim to solve transient free-surface Navier-Stokes flow or identify viscosity,
contact-angle hysteresis, pinning energy, or motor safety limits.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

from physical_lab_utube_experiment import DEFAULT_A_M, DEFAULT_R_IN_M, threshold

SCHEMA = "engineering-lab-utube-dynamic-threshold/v1"
FIT_SCHEMA = "engineering-lab-utube-hysteresis-fit/v1"

BOUNDARY = (
    "Dynamic-threshold results are reduced-order descriptions of measured ramp experiments. "
    "The fitted quasi-static half-width and time constant are empirical apparatus-level descriptors. "
    "They must not be interpreted as contact-angle hysteresis, viscosity, pinning energy, a hardware safety margin, "
    "or a complete transient fluid-dynamics identification without an independently validated physical model."
)


def _finite_positive(value: Any, name: str, *, allow_zero: bool = False) -> float:
    x = float(value)
    if not math.isfinite(x) or (x < 0 if allow_zero else x <= 0):
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}")
    return x


def dynamic_branch_thresholds(
    static_threshold_rpm: float,
    ramp_rate_rpm_s: float,
    *,
    response_tau_s: float = 0.0,
    quasi_static_halfwidth_rpm: float = 0.0,
) -> dict[str, float | str]:
    """Predict commanded-speed up/down thresholds for a symmetric reduced-order loop.

    For a monotonic ramp with magnitude ``r`` the model is
      n_up   = n_eq + H + r*tau
      n_down = n_eq - H - r*tau
    where H is an empirical quasi-static half-width and tau is a first-order
    command-to-apparatus response time.  This relation is descriptive and should
    not be re-labeled as a constitutive fluid law.
    """
    n_eq = _finite_positive(static_threshold_rpm, "static_threshold_rpm")
    rate = _finite_positive(abs(float(ramp_rate_rpm_s)), "ramp_rate_rpm_s", allow_zero=True)
    tau = _finite_positive(response_tau_s, "response_tau_s", allow_zero=True)
    half = _finite_positive(quasi_static_halfwidth_rpm, "quasi_static_halfwidth_rpm", allow_zero=True)
    lag = rate * tau
    up = n_eq + half + lag
    down = n_eq - half - lag
    return {
        "schema": SCHEMA,
        "static_threshold_rpm": n_eq,
        "ramp_rate_rpm_s": rate,
        "response_tau_s": tau,
        "quasi_static_halfwidth_rpm": half,
        "dynamic_lag_rpm": lag,
        "up_threshold_rpm": up,
        "down_threshold_rpm": down,
        "loop_width_rpm": up - down,
        "loop_center_rpm": 0.5 * (up + down),
        "boundary": BOUNDARY,
    }


def _paired_rows(
    volumes_ml: Iterable[float],
    ramp_rates_rpm_s: Iterable[float],
    up_thresholds_rpm: Iterable[float],
    down_thresholds_rpm: Iterable[float],
) -> list[tuple[float, float, float, float]]:
    rows: list[tuple[float, float, float, float]] = []
    for volume, rate, up, down in zip(volumes_ml, ramp_rates_rpm_s, up_thresholds_rpm, down_thresholds_rpm):
        try:
            volume = float(volume); rate = abs(float(rate)); up = float(up); down = float(down)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(x) for x in (volume, rate, up, down)):
            continue
        if volume <= 0 or rate < 0 or up <= 0 or down <= 0 or up < down:
            continue
        rows.append((volume, rate, up, down))
    if len(rows) < 3:
        raise ValueError("at least three finite paired up/down ramp observations are required")
    return rows


def analyze_hysteresis_sweeps(
    volumes_ml: Iterable[float],
    ramp_rates_rpm_s: Iterable[float],
    up_thresholds_rpm: Iterable[float],
    down_thresholds_rpm: Iterable[float],
    *,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    nq: int = 48,
) -> dict[str, Any]:
    """Fit loop half-width = H + |dn/dt|*tau and compare loop centers to n_g(V)."""
    rows = _paired_rows(volumes_ml, ramp_rates_rpm_s, up_thresholds_rpm, down_thresholds_rpm)
    records: list[dict[str, float]] = []
    for volume, rate, up, down in rows:
        modeled = float(threshold(volume, rin=float(rin_m), a=float(a_m), nq=int(nq)))
        center = 0.5 * (up + down)
        halfwidth = 0.5 * (up - down)
        records.append({
            "V_mL": volume,
            "ramp_rate_rpm_s": rate,
            "up_threshold_rpm": up,
            "down_threshold_rpm": down,
            "loop_center_rpm": center,
            "loop_halfwidth_rpm": halfwidth,
            "loop_width_rpm": 2.0 * halfwidth,
            "model_static_threshold_rpm": modeled,
            "center_minus_model_rpm": center - modeled,
        })
    frame = pd.DataFrame(records)
    x = frame["ramp_rate_rpm_s"].to_numpy(dtype=float)
    y = frame["loop_halfwidth_rpm"].to_numpy(dtype=float)
    if float(np.ptp(x)) <= 1e-15:
        raise ValueError("ramp-rate variation is required to identify a response time constant")
    design = np.column_stack([x, np.ones(len(x))])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    tau = max(0.0, float(slope))
    half = max(0.0, float(intercept))
    predicted_halfwidth = half + tau * x
    half_residual = y - predicted_halfwidth
    center_residual = frame["center_minus_model_rpm"].to_numpy(dtype=float)
    frame["predicted_halfwidth_rpm"] = predicted_halfwidth
    frame["halfwidth_residual_rpm"] = half_residual
    frame["predicted_up_from_center_rpm"] = frame["model_static_threshold_rpm"] + predicted_halfwidth
    frame["predicted_down_from_center_rpm"] = frame["model_static_threshold_rpm"] - predicted_halfwidth
    y_mean = float(np.mean(y))
    sst = float(np.sum((y - y_mean) ** 2))
    sse = float(np.sum(half_residual ** 2))
    return {
        "schema": FIT_SCHEMA,
        "frame": frame,
        "fit": {
            "response_tau_s": tau,
            "quasi_static_halfwidth_rpm": half,
            "halfwidth_rmse_rpm": float(np.sqrt(np.mean(half_residual ** 2))),
            "halfwidth_r2": None if sst <= 1e-15 else float(1.0 - sse / sst),
            "center_model_rmse_rpm": float(np.sqrt(np.mean(center_residual ** 2))),
            "center_model_bias_rpm": float(np.mean(center_residual)),
            "mean_loop_width_rpm": float(np.mean(frame["loop_width_rpm"])),
            "max_loop_width_rpm": float(np.max(frame["loop_width_rpm"])),
            "n": int(len(frame)),
        },
        "geometry": {"R_in_m": float(rin_m), "a_m": float(a_m), "quadrature_order": int(nq)},
        "boundary": BOUNDARY,
    }


def rate_sweep_prediction(
    volume_ml: float,
    ramp_rates_rpm_s: Iterable[float],
    *,
    response_tau_s: float,
    quasi_static_halfwidth_rpm: float,
    rin_m: float = DEFAULT_R_IN_M,
    a_m: float = DEFAULT_A_M,
    nq: int = 48,
) -> pd.DataFrame:
    """Generate a transparent up/down threshold envelope across ramp rate."""
    static_ng = float(threshold(float(volume_ml), rin=float(rin_m), a=float(a_m), nq=int(nq)))
    rows = []
    for rate in ramp_rates_rpm_s:
        result = dynamic_branch_thresholds(
            static_ng,
            float(rate),
            response_tau_s=response_tau_s,
            quasi_static_halfwidth_rpm=quasi_static_halfwidth_rpm,
        )
        rows.append({
            "V_mL": float(volume_ml),
            "ramp_rate_rpm_s": float(result["ramp_rate_rpm_s"]),
            "static_threshold_rpm": static_ng,
            "up_threshold_rpm": float(result["up_threshold_rpm"]),
            "down_threshold_rpm": float(result["down_threshold_rpm"]),
            "loop_width_rpm": float(result["loop_width_rpm"]),
        })
    return pd.DataFrame(rows).sort_values("ramp_rate_rpm_s", kind="stable").reset_index(drop=True)
