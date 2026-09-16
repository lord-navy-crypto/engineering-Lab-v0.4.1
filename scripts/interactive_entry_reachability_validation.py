#!/usr/bin/env python3
"""Audit packaged Streamlit-interactive functions against native reachability.

Canonical surface targets and already-reviewed public render entries inherit their
existing reachability decision. Private/non-render interactive children must still
be explicitly classified here, so adding a buried control cannot silently pass CI.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
CLASSIFICATIONS = ROOT / "src-tauri" / "resources" / "interactive_entry_classification.json"
RENDER_CLASSIFICATIONS = ROOT / "src-tauri" / "resources" / "render_entry_classification.json"

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
RENDER_CLASS_MAP = {
    "native": "native-surface",
    "dependent-child": "child-capability",
    "aggregate": "aggregate",
    "helper": "helper",
    "legacy": "legacy",
    "router": "intentionally-internal",
}


def interaction_call_name(node: ast.Call) -> str | None:
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


def _load_private_classifications() -> dict[tuple[str, str], dict]:
    rows = json.loads(CLASSIFICATIONS.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise AssertionError("interactive_entry_classification.json must be an array")
    classified: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError("interactive classifications must be objects")
        module = str(row.get("module") or "")
        functions = row.get("functions")
        names = [str(row.get("function") or "")] if functions is None else [str(x) for x in functions]
        if not module or not names or any(not x for x in names):
            raise AssertionError("interactive classification requires module and function/functions")
        for function in names:
            key = (module, function)
            if key in classified:
                raise AssertionError(f"duplicate interactive classification: {module}.{function}")
            classified[key] = dict(row)
    return classified


def _load_render_classifications() -> dict[tuple[str, str], dict]:
    rows = json.loads(RENDER_CLASSIFICATIONS.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        if isinstance(row, dict):
            module = str(row.get("module") or "")
            callable_name = str(row.get("callable") or "")
            if module and callable_name:
                out[(module, callable_name)] = row
    return out


def main() -> None:
    surfaces = json.loads(SURFACES.read_text(encoding="utf-8"))
    surface_ids = {str(row.get("id") or "") for row in surfaces if isinstance(row, dict)}
    surface_targets = {
        (str(row.get("targetModule") or ""), str(row.get("targetCallable") or "")): str(row.get("id") or "")
        for row in surfaces if isinstance(row, dict) and row.get("targetModule") and row.get("targetCallable")
    }
    private = _load_private_classifications()
    render_review = _load_render_classifications()

    discovered: dict[tuple[str, str], dict[str, object]] = {}
    for path in sorted(UI_ROOT.glob("physical_lab_*.py")):
        for entry in interactive_functions(path):
            discovered[(path.stem, str(entry["function"]))] = entry

    effective: dict[tuple[str, str], dict] = {}
    provenance: dict[tuple[str, str], str] = {}
    for key in discovered:
        if key in surface_targets:
            effective[key] = {"classification": "native-surface", "surfaceId": surface_targets[key]}
            provenance[key] = "surface-manifest"
            continue
        reviewed = render_review.get(key)
        if reviewed:
            mapped = RENDER_CLASS_MAP.get(str(reviewed.get("classification") or ""))
            if mapped:
                row = {"classification": mapped}
                if reviewed.get("surfaceId"):
                    row["surfaceId"] = str(reviewed["surfaceId"])
                if reviewed.get("coveredBy"):
                    row["coveredBy"] = str(reviewed["coveredBy"])
                if mapped == "intentionally-internal":
                    row["rationale"] = "Reviewed public render router; reachability is provided by its registered child surfaces."
                effective[key] = row
                provenance[key] = "render-entry-review"
                continue
        if key in private:
            effective[key] = private[key]
            provenance[key] = "interactive-private-review"

    missing = sorted(key for key in discovered if key not in effective)
    if missing:
        detail = []
        for module, function in missing:
            entry = discovered[(module, function)]
            detail.append(f"  - {module}.{function} [line {entry['line']}] calls={','.join(entry['calls'])}")
        raise AssertionError(
            "private/non-render interactive functions lack reachability classification:\n" + "\n".join(detail)
        )

    stale = sorted(key for key in private if key not in discovered)
    if stale:
        raise AssertionError(
            "interactive private classification contains stale/non-interactive entries:\n  - "
            + "\n  - ".join(f"{m}.{f}" for m, f in stale)
        )

    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    for key, row in effective.items():
        classification = str(row.get("classification") or "")
        if classification not in VALID_CLASSES:
            raise AssertionError(f"invalid interactive classification for {key[0]}.{key[1]}: {classification!r}")
        counts[classification] = counts.get(classification, 0) + 1
        sources[provenance[key]] = sources.get(provenance[key], 0) + 1
        surface_id = str(row.get("surfaceId") or "")
        covered_by = str(row.get("coveredBy") or "")
        rationale = str(row.get("rationale") or "").strip()
        if classification == "native-surface":
            if not surface_id or surface_id not in surface_ids:
                raise AssertionError(f"native-surface {key[0]}.{key[1]} requires valid surfaceId")
        elif classification in {"child-capability", "aggregate", "prerequisite-flow", "legacy", "helper"}:
            if not covered_by or covered_by not in surface_ids:
                raise AssertionError(f"{classification} {key[0]}.{key[1]} requires valid coveredBy")
        elif classification == "intentionally-internal" and not rationale:
            raise AssertionError(f"intentionally-internal {key[0]}.{key[1]} requires rationale")

    print(json.dumps({
        "interactive_functions": len(discovered),
        "classification_counts": counts,
        "classification_sources": sources,
        "unclassified_interactive_functions": 0,
        "interactive_reachability_audit": True,
        "container_control_detection": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
