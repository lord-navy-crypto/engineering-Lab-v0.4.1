#!/usr/bin/env python3
"""Audit packaged Streamlit-interactive functions against native reachability classification.

The audit intentionally detects controls called through Streamlit itself *and* through
containers returned by Streamlit (columns/forms/sidebars/etc.). Every interactive
function must be explicitly classified; private naming alone is never an exemption.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
CLASSIFICATIONS = ROOT / "src-tauri" / "resources" / "interactive_entry_classification.json"

# User-action controls only. Display-only calls such as dataframe/plotly_chart/metric
# do not create a separate interaction-reachability obligation.
INTERACTIONS = {
    "button", "form", "form_submit_button", "tabs", "selectbox", "multiselect",
    "radio", "checkbox", "toggle", "slider", "select_slider", "number_input",
    "text_input", "text_area", "date_input", "time_input", "color_picker",
    "file_uploader", "camera_input", "data_editor", "download_button", "chat_input",
    "feedback", "pills", "segmented_control", "expander",
}
VALID_CLASSES = {
    "native-surface", "child-capability", "aggregate", "prerequisite-flow",
    "helper", "legacy", "intentionally-internal",
}


def interaction_call_name(node: ast.Call) -> str | None:
    """Return the interactive method name regardless of Streamlit/container receiver.

    This deliberately accepts ``st.button(...)``, ``col.button(...)``,
    ``sidebar.selectbox(...)`` and similar container calls. We scan only packaged
    Engineering Lab UI modules, so explicit classification resolves false positives.
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in INTERACTIONS:
        return func.attr
    return None


def interactive_functions(path: Path) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    found: list[dict[str, object]] = []
    # Walk function bodies, including private helpers. Nested functions are recorded
    # independently and excluded from their parent's call set to avoid double-counting.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls: set[str] = set()
        stack = list(node.body)
        while stack:
            item = stack.pop()
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(item, ast.Call):
                name = interaction_call_name(item)
                if name:
                    calls.add(name)
            stack.extend(ast.iter_child_nodes(item))
        if calls:
            found.append({"function": node.name, "calls": sorted(calls), "line": node.lineno})
    return sorted(found, key=lambda item: (int(item["line"]), str(item["function"])))


def main() -> None:
    surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
    surface_ids = {str(row.get("id") or "") for row in surfaces if isinstance(row, dict)}
    surface_targets = {
        (str(row.get("targetModule") or ""), str(row.get("targetCallable") or "")): str(row.get("id") or "")
        for row in surfaces if isinstance(row, dict) and row.get("targetModule") and row.get("targetCallable")
    }
    rows = json.loads(CLASSIFICATIONS.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise AssertionError("interactive_entry_classification.json must be an array")

    classified: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError("interactive classifications must be objects")
        module = str(row.get("module") or "")
        function = str(row.get("function") or "")
        key = (module, function)
        if not module or not function:
            raise AssertionError("interactive classification requires module and function")
        if key in classified:
            raise AssertionError(f"duplicate interactive classification: {module}.{function}")
        classified[key] = row

    discovered: dict[tuple[str, str], dict[str, object]] = {}
    for path in sorted(UI_ROOT.glob("physical_lab_*.py")):
        for entry in interactive_functions(path):
            discovered[(path.stem, str(entry["function"]))] = entry

    missing = sorted(key for key in discovered if key not in classified)
    if missing:
        detail = []
        for module, function in missing:
            entry = discovered[(module, function)]
            target = surface_targets.get((module, function))
            hint = f" surface={target}" if target else ""
            detail.append(f"  - {module}.{function} [line {entry['line']}] calls={','.join(entry['calls'])}{hint}")
        raise AssertionError(
            "interactive Streamlit functions lack reachability classification:\n" + "\n".join(detail)
        )

    stale = sorted(key for key in classified if key not in discovered)
    if stale:
        raise AssertionError(
            "interactive classification contains stale/non-interactive entries:\n  - "
            + "\n  - ".join(f"{m}.{f}" for m, f in stale)
        )

    counts: dict[str, int] = {}
    for key, row in classified.items():
        classification = str(row.get("classification") or "")
        if classification not in VALID_CLASSES:
            raise AssertionError(f"invalid interactive classification for {key[0]}.{key[1]}: {classification!r}")
        counts[classification] = counts.get(classification, 0) + 1
        surface_id = str(row.get("surfaceId") or "")
        covered_by = str(row.get("coveredBy") or "")
        rationale = str(row.get("rationale") or "").strip()
        if classification == "native-surface":
            if not surface_id or surface_id not in surface_ids:
                raise AssertionError(f"native-surface {key[0]}.{key[1]} requires valid surfaceId")
            direct = surface_targets.get(key)
            if direct and direct != surface_id:
                raise AssertionError(f"native-surface {key[0]}.{key[1]} surfaceId {surface_id} disagrees with manifest target {direct}")
        elif classification in {"child-capability", "aggregate", "prerequisite-flow", "legacy", "helper"}:
            if not covered_by or covered_by not in surface_ids:
                raise AssertionError(f"{classification} {key[0]}.{key[1]} requires valid coveredBy")
        elif classification == "intentionally-internal":
            if not rationale:
                raise AssertionError(f"intentionally-internal {key[0]}.{key[1]} requires rationale")

    print(json.dumps({
        "interactive_functions": len(discovered),
        "classification_counts": counts,
        "unclassified_interactive_functions": 0,
        "interactive_reachability_audit": True,
        "container_control_detection": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
