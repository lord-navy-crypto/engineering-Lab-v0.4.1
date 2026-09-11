"""Persistent allow-listed parameter-sweep executor for Physical Lab.

This module turns Research Orchestrator design rows into bounded local campaigns.
It does not execute arbitrary user code: adapters are explicit and profile-scoped.
Jobs persist under PHYSICAL_LAB_DATA_DIR/research-sweeps with per-point cache,
progress, cancellation, partial-failure retention, and result publication.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

JOB_SCHEMA = "physical-lab-sweep-job-v1"
RESULT_SCHEMA = "physical-lab-sweep-result-v1"
MAX_SWEEP_POINTS = 500
MAX_PARALLEL_SWEEPS = 2
_CANCELLED = False

ADAPTERS: dict[str, dict[str, Any]] = {
    "pid-step": {
        "profiles": ["oscillation-integration"],
        "module": "physical_lab_model_depth_ix",
        "function": "pid_step_response",
        "label": "PID step response",
    },
    "lqr-kalman": {
        "profiles": ["oscillation-integration"],
        "module": "physical_lab_model_depth_ix",
        "function": "lqr_kalman_demo",
        "label": "LQR + Kalman benchmark",
    },
    "heat-1d": {
        "profiles": ["numerical-methods"],
        "module": "physical_lab_model_depth_ix",
        "function": "heat_equation_1d",
        "label": "1-D heat equation",
    },
    "wave-1d": {
        "profiles": ["numerical-methods"],
        "module": "physical_lab_model_depth_ix",
        "function": "wave_equation_1d",
        "label": "1-D wave equation",
    },
    "poisson-2d": {
        "profiles": ["numerical-methods"],
        "module": "physical_lab_model_depth_ix",
        "function": "poisson_equation_2d",
        "label": "2-D Poisson field",
    },
    "chirp-frf": {
        "profiles": ["oscillation-integration", "numerical-methods"],
        "module": "physical_lab_model_depth_viii",
        "function": "chirp_frf_experiment",
        "label": "Chirp FRF experiment",
    },
}


def _signal_cancel(_signum, _frame) -> None:
    global _CANCELLED
    _CANCELLED = True


for _sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, _signal_cancel)
    except Exception:
        pass


def _plain(v: Any) -> Any:
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, Mapping):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if hasattr(v, "tolist"):
        return _plain(v.tolist())
    if hasattr(v, "item"):
        try:
            return _plain(v.item())
        except Exception:
            pass
    return v


def _root() -> Path | None:
    raw = os.environ.get("PHYSICAL_LAB_DATA_DIR", "").strip()
    if not raw:
        return None
    root = Path(raw) / "research-sweeps"
    root.mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(parents=True, exist_ok=True)
    return root


def available_adapters(profile: str) -> list[dict[str, str]]:
    out = []
    for key, spec in ADAPTERS.items():
        if profile in spec["profiles"]:
            out.append({"id": key, "label": str(spec["label"])})
    return out


def _job_dir(job_id: str) -> Path:
    root = _root()
    if root is None:
        raise RuntimeError("PHYSICAL_LAB_DATA_DIR is not configured")
    if not job_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in job_id):
        raise ValueError("invalid sweep job id")
    return root / job_id


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_plain(dict(value)), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _design_hash(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps({"profile": profile, "adapter": adapter, "rows": _plain(list(rows))}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_sweep_job(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    root = _root()
    if root is None:
        raise RuntimeError("PHYSICAL_LAB_DATA_DIR is not configured")
    if adapter not in ADAPTERS or profile not in ADAPTERS[adapter]["profiles"]:
        raise ValueError("adapter is not allow-listed for this profile")
    design = [dict(row) for row in rows]
    if not design or len(design) > MAX_SWEEP_POINTS:
        raise ValueError(f"campaign must contain 1..{MAX_SWEEP_POINTS} points")
    for row in design:
        for key, value in row.items():
            if key == "design_index":
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError("sweep parameters must be finite numeric scalars")
    job_id = f"sweep-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}"
    directory = root / job_id
    directory.mkdir(parents=True, exist_ok=False)
    design_sha = _design_hash(profile, adapter, design)
    _atomic_json(directory / "design.json", {"profile": profile, "adapter": adapter, "rows": design, "design_sha256": design_sha})
    record = {
        "schema": JOB_SCHEMA,
        "id": job_id,
        "profile": profile,
        "adapter": adapter,
        "adapter_label": ADAPTERS[adapter]["label"],
        "design_sha256": design_sha,
        "point_count": len(design),
        "status": "queued",
        "stage": "queued",
        "progress": 0.0,
        "completed_points": 0,
        "failed_points": 0,
        "cached_points": 0,
        "pid": None,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "error": None,
        "result_path": None,
        "boundary": "Allow-listed local model sweep. Per-point numerical success is not experimental validation or parameter optimality.",
    }
    _atomic_json(directory / "job.json", record)
    return record


def read_sweep_job(job_id: str) -> dict[str, Any] | None:
    return _read_json(_job_dir(job_id) / "job.json")


def list_sweep_jobs(*, profile: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    root = _root()
    if root is None:
        return []
    rows = []
    for path in root.iterdir():
        if not path.is_dir() or path.name == "cache":
            continue
        record = _read_json(path / "job.json")
        if not record or record.get("schema") != JOB_SCHEMA:
            continue
        if profile and record.get("profile") != profile:
            continue
        if record.get("status") == "running" and not _pid_alive(record.get("pid")):
            record.update({"status": "interrupted", "stage": "interrupted", "pid": None, "finished_at": time.time(), "error": record.get("error") or "worker exited before terminal state"})
            _atomic_json(path / "job.json", record)
        rows.append(record)
    rows.sort(key=lambda x: (float(x.get("created_at") or 0), str(x.get("id") or "")), reverse=True)
    return rows[:max(1, min(int(limit), 200))]


def start_sweep_job(job_id: str) -> dict[str, Any]:
    record = read_sweep_job(job_id)
    if not record:
        raise FileNotFoundError(job_id)
    if record.get("status") not in {"queued", "interrupted", "failed", "cancelled"}:
        return record
    running = [r for r in list_sweep_jobs(limit=200) if r.get("status") == "running" and _pid_alive(r.get("pid"))]
    if len(running) >= MAX_PARALLEL_SWEEPS:
        raise RuntimeError("maximum parallel sweep campaigns already running")
    directory = _job_dir(job_id)
    try:
        (directory / "cancel.requested").unlink()
    except FileNotFoundError:
        pass
    log = open(directory / "worker.log", "ab", buffering=0)
    try:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--run-job", str(directory)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy(), start_new_session=True, close_fds=True)
    finally:
        log.close()
    record.update({"status": "running", "stage": "starting", "progress": max(float(record.get("progress") or 0.0), 0.01), "pid": int(proc.pid), "started_at": time.time(), "finished_at": None, "error": None})
    _atomic_json(directory / "job.json", record)
    return record


def cancel_sweep_job(job_id: str) -> dict[str, Any]:
    record = read_sweep_job(job_id)
    if not record:
        raise FileNotFoundError(job_id)
    if record.get("status") in {"succeeded", "failed", "cancelled"}:
        return record
    directory = _job_dir(job_id)
    (directory / "cancel.requested").write_text(str(time.time()), encoding="utf-8")
    pid = record.get("pid")
    if _pid_alive(pid):
        try:
            os.killpg(int(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
    record.update({"status": "cancelled", "stage": "cancelled", "pid": None, "finished_at": time.time()})
    _atomic_json(directory / "job.json", record)
    return record


def read_sweep_result(job_id: str) -> dict[str, Any] | None:
    path = _job_dir(job_id) / "result.json"
    return _read_json(path) if path.exists() else None


def _point_key(adapter: str, params: Mapping[str, Any]) -> str:
    payload = json.dumps({"adapter": adapter, "parameters": _plain(dict(params))}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _flatten_scalars(value: Any, prefix: str = "", out: dict[str, float] | None = None) -> dict[str, float]:
    out = out if out is not None else {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            _flatten_scalars(item, name, out)
    elif isinstance(value, bool):
        return out
    elif isinstance(value, (int, float)):
        x = float(value)
        if math.isfinite(x):
            out[prefix] = x
    return out


def execute_adapter(adapter: str, params: Mapping[str, Any]) -> dict[str, Any]:
    spec = ADAPTERS.get(adapter)
    if not spec:
        raise ValueError("unknown sweep adapter")
    module = importlib.import_module(str(spec["module"]))
    fn = getattr(module, str(spec["function"]))
    call_params = {str(k): float(v) for k, v in params.items() if k != "design_index"}
    result = fn(**call_params)
    metrics = _flatten_scalars(result)
    return {"parameters": call_params, "metrics": metrics, "result": _plain(result)}


def _cancel_requested(job_dir: Path) -> bool:
    return _CANCELLED or (job_dir / "cancel.requested").exists()


def run_job(job_dir: Path) -> int:
    job_dir = job_dir.resolve()
    record = _read_json(job_dir / "job.json") or {}
    design = _read_json(job_dir / "design.json") or {}
    adapter = str(design.get("adapter") or record.get("adapter") or "")
    rows = list(design.get("rows") or [])
    root = _root()
    if root is None:
        raise RuntimeError("PHYSICAL_LAB_DATA_DIR is not configured")
    cache_root = root / "cache"
    record.update({"status": "running", "stage": "running", "pid": os.getpid(), "started_at": record.get("started_at") or time.time(), "error": None})
    _atomic_json(job_dir / "job.json", record)
    outputs = []
    failed = 0
    cached = 0
    for i, row in enumerate(rows):
        if _cancel_requested(job_dir):
            record.update({"status": "cancelled", "stage": "cancelled", "pid": None, "finished_at": time.time()})
            _atomic_json(job_dir / "job.json", record)
            return 130
        params = {k: v for k, v in dict(row).items() if k != "design_index"}
        key = _point_key(adapter, params)
        cache_path = cache_root / f"{key}.json"
        item = _read_json(cache_path)
        if item is not None:
            cached += 1
            point = {"design_index": int(row.get("design_index", i)), "status": "succeeded", "cached": True, **item}
        else:
            try:
                started = time.perf_counter()
                item = execute_adapter(adapter, params)
                item["runtime_s"] = time.perf_counter() - started
                _atomic_json(cache_path, item)
                point = {"design_index": int(row.get("design_index", i)), "status": "succeeded", "cached": False, **item}
            except Exception as exc:
                failed += 1
                point = {"design_index": int(row.get("design_index", i)), "status": "failed", "cached": False, "parameters": _plain(params), "metrics": {}, "error": f"{type(exc).__name__}: {exc}"}
        outputs.append(point)
        completed = i + 1
        record.update({"stage": "running", "progress": completed / max(len(rows), 1), "completed_points": completed, "failed_points": failed, "cached_points": cached})
        _atomic_json(job_dir / "job.json", record)
        _atomic_json(job_dir / "partial-result.json", {"schema": RESULT_SCHEMA, "adapter": adapter, "points": outputs})
    result = {"schema": RESULT_SCHEMA, "profile": record.get("profile"), "adapter": adapter, "design_sha256": record.get("design_sha256"), "point_count": len(rows), "succeeded_points": len(rows) - failed, "failed_points": failed, "cached_points": cached, "points": outputs, "boundary": "Finite allow-listed computational sweep. Cached equality means identical adapter/parameter inputs, not equivalence of physical experiments."}
    _atomic_json(job_dir / "result.json", result)
    record.update({"status": "succeeded" if failed < len(rows) else "failed", "stage": "complete", "progress": 1.0, "pid": None, "finished_at": time.time(), "result_path": str(job_dir / "result.json"), "failed_points": failed, "cached_points": cached})
    _atomic_json(job_dir / "job.json", record)
    return 0 if failed < len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-job")
    args = parser.parse_args(argv)
    if not args.run_job:
        parser.error("--run-job is required")
    try:
        return run_job(Path(args.run_job))
    except Exception as exc:
        try:
            directory = Path(args.run_job).resolve()
            record = _read_json(directory / "job.json") or {}
            record.update({"status": "failed", "stage": "failed", "pid": None, "finished_at": time.time(), "error": f"{type(exc).__name__}: {exc}"})
            _atomic_json(directory / "job.json", record)
        except Exception:
            pass
        print(f"Sweep worker failed: {type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
