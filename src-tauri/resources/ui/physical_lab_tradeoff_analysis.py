"""Descriptive correlation and Pareto trade-off helpers for Engineering Lab.

These helpers operate on existing numeric tables. Correlation is descriptive and does
not imply causality. Pareto membership means non-dominance only for the selected
columns/directions; it is not proof of physical optimality or model validity.
"""
from __future__ import annotations

from typing import Sequence

import pandas as pd

BOUNDARY = (
    "Correlation is descriptive association, not causality. Pareto frontier membership is non-dominance "
    "for the selected objectives only; it does not establish physical optimality, feasibility, validation, or uncertainty."
)


def correlation_matrix(frame: pd.DataFrame, columns: Sequence[str], method: str = "pearson") -> pd.DataFrame:
    method = str(method).lower()
    if method not in {"pearson", "spearman"}:
        raise ValueError("correlation method must be pearson or spearman")
    selected: dict[str, pd.Series] = {}
    for name in columns:
        if name not in frame.columns:
            raise ValueError(f"column {name!r} is not present")
        series = pd.to_numeric(frame[name], errors="coerce")
        if series.notna().sum() >= 2:
            selected[str(name)] = series
    if len(selected) < 2:
        raise ValueError("at least two numeric columns with two finite observations are required")
    return pd.DataFrame(selected).corr(method=method, min_periods=2)


def pareto_frontier(
    frame: pd.DataFrame,
    *,
    x: str,
    x_goal: str,
    y: str,
    y_goal: str,
) -> pd.DataFrame:
    """Return finite objective rows with a Pareto flag for exactly two objectives."""
    if x == y:
        raise ValueError("Pareto objectives must use different columns")
    if x not in frame.columns or y not in frame.columns:
        raise ValueError("selected Pareto objective is not present")
    if x_goal not in {"min", "max"} or y_goal not in {"min", "max"}:
        raise ValueError("objective directions must be min or max")
    work = pd.DataFrame({
        "source_index": frame.index,
        x: pd.to_numeric(frame[x], errors="coerce"),
        y: pd.to_numeric(frame[y], errors="coerce"),
    }).dropna(subset=[x, y]).reset_index(drop=True)
    if work.empty:
        return work.assign(pareto=pd.Series(dtype=bool))
    tx = work[x] if x_goal == "min" else -work[x]
    ty = work[y] if y_goal == "min" else -work[y]
    work["__x"] = tx
    work["__y"] = ty
    work["pareto"] = False
    best_prior: float | None = None
    for x_value, group in work.sort_values(["__x", "__y"], kind="mergesort").groupby("__x", sort=True):
        group_min = float(group["__y"].min())
        is_new = best_prior is None or group_min < best_prior
        if is_new:
            indices = group.index[group["__y"] == group_min]
            work.loc[indices, "pareto"] = True
            best_prior = group_min if best_prior is None else min(best_prior, group_min)
    return work.drop(columns=["__x", "__y"])
