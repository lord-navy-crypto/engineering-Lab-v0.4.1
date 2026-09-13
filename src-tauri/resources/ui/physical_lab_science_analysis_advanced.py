"""Advanced, explicit science-analysis helpers for Engineering Lab.

This module never turns descriptive statistics into validation or causality. It
provides robust screening summaries, unit-aware comparison contracts and portable
analysis summaries over already-existing evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from physical_lab_units import compatible, convert
from physical_lab_visual_analytics import elasticity_sensitivity, local_sensitivity, standardized_sensitivity

SUMMARY_SCHEMA = "engineering-lab-science-analysis-summary-v1"
COMPARISON_SCHEMA = "engineering-lab-unit-aware-comparison-v1"
BOUNDARY = (
    "Advanced science analysis is descriptive screening over existing evidence. "
    "Agreement, ranking, sensitivity, unit conversion and summary artifacts do not establish causality, validation, calibration equivalence, uncertainty completeness or physical correctness."
)


def _finite(series: pd.Series) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return out.dropna()


def robust_sensitivity_summary(frame: pd.DataFrame, parameters: Sequence[str], output: str) -> pd.DataFrame:
    """Combine complementary descriptive sensitivity views without inventing one score."""
    standardized = standardized_sensitivity(frame, parameters, output)
    by_parameter = {str(row["parameter"]): dict(row) for row in standardized.to_dict("records")}
    rows: list[dict[str, Any]] = []
    for parameter in parameters:
        if parameter not in frame.columns or parameter == output:
            continue
        row = {"parameter": str(parameter)}
        row.update(by_parameter.get(str(parameter), {}))
        try:
            local = local_sensitivity(frame, parameter, output)
            slopes = _finite(local["sensitivity"])
            if not slopes.empty:
                signs = np.sign(slopes.to_numpy(dtype=float))
                nonzero = signs[signs != 0]
                row["median_local_slope"] = float(slopes.median())
                row["local_slope_iqr"] = float(slopes.quantile(0.75) - slopes.quantile(0.25))
                row["local_sign_consistency"] = float(abs(nonzero.mean())) if len(nonzero) else 0.0
                row["local_segments"] = int(len(slopes))
        except Exception:
            pass
        try:
            elasticity = elasticity_sensitivity(frame, parameter, output)
            values = _finite(elasticity["elasticity"])
            if not values.empty:
                row["median_elasticity"] = float(values.median())
                row["median_abs_elasticity"] = float(values.abs().median())
        except Exception:
            pass
        if len(row) > 1:
            slope = row.get("standardized_slope")
            rho = row.get("spearman")
            if slope is not None and rho is not None and math.isfinite(float(slope)) and math.isfinite(float(rho)):
                row["direction_agreement"] = bool(float(slope) == 0 or float(rho) == 0 or math.copysign(1.0, float(slope)) == math.copysign(1.0, float(rho)))
            rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty and "abs_standardized_slope" in out.columns:
        out = out.sort_values("abs_standardized_slope", ascending=False, na_position="last")
    return out.reset_index(drop=True)


def unit_aware_comparison_contract(sources: Sequence[Mapping[str, Any]], *, target_unit: str | None = None) -> dict[str, Any]:
    """Describe whether values from multiple sources may be placed on one physical axis."""
    if len(sources) < 2:
        raise ValueError("comparison requires at least two sources")
    units = [str(source.get("unit") or "").strip() for source in sources]
    if any(not unit for unit in units):
        return {"schema": COMPARISON_SCHEMA, "status": "UNSPECIFIED", "comparable": False, "target_unit": None, "sources": [dict(s) for s in sources], "boundary": BOUNDARY}
    reference = str(target_unit or units[0]).strip()
    if not reference:
        raise ValueError("target unit must be explicit")
    incompatible = [unit for unit in units if unit != reference and not compatible(unit, reference)]
    if incompatible:
        return {"schema": COMPARISON_SCHEMA, "status": "INCOMPATIBLE", "comparable": False, "target_unit": reference, "sources": [dict(s) for s in sources], "boundary": BOUNDARY}
    status = "EXACT" if all(unit == reference for unit in units) else "CONVERTIBLE"
    return {"schema": COMPARISON_SCHEMA, "status": status, "comparable": True, "target_unit": reference, "sources": [dict(s) for s in sources], "boundary": BOUNDARY}


def convert_comparison_values(values: Sequence[Any], from_unit: str, target_unit: str) -> list[float | None]:
    if from_unit != target_unit and not compatible(from_unit, target_unit):
        raise ValueError(f"incompatible comparison units: {from_unit!r} -> {target_unit!r}")
    out: list[float | None] = []
    for value in values:
        try:
            numeric = float(value)
        except Exception:
            out.append(None)
            continue
        if not math.isfinite(numeric):
            out.append(None)
        else:
            out.append(numeric if from_unit == target_unit else float(convert(numeric, from_unit, target_unit)))
    return out


def summary_identity(title: str, source_identity: Mapping[str, Any], analyses: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    stable = {"schema": SUMMARY_SCHEMA, "title": str(title).strip(), "source": dict(source_identity), "analyses": [dict(a) for a in analyses]}
    raw = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"science-summary-{digest[:20]}", digest


def save_analysis_summary(project_path: str | Path, *, title: str, source_identity: Mapping[str, Any], analyses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not analyses:
        raise ValueError("science analysis summary requires at least one analysis")
    summary_id, digest = summary_identity(title, source_identity, analyses)
    record = {"schema": SUMMARY_SCHEMA, "summary_id": summary_id, "sha256": digest, "title": str(title).strip() or "Science Analysis Summary", "source": dict(source_identity), "analyses": [dict(a) for a in analyses], "boundary": BOUNDARY}
    root = Path(project_path) / "reports" / "science-analysis-summaries"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{summary_id}.json"
    md_path = root / f"{summary_id}.md"
    if not json_path.exists():
        json_path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    if not md_path.exists():
        lines = [f"# {record['title']}", "", f"Summary ID: `{summary_id}`", f"SHA-256: `{digest}`", "", "## Analyses"]
        for i, analysis in enumerate(record["analyses"], start=1):
            lines.extend(["", f"### {i}. {analysis.get('kind', 'analysis')}", "", "```json", json.dumps(analysis, indent=2, sort_keys=True, ensure_ascii=False), "```"])
        lines.extend(["", "## Scientific boundary", "", BOUNDARY, ""])
        md_path.write_text("\n".join(lines), encoding="utf-8")
    return {**record, "json_path": str(json_path), "markdown_path": str(md_path)}
