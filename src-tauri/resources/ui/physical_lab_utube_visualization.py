"""Native scientific visualization helpers for the rotating U-tube model.

This module contains deterministic, plot-agnostic geometry and derived-view builders.
It deliberately does not mutate Project state, infer measurement meaning, or replace
the validated U-tube scientific core. UI modules may turn these tables into Plotly
figures while preserving the explicit model/evidence boundaries.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

import physical_lab_utube_experiment as utube

VISUALIZATION_SCHEMA = "engineering-lab-utube-visualization/v1"

BOUNDARY = (
    "U-tube visualization products are deterministic derived views of the declared "
    "model inputs. Geometry traces are schematic centerline/reference views rather "
    "than CFD or reconstructed liquid interfaces. Effective-potential and threshold "
    "maps are model diagnostics, not experimental observations or safety limits."
)


def _finite(value: Any, name: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def reference_geometry(
    rin_m: float = utube.DEFAULT_R_IN_M,
    a_m: float = utube.DEFAULT_A_M,
    *,
    bend_points: int = 181,
    leg_height_m: float | None = None,
) -> pd.DataFrame:
    """Return a front-view U-tube centerline suitable for a scientific schematic.

    The bend uses the same centerline radius ``R = R_in + a`` and vertical reference
    ``ell = R_in + 2a`` used by the capacity model. The straight legs are a display
    continuation from the two bend endpoints and do not assert a finite hardware
    tube length unless ``leg_height_m`` is supplied explicitly.
    """
    geom = utube.geometry(rin_m, a_m)
    R = geom["R_m"]
    ell = geom["ell_m"]
    n = max(31, min(int(bend_points), 1001))
    height = float(leg_height_m) if leg_height_m is not None else max(4.0 * a_m, 0.75 * R)
    if not np.isfinite(height) or height <= 0:
        raise ValueError("leg_height_m must be positive")

    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n)
    bend = pd.DataFrame({
        "segment": "bend",
        "order": np.arange(n, dtype=int),
        "x_m": R * np.sin(theta),
        "z_m": ell - R * np.cos(theta),
        "theta_rad": theta,
    })
    leg_n = max(20, n // 4)
    z_leg = np.linspace(ell, ell + height, leg_n)
    left = pd.DataFrame({
        "segment": "left-leg",
        "order": np.arange(leg_n, dtype=int),
        "x_m": -R,
        "z_m": z_leg,
        "theta_rad": np.nan,
    })
    right = pd.DataFrame({
        "segment": "right-leg",
        "order": np.arange(leg_n, dtype=int),
        "x_m": R,
        "z_m": z_leg,
        "theta_rad": np.nan,
    })
    return pd.concat([left, bend, right], ignore_index=True)


def effective_potential_profile(
    n_rpm: float,
    rin_m: float = utube.DEFAULT_R_IN_M,
    a_m: float = utube.DEFAULT_A_M,
    *,
    points: int = 361,
) -> pd.DataFrame:
    """Return the rotating-frame centerline effective-potential profile on the bend.

    The reported potential is shifted by its minimum because only relative potential
    is used for this visualization. It is expressed in J/kg (= m²/s²).
    """
    speed = _finite(n_rpm, "n_rpm")
    if speed <= 0:
        raise ValueError("n_rpm must be positive")
    geom = utube.geometry(rin_m, a_m)
    R = geom["R_m"]
    ell = geom["ell_m"]
    w = float(utube.omega(speed))
    n = max(51, min(int(points), 2001))
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n)
    x = R * np.sin(theta)
    z = ell - R * np.cos(theta)
    potential = utube.G * z - 0.5 * w * w * x * x
    relative = potential - float(np.min(potential))
    return pd.DataFrame({
        "theta_deg": np.degrees(theta),
        "x_m": x,
        "z_m": z,
        "effective_potential_J_kg": potential,
        "relative_potential_J_kg": relative,
    })


def capacity_decomposition(
    volume_ml: float,
    n_rpm: float,
    rin_m: float = utube.DEFAULT_R_IN_M,
    a_m: float = utube.DEFAULT_A_M,
    nq: int = 84,
) -> dict[str, Any]:
    """Return capacity components plus physically useful margins for one state."""
    volume = _finite(volume_ml, "volume_ml")
    speed = _finite(n_rpm, "n_rpm")
    if volume <= 0 or speed <= 0:
        raise ValueError("volume_ml and n_rpm must be positive")
    total, curved, legs = utube.capacity(speed, rin_m, a_m, int(nq))
    ng = utube.threshold(volume, rin_m, a_m, int(nq))
    nc = utube.critical_speed(rin_m, a_m)
    return {
        "schema": VISUALIZATION_SCHEMA,
        "volume_ml": volume,
        "n_rpm": speed,
        "critical_speed_rpm": nc,
        "threshold_rpm": ng,
        "threshold_margin_rpm": speed - ng,
        "capacity_total_ml": total,
        "capacity_curved_ml": curved,
        "capacity_legs_ml": legs,
        "capacity_margin_ml": total - volume,
        "curved_fraction": curved / total if total > 0 else None,
        "legs_fraction": legs / total if total > 0 else None,
        "boundary": BOUNDARY,
    }


def threshold_phase_map(
    volumes_ml: Iterable[float],
    speeds_rpm: Iterable[float],
    rin_m: float = utube.DEFAULT_R_IN_M,
    a_m: float = utube.DEFAULT_A_M,
    nq: int = 48,
    *,
    near_threshold_band_rpm: float = 3.0,
) -> pd.DataFrame:
    """Classify a bounded V×n grid using the two distinct U-tube thresholds.

    Regimes intentionally preserve the distinction between angular bifurcation ``n_c``
    and finite-volume capacity threshold ``n_g(V)``.
    """
    volumes = [float(v) for v in volumes_ml]
    speeds = [float(n) for n in speeds_rpm]
    if not volumes or not speeds:
        raise ValueError("volumes_ml and speeds_rpm must be non-empty")
    if any((not np.isfinite(v) or v <= 0) for v in volumes):
        raise ValueError("all volumes must be finite and positive")
    if any((not np.isfinite(n) or n <= 0) for n in speeds):
        raise ValueError("all speeds must be finite and positive")
    band = abs(_finite(near_threshold_band_rpm, "near_threshold_band_rpm"))
    nc = utube.critical_speed(rin_m, a_m)
    thresholds = {v: utube.threshold(v, rin_m, a_m, int(nq)) for v in volumes}
    rows: list[dict[str, Any]] = []
    for volume in volumes:
        ng = thresholds[volume]
        for speed in speeds:
            if speed < nc:
                regime = "below-angular-bifurcation"
                code = 0
            elif abs(speed - ng) <= band:
                regime = "near-finite-volume-threshold"
                code = 2
            elif speed < ng:
                regime = "between-nc-and-ng"
                code = 1
            else:
                regime = "above-finite-volume-threshold"
                code = 3
            rows.append({
                "V_mL": volume,
                "n_rpm": speed,
                "critical_speed_rpm": nc,
                "threshold_rpm": ng,
                "threshold_margin_rpm": speed - ng,
                "regime": regime,
                "regime_code": code,
            })
    return pd.DataFrame(rows)
