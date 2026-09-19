"""Uncertainty propagation and validation helpers for the rotating U-tube model.

This layer never changes the deterministic model. It propagates explicitly supplied
parameter uncertainty through that model and keeps numerical uncertainty distinct
from physical/model-form uncertainty.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

import physical_lab_utube_experiment as utube

SCHEMA = "engineering-lab-utube-uncertainty/v1"
BOUNDARY = (
    "Uncertainty propagation reflects only the distributions and independence assumptions explicitly supplied here. "
    "It does not include unknown model-form error, unreported calibration error, or causal uncertainty. "
    "Predictive interval overlap is evidence about consistency under these assumptions, not proof of model validity."
)

_DEFAULTS = {
    "volume_ml": 3.0,
    "n_rpm": 260.0,
    "rin_m": utube.DEFAULT_R_IN_M,
    "a_m": utube.DEFAULT_A_M,
    "rho_kg_m3": utube.DEFAULT_RHO,
    "gamma_mN_m": 54.54,
    "theta_deg": 48.9,
}


def _finite(value: Any, name: str) -> float:
    x = float(value)
    if not np.isfinite(x):
        raise ValueError(f"{name} must be finite")
    return x


def _draw_normal(rng: np.random.Generator, mean: float, sd: float, size: int, *, positive: bool = False) -> np.ndarray:
    if sd < 0:
        raise ValueError("standard uncertainty must be non-negative")
    if sd == 0:
        values = np.full(size, mean, dtype=float)
    else:
        values = rng.normal(mean, sd, size=size)
    if positive:
        floor = max(abs(mean) * 1e-9, 1e-12)
        values = np.maximum(values, floor)
    return values


def _summary(values: Sequence[float]) -> dict[str, float | int | None]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"n": 0, "mean": None, "sd": None, "p2_5": None, "median": None, "p97_5": None}
    return {
        "n": int(arr.size),
        "mean": float(np.mean(arr)),
        "sd": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "p2_5": float(np.percentile(arr, 2.5)),
        "median": float(np.median(arr)),
        "p97_5": float(np.percentile(arr, 97.5)),
    }


def propagate_uncertainty(
    means: Mapping[str, float] | None = None,
    standard_uncertainties: Mapping[str, float] | None = None,
    *,
    samples: int = 500,
    seed: int = 0,
    nq: int = 48,
) -> dict[str, Any]:
    """Seeded Monte Carlo propagation for explicitly independent Normal inputs."""
    means = {**_DEFAULTS, **dict(means or {})}
    std = {key: 0.0 for key in _DEFAULTS}
    std.update({str(k): _finite(v, f"u({k})") for k, v in dict(standard_uncertainties or {}).items()})
    n_samples = max(8, min(int(samples), 5000))
    rng = np.random.default_rng(int(seed))

    draws = {
        "volume_ml": _draw_normal(rng, _finite(means["volume_ml"], "volume_ml"), std["volume_ml"], n_samples, positive=True),
        "n_rpm": _draw_normal(rng, _finite(means["n_rpm"], "n_rpm"), std["n_rpm"], n_samples, positive=True),
        "rin_m": _draw_normal(rng, _finite(means["rin_m"], "rin_m"), std["rin_m"], n_samples, positive=True),
        "a_m": _draw_normal(rng, _finite(means["a_m"], "a_m"), std["a_m"], n_samples, positive=True),
        "rho_kg_m3": _draw_normal(rng, _finite(means["rho_kg_m3"], "rho_kg_m3"), std["rho_kg_m3"], n_samples, positive=True),
        "gamma_mN_m": _draw_normal(rng, _finite(means["gamma_mN_m"], "gamma_mN_m"), std["gamma_mN_m"], n_samples, positive=True),
        "theta_deg": _draw_normal(rng, _finite(means["theta_deg"], "theta_deg"), std["theta_deg"], n_samples),
    }

    rows: list[dict[str, Any]] = []
    failures = 0
    for i in range(n_samples):
        params = {key: float(values[i]) for key, values in draws.items()}
        try:
            nc = utube.critical_speed(params["rin_m"], params["a_m"])
            ng = utube.threshold(params["volume_ml"], params["rin_m"], params["a_m"], nq=int(nq))
            row = {**params, "n_c_rpm": nc, "n_g_rpm": ng, "above_bifurcation": params["n_rpm"] > nc}
            if params["n_rpm"] > nc:
                coeff = utube.local_coefficients(params["n_rpm"], params["rin_m"], params["a_m"], params["rho_kg_m3"])
                S = utube.surface_coefficient(params["gamma_mN_m"], params["theta_deg"])
                a_bulk = 1.0 - 2.0 ** (-0.5)
                a_surf = 2.0 ** (1.0 / 3.0) - 1.0
                crossing = float((a_surf * S / (a_bulk * coeff["K_mL"])) ** (6.0 / 5.0))
                dF = float(-a_bulk * coeff["K_mL"] * params["volume_ml"] ** 1.5 + a_surf * S * params["volume_ml"] ** (2.0 / 3.0))
                row.update({"vstar_ml": crossing, "delta_f_j": dF})
            rows.append(row)
        except Exception:
            failures += 1

    frame = pd.DataFrame(rows)
    outputs = {}
    for column in ("n_c_rpm", "n_g_rpm", "vstar_ml", "delta_f_j"):
        outputs[column] = _summary(pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").dropna())
    return {
        "schema": SCHEMA,
        "assumptions": {"input_distributions": "independent Normal", "nq": int(nq), "seed": int(seed)},
        "means": {k: float(v) for k, v in means.items()},
        "standard_uncertainties": std,
        "samples_requested": n_samples,
        "samples_succeeded": int(len(frame)),
        "samples_failed": int(failures),
        "outputs": outputs,
        "records": frame.to_dict(orient="records"),
        "boundary": BOUNDARY,
    }


def local_uncertainty_budget(
    means: Mapping[str, float] | None,
    standard_uncertainties: Mapping[str, float],
    *,
    output: str = "n_g_rpm",
    nq: int = 48,
) -> pd.DataFrame:
    """First-order one-at-a-time uncertainty budget around the supplied mean point."""
    base = {**_DEFAULTS, **dict(means or {})}

    def evaluate(params: Mapping[str, float]) -> float:
        if output == "n_c_rpm":
            return utube.critical_speed(params["rin_m"], params["a_m"])
        if output == "n_g_rpm":
            return utube.threshold(params["volume_ml"], params["rin_m"], params["a_m"], nq=int(nq))
        if output == "vstar_ml":
            coeff = utube.local_coefficients(params["n_rpm"], params["rin_m"], params["a_m"], params["rho_kg_m3"])
            S = utube.surface_coefficient(params["gamma_mN_m"], params["theta_deg"])
            a_bulk = 1.0 - 2.0 ** (-0.5); a_surf = 2.0 ** (1.0 / 3.0) - 1.0
            return float((a_surf * S / (a_bulk * coeff["K_mL"])) ** (6.0 / 5.0))
        raise ValueError("unsupported uncertainty-budget output")

    rows = []
    variances = []
    for name, raw_sd in standard_uncertainties.items():
        if name not in base:
            continue
        sd = _finite(raw_sd, f"u({name})")
        if sd <= 0:
            continue
        plus = dict(base); minus = dict(base)
        plus[name] = float(base[name]) + sd
        minus[name] = float(base[name]) - sd
        if name in {"volume_ml", "n_rpm", "rin_m", "a_m", "rho_kg_m3", "gamma_mN_m"} and minus[name] <= 0:
            minus[name] = max(float(base[name]) * 1e-6, 1e-12)
        y_plus = evaluate(plus); y_minus = evaluate(minus)
        contribution = 0.5 * abs(y_plus - y_minus)
        variance = contribution**2
        variances.append(variance)
        rows.append({"parameter": name, "standard_uncertainty": sd, "output_change_1sigma": contribution, "variance_proxy": variance})
    total = float(sum(variances))
    for row in rows:
        row["fraction_of_variance_proxy"] = 0.0 if total <= 0 else row["variance_proxy"] / total
    return pd.DataFrame(rows).sort_values("fraction_of_variance_proxy", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=["parameter","standard_uncertainty","output_change_1sigma","variance_proxy","fraction_of_variance_proxy"])


def predictive_interval_check(observed: Sequence[float], predictive_samples: Sequence[float]) -> dict[str, Any]:
    obs = np.asarray(observed, dtype=float); obs = obs[np.isfinite(obs)]
    pred = np.asarray(predictive_samples, dtype=float); pred = pred[np.isfinite(pred)]
    if obs.size == 0 or pred.size < 2:
        raise ValueError("observed values and at least two predictive samples are required")
    lo, hi = np.percentile(pred, [2.5, 97.5])
    return {
        "observed_n": int(obs.size),
        "observed_mean": float(np.mean(obs)),
        "observed_sd": float(np.std(obs, ddof=1)) if obs.size > 1 else 0.0,
        "predictive_mean": float(np.mean(pred)),
        "predictive_sd": float(np.std(pred, ddof=1)),
        "predictive_p2_5": float(lo),
        "predictive_p97_5": float(hi),
        "observed_mean_inside_predictive_95pct": bool(lo <= float(np.mean(obs)) <= hi),
        "boundary": BOUNDARY,
    }
