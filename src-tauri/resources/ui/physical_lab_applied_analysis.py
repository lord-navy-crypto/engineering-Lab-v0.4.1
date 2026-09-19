"""Applied mathematics and statistics helpers for Engineering Lab.

The functions in this module operate on existing numeric evidence or generate
prospective experiment designs. They do not establish causality, validation, or
physical truth. Model families are explicit and allow-listed; no eval/exec or
arbitrary user code is used.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.stats import qmc

APPLIED_ANALYSIS_SCHEMA = "engineering-lab-applied-analysis/v1"
DOE_SCHEMA = "engineering-lab-doe-design/v1"
MAX_BOOTSTRAP_RESAMPLES = 20000
MAX_DOE_ROWS = 5000
BOUNDARY = (
    "Applied analysis is descriptive/inferential computation over explicit inputs. "
    "Regression, bootstrap intervals, parameter estimates and DOE proposals do not by themselves establish causality, model validity, calibration equivalence, or experimental confirmation."
)


def _numeric_frame(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out = pd.DataFrame({str(c): pd.to_numeric(frame[c], errors="coerce") for c in columns})
    return out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def regression_diagnostics(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, include_intercept: bool = True) -> dict[str, Any]:
    predictors = [str(x) for x in predictors]
    if not predictors:
        raise ValueError("regression requires at least one predictor")
    if response in predictors:
        raise ValueError("response cannot also be a predictor")
    work = _numeric_frame(frame, [*predictors, response])
    n = len(work)
    if n < len(predictors) + int(include_intercept) + 2:
        raise ValueError("not enough finite observations for regression diagnostics")
    x = work[predictors].to_numpy(dtype=float)
    if include_intercept:
        x_design = np.column_stack([np.ones(n), x])
        names = ["intercept", *predictors]
    else:
        x_design = x
        names = list(predictors)
    y = work[response].to_numpy(dtype=float)
    beta, _resid, rank, singular = np.linalg.lstsq(x_design, y, rcond=None)
    predicted = x_design @ beta
    residual = y - predicted
    p = x_design.shape[1]
    rss = float(np.sum(residual ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else float("nan")
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - p) if n > p and math.isfinite(r2) else float("nan")
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mae = float(np.mean(np.abs(residual)))
    dof = max(n - p, 1)
    sigma2 = rss / dof
    xtx_inv = np.linalg.pinv(x_design.T @ x_design)
    se = np.sqrt(np.maximum(np.diag(sigma2 * xtx_inv), 0.0))
    leverage = np.clip(np.diag(x_design @ xtx_inv @ x_design.T), 0.0, 1.0)
    denom = np.sqrt(np.maximum(sigma2 * (1.0 - leverage), np.finfo(float).eps))
    standardized_residual = residual / denom
    cooks = (standardized_residual ** 2 / max(p, 1)) * leverage / np.maximum(1.0 - leverage, np.finfo(float).eps)
    condition = float(np.linalg.cond(x_design))
    coefficients = [
        {"term": name, "estimate": float(value), "standard_error": float(err)}
        for name, value, err in zip(names, beta, se)
    ]
    diagnostics = pd.DataFrame({
        "observed": y,
        "predicted": predicted,
        "residual": residual,
        "standardized_residual": standardized_residual,
        "leverage": leverage,
        "cooks_distance": cooks,
    })
    return {
        "kind": "linear-regression",
        "predictors": predictors,
        "response": str(response),
        "include_intercept": bool(include_intercept),
        "n": int(n),
        "rank": int(rank),
        "condition_number": condition,
        "r2": r2,
        "adjusted_r2": adj_r2,
        "rmse": rmse,
        "mae": mae,
        "residual_mean": float(np.mean(residual)),
        "coefficients": coefficients,
        "diagnostics": diagnostics,
        "boundary": BOUNDARY,
    }


def polynomial_regression(frame: pd.DataFrame, predictor: str, response: str, *, degree: int = 2) -> dict[str, Any]:
    degree = int(degree)
    if degree < 1 or degree > 6:
        raise ValueError("polynomial degree must be between 1 and 6")
    work = _numeric_frame(frame, [predictor, response])
    if len(work) < degree + 3:
        raise ValueError("not enough finite observations for polynomial regression")
    x = work[predictor].to_numpy(dtype=float)
    y = work[response].to_numpy(dtype=float)
    design = np.vander(x, N=degree + 1, increasing=True)
    beta, _resid, rank, _singular = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ beta
    residual = y - predicted
    rss = float(np.sum(residual ** 2)); tss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else float("nan")
    return {
        "kind": "polynomial-regression",
        "predictor": predictor,
        "response": response,
        "degree": degree,
        "rank": int(rank),
        "coefficients": [{"power": i, "estimate": float(v)} for i, v in enumerate(beta)],
        "r2": r2,
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "diagnostics": pd.DataFrame({predictor: x, "observed": y, "predicted": predicted, "residual": residual}).sort_values(predictor),
        "boundary": BOUNDARY,
    }


def bootstrap_statistic(values: Sequence[Any], *, statistic: str = "mean", resamples: int = 2000, confidence: float = 0.95, seed: int = 0) -> dict[str, Any]:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(arr) < 2:
        raise ValueError("bootstrap requires at least two finite observations")
    resamples = int(resamples)
    if resamples < 100 or resamples > MAX_BOOTSTRAP_RESAMPLES:
        raise ValueError(f"bootstrap resamples must be between 100 and {MAX_BOOTSTRAP_RESAMPLES}")
    confidence = float(confidence)
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be between 0.5 and 1.0")
    funcs = {"mean": np.mean, "median": np.median, "std": lambda x: np.std(x, ddof=1)}
    if statistic not in funcs:
        raise ValueError("bootstrap statistic must be mean, median or std")
    fn = funcs[statistic]
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, len(arr), size=(resamples, len(arr)))
    samples = arr[idx]
    estimates = np.asarray([fn(row) for row in samples], dtype=float)
    alpha = (1.0 - confidence) / 2.0
    lo, hi = np.quantile(estimates, [alpha, 1.0 - alpha])
    return {
        "kind": "bootstrap-statistic",
        "statistic": statistic,
        "n": int(len(arr)),
        "resamples": resamples,
        "confidence": confidence,
        "seed": int(seed),
        "estimate": float(fn(arr)),
        "bootstrap_standard_error": float(np.std(estimates, ddof=1)),
        "interval": [float(lo), float(hi)],
        "distribution": estimates.tolist(),
        "boundary": BOUNDARY,
    }


def monte_carlo_propagation(*, means: Sequence[float], standard_uncertainties: Sequence[float], coefficients: Sequence[float], samples: int = 5000, seed: int = 0) -> dict[str, Any]:
    means = np.asarray(means, dtype=float); stds = np.asarray(standard_uncertainties, dtype=float); coeffs = np.asarray(coefficients, dtype=float)
    if not (len(means) == len(stds) == len(coeffs)) or len(means) == 0:
        raise ValueError("means, standard uncertainties and coefficients must have equal non-zero length")
    if np.any(stds < 0) or not np.all(np.isfinite(means)) or not np.all(np.isfinite(stds)) or not np.all(np.isfinite(coeffs)):
        raise ValueError("Monte Carlo inputs must be finite and standard uncertainties non-negative")
    samples = int(samples)
    if samples < 100 or samples > MAX_BOOTSTRAP_RESAMPLES:
        raise ValueError(f"Monte Carlo samples must be between 100 and {MAX_BOOTSTRAP_RESAMPLES}")
    rng = np.random.default_rng(int(seed))
    draws = rng.normal(means, stds, size=(samples, len(means)))
    output = draws @ coeffs
    q025, q50, q975 = np.quantile(output, [0.025, 0.5, 0.975])
    return {
        "kind": "linear-monte-carlo-propagation",
        "samples": samples,
        "seed": int(seed),
        "mean": float(np.mean(output)),
        "standard_deviation": float(np.std(output, ddof=1)),
        "percentile_95": [float(q025), float(q975)],
        "median": float(q50),
        "distribution": output.tolist(),
        "boundary": BOUNDARY,
    }


def _validate_factors(factors: Sequence[Mapping[str, Any]]) -> list[dict[str, float | str]]:
    parsed: list[dict[str, float | str]] = []
    seen: set[str] = set()
    for item in factors:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            raise ValueError("DOE factor names must be unique and non-empty")
        low = float(item.get("low")); high = float(item.get("high"))
        if not math.isfinite(low) or not math.isfinite(high) or not low < high:
            raise ValueError(f"factor {name!r} requires finite low < high")
        parsed.append({"name": name, "low": low, "high": high}); seen.add(name)
    if not parsed:
        raise ValueError("DOE requires at least one factor")
    return parsed


def design_experiment(factors: Sequence[Mapping[str, Any]], *, method: str = "latin-hypercube", samples: int = 32, seed: int = 0, center_points: int = 1) -> dict[str, Any]:
    parsed = _validate_factors(factors); method = str(method).lower()
    names = [str(x["name"]) for x in parsed]; low = np.array([float(x["low"]) for x in parsed]); high = np.array([float(x["high"]) for x in parsed])
    k = len(parsed)
    if method == "full-factorial":
        count = 2 ** k
        if count > MAX_DOE_ROWS:
            raise ValueError("full factorial design exceeds row limit")
        unit = np.array(list(itertools.product([0.0, 1.0], repeat=k)), dtype=float)
    elif method == "latin-hypercube":
        samples = int(samples)
        if samples < 2 or samples > MAX_DOE_ROWS: raise ValueError("invalid DOE sample count")
        unit = qmc.LatinHypercube(d=k, seed=int(seed)).random(samples)
    elif method == "random":
        samples = int(samples)
        if samples < 2 or samples > MAX_DOE_ROWS: raise ValueError("invalid DOE sample count")
        unit = np.random.default_rng(int(seed)).random((samples, k))
    elif method == "central-composite":
        if k > 8:
            raise ValueError("central composite design supports at most 8 factors")
        factorial = np.array(list(itertools.product([-1.0, 1.0], repeat=k)), dtype=float)
        alpha = math.sqrt(k)
        axial = []
        for i in range(k):
            plus = np.zeros(k); minus = np.zeros(k); plus[i] = alpha; minus[i] = -alpha
            axial.extend([plus, minus])
        centers = np.zeros((max(int(center_points), 1), k))
        coded = np.vstack([factorial, np.asarray(axial), centers])
        if len(coded) > MAX_DOE_ROWS: raise ValueError("central composite design exceeds row limit")
        unit = np.clip((coded / max(alpha, 1.0) + 1.0) / 2.0, 0.0, 1.0)
    else:
        raise ValueError("DOE method must be full-factorial, latin-hypercube, random or central-composite")
    actual = low + unit * (high - low)
    frame = pd.DataFrame(actual, columns=names)
    frame.insert(0, "design_run", np.arange(1, len(frame) + 1, dtype=int))
    return {"schema": DOE_SCHEMA, "method": method, "seed": int(seed), "factors": parsed, "row_count": int(len(frame)), "design": frame, "boundary": "DOE rows are proposed experiment settings only; generating a design does not execute an experiment or create evidence."}


_SAFE_MODELS = {
    "linear": (lambda x, a, b: a + b * x, ["intercept", "slope"]),
    "quadratic": (lambda x, a, b, c: a + b * x + c * x * x, ["intercept", "linear", "quadratic"]),
    "exponential": (lambda x, a, b, c: a * np.exp(b * x) + c, ["amplitude", "rate", "offset"]),
}


def estimate_parameters(frame: pd.DataFrame, x: str, y: str, *, model: str = "linear") -> dict[str, Any]:
    model = str(model).lower()
    if model not in _SAFE_MODELS:
        raise ValueError(f"unsupported parameter-estimation model: {model}")
    work = _numeric_frame(frame, [x, y])
    if len(work) < 5:
        raise ValueError("parameter estimation requires at least five finite observations")
    xv = work[x].to_numpy(dtype=float); yv = work[y].to_numpy(dtype=float)
    fn, names = _SAFE_MODELS[model]
    if model == "linear":
        p0 = [float(np.mean(yv)), 0.0]
    elif model == "quadratic":
        coeff = np.polyfit(xv, yv, 2); p0 = [float(coeff[2]), float(coeff[1]), float(coeff[0])]
    else:
        p0 = [float(np.ptp(yv) or 1.0), 0.0, float(np.min(yv))]
    params, covariance = optimize.curve_fit(fn, xv, yv, p0=p0, maxfev=20000)
    predicted = fn(xv, *params); residual = yv - predicted
    errors = np.sqrt(np.maximum(np.diag(covariance), 0.0)) if covariance.size else np.full(len(params), np.nan)
    return {
        "kind": "parameter-estimation",
        "model": model,
        "x": x,
        "y": y,
        "n": int(len(work)),
        "parameters": [{"name": n, "estimate": float(v), "standard_error": float(e)} for n, v, e in zip(names, params, errors)],
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "mae": float(np.mean(np.abs(residual))),
        "diagnostics": pd.DataFrame({x: xv, "observed": yv, "predicted": predicted, "residual": residual}).sort_values(x),
        "boundary": BOUNDARY,
    }


def artifact_identity(kind: str, source_identity: Mapping[str, Any], configuration: Mapping[str, Any]) -> tuple[str, str]:
    semantic = {"schema": APPLIED_ANALYSIS_SCHEMA, "kind": str(kind), "source": dict(source_identity), "configuration": dict(configuration)}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"applied-{digest[:20]}", digest


def save_analysis_artifact(project_path: Path, *, kind: str, source_identity: Mapping[str, Any], configuration: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    artifact_id, digest = artifact_identity(kind, source_identity, configuration)
    record = {"schema": APPLIED_ANALYSIS_SCHEMA, "artifact_id": artifact_id, "sha256": digest, "kind": str(kind), "source": dict(source_identity), "configuration": dict(configuration), "summary": dict(summary), "boundary": BOUNDARY}
    root = Path(project_path) / "reports" / "applied-analysis"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{artifact_id}.json"
    if not path.exists():
        path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return {**record, "path": str(path)}
