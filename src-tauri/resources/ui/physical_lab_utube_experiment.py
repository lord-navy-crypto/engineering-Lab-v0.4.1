"""Native U-tube rotation experiment model/data contracts for Engineering Lab.

This module extracts the deterministic scientific core from the standalone analysis
workflow into reusable, auditable capabilities.  It intentionally does not create
figures and does not infer scientific meaning beyond explicit contracts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from numpy.polynomial.legendre import leggauss
from scipy.optimize import brentq

UTUBE_SCHEMA = "engineering-lab-utube-rotation/v1"
UTUBE_DATASET_SCHEMA = "engineering-lab-utube-dataset/v1"
UTUBE_MODEL_SCHEMA = "engineering-lab-utube-model/v1"

G = 9.80665
DEFAULT_R_IN_M = 15.12e-3
DEFAULT_A_M = 7.48e-3
DEFAULT_RHO = 997.8

BOUNDARY = (
    "The U-tube model computes deterministic predictions from explicit geometry, "
    "fluid properties and numerical settings. Agreement with measurements is a "
    "validation observation, not proof of model truth. Numerical convergence does "
    "not establish physical validity. Signed and magnitude angle representations "
    "are distinct and must not be silently interchanged."
)


@dataclass(frozen=True)
class DatasetContract:
    role: str
    required_columns: tuple[str, ...]
    units: Mapping[str, str]
    semantics: Mapping[str, str]


DATASET_CONTRACTS: tuple[DatasetContract, ...] = (
    DatasetContract(
        "equilibrium-angle-micro",
        ("n_rpm", "theta_deg"),
        {"n_rpm": "rpm", "theta_deg": "deg"},
        {"theta_deg": "signed equilibrium angle; sign preserves tube-side orientation"},
    ),
    DatasetContract(
        "macro-volume-break",
        ("V_mL", "n_minus_rpm", "n_plus_rpm"),
        {"V_mL": "mL", "n_minus_rpm": "rpm", "n_plus_rpm": "rpm"},
        {"n_minus_rpm": "lower bracketing speed", "n_plus_rpm": "upper bracketing speed"},
    ),
    DatasetContract(
        "neck-dimensions",
        ("n_rpm", "h_mm", "w_mm"),
        {"n_rpm": "rpm", "h_mm": "mm", "w_mm": "mm"},
        {"h_mm": "central depth/thickness", "w_mm": "central width"},
    ),
    DatasetContract(
        "radius-scan",
        ("Rin_mm", "V_mL", "n_break_rpm"),
        {"Rin_mm": "mm", "V_mL": "mL", "n_break_rpm": "rpm"},
        {"n_break_rpm": "measured break/disconnect speed"},
    ),
    DatasetContract(
        "macro-interface",
        ("gamma_mN_m", "n_break_rpm"),
        {"gamma_mN_m": "mN/m", "n_break_rpm": "rpm"},
        {"gamma_mN_m": "measured surface tension"},
    ),
    DatasetContract(
        "surface-calibration",
        ("solution", "gamma_mN_m", "theta_deg"),
        {"gamma_mN_m": "mN/m", "theta_deg": "deg"},
        {"theta_deg": "equilibrium/contact angle used by the free-energy scaling model"},
    ),
)


def _finite_float(value: Any, name: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def identify_dataset(frame: pd.DataFrame) -> list[str]:
    """Return compatible U-tube dataset roles without guessing between ambiguous roles."""
    columns = set(map(str, frame.columns))
    matches = [c.role for c in DATASET_CONTRACTS if set(c.required_columns).issubset(columns)]
    return matches


def validate_dataset(frame: pd.DataFrame, *, role: str | None = None) -> dict[str, Any]:
    contracts = {c.role: c for c in DATASET_CONTRACTS}
    if role is None:
        matches = identify_dataset(frame)
        if len(matches) != 1:
            raise ValueError(f"dataset role is ambiguous or unsupported: {matches}")
        role = matches[0]
    if role not in contracts:
        raise ValueError(f"unknown U-tube dataset role: {role}")
    contract = contracts[role]
    missing = [c for c in contract.required_columns if c not in frame.columns]
    if missing:
        raise ValueError(f"{role} missing required columns: {missing}")
    canonical = frame.loc[:, list(contract.required_columns)].copy()
    csv_bytes = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return {
        "schema": UTUBE_DATASET_SCHEMA,
        "role": role,
        "rows": int(len(frame)),
        "required_columns": list(contract.required_columns),
        "units": dict(contract.units),
        "semantics": dict(contract.semantics),
        "sha256": hashlib.sha256(csv_bytes).hexdigest(),
    }


def angle_views(frame: pd.DataFrame, column: str = "theta_deg") -> pd.DataFrame:
    """Preserve signed angle and expose magnitude explicitly; never overwrite the signed field."""
    if column not in frame.columns:
        raise ValueError(f"missing angle field: {column}")
    out = frame.copy()
    signed = pd.to_numeric(out[column], errors="coerce")
    out[f"{column}_signed"] = signed
    out[f"{column}_magnitude"] = signed.abs()
    return out


def omega(n_rpm: float | np.ndarray) -> float | np.ndarray:
    return 2.0 * np.pi * np.asarray(n_rpm) / 60.0


def geometry(rin: float = DEFAULT_R_IN_M, a: float = DEFAULT_A_M) -> dict[str, float]:
    rin = _finite_float(rin, "rin")
    a = _finite_float(a, "a")
    if rin <= 0 or a <= 0:
        raise ValueError("rin and a must be positive")
    return {"R_in_m": rin, "a_m": a, "R_m": rin + a, "ell_m": rin + 2 * a}


def critical_speed(rin: float = DEFAULT_R_IN_M, a: float = DEFAULT_A_M) -> float:
    ell = geometry(rin, a)["ell_m"]
    return float(60.0 * np.sqrt(G / ell) / (2.0 * np.pi))


def capacity(
    n_rpm: float,
    rin: float = DEFAULT_R_IN_M,
    a: float = DEFAULT_A_M,
    nq: int = 84,
) -> tuple[float, float, float]:
    """Return total, curved-part and two-leg low-potential capacities in mL."""
    n_rpm = _finite_float(n_rpm, "n_rpm")
    if nq < 12:
        raise ValueError("nq must be >= 12")
    geom = geometry(rin, a)
    r_center, ell = geom["R_m"], geom["ell_m"]
    w0 = float(omega(n_rpm))
    if w0 <= 0:
        raise ValueError("n_rpm must be positive")
    x, w = leggauss(int(nq))

    theta = 0.5 * np.pi * x
    w_theta = 0.5 * np.pi * w
    s = a * x
    w_s = a * w
    th, ss = np.meshgrid(theta, s, indexing="ij")
    radius = r_center + ss
    t_max = np.sqrt(np.maximum(0.0, a * a - ss * ss))
    q = 2 * G * (ell - radius * np.cos(th)) / w0**2 - radius**2 * np.sin(th) ** 2
    length_t = np.zeros_like(q)
    full = q <= 0
    partial = (q > 0) & (q < t_max**2)
    length_t[full] = 2 * t_max[full]
    length_t[partial] = 2 * (t_max[partial] - np.sqrt(q[partial]))
    c_arc = np.sum(radius * length_t * np.outer(w_theta, w_s))

    radial = 0.5 * a * (x + 1)
    w_radial = 0.5 * a * w
    polar = np.pi * (x + 1)
    w_polar = np.pi * w
    rr, pp = np.meshgrid(radial, polar, indexing="ij")
    u = rr * np.cos(pp)
    t = rr * np.sin(pp)
    r2 = (r_center + u) ** 2 + t**2
    z_max = np.maximum(w0**2 * r2 / (2 * G) - ell, 0.0)
    c_leg = 2 * np.sum(z_max * rr * np.outer(w_radial, w_polar))
    return float((c_arc + c_leg) * 1e6), float(c_arc * 1e6), float(c_leg * 1e6)


def threshold(
    volume_ml: float,
    rin: float = DEFAULT_R_IN_M,
    a: float = DEFAULT_A_M,
    nq: int = 84,
    upper_rpm: float = 520.0,
) -> float:
    volume_ml = _finite_float(volume_ml, "volume_ml")
    if volume_ml <= 0:
        raise ValueError("volume_ml must be positive")
    nc = critical_speed(rin, a)
    return float(brentq(lambda n: capacity(float(n), rin, a, nq)[0] - volume_ml, nc + 1e-5, upper_rpm, xtol=1e-10))


def volume_below_level(
    n_rpm: float,
    h: float,
    rin: float = DEFAULT_R_IN_M,
    a: float = DEFAULT_A_M,
    nq: int = 112,
) -> float:
    """Volume in mL below the equipotential crossing the centre at depth h."""
    geom = geometry(rin, a)
    r_center, ell = geom["R_m"], geom["ell_m"]
    w0 = float(omega(n_rpm))
    x, w = leggauss(int(nq))
    theta = 0.5 * np.pi * x
    w_theta = 0.5 * np.pi * w
    s = a * x
    w_s = a * w
    th, ss = np.meshgrid(theta, s, indexing="ij")
    radius = r_center + ss
    t_max = np.sqrt(np.maximum(0.0, a * a - ss * ss))
    q = 2 * G * (ell - h - radius * np.cos(th)) / w0**2 - radius**2 * np.sin(th) ** 2
    length_t = np.zeros_like(q)
    full = q <= 0
    partial = (q > 0) & (q < t_max**2)
    length_t[full] = 2 * t_max[full]
    length_t[partial] = 2 * (t_max[partial] - np.sqrt(q[partial]))
    c_arc = np.sum(radius * length_t * np.outer(w_theta, w_s))
    radial = 0.5 * a * (x + 1)
    w_radial = 0.5 * a * w
    polar = np.pi * (x + 1)
    w_polar = np.pi * w
    rr, pp = np.meshgrid(radial, polar, indexing="ij")
    u = rr * np.cos(pp)
    t = rr * np.sin(pp)
    r2 = (r_center + u) ** 2 + t**2
    z_max = np.maximum(w0**2 * r2 / (2 * G) - ell + h, 0.0)
    c_leg = 2 * np.sum(z_max * rr * np.outer(w_radial, w_polar))
    return float((c_arc + c_leg) * 1e6)


def central_depth(n_rpm: float, volume_ml: float = 3.0, nq: int = 112) -> float:
    if volume_below_level(n_rpm, 0.0, nq=nq) >= volume_ml:
        return 0.0
    return float(brentq(lambda h: volume_below_level(n_rpm, h, nq=nq) - volume_ml, 0.0, 2 * DEFAULT_A_M, xtol=1e-12))


def central_width(n_rpm: float, h: float, a: float = DEFAULT_A_M) -> float:
    if h <= 0:
        return 0.0
    beta = float(omega(n_rpm)) ** 2 / (2 * G)
    def intersection(t: float) -> float:
        return np.sqrt(max(a * a - t * t, 0.0)) - (a - h - beta * t * t)
    if intersection(a) >= 0:
        return float(2 * a)
    return float(2 * brentq(intersection, 0.0, a, xtol=1e-14))


def local_coefficients(n_rpm: float, rin: float = DEFAULT_R_IN_M, a: float = DEFAULT_A_M, rho: float = DEFAULT_RHO) -> dict[str, float]:
    geom = geometry(rin, a)
    R, ell = geom["R_m"], geom["ell_m"]
    w = float(omega(n_rpm))
    cos_theta_m = float(np.clip(G / (w**2 * ell), -1.0, 1.0))
    sin_theta_m = float(np.sqrt(1.0 - cos_theta_m**2))
    f_n = w**2 * ell
    k_q = w**2 * sin_theta_m**2
    k_t = w**2 * R / a
    if k_q <= 0 or k_t <= 0:
        raise ValueError("free-energy local coefficients require rotation above the angular bifurcation")
    A0 = np.pi / (f_n * np.sqrt(k_q * k_t))
    K = (2.0 * rho / (3.0 * np.sqrt(np.pi))) * np.sqrt(f_n) * (k_q * k_t) ** 0.25
    return {"f_n": f_n, "k_q": k_q, "k_t": k_t, "A0": A0, "K_SI": K, "K_mL": K * 1e-9, "theta_m_deg": float(np.degrees(np.arccos(cos_theta_m)))}


def surface_coefficient(gamma_mN_m: float, theta_deg: float) -> float:
    gamma = _finite_float(gamma_mN_m, "gamma_mN_m") * 1e-3
    theta = np.radians(_finite_float(theta_deg, "theta_deg"))
    D = (1.0 - np.cos(theta)) ** 2 * (2.0 + np.cos(theta))
    return float(gamma * np.pi ** (1 / 3) * 3 ** (2 / 3) * D ** (1 / 3) * 1e-4)


def vstar(n_rpm: float, gamma_mN_m: float, theta_deg: float) -> float:
    K = local_coefficients(n_rpm)["K_mL"]
    S = surface_coefficient(gamma_mN_m, theta_deg)
    a_bulk = 1.0 - 2.0 ** (-0.5)
    a_surf = 2.0 ** (1.0 / 3.0) - 1.0
    return float((a_surf * S / (a_bulk * K)) ** (6.0 / 5.0))


def delta_free_energy(volume_ml: float | np.ndarray, n_rpm: float, gamma_mN_m: float, theta_deg: float) -> float | np.ndarray:
    V = np.asarray(volume_ml, dtype=float)
    K = local_coefficients(n_rpm)["K_mL"]
    S = surface_coefficient(gamma_mN_m, theta_deg)
    a_bulk = 1.0 - 2.0 ** (-0.5)
    a_surf = 2.0 ** (1.0 / 3.0) - 1.0
    return -a_bulk * K * V**1.5 + a_surf * S * V ** (2.0 / 3.0)


def quadrature_convergence(volumes_ml: Sequence[float], nq_values: Sequence[int] = (32, 48, 64, 84, 112, 160)) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    previous: dict[float, float] = {}
    for nq in nq_values:
        for volume in volumes_ml:
            value = threshold(float(volume), nq=int(nq))
            prior = previous.get(float(volume))
            rows.append({
                "V_mL": float(volume),
                "nq": int(nq),
                "threshold_rpm": value,
                "delta_from_previous_rpm": None if prior is None else abs(value - prior),
            })
            previous[float(volume)] = value
    return pd.DataFrame(rows)


def model_spec() -> dict[str, Any]:
    return {
        "schema": UTUBE_MODEL_SCHEMA,
        "model_id": "utube-rotation-3d-potential",
        "inputs": {
            "geometry": {"R_in_m": DEFAULT_R_IN_M, "a_m": DEFAULT_A_M},
            "fluid": {"rho_kg_m3": DEFAULT_RHO},
            "numerics": {"quadrature": "Gauss-Legendre", "root_solver": "Brent"},
        },
        "capabilities": ["critical-speed", "3d-capacity", "neck-geometry", "free-energy-scaling", "quadrature-convergence"],
        "boundary": BOUNDARY,
    }


def scientific_object(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Machine-readable object suitable for Engineering Lab Scientific Context/OpenPenguin."""
    return {
        "schema": UTUBE_SCHEMA,
        "object_type": "experiment-model",
        "object_id": "utube-rotation-experiment",
        "title": "Rotating U-tube liquid experiment",
        "model": model_spec(),
        "source": dict(source or {}),
        "eligible_analysis_hints": [
            "regression-diagnostics",
            "bootstrap",
            "sensitivity-screening",
            "response-surface",
            "conditioning",
        ],
        "interpretation_constraints": [
            "Do not replace signed angle data with magnitudes when discussing side/orientation.",
            "Do not describe numerical convergence as physical validation.",
            "Do not describe theory-experiment agreement as proof of the model.",
            "Do not infer calibration or uncertainty that is not explicitly supplied.",
        ],
        "authority": {"scientific_evidence": "Engineering Lab", "ai_execution": False, "mutation_authority": False},
    }
