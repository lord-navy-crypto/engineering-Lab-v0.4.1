"""Provenance-preserving design-to-sweep bridge for Engineering Lab.

Reserved ``__*`` fields are analysis metadata. They are preserved in the sweep
design/result but are never passed to the allow-listed model adapter. Queueing a
design never starts execution automatically.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import physical_lab_sweep_executor as sweeps
from physical_lab_applied_analysis_advanced import adapter_parameter_names

BOUNDARY = (
    "Design metadata is preserved for downstream analysis provenance only. "
    "Queueing creates no computational evidence and never starts a sweep; execution requires a separate explicit user action."
)


def prepare_rows_preserving_metadata(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    allowed = set(adapter_parameter_names(profile, adapter))
    if not rows:
        raise ValueError("design has no rows")
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        clean: dict[str, Any] = {"design_index": int(row.get("design_index", index))}
        for raw_key, value in row.items():
            key = str(raw_key)
            if key == "design_index":
                continue
            if key.startswith("__"):
                if value is None or isinstance(value, (str, bool, int)):
                    clean[key] = value
                elif isinstance(value, float) and math.isfinite(value):
                    clean[key] = value
                else:
                    raise ValueError(f"reserved metadata {key!r} must be a JSON scalar")
                continue
            if key not in allowed:
                raise ValueError(f"design field is not accepted by adapter: {key}")
            if isinstance(value, bool):
                raise ValueError(f"adapter parameter {key!r} must be finite numeric")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"adapter parameter {key!r} must be finite numeric")
            clean[key] = numeric
        prepared.append(clean)
    return prepared


def queue_design_with_metadata(profile: str, adapter: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    prepared = prepare_rows_preserving_metadata(profile, adapter, rows)
    job = sweeps.create_sweep_job(profile, adapter, prepared)
    return {
        **job,
        "execution_started": False,
        "design_metadata_preserved": True,
        "boundary": BOUNDARY,
    }
