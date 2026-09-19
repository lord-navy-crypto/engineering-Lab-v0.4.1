#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_tradeoff_analysis as ta

    frame = pd.DataFrame({
        "p": [1.0, 2.0, 3.0, 4.0, 5.0],
        "q": [5.0, 4.0, 3.0, 2.0, 1.0],
        "y": [2.0, 4.2, 5.9, 8.1, 10.2],
    })
    summary = ta.robust_sensitivity_summary(frame, ["p", "q"], "y")
    require(set(summary["parameter"]) == {"p", "q"}, "robust sensitivity parameters missing")
    require("median_local_slope" in summary.columns, "local sensitivity summary missing")
    require("median_abs_elasticity" in summary.columns, "elasticity summary missing")
    require("direction_agreement" in summary.columns, "direction agreement missing")
    require("score" not in summary.columns and "overall_score" not in summary.columns, "unexpected synthetic master score")

    exact = ta.unit_aware_comparison_contract([{"id": "a", "unit": "m"}, {"id": "b", "unit": "m"}])
    require(exact["status"] == "EXACT" and exact["comparable"], "exact-unit comparison failed")
    convertible = ta.unit_aware_comparison_contract([{"id": "a", "unit": "m"}, {"id": "b", "unit": "mm"}])
    require(convertible["status"] == "CONVERTIBLE" and convertible["comparable"], "convertible-unit comparison failed")
    incompatible = ta.unit_aware_comparison_contract([{"id": "a", "unit": "m"}, {"id": "b", "unit": "s"}])
    require(incompatible["status"] == "INCOMPATIBLE" and not incompatible["comparable"], "incompatible units were accepted")
    unspecified = ta.unit_aware_comparison_contract([{"id": "a", "unit": ""}, {"id": "b", "unit": "m"}])
    require(unspecified["status"] == "UNSPECIFIED" and not unspecified["comparable"], "unspecified units were accepted")
    converted = ta.convert_comparison_values([1.0, 2.0], "m", "mm")
    require(converted == [1000.0, 2000.0], "comparison value conversion failed")

    source = {"dataset_id": "fixture", "sha256": "abc"}
    analyses = [
        {"kind": "robust-sensitivity", "output": "y", "parameters": ["p", "q"]},
        {"kind": "pareto", "x": "cost", "y": "performance", "x_goal": "min", "y_goal": "max"},
    ]
    id1, sha1 = ta.summary_identity("Fixture Summary", source, analyses)
    id2, sha2 = ta.summary_identity("Fixture Summary", source, analyses)
    require(id1 == id2 and sha1 == sha2, "summary identity is not deterministic")

    with tempfile.TemporaryDirectory() as tmp:
        saved = ta.save_analysis_summary(tmp, title="Fixture Summary", source_identity=source, analyses=analyses)
        json_path = Path(saved["json_path"])
        md_path = Path(saved["markdown_path"])
        require(json_path.exists() and md_path.exists(), "summary artifacts were not written")
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        require(loaded["summary_id"] == id1 and loaded["sha256"] == sha1, "summary JSON identity mismatch")
        require("Scientific boundary" in md_path.read_text(encoding="utf-8"), "summary markdown boundary missing")

    require("not causal" in ta.BOUNDARY.lower(), "analysis boundary missing")
    print("PASS: robust sensitivity, unit-aware comparison and science summary artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
