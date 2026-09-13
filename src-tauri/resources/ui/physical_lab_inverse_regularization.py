"""Inverse-problem regularization helpers for Engineering Lab.

TSVD, GCV and L-curve diagnostics operate on an explicit linear design matrix.
They provide numerical regularization diagnostics, not physical identifiability,
model validation, causality, or an automatically correct regularization choice.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
import pandas as pd

BOUNDARY = (
    "TSVD, GCV and L-curve diagnostics describe numerical regularization trade-offs for an explicit linear inverse problem. "
    "A selected truncation rank or regularization strength is an analysis choice, not proof of physical identifiability, model validity, or truth."
)


def _problem(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, standardize: bool = True) -> dict[str, Any]:
    predictors = [str(p) for p in predictors]
    if not predictors or response in predictors:
        raise ValueError("choose predictors distinct from the response")
    missing = [c for c in [*predictors, response] if c not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    work = pd.DataFrame({c: pd.to_numeric(frame[c], errors="coerce") for c in [*predictors, response]})
    work = work.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if len(work) < len(predictors) + 2:
        raise ValueError("not enough finite observations for inverse analysis")
    raw_x = work[predictors].to_numpy(dtype=float)
    y = work[response].to_numpy(dtype=float)
    means = raw_x.mean(axis=0)
    scales = np.ones(len(predictors), dtype=float)
    x = raw_x - means
    if standardize:
        scales = x.std(axis=0, ddof=1)
        if np.any(~np.isfinite(scales)) or np.any(scales <= 0):
            raise ValueError("standardization requires non-zero finite predictor variance")
        x = x / scales
    # Center response so SVD regularization applies only to slope coefficients.
    y_mean = float(y.mean())
    yc = y - y_mean
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    return {
        "work": work,
        "x": x,
        "y": y,
        "yc": yc,
        "y_mean": y_mean,
        "means": means,
        "scales": scales,
        "u": u,
        "singular": singular,
        "vt": vt,
        "predictors": predictors,
        "response": str(response),
        "standardized": bool(standardize),
    }


def truncated_svd_regression(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, rank: int, standardize: bool = True) -> dict[str, Any]:
    problem = _problem(frame, predictors, response, standardize=standardize)
    singular = problem["singular"]
    max_rank = int(len(singular))
    rank = int(rank)
    if rank < 1 or rank > max_rank:
        raise ValueError(f"TSVD rank must be within 1..{max_rank}")
    tol = np.finfo(float).eps * max(problem["x"].shape) * (float(singular[0]) if max_rank else 1.0)
    usable = np.where(singular[:rank] > tol, 1.0 / singular[:rank], 0.0)
    beta = problem["vt"][:rank].T @ (usable * (problem["u"][:, :rank].T @ problem["yc"]))
    predicted = problem["y_mean"] + problem["x"] @ beta
    residual = problem["y"] - predicted
    coefficients = [{"term": "intercept", "estimate": problem["y_mean"]}]
    coefficients.extend({"term": p, "estimate": float(v)} for p, v in zip(problem["predictors"], beta))
    return {
        "kind": "tsvd-linear-inverse",
        "rank": rank,
        "max_rank": max_rank,
        "predictors": problem["predictors"],
        "response": problem["response"],
        "standardized": problem["standardized"],
        "singular_values": [float(v) for v in singular],
        "coefficients": coefficients,
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "data_residual_norm": float(np.linalg.norm(residual)),
        "solution_norm": float(np.linalg.norm(beta)),
        "diagnostics": pd.DataFrame({"observed": problem["y"], "predicted": predicted, "residual": residual}),
        "boundary": BOUNDARY,
    }


def tsvd_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, standardize: bool = True) -> pd.DataFrame:
    problem = _problem(frame, predictors, response, standardize=standardize)
    rows = []
    for rank in range(1, len(problem["singular"]) + 1):
        result = truncated_svd_regression(frame, predictors, response, rank=rank, standardize=standardize)
        rows.append({"rank": rank, "rmse": result["rmse"], "data_residual_norm": result["data_residual_norm"], "solution_norm": result["solution_norm"]})
    return pd.DataFrame(rows)


def tikhonov_gcv_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, lambdas: Sequence[float] | None = None, standardize: bool = True) -> pd.DataFrame:
    problem = _problem(frame, predictors, response, standardize=standardize)
    if lambdas is None:
        lambdas = np.logspace(-10, 6, 96)
    x = problem["x"]
    y = problem["yc"]
    n = len(y)
    u, singular, vt = problem["u"], problem["singular"], problem["vt"]
    uy = u.T @ y
    rows = []
    for value in lambdas:
        lam = float(value)
        if not math.isfinite(lam) or lam <= 0:
            continue
        filt = singular / (singular ** 2 + lam)
        beta = vt.T @ (filt * uy)
        fitted = x @ beta
        residual = y - fitted
        residual_sq = float(np.dot(residual, residual))
        trace_h = float(np.sum((singular ** 2) / (singular ** 2 + lam)))
        denom = (n - trace_h) ** 2
        gcv = float(n * residual_sq / denom) if denom > np.finfo(float).eps else float("inf")
        rows.append({
            "regularization": lam,
            "gcv": gcv,
            "effective_degrees_of_freedom": trace_h,
            "data_residual_norm": float(np.linalg.norm(residual)),
            "solution_norm": float(np.linalg.norm(beta)),
            "rmse": float(np.sqrt(np.mean(residual ** 2))),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("GCV path has no valid positive regularization values")
    return out.sort_values("regularization").reset_index(drop=True)


def gcv_choice(path: pd.DataFrame) -> dict[str, float]:
    if path.empty or "gcv" not in path.columns or "regularization" not in path.columns:
        raise ValueError("GCV path is empty or malformed")
    finite = path.replace([np.inf, -np.inf], np.nan).dropna(subset=["gcv", "regularization"])
    if finite.empty:
        raise ValueError("GCV path has no finite score")
    row = finite.loc[finite["gcv"].idxmin()]
    return {"regularization": float(row["regularization"]), "gcv": float(row["gcv"])}


def lcurve_curvature(path: pd.DataFrame) -> pd.DataFrame:
    required = {"regularization", "data_residual_norm", "solution_norm"}
    if path.empty or not required.issubset(path.columns):
        raise ValueError("L-curve path is empty or malformed")
    work = path.sort_values("regularization").copy()
    x = np.log(np.maximum(pd.to_numeric(work["data_residual_norm"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny))
    y = np.log(np.maximum(pd.to_numeric(work["solution_norm"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny))
    t = np.log(np.maximum(pd.to_numeric(work["regularization"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny))
    if len(work) < 5 or not (np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(np.isfinite(t))):
        raise ValueError("L-curve curvature needs at least five finite path points")
    dx = np.gradient(x, t); dy = np.gradient(y, t)
    ddx = np.gradient(dx, t); ddy = np.gradient(dy, t)
    denom = np.maximum((dx * dx + dy * dy) ** 1.5, np.finfo(float).eps)
    curvature = np.abs(dx * ddy - dy * ddx) / denom
    # Endpoints are unreliable under finite differencing; mark them unavailable.
    curvature[0] = np.nan; curvature[-1] = np.nan
    work["lcurve_curvature"] = curvature
    return work


def lcurve_choice(path: pd.DataFrame) -> dict[str, float]:
    work = lcurve_curvature(path)
    finite = work.replace([np.inf, -np.inf], np.nan).dropna(subset=["lcurve_curvature", "regularization"])
    if finite.empty:
        raise ValueError("L-curve path has no finite interior curvature")
    row = finite.loc[finite["lcurve_curvature"].idxmax()]
    return {"regularization": float(row["regularization"]), "curvature": float(row["lcurve_curvature"])}
