#!/usr/bin/env python3
"""Run pinned Radiation Platform physics on one Physical Lab 3-D field map.

The worker preserves per-Lab dependency isolation. Ordinary manufacturing
ensembles use the lighter scalar solver. When an angular map is explicitly
requested, the worker upgrades to the full trajectory result because the pinned
Radiation Platform angular-map routine requires fitted trajectory splines.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

RADIATION_PLATFORM_REVISION = "6d19b36304c9d30f9b608214f7cfb9fcbaf941d4"


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _observer_vector(distance_m: float, theta_x_mrad: float, theta_y_mrad: float):
    import numpy as np

    tx = 1e-3 * float(theta_x_mrad)
    ty = 1e-3 * float(theta_y_mrad)
    return np.asarray([
        float(distance_m) * math.tan(tx),
        float(distance_m) * math.tan(ty),
        float(distance_m),
    ], dtype=float)


def _extract_stokes(result: dict[str, Any]) -> dict[str, Any]:
    nested = result.get("Stokes") if isinstance(result.get("Stokes"), dict) else {}
    out = {key: _finite(nested.get(key)) for key in ("I", "Q", "U", "V", "P_lin", "P_circ")}
    # run_sim_scalar intentionally flattens the two polarization fractions.
    if out["P_lin"] is None:
        out["P_lin"] = _finite(result.get("P_lin"))
    if out["P_circ"] is None:
        out["P_circ"] = _finite(result.get("P_circ"))
    plin = out.get("P_lin")
    pcirc = out.get("P_circ")
    out["polarization_degree"] = (
        math.sqrt(plin * plin + pcirc * pcirc)
        if plin is not None and pcirc is not None else None
    )
    out["basis_convention"] = nested.get("basis_convention")
    out["V_convention"] = nested.get("V_convention")
    return out


def _extract_harmonics(result: dict[str, Any]) -> dict[str, Any]:
    nested = result.get("harmonic_ratios") if isinstance(result.get("harmonic_ratios"), dict) else {}
    out = {str(key): _finite(value) for key, value in nested.items() if _finite(value) is not None}
    # Scalar runtime schema exposes these at top level.
    for key in ("H3_over_H1", "H5_over_H1", "radiation_H3_over_H1", "radiation_H5_over_H1"):
        value = _finite(result.get(key))
        if value is not None:
            canonical = key.replace("radiation_", "")
            out.setdefault(canonical, value)
    return out


def _extract_result(result: dict[str, Any]) -> dict[str, Any]:
    photon = result.get("photon_energy") if isinstance(result.get("photon_energy"), dict) else {}
    kcomp = result.get("K_components") if isinstance(result.get("K_components"), dict) else {}
    traj_phase = result.get("trajectory_phase") if isinstance(result.get("trajectory_phase"), dict) else {}
    residuals = result.get("theory_residuals") if isinstance(result.get("theory_residuals"), dict) else {}
    names = [
        "f0", "P_larmor", "relative_linewidth", "spectral_fwhm_hz",
        "spectral_quality_factor", "P_circ", "gamma_avg",
        "max_transverse_excursion_m", "period_repeatability_rms_m",
        "orbit_phase_error_rms_rad", "exit_xprime_rad", "exit_yprime_rad",
        "frequency_relative_residual",
    ]
    out = {name: _finite(result.get(name)) for name in names}
    for key in ("max_transverse_excursion_m", "period_repeatability_rms_m", "orbit_phase_error_rms_rad", "exit_xprime_rad", "exit_yprime_rad"):
        if out.get(key) is None:
            out[key] = _finite(traj_phase.get(key))
    if out.get("frequency_relative_residual") is None:
        out["frequency_relative_residual"] = _finite(residuals.get("frequency_relative_residual"))

    photon_energy_eV = _finite(photon.get("eV"))
    if photon_energy_eV is None:
        photon_energy_eV = _finite(result.get("photon_energy_eV"))
    out["photon_energy_eV"] = photon_energy_eV

    for key in ("K0", "Kx", "Ky", "K_eff_rms"):
        value = _finite(kcomp.get(key))
        if value is None:
            value = _finite(result.get(key))
        out[f"K_{key}"] = value

    st = _extract_stokes(result)
    out["P_lin"] = st.get("P_lin")
    out["P_circ"] = st.get("P_circ") if st.get("P_circ") is not None else out.get("P_circ")
    out["polarization_degree"] = st.get("polarization_degree")
    harmonics = _extract_harmonics(result)
    out["H3_over_H1"] = harmonics.get("H3_over_H1")
    out["H5_over_H1"] = harmonics.get("H5_over_H1")
    return out


def _json_safe_matrix(values):
    import numpy as np

    arr = np.asarray(values)
    if arr.ndim != 2:
        raise ValueError("angular-map quantity must be a 2-D array")
    return [[_finite(x) for x in row] for row in arr]


def _extract_angular_map(v11, result: dict[str, Any], cfg: dict[str, Any], gamma: float) -> dict[str, Any] | None:
    import numpy as np

    if not bool(cfg.get("includeAngularMap", False)):
        return None
    if "splines" not in result:
        raise RuntimeError("Angular radiation requires a full trajectory result with fitted splines")
    grid_points = int(cfg.get("angularGridPoints", 9))
    if grid_points < 5 or grid_points > 15 or grid_points % 2 == 0:
        raise ValueError("angularGridPoints must be an odd integer from 5 through 15")
    extent = float(cfg.get("angularExtentGammaTheta", 3.0))
    if not (0.25 <= extent <= 8.0):
        raise ValueError("angularExtentGammaTheta must be between 0.25 and 8")
    n_obs = int(cfg.get("angularObserverSamples", 1200))
    if n_obs < 400 or n_obs > 6000:
        raise ValueError("angularObserverSamples must be between 400 and 6000")
    distance = float(cfg.get("observerDistanceM", 100.0))

    angular = v11.angular_map_2d(
        result,
        gamma_for_grid=gamma,
        grid_points=grid_points,
        extent_gamma_theta=extent,
        observer_distance=distance,
        n_obs=n_obs,
    )
    theta_x = np.asarray(angular.get("theta_x"), dtype=float)
    theta_y = np.asarray(angular.get("theta_y"), dtype=float)
    return {
        "theta_x_rad": [float(x) for x in theta_x],
        "theta_y_rad": [float(x) for x in theta_y],
        "fluence_J_m2": _json_safe_matrix(angular.get("fluence_J_m2")),
        "P_circ": _json_safe_matrix(angular.get("P_circ")),
        "P_lin": _json_safe_matrix(angular.get("P_lin")),
        "f_peak_hz": _json_safe_matrix(angular.get("f_peak_hz")),
        "f_expected_hz": _json_safe_matrix(angular.get("f_expected_hz")),
        "valid_mask": [[bool(x) for x in row] for row in np.asarray(angular.get("valid_mask"), dtype=bool)],
        "failure_count": int(angular.get("failure_count", 0)),
        "failures": list(angular.get("failures", []))[:25],
        "mean_theta_x_rad": _finite(angular.get("mean_theta_x_rad")),
        "mean_theta_y_rad": _finite(angular.get("mean_theta_y_rad")),
        "rms_divergence_x_rad": _finite(angular.get("rms_divergence_x_rad")),
        "rms_divergence_y_rad": _finite(angular.get("rms_divergence_y_rad")),
        "grid_points": grid_points,
        "extent_gamma_theta": extent,
        "observer_samples": n_obs,
        "boundary": "Each valid pixel is recomputed from the pinned single-electron trajectory/radiation solver. Failed pixels remain null rather than being silently replaced by zero. This is not a bunch-emittance, beamline-optics or detector map.",
    }


def run(config_path: Path, output_path: Path) -> None:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    source = Path(str(cfg["radiationPlatformSource"])).resolve()
    map_path = Path(str(cfg["fieldMapNpz"])).resolve()
    if not source.is_dir():
        raise RuntimeError(f"Radiation Platform source is missing: {source}")
    if not map_path.is_file():
        raise RuntimeError(f"3-D field-map evidence is missing: {map_path}")

    sys.path.insert(0, str(source))
    import numpy as np
    import pandas as pd
    import undulator_v11_radia_integrated_v9 as v11

    data = np.load(map_path, allow_pickle=False)
    x_mm = np.asarray(data["x_mm"], dtype=float)
    y_mm = np.asarray(data["y_mm"], dtype=float)
    z_mm = np.asarray(data["z_mm"], dtype=float)
    field = np.asarray(data["B_T"], dtype=float)
    expected = (len(z_mm), len(y_mm), len(x_mm), 3)
    if field.shape != expected:
        raise ValueError(f"field-map shape {field.shape} does not match expected {expected}")
    if min(len(x_mm), len(y_mm)) < 3 or len(z_mm) < 9:
        raise ValueError("field map is too small for a 3-D Radiation Platform device")
    if not np.all(np.isfinite(field)):
        raise ValueError("field map contains non-finite values")

    bt = np.transpose(field, (2, 1, 0, 3))
    X, Y, Z = np.meshgrid(x_mm * 1e-3, y_mm * 1e-3, z_mm * 1e-3, indexing="ij")
    frame = pd.DataFrame({
        "x_m": X.ravel(), "y_m": Y.ravel(), "z_m": Z.ravel(),
        "Bx_T": bt[..., 0].ravel(), "By_T": bt[..., 1].ravel(), "Bz_T": bt[..., 2].ravel(),
    })
    device = v11._field_map_from_dataframe(
        frame,
        lambda_u=float(cfg["periodMm"]) * 1e-3,
        device_name=str(cfg.get("deviceName", "radia-field-map")),
        handedness=int(cfg.get("handedness", 1)),
        shift_z_to_zero=True,
        source_label=str(cfg.get("sourceLabel", "Physical Lab RADIA manufacturing realization")),
    )

    gamma = float(cfg["gamma"])
    n_periods = int(cfg["nPeriods"])
    ppp = int(cfg.get("pointsPerPeriod", 48))
    span = v11.simulation_span_for_device(gamma, device, n_periods=n_periods)
    n_base = v11.samples_for_periods(
        n_periods,
        pts_per_period=ppp,
        min_pts=max(1000, n_periods * ppp),
        max_pts=max(4000, n_periods * ppp + 1),
    )
    observer = _observer_vector(
        float(cfg.get("observerDistanceM", 100.0)),
        float(cfg.get("thetaXMrad", 0.0)),
        float(cfg.get("thetaYMrad", 0.0)),
    )

    include_angular = bool(cfg.get("includeAngularMap", False))
    solver = v11.run_sim if include_angular else v11.run_sim_scalar
    result = solver(
        device,
        None,
        span,
        observer,
        n_base=n_base,
        gamma0_input=gamma,
        rtol=float(cfg.get("rtol", 1e-9)),
        atol=float(cfg.get("atol", 1e-11)),
    )
    if not result:
        raise RuntimeError("Radiation Platform returned no result")

    angular_map = _extract_angular_map(v11, result, cfg, gamma)
    payload = {
        "schema": "physical-lab-radia-radiation-worker-v2",
        "radiationPlatformRevision": RADIATION_PLATFORM_REVISION,
        "solverMode": "full-trajectory" if include_angular else "scalar",
        "fieldMap": {
            "nx": int(len(x_mm)), "ny": int(len(y_mm)), "nz": int(len(z_mm)),
            "points": int(len(x_mm) * len(y_mm) * len(z_mm)),
        },
        "inputs": {
            "gamma": gamma,
            "nPeriods": n_periods,
            "pointsPerPeriod": ppp,
            "observerDistanceM": float(cfg.get("observerDistanceM", 100.0)),
            "thetaXMrad": float(cfg.get("thetaXMrad", 0.0)),
            "thetaYMrad": float(cfg.get("thetaYMrad", 0.0)),
        },
        "observables": _extract_result(result),
        "stokes": _extract_stokes(result),
        "harmonicRatios": _extract_harmonics(result),
        "angularMap": angular_map,
        "boundary": "Scalar and optional angular observables come from the pinned Radiation Platform single-electron field-map trajectory/radiation solver. They do not include bunch emittance, energy spread, coherent effects, beamline optics or detector response.",
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(Path(args.config), Path(args.output))


if __name__ == "__main__":
    main()
