"""One-factor-at-a-time manufacturing-error attribution for RADIA -> radiation physics.

This module deliberately avoids a synthetic global sensitivity/quality score. It
holds all but one configured manufacturing-error magnitude at zero, rebuilds the
real RADIA field for a small fixed seed set, then propagates each realization
through the pinned Radiation Platform scalar trajectory/radiation solver.

The result is screening evidence: which configured error family most strongly
moves each observable under the explicit finite perturbations tested here. It is
not a Sobol/global-sensitivity analysis and does not prove production statistics.
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


def summarize_one_factor_records(
    nominal: Mapping[str, Any],
    records_by_error: Mapping[str, Sequence[Mapping[str, Any]]],
    error_magnitudes: Mapping[str, float],
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
) -> dict[str, Any]:
    """Summarize already-computed OFAT records without combining unlike units."""
    import numpy as np

    nominal_obs = nominal.get("observables") if isinstance(nominal.get("observables"), Mapping) else nominal
    rows: list[dict[str, Any]] = []
    by_metric: dict[str, list[dict[str, Any]]] = {m: [] for m in metrics}

    for error_key in ERROR_KEYS:
        members = list(records_by_error.get(error_key) or [])
        magnitude = abs(float(error_magnitudes.get(error_key, 0.0) or 0.0))
        if magnitude <= 0.0 or not members:
            continue
        for metric in metrics:
            n0 = _finite(nominal_obs.get(metric))
            if n0 is None:
                continue
            values: list[float] = []
            for member in members:
                obs = member.get("observables") if isinstance(member.get("observables"), Mapping) else member
                x = _finite(obs.get(metric))
                if x is not None:
                    values.append(x)
            if not values:
                continue
            arr = np.asarray(values, dtype=float)
            delta = arr - n0
            abs_delta = np.abs(delta)
            row = {
                "error": error_key,
                "inputMagnitude": magnitude,
                "metric": metric,
                "nominal": n0,
                "count": int(len(arr)),
                "meanSignedDelta": float(np.mean(delta)),
                "medianAbsDelta": float(np.median(abs_delta)),
                "maxAbsDelta": float(np.max(abs_delta)),
                "medianAbsDeltaPerInputUnit": float(np.median(abs_delta) / magnitude),
                "maxAbsDeltaPerInputUnit": float(np.max(abs_delta) / magnitude),
            }
            rows.append(row)
            by_metric[metric].append(row)

    leaders: dict[str, Any] = {}
    for metric, metric_rows in by_metric.items():
        if not metric_rows:
            continue
        # Compare configured perturbations by absolute output movement. This is
        # intentionally metric-local; there is no cross-metric global score.
        winner = max(metric_rows, key=lambda r: r["medianAbsDelta"])
        leaders[metric] = {
            "error": winner["error"],
            "medianAbsDelta": winner["medianAbsDelta"],
            "inputMagnitude": winner["inputMagnitude"],
            "evidenceCount": winner["count"],
        }

    return {
        "rows": rows,
        "leadersByMetric": leaders,
        "boundary": (
            "This is finite one-factor-at-a-time screening at the explicitly configured error magnitudes and seeds. "
            "It does not capture interaction terms, infer process distributions, or replace global sensitivity / tolerance analysis. "
            "No cross-metric aggregate quality score is formed."
        ),
    }


def run_one_factor_sensitivity(
    namespace: Mapping[str, Any],
    *,
    seeds: Sequence[int],
    gamma: float,
    observer_distance_m: float = 100.0,
    theta_x_mrad: float = 0.0,
    theta_y_mrad: float = 0.0,
    transverse_half_width_mm: float = 1.0,
    transverse_points: int = 3,
    z_samples_per_period: int = 8,
    tracking_points_per_period: int = 24,
) -> dict[str, Any]:
    """Run bounded OFAT screening through real RADIA fields and pinned radiation physics."""
    if len(seeds) < 2 or len(seeds) > 4:
        raise ValueError("Use 2 to 4 fixed seeds for one-factor sensitivity screening")
    if len(set(int(s) for s in seeds)) != len(seeds):
        raise ValueError("Sensitivity seeds must be distinct")
    if gamma <= 1.0:
        raise ValueError("electron gamma must be > 1")

    prop = _load_propagation()
    if not prop._full_mode():
        raise RuntimeError("Manufacturing radiation sensitivity requires Physical Lab Full mode")
    source, python = prop._managed_radiation_paths()
    prop._verify_radiation_source(source)
    if not python.is_file():
        raise RuntimeError("Radiation Platform isolated .venv is missing")

    import numpy as np

    params = dict(namespace.get("current_params") or {})
    if not params:
        raise RuntimeError("Current RADIA parameters are unavailable")
    if bool(params.get("target_b0_enabled")):
        raise ValueError("Freeze calibrated Br and disable target-B0 calibration before sensitivity screening")
    magnitudes = prop._active_manufacturing_errors(params)
    active = [k for k in ERROR_KEYS if abs(float(magnitudes.get(k, 0.0))) > 0.0]
    if not active:
        raise ValueError("Enter at least one non-zero manufacturing-error magnitude")

    nx = int(transverse_points)
    if nx not in {3, 5}:
        raise ValueError("transverse_points must be 3 or 5 for screening")
    x_mm = np.linspace(-float(transverse_half_width_mm), float(transverse_half_width_mm), nx)
    y_mm = x_mm.copy()
    z_mm = prop._z_grid(namespace, params, int(z_samples_per_period))
    field_points = len(x_mm) * len(y_mm) * len(z_mm)
    if field_points > prop.MAX_FIELD_POINTS_PER_MEMBER:
        raise ValueError("Sensitivity field grid exceeds the bounded per-realization limit")

    common_worker = {
        "periodMm": float(params.get("period_mm", 50.0)),
        "deviceName": str(params.get("device", "radia-field-map")),
        "gamma": float(gamma),
        "nPeriods": int(params.get("periods", 20)),
        "pointsPerPeriod": int(tracking_points_per_period),
        "observerDistanceM": float(observer_distance_m),
        "thetaXMrad": float(theta_x_mrad),
        "thetaYMrad": float(theta_y_mrad),
        "includeAngularMap": False,
    }

    with tempfile.TemporaryDirectory(prefix="physical-lab-radiation-sensitivity-") as td:
        tmp = Path(td)
        nominal_params = dict(params)
        nominal_params["errors_enabled"] = False
        nominal_field = prop._build_and_sample_3d(namespace, nominal_params, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
        nominal_map = tmp / "nominal.npz"
        np.savez_compressed(nominal_map, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=nominal_field)
        nominal = prop._invoke_radiation_worker(
            source, python, nominal_map,
            {**common_worker, "sourceLabel": "Physical Lab OFAT nominal RADIA field"},
            tmp / "nominal.json",
        )

        records_by_error: dict[str, list[dict[str, Any]]] = {}
        for error_key in active:
            rows: list[dict[str, Any]] = []
            for seed in [int(s) for s in seeds]:
                p = dict(params)
                p["errors_enabled"] = True
                p["error_seed"] = seed
                for key in ERROR_KEYS:
                    p[key] = float(magnitudes.get(key, 0.0)) if key == error_key else 0.0
                field = prop._build_and_sample_3d(namespace, p, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
                map_path = tmp / f"{error_key}-{seed}.npz"
                np.savez_compressed(map_path, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=field)
                record = prop._invoke_radiation_worker(
                    source, python, map_path,
                    {**common_worker, "sourceLabel": f"Physical Lab OFAT {error_key} seed {seed}"},
                    tmp / f"{error_key}-{seed}.json",
                )
                record["seed"] = seed
                record["error"] = error_key
                rows.append(record)
            records_by_error[error_key] = rows

    summary = summarize_one_factor_records(nominal, records_by_error, magnitudes)
    return {
        "schema": "physical-lab-radiation-ofat-sensitivity-v1",
        "activeErrors": active,
        "errorMagnitudes": {k: float(magnitudes[k]) for k in active},
        "seeds": [int(s) for s in seeds],
        "grid": {"transversePoints": nx, "zPoints": int(len(z_mm)), "fieldPointsPerRun": int(field_points)},
        "nominal": nominal,
        "recordsByError": records_by_error,
        "summary": summary,
        "boundary": summary["boundary"],
    }
