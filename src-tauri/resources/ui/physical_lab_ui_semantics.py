"""Shared presentation-only scientific UI semantics for Engineering Lab.

This module formats caller-supplied identity and status information. It does not
infer scientific meaning from payloads, validate models, execute jobs, or mutate
project state.
"""
from __future__ import annotations

from typing import Any

OBJECT_TYPES = {"MEASUREMENT", "DATASET", "MODEL", "RESULT"}

VALIDATION_STATES = {"PASS", "REVIEW", "FAIL", "NOT ESTABLISHED"}
SCIENTIFIC_STATES = {"SUPPORTED", "REVIEW", "NOT ESTABLISHED", "OUT OF SCOPE"}
PROVENANCE_STATES = {"RECORDED", "PARTIAL", "NOT RECORDED", "UNSPECIFIED"}
EXECUTION_STATES = {
    "CONFIGURED",
    "PENDING",
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "INTERRUPTED",
    "BLOCKED",
    "NOT APPLICABLE",
}

STATUS_AXIS_LABELS = {
    "validation": "Validation",
    "scientific": "Scientific Status",
    "provenance": "Provenance",
    "execution": "Execution",
}

STATUS_SYMBOLS = {
    "PASS": "✓",
    "SUPPORTED": "✓",
    "RECORDED": "●",
    "CONFIGURED": "○",
    "PENDING": "○",
    "QUEUED": "◇",
    "RUNNING": "◆",
    "SUCCEEDED": "●",
    "REVIEW": "△",
    "PARTIAL": "◐",
    "FAIL": "×",
    "FAILED": "×",
    "CANCELLED": "⊘",
    "INTERRUPTED": "△",
    "BLOCKED": "□",
    "NOT ESTABLISHED": "?",
    "NOT RECORDED": "○",
    "UNSPECIFIED": "?",
    "OUT OF SCOPE": "—",
    "NOT APPLICABLE": "—",
}


def _canonical(value: str | None) -> str:
    return str(value or "").strip().replace("_", " ").upper()


def normalize_object_type(value: str | None) -> str:
    """Return an explicitly supplied supported object type or UNKNOWN.

    Deliberately does not inspect schemas, field names, or payload shape.
    """
    candidate = _canonical(value)
    return candidate if candidate in OBJECT_TYPES else "UNKNOWN"


def _normalize(value: str | None, allowed: set[str], fallback: str) -> str:
    candidate = _canonical(value)
    return candidate if candidate in allowed else fallback


def normalize_status_axes(
    *,
    validation: str | None = None,
    scientific: str | None = None,
    provenance: str | None = None,
    execution: str | None = None,
) -> dict[str, str]:
    """Normalize four independent axes without cross-axis promotion."""
    return {
        "validation": _normalize(validation, VALIDATION_STATES, "NOT ESTABLISHED"),
        "scientific": _normalize(scientific, SCIENTIFIC_STATES, "NOT ESTABLISHED"),
        "provenance": _normalize(provenance, PROVENANCE_STATES, "UNSPECIFIED"),
        "execution": _normalize(execution, EXECUTION_STATES, "NOT APPLICABLE"),
    }


def status_display(axis: str, value: str) -> str:
    """Return status as symbol + visible text; color is never required."""
    normalized_axis = str(axis or "").strip().lower()
    label = STATUS_AXIS_LABELS.get(normalized_axis, normalized_axis.replace("_", " ").title() or "Status")
    state = _canonical(value) or "UNSPECIFIED"
    symbol = STATUS_SYMBOLS.get(state, "?")
    return f"{symbol} {label}: {state}"


def render_context_header(
    st: Any,
    *,
    project: str | None = None,
    workspace: str | None = None,
    task: str | None = None,
    source: str | None = None,
) -> None:
    """Render PROJECT → WORKSPACE → TASK → SOURCE context without navigation state."""
    parts: list[str] = []
    for label, value in (
        ("PROJECT", project),
        ("WORKSPACE", workspace),
        ("TASK", task),
        ("SOURCE", source),
    ):
        text = str(value or "").strip()
        if text:
            parts.append(f"**{label}** · {text}")
    if parts:
        st.caption("  →  ".join(parts))


def render_object_card(
    st: Any,
    *,
    object_type: str,
    title: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Render caller-declared object identity and caller-supplied metadata."""
    kind = normalize_object_type(object_type)
    st.markdown(f"**{kind} · {str(title or 'Untitled').strip() or 'Untitled'}**")
    values = dict(metadata or {})
    if not values:
        st.caption("No compact metadata supplied; use the detailed workspace view for authoritative fields.")
        return
    parts: list[str] = []
    for key, value in values.items():
        if value is None or value == "":
            continue
        text = str(value)
        if "sha" in str(key).lower() and len(text) > 20:
            text = text[:16] + "…"
        parts.append(f"{key}: {text}")
    if parts:
        st.caption(" · ".join(parts))
    else:
        st.caption("No compact metadata supplied; use the detailed workspace view for authoritative fields.")


def render_status_card(
    st: Any,
    *,
    validation: str | None = None,
    scientific: str | None = None,
    provenance: str | None = None,
    execution: str | None = None,
) -> None:
    """Render four independent status axes with text and symbols."""
    axes = normalize_status_axes(
        validation=validation,
        scientific=scientific,
        provenance=provenance,
        execution=execution,
    )
    columns = st.columns(4)
    for idx, axis in enumerate(("validation", "scientific", "provenance", "execution")):
        columns[idx].markdown(status_display(axis, axes[axis]))
