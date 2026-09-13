#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_visualization_studio as viz

    result = {
        "schema": "fixture/v1",
        "time_s": [0.0, 1.0, 2.0],
        "signal": [2.0, 4.0, 8.0],
        "gain": 3.0,
        "field": [[1.0, 2.0], [3.0, 4.0]],
        "nested": {"metric": 7.0},
    }
    inventory = viz.numeric_inventory(result)
    kinds = {row["path"]: row["kind"] for row in inventory}
    require(kinds.get("$.time_s") == "vector", "time vector missing")
    require(kinds.get("$.signal") == "vector", "signal vector missing")
    require(kinds.get("$.field") == "matrix", "matrix discovery missing")
    require(kinds.get("$.nested.metric") == "scalar", "nested scalar missing")

    frame = viz.result_frame(result)
    require(list(frame["$.signal"]) == [2.0, 4.0, 8.0], "result vector changed")
    require(list(frame["$.gain"]) == [3.0, 3.0, 3.0], "scalar broadcast failed")
    require(viz.matrix_by_path(result, "$.field").shape == (2, 2), "matrix retrieval failed")

    dataset = {"columns": {"x": [1, 2, 3], "y": [4, 5, 6]}}
    dataset_frame = viz.dataset_frame(dataset)
    require(list(dataset_frame.columns) == ["x", "y"], "dataset columns changed")
    require(viz.numeric_columns(dataset_frame) == ["x", "y"], "numeric dataset detection failed")

    sweep = {
        "points": [
            {"status": "succeeded", "design_index": 0, "parameters": {"k": 1.0}, "result": {"score": 2.0, "series": [1, 2]}},
            {"status": "failed", "design_index": 1, "parameters": {"k": 2.0}, "error": "fixture"},
            {"status": "succeeded", "design_index": 2, "parameters": {"k": 3.0}, "result": {"score": 6.0}},
        ]
    }
    sweep_frame = viz.sweep_frame(sweep)
    require(len(sweep_frame) == 2, "failed sweep point leaked into visualization")
    require(list(sweep_frame["param:k"]) == [1.0, 3.0], "sweep parameter flattening failed")
    require(list(sweep_frame["result:$.score"]) == [2.0, 6.0], "sweep scalar output flattening failed")

    normalized = viz.transform(dataset_frame, ["y"], "min-max")
    require(abs(float(normalized["y"].iloc[0])) < 1e-12, "min-max lower bound wrong")
    require(abs(float(normalized["y"].iloc[-1]) - 1.0) < 1e-12, "min-max upper bound wrong")
    stats = viz.summary(dataset_frame, ["y"])
    require(stats and stats[0]["mean"] == 5.0, "summary statistics wrong")

    linear = viz.axis_values(0.0, 1.0, 3, "linear")
    require(linear == [0.0, 0.5, 1.0], "linear axis generation wrong")
    log = viz.axis_values(1.0, 100.0, 3, "log")
    require(all(abs(a - b) < 1e-9 for a, b in zip(log, [1.0, 10.0, 100.0])), "log axis generation wrong")

    design = viz.build_scan_design(parameter_a="k", values_a=[1.0, 2.0], parameter_b="c", values_b=[10.0, 20.0], fixed={"m": 3.0})
    require(len(design) == 4, "2-D scan Cartesian product wrong")
    require(design[0] == {"m": 3.0, "k": 1.0, "design_index": 0, "c": 10.0}, "scan row content wrong")
    try:
        viz.build_scan_design(parameter_a="k", values_a=list(range(501)))
    except ValueError:
        pass
    else:
        raise AssertionError("scan point safety limit was not enforced")

    require("not evidence" in viz.BOUNDARY.lower(), "visualization evidence boundary missing")
    print("PASS: Visualization Studio numeric discovery, plotting tables, matrices and bounded DIY scans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
