"""Reusable research-orchestration utilities for Physical Lab.

This module is deliberately profile-agnostic. It supplies common research plumbing
that can be reused by any model workspace:
- bounded Cartesian parameter-grid design generation;
- CSV/TSV numeric table parsing with missing/invalid accounting;
- convergence-order diagnostics from resolution/error pairs;
- baseline-relative comparison of numeric run metrics.

It does not execute arbitrary user code or infer model validity from numerical agreement.
"""
from __future__ import annotations

import csv
import io
import itertools
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

MAX_DESIGN_POINTS = 5000
MAX_TABLE_ROWS = 200000
MAX_TABLE_COLUMNS = 128


def _plain(v: Any) -> Any:
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return [_plain(x) for x in v.tolist()]
    if hasattr(v, "item"):
        try:
            return _plain(v.item())
        except Exception:
            pass
    return v


def parameter_axis(*, name: str, low: float, high: float, count: int, scale: str = "linear") -> dict[str, Any]:
    name = str(name).strip()
    if not name:
        raise ValueError("parameter name is required")
    lo, hi = float(low), float(high)
    n = int(count)
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        raise ValueError("parameter bounds must be finite with high >= low")
    if n < 1 or n > 101:
        raise ValueError("parameter count must be between 1 and 101")
    mode = str(scale).lower()
    if mode not in {"linear", "log"}:
        raise ValueError("scale must be linear or log")
    if mode == "log" and (lo <= 0 or hi <= 0):
        raise ValueError("log-scale bounds must be positive")
    if n == 1:
        values = np.asarray([lo], dtype=float)
    elif mode == "linear":
        values = np.linspace(lo, hi, n)
    else:
        values = np.geomspace(lo, hi, n)
    return {"name": name, "low": lo, "high": hi, "count": n, "scale": mode, "values": values.tolist()}


