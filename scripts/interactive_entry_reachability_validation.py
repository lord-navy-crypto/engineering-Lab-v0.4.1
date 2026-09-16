#!/usr/bin/env python3
"""Audit packaged Streamlit-interactive functions against native reachability classification."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
CLASSIFICATIONS = ROOT / "src-tauri" / "resources" / "interactive_entry_classification.json"

INTERACTIONS = {
    "button", "form", "form_submit_button", "tabs", "selectbox", "multiselect",
    "radio", "checkbox", "slider", "number_input", "text_input", "text_area",
    "file_uploader", "data_editor", "download_button", "expander",
}
VALID_CLASSES = {
    "native-surface", "child-capability", "aggregate", "prerequisite-flow",
    "helper", "legacy", "intentionally-internal",
}


def streamlit_call_name(node: ast.Call) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in INTERACTIONS:
        return None
    value = func.value
    if isinstance(value, ast.Name) and value.id == "st":
        return func.attr
    return None


def interactive_functions(path: Path) -> list[dict[str, object]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    found: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = sorted({name for item in ast.walk(node) if isinstance(item, ast.Call) and (name := streamlit_call_name(item))})
        if calls:
            found.append({"function": node.name, "calls": calls, "line": node.lineno})
    return sorted(found, key=lambda item: (int(item["line"]), str(item["function"])))


def main() -> None:
    surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
    surface_ids = {str(row.get("id") or "") for row in surfaces if isinstance(row, dict)}
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
            detail.append(f"  - {module}.{function} [line {entry['line']}] calls={','.join(entry['calls'])}")
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
        if classification == "native-surface":
            if not surface_id or surface_id not in surface_ids:
                raise AssertionError(f"native-surface {key[0]}.{key[1]} requires valid surfaceId")
        elif classification == "child-capability":
            if not ((surface_id and surface_id in surface_ids) or (covered_by and covered_by in surface_ids)):
                raise AssertionError(f"child-capability {key[0]}.{key[1]} requires valid surfaceId or coveredBy")
        elif classification in {"aggregate", "prerequisite-flow", "legacy"}:
            if not covered_by or covered_by not in surface_ids:
                raise AssertionError(f"{classification} {key[0]}.{key[1]} requires valid coveredBy")
        elif classification == "intentionally-internal":
            if not str(row.get("rationale") or "").strip():
                raise AssertionError(f"intentionally-internal {key[0]}.{key[1]} requires rationale")

    print(json.dumps({
        "interactive_functions": len(discovered),
        "classification_counts": counts,
        "unclassified_interactive_functions": 0,
        "interactive_reachability_audit": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
