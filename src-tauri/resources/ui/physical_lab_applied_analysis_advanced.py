"""Advanced applied mathematics/statistics helpers for Engineering Lab.

All routines are explicit, bounded, and deterministic for a fixed seed. Robust
regression and cross-validation are descriptive model checks; factorial/Morris
outputs are screening analyses. DOE-to-sweep integration may create a queued job,
but never starts execution automatically.
"""
from __future__ import annotations

import inspect
import importlib
import itertools
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

import physical_lab_sweep_executor as sweeps

BOUNDARY = (
    "Advanced applied analysis supports robust fitting, validation and sensitivity screening over explicit data. "
    "These calculations do not establish causality, physical validity, calibration equivalence or experimental confirmation. "
    "Generated designs and queued sweep jobs are prospective until separately executed and recorded as evidence."
)


def _finite_frame(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out = pd.DataFrame({str(c): pd.to_numeric(frame[c], errors="coerce") for c in columns})
    return out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def robust_regression_huber(frame: pd.DataFrame, predictors: Sequence[str], response: str, *, delta: float = 1.345, max_iter: int = 100, tol: float = 1e-8) -> dict[str, Any]:
    predictors = [str(p) for p in predictors]
    if not predictors or response in predictors:
        raise ValueError("choose at least one predictor distinct from the response")
    work = _finite_frame(frame, [*predictors, response])
    if len(work) < len(predictors) + 3:
        raise ValueError("not enough finite rows for robust regression")
    x = np.column_stack([np.ones(len(work)), work[predictors].to_numpy(dtype=float)])
    y = work[response].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    converged = False
    weights = np.ones(len(y), dtype=float)
    for iteration in range(1, int(max_iter) + 1):
        residual = y - x @ beta
        center = float(np.median(residual))
        mad = float(np.median(np.abs(residual - center)))
        scale = max(1.4826 * mad, np.finfo(float).eps)
        u = residual / scale
        abs_u = np.abs(u)
        weights = np.where(abs_u <= delta, 1.0, delta / np.maximum(abs_u, np.finfo(float).eps))
        root_w = np.sqrt(weights)
        new_beta, *_ = np.linalg.lstsq(x * root_w[:, None], y * root_w, rcond=None)
        if float(np.linalg.norm(new_beta - beta)) <= tol * (1.0 + float(np.linalg.norm(beta))):
            beta = new_beta
            converged = True
            break
        beta = new_beta
    predicted = x @ beta
    residual = y - predicted
    terms = ["intercept", *predictors]
    return {
        "kind": "huber-regression",
        "predictors": predictors,
        "response": str(response),
        "delta": float(delta),
        "iterations": int(iteration),
        "converged": bool(converged),
        "coefficients": [{"term": t, "estimate": float(v)} for t, v in zip(terms, beta)],
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "mae": float(np.mean(np.abs(residual))),
        "downweighted_fraction": float(np.mean(weights < 0.999999)),
        "diagnostics": pd.DataFrame({"observed": y, "predicted": predicted, "residual": residual, "weight": weights}),
        "boundary": BOUNDARY,
    }


def _poly_fit_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, degree: int) -> np.ndarray:
    train = np.vander(x_train, N=degree + 1, increasing=True)
    test = np.vander(x_test, N=degree + 1, increasing=True)
    beta, *_ = np.linalg.lstsq(train, y_train, rcond=None)
    return test @ beta