def cartesian_parameter_grid(axes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not axes:
        raise ValueError("at least one parameter axis is required")
    if len(axes) > 6:
        raise ValueError("at most six axes are supported in one bounded design")
    normalized = []
    names = set()
    total = 1
    for raw in axes:
        axis = parameter_axis(
            name=str(raw.get("name", "")), low=float(raw.get("low", 0.0)), high=float(raw.get("high", 0.0)),
            count=int(raw.get("count", 1)), scale=str(raw.get("scale", "linear")),
        )
        if axis["name"] in names:
            raise ValueError("parameter names must be unique")
        names.add(axis["name"])
        total *= int(axis["count"])
        if total > MAX_DESIGN_POINTS:
            raise ValueError(f"Cartesian design exceeds {MAX_DESIGN_POINTS} points")
        normalized.append(axis)
    rows = []
    for idx, combo in enumerate(itertools.product(*[a["values"] for a in normalized])):
        row = {"design_index": idx}
        row.update({a["name"]: float(v) for a, v in zip(normalized, combo)})
        rows.append(row)
    return _plain({
        "schema": "physical-lab-parameter-grid-v1",
        "axes": normalized,
        "point_count": len(rows),
        "rows": rows,
        "boundary": "Bounded Cartesian design only. Grid density does not imply uncertainty coverage, optimality, or statistical representativeness.",
    })


def parse_numeric_table(data: bytes, *, filename: str = "table.csv") -> dict[str, Any]:
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise ValueError("table data is empty")
    text = bytes(data).decode("utf-8-sig")
    delimiter = "\t" if str(filename).lower().endswith(".tsv") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("table has no header")
    header = [str(x).strip() for x in header[:MAX_TABLE_COLUMNS]]
    if not header or any(not x for x in header) or len(set(header)) != len(header):
        raise ValueError("table columns must be non-empty and unique")
    columns = {name: [] for name in header}
    raw_rows = 0
    truncated = False
    for row in reader:
        if raw_rows >= MAX_TABLE_ROWS:
            truncated = True
            break
        raw_rows += 1
        for j, name in enumerate(header):
            cell = row[j].strip() if j < len(row) else ""
            if cell == "":
                columns[name].append(None)
                continue
            try:
                val = float(cell)
                columns[name].append(val if math.isfinite(val) else None)
            except Exception:
                columns[name].append(None)
    summaries = []
    numeric_columns = []
    for name in header:
        vals = columns[name]
        finite = np.asarray([v for v in vals if v is not None], dtype=float)
        valid = int(finite.size)
        missing = len(vals) - valid
        if valid > 0:
            numeric_columns.append(name)
            summaries.append({
                "column": name, "valid_numeric": valid, "missing_or_non_numeric": missing,
                "min": float(np.min(finite)), "max": float(np.max(finite)),
                "mean": float(np.mean(finite)), "std": float(np.std(finite, ddof=1)) if valid > 1 else 0.0,
            })
        else:
            summaries.append({"column": name, "valid_numeric": 0, "missing_or_non_numeric": missing, "min": None, "max": None, "mean": None, "std": None})
    preview = []
    for i in range(min(raw_rows, 50)):
        preview.append({name: columns[name][i] for name in header})
    return _plain({
        "schema": "physical-lab-numeric-table-v1",
        "filename": str(filename), "delimiter": delimiter, "row_count": raw_rows,
        "columns": header, "numeric_columns": numeric_columns, "summaries": summaries,
        "preview": preview, "column_data": columns, "truncated": truncated,
        "boundary": "Numeric parser only. Missing/non-numeric cells are retained as null; no units, calibration, time-base validity, or experimental meaning are inferred.",
    })


def convergence_diagnostics(resolution: Sequence[float], error: Sequence[float]) -> dict[str, Any]:
    h = np.asarray(resolution, dtype=float)
    e = np.asarray(error, dtype=float)
    if h.ndim != 1 or e.ndim != 1 or h.size != e.size or h.size < 3:
        raise ValueError("resolution and error require at least three paired points")
    mask = np.isfinite(h) & np.isfinite(e) & (h > 0) & (e > 0)
    h, e = h[mask], e[mask]
    if h.size < 3:
        raise ValueError("at least three positive finite pairs are required")
    order_idx = np.argsort(h)[::-1]
    h, e = h[order_idx], e[order_idx]
    x, y = np.log(h), np.log(e)
    A = np.column_stack([np.ones_like(x), x])
    coeff, *_ = np.linalg.lstsq(A, y, rcond=None)
    intercept, p = float(coeff[0]), float(coeff[1])
    fit = A @ coeff
    ss_res = float(np.sum((y-fit)**2)); ss_tot = float(np.sum((y-np.mean(y))**2))
    r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else 1.0
    local_orders = []
    for i in range(len(h)-1):
        if h[i] != h[i+1] and e[i] != e[i+1]:
            local_orders.append(math.log(e[i]/e[i+1]) / math.log(h[i]/h[i+1]))
    return _plain({
        "schema": "physical-lab-convergence-v1", "resolution": h, "error": e,
        "observed_order": p, "loglog_r2": r2, "error_model_prefactor": math.exp(intercept),
        "local_orders": local_orders,
        "finest_resolution": float(h[-1]), "finest_error": float(e[-1]),
        "boundary": "Observed order is a finite-range log-log regression of supplied positive errors versus resolution. A high R² is not proof that the asymptotic regime has been reached.",
    })


def compare_numeric_runs(rows: Sequence[Mapping[str, Any]], *, baseline_index: int = 0) -> dict[str, Any]:
    if len(rows) < 2:
        raise ValueError("at least two runs are required")
    if not (0 <= int(baseline_index) < len(rows)):
        raise ValueError("baseline index out of range")
    base = rows[int(baseline_index)]
    shared = []
    for key in base.keys():
        try:
            b = float(base[key])
        except Exception:
            continue
        if not math.isfinite(b):
            continue
        ok = True
        for row in rows:
            try:
                v = float(row[key])
                ok = ok and math.isfinite(v)
            except Exception:
                ok = False
        if ok:
            shared.append(str(key))
    if not shared:
        raise ValueError("runs have no shared finite numeric metrics")
    out = []
    for i, row in enumerate(rows):
        record = {"run_index": i, "is_baseline": i == int(baseline_index)}
        for key in shared:
            b, v = float(base[key]), float(row[key])
            record[key] = v
            record[f"delta::{key}"] = v-b
            record[f"relative_delta::{key}"] = None if abs(b) <= 1e-30 else (v-b)/abs(b)
        out.append(record)
    return _plain({
        "schema": "physical-lab-run-comparison-v1", "baseline_index": int(baseline_index),
        "shared_metrics": shared, "rows": out,
        "boundary": "Arithmetic baseline comparison only. Relative deltas are undefined for zero baselines and do not imply statistical or practical significance.",
    })
