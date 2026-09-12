from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_sweep_executor import (
    available_adapters,
    create_sweep_job,
    read_sweep_result,
    read_sweep_job,
    run_job,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = td

        adapters = {x["id"] for x in available_adapters("oscillation-integration")}
        assert "pid-step" in adapters

        rows = [
            {"design_index": 0, "kp": 6.0},
            {"design_index": 1, "kp": 9.0},
        ]
        first = create_sweep_job("oscillation-integration", "pid-step", rows)
        code = run_job(Path(td) / "research-sweeps" / first["id"])
        assert code == 0
        result = read_sweep_result(first["id"])
        assert result is not None
        assert result["succeeded_points"] == 2
        assert result["failed_points"] == 0
        assert result["cached_points"] == 0
        assert all(point["status"] == "succeeded" for point in result["points"])
        assert all("overshoot_pct" in point["metrics"] for point in result["points"])

        second = create_sweep_job("oscillation-integration", "pid-step", rows)
        code = run_job(Path(td) / "research-sweeps" / second["id"])
        assert code == 0
        result2 = read_sweep_result(second["id"])
        assert result2 is not None
        assert result2["cached_points"] == 2
        assert all(point["cached"] is True for point in result2["points"])

        mixed = create_sweep_job(
            "oscillation-integration",
            "pid-step",
            [
                {"design_index": 0, "kp": 8.0},
                {"design_index": 1, "not_a_parameter": 1.0},
                {"design_index": 2, "kp": 10.0},
            ],
        )
        code = run_job(Path(td) / "research-sweeps" / mixed["id"])
        assert code == 0
        mixed_result = read_sweep_result(mixed["id"])
        assert mixed_result is not None
        assert mixed_result["succeeded_points"] == 2
        assert mixed_result["failed_points"] == 1
        assert [p["status"] for p in mixed_result["points"]] == ["succeeded", "failed", "succeeded"]
        final_job = read_sweep_job(mixed["id"])
        assert final_job is not None and final_job["status"] == "succeeded"

    print("Sweep Executor validation: PASS")


if __name__ == "__main__":
    main()
