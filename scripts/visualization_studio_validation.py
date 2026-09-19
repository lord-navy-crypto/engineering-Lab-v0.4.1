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
    import numpy as np
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
    ndarray_inventory = viz.numeric_inventory(np.asarray([1.0, 2.0, 3.0]), "$.array")
    require(ndarray_inventory and ndarray_inventory[0]["kind"] == "vector", "numpy vector discovery missing")

    frame = viz.result_frame(result)
    require(list(frame["$.signal"]) == [2.0, 4.0, 8.0], "result vector changed")
    require(list(frame["$.gain"]) == [3.0, 3.0, 3.0], "scalar broadcast failed")
    require(viz.matrix_by_path(result, "$.field").shape == (2, 2), "matrix retrieval failed")

    dataset = {"columns": {"x": [1, 2, 3], "y": [4, 5, 6]}}
    dataset_frame = viz.dataset_frame(dataset)
    require(list(dataset_frame.columns) == ["x", "y"], "dataset columns changed")
    require(viz.numeric_columns(dataset_frame) == ["x", "y"], "numeric dataset detection failed")
    research = viz.research_table_frame({"column_data": {"a": [1, 2], "b": [3, 4]}})
    require(list(research.columns) == ["a", "b"], "research table bridge failed")

    sweep = {
        "points": [
            {"status": "succeeded", "design_index": 0, "parameters": {"k": 1.0}, "metrics": {"peak": 9.0}, "result": {"score": 2.0, "series": [1, 2]}},
            {"status": "failed", "design_index": 1, "parameters": {"k": 2.0}, "error": "fixture"},
            {"status": "succeeded", "design_index": 2, "parameters": {"k": 3.0}, "metrics": {"peak": 12.0}, "result": {"score": 6.0}},
        ]
    }
    sweep_frame = viz.sweep_frame(sweep)
    require(len(sweep_frame) == 2, "failed sweep point leaked into visualization")
    require(list(sweep_frame["param:k"]) == [1.0, 3.0], "sweep parameter flattening failed")
    require(list(sweep_frame["metric:peak"]) == [9.0, 12.0], "sweep metrics were not exposed")
    require(list(sweep_frame["result:$.score"]) == [2.0, 6.0], "sweep scalar output flattening failed")

    normalized = viz.transform(dataset_frame, ["y"], "min-max")
    require(abs(float(normalized["y"].iloc[0])) < 1e-12, "min-max lower bound wrong")
    require(abs(float(normalized["y"].iloc[-1]) - 1.0) < 1e-12, "min-max upper bound wrong")
    stats = viz.summary(dataset_frame, ["y"])
    require(stats and stats[0]["mean"] == 5.0, "summary statistics wrong")

    model_spec = {
        "schema": "physical-lab-model-spec-v1",
        "metadata": {"name": "Fixture oscillator", "description": "fixture"},
        "compute": {"entry_function": "simulate", "calling_convention": "keyword-arguments"},
        "parameters": [
            {"name": "omega", "label": "Angular frequency", "default": 2.0, "required": False, "type": "number", "unit": "rad/s", "control": "slider", "min": 0.5, "max": 5.0},
            {"name": "steps", "label": "Steps", "default": 100, "required": False, "type": "number", "unit": None, "control": "number", "min": None, "max": None},
        ],
        "outputs": [{"name": "time", "label": "Time", "kind": "vector"}, {"name": "position", "label": "Position", "kind": "vector"}],
        "visualizations": [{"kind": "line", "title": "Position vs time", "outputs": ["time", "position"]}],
    }
    guidance = viz.model_spec_guidance(model_spec)
    require(guidance["name"] == "Fixture oscillator", "ModelSpec metadata lost")
    require(guidance["parameters"][0]["min"] == 0.5 and guidance["parameters"][0]["max"] == 5.0, "ModelSpec parameter range lost")
    require(guidance["visualizations"][0]["kind"] == "line", "ModelSpec visualization hint lost")
    compatible = viz.scan_parameter_compatibility(guidance, ["omega", "duration"])
    require(compatible[0]["adapter_compatible"] is True, "compatible ModelSpec parameter rejected")
    require(compatible[1]["adapter_compatible"] is False, "incompatible ModelSpec parameter accepted")
    try:
        viz.model_spec_guidance({"schema": "unknown/v1", "parameters": [], "outputs": []})
    except ValueError:
        pass
    else:
        raise AssertionError("unknown ModelSpec schema was accepted")

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
    print("PASS: Visualization Studio numeric discovery, ModelSpec guidance, sweep metrics and bounded DIY scans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
