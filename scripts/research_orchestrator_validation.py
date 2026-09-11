from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_research_orchestrator import (
    cartesian_parameter_grid,
    compare_numeric_runs,
    convergence_diagnostics,
    parse_numeric_table,
)


def main() -> None:
    design = cartesian_parameter_grid([
        {"name":"a","low":0.0,"high":1.0,"count":3,"scale":"linear"},
        {"name":"b","low":1.0,"high":1000.0,"count":4,"scale":"log"},
    ])
    assert design["point_count"] == 12
    bvals = design["axes"][1]["values"]
    ratios = [bvals[i+1]/bvals[i] for i in range(len(bvals)-1)]
    assert max(ratios)-min(ratios) < 1e-12

    table = parse_numeric_table(b"h,error,label\n0.4,0.16,a\n0.2,0.04,b\n0.1,0.01,c\n0.05,bad,d\n", filename="study.csv")
    assert table["row_count"] == 4
    assert table["column_data"]["error"][-1] is None
    assert "label" not in table["numeric_columns"]

    conv = convergence_diagnostics([0.4,0.2,0.1,0.05], [0.16,0.04,0.01,0.0025])
    assert abs(float(conv["observed_order"])-2.0) < 1e-12
    assert float(conv["loglog_r2"]) > 0.999999999999

    comp = compare_numeric_runs([
        {"rmse":2.0,"cost":10.0},
        {"rmse":1.5,"cost":12.0},
        {"rmse":2.5,"cost":8.0},
    ], baseline_index=0)
    assert abs(float(comp["rows"][1]["delta::rmse"])+0.5) < 1e-12
    assert abs(float(comp["rows"][1]["relative_delta::rmse"])+0.25) < 1e-12
    assert abs(float(comp["rows"][2]["delta::cost"])+2.0) < 1e-12

    print("Research Orchestrator validation: PASS")


if __name__ == "__main__":
    main()
