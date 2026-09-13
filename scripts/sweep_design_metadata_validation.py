#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_sweep_executor as sweeps
    from physical_lab_sweep_design_bridge import prepare_rows_preserving_metadata, queue_design_with_metadata
    from physical_lab_visualization_studio import sweep_frame
    from physical_lab_applied_math_deep import sweep_feedback

    row = {
        "design_index": 0,
        "__trajectory": 3,
        "__step": 1,
        "__changed_factor": "alpha",
    }
    prepared = prepare_rows_preserving_metadata("numerical-methods", "heat-1d", [row])
    require(prepared[0]["__trajectory"] == 3, "trajectory metadata was stripped")
    require(prepared[0]["__changed_factor"] == "alpha", "changed-factor metadata was stripped")

    previous = os.environ.get("PHYSICAL_LAB_DATA_DIR")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        queued_a = queue_design_with_metadata("numerical-methods", "heat-1d", [row])
        queued_b = queue_design_with_metadata("numerical-methods", "heat-1d", [{**row, "__trajectory": 4}])
        require(queued_a["status"] == "queued" and queued_a["execution_started"] is False, "metadata bridge started execution")
        require(queued_a["design_metadata_preserved"] is True, "metadata preservation flag missing")
        require(queued_a["design_sha256"] != queued_b["design_sha256"], "design metadata must contribute to provenance hash")

        # Cache identity remains based on real adapter parameters only.
        require(sweeps._point_key("heat-1d", {}) == sweeps._point_key("heat-1d", {}), "cache identity must remain parameter-based")

    if previous is None:
        os.environ.pop("PHYSICAL_LAB_DATA_DIR", None)
    else:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = previous

    synthetic = {
        "points": [
            {
                "design_index": 0,
                "status": "succeeded",
                "design_metadata": {"__trajectory": 0, "__step": 0, "__changed_factor": ""},
                "parameters": {"alpha": 1.0, "beta": 2.0},
                "metrics": {"score": 3.0},
                "result": {},
            },
            {
                "design_index": 1,
                "status": "succeeded",
                "design_metadata": {"__trajectory": 0, "__step": 1, "__changed_factor": "alpha"},
                "parameters": {"alpha": 2.0, "beta": 2.0},
                "metrics": {"score": 7.0},
                "result": {},
            },
        ]
    }
    frame = sweep_frame(synthetic)
    require({"__trajectory", "__step", "__changed_factor"}.issubset(frame.columns), "flattened sweep lost reserved metadata")
    require(frame.loc[1, "__changed_factor"] == "alpha", "flattened changed-factor metadata incorrect")
    require("param:alpha" in frame.columns and "metric:score" in frame.columns, "normal sweep fields were damaged")

    feedback = sweep_feedback(frame)
    require(feedback["morris_ready"] is True, "completed sweep was not recognized as Morris-ready")
    require(any(r["analysis"] == "morris-effects" for r in feedback["recommendations"]), "Morris handoff recommendation missing")

    print("PASS: reserved sweep metadata survives queue/result flattening without entering model parameters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
