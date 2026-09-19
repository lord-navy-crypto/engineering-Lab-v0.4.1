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
        "kind": "pca-svd", "columns": columns, "rows": int(len(work)), "standardized": bool(standardize),
        "means": {c: float(v) for c, v in zip(columns, means)}, "scales": {c: float(v) for c, v in zip(columns, scales)},
        "effective_rank": rank, "singular_values": [float(v) for v in singular],
        "explained_variance_ratio": [float(v) for v in explained], "cumulative_variance_ratio": [float(v) for v in cumulative],
        "loadings": pd.DataFrame(loading_rows), "scores": score_frame, "boundary": BOUNDARY,
    }


def conditioning_diagnostics(frame: pd.DataFrame, columns: Sequence[str], *, center: bool = True, standardize: bool = False) -> dict[str, Any]:
    columns = [str(c) for c in columns]
    if not columns: raise ValueError("conditioning diagnostics require at least one numeric column")
    work = _finite_frame(frame, columns); x = work.to_numpy(dtype=float)
    if center: x = x - x.mean(axis=0)
    if standardize:
        scale = x.std(axis=0, ddof=1)
        if np.any(scale <= 0) or np.any(~np.isfinite(scale)): raise ValueError("standardized conditioning requires non-zero finite variance")
        x = x / scale
    singular = np.linalg.svd(x, compute_uv=False)
    if singular.size == 0: raise ValueError("conditioning matrix is empty")
    eps = np.finfo(float).eps; largest = float(np.max(singular)); smallest = float(np.min(singular))
    condition = float(np.inf if smallest <= eps * max(largest, 1.0) else largest / smallest)
    rank = int(np.linalg.matrix_rank(x))
    return {"kind": "conditioning-diagnostics", "columns": columns, "rows": int(len(work)), "centered": bool(center), "standardized": bool(standardize), "rank": rank, "column_count": int(len(columns)), "full_column_rank": bool(rank == len(columns)), "condition_number": condition, "singular_values": [float(v) for v in singular], "boundary": "A large condition number indicates numerical sensitivity/near-collinearity in this representation; it is not proof that any physical variable is redundant or invalid."}


def _inverse_problem(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, standardize: bool = True) -> dict[str, Any]:
    predictors = [str(p) for p in predictors]
    if not predictors or response in predictors: raise ValueError("choose predictors distinct from the response")
    work = _finite_frame(frame, [*predictors, response])
    if len(work) < len(predictors) + 2: raise ValueError("not enough finite observations for inverse solve")
    raw_x = work[predictors].to_numpy(dtype=float); y = work[response].to_numpy(dtype=float)
    means = raw_x.mean(axis=0); scales = np.ones(len(predictors), dtype=float); x = raw_x - means
    if standardize:
        scales = x.std(axis=0, ddof=1)
        if np.any(scales <= 0) or np.any(~np.isfinite(scales)): raise ValueError("standardization requires non-zero predictor variance")
        x = x / scales
    y_mean = float(y.mean()); yc = y - y_mean; u, singular, vt = np.linalg.svd(x, full_matrices=False)
    return {"work": work, "x": x, "y": y, "yc": yc, "y_mean": y_mean, "means": means, "scales": scales, "u": u, "singular": singular, "vt": vt, "predictors": predictors, "response": str(response), "standardized": bool(standardize)}


def tikhonov_regression(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, regularization: float = 1e-3, standardize: bool = True, penalize_intercept: bool = False) -> dict[str, Any]:
    predictors = [str(p) for p in predictors]
    if not predictors or response in predictors: raise ValueError("choose predictors distinct from the response")
    lam = float(regularization)
    if not math.isfinite(lam) or lam < 0: raise ValueError("regularization must be finite and non-negative")
    work = _finite_frame(frame, [*predictors, response])
    if len(work) < len(predictors) + 2: raise ValueError("not enough finite observations for inverse solve")
    raw_x = work[predictors].to_numpy(dtype=float); y = work[response].to_numpy(dtype=float); means = raw_x.mean(axis=0); scales = np.ones(len(predictors), dtype=float); x = raw_x - means
    if standardize:
        scales = x.std(axis=0, ddof=1)
        if np.any(scales <= 0) or np.any(~np.isfinite(scales)): raise ValueError("standardization requires non-zero predictor variance")
        x = x / scales
    design = np.column_stack([np.ones(len(x)), x]); penalty = np.eye(design.shape[1])
    if not penalize_intercept: penalty[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + lam * penalty, design.T @ y); predicted = design @ beta; residual = y - predicted
    return {"kind": "tikhonov-linear-inverse", "predictors": predictors, "response": str(response), "regularization": lam, "standardized": bool(standardize), "penalize_intercept": bool(penalize_intercept), "coefficients": [{"term": t, "estimate": float(v)} for t, v in zip(["intercept", *predictors], beta)], "rmse": float(np.sqrt(np.mean(residual ** 2))), "mae": float(np.mean(np.abs(residual))), "data_residual_norm": float(np.linalg.norm(residual)), "regularization_norm": float(np.linalg.norm(beta[1:] if not penalize_intercept else beta)), "diagnostics": pd.DataFrame({"observed": y, "predicted": predicted, "residual": residual}), "preprocessing": {"means": {p: float(v) for p, v in zip(predictors, means)}, "scales": {p: float(v) for p, v in zip(predictors, scales)}}, "boundary": "Tikhonov regularization stabilizes a specified linear inverse problem by imposing a coefficient penalty. The chosen regularization strength is an analysis assumption, not a physical law."}


