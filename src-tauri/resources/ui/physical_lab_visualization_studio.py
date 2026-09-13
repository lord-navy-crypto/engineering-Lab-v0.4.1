"""Model-agnostic visualization and DIY scan helpers for Engineering Lab.

This layer changes representation, not evidence. It never evaluates arbitrary
expressions and never infers physical meaning, units, uncertainty, validation,
or causality from numeric arrays.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

MAX_VISUAL_ROWS = 200_000
MAX_SCAN_POINTS = 500
MODEL_SPEC_SCHEMA = "physical-lab-model-spec-v1"
BOUNDARY = (
    "Visualization changes representation, not evidence. Axis selection, filtering, normalization, "
    "aggregation and plotting do not create physical meaning, uncertainty, validation, or causality."
)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def numeric_inventory(value: Any, path: str = "$") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scalar = _number(value)
    if scalar is not None:
        return [{"path": path, "kind": "scalar", "shape": [], "size": 1, "values": [scalar]}]
    if isinstance(value, np.ndarray):
        try:
            arr = np.asarray(value)
            if arr.size and arr.dtype.kind in "iuf" and np.isfinite(arr.astype(float)).all():
                if arr.ndim == 1:
                    return [{"path": path, "kind": "vector", "shape": list(arr.shape), "size": int(arr.size), "values": arr.astype(float).tolist()}]
                if arr.ndim == 2:
                    return [{"path": path, "kind": "matrix", "shape": list(arr.shape), "size": int(arr.size), "values": arr.astype(float).tolist()}]
        except Exception:
            return rows
    if isinstance(value, Mapping):
        for key, child in value.items():
            rows.extend(numeric_inventory(child, f"{path}.{key}" if path != "$" else f"$.{key}"))
        return rows
    if isinstance(value, (list, tuple)):
        try:
            arr = np.asarray(value)
            if arr.size and arr.dtype.kind in "iuf" and np.isfinite(arr.astype(float)).all():
                if arr.ndim == 1:
                    return [{"path": path, "kind": "vector", "shape": list(arr.shape), "size": int(arr.size), "values": arr.astype(float).tolist()}]
                if arr.ndim == 2:
                    return [{"path": path, "kind": "matrix", "shape": list(arr.shape), "size": int(arr.size), "values": arr.astype(float).tolist()}]
        except Exception:
            pass
        for index, child in enumerate(value):
            rows.extend(numeric_inventory(child, f"{path}[{index}]"))
    return rows


def _path_get(root: Any, path: str) -> Any:
    if path == "$":
        return root
    if not path.startswith("$."):
        raise ValueError("path must begin with $.")
    current = root
    token = ""
    i = 2
    while i <= len(path):
        ch = path[i] if i < len(path) else "."
        if ch == ".":
            if token:
                current = current[token]
                token = ""
            i += 1
        elif ch == "[":
            if token:
                current = current[token]
                token = ""
            end = path.find("]", i)
            if end < 0:
                raise ValueError(path)
            current = current[int(path[i + 1:end])]
            i = end + 1
        else:
            token += ch
            i += 1
    return current


def result_frame(result: Mapping[str, Any]) -> pd.DataFrame:
    inventory = numeric_inventory(result)
    vectors = [row for row in inventory if row["kind"] == "vector"]
    scalars = [row for row in inventory if row["kind"] == "scalar"]
    n = min(max([int(row["size"]) for row in vectors] or [1]), MAX_VISUAL_ROWS)
    data: dict[str, list[float | int]] = {"index": list(range(n))}
    for row in vectors:
        values = list(row["values"])
        if len(values) == n:
            data[str(row["path"])] = values
    for row in scalars:
        data[str(row["path"])] = [float(row["values"][0])] * n
    return pd.DataFrame(data)


def matrix_by_path(result: Mapping[str, Any], path: str) -> np.ndarray:
    arr = np.asarray(_path_get(result, path), dtype=float)
    if arr.ndim != 2 or not np.isfinite(arr).all():
        raise ValueError("selected field is not a finite numeric matrix")
    return arr


def dataset_frame(dataset: Mapping[str, Any]) -> pd.DataFrame:
    columns = dataset.get("columns") or {}
    if not isinstance(columns, Mapping):
        return pd.DataFrame()
    valid = {str(k): list(v) for k, v in columns.items() if isinstance(v, (list, tuple))}
    if not valid:
        return pd.DataFrame()
    n = min(min(map(len, valid.values())), MAX_VISUAL_ROWS)
    return pd.DataFrame({k: v[:n] for k, v in valid.items()})


def research_table_frame(parsed: Mapping[str, Any]) -> pd.DataFrame:
    columns = parsed.get("column_data") or {}
    if not isinstance(columns, Mapping):
        return pd.DataFrame()
    valid = {str(k): list(v) for k, v in columns.items() if isinstance(v, (list, tuple))}
    if not valid:
        return pd.DataFrame()
    n = min(min(map(len, valid.values())), MAX_VISUAL_ROWS)
    return pd.DataFrame({k: v[:n] for k, v in valid.items()})


def sweep_frame(sweep_result: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for point in list(sweep_result.get("points") or []):
        if not isinstance(point, Mapping) or point.get("status") != "succeeded":
            continue
        row: dict[str, Any] = {"design_index": point.get("design_index")}
        metadata = point.get("design_metadata") or {}
        if isinstance(metadata, Mapping):
            for key, value in metadata.items():
                key = str(key)
                if not key.startswith("__"):
                    continue
                if value is None or isinstance(value, (str, bool, int)):
                    row[key] = value
                elif isinstance(value, float) and math.isfinite(value):
                    row[key] = value
        design = point.get("parameters") or point.get("design") or point.get("inputs") or {}
        if isinstance(design, Mapping):
            for key, value in design.items():
                number = _number(value)
                if number is not None:
                    row[f"param:{key}"] = number
        metrics = point.get("metrics") or {}
        if isinstance(metrics, Mapping):
            for key, value in metrics.items():
                number = _number(value)
                if number is not None:
                    row[f"metric:{key}"] = number
        result = point.get("result") or {}
        if isinstance(result, Mapping):
            for item in numeric_inventory(result):
                if item["kind"] == "scalar":
                    row[f"result:{item['path']}"] = float(item["values"][0])
        rows.append(row)
    return pd.DataFrame(rows[:MAX_VISUAL_ROWS])


def numeric_columns(frame: pd.DataFrame) -> list[str]:
    out: list[str] = []
    for column in frame.columns:
        series = pd.to_numeric(frame[column], errors="coerce")
        if series.notna().any():
            out.append(str(column))
    return out


def transform(frame: pd.DataFrame, columns: Sequence[str], mode: str) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out.columns:
            continue
        series = pd.to_numeric(out[column], errors="coerce")
        if mode == "z-score":
            sd = float(series.std(ddof=0))
            out[column] = (series - float(series.mean())) / sd if sd > 0 else 0.0
        elif mode == "min-max":
            lo, hi = float(series.min()), float(series.max())
            out[column] = (series - lo) / (hi - lo) if hi > lo else 0.0
        elif mode == "absolute":
            out[column] = series.abs()
        else:
            out[column] = series
    return out


def summary(frame: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    rows = []
    for column in columns:
        if column not in frame.columns:
            continue
        s = pd.to_numeric(frame[column], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append({"field": column, "count": int(s.size), "min": float(s.min()), "max": float(s.max()), "mean": float(s.mean()), "median": float(s.median()), "std": float(s.std(ddof=0))})
    return rows


def model_spec_guidance(spec: Mapping[str, Any]) -> dict[str, Any]:
    if spec.get("schema") != MODEL_SPEC_SCHEMA:
        raise ValueError(f"ModelSpec schema must be {MODEL_SPEC_SCHEMA}")
    params = spec.get("parameters")
    outputs = spec.get("outputs")
    if not isinstance(params, list) or not isinstance(outputs, list):
        raise ValueError("ModelSpec must provide parameter and output lists")
    parameters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in params[:200]:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        if not name or name in seen or name.startswith("*"):
            continue
        seen.add(name)
        parameters.append({
            "name": name,
            "label": str(row.get("label") or name),
            "unit": row.get("unit"),
            "control": row.get("control"),
            "default": _number(row.get("default")),
            "min": _number(row.get("min")),
            "max": _number(row.get("max")),
            "required": bool(row.get("required")),
        })
    clean_outputs = []
    for row in outputs[:200]:
        if isinstance(row, Mapping) and str(row.get("name") or "").strip():
            clean_outputs.append({"name": str(row.get("name")), "label": str(row.get("label") or row.get("name")), "kind": str(row.get("kind") or "auto")})
    visualizations = []
    for row in list(spec.get("visualizations") or [])[:100]:
        if isinstance(row, Mapping):
            visualizations.append({str(k): v for k, v in row.items() if k in {"kind", "title", "outputs", "x", "y", "z"}})
    metadata = spec.get("metadata") if isinstance(spec.get("metadata"), Mapping) else {}
    return {
        "schema": MODEL_SPEC_SCHEMA,
        "name": str(metadata.get("name") or "Research model"),
        "description": str(metadata.get("description") or ""),
        "parameters": parameters,
        "outputs": clean_outputs,
        "visualizations": visualizations,
        "boundary": "ModelSpec guides controls and visualization hints only; it does not grant execution authority.",
    }


def scan_parameter_compatibility(guidance: Mapping[str, Any], accepted_parameters: Sequence[str]) -> list[dict[str, Any]]:
    accepted = {str(name) for name in accepted_parameters}
    rows = []
    for param in list(guidance.get("parameters") or []):
        if isinstance(param, Mapping):
            rows.append({**dict(param), "adapter_compatible": str(param.get("name")) in accepted})
    return rows


def axis_values(start: float, stop: float, count: int, spacing: str) -> list[float]:
    count = int(count)
    if count < 1 or count > MAX_SCAN_POINTS:
        raise ValueError(f"scan axis count must be 1..{MAX_SCAN_POINTS}")
    if not math.isfinite(float(start)) or not math.isfinite(float(stop)):
        raise ValueError("scan bounds must be finite")
    if spacing == "log":
        if start <= 0 or stop <= 0:
            raise ValueError("log scan bounds must be positive")
        return np.geomspace(float(start), float(stop), count).astype(float).tolist()
    return np.linspace(float(start), float(stop), count).astype(float).tolist()


def build_scan_design(*, parameter_a: str, values_a: Sequence[float], fixed: Mapping[str, float] | None = None, parameter_b: str | None = None, values_b: Sequence[float] | None = None) -> list[dict[str, float | int]]:
    parameter_a = str(parameter_a).strip()
    parameter_b = str(parameter_b or "").strip()
    if not parameter_a:
        raise ValueError("parameter A name is required")
    if parameter_b and parameter_b == parameter_a:
        raise ValueError("parameter names must differ")
    fixed_values: dict[str, float] = {}
    for key, value in dict(fixed or {}).items():
        number = _number(value)
        if number is None:
            raise ValueError(f"fixed parameter {key!r} must be finite numeric")
        fixed_values[str(key)] = number
    if parameter_a in fixed_values or (parameter_b and parameter_b in fixed_values):
        raise ValueError("a scanned parameter cannot also be fixed")
    b_values = list(values_b or []) if parameter_b else [None]
    total = len(values_a) * len(b_values)
    if total < 1 or total > MAX_SCAN_POINTS:
        raise ValueError(f"DIY scan must contain 1..{MAX_SCAN_POINTS} points")
    rows: list[dict[str, float | int]] = []
    for index, (a, b) in enumerate((a, b) for a in values_a for b in b_values):
        row: dict[str, float | int] = {**fixed_values, parameter_a: float(a), "design_index": index}
        if parameter_b and b is not None:
            row[parameter_b] = float(b)
        rows.append(row)
    return rows
