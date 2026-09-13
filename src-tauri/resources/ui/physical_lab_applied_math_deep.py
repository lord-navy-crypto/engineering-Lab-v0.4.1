"""Deep applied-mathematics helpers for Engineering Lab.

PCA/SVD, conditioning diagnostics, regularized linear inverse problems and completed
sweep feedback operate only on explicit numeric inputs. They are computational
analysis tools, not evidence generators and not proofs of physical mechanism.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

BOUNDARY = (
    "Deep applied mathematics describes numerical structure in explicit data. PCA/SVD components, "
    "condition numbers, regularized inverse solutions and sweep-analysis recommendations do not establish "
    "causality, physical identifiability, model validity, calibration equivalence or experimental confirmation."
)


def _finite_frame(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    names = [str(c) for c in columns]
    missing = [c for c in names if c not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out = pd.DataFrame({c: pd.to_numeric(frame[c], errors="coerce") for c in names})
    return out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def pca_svd(frame: pd.DataFrame, columns: Sequence[str], *, standardize: bool = True, max_components: int | None = None) -> dict[str, Any]:
    columns = [str(c) for c in columns]
    if len(columns) < 2:
        raise ValueError("PCA/SVD requires at least two numeric columns")
    work = _finite_frame(frame, columns)
    if len(work) < 2:
        raise ValueError("PCA/SVD requires at least two complete finite rows")
    x = work.to_numpy(dtype=float)
    means = x.mean(axis=0)
    centered = x - means
    scales = np.ones(len(columns), dtype=float)
    if standardize:
        scales = centered.std(axis=0, ddof=1)
        if np.any(~np.isfinite(scales)) or np.any(scales <= 0):
            bad = [columns[i] for i, s in enumerate(scales) if not math.isfinite(float(s)) or s <= 0]
            raise ValueError(f"standardization requires non-zero finite variance: {bad}")
        centered = centered / scales
    u, singular, vt = np.linalg.svd(centered, full_matrices=False)
    total = float(np.sum(singular ** 2))
    explained = (singular ** 2 / total) if total > 0 else np.zeros_like(singular)
    cumulative = np.cumsum(explained)
    rank = int(np.linalg.matrix_rank(centered))
    kmax = min(centered.shape)
    k = kmax if max_components is None else max(1, min(int(max_components), kmax))
    scores = u[:, :k] * singular[:k]
    loading_rows = []
    for j in range(k):
        row = {"component": f"PC{j+1}", "singular_value": float(singular[j]), "explained_variance_ratio": float(explained[j]), "cumulative_variance_ratio": float(cumulative[j])}
        for i, name in enumerate(columns):
            row[name] = float(vt[j, i])
        loading_rows.append(row)
    score_frame = pd.DataFrame(scores, columns=[f"PC{i+1}" for i in range(k)])
    score_frame.insert(0, "row", np.arange(len(score_frame), dtype=int))
    return {
        "kind": "pca-svd",
        "columns": columns,
        "rows": int(len(work)),
        "standardized": bool(standardize),
        "means": {c: float(v) for c, v in zip(columns, means)},
        "scales": {c: float(v) for c, v in zip(columns, scales)},
        "effective_rank": rank,
        "singular_values": [float(v) for v in singular],
        "explained_variance_ratio": [float(v) for v in explained],
        "cumulative_variance_ratio": [float(v) for v in cumulative],
        "loadings": pd.DataFrame(loading_rows),
        "scores": score_frame,
        "boundary": BOUNDARY,
    }


def conditioning_diagnostics(frame: pd.DataFrame, columns: Sequence[str], *, center: bool = True, standardize: bool = False) -> dict[str, Any]:
    columns = [str(c) for c in columns]
    if not columns:
        raise ValueError("conditioning diagnostics require at least one numeric column")
    work = _finite_frame(frame, columns)
    x = work.to_numpy(dtype=float)
    if center:
        x = x - x.mean(axis=0)
    if standardize:
        scale = x.std(axis=0, ddof=1)
        if np.any(scale <= 0) or np.any(~np.isfinite(scale)):
            raise ValueError("standardized conditioning requires non-zero finite variance")
        x = x / scale
    singular = np.linalg.svd(x, compute_uv=False)
    if singular.size == 0:
        raise ValueError("conditioning matrix is empty")
    eps = np.finfo(float).eps
    largest = float(np.max(singular))
    smallest = float(np.min(singular))
    condition = float(np.inf if smallest <= eps * max(largest, 1.0) else largest / smallest)
    rank = int(np.linalg.matrix_rank(x))
    return {
        "kind": "conditioning-diagnostics",
        "columns": columns,
        "rows": int(len(work)),
        "centered": bool(center),
        "standardized": bool(standardize),
        "rank": rank,
        "column_count": int(len(columns)),
        "full_column_rank": bool(rank == len(columns)),
        "condition_number": condition,
        "singular_values": [float(v) for v in singular],
        "boundary": "A large condition number indicates numerical sensitivity/near-collinearity in this representation; it is not proof that any physical variable is redundant or invalid.",
    }


def tikhonov_regression(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, regularization: float = 1e-3, standardize: bool = True, penalize_intercept: bool = False) -> dict[str, Any]:
    predictors = [str(p) for p in predictors]
    if not predictors or response in predictors:
        raise ValueError("choose predictors distinct from the response")
    lam = float(regularization)
    if not math.isfinite(lam) or lam < 0:
        raise ValueError("regularization must be finite and non-negative")
    work = _finite_frame(frame, [*predictors, response])
    if len(work) < len(predictors) + 2:
        raise ValueError("not enough finite observations for inverse solve")
    raw_x = work[predictors].to_numpy(dtype=float)
    y = work[response].to_numpy(dtype=float)
    means = raw_x.mean(axis=0)
    scales = np.ones(len(predictors), dtype=float)
    x = raw_x - means
    if standardize:
        scales = x.std(axis=0, ddof=1)
        if np.any(scales <= 0) or np.any(~np.isfinite(scales)):
            raise ValueError("standardization requires non-zero predictor variance")
        x = x / scales
    design = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(design.shape[1])
    if not penalize_intercept:
        penalty[0, 0] = 0.0
    lhs = design.T @ design + lam * penalty
    rhs = design.T @ y
    beta = np.linalg.solve(lhs, rhs)
    predicted = design @ beta
    residual = y - predicted
    data_residual_norm = float(np.linalg.norm(residual))
    regularization_norm = float(np.linalg.norm(beta[1:] if not penalize_intercept else beta))
    terms = ["intercept", *predictors]
    return {
        "kind": "tikhonov-linear-inverse",
        "predictors": predictors,
        "response": str(response),
        "regularization": lam,
        "standardized": bool(standardize),
        "penalize_intercept": bool(penalize_intercept),
        "coefficients": [{"term": t, "estimate": float(v)} for t, v in zip(terms, beta)],
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "mae": float(np.mean(np.abs(residual))),
        "data_residual_norm": data_residual_norm,
        "regularization_norm": regularization_norm,
        "diagnostics": pd.DataFrame({"observed": y, "predicted": predicted, "residual": residual}),
        "preprocessing": {"means": {p: float(v) for p, v in zip(predictors, means)}, "scales": {p: float(v) for p, v in zip(predictors, scales)}},
        "boundary": "Tikhonov regularization stabilizes a specified linear inverse problem by imposing a coefficient penalty. The chosen regularization strength is an analysis assumption, not a physical law.",
    }


def regularization_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, lambdas: Sequence[float] | None = None, standardize: bool = True) -> pd.DataFrame:
    if lambdas is None:
        lambdas = np.logspace(-8, 4, 40)
    rows = []
    for value in lambdas:
        lam = float(value)
        if lam < 0 or not math.isfinite(lam):
            continue
        result = tikhonov_regression(frame, predictors, response, regularization=lam, standardize=standardize)
        rows.append({
            "regularization": lam,
            "rmse": float(result["rmse"]),
            "data_residual_norm": float(result["data_residual_norm"]),
            "regularization_norm": float(result["regularization_norm"]),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("regularization path has no valid points")
    return out.sort_values("regularization").reset_index(drop=True)


def sweep_feedback(frame: pd.DataFrame) -> dict[str, Any]:
    """Classify a flattened completed Sweep table and suggest valid downstream analyses."""
    if frame.empty:
        raise ValueError("sweep feedback requires a non-empty table")
    parameter_columns = [str(c) for c in frame.columns if str(c).startswith("param:")]
    output_columns = [str(c) for c in frame.columns if str(c).startswith("metric:") or str(c).startswith("result:")]
    parameter_summary = []
    for column in parameter_columns:
        values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        parameter_summary.append({"field": column, "finite": int(len(values)), "unique": int(values.nunique())})
    two_level = [r["field"] for r in parameter_summary if r["unique"] == 2]
    varying = [r["field"] for r in parameter_summary if r["unique"] >= 2]
    recommendations: list[dict[str, Any]] = []
    if len(two_level) >= 1 and output_columns:
        recommendations.append({"analysis": "factorial-effects", "parameters": two_level[:8], "outputs": output_columns[:12], "reason": "one or more sweep parameters have exactly two observed levels"})
    if len(varying) >= 2 and output_columns:
        for a, b in itertools.combinations(varying[:8], 2):
            recommendations.append({"analysis": "response-surface", "parameters": [a, b], "outputs": output_columns[:12], "reason": "two parameters vary across the completed sweep"})
            if len(recommendations) >= 12:
                break
    if varying and output_columns:
        recommendations.append({"analysis": "sensitivity-screening", "parameters": varying[:12], "outputs": output_columns[:12], "reason": "completed sweep exposes varying numeric parameters and outputs"})
    morris_ready = {"__trajectory", "__step", "__changed_factor"}.issubset(set(frame.columns))
    if morris_ready and output_columns:
        recommendations.insert(0, {"analysis": "morris-effects", "parameters": varying[:12], "outputs": output_columns[:12], "reason": "Morris trajectory metadata is preserved in the completed table"})
    return {
        "kind": "completed-sweep-feedback",
        "parameter_columns": parameter_columns,
        "output_columns": output_columns,
        "parameter_summary": parameter_summary,
        "two_level_parameters": two_level,
        "varying_parameters": varying,
        "morris_ready": bool(morris_ready),
        "recommendations": recommendations,
        "boundary": "Feedback classifies table structure and recommends compatible analyses only. It does not rank scientific importance or validate the sweep model.",
    }
