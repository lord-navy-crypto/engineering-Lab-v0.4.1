"""Bounded two-factor interaction screening for RADIA -> radiation observables.

For each selected manufacturing-error pair A,B, evaluate the same seed at four
states: nominal, A only, B only, and A+B. The second-order interaction residual
is

    I_AB = y(A+B) - y(A) - y(B) + y(0)

which removes the two main effects before judging non-additivity. This is a
finite local screening experiment at explicit perturbation magnitudes and seeds,
not a Sobol decomposition or production-process model.
"""
from __future__ import annotations

import importlib.util
import itertools
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


def _obs(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return record.get("observables") if isinstance(record.get("observables"), Mapping) else record


def summarize_pair_records(
    records: Sequence[Mapping[str, Any]],
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
) -> dict[str, Any]:
    """Summarize precomputed 0/A/B/AB records using the factorial interaction contrast."""
    import numpy as np

    rows: list[dict[str, Any]] = []
    by_metric: dict[str, list[dict[str, Any]]] = {m: [] for m in metrics}
    for item in records:
        pair = tuple(item.get("pair") or ())
        if len(pair) != 2:
            continue
        states = item.get("states") if isinstance(item.get("states"), Mapping) else {}
        r0, ra, rb, rab = (states.get(k) for k in ("nominal", "A", "B", "AB"))
        if not all(isinstance(x, Mapping) for x in (r0, ra, rb, rab)):
            continue
        for metric in metrics:
            y0 = _finite(_obs(r0).get(metric))
            ya = _finite(_obs(ra).get(metric))
            yb = _finite(_obs(rb).get(metric))
            yab = _finite(_obs(rab).get(metric))
            if None in (y0, ya, yb, yab):
                continue
            main_a = ya - y0
            main_b = yb - y0
            interaction = yab - ya - yb + y0
            additive_prediction = y0 + main_a + main_b
            main_scale = abs(main_a) + abs(main_b)
            ratio = abs(interaction) / main_scale if main_scale > 1e-30 else None
            row = {
                "errorA": pair[0],
                "errorB": pair[1],
                "seed": item.get("seed"),
                "metric": metric,
                "nominal": y0,
                "mainEffectA": main_a,
                "mainEffectB": main_b,
                "combinedDelta": yab - y0,
                "interactionResidual": interaction,
                "absInteractionResidual": abs(interaction),
                "interactionToMainScale": ratio,
                "additivePrediction": additive_prediction,
                "combinedValue": yab,
            }
            rows.append(row)
            by_metric[metric].append(row)

    leaders = {}
    for metric, metric_rows in by_metric.items():
        if metric_rows:
            top = max(metric_rows, key=lambda r: r["absInteractionResidual"])
            leaders[metric] = {
                "errorA": top["errorA"],
                "errorB": top["errorB"],
                "seed": top["seed"],
                "absInteractionResidual": top["absInteractionResidual"],
                "interactionToMainScale": top["interactionToMainScale"],
            }

    grouped = []
    keys = sorted({(r["errorA"], r["errorB"], r["metric"]) for r in rows})
    for a, b, metric in keys:
        vals = [r["interactionResidual"] for r in rows if r["errorA"] == a and r["errorB"] == b and r["metric"] == metric]
        ratios = [r["interactionToMainScale"] for r in rows if r["errorA"] == a and r["errorB"] == b and r["metric"] == metric and r["interactionToMainScale"] is not None]
        arr = np.asarray(vals, dtype=float)
        grouped.append({
            "errorA": a,
            "errorB": b,
            "metric": metric,
            "count": int(len(arr)),
            "meanInteractionResidual": float(np.mean(arr)),
            "medianAbsInteractionResidual": float(np.median(np.abs(arr))),
            "maxAbsInteractionResidual": float(np.max(np.abs(arr))),
            "medianInteractionToMainScale": float(np.median(ratios)) if ratios else None,
        })

    return {
        "rows": rows,
        "grouped": grouped,
        "leadersByMetric": leaders,
        "boundary": (
            "The factorial contrast removes the two isolated main effects before measuring pairwise non-additivity. "
            "Results are local to the configured perturbation magnitudes and fixed seeds; they do not capture higher-order interactions, "
            "global variance decomposition, process distributions, or manufacturing yield."
        ),
    }


def run_pair_interactions(
    namespace: Mapping[str, Any],
    *,
    pairs: Sequence[Sequence[str]],
    seeds: Sequence[int],
    gamma: float,
    observer_distance_m: float = 100.0,
    transverse_half_width_mm: float = 1.0,
    transverse_points: int = 3,
    z_samples_per_period: int = 8,
    tracking_points_per_period: int = 24,
) -> dict[str, Any]:
    if gamma <= 1.0:
        raise ValueError("electron gamma must be > 1")
    if len(seeds) < 1 or len(seeds) > 2:
        raise ValueError("Use one or two fixed seeds for pairwise interaction screening")
    if len(set(int(s) for s in seeds)) != len(seeds):
        raise ValueError("Interaction seeds must be distinct")

    norm_pairs = []
    for pair in pairs:
        if len(pair) != 2:
            raise ValueError("Each interaction pair must contain exactly two error keys")
        a, b = str(pair[0]), str(pair[1])
        if a == b or a not in ERROR_KEYS or b not in ERROR_KEYS:
            raise ValueError(f"Invalid manufacturing-error pair: {pair}")
        key = tuple(sorted((a, b), key=ERROR_KEYS.index))
        if key not in norm_pairs:
            norm_pairs.append(key)
    if not norm_pairs or len(norm_pairs) > 3:
        raise ValueError("Select one to three unique error pairs")

    prop = _load_propagation()
    if not prop._full_mode():
        raise RuntimeError("Pairwise radiation interaction screening requires Physical Lab Full mode")
    source, python = prop._managed_radiation_paths()
    prop._verify_radiation_source(source)
    if not python.is_file():
        raise RuntimeError("Radiation Platform isolated .venv is missing")

    import numpy as np

    params = dict(namespace.get("current_params") or {})
    if not params:
        raise RuntimeError("Current RADIA parameters are unavailable")
    if bool(params.get("target_b0_enabled")):
        raise ValueError("Freeze calibrated Br and disable target-B0 calibration before interaction screening")
    magnitudes = prop._active_manufacturing_errors(params)
    for a, b in norm_pairs:
        if abs(float(magnitudes.get(a, 0.0))) <= 0 or abs(float(magnitudes.get(b, 0.0))) <= 0:
            raise ValueError(f"Both errors in pair {a} × {b} must have non-zero configured magnitudes")

    nx = int(transverse_points)
    if nx not in {3, 5}:
        raise ValueError("transverse_points must be 3 or 5")
    x_mm = np.linspace(-float(transverse_half_width_mm), float(transverse_half_width_mm), nx)
    y_mm = x_mm.copy()
    z_mm = prop._z_grid(namespace, params, int(z_samples_per_period))
    field_points = len(x_mm) * len(y_mm) * len(z_mm)
    if field_points > prop.MAX_FIELD_POINTS_PER_MEMBER:
        raise ValueError("Interaction field grid exceeds the bounded per-realization limit")

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
    with tempfile.TemporaryDirectory(prefix="physical-lab-radiation-interaction-") as td:
        tmp = Path(td)
        nominal_params = dict(params)
        nominal_params["errors_enabled"] = False
        nominal_field = prop._build_and_sample_3d(namespace, nominal_params, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
        nominal_map = tmp / "nominal.npz"
        np.savez_compressed(nominal_map, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=nominal_field)
        nominal = prop._invoke_radiation_worker(source, python, nominal_map, {**common, "sourceLabel": "Physical Lab pairwise-interaction nominal field"}, tmp / "nominal.json")

        for a, b in norm_pairs:
            for seed in [int(s) for s in seeds]:
                states = {"nominal": nominal}
                for label, enabled in (("A", (a,)), ("B", (b,)), ("AB", (a, b))):
                    p = dict(params)
                    p["errors_enabled"] = True
                    p["error_seed"] = seed
                    for key in ERROR_KEYS:
                        p[key] = float(magnitudes.get(key, 0.0)) if key in enabled else 0.0
                    field = prop._build_and_sample_3d(namespace, p, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
                    map_path = tmp / f"{a}__{b}__{seed}__{label}.npz"
                    np.savez_compressed(map_path, x_mm=x_mm, y_mm=y_mm, z_mm=z_mm, B_T=field)
                    states[label] = prop._invoke_radiation_worker(
                        source, python, map_path,
                        {**common, "sourceLabel": f"Physical Lab pairwise interaction {a} × {b} seed {seed} state {label}"},
                        tmp / f"{a}__{b}__{seed}__{label}.json",
                    )
                records.append({"pair": [a, b], "seed": seed, "states": states})

    summary = summarize_pair_records(records)
    return {
        "schema": "physical-lab-radiation-pair-interactions-v1",
        "pairs": [list(p) for p in norm_pairs],
        "seeds": [int(s) for s in seeds],
        "errorMagnitudes": {k: float(magnitudes[k]) for p in norm_pairs for k in p},
        "grid": {"transversePoints": nx, "zPoints": int(len(z_mm)), "fieldPointsPerRun": int(field_points)},
        "records": records,
        "summary": summary,
        "boundary": summary["boundary"],
    }
