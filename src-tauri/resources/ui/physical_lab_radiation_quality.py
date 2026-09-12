"""Analyze radiation-quality degradation across propagated manufacturing realizations.

Consumes worker-v2 records produced by the existing RADIA -> trajectory -> radiation
propagation. It does not rerun physics and does not infer manufacturing yield.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

QUALITY_METRICS = (
    "P_lin",
    "P_circ",
    "polarization_degree",
    "H3_over_H1",
    "H5_over_H1",
    "relative_linewidth",
    "photon_energy_eV",
)


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def flatten_radiation_quality(record: Mapping[str, Any]) -> dict[str, float | None]:
    obs = record.get("observables") if isinstance(record.get("observables"), Mapping) else {}
    stokes = record.get("stokes") if isinstance(record.get("stokes"), Mapping) else {}
    harmonic = record.get("harmonicRatios") if isinstance(record.get("harmonicRatios"), Mapping) else {}
    return {
        "P_lin": _finite(stokes.get("P_lin", obs.get("P_lin"))),
        "P_circ": _finite(stokes.get("P_circ", obs.get("P_circ"))),
        "polarization_degree": _finite(stokes.get("polarization_degree", obs.get("polarization_degree"))),
        "H3_over_H1": _finite(harmonic.get("H3_over_H1")),
        "H5_over_H1": _finite(harmonic.get("H5_over_H1")),
        "relative_linewidth": _finite(obs.get("relative_linewidth")),
        "photon_energy_eV": _finite(obs.get("photon_energy_eV")),
    }


def summarize_radiation_quality(
    nominal: Mapping[str, Any],
    members: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    import numpy as np

    if len(members) < 2:
        raise ValueError("At least two manufacturing realizations are required")
    nominal_flat = flatten_radiation_quality(nominal)
    member_rows = []
    for member in members:
        flat = flatten_radiation_quality(member)
        member_rows.append({"seed": member.get("seed"), **flat})

    metrics: dict[str, Any] = {}
    for metric in QUALITY_METRICS:
        n0 = nominal_flat.get(metric)
        samples = [(row.get("seed"), _finite(row.get(metric))) for row in member_rows]
        samples = [(seed, value) for seed, value in samples if value is not None]
        if not samples:
            continue
        vals = np.asarray([value for _, value in samples], dtype=float)
        row: dict[str, Any] = {
            "nominal": n0,
            "count": int(len(vals)),
            "mean": float(np.mean(vals)),
            "sampleStdDev": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
            "min": float(np.min(vals)),
            "median": float(np.median(vals)),
            "max": float(np.max(vals)),
        }
        if n0 is not None:
            delta = vals - float(n0)
            idx = int(np.argmax(np.abs(delta)))
            row.update({
                "meanDeltaFromNominal": float(np.mean(delta)),
                "maxAbsDeltaFromNominal": float(abs(delta[idx])),
                "worstSeedByAbsoluteDelta": samples[idx][0],
                "worstValue": float(vals[idx]),
            })
            if abs(float(n0)) > 1e-15:
                rel = delta / abs(float(n0))
                row["maxAbsRelativeDelta"] = float(np.max(np.abs(rel)))
        metrics[metric] = row

    degradation_score_rows = []
    for member, flat in zip(members, member_rows):
        components = []
        for metric in ("polarization_degree", "P_circ", "P_lin"):
            n0 = nominal_flat.get(metric)
            value = _finite(flat.get(metric))
            if n0 is not None and value is not None:
                components.append(abs(value - n0))
        for metric in ("H3_over_H1", "H5_over_H1", "relative_linewidth"):
            n0 = nominal_flat.get(metric)
            value = _finite(flat.get(metric))
            if n0 is not None and value is not None and abs(n0) > 1e-15:
                components.append(abs(value - n0) / abs(n0))
        degradation_score_rows.append({
            "seed": member.get("seed"),
            "diagnostic_deviation_score": float(sum(components)),
            "component_count": len(components),
        })

    ranked = sorted(degradation_score_rows, key=lambda row: row["diagnostic_deviation_score"], reverse=True)
    return {
        "schema": "physical-lab-radiation-quality-degradation-v1",
        "nominal": nominal_flat,
        "members": member_rows,
        "metrics": metrics,
        "diagnosticRanking": ranked,
        "boundary": (
            "The diagnostic deviation score is only a ranking aid across the explicitly simulated seeds; "
            "it is not a physical objective function, yield probability, tolerance certification, or universal radiation-quality score."
        ),
    }
