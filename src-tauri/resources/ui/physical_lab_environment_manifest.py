"""Deterministic software/environment manifests for Physical Lab reproducibility.

The stable fingerprint excludes capture time and machine identity. It records only
scientifically relevant software/runtime facts that can affect computational output.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now

ENV_SCHEMA = "physical-lab-environment-manifest-v1"
PACKAGES = ("numpy", "scipy", "pandas", "streamlit", "matplotlib")


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def build_environment_manifest(*, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    stable = {
        "schema": ENV_SCHEMA,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": _package_versions(),
        "physical_lab": {
            "engine_mode": os.environ.get("PHYSICAL_LAB_ENGINE_MODE", "safe"),
            "source_commit": os.environ.get("PHYSICAL_LAB_SOURCE_COMMIT") or None,
            "solver_backend": os.environ.get("PHYSICAL_LAB_SOLVER_BACKEND") or None,
            "app_version": "0.10.0",
        },
        "extra": plain(dict(extra or {})),
    }
    return {
        **stable,
        "environment_sha256": _sha(stable),
        "boundary": "Software/runtime provenance only. Matching environments improve reproducibility but do not guarantee bitwise-identical results across hardware, BLAS libraries, compilers, threads, or nondeterministic solvers.",
    }


def save_environment_manifest(project_dir: str | Path, *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    manifest = build_environment_manifest(extra=extra)
    record = {
        **manifest,
        "project_id": project.get("project_id"),
        "captured_at": utc_now(),
    }
    root = path / "environments"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"environment-{manifest['environment_sha256'][:20]}.json"
    target.write_text(json.dumps(plain(record), indent=2, sort_keys=True), encoding="utf-8")
    return record


def list_environment_manifests(project_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    root = path / "environments"
    if not root.exists():
        return []
    rows = []
    for file in sorted(root.glob("environment-*.json")):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("schema") == ENV_SCHEMA:
            rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda r: str(r.get("captured_at") or ""), reverse=True)
    return rows


def compare_environments(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        ("python.version", (a.get("python") or {}).get("version"), (b.get("python") or {}).get("version")),
        ("platform.system", (a.get("platform") or {}).get("system"), (b.get("platform") or {}).get("system")),
        ("platform.release", (a.get("platform") or {}).get("release"), (b.get("platform") or {}).get("release")),
        ("platform.machine", (a.get("platform") or {}).get("machine"), (b.get("platform") or {}).get("machine")),
        ("source_commit", (a.get("physical_lab") or {}).get("source_commit"), (b.get("physical_lab") or {}).get("source_commit")),
        ("solver_backend", (a.get("physical_lab") or {}).get("solver_backend"), (b.get("physical_lab") or {}).get("solver_backend")),
    ]
    for name in sorted(set((a.get("packages") or {})) | set((b.get("packages") or {}))):
        keys.append((f"package.{name}", (a.get("packages") or {}).get(name), (b.get("packages") or {}).get(name)))
    diff = [{"field": name, "a": va, "b": vb} for name, va, vb in keys if va != vb]
    return {
        "same_fingerprint": str(a.get("environment_sha256") or "") == str(b.get("environment_sha256") or ""),
        "differences": diff,
        "boundary": "Environment comparison reports version/configuration differences only; it does not attribute output differences to a particular dependency.",
    }
