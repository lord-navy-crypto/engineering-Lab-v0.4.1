"""Project-level data bridge and reproducibility packaging for Engineering Lab.

Provides cross-cutting project features:
- canonical numeric datasets stored inside a .physlab project and reusable across profiles;
- deterministic reproducibility ZIP packs containing project metadata, manifests,
  references, selected provenance metadata, Lab Journey events, frozen run snapshots,
  saved coupling pipelines/workflows, software environment snapshots, a generated
  report, and SHA-256 checksums.

This module does not reinterpret units or scientific meaning and never executes code.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile
from typing import Any, Mapping, Sequence

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, utc_now

DATASET_SCHEMA = "physical-lab-canonical-dataset-v1"
PACK_SCHEMA = "physical-lab-reproducibility-pack-v1"
MAX_DATASET_ROWS = 200000
MAX_PACK_FILE_BYTES = 8 * 1024 * 1024


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return _sha_bytes(raw)


def _safe_name(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in str(value).strip())
    return (out.strip("-.") or "dataset")[:80]


def _dataset_dir(project_dir: Path) -> Path:
    path = project_dir / "datasets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_canonical_dataset(
    project_dir: str | Path,
    *,
    name: str,
    profile: str,
    columns: Mapping[str, Sequence[Any]],
    units: Mapping[str, str] | None = None,
    source: str = "",
    notes: str = "",
) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    if not columns:
        raise ValueError("dataset requires at least one column")
    names = [str(k).strip() for k in columns]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise ValueError("dataset column names must be non-empty and unique")
    lengths = {len(columns[k]) for k in columns}
    if len(lengths) != 1:
        raise ValueError("dataset columns must have equal length")
    n = next(iter(lengths))
    if n < 1 or n > MAX_DATASET_ROWS:
        raise ValueError(f"dataset row count must be between 1 and {MAX_DATASET_ROWS}")
    normalized: dict[str, list[float | None]] = {}
    for key, seq in columns.items():
        vals: list[float | None] = []
        for value in seq:
            if value is None:
                vals.append(None); continue
            try:
                x = float(value)
            except Exception:
                vals.append(None); continue
            vals.append(x if math.isfinite(x) else None)
        normalized[str(key)] = vals
    stable = {
        "schema": DATASET_SCHEMA,
        "project_id": project["project_id"],
        "name": str(name).strip() or "Dataset",
        "profile": str(profile),
        "row_count": n,
        "columns": normalized,
        "units": {str(k): str(v) for k, v in dict(units or {}).items() if str(k) in normalized},
        "source": str(source),
        "notes": str(notes),
    }
    digest = _sha_json(stable)
    dataset_id = f"dataset-{digest[:20]}"
    record = {
        **stable,
        "dataset_id": dataset_id,
        "created_at": utc_now(),
        "sha256": digest,
        "boundary": "Canonical numeric transport dataset. Units and physical interpretation are user-supplied metadata; saving a dataset does not validate or calibrate it.",
    }
    target = _dataset_dir(path) / f"{_safe_name(record['name'])}-{digest[:12]}.json"
    target.write_text(json.dumps(plain(record), indent=2, sort_keys=True), encoding="utf-8")
    return record


def list_canonical_datasets(project_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    rows = []
    for file in sorted(_dataset_dir(path).glob("*.json")):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("schema") == DATASET_SCHEMA:
            rows.append({**value, "file_path": str(file)})
    rows.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("dataset_id") or "")), reverse=True)
    return rows


def dataset_csv_bytes(dataset: Mapping[str, Any]) -> bytes:
    if dataset.get("schema") != DATASET_SCHEMA:
        raise ValueError("not a canonical Physical Lab dataset")
    cols = dataset.get("columns") or {}
    names = list(cols)
    n = int(dataset.get("row_count") or 0)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(names)
    for i in range(n):
        writer.writerow(["" if cols[k][i] is None else cols[k][i] for k in names])
    return out.getvalue().encode("utf-8")


def _candidate_pack_files(project_dir: Path, *, include_measurement_assets: bool) -> list[Path]:
    roots = [
        "project.json", "experiments", "results", "calibration", "provenance",
        "datasets", "pipelines", "workflows", "environments", "run-snapshots",
        "journey", "reports",
    ]
    if include_measurement_assets:
        roots.append("measurements")
    else:
        roots.append("measurements/index.json")
    files: list[Path] = []
    for rel in roots:
        p = project_dir / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(x for x in p.rglob("*") if x.is_file())
    return sorted(set(files))


def build_reproducibility_pack(project_dir: str | Path, *, include_measurement_assets: bool = False) -> dict[str, Any]:
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)
    report = projects.render_project_report_markdown(path, generated_at=str(project.get("updated_at") or project.get("created_at") or ""))
    selected = []
    omitted = []
    for file in _candidate_pack_files(path, include_measurement_assets=include_measurement_assets):
        try:
            size = file.stat().st_size
        except OSError:
            continue
        rel = file.relative_to(path).as_posix()
        if size > MAX_PACK_FILE_BYTES:
            omitted.append({"path": rel, "reason": "file exceeds per-file pack limit", "size_bytes": size})
        else:
            selected.append(file)
    manifest_entries = []
    for file in selected:
        data = file.read_bytes()
        manifest_entries.append({"path": file.relative_to(path).as_posix(), "size_bytes": len(data), "sha256": _sha_bytes(data)})
    stable_manifest = {
        "schema": PACK_SCHEMA,
        "project_id": project["project_id"],
        "project_name": project.get("name"),
        "include_measurement_assets": bool(include_measurement_assets),
        "files": manifest_entries,
        "omitted": omitted,
    }
    stable_manifest["manifest_sha256"] = _sha_json(stable_manifest)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in selected:
            info = zipfile.ZipInfo(file.relative_to(path).as_posix(), date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, file.read_bytes())
        info = zipfile.ZipInfo("PROJECT_REPORT.md", date_time=(1980,1,1,0,0,0)); info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, report.encode("utf-8"))
        info = zipfile.ZipInfo("REPRODUCIBILITY_MANIFEST.json", date_time=(1980,1,1,0,0,0)); info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, json.dumps(stable_manifest, indent=2, sort_keys=True).encode("utf-8"))
    payload = bio.getvalue()
    return {
        "schema": PACK_SCHEMA,
        "filename": f"{_safe_name(project.get('slug') or project.get('name') or 'physical-lab')}-reproducibility.zip",
        "bytes": payload,
        "size_bytes": len(payload),
        "file_count": len(selected) + 2,
        "manifest": stable_manifest,
        "zip_sha256": _sha_bytes(payload),
        "boundary": "Portable provenance/reproducibility package, not a scientific validation certificate. External solver binaries, large omitted files, and environment recreation may still be required.",
    }
