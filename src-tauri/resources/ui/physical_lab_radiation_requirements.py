"""Requirement contours over a bounded local radiation response surface.

This module classifies the already-fit local quadratic surrogate inside coded
[-1,+1]^2 against explicit lower/upper engineering bounds. The resulting PASS
fraction is geometric grid area in the surrogate box only; it is not a
manufacturing yield or probability.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _predict(coeff: Mapping[str, Any], x: float, y: float) -> float:
    return float(
        coeff["intercept"] + coeff["linearA"]*x + coeff["linearB"]*y
        + coeff["quadraticA"]*x*x + coeff["quadraticB"]*y*y
        + coeff["interactionAB"]*x*y
    )


def classify_requirement_surface(
    surface: Mapping[str, Any],
    *,
    lower: float | None = None,
    upper: float | None = None,
    points: int = 81,
) -> dict[str, Any]:
    if lower is None and upper is None:
        raise ValueError("At least one requirement bound is required")
    lo = _finite(lower) if lower is not None else None
    hi = _finite(upper) if upper is not None else None
    if lower is not None and lo is None:
        raise ValueError("lower bound must be finite")
    if upper is not None and hi is None:
        raise ValueError("upper bound must be finite")
    if lo is not None and hi is not None and lo > hi:
        raise ValueError("lower bound must not exceed upper bound")

    import numpy as np

    coeff = surface.get("coefficients") or {}
    required = {"intercept","linearA","linearB","quadraticA","quadraticB","interactionAB"}
    if not required.issubset(coeff):
        raise ValueError("surface coefficients are incomplete")

    n = max(21, min(int(points), 201))
    axis = np.linspace(-1.0, 1.0, n)
    predicted = np.empty((n, n), dtype=float)
    passed = np.zeros((n, n), dtype=bool)
    margin = np.empty((n, n), dtype=float)

    for iy, y in enumerate(axis):
        for ix, x in enumerate(axis):
            value = _predict(coeff, float(x), float(y))
            predicted[iy, ix] = value
            ok_lo = lo is None or value >= lo
            ok_hi = hi is None or value <= hi
            passed[iy, ix] = ok_lo and ok_hi
            margins = []
            if lo is not None:
                margins.append(value - lo)
            if hi is not None:
                margins.append(hi - value)
            margin[iy, ix] = min(margins)

    center_idx = int(np.argmin(np.abs(axis)))
    center_value = float(predicted[center_idx, center_idx])
    center_pass = bool(passed[center_idx, center_idx])

    # Distance in coded-factor space from the center to the nearest grid cell
    # whose PASS/REVIEW classification differs. This is a discretized local
    # tolerance-boundary distance, not an exact analytic distance.
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    changed = passed != center_pass
    nearest = None
    if np.any(changed):
        dist = np.sqrt(xx[changed]**2 + yy[changed]**2)
        nearest = float(np.min(dist))

    return {
        "schema": "physical-lab-radiation-requirement-contour-v1",
        "metric": surface.get("metric"),
        "factorA": surface.get("factorA"),
        "factorB": surface.get("factorB"),
        "lower": lo,
        "upper": hi,
        "codedA": [float(x) for x in axis],
        "codedB": [float(x) for x in axis],
        "predicted": predicted.tolist(),
        "passMask": passed.tolist(),
        "margin": margin.tolist(),
        "passGridFraction": float(np.mean(passed)),
        "centerValue": center_value,
        "centerStatus": "PASS" if center_pass else "REVIEW",
        "nearestClassificationBoundaryFromCenterCoded": nearest,
        "boundary": (
            "PASS/REVIEW is predicted only by the local quadratic surrogate inside the sampled coded [-1,+1] box. "
            "passGridFraction is geometric sampled area, not probability or manufacturing yield. The boundary distance is grid-discretized."
        ),
    }
