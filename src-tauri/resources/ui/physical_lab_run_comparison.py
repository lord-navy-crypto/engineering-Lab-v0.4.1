"""Run comparison and staleness analysis for Physical Lab.

The engine compares persisted scientific results without collapsing distinct evidence
layers into one score. It separates scientific-input identity, result schema/contract,
software environment, numerical sanity, uncertainty objects, scalar metrics and
runtime metadata. Staleness is an explicit provenance warning, not a statement that
an older numerical result is wrong.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_environment_manifest import build_environment_manifest, compare_environments, list_environment_manifests
from physical_lab_experiment_kernel import plain
from physical_lab_result_contracts import annotate_inventory, find_uncertainty_objects, get_contract, validate_contract_inventory
from physical_lab_result_inspector import inspect_result, load_project_result, load_sweep_point, numerical_sanity_report

COMPARISON_SCHEMA = "physical-lab-run-comparison-v1"
STALENESS_SCHEMA = "physical-lab-result-staleness-v1"


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _finite_scalar(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    x = float(value)
    return x if math.isfinite(x) else None


def flatten_scalars(value: Any, prefix: str = "", out: dict[str, float] | None = None, *, limit: int = 600) -> dict[str, float]:
    target = out if out is not None else {}
    if len(target) >= limit:
        return target
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            flatten_scalars(item, name, target, limit=limit)
            if len(target) >= limit:
                break
        return target
    scalar = _finite_scalar(value)
    if scalar is not None and prefix:
        target[prefix] = scalar
    return target


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _experiment_manifest(project_dir: Path, experiment_id: str | None) -> dict[str, Any] | None:
    if not experiment_id:
        return None
    doc = projects.open_project(project_dir)
    entry = (doc.get("experiments") or {}).get(str(experiment_id))
    if not isinstance(entry, Mapping):
        return None
    rel = entry.get("manifest_path")
    if not rel:
        return None
    return _read_json(project_dir / str(rel))


def _nearest_environment(project_dir: Path, *, source_commit: str | None = None) -> dict[str, Any] | None:
    rows = list_environment_manifests(project_dir)
    if source_commit:
        for row in rows:
            if str((row.get("physical_lab") or {}).get("source_commit") or "") == str(source_commit):
                return row
    return rows[0] if rows else None


def project_run_snapshot(project_dir: str | Path, job_id: str) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    doc = projects.open_project(path)
    result_entry = (doc.get("results") or {}).get(str(job_id))
    job_entry = (doc.get("jobs") or {}).get(str(job_id))
    if not isinstance(result_entry, Mapping) or not isinstance(job_entry, Mapping):
        raise KeyError(f"project run not found: {job_id}")
    result, identity = load_project_result(path, str(job_id))
    manifest = _experiment_manifest(path, str(result_entry.get("experiment_id") or job_entry.get("experiment_id") or ""))
    provenance = dict((manifest or {}).get("provenance") or {})
    env = _nearest_environment(path, source_commit=str(provenance.get("source_commit") or "") or None)
    runtime = None
    created = job_entry.get("created_at")
    updated = job_entry.get("updated_at")
    # ISO timestamps are retained as metadata; runtime is only populated when already explicit.
    if _finite_scalar(job_entry.get("runtime_s")) is not None:
        runtime = float(job_entry["runtime_s"])
    return build_run_snapshot(
        run_id=str(job_id),
        source_kind="project-compute",
        result=result,
        result_identity=identity,
        profile=str(job_entry.get("profile") or (manifest or {}).get("profile") or ""),
        experiment_sha256=str(job_entry.get("experiment_sha256") or (manifest or {}).get("experiment_sha256") or "") or None,
        source_commit=str(provenance.get("source_commit") or "") or None,
        environment=env,
        runtime_s=runtime,
        parameters=dict((manifest or {}).get("parameters") or {}),
        metadata={"created_at": created, "updated_at": updated, "runner": job_entry.get("runner")},
    )


def sweep_point_snapshot(job_id: str, point_index: int) -> dict[str, Any]:
    from physical_lab_sweep_executor import read_sweep_job, read_sweep_result
    record = read_sweep_job(str(job_id))
    full = read_sweep_result(str(job_id))
    if not record or not full:
        raise FileNotFoundError(job_id)
    points = list(full.get("points") or [])
    if not 0 <= int(point_index) < len(points):
        raise IndexError(point_index)
    point = points[int(point_index)]
    if not isinstance(point, Mapping) or point.get("status") != "succeeded" or not isinstance(point.get("result"), Mapping):
        raise ValueError("selected sweep point is not a successful full result")
    result, identity = load_sweep_point(str(job_id), int(point_index))
    return build_run_snapshot(
        run_id=f"{job_id}:point:{point_index}",
        source_kind="sweep-point",
        result=result,
        result_identity=identity,
        profile=str(record.get("profile") or full.get("profile") or ""),
        experiment_sha256=None,
        source_commit=None,
        environment=None,
        runtime_s=_finite_scalar(point.get("runtime_s")),
        parameters=dict(point.get("parameters") or {}),
        metadata={"adapter": record.get("adapter"), "cached": point.get("cached"), "design_index": point.get("design_index")},
    )


def build_run_snapshot(
    *,
    run_id: str,
    source_kind: str,
    result: Mapping[str, Any],
    result_identity: Mapping[str, Any] | None = None,
    profile: str = "",
    experiment_sha256: str | None = None,
    source_commit: str | None = None,
    environment: Mapping[str, Any] | None = None,
    runtime_s: float | None = None,
    parameters: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    inspection = inspect_result(result)
    annotated = annotate_inventory(result.get("schema"), inspection["inventory"])
    conformance = validate_contract_inventory(result.get("schema"), inspection["inventory"])
    sanity = numerical_sanity_report(result)
    uncertainty = find_uncertainty_objects(result)
    contract = get_contract(str(result.get("schema") or ""))
    stable = {
        "run_id": str(run_id),
        "source_kind": str(source_kind),
        "profile": str(profile),
        "experiment_sha256": experiment_sha256,
        "source_commit": source_commit,
        "result_schema": result.get("schema"),
        "result_sha256": inspection["result_sha256"],
        "contract_sha256": (contract or {}).get("contract_sha256"),
        "environment_sha256": (environment or {}).get("environment_sha256"),
        "runtime_s": runtime_s,
        "parameters": plain(dict(parameters or {})),
        "metrics": flatten_scalars(result),
        "sanity": {"status": sanity["status"], "sha256": sanity["sanity_sha256"], "checks": sanity["checks"]},
        "contract_conformance": conformance,
        "uncertainty_objects": [row["value"] for row in uncertainty],
        "result_identity": plain(dict(result_identity or {})),
        "metadata": plain(dict(metadata or {})),
        "environment": plain(dict(environment or {})) if environment else None,
        "contract_registered": bool(annotated["registered"]),
    }
    return {**stable, "snapshot_sha256": _sha(stable)}


def staleness_report(snapshot: Mapping[str, Any], *, current_environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []
    schema = str(snapshot.get("result_schema") or "")
    current_contract = get_contract(schema)
    old_contract_sha = str(snapshot.get("contract_sha256") or "")
    current_contract_sha = str((current_contract or {}).get("contract_sha256") or "")
    if old_contract_sha and current_contract_sha and old_contract_sha != current_contract_sha:
        reasons.append({"severity": "stale", "code": "CONTRACT_CHANGED", "message": "Registered result contract has changed since this snapshot."})
    elif not old_contract_sha:
        reasons.append({"severity": "unknown", "code": "CONTRACT_UNKNOWN", "message": "No contract fingerprint is available for this result."})

    old_commit = str(snapshot.get("source_commit") or "")
    current_commit = str(((current_environment or {}).get("physical_lab") or {}).get("source_commit") or "")
    if old_commit and current_commit and old_commit != current_commit:
        reasons.append({"severity": "stale", "code": "SOURCE_COMMIT_CHANGED", "message": f"Result source commit {old_commit[:12]} differs from current {current_commit[:12]}."})
    elif not old_commit:
        reasons.append({"severity": "unknown", "code": "SOURCE_COMMIT_UNKNOWN", "message": "Result source commit is unavailable."})

    old_env = snapshot.get("environment")
    if isinstance(old_env, Mapping) and current_environment:
        diff = compare_environments(old_env, current_environment)
        if diff["differences"]:
            reasons.append({"severity": "caution", "code": "ENVIRONMENT_DRIFT", "message": f"Software/runtime environment differs in {len(diff['differences'])} tracked field(s).", "differences": diff["differences"]})
    elif not old_env:
        reasons.append({"severity": "unknown", "code": "ENVIRONMENT_UNKNOWN", "message": "No saved environment snapshot is associated with this run."})

    severe = any(x["severity"] == "stale" for x in reasons)
    caution = any(x["severity"] in {"caution", "unknown"} for x in reasons)
    status = "STALE" if severe else ("REVIEW" if caution else "CURRENT")
    stable = {"schema": STALENESS_SCHEMA, "snapshot_sha256": snapshot.get("snapshot_sha256"), "status": status, "reasons": reasons}
    return {**stable, "staleness_sha256": _sha(stable), "boundary": "Staleness is provenance/version drift, not evidence that an older numerical result is incorrect. Re-run decisions remain scientific and project-specific."}


def _compare_mapping(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(set(a) | set(b)):
        va, vb = a.get(key), b.get(key)
        if va != vb:
            rows.append({"field": key, "a": plain(va), "b": plain(vb)})
    return rows


def compare_runs(a: Mapping[str, Any], b: Mapping[str, Any], *, current_environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ma = dict(a.get("metrics") or {}); mb = dict(b.get("metrics") or {})
    common = sorted(set(ma) & set(mb))
    metric_rows = []
    for key in common:
        va, vb = float(ma[key]), float(mb[key])
        delta = vb - va
        rel = None if abs(va) <= 1e-30 else delta / abs(va)
        metric_rows.append({"metric": key, "a": va, "b": vb, "delta_b_minus_a": delta, "relative_delta": rel})
    same_schema = a.get("result_schema") == b.get("result_schema")
    same_experiment = bool(a.get("experiment_sha256") and a.get("experiment_sha256") == b.get("experiment_sha256"))
    same_contract = bool(a.get("contract_sha256") and a.get("contract_sha256") == b.get("contract_sha256"))
    same_environment = bool(a.get("environment_sha256") and a.get("environment_sha256") == b.get("environment_sha256"))
    if not same_schema:
        comparability = "INCOMPATIBLE-SCHEMA"
    elif not same_contract:
        comparability = "REVIEW-CONTRACT"
    elif a.get("experiment_sha256") and b.get("experiment_sha256") and not same_experiment:
        comparability = "DIFFERENT-INPUTS"
    elif a.get("environment_sha256") and b.get("environment_sha256") and not same_environment:
        comparability = "COMPARABLE-WITH-ENV-DRIFT"
    else:
        comparability = "COMPARABLE"
    stable = {
        "schema": COMPARISON_SCHEMA,
        "run_a": a.get("run_id"),
        "run_b": b.get("run_id"),
        "comparability": comparability,
        "same_result_schema": same_schema,
        "same_experiment": same_experiment,
        "same_contract": same_contract,
        "same_environment": same_environment,
        "parameter_differences": _compare_mapping(dict(a.get("parameters") or {}), dict(b.get("parameters") or {})),
        "metric_differences": metric_rows,
        "runtime": {"a": a.get("runtime_s"), "b": b.get("runtime_s")},
        "sanity": {"a": a.get("sanity"), "b": b.get("sanity")},
        "uncertainty": {"a": a.get("uncertainty_objects") or [], "b": b.get("uncertainty_objects") or []},
        "staleness": {
            "a": staleness_report(a, current_environment=current_environment),
            "b": staleness_report(b, current_environment=current_environment),
        },
    }
    return {**stable, "comparison_sha256": _sha(stable), "boundary": "Comparison reports provenance, parameter and numeric differences. It does not imply causal attribution, statistical significance, experimental equivalence or model validation."}
