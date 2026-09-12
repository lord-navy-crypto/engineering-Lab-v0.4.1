"""Bounded local quadratic response surfaces for RADIA -> radiation observables.

The study uses two selected manufacturing-error *magnitude* families. Coded levels
-1, 0, +1 map to 0.0, 0.5, 1.0 times each currently configured magnitude so
negative tolerance magnitudes are never invented. A single fixed manufacturing
seed is reused across the 3x3 design to reduce realization noise while scaling
those two error families.

Each observable is fit to

    y = b0 + b1*x1 + b2*x2 + b11*x1^2 + b22*x2^2 + b12*x1*x2

inside the sampled box only. This is a local surrogate, not a global sensitivity
model, manufacturing-yield estimate, or permission to extrapolate.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence

ERROR_KEYS = (
    "field_error_pct",
    "longitudinal_error_mm",
    "transverse_error_mm",
    "angle_error_deg",
    "gap_asymmetry_mm",
    "bank_imbalance_pct",
)
DEFAULT_METRICS = (
    "photon_energy_eV",
    "relative_linewidth",
    "P_lin",
    "P_circ",
    "polarization_degree",
    "H3_over_H1",
    "H5_over_H1",
    "max_transverse_excursion_m",
    "orbit_phase_error_rms_rad",
)
CODED_LEVELS = (-1.0, 0.0, 1.0)
LEVEL_TO_SCALE = {-1.0: 0.0, 0.0: 0.5, 1.0: 1.0}


def _load_propagation():
    try:
        import physical_lab_radia_radiation_propagation as prop
        return prop
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radia_radiation_propagation.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radia_radiation_propagation", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        prop = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radia_radiation_propagation", prop)
        spec.loader.exec_module(prop)
        return prop


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _metric(record: Mapping[str, Any], metric: str) -> float | None:
    obs = record.get("observables") if isinstance(record.get("observables"), Mapping) else {}
    stokes = record.get("stokes") if isinstance(record.get("stokes"), Mapping) else {}
    harmonics = record.get("harmonicRatios") if isinstance(record.get("harmonicRatios"), Mapping) else {}
    for source in (obs, stokes, harmonics, record):
        value = _finite(source.get(metric))
        if value is not None:
            return value
    return None


def design_row(x1: float, x2: float) -> list[float]:
    x1 = float(x1); x2 = float(x2)
    return [1.0, x1, x2, x1 * x1, x2 * x2, x1 * x2]


def predict_quadratic(coefficients: Mapping[str, float], x1: float, x2: float) -> float:
    return float(
        coefficients["intercept"]
        + coefficients["linearA"] * x1
        + coefficients["linearB"] * x2
        + coefficients["quadraticA"] * x1 * x1
        + coefficients["quadraticB"] * x2 * x2
        + coefficients["interactionAB"] * x1 * x2
    )


def fit_metric_surface(
    records: Sequence[Mapping[str, Any]],
    metric: str,
    *,
    factor_a: str,
    factor_b: str,
) -> dict[str, Any]:
    import numpy as np

    rows = []
    values = []
    used = []
    for record in records:
        y = _metric(record, metric)
        x1 = _finite(record.get("codedA")); x2 = _finite(record.get("codedB"))
        if y is None or x1 is None or x2 is None:
            continue
        rows.append(design_row(x1, x2))
        values.append(y)
        used.append({"codedA": x1, "codedB": x2, "value": y})
    if len(rows) < 6:
        raise ValueError(f"Need at least 6 finite design points to fit {metric}; got {len(rows)}")
    X = np.asarray(rows, dtype=float)
    y = np.asarray(values, dtype=float)
    beta, _, rank, singular = np.linalg.lstsq(X, y, rcond=None)
    if int(rank) < 6:
        raise ValueError(f"Quadratic design for {metric} is rank deficient")
    pred = X @ beta
    resid = y - pred
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else (1.0 if ss_res <= 1e-30 else 0.0)
    coeff = {
        "intercept": float(beta[0]),
        "linearA": float(beta[1]),
        "linearB": float(beta[2]),
        "quadraticA": float(beta[3]),
        "quadraticB": float(beta[4]),
        "interactionAB": float(beta[5]),
    }
    return {
        "metric": metric,
        "factorA": factor_a,
        "factorB": factor_b,
        "coefficients": coeff,
        "fit": {
            "pointCount": int(len(y)),
            "rank": int(rank),
            "r2": float(r2),
            "rmse": float(np.sqrt(np.mean(resid ** 2))),
            "maxAbsResidual": float(np.max(np.abs(resid))),
            "conditionNumber": float(np.max(singular) / np.min(singular)) if len(singular) and np.min(singular) > 0 else None,
        },
        "points": used,
    }


def summarize_response_surfaces(
    records: Sequence[Mapping[str, Any]],
    *,
    factor_a: str,
    factor_b: str,
    metrics: Sequence[str] = DEFAULT_METRICS,
) -> dict[str, Any]:
    surfaces = {}
    for metric in metrics:
        try:
            surfaces[metric] = fit_metric_surface(records, metric, factor_a=factor_a, factor_b=factor_b)
        except ValueError:
            continue
    return {
        "surfaces": surfaces,
        "boundary": (
            "Quadratic surfaces are local interpolation/surrogate models over the explicit 3x3 coded design only. "
            "R² measures fit to these simulated design points, not physical validation. Do not extrapolate outside coded [-1,+1], "
            "infer manufacturing probabilities, or treat a single fixed seed as a process distribution."
        ),
    }


def prediction_grid(surface: Mapping[str, Any], points: int = 31) -> dict[str, Any]:
    import numpy as np

    n = max(11, min(int(points), 101))
    axis = np.linspace(-1.0, 1.0, n)
    coeff = surface.get("coefficients") or {}
    z = [[predict_quadratic(coeff, float(x), float(y)) for x in axis] for y in axis]
    return {"codedA": [float(x) for x in axis], "codedB": [float(x) for x in axis], "predicted": z}


def run_two_factor_response_surface(
    namespace: Mapping[str, Any],
    *,
    factor_a: str,
    factor_b: str,
    seed: int,
    gamma: float,
    observer_distance_m: float = 100.0,
    transverse_half_width_mm: float = 1.0,
    transverse_points: int = 3,
    z_samples_per_period: int = 8,
    tracking_points_per_period: int = 24,
) -> dict[str, Any]:
    if factor_a == factor_b or factor_a not in ERROR_KEYS or factor_b not in ERROR_KEYS:
        raise ValueError("Choose two distinct supported manufacturing-error families")
    if gamma <= 1.0:
        raise ValueError("electron gamma must be > 1")

    prop = _load_propagation()
    if not prop._full_mode():
        raise RuntimeError("Radiation response-surface modeling requires Physical Lab Full mode")
    source, python = prop._managed_radiation_paths()
    prop._verify_radiation_source(source)
    if not python.is_file():
        raise RuntimeError("Radiation Platform isolated .venv is missing")

    import numpy as np

    params = dict(namespace.get("current_params") or {})
    if not params:
        raise RuntimeError("Current RADIA parameters are unavailable")
    if bool(params.get("target_b0_enabled")):
        raise ValueError("Freeze calibrated Br and disable target-B0 calibration before response-surface modeling")
    magnitudes = prop._active_manufacturing_errors(params)
    mag_a = abs(float(magnitudes.get(factor_a, 0.0)))
    mag_b = abs(float(magnitudes.get(factor_b, 0.0)))
    if mag_a <= 0.0 or mag_b <= 0.0:
        raise ValueError("Both selected factors must have non-zero configured manufacturing-error magnitudes")

    nx = int(transverse_points)
    if nx not in {3, 5}:
        raise ValueError("transverse_points must be 3 or 5")
    x_mm = np.linspace(-float(transverse_half_width_mm), float(transverse_half_width_mm), nx)
    y_mm = x_mm.copy()
    z_mm = prop._z_grid(namespace, params, int(z_samples_per_period))
    field_points = len(x_mm) * len(y_mm) * len(z_mm)
    if field_points > prop.MAX_FIELD_POINTS_PER_MEMBER:
        raise ValueError("Response-surface field grid exceeds the bounded per-realization limit")

    common = {
        "periodMm": float(params.get("period_mm", 50.0)),
        "deviceName": str(params.get("device", "radia-field-map")),
        "gamma": float(gamma),
        "nPeriods": int(params.get("periods", 20)),
        "pointsPerPeriod": int(tracking_points_per_period),
        "observerDistanceM": float(observer_distance_m),
        "thetaXMrad": 0.0,
        "thetaYMrad": 0.0,
        "includeAngularMap": False,
    }

    records = []
    with tempfile.TemporaryDirectory(prefix="physical-lab-radiation-response-surface-") as td:
        tmp = Path(td)
        for coded_a in CODED_LEVELS:
            for coded_b in CODED_LEVELS:
                scale_a = LEVEL_TO_SCALE[coded_a]
                scale_b = LEVEL_TO_SCALE[coded_b]
                p = dict(params)
                for key in ERROR_KEYS:
                    p[key] = 0.0
                p[factor_a] = mag_a * scale_a
                p[factor_b] = mag_b * scale_b
                active = abs(p[factor_a]) > 0.0 or abs(p[factor_b]) > 0.0
                p["errors_enabled"] = active
                p["error_seed"] = int(seed)
                field = prop._build_and_sample_3d(namespace, p, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
                map_path = tmp / f"a{coded_a:+.0f}_b{coded_b:+.0f}.npz"
                np.savez_compressed(map_path, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=field)
                record = prop._invoke_radiation_worker(
                    source, python, map_path,
                    {**common, "sourceLabel": f"Physical Lab response surface {factor_a}={scale_a:.2f}M, {factor_b}={scale_b:.2f}M, seed {int(seed)}"},
                    tmp / f"a{coded_a:+.0f}_b{coded_b:+.0f}.json",
                )
                record.update({
                    "codedA": float(coded_a), "codedB": float(coded_b),
                    "scaleA": float(scale_a), "scaleB": float(scale_b),
                    "factorAValue": float(p[factor_a]), "factorBValue": float(p[factor_b]),
                })
                records.append(record)

    summary = summarize_response_surfaces(records, factor_a=factor_a, factor_b=factor_b)
    return {
        "schema": "physical-lab-radiation-response-surface-v1",
        "factorA": factor_a,
        "factorB": factor_b,
        "configuredMagnitudes": {factor_a: mag_a, factor_b: mag_b},
        "codedLevelToScale": {str(int(k)): v for k, v in LEVEL_TO_SCALE.items()},
        "seed": int(seed),
        "designPointCount": len(records),
        "grid": {"transversePoints": nx, "zPoints": int(len(z_mm)), "fieldPointsPerRun": int(field_points)},
        "records": records,
        "summary": summary,
        "boundary": summary["boundary"],
    }
