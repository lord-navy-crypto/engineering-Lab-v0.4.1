#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_applied_math_deep as deep

    x = np.linspace(-3.0, 3.0, 80)
    frame = pd.DataFrame({"x": x, "x2": 2.0 * x + 0.01 * np.sin(x), "noise": np.sin(4*x)})
    pca = deep.pca_svd(frame, ["x", "x2", "noise"], standardize=True)
    require(pca["effective_rank"] >= 2, "PCA effective rank unexpectedly low")
    require(pca["explained_variance_ratio"][0] > 0.60, "PCA failed to capture the strong shared linear structure")
    require(abs(sum(pca["explained_variance_ratio"]) - 1.0) < 1e-10, "explained variance does not sum to one")

    collinear = pd.DataFrame({"a": x, "b": 2.0*x, "c": -3.0*x})
    cond = deep.conditioning_diagnostics(collinear, ["a", "b", "c"], center=True)
    require(cond["rank"] == 1, "conditioning diagnostics failed to detect rank deficiency")
    require(not cond["full_column_rank"], "rank-deficient matrix reported full column rank")

    rng = np.random.default_rng(5)
    p1 = rng.normal(size=120)
    p2 = p1 + rng.normal(scale=0.02, size=120)
    y = 2.0 + 3.0*p1 - 1.0*p2 + rng.normal(scale=0.05, size=120)
    inverse_frame = pd.DataFrame({"p1": p1, "p2": p2, "y": y})
    low = deep.tikhonov_regression(inverse_frame, ["p1", "p2"], "y", regularization=1e-8, standardize=True)
    high = deep.tikhonov_regression(inverse_frame, ["p1", "p2"], "y", regularization=100.0, standardize=True)
    require(high["regularization_norm"] < low["regularization_norm"], "larger Tikhonov regularization did not shrink coefficient norm")
    path = deep.regularization_path(inverse_frame, ["p1", "p2"], "y", lambdas=[0.0, 0.01, 1.0, 100.0])
    require(list(path["regularization"]) == [0.0, 0.01, 1.0, 100.0], "regularization path ordering failed")

    sweep = pd.DataFrame({
        "param:a": [0, 0, 1, 1],
        "param:b": [0, 1, 0, 1],
        "metric:error": [4.0, 3.0, 2.5, 1.0],
        "result:$.power": [1.0, 2.0, 3.0, 4.0],
    })
    feedback = deep.sweep_feedback(sweep)
    require(set(feedback["two_level_parameters"]) == {"param:a", "param:b"}, "two-level sweep parameters not detected")
    analyses = {r["analysis"] for r in feedback["recommendations"]}
    require("factorial-effects" in analyses, "factorial feedback missing")
    require("response-surface" in analyses, "response-surface feedback missing")
    require("sensitivity-screening" in analyses, "sensitivity feedback missing")
    require(not feedback["morris_ready"], "ordinary sweep was incorrectly classified as Morris-ready")

    require("do not establish causality" in deep.BOUNDARY, "deep applied-math scientific boundary missing")
    print("PASS: PCA/SVD, conditioning, Tikhonov regularization and completed-sweep feedback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
