"""Unified result inspection, numerical sanity checks and explicit materialization.

Design goals are intentionally conservative:
- inspect arbitrary JSON-like scientific results without inventing domain meaning;
- separate numerical/structural sanity from validation and uncertainty claims;
- materialize selected result fields into canonical project datasets through
  explicit, auditable extraction rules;
- preserve PROV-inspired Entity/Activity derivation metadata for each extraction.

No arbitrary expressions or code execution are supported.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now
from physical_lab_project_interop import save_canonical_dataset

INSPECTION_SCHEMA = "physical-lab-result-inspection-v1"
SANITY_SCHEMA = "physical-lab-result-sanity-v1"
MATERIALIZATION_SCHEMA = "physical-lab-result-materialization-v1"
MAX_INVENTORY_FIELDS = 1200
MAX_SERIES_LENGTH = 200000
REDUCERS = ("series", "mean", "min", "max", "first", "last", "index")


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(value))[:100]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numeric_vector(value: Any) -> list[float | None] | None:
    if not isinstance(value, (list, tuple)):
        return None
    out: list[float | None] = []
    for item in value:
        if item is None:
            out.append(None)
        elif _is_number(item):
            x = float(item)
            out.append(x if math.isfinite(x) else None)
        else:
            return None
    return out


def _numeric_matrix(value: Any) -> list[list[float | None]] | None:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    rows: list[list[float | None]] = []
    width = None
    for row in value:
        vec = _numeric_vector(row)
        if vec is None:
            return None
        width = len(vec) if width is None else width
        if len(vec) != width:
            return None
        rows.append(vec)
    return rows


def _field_role(path: str) -> str:
    p = path.lower()
    uncertainty_tokens = (
        "uncertainty", "standard_error", "stderr", "std_error", "confidence_interval",
        "coverage_interval", "coverage_probability", "sigma",
    )
    quality_tokens = (
        "rmse", "mae", "residual", "error", "drift", "cfl", "condition",
        "r2", "deviation", "convergence", "relative_residual",
    )
    if any(token in p for token in uncertainty_tokens):
        return "uncertainty"
    if any(token in p for token in quality_tokens):
        return "numerical-quality"
    if p.endswith("boundary") or ".boundary" in p:
        return "scientific-boundary"
    return "observable"


def _summary_from_values(values: Sequence[float | None]) -> dict[str, Any]:
    finite = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    missing = len(values) - len(finite)
    if not finite:
        return {"count": len(values), "finite_count": 0, "missing_count": missing}
    mean = sum(finite) / len(finite)
    variance = sum((x - mean) ** 2 for x in finite) / max(len(finite) - 1, 1)
    return {
        "count": len(values),
        "finite_count": len(finite),
        "missing_count": missing,
        "min": min(finite),
        "max": max(finite),
        "mean": mean,
        "std": math.sqrt(max(variance, 0.0)),
    }


def classify_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "boolean"}
    if _is_number(value):
        x = float(value)
        return {"kind": "scalar", "finite": math.isfinite(x), "value": x if math.isfinite(x) else None}
    if isinstance(value, str):
        return {"kind": "text", "length": len(value)}
    vector = _numeric_vector(value)
    if vector is not None:
        return {"kind": "vector", **_summary_from_values(vector)}
    matrix = _numeric_matrix(value)
    if matrix is not None:
        flat = [x for row in matrix for x in row]
        return {"kind": "matrix", "rows": len(matrix), "columns": len(matrix[0]) if matrix else 0, **_summary_from_values(flat)}
    if isinstance(value, Mapping):
        return {"kind": "mapping", "size": len(value)}
    if isinstance(value, (list, tuple)):
        return {"kind": "sequence", "size": len(value)}
    return {"kind": type(value).__name__}


def _inventory(value: Any, prefix: str, rows: list[dict[str, Any]]) -> None:
    if len(rows) >= MAX_INVENTORY_FIELDS:
        return
    if isinstance(value, Mapping):
        if prefix:
            info = classify_value(value)
            rows.append({"path": prefix, "role": _field_role(prefix), **info})
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            _inventory(item, path, rows)
        return
    info = classify_value(value)
    rows.append({"path": prefix or "$", "role": _field_role(prefix), **info})


def inspect_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    inventory: list[dict[str, Any]] = []
    _inventory(result, "", inventory)
    counts: dict[str, int] = {}
    roles: dict[str, int] = {}
    for row in inventory:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
        roles[row["role"]] = roles.get(row["role"], 0) + 1
    stable = {
        "schema": INSPECTION_SCHEMA,
        "result_schema": result.get("schema"),
        "result_sha256": _sha(result),
        "field_count": len(inventory),
        "kind_counts": counts,
        "role_counts": roles,
        "inventory": inventory,
    }
    return {
        **stable,
        "inspection_sha256": _sha(stable),
        "boundary": "Structural result inspection only. Field names and numeric summaries do not establish physical validity, experimental agreement, or uncertainty coverage.",
    }


def resolve_path(result: Mapping[str, Any], path: str) -> Any:
    current: Any = result
    for token in str(path).split("."):
        if not token:
            continue
        if not isinstance(current, Mapping) or token not in current:
            raise KeyError(f"result path not found: {path}")
        current = current[token]
    return current


def _finite_flat(value: Any) -> list[float]:
    if _is_number(value):
        x = float(value)
        return [x] if math.isfinite(x) else []
    vector = _numeric_vector(value)
    if vector is not None:
        return [float(x) for x in vector if x is not None]
    matrix = _numeric_matrix(value)
    if matrix is not None:
        return [float(x) for row in matrix for x in row if x is not None]
    return []


def _add_check(checks: list[dict[str, Any]], severity: str, code: str, message: str, *, path: str = "") -> None:
    checks.append({"severity": severity, "code": code, "path": path, "message": message})


def numerical_sanity_report(result: Mapping[str, Any]) -> dict[str, Any]:
    inspection = inspect_result(result)
    checks: list[dict[str, Any]] = []
    schema = str(result.get("schema") or "")
    if not schema:
        _add_check(checks, "review", "MISSING_SCHEMA", "Result has no explicit schema identifier.")
    if not str(result.get("boundary") or "").strip():
        _add_check(checks, "review", "MISSING_BOUNDARY", "Result does not state a scientific/interpretive boundary.")

    for row in inspection["inventory"]:
        if row.get("kind") in {"vector", "matrix"} and int(row.get("missing_count") or 0) > 0:
            _add_check(checks, "review", "MISSING_NUMERIC_VALUES", f"Numeric array contains {row['missing_count']} missing/non-finite value(s).", path=str(row["path"]))
        if row.get("role") == "uncertainty" and row.get("kind") in {"scalar", "vector", "matrix"}:
            vals = _finite_flat(resolve_path(result, str(row["path"])))
            if vals and min(vals) < 0:
                _add_check(checks, "fail", "NEGATIVE_UNCERTAINTY", "Uncertainty-like quantity contains a negative value.", path=str(row["path"]))

    bounded_tokens = ("probability", "coherence", "returned_fraction", "pass_fraction", "coverage_probability")
    for row in inspection["inventory"]:
        p = str(row["path"]).lower()
        if not any(token in p for token in bounded_tokens):
            continue
        vals = _finite_flat(resolve_path(result, str(row["path"])))
        if vals and (min(vals) < -1e-12 or max(vals) > 1.0 + 1e-12):
            _add_check(checks, "fail", "OUT_OF_UNIT_INTERVAL", "Probability/coherence/fraction quantity lies outside [0,1].", path=str(row["path"]))

    # Schema-specific numerical expectations. These are solver sanity checks, not validation.
    if schema == "physical-lab-wave-fd-v1":
        cfl = float(result.get("cfl") or 0.0)
        if not (0.0 < cfl <= 1.0 + 1e-12):
            _add_check(checks, "fail", "WAVE_CFL", f"Explicit wave solver CFL={cfl:.6g} is outside (0,1].", path="cfl")
    if schema == "physical-lab-poisson-fd-v1":
        rr = result.get("relative_residual")
        if _is_number(rr) and float(rr) < 0:
            _add_check(checks, "fail", "NEGATIVE_RESIDUAL", "Relative residual cannot be negative.", path="relative_residual")
    if schema == "physical-lab-lqr-kalman-v1":
        eig = _finite_flat(result.get("closed_loop_eigenvalues_real"))
        if eig and max(eig) >= 0:
            _add_check(checks, "fail", "CLOSED_LOOP_UNSTABLE", "Closed-loop eigenvalue has non-negative real part.", path="closed_loop_eigenvalues_real")

    for key in ("l2_error", "max_error", "rmse", "mae", "relative_residual", "control_rms", "position_estimation_rmse", "velocity_estimation_rmse"):
        if key in result and _is_number(result[key]) and float(result[key]) < 0:
            _add_check(checks, "fail", "NEGATIVE_ERROR_METRIC", f"{key} is negative.", path=key)

    severities = [row["severity"] for row in checks]
    status = "FAIL" if "fail" in severities else ("REVIEW" if "review" in severities else "PASS")
    stable = {
        "schema": SANITY_SCHEMA,
        "result_sha256": inspection["result_sha256"],
        "result_schema": schema or None,
        "status": status,
        "checks": checks,
    }
    return {
        **stable,
        "sanity_sha256": _sha(stable),
        "boundary": "Numerical/structural sanity only. PASS is not model validation, experimental validation, certification, or a statement that reported uncertainty is complete.",
    }


def extract_numeric(value: Any, reducer: str, *, index: int = 0) -> list[float | None]:
    mode = str(reducer).lower()
    if mode not in REDUCERS:
        raise ValueError(f"unsupported result reducer: {reducer}")
    if _is_number(value):
        x = float(value)
        if not math.isfinite(x):
            raise ValueError("selected scalar result is non-finite")
        return [x]
    vector = _numeric_vector(value)
    matrix = _numeric_matrix(value)
    if mode == "series":
        if vector is None:
            raise ValueError("series reducer requires a one-dimensional numeric vector")
        if len(vector) > MAX_SERIES_LENGTH:
            raise ValueError("selected series exceeds materialization row limit")
        return list(vector)
    vals = _finite_flat(value)
    if not vals:
        raise ValueError("selected result field has no finite numeric values")
    if mode == "mean": return [sum(vals) / len(vals)]
    if mode == "min": return [min(vals)]
    if mode == "max": return [max(vals)]
    if mode == "first": return [vals[0]]
    if mode == "last": return [vals[-1]]
    if mode == "index":
        idx = int(index)
        if idx < 0: idx += len(vals)
        if not 0 <= idx < len(vals):
            raise ValueError("result index out of range")
        return [vals[idx]]
    # A scalar with series was handled above; matrices must be reduced.
    raise ValueError("unsupported extraction combination")


def materialize_result(
    project_dir: str | Path,
    *,
    result: Mapping[str, Any],
    source_identity: Mapping[str, Any],
    name: str,
    profile: str,
    rules: Sequence[Mapping[str, Any]],
    notes: str = "",
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    if not 1 <= len(rules) <= 24:
        raise ValueError("materialization requires 1..24 extraction rules")
    result_sha = _sha(result)
    outputs: dict[str, list[float | None]] = {}
    normalized_rules = []
    for rule in rules:
        source_path = str(rule.get("path") or "").strip()
        column = str(rule.get("column_name") or source_path.split(".")[-1] or "value").strip()
        if not source_path or not column:
            raise ValueError("each extraction rule requires path and column_name")
        if column in outputs:
            raise ValueError("materialized column names must be unique")
        reducer = str(rule.get("reducer") or "series")
        index = int(rule.get("index") or 0)
        values = extract_numeric(resolve_path(result, source_path), reducer, index=index)
        outputs[column] = values
        normalized_rules.append({
            "path": source_path,
            "column_name": column,
            "reducer": reducer,
            "index": index if reducer == "index" else None,
            "unit": str(rule.get("unit") or ""),
        })

    lengths = [len(v) for v in outputs.values()]
    row_count = max(lengths)
    for key, values in list(outputs.items()):
        if len(values) == row_count:
            continue
        if len(values) == 1:
            outputs[key] = values * row_count
        else:
            raise ValueError("series extraction lengths disagree; only scalar-to-series broadcasting is allowed")
    units = {row["column_name"]: row["unit"] for row in normalized_rules if row["unit"]}
    dataset = save_canonical_dataset(
        path,
        name=name,
        profile=profile,
        columns=outputs,
        units=units,
        source=f"result:{source_identity.get('id') or result_sha[:16]}",
        notes=notes,
    )

    source_entity_id = str(source_identity.get("id") or f"result-{result_sha[:20]}")
    stable = {
        "schema": MATERIALIZATION_SCHEMA,
        "project_id": project.get("project_id"),
        "source_entity": {
            "id": source_entity_id,
            "kind": str(source_identity.get("kind") or "result"),
            "sha256": str(source_identity.get("sha256") or result_sha),
            "result_schema": result.get("schema"),
        },
        "activity": {
            "type": "result-extraction",
            "rules": normalized_rules,
            "software_agent": "Physical Lab Result Materializer",
        },
        "generated_entity": {
            "id": dataset["dataset_id"],
            "kind": "canonical-dataset",
            "sha256": dataset["sha256"],
        },
        "relations": {
            "used": [source_entity_id],
            "wasGeneratedBy": {dataset["dataset_id"]: "result-extraction"},
            "wasDerivedFrom": {dataset["dataset_id"]: source_entity_id},
            "wasAssociatedWith": {"result-extraction": "Physical Lab Result Materializer"},
        },
    }
    digest = _sha(stable)
    record = {
        **stable,
        "materialization_id": f"materialization-{digest[:20]}",
        "sha256": digest,
        "created_at": utc_now(),
        "boundary": "PROV-inspired extraction record. Derivation records data lineage only; it does not establish scientific validity or uncertainty completeness.",
    }
    target_dir = path / "provenance" / "materializations"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{record['materialization_id']}.json"
    target.write_text(json.dumps(plain(record), indent=2, sort_keys=True), encoding="utf-8")
    return {"dataset": dataset, "provenance": record}


def list_materializations(project_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    root = path / "provenance" / "materializations"
    if not root.exists():
        return []
    rows = []
    for file in sorted(root.glob("*.json")):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("schema") == MATERIALIZATION_SCHEMA:
            rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda x: (str(x.get("created_at") or ""), str(x.get("materialization_id") or "")), reverse=True)
    return rows


def _resolve_portable_path(reference: str) -> Path:
    p = Path(str(reference)).expanduser()
    if p.is_absolute():
        return p
    root = os.environ.get("PHYSICAL_LAB_DATA_DIR", "").strip()
    return (Path(root).expanduser().resolve() / p) if root else p


def load_project_result(project_dir: str | Path, job_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    doc = projects.open_project(project_dir)
    entry = (doc.get("results") or {}).get(str(job_id))
    if not isinstance(entry, Mapping):
        raise KeyError(f"project result not found: {job_id}")
    result_path = _resolve_portable_path(str(entry.get("result_path") or ""))
    value = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("project result must be a JSON object")
    identity = {
        "id": f"project-result:{job_id}",
        "kind": "project-compute-result",
        "sha256": str(entry.get("result_sha256") or _sha(value)),
        "job_id": str(job_id),
    }
    return value, identity


def load_sweep_point(job_id: str, point_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    from physical_lab_sweep_executor import read_sweep_result
    result = read_sweep_result(str(job_id))
    if not result:
        raise KeyError(f"sweep result not found: {job_id}")
    points = list(result.get("points") or [])
    idx = int(point_index)
    if not 0 <= idx < len(points):
        raise IndexError("sweep point index out of range")
    point = points[idx]
    payload = point.get("result") if isinstance(point, Mapping) else None
    if not isinstance(payload, Mapping):
        raise ValueError("selected sweep point has no successful full result payload")
    payload = dict(payload)
    point_sha = _sha(payload)
    identity = {
        "id": f"sweep-result:{job_id}:{idx}",
        "kind": "sweep-point-result",
        "sha256": point_sha,
        "job_id": str(job_id),
        "point_index": idx,
        "adapter": result.get("adapter"),
    }
    return payload, identity
