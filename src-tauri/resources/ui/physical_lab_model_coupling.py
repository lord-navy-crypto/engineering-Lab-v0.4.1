"""Auditable model-to-model coupling for Physical Lab.

A coupling pipeline maps canonical project-dataset columns into parameters of an
allow-listed sweep adapter. Mappings are intentionally bounded and transparent:
column reducer -> optional unit conversion -> affine scale/offset -> target parameter.
No arbitrary expressions, imports, or user code are executed.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import physical_lab_project_kernel as projects
import physical_lab_units as units
from physical_lab_experiment_kernel import plain, utc_now
from physical_lab_sweep_executor import ADAPTERS, create_sweep_job

PIPELINE_SCHEMA = "physical-lab-model-coupling-v1"
PACKET_SCHEMA = "physical-lab-parameter-packet-v1"
REDUCERS = ("mean", "min", "max", "first", "last", "row")
MAX_MAPPINGS = 16


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _pipeline_dir(project_dir: Path) -> Path:
    p = project_dir / "pipelines"
    p.mkdir(parents=True, exist_ok=True)
    return p


def adapter_catalog() -> list[dict[str, Any]]:
    rows = []
    for adapter_id, spec in sorted(ADAPTERS.items()):
        rows.append({
            "id": adapter_id,
            "label": str(spec.get("label") or adapter_id),
            "profiles": list(spec.get("profiles") or []),
            "module": str(spec.get("module") or ""),
            "function": str(spec.get("function") or ""),
        })
    return rows


def adapter_parameters(adapter_id: str) -> list[dict[str, Any]]:
    spec = ADAPTERS.get(str(adapter_id))
    if spec is None:
        raise ValueError("unknown coupling target adapter")
    import importlib
    module = importlib.import_module(str(spec["module"]))
    function = getattr(module, str(spec["function"]))
    signature = inspect.signature(function)
    rows = []
    for name, parameter in signature.parameters.items():
        if name == "self" or parameter.kind not in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}:
            continue
        default = None if parameter.default is inspect._empty else parameter.default
        rows.append({"name": name, "default": plain(default), "required": parameter.default is inspect._empty})
    return rows


def _finite_column(dataset: Mapping[str, Any], column: str) -> list[float]:
    columns = dataset.get("columns") or {}
    if column not in columns:
        raise ValueError(f"unknown source column: {column}")
    values = []
    for item in columns[column]:
        if item is None:
            continue
        try:
            x = float(item)
        except Exception:
            continue
        if math.isfinite(x):
            values.append(x)
    if not values:
        raise ValueError(f"source column has no finite values: {column}")
    return values


def reduce_column(dataset: Mapping[str, Any], column: str, reducer: str, *, row_index: int = 0) -> float:
    values = _finite_column(dataset, column)
    mode = str(reducer).lower()
    if mode not in REDUCERS:
        raise ValueError(f"unsupported reducer: {reducer}")
    if mode == "mean": return float(np.mean(values))
    if mode == "min": return float(np.min(values))
    if mode == "max": return float(np.max(values))
    if mode == "first": return float(values[0])
    if mode == "last": return float(values[-1])
    index = int(row_index)
    if index < 0: index += len(values)
    if not 0 <= index < len(values):
        raise ValueError("row reducer index out of range after missing values are removed")
    return float(values[index])


def apply_mapping(dataset: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
    column = str(mapping.get("source_column") or "")
    reducer = str(mapping.get("reducer") or "mean")
    raw = reduce_column(dataset, column, reducer, row_index=int(mapping.get("row_index") or 0))
    source_unit = str(mapping.get("source_unit") or (dataset.get("units") or {}).get(column) or "")
    target_unit = str(mapping.get("target_unit") or "")
    converted = raw
    conversion = None
    if source_unit or target_unit:
        if not source_unit or not target_unit:
            raise ValueError("unit conversion requires both source_unit and target_unit")
        converted = units.convert(raw, source_unit, target_unit)
        conversion = {"from": source_unit, "to": target_unit}
    scale = float(mapping.get("scale", 1.0)); offset = float(mapping.get("offset", 0.0))
    if not (math.isfinite(scale) and math.isfinite(offset)):
        raise ValueError("mapping scale and offset must be finite")
    value = scale * converted + offset
    if not math.isfinite(value):
        raise ValueError("mapped target value is non-finite")
    target_parameter = str(mapping.get("target_parameter") or "").strip()
    if not target_parameter:
        raise ValueError("target_parameter is required")
    return {
        "target_parameter": target_parameter,
        "value": float(value),
        "source_column": column,
        "reducer": reducer,
        "row_index": int(mapping.get("row_index") or 0) if reducer == "row" else None,
        "raw_value": raw,
        "converted_value": converted,
        "conversion": conversion,
        "scale": scale,
        "offset": offset,
    }


def build_parameter_packet(dataset: Mapping[str, Any], *, adapter_id: str, target_profile: str, mappings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if dataset.get("schema") != "physical-lab-canonical-dataset-v1":
        raise ValueError("source must be a canonical Physical Lab dataset")
    spec = ADAPTERS.get(str(adapter_id))
    if spec is None:
        raise ValueError("unknown coupling target adapter")
    profiles = list(spec.get("profiles") or [])
    if str(target_profile) not in profiles:
        raise ValueError("target profile is not supported by selected adapter")
    if not 1 <= len(mappings) <= MAX_MAPPINGS:
        raise ValueError(f"coupling requires 1..{MAX_MAPPINGS} mappings")
    allowed = {row["name"] for row in adapter_parameters(adapter_id)}
    applied = [apply_mapping(dataset, row) for row in mappings]
    names = [row["target_parameter"] for row in applied]
    if len(set(names)) != len(names):
        raise ValueError("target parameters must be mapped at most once")
    unknown = [name for name in names if name not in allowed]
    if unknown:
        raise ValueError("mapping targets unsupported adapter parameters: " + ", ".join(unknown))
    params = {row["target_parameter"]: row["value"] for row in applied}
    stable = {
        "schema": PACKET_SCHEMA,
        "source_dataset_id": dataset.get("dataset_id"),
        "source_dataset_sha256": dataset.get("sha256"),
        "source_profile": dataset.get("profile"),
        "target_adapter": str(adapter_id),
        "target_profile": str(target_profile),
        "mappings": applied,
        "parameters": params,
    }
    return {
        **stable,
        "packet_sha256": _sha(stable),
        "boundary": "Explicit deterministic data-to-parameter mapping only. Scientific compatibility, causality, calibration validity and model-form suitability are not inferred by the pipeline.",
    }


def save_pipeline(project_dir: str | Path, *, name: str, packet: Mapping[str, Any], notes: str = "") -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("not a Physical Lab parameter packet")
    stable = {
        "schema": PIPELINE_SCHEMA,
        "project_id": project.get("project_id"),
        "name": str(name).strip() or "Model coupling pipeline",
        "packet": plain(dict(packet)),
        "notes": str(notes),
    }
    digest = _sha(stable)
    record = {
        **stable,
        "pipeline_id": f"pipeline-{digest[:20]}",
        "sha256": digest,
        "created_at": utc_now(),
        "boundary": "Saved coupling provenance. A stored mapping records how values were transported; it does not certify that the two models are physically compatible.",
    }
    target = _pipeline_dir(path) / f"{record['pipeline_id']}.json"
    target.write_text(json.dumps(plain(record), indent=2, sort_keys=True), encoding="utf-8")
    return record


def list_pipelines(project_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve(); projects.open_project(path)
    rows = []
    for file in sorted(_pipeline_dir(path).glob("*.json")):
        try: value = json.loads(file.read_text(encoding="utf-8"))
        except Exception: continue
        if isinstance(value, dict) and value.get("schema") == PIPELINE_SCHEMA:
            rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("pipeline_id") or "")), reverse=True)
    return rows


def queue_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("not a Physical Lab parameter packet")
    row = {"design_index": 0, **dict(packet.get("parameters") or {})}
    return create_sweep_job(str(packet.get("target_profile") or ""), str(packet.get("target_adapter") or ""), [row])
