"""Scientific visual-analytics helpers for Engineering Lab.

This module adds representation and interaction only. Error bars are displayed from
explicit user-selected numeric fields; no uncertainty semantics are inferred as
scientific truth. Multi-source overlays preserve source identity and never merge
records into new evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

DASHBOARD_SCHEMA = "engineering-lab-visual-analytics-dashboard-v1"
BOUNDARY = (
    "Visual analytics changes representation and selection, not evidence. Error bars only visualize "
    "explicit selected fields; overlays do not establish comparability, validation, uncertainty semantics, or causality."
)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def common_numeric_columns(frames: Sequence[pd.DataFrame]) -> list[str]:
    """Return numeric column names present with at least one finite value in every frame."""
    if not frames:
        return []
    common = set(str(c) for c in frames[0].columns)
    for frame in frames[1:]:
        common &= {str(c) for c in frame.columns}
    out: list[str] = []
    for name in sorted(common):
        ok = True
        for frame in frames:
            s = _numeric(frame[name]).dropna()
            finite = s[s.map(lambda x: math.isfinite(float(x)))]
            if finite.empty:
                ok = False
                break
        if ok:
            out.append(name)
    return out


def uncertainty_candidates(columns: Sequence[str], y: str) -> dict[str, list[str]]:
    """Suggest, but never assign, uncertainty-like fields by conservative name matching."""
    y_text = str(y)
    base = y_text.split(":", 1)[-1].split(".")[-1].lstrip("$")
    lowered = {str(c).lower(): str(c) for c in columns}
    symmetric: list[str] = []
    lower: list[str] = []
    upper: list[str] = []
    for suffix in ("_sigma", "_std", "_stderr", "_error", "_err", ".sigma", ".std"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered:
                symmetric.append(lowered[candidate.lower()])
    for suffix in ("_lower", "_lo", "_min", ".lower", ".lo"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered:
                lower.append(lowered[candidate.lower()])
    for suffix in ("_upper", "_hi", "_max", ".upper", ".hi"):
        for candidate in (f"{base}{suffix}", f"{y_text}{suffix}"):
            if candidate.lower() in lowered:
                upper.append(lowered[candidate.lower()])
    return {
        "symmetric": list(dict.fromkeys(symmetric)),
        "lower": list(dict.fromkeys(lower)),
        "upper": list(dict.fromkeys(upper)),
    }


def uncertainty_error_arrays(
    frame: pd.DataFrame,
    y: str,
    *,
    symmetric: str | None = None,
    lower: str | None = None,
    upper: str | None = None,
) -> dict[str, list[float]]:
    """Build Plotly-compatible non-negative error arrays from explicit fields."""
    if y not in frame.columns:
        raise ValueError(f"Y field {y!r} is not present")
    yv = _numeric(frame[y])
    if symmetric:
        if symmetric not in frame.columns:
            raise ValueError(f"uncertainty field {symmetric!r} is not present")
        err = _numeric(frame[symmetric])
        if err.isna().any() or (err < 0).any():
            raise ValueError("symmetric uncertainty must be finite and non-negative")
        return {"array": [float(x) for x in err], "arrayminus": [float(x) for x in err]}
    if lower or upper:
        if not lower or not upper:
            raise ValueError("both lower and upper fields are required for asymmetric bounds")
        if lower not in frame.columns or upper not in frame.columns:
            raise ValueError("lower/upper uncertainty fields are not present")
        lo = _numeric(frame[lower]); hi = _numeric(frame[upper])
        if lo.isna().any() or hi.isna().any() or yv.isna().any():
            raise ValueError("Y and bound fields must be finite numeric values")
        minus = yv - lo
        plus = hi - yv
        if (minus < 0).any() or (plus < 0).any():
            raise ValueError("bounds must satisfy lower <= Y <= upper")
        return {"array": [float(x) for x in plus], "arrayminus": [float(x) for x in minus]}
    return {}


def overlay_frame(sources: Sequence[tuple[str, pd.DataFrame]], x: str, y: str) -> pd.DataFrame:
    """Create a long-form comparison table without changing source values."""
    rows: list[pd.DataFrame] = []
    for label, frame in sources:
        if x not in frame.columns or y not in frame.columns:
            continue
        part = pd.DataFrame({"x": _numeric(frame[x]), "y": _numeric(frame[y])})
        part["source"] = str(label)
        part["source_row"] = list(range(len(part)))
        part = part.dropna(subset=["x", "y"])
        rows.append(part)
    if not rows:
        return pd.DataFrame(columns=["x", "y", "source", "source_row"])
    return pd.concat(rows, ignore_index=True)


def selection_indices(selection: Any, row_count: int) -> list[int]:
    """Defensively decode Streamlit/Plotly selection state across supported versions."""
    value = selection
    if hasattr(value, "selection"):
        value = getattr(value, "selection")
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict()
        except Exception:
            pass
    if not isinstance(value, Mapping):
        return []
    if isinstance(value.get("selection"), Mapping):
        value = value["selection"]
    points = value.get("points") or []
    indices: list[int] = []
    if isinstance(points, Sequence) and not isinstance(points, (str, bytes)):
        for point in points:
            if not isinstance(point, Mapping):
                continue
            candidate = point.get("point_index", point.get("pointNumber", point.get("point_number")))
            try:
                idx = int(candidate)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < int(row_count) and idx not in indices:
                indices.append(idx)
    return indices


def dashboard_identity(title: str, panels: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    semantic = {"schema": DASHBOARD_SCHEMA, "title": str(title).strip(), "panels": [dict(p) for p in panels]}
    raw = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"dashboard-{digest[:20]}", digest


def save_dashboard(project_path: Path, *, title: str, panels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not panels:
        raise ValueError("dashboard requires at least one panel")
    dashboard_id, digest = dashboard_identity(title, panels)
    record = {
        "schema": DASHBOARD_SCHEMA,
        "dashboard_id": dashboard_id,
        "sha256": digest,
        "title": str(title).strip() or "Visual Analytics Dashboard",
        "panels": [dict(p) for p in panels],
        "boundary": BOUNDARY,
    }
    root = Path(project_path) / "reports" / "visual-analytics-dashboards"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{dashboard_id}.json"
    if not path.exists():
        path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return {**record, "path": str(path)}