def regularization_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, lambdas: Sequence[float] | None = None, standardize: bool = True) -> pd.DataFrame:
    if lambdas is None: lambdas = np.logspace(-8, 4, 40)
    rows = []
    for value in lambdas:
        lam = float(value)
        if lam < 0 or not math.isfinite(lam): continue
        result = tikhonov_regression(frame, predictors, response, regularization=lam, standardize=standardize)
        rows.append({"regularization": lam, "rmse": float(result["rmse"]), "data_residual_norm": float(result["data_residual_norm"]), "regularization_norm": float(result["regularization_norm"])})
    out = pd.DataFrame(rows)
    if out.empty: raise ValueError("regularization path has no valid points")
    return out.sort_values("regularization").reset_index(drop=True)


def truncated_svd_regression(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, rank: int, standardize: bool = True) -> dict[str, Any]:
    problem = _inverse_problem(frame, predictors, response, standardize=standardize); singular = problem["singular"]; max_rank = int(len(singular)); rank = int(rank)
    if rank < 1 or rank > max_rank: raise ValueError(f"TSVD rank must be within 1..{max_rank}")
    tol = np.finfo(float).eps * max(problem["x"].shape) * (float(singular[0]) if max_rank else 1.0)
    usable = np.where(singular[:rank] > tol, 1.0 / singular[:rank], 0.0)
    beta = problem["vt"][:rank].T @ (usable * (problem["u"][:, :rank].T @ problem["yc"]))
    predicted = problem["y_mean"] + problem["x"] @ beta; residual = problem["y"] - predicted
    coefficients = [{"term": "intercept", "estimate": problem["y_mean"]}] + [{"term": p, "estimate": float(v)} for p, v in zip(problem["predictors"], beta)]
    return {"kind": "tsvd-linear-inverse", "rank": rank, "max_rank": max_rank, "predictors": problem["predictors"], "response": problem["response"], "standardized": problem["standardized"], "singular_values": [float(v) for v in singular], "coefficients": coefficients, "rmse": float(np.sqrt(np.mean(residual ** 2))), "data_residual_norm": float(np.linalg.norm(residual)), "solution_norm": float(np.linalg.norm(beta)), "diagnostics": pd.DataFrame({"observed": problem["y"], "predicted": predicted, "residual": residual}), "boundary": "TSVD suppresses discarded singular directions. Retained rank is a numerical regularization choice, not a claim about physical dimensionality."}


def tsvd_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, standardize: bool = True) -> pd.DataFrame:
    problem = _inverse_problem(frame, predictors, response, standardize=standardize); rows = []
    for rank in range(1, len(problem["singular"]) + 1):
        result = truncated_svd_regression(frame, predictors, response, rank=rank, standardize=standardize)
        rows.append({"rank": rank, "rmse": result["rmse"], "data_residual_norm": result["data_residual_norm"], "solution_norm": result["solution_norm"]})
    return pd.DataFrame(rows)


def tikhonov_gcv_path(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, lambdas: Sequence[float] | None = None, standardize: bool = True) -> pd.DataFrame:
    problem = _inverse_problem(frame, predictors, response, standardize=standardize)
    if lambdas is None: lambdas = np.logspace(-10, 6, 96)
    x, y, n = problem["x"], problem["yc"], len(problem["yc"]); u, singular, vt = problem["u"], problem["singular"], problem["vt"]; uy = u.T @ y; rows = []
    for value in lambdas:
        lam = float(value)
        if not math.isfinite(lam) or lam <= 0: continue
        filt = singular / (singular ** 2 + lam); beta = vt.T @ (filt * uy); residual = y - x @ beta; rss = float(np.dot(residual, residual)); trace_h = float(np.sum((singular ** 2) / (singular ** 2 + lam))); denom = (n - trace_h) ** 2
        rows.append({"regularization": lam, "gcv": float(n * rss / denom) if denom > np.finfo(float).eps else float("inf"), "effective_degrees_of_freedom": trace_h, "data_residual_norm": float(np.linalg.norm(residual)), "solution_norm": float(np.linalg.norm(beta)), "rmse": float(np.sqrt(np.mean(residual ** 2)))})
    out = pd.DataFrame(rows)
    if out.empty: raise ValueError("GCV path has no valid positive regularization values")
    return out.sort_values("regularization").reset_index(drop=True)


