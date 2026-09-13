#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_scientific_visualization as sv
    from physical_lab_result_contracts import make_uncertainty

    require(sv.axis_label("x", "m") == "x [m]", "axis unit label failed")
    converted = sv.convert_series([1.0, 2.0], "m", "mm")
    require(converted == [1000.0, 2000.0], "length conversion failed")
    try:
        sv.convert_series([1.0], "s", "m")
    except ValueError:
        pass
    else:
        raise AssertionError("incompatible unit conversion was accepted")

    result = {"schema": "physical-lab-heat-cn-v1", "x": [0.0, 1.0], "numerical": [1.0, 2.0]}
    meta = sv.field_metadata(result, "x")
    require(meta["registered"] and meta["unit"] == "m", "result contract metadata missing")

    uq1 = make_uncertainty(estimate=10.0, unit="V", standard_uncertainty=0.5, method="fixture")
    uq2 = make_uncertainty(estimate=5.0, unit="A", interval=(4.5, 5.8), coverage_probability=0.95, method="fixture")
    rows = sv.uncertainty_records({"a": uq1, "nested": {"b": uq2}})
    require(len(rows) == 2 and all(r["valid"] for r in rows), "native UQ discovery failed")
    p1 = sv.uncertainty_plot_record(rows[0])
    require(p1["error_plus"] is not None and p1["error_plus"] >= 0, "standard uncertainty plotting failed")
    interval_record = next(r for r in rows if r.get("interval"))
    p2 = sv.uncertainty_plot_record(interval_record)
    require(abs(p2["error_minus"] - 0.5) < 1e-12 and abs(p2["error_plus"] - 0.8) < 1e-12, "interval error arrays failed")

    frame = pd.DataFrame({
        "x": [0.0, 1.0, 2.0, 3.0],
        "p": [1.0, 2.0, 3.0, 4.0],
        "q": [4.0, 3.0, 2.0, 1.0],
        "y": [2.0, 4.0, 6.0, 8.0],
    })
    local = sv.local_sensitivity(frame, "p", "y")
    require(len(local) == 3 and all(abs(v - 2.0) < 1e-12 for v in local["sensitivity"]), "local sensitivity failed")
    screening = sv.standardized_sensitivity(frame, ["p", "q"], "y")
    require(set(screening["parameter"]) == {"p", "q"}, "standardized sensitivity screening failed")

    grid = pd.DataFrame({
        "a": [0, 0, 1, 1],
        "b": [0, 1, 0, 1],
        "z": [1.0, 2.0, 3.0, 4.0],
    })
    surface = sv.response_surface(grid, "a", "b", "z")
    require(surface["grid_cells"] == 4 and surface["coverage"] == 4, "response surface grid failed")
    sparse = sv.response_surface(grid.iloc[:3], "a", "b", "z")
    require(sparse["grid_cells"] == 4 and sparse["coverage"] == 3, "missing response cell was invented")

    require("not causality" in sv.BOUNDARY.lower(), "scientific visualization boundary missing")
    print("PASS: unit-aware contracts, native UQ, sensitivity and response-surface semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
