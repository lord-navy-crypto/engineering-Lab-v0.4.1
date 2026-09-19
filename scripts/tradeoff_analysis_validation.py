#!/usr/bin/env python3
from __future__ import annotations

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
    import physical_lab_tradeoff_analysis as ta

    frame = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0],
        "b": [2.0, 4.0, 6.0, 8.0],
        "c": [4.0, 3.0, 2.0, 1.0],
    })
    pearson = ta.correlation_matrix(frame, ["a", "b", "c"], method="pearson")
    require(abs(float(pearson.loc["a", "b"]) - 1.0) < 1e-12, "expected perfect positive correlation")
    require(abs(float(pearson.loc["a", "c"]) + 1.0) < 1e-12, "expected perfect negative correlation")
    spearman = ta.correlation_matrix(frame, ["a", "c"], method="spearman")
    require(abs(float(spearman.loc["a", "c"]) + 1.0) < 1e-12, "Spearman correlation wrong")

    trade = pd.DataFrame({
        "cost": [1.0, 2.0, 3.0, 4.0, 2.0],
        "quality": [1.0, 4.0, 5.0, 5.5, 4.0],
    })
    frontier = ta.pareto_frontier(trade, x="cost", x_goal="min", y="quality", y_goal="max")
    pareto_rows = set(int(i) for i in frontier.loc[frontier["pareto"], "source_index"])
    require(pareto_rows == {0, 1, 2, 3, 4}, f"unexpected frontier for improving quality trade-off: {pareto_rows}")

    dominated_case = pd.DataFrame({
        "cost": [1.0, 2.0, 3.0, 2.0],
        "error": [5.0, 4.0, 6.0, 4.0],
    })
    result = ta.pareto_frontier(dominated_case, x="cost", x_goal="min", y="error", y_goal="min")
    pareto_rows = set(int(i) for i in result.loc[result["pareto"], "source_index"])
    require(pareto_rows == {0, 1, 3}, f"dominated point handling wrong: {pareto_rows}")
    require(not bool(result.loc[result["source_index"] == 2, "pareto"].iloc[0]), "dominated point was marked Pareto")

    flipped = ta.pareto_frontier(dominated_case, x="cost", x_goal="max", y="error", y_goal="min")
    flipped_rows = set(int(i) for i in flipped.loc[flipped["pareto"], "source_index"])
    require(2 in flipped_rows, "objective direction flip was ignored")

    boundary = ta.BOUNDARY.lower()
    require("not causal" in boundary, "correlation boundary missing")
    require("non-dominance" in boundary, "Pareto boundary missing")
    print("PASS: correlation and two-objective Pareto trade-off analysis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