def gcv_choice(path: pd.DataFrame) -> dict[str, float]:
    if path.empty or "gcv" not in path.columns or "regularization" not in path.columns: raise ValueError("GCV path is empty or malformed")
    finite = path.replace([np.inf, -np.inf], np.nan).dropna(subset=["gcv", "regularization"])
    if finite.empty: raise ValueError("GCV path has no finite score")
    row = finite.loc[finite["gcv"].idxmin()]
    return {"regularization": float(row["regularization"]), "gcv": float(row["gcv"])}


def lcurve_curvature(path: pd.DataFrame) -> pd.DataFrame:
    required = {"regularization", "data_residual_norm", "solution_norm"}
    if path.empty or not required.issubset(path.columns): raise ValueError("L-curve path is empty or malformed")
    work = path.sort_values("regularization").copy(); x = np.log(np.maximum(pd.to_numeric(work["data_residual_norm"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny)); y = np.log(np.maximum(pd.to_numeric(work["solution_norm"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny)); t = np.log(np.maximum(pd.to_numeric(work["regularization"], errors="coerce").to_numpy(dtype=float), np.finfo(float).tiny))
    if len(work) < 5 or not (np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(np.isfinite(t))): raise ValueError("L-curve curvature needs at least five finite path points")
    dx = np.gradient(x, t); dy = np.gradient(y, t); ddx = np.gradient(dx, t); ddy = np.gradient(dy, t); denom = np.maximum((dx * dx + dy * dy) ** 1.5, np.finfo(float).eps); curvature = np.abs(dx * ddy - dy * ddx) / denom; curvature[0] = np.nan; curvature[-1] = np.nan; work["lcurve_curvature"] = curvature
    return work


def lcurve_choice(path: pd.DataFrame) -> dict[str, float]:
    work = lcurve_curvature(path); finite = work.replace([np.inf, -np.inf], np.nan).dropna(subset=["lcurve_curvature", "regularization"])
    if finite.empty: raise ValueError("L-curve path has no finite interior curvature")
    row = finite.loc[finite["lcurve_curvature"].idxmax()]
    return {"regularization": float(row["regularization"]), "curvature": float(row["lcurve_curvature"])}


def sweep_feedback(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty: raise ValueError("sweep feedback requires a non-empty table")
    parameter_columns = [str(c) for c in frame.columns if str(c).startswith("param:")]; output_columns = [str(c) for c in frame.columns if str(c).startswith("metric:") or str(c).startswith("result:")]
    parameter_summary = []
    for column in parameter_columns:
        values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna(); parameter_summary.append({"field": column, "finite": int(len(values)), "unique": int(values.nunique())})
    two_level = [r["field"] for r in parameter_summary if r["unique"] == 2]; varying = [r["field"] for r in parameter_summary if r["unique"] >= 2]; recommendations: list[dict[str, Any]] = []
    if len(two_level) >= 1 and output_columns: recommendations.append({"analysis": "factorial-effects", "parameters": two_level[:8], "outputs": output_columns[:12], "reason": "one or more sweep parameters have exactly two observed levels"})
    if len(varying) >= 2 and output_columns:
        for a, b in itertools.combinations(varying[:8], 2):
            recommendations.append({"analysis": "response-surface", "parameters": [a, b], "outputs": output_columns[:12], "reason": "two parameters vary across the completed sweep"})
            if len(recommendations) >= 12: break
    if varying and output_columns: recommendations.append({"analysis": "sensitivity-screening", "parameters": varying[:12], "outputs": output_columns[:12], "reason": "completed sweep exposes varying numeric parameters and outputs"})
    morris_ready = {"__trajectory", "__step", "__changed_factor"}.issubset(set(frame.columns))
    if morris_ready and output_columns: recommendations.insert(0, {"analysis": "morris-effects", "parameters": varying[:12], "outputs": output_columns[:12], "reason": "Morris trajectory metadata is preserved in the completed table"})
    return {"kind": "completed-sweep-feedback", "parameter_columns": parameter_columns, "output_columns": output_columns, "parameter_summary": parameter_summary, "two_level_parameters": two_level, "varying_parameters": varying, "morris_ready": bool(morris_ready), "recommendations": recommendations, "boundary": "Feedback classifies table structure and recommends compatible analyses only. It does not rank scientific importance or validate the sweep model."}
