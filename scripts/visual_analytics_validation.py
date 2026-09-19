#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_visual_analytics as va
    import physical_lab_visual_analytics_ui as vau

    a = pd.DataFrame({"x": [1, 2, 3], "y": [10.0, 20.0, 30.0], "note": ["a", "b", "c"]})
    b = pd.DataFrame({"x": [4, 5], "y": [40, 50], "other": [1.0, 2.0]})
    common = va.common_numeric_columns([a, b])
    require(common == ["x", "y"], f"unexpected common numeric columns: {common}")

    frame = pd.DataFrame({
        "t": [0.0, 1.0, 2.0],
        "signal": [10.0, 12.0, 15.0],
        "signal_sigma": [0.5, 0.6, 0.8],
        "signal_lower": [9.0, 10.5, 13.0],
        "signal_upper": [11.0, 13.5, 17.0],
    })
    hints = va.uncertainty_candidates(frame.columns, "signal")
    require("signal_sigma" in hints["symmetric"], "symmetric uncertainty hint missing")
    require("signal_lower" in hints["lower"], "lower-bound hint missing")
    require("signal_upper" in hints["upper"], "upper-bound hint missing")

    symmetric = va.uncertainty_error_arrays(frame, "signal", symmetric="signal_sigma")
    require(symmetric["array"] == [0.5, 0.6, 0.8], "symmetric error array changed")
    require(symmetric["arrayminus"] == [0.5, 0.6, 0.8], "symmetric minus error array changed")

    asymmetric = va.uncertainty_error_arrays(frame, "signal", lower="signal_lower", upper="signal_upper")
    require(asymmetric["array"] == [1.0, 1.5, 2.0], "upper error distances wrong")
    require(asymmetric["arrayminus"] == [1.0, 1.5, 2.0], "lower error distances wrong")

    invalid = frame.copy()
    invalid["bad_sigma"] = [0.1, -0.2, 0.3]
    try:
        va.uncertainty_error_arrays(invalid, "signal", symmetric="bad_sigma")
    except ValueError:
        pass
    else:
        raise AssertionError("negative uncertainty was accepted")

    overlay = va.overlay_frame([("A", a), ("B", b)], "x", "y")
    require(len(overlay) == 5, "overlay row count wrong")
    require(list(overlay["source"]) == ["A", "A", "A", "B", "B"], "overlay source identity changed")
    require(list(overlay["source_row"]) == [0, 1, 2, 0, 1], "overlay source-row identity changed")

    selection = {"selection": {"points": [{"point_index": 2}, {"pointNumber": 0}, {"point_index": 2}, {"point_index": 99}]}}
    require(va.selection_indices(selection, 3) == [2, 0], "selection decoder did not deduplicate/bound indices")

    # Multi-trace Plotly point indices are local to each trace. The linked-view UI
    # must prefer explicit customdata carrying the global row position.
    linked_selection = {
        "selection": {
            "points": [
                {"point_index": 0, "customdata": [3]},
                {"point_index": 1, "customdata": 4},
                {"point_index": 0, "customdata": [3]},
            ]
        }
    }
    require(vau._linked_selection_indices(linked_selection, 5) == [3, 4], "linked-view selection ignored global customdata row identity")

    panels = [
        {"kind": "uncertainty-plot", "source": {"id": "dataset:a"}, "x": "t", "y": "signal", "error_mode": "Symmetric field", "symmetric": "signal_sigma"},
        {"kind": "multi-source-overlay", "sources": [{"id": "dataset:a"}, {"id": "dataset:b"}], "x": "x", "y": "y"},
    ]
    first_id, first_sha = va.dashboard_identity("Study A", panels)
    second_id, second_sha = va.dashboard_identity("Study A", panels)
    require(first_id == second_id and first_sha == second_sha, "dashboard identity is not deterministic")

    with tempfile.TemporaryDirectory() as tmp:
        saved = va.save_dashboard(Path(tmp), title="Study A", panels=panels)
        path = Path(saved["path"])
        require(path.exists(), "dashboard recipe was not written")
        require(path.parent.name == "visual-analytics-dashboards", "dashboard path is outside expected reports subtree")
        again = va.save_dashboard(Path(tmp), title="Study A", panels=panels)
        require(saved["dashboard_id"] == again["dashboard_id"], "same dashboard produced a new identity")

    require("not evidence" in va.BOUNDARY.lower(), "scientific boundary missing")
    print("PASS: Visual Analytics uncertainty, overlay, selection and dashboard contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