def cross_validate_polynomials(frame: pd.DataFrame, predictor: str, response: str, *, degrees: Sequence[int] = (1, 2, 3), folds: int = 5, seed: int = 0) -> pd.DataFrame:
    work = _finite_frame(frame, [predictor, response])
    n = len(work)
    folds = int(folds)
    if folds < 2 or folds > min(20, n):
        raise ValueError("fold count must be between 2 and the number of finite observations")
    degrees = sorted({int(d) for d in degrees})
    if not degrees or any(d < 1 or d > 6 for d in degrees):
        raise ValueError("polynomial degrees must be within 1..6")
    rng = np.random.default_rng(int(seed))
    order = rng.permutation(n)
    fold_ids = np.arange(n) % folds
    assigned = np.empty(n, dtype=int); assigned[order] = fold_ids
    x = work[predictor].to_numpy(dtype=float); y = work[response].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for degree in degrees:
        fold_rmse = []
        fold_mae = []
        for fold in range(folds):
            test_mask = assigned == fold; train_mask = ~test_mask
            if train_mask.sum() <= degree or test_mask.sum() == 0:
                continue
            pred = _poly_fit_predict(x[train_mask], y[train_mask], x[test_mask], degree)
            err = y[test_mask] - pred
            fold_rmse.append(float(np.sqrt(np.mean(err ** 2))))
            fold_mae.append(float(np.mean(np.abs(err))))
        if not fold_rmse:
            continue
        rows.append({
            "degree": degree,
            "folds_used": len(fold_rmse),
            "cv_rmse_mean": float(np.mean(fold_rmse)),
            "cv_rmse_std": float(np.std(fold_rmse, ddof=1)) if len(fold_rmse) > 1 else 0.0,
            "cv_mae_mean": float(np.mean(fold_mae)),
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["cv_rmse_mean", "degree"]).reset_index(drop=True) if not out.empty else out


def factorial_effects(frame: pd.DataFrame, factors: Sequence[str], response: str, *, include_interactions: bool = True) -> dict[str, Any]:
    factors = [str(f) for f in factors]
    if len(factors) < 1:
        raise ValueError("factorial effects require at least one factor")
    work = _finite_frame(frame, [*factors, response])
    coded: dict[str, np.ndarray] = {}
    levels: dict[str, list[float]] = {}
    for factor in factors:
        values = np.sort(work[factor].unique())
        if len(values) != 2:
            raise ValueError(f"factor {factor!r} must have exactly two observed levels")
        levels[factor] = [float(values[0]), float(values[1])]
        coded[factor] = np.where(work[factor].to_numpy(dtype=float) == values[0], -1.0, 1.0)
    columns = [np.ones(len(work))]; names = ["intercept"]
    for factor in factors:
        columns.append(coded[factor]); names.append(factor)
    if include_interactions:
        for a, b in itertools.combinations(factors, 2):
            columns.append(coded[a] * coded[b]); names.append(f"{a}:{b}")
    design = np.column_stack(columns)
    y = work[response].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ beta; residual = y - predicted
    effects = []
    for name, coefficient in zip(names[1:], beta[1:]):
        effects.append({"term": name, "effect": float(2.0 * coefficient), "coefficient": float(coefficient), "kind": "interaction" if ":" in name else "main"})
    effects.sort(key=lambda r: abs(float(r["effect"])), reverse=True)
    return {
        "kind": "two-level-factorial-effects",
        "factors": factors,
        "levels": levels,
        "response": response,
        "effects": effects,
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "n": int(len(work)),
        "boundary": "Factorial effects describe contrasts within the observed two-level design; they do not establish causality or extrapolate beyond those levels.",
    }


def morris_design(factors: Sequence[Mapping[str, Any]], *, trajectories: int = 8, levels: int = 6, seed: int = 0) -> dict[str, Any]:
    parsed = []
    for item in factors:
        name = str(item.get("name") or "").strip(); low = float(item.get("low")); high = float(item.get("high"))
        if not name or not math.isfinite(low) or not math.isfinite(high) or not low < high:
            raise ValueError("Morris factors require unique names and finite low < high")
        if any(p["name"] == name for p in parsed):
            raise ValueError("Morris factor names must be unique")
        parsed.append({"name": name, "low": low, "high": high})
    if not parsed:
        raise ValueError("Morris design requires at least one factor")
    trajectories = int(trajectories); levels = int(levels)
    if trajectories < 2 or trajectories > 100 or levels < 4 or levels > 20:
        raise ValueError("Morris trajectories must be 2..100 and levels 4..20")
    k = len(parsed); delta = levels / (2.0 * (levels - 1.0))
    grid = np.linspace(0.0, 1.0, levels)
    rng = np.random.default_rng(int(seed)); rows = []
    for traj in range(trajectories):
        base = rng.choice(grid[grid <= 1.0 - delta], size=k)
        order = rng.permutation(k)
        point = base.copy()
        rows.append((traj, 0, "", point.copy()))
        for step, idx in enumerate(order, start=1):
            point = point.copy(); point[idx] += delta
            rows.append((traj, step, parsed[idx]["name"], point.copy()))
    records = []
    for traj, step, changed, unit in rows:
        record: dict[str, Any] = {"design_index": len(records), "__trajectory": int(traj), "__step": int(step), "__changed_factor": changed}
        for i, factor in enumerate(parsed):
            record[factor["name"]] = float(factor["low"] + unit[i] * (factor["high"] - factor["low"]))
        records.append(record)
    return {"kind": "morris-screening-design", "levels": levels, "trajectories": trajectories, "delta_unit": float(delta), "factors": parsed, "rows": records, "boundary": "Morris rows are prospective screening settings until executed by an allow-listed model or experiment."}


def morris_effects(frame: pd.DataFrame, response: str, factors: Sequence[str]) -> pd.DataFrame:
    required = ["__trajectory", "__step", "__changed_factor", response, *factors]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"Morris analysis missing columns: {missing}")
    numeric = _finite_frame(frame, ["__trajectory", "__step", response, *factors])
    changed = frame.loc[numeric.index, "__changed_factor"].astype(str).reset_index(drop=True)
    numeric["__changed_factor"] = changed
    elementary: dict[str, list[float]] = {str(f): [] for f in factors}
    for _traj, group in numeric.sort_values(["__trajectory", "__step"]).groupby("__trajectory"):
        group = group.reset_index(drop=True)
        for i in range(1, len(group)):
            factor = str(group.loc[i, "__changed_factor"])
            if factor not in elementary:
                continue
            dx = float(group.loc[i, factor] - group.loc[i - 1, factor]); dy = float(group.loc[i, response] - group.loc[i - 1, response])
            if dx != 0 and math.isfinite(dx) and math.isfinite(dy):
                elementary[factor].append(dy / dx)
    rows = []
    for factor, values in elementary.items():
        if not values:
            continue
        arr = np.asarray(values, dtype=float)
        rows.append({"factor": factor, "mu": float(np.mean(arr)), "mu_star": float(np.mean(np.abs(arr))), "sigma": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0, "elementary_effects": int(len(arr))})
    out = pd.DataFrame(rows)
    return out.sort_values("mu_star", ascending=False).reset_index(drop=True) if not out.empty else out


