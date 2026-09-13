"""Scientific visual-analytics helpers for Engineering Lab.

This module changes representation and interaction only. It consumes explicit result
contracts, unit metadata and uncertainty objects where available, but does not invent
scientific meaning, validation, uncertainty or causality.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from physical_lab_result_contracts import find_uncertainty_objects, get_contract, validate_uncertainty
from physical_lab_units import compatible, convert, supported_units, unit_info

DASHBOARD_SCHEMA = "engineering-lab-visual-analytics-dashboard-v1"
SCIENCE_RECIPE_SCHEMA = "engineering-lab-science-analysis-recipe-v1"
BOUNDARY = (
    "Visual analytics changes representation and selection, not evidence. Explicit contracts/units/UQ are consumed when available; "
    "unregistered fields remain unspecified. Overlays, sensitivity, correlation and response surfaces do not establish comparability, validation, uncertainty completeness or causality."
)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def common_numeric_columns(frames: Sequence[pd.DataFrame]) -> list[str]:
    if not frames:
        return []
    common = set(str(c) for c in frames[0].columns)
    for frame in frames[1:]:
        common &= {str(c) for c in frame.columns}
    out: list[str] = []
    for name in sorted(common):
        if all(not _numeric(frame[name]).dropna().map(lambda x: math.isfinite(float(x))).loc[lambda s: s].empty for frame in frames):
            out.append(name)
    return out


def uncertainty_candidates(columns: Sequence[str], y: str) -> dict[str, list[str]]:
    y_text = str(y); base = y_text.split(":", 1)[-1].split(".")[-1].lstrip("$")
    lowered = {str(c).lower(): str(c) for c in columns}
    symmetric: list[str] = []; lower: list[str] = []; upper: list[str] = []
    for suffix in ("_sigma", "_std", "_stderr", "_error", "_err", ".sigma", ".std"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered: symmetric.append(lowered[candidate.lower()])
    for suffix in ("_lower", "_lo", "_min", ".lower", ".lo"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered: lower.append(lowered[candidate.lower()])
    for suffix in ("_upper", "_hi", "_max", ".upper", ".hi"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered: upper.append(lowered[candidate.lower()])
    return {"symmetric": list(dict.fromkeys(symmetric)), "lower": list(dict.fromkeys(lower)), "upper": list(dict.fromkeys(upper))}


def uncertainty_error_arrays(frame: pd.DataFrame, y: str, *, symmetric: str | None = None, lower: str | None = None, upper: str | None = None) -> dict[str, list[float]]:
    if y not in frame.columns: raise ValueError(f"Y field {y!r} is not present")
    yv = _numeric(frame[y])
    if symmetric:
        if symmetric not in frame.columns: raise ValueError(f"uncertainty field {symmetric!r} is not present")
        err = _numeric(frame[symmetric])
        if err.isna().any() or (err < 0).any(): raise ValueError("symmetric uncertainty must be finite and non-negative")
        return {"array": [float(x) for x in err], "arrayminus": [float(x) for x in err]}
    if lower or upper:
        if not lower or not upper: raise ValueError("both lower and upper fields are required for asymmetric bounds")
        if lower not in frame.columns or upper not in frame.columns: raise ValueError("lower/upper uncertainty fields are not present")
        lo = _numeric(frame[lower]); hi = _numeric(frame[upper])
        if lo.isna().any() or hi.isna().any() or yv.isna().any(): raise ValueError("Y and bound fields must be finite numeric values")
        minus = yv - lo; plus = hi - yv
        if (minus < 0).any() or (plus < 0).any(): raise ValueError("bounds must satisfy lower <= Y <= upper")
        return {"array": [float(x) for x in plus], "arrayminus": [float(x) for x in minus]}
    return {}


def overlay_frame(sources: Sequence[tuple[str, pd.DataFrame]], x: str, y: str) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for label, frame in sources:
        if x not in frame.columns or y not in frame.columns: continue
        part = pd.DataFrame({"x": _numeric(frame[x]), "y": _numeric(frame[y])})
        part["source"] = str(label); part["source_row"] = list(range(len(part)))
        rows.append(part.dropna(subset=["x", "y"]))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["x", "y", "source", "source_row"])


def selection_indices(selection: Any, row_count: int) -> list[int]:
    value = selection
    if hasattr(value, "selection"): value = getattr(value, "selection")
    if hasattr(value, "to_dict"):
        try: value = value.to_dict()
        except Exception: pass
    if not isinstance(value, Mapping): return []
    if isinstance(value.get("selection"), Mapping): value = value["selection"]
    points = value.get("points") or []; indices: list[int] = []
    if isinstance(points, Sequence) and not isinstance(points, (str, bytes)):
        for point in points:
            if not isinstance(point, Mapping): continue
            candidate = point.get("point_index", point.get("pointNumber", point.get("point_number")))
            try: idx = int(candidate)
            except (TypeError, ValueError): continue
            if 0 <= idx < int(row_count) and idx not in indices: indices.append(idx)
    return indices


def dashboard_identity(title: str, panels: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    semantic = {"schema": DASHBOARD_SCHEMA, "title": str(title).strip(), "panels": [dict(p) for p in panels]}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest(); return f"dashboard-{digest[:20]}", digest


def save_dashboard(project_path: Path, *, title: str, panels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not panels: raise ValueError("dashboard requires at least one panel")
    dashboard_id, digest = dashboard_identity(title, panels)
    record = {"schema": DASHBOARD_SCHEMA, "dashboard_id": dashboard_id, "sha256": digest, "title": str(title).strip() or "Visual Analytics Dashboard", "panels": [dict(p) for p in panels], "boundary": BOUNDARY}
    root = Path(project_path) / "reports" / "visual-analytics-dashboards"; root.mkdir(parents=True, exist_ok=True)
    path = root / f"{dashboard_id}.json"
    if not path.exists(): path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return {**record, "path": str(path)}


# Explicit scientific semantics -------------------------------------------------

def contract_field_metadata(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    contract = get_contract(result.get("schema")); return dict((contract or {}).get("fields") or {})


def field_metadata(result: Mapping[str, Any], field: str) -> dict[str, Any]:
    meta = contract_field_metadata(result).get(str(field))
    if not meta: return {"registered": False, "field": str(field), "unit": "", "quantity": None, "role": None}
    return {"registered": True, "field": str(field), "unit": str(meta.get("unit") or ""), "quantity": meta.get("quantity"), "role": meta.get("role"), "shape": meta.get("shape"), "description": meta.get("description") or ""}


def axis_label(field: str, unit: str | None = None) -> str:
    u = str(unit or "").strip(); return f"{field} [{u}]" if u else str(field)


def convertible_units(unit: str) -> list[str]:
    info = unit_info(unit)
    return list(supported_units().get(str(info.get("dimension")), [])) if info.get("known") else []


def unit_comparability(unit_a: str | None, unit_b: str | None) -> dict[str, Any]:
    a = str(unit_a or "").strip(); b = str(unit_b or "").strip()
    if not a or not b:
        return {"status": "UNSPECIFIED", "comparable": False, "convertible": False, "unit_a": a, "unit_b": b}
    if a == b:
        return {"status": "EXACT", "comparable": True, "convertible": False, "unit_a": a, "unit_b": b}
    if compatible(a, b):
        return {"status": "CONVERTIBLE", "comparable": True, "convertible": True, "unit_a": a, "unit_b": b}
    return {"status": "INCOMPATIBLE", "comparable": False, "convertible": False, "unit_a": a, "unit_b": b}


def convert_series(values: Sequence[Any], from_unit: str, to_unit: str) -> list[float | None]:
    if from_unit != to_unit and not compatible(from_unit, to_unit): raise ValueError(f"incompatible units: {from_unit!r} -> {to_unit!r}")
    out: list[float | None] = []
    for value in values:
        try: x = float(value)
        except Exception: out.append(None); continue
        if not math.isfinite(x): out.append(None)
        else: out.append(x if from_unit == to_unit else convert(x, from_unit, to_unit))
    return out


def uncertainty_records(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in find_uncertainty_objects(result):
        value = dict(item.get("value") or {}); validation = validate_uncertainty(value)
        rows.append({"path": item.get("path"), "valid": bool(validation.get("valid")), "errors": list(validation.get("errors") or []), "estimate": value.get("estimate"), "unit": value.get("unit") or "", "standard_uncertainty": value.get("standard_uncertainty"), "coverage_factor": value.get("coverage_factor"), "interval": value.get("interval"), "coverage_probability": value.get("coverage_probability"), "method": value.get("method"), "sha256": value.get("uncertainty_sha256")})
    return rows


def uncertainty_plot_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not record.get("valid"): raise ValueError("uncertainty object is not structurally valid")
    estimate = float(record.get("estimate")); unit = str(record.get("unit") or ""); su = record.get("standard_uncertainty"); interval = record.get("interval")
    if su is not None:
        err = float(su); return {"estimate": estimate, "unit": unit, "error_plus": err, "error_minus": err, "kind": "standard-uncertainty"}
    if isinstance(interval, Sequence) and len(interval) == 2:
        lo, hi = float(interval[0]), float(interval[1]); return {"estimate": estimate, "unit": unit, "error_plus": hi-estimate, "error_minus": estimate-lo, "kind": "interval"}
    return {"estimate": estimate, "unit": unit, "error_plus": None, "error_minus": None, "kind": "estimate-only"}


def local_sensitivity(frame: pd.DataFrame, parameter: str, output: str) -> pd.DataFrame:
    if parameter not in frame.columns or output not in frame.columns: raise ValueError("parameter/output field missing")
    work = pd.DataFrame({"x": _numeric(frame[parameter]), "y": _numeric(frame[output])}).replace([np.inf, -np.inf], np.nan).dropna()
    grouped = work.groupby("x", as_index=False)["y"].mean().sort_values("x")
    if len(grouped) < 2: raise ValueError("parameter must vary across at least two finite points")
    x = grouped["x"].to_numpy(dtype=float); y = grouped["y"].to_numpy(dtype=float); dx = np.diff(x)
    if np.any(dx == 0): raise ValueError("parameter values must be distinct")
    return pd.DataFrame({"parameter_center": (x[:-1]+x[1:])/2.0, "output_center": (y[:-1]+y[1:])/2.0, "sensitivity": np.diff(y)/dx, "delta_parameter": dx, "delta_output": np.diff(y)})


def elasticity_sensitivity(frame: pd.DataFrame, parameter: str, output: str) -> pd.DataFrame:
    local = local_sensitivity(frame, parameter, output).copy()
    xmid = pd.to_numeric(local["parameter_center"], errors="coerce")
    ymid = pd.to_numeric(local["output_center"], errors="coerce")
    slope = pd.to_numeric(local["sensitivity"], errors="coerce")
    valid = xmid.notna() & ymid.notna() & slope.notna() & (ymid.abs() > 0)
    local["elasticity"] = np.nan
    local.loc[valid, "elasticity"] = slope[valid] * xmid[valid] / ymid[valid]
    return local


def standardized_sensitivity(frame: pd.DataFrame, parameters: Sequence[str], output: str) -> pd.DataFrame:
    if output not in frame.columns: raise ValueError("output field missing")
    y_all = _numeric(frame[output]).replace([np.inf, -np.inf], np.nan); rows = []
    for parameter in parameters:
        if parameter not in frame.columns or parameter == output: continue
        x_all = _numeric(frame[parameter]).replace([np.inf, -np.inf], np.nan); mask = x_all.notna() & y_all.notna(); x = x_all[mask]; y = y_all[mask]
        if len(x) < 3 or float(x.std(ddof=0)) == 0 or float(y.std(ddof=0)) == 0: continue
        zx = (x-x.mean())/x.std(ddof=0); zy = (y-y.mean())/y.std(ddof=0); slope = float((zx*zy).mean()); spearman = float(x.rank().corr(y.rank(), method="pearson"))
        rows.append({"parameter": parameter, "standardized_slope": slope, "abs_standardized_slope": abs(slope), "spearman": spearman, "n": int(len(x))})
    out = pd.DataFrame(rows); return out.sort_values("abs_standardized_slope", ascending=False).reset_index(drop=True) if not out.empty else out


def response_surface(frame: pd.DataFrame, x: str, y: str, z: str, *, agg: str = "mean") -> dict[str, Any]:
    if any(name not in frame.columns for name in (x, y, z)): raise ValueError("response-surface field missing")
    work = pd.DataFrame({x: _numeric(frame[x]), y: _numeric(frame[y]), z: _numeric(frame[z])}).replace([np.inf, -np.inf], np.nan).dropna()
    if work.empty or work[x].nunique() < 2 or work[y].nunique() < 2: raise ValueError("response surface needs finite data and at least two unique values on both axes")
    if agg not in {"mean", "median", "min", "max"}: raise ValueError("unsupported response-surface aggregation")
    pivot = work.pivot_table(index=y, columns=x, values=z, aggfunc=agg); arr = pivot.to_numpy(dtype=float)
    return {"x": [float(v) for v in pivot.columns], "y": [float(v) for v in pivot.index], "z": arr.tolist(), "rows": int(len(work)), "coverage": int(np.isfinite(arr).sum()), "grid_cells": int(arr.shape[0]*arr.shape[1]), "aggregation": agg}


def response_surface_slice(surface: Mapping[str, Any], *, axis: str, index: int) -> pd.DataFrame:
    x = list(surface.get("x") or []); y = list(surface.get("y") or []); z = np.asarray(surface.get("z") or [], dtype=float)
    if z.ndim != 2 or z.shape != (len(y), len(x)): raise ValueError("invalid response-surface shape")
    if axis == "x":
        if not 0 <= index < len(x): raise ValueError("x slice index out of range")
        return pd.DataFrame({"coordinate": y, "response": z[:, index], "fixed_axis": "x", "fixed_value": x[index]})
    if axis == "y":
        if not 0 <= index < len(y): raise ValueError("y slice index out of range")
        return pd.DataFrame({"coordinate": x, "response": z[index, :], "fixed_axis": "y", "fixed_value": y[index]})
    raise ValueError("slice axis must be 'x' or 'y'")


def science_analysis_identity(source_identity: Mapping[str, Any], analysis: Mapping[str, Any]) -> tuple[str, str]:
    semantic = {"schema": SCIENCE_RECIPE_SCHEMA, "source": dict(source_identity), "analysis": dict(analysis)}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"science-{digest[:20]}", digest


def save_science_analysis_recipe(project_path: Path, *, source_identity: Mapping[str, Any], analysis: Mapping[str, Any]) -> dict[str, Any]:
    recipe_id, digest = science_analysis_identity(source_identity, analysis)
    record = {"schema": SCIENCE_RECIPE_SCHEMA, "recipe_id": recipe_id, "sha256": digest, "source": dict(source_identity), "analysis": dict(analysis), "boundary": BOUNDARY}
    root = Path(project_path) / "reports" / "science-analysis-recipes"; root.mkdir(parents=True, exist_ok=True)
    path = root / f"{recipe_id}.json"
    if not path.exists(): path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return {**record, "path": str(path)}
