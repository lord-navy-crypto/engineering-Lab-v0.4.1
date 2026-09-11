"""Targeted nominal-vs-manufacturing-seed angular radiation comparison.

The finite manufacturing ensemble remains scalar for throughput. This module
rebuilds only the nominal field and one explicitly selected seed, then invokes
the full pinned trajectory/radiation solver for both. It is therefore suitable
for follow-up diagnosis after the scalar ensemble identifies a seed of interest.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any, Mapping


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _matrix(values):
    import numpy as np

    return np.asarray([[np.nan if value is None else float(value) for value in row] for row in values], dtype=float)


def compare_angular_maps(nominal: Mapping[str, Any], seeded: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np

    a0 = nominal.get("angularMap") if isinstance(nominal.get("angularMap"), Mapping) else None
    a1 = seeded.get("angularMap") if isinstance(seeded.get("angularMap"), Mapping) else None
    if not a0 or not a1:
        raise ValueError("Both records must contain angularMap evidence")
    tx0 = np.asarray(a0.get("theta_x_rad"), dtype=float)
    ty0 = np.asarray(a0.get("theta_y_rad"), dtype=float)
    tx1 = np.asarray(a1.get("theta_x_rad"), dtype=float)
    ty1 = np.asarray(a1.get("theta_y_rad"), dtype=float)
    if tx0.shape != tx1.shape or ty0.shape != ty1.shape or not np.allclose(tx0, tx1) or not np.allclose(ty0, ty1):
        raise ValueError("Nominal and seeded angular grids do not match")

    valid0 = np.asarray(a0.get("valid_mask"), dtype=bool)
    valid1 = np.asarray(a1.get("valid_mask"), dtype=bool)
    valid = valid0 & valid1
    if valid.ndim != 2 or not np.any(valid):
        raise ValueError("No mutually valid angular pixels are available")

    fields = {
        "fluence_J_m2": ("absolute", None),
        "P_lin": ("absolute", None),
        "P_circ": ("absolute", None),
        "f_peak_hz": ("relative", None),
    }
    maps: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    for key, (mode, _) in fields.items():
        m0 = _matrix(a0.get(key, []))
        m1 = _matrix(a1.get(key, []))
        if m0.shape != valid.shape or m1.shape != valid.shape:
            raise ValueError(f"{key} shape does not match validity grid")
        good = valid & np.isfinite(m0) & np.isfinite(m1)
        delta = np.full_like(m0, np.nan, dtype=float)
        delta[good] = m1[good] - m0[good]
        abs_delta = np.abs(delta[good])
        row = {
            "validPixelCount": int(np.sum(good)),
            "meanDelta": float(np.mean(delta[good])) if np.any(good) else None,
            "rmsDelta": float(np.sqrt(np.mean(delta[good] ** 2))) if np.any(good) else None,
            "maxAbsDelta": float(np.max(abs_delta)) if np.any(good) else None,
        }
        if mode == "relative":
            denom = np.abs(m0)
            rel_good = good & (denom > 1e-30)
            rel = np.full_like(m0, np.nan, dtype=float)
            rel[rel_good] = delta[rel_good] / denom[rel_good]
            row["rmsRelativeDelta"] = float(np.sqrt(np.mean(rel[rel_good] ** 2))) if np.any(rel_good) else None
            row["maxAbsRelativeDelta"] = float(np.max(np.abs(rel[rel_good]))) if np.any(rel_good) else None
        maps[key] = [[None if not math.isfinite(float(value)) else float(value) for value in row_values] for row_values in delta]
        metrics[key] = row

    nominal_obs = nominal.get("observables") if isinstance(nominal.get("observables"), Mapping) else {}
    seeded_obs = seeded.get("observables") if isinstance(seeded.get("observables"), Mapping) else {}
    nominal_st = nominal.get("stokes") if isinstance(nominal.get("stokes"), Mapping) else {}
    seeded_st = seeded.get("stokes") if isinstance(seeded.get("stokes"), Mapping) else {}
    scalar = {}
    for key, src0, src1 in (
        ("photon_energy_eV", nominal_obs, seeded_obs),
        ("relative_linewidth", nominal_obs, seeded_obs),
        ("P_lin", nominal_st, seeded_st),
        ("P_circ", nominal_st, seeded_st),
        ("polarization_degree", nominal_st, seeded_st),
    ):
        v0 = _finite(src0.get(key))
        v1 = _finite(src1.get(key))
        if v0 is None or v1 is None:
            continue
        scalar[key] = {"nominal": v0, "seeded": v1, "delta": v1 - v0}

    return {
        "schema": "physical-lab-radiation-seed-map-comparison-v1",
        "theta_x_rad": [float(x) for x in tx0],
        "theta_y_rad": [float(y) for y in ty0],
        "mutuallyValidPixels": int(np.sum(valid)),
        "deltaMaps": maps,
        "mapMetrics": metrics,
        "scalarDeltas": scalar,
        "boundary": (
            "This compares one explicitly simulated manufacturing realization with the nominal device on the same single-electron angular grid. "
            "It diagnoses spatial radiation changes for that seed only; it is not a population yield estimate or worst-case guarantee outside the sampled seeds."
        ),
    }


def run_seed_map_comparison(
    namespace: Mapping[str, Any],
    propagation_module,
    *,
    seed: int,
    transverse_half_width_mm: float,
    transverse_points: int,
    z_samples_per_period: int,
    gamma: float,
    observer_distance_m: float,
    tracking_points_per_period: int,
    angular_grid_points: int,
    angular_extent_gamma_theta: float,
    angular_observer_samples: int,
) -> dict[str, Any]:
    if not propagation_module._full_mode():
        raise RuntimeError("Targeted seed radiation comparison requires Physical Lab Full mode")
    source, python = propagation_module._managed_radiation_paths()
    propagation_module._verify_radiation_source(source)
    params = dict(namespace.get("current_params") or {})
    if not params:
        raise RuntimeError("Current RADIA parameters are unavailable")
    if bool(params.get("target_b0_enabled")):
        raise ValueError("Freeze calibrated Br and disable target-B0 calibration before comparing manufacturing seeds")

    import numpy as np

    nx = int(transverse_points)
    x_mm = np.linspace(-float(transverse_half_width_mm), float(transverse_half_width_mm), nx)
    y_mm = x_mm.copy()
    z_mm = propagation_module._z_grid(namespace, params, int(z_samples_per_period))
    common = {
        "periodMm": float(params.get("period_mm", 50.0)),
        "deviceName": str(params.get("device", "radia-field-map")),
        "gamma": float(gamma),
        "nPeriods": int(params.get("periods", 20)),
        "pointsPerPeriod": int(tracking_points_per_period),
        "observerDistanceM": float(observer_distance_m),
        "thetaXMrad": 0.0,
        "thetaYMrad": 0.0,
        "includeAngularMap": True,
        "angularGridPoints": int(angular_grid_points),
        "angularExtentGammaTheta": float(angular_extent_gamma_theta),
        "angularObserverSamples": int(angular_observer_samples),
    }

    with tempfile.TemporaryDirectory(prefix="physical-lab-seed-map-") as td:
        tmp = Path(td)
        nominal_params = dict(params)
        nominal_params["errors_enabled"] = False
        seeded_params = dict(params)
        seeded_params["errors_enabled"] = True
        seeded_params["error_seed"] = int(seed)

        nominal_field = propagation_module._build_and_sample_3d(namespace, nominal_params, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
        seeded_field = propagation_module._build_and_sample_3d(namespace, seeded_params, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
        nominal_map = tmp / "nominal.npz"
        seeded_map = tmp / f"seed-{int(seed)}.npz"
        np.savez_compressed(nominal_map, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=nominal_field)
        np.savez_compressed(seeded_map, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=seeded_field)

        nominal = propagation_module._invoke_radiation_worker(
            source, python, nominal_map,
            {**common, "sourceLabel": "Physical Lab nominal RADIA field for targeted radiation map comparison"},
            tmp / "nominal.json",
        )
        seeded = propagation_module._invoke_radiation_worker(
            source, python, seeded_map,
            {**common, "sourceLabel": f"Physical Lab RADIA manufacturing seed {int(seed)} for targeted radiation map comparison"},
            tmp / "seeded.json",
        )

    return {
        "seed": int(seed),
        "nominal": nominal,
        "seeded": seeded,
        "comparison": compare_angular_maps(nominal, seeded),
    }
