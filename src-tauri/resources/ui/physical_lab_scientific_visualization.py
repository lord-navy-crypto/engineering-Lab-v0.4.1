"""Scientific-semantic visualization helpers for Engineering Lab.

This layer consumes explicit result contracts, unit metadata, uncertainty objects and
sweep tables. It does not invent units, uncertainty, validation or causality.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from physical_lab_result_contracts import find_uncertainty_objects, get_contract, validate_uncertainty
from physical_lab_units import compatible, convert, supported_units, unit_info

BOUNDARY = (
    "Scientific visualization consumes explicit schema/unit/UQ metadata when available. "
    "Unregistered fields remain plottable but their physical meaning is unspecified. "
    "Sensitivity and response-surface summaries are descriptive computational analyses, not causality or validation."
)


def contract_field_metadata(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    contract = get_contract(result.get("schema"))
    return dict((contract or {}).get("fields") or {})


def field_metadata(result: Mapping[str, Any], field: str) -> dict[str, Any]:
    meta = contract_field_metadata(result).get(str(field))
    if not meta:
        return {"registered": False, "field": str(field), "unit": "", "quantity": None, "role": None}
    return {
        "registered": True,
        "field": str(field),
        "unit": str(meta.get("unit") or ""),
        "quantity": meta.get("quantity"),
        "role": meta.get("role"),
        "shape": meta.get("shape"),
        "description": meta.get("description") or "",
    }


def axis_label(field: str, unit: str | None = None) -> str:
    u = str(unit or "").strip()
    return f"{field} [{u}]" if u else str(field)


def convertible_units(unit: str) -> list[str]:
    info = unit_info(unit)
    if not info.get("known"):
        return []
    return list(supported_units().get(str(info["dimension"]), []))


def convert_series(values: Sequence[Any], from_unit: str, to_unit: str) -> list[float | None]:
    if from_unit == to_unit:
        out = []
        for value in values:
            try:
                x = float(value)
            except Exception:
                out.append(None); continue
            out.append(x if math.isfinite(x) else None)
        return out
    if not compatible(from_unit, to_unit):
        raise ValueError(f"incompatible units: {from_unit!r} -> {to_unit!r}")
    out: list[float | None] = []
    for value in values:
        try:
            x = float(value)
            out.append(convert(x, from_unit, to_unit) if math.isfinite(x) else None)
        except Exception:
            out.append(None)
    return out


def overlay_unit_plan(source_units: Sequence[str]) -> dict[str, Any]:
    units = [str(u or "") for u in source_units]
    specified = [u for u in units if u]
    if not specified:
        return {"compatible": True, "registered": False, "canonical_target": "", "units": units}
    target = specified[0]
    for unit in specified[1:]:
        if not compatible(target, unit):
            return {"compatible": False, "registered": True, "canonical_target": target, "units": units}
    return {"compatible": True, "registered": True, "canonical_target": target, "units": units}


def uncertainty_records(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in find_uncertainty_objects(result):
        value = dict(item.get("value") or {})
        validation = validate_uncertainty(value)
        rows.append({
            "path": item.get("path"),
            "valid": bool(validation.get("valid")),
            "errors": list(validation.get("errors") or []),
            "estimate": value.get("estimate"),
            "unit": value.get("unit") or "",
            "standard_uncertainty": value.get("standard_uncertainty"),
            "coverage_factor": value.get("coverage_factor"),
            "interval": value.get("interval"),
            "coverage_probability": value.get("coverage_probability"),
            "method": value.get("method"),
            "sha256": value.get("uncertainty_sha256"),
        })
    return rows


def uncertainty_plot_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not record.get("valid"):
        raise ValueError("uncertainty object is not structurally valid")
    estimate = float(record.get("estimate"))
    unit = str(record.get("unit") or "")
    su = record.get("standard_uncertainty")
    interval = record.get("interval")
    if su is not None:
        err = float(su)
        return {"estimate": estimate, "unit": unit, "error_plus": err, "error_minus": err, "kind": "standard-uncertainty"}
    if isinstance(interval, Sequence) and len(interval) == 2:
        lo, hi = float(interval[0]), float(interval[1])
        return {"estimate": estimate, "unit": unit, "error_plus": hi - estimate, "error_minus": estimate - lo, "kind": "interval"}
    return {"estimate": estimate, "unit": unit, "error_plus": None, "error_minus": None, "kind": "estimate-only"}


def _finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    s = pd.to_numeric(frame[column], errors="coerce")
    return s.where(np.isfinite(s), np.nan)


def local_sensitivity(frame: pd.DataFrame, parameter: str, output: str) -> pd.DataFrame:
    """Finite-difference dy/dx over sorted unique parameter values."""
    if parameter not in frame.columns or output not in frame.columns:
        raise ValueError("parameter/output field missing")
    work = pd.DataFrame({"x": _finite_numeric(frame, parameter), "y": _finite_numeric(frame, output)}).dropna()
    if len(work) < 2:
        raise ValueError("at least two finite points are required")
    grouped = work.groupby("x", as_index=False)["y"].mean().sort_values("x")
    if len(grouped) < 2:
        raise ValueError("parameter must vary")
    x = grouped["x"].to_numpy(dtype=float)
    y = grouped["y"].to_numpy(dtype=float)
    dx = np.diff(x)
    if np.any(dx == 0):
        raise ValueError("parameter values must be distinct after grouping")
    slopes = np.diff(y) / dx
    centers = (x[:-1] + x[1:]) / 2.0
    return pd.DataFrame({"parameter_center": centers, "sensitivity": slopes, "delta_parameter": dx, "delta_output": np.diff(y)})


def standardized_sensitivity(frame: pd.DataFrame, parameters: Sequence[str], output: str) -> pd.DataFrame:
    """Univariate standardized linear slope and rank correlation for screening."""
    if output not in frame.columns:
        raise ValueError("output field missing")
    rows = []
    y_all = _finite_numeric(frame, output)
    for parameter in parameters:
        if parameter not in frame.columns or parameter == output:
            continue
        x_all = _finite_numeric(frame, parameter)
        mask = x_all.notna() & y_all.notna()
        x = x_all[mask]; y = y_all[mask]
        if len(x) < 3 or float(x.std(ddof=0)) == 0 or float(y.std(ddof=0)) == 0:
            continue
        zx = (x - x.mean()) / x.std(ddof=0)
        zy = (y - y.mean()) / y.std(ddof=0)
        slope = float((zx * zy).mean())
        spearman = float(x.rank().corr(y.rank(), method="pearson"))
        rows.append({"parameter": parameter, "standardized_slope": slope, "abs_standardized_slope": abs(slope), "spearman": spearman, "n": int(len(x))})
    out = pd.DataFrame(rows)
    return out.sort_values("abs_standardized_slope", ascending=False).reset_index(drop=True) if not out.empty else out


def response_surface(frame: pd.DataFrame, x: str, y: str, z: str, *, agg: str = "mean") -> dict[str, Any]:
    if any(name not in frame.columns for name in (x, y, z)):
        raise ValueError("response-surface field missing")
    work = pd.DataFrame({x: _finite_numeric(frame, x), y: _finite_numeric(frame, y), z: _finite_numeric(frame, z)}).dropna()
    if work.empty:
        raise ValueError("no finite response-surface rows")
    if work[x].nunique() < 2 or work[y].nunique() < 2:
        raise ValueError("response surface needs at least two unique values on both axes")
    if agg not in {"mean", "median", "min", "max"}:
        raise ValueError("unsupported response-surface aggregation")
    pivot = work.pivot_table(index=y, columns=x, values=z, aggfunc=agg)
    return {
        "x": [float(v) for v in pivot.columns],
        "y": [float(v) for v in pivot.index],
        "z": pivot.to_numpy(dtype=float).tolist(),
        "rows": int(len(work)),
        "coverage": int(np.isfinite(pivot.to_numpy(dtype=float)).sum()),
        "grid_cells": int(pivot.shape[0] * pivot.shape[1]),
        "aggregation": agg,
    }