def adapter_parameter_names(profile: str, adapter: str) -> list[str]:
    spec = sweeps.ADAPTERS.get(str(adapter))
    if not spec or profile not in spec.get("profiles", []):
        raise ValueError("adapter is not allow-listed for this profile")
    module = importlib.import_module(str(spec["module"])); fn = getattr(module, str(spec["function"]))
    signature = inspect.signature(fn)
    names = []
    for name, parameter in signature.parameters.items():
        if parameter.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        names.append(str(name))
    return names


def prepare_sweep_rows(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, float | int]]:
    allowed = set(adapter_parameter_names(profile, adapter)); prepared = []
    if not rows:
        raise ValueError("design has no rows")
    for index, row in enumerate(rows):
        clean: dict[str, float | int] = {"design_index": int(row.get("design_index", index))}
        unknown = [str(k) for k in row if not str(k).startswith("__") and k != "design_index" and str(k) not in allowed]
        if unknown:
            raise ValueError(f"design fields are not accepted by adapter: {unknown}")
        for key, value in row.items():
            key = str(key)
            if key.startswith("__") or key == "design_index":
                continue
            if key not in allowed:
                continue
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError("sweep design values must be finite")
            clean[key] = numeric
        prepared.append(clean)
    return prepared


def queue_design_as_sweep(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    prepared = prepare_sweep_rows(profile, adapter, rows)
    job = sweeps.create_sweep_job(profile, adapter, prepared)
    return {**job, "execution_started": False, "boundary": "Sweep job was queued only. Starting execution requires a separate explicit user action."}
