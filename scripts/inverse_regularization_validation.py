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
    import physical_lab_inverse_regularization as ir

    rng = np.random.default_rng(12)
    x = np.linspace(-2.0, 2.0, 90)
    x2 = x + rng.normal(0.0, 0.01, len(x))
    y = 1.2 + 2.5 * x - 1.7 * x2 + rng.normal(0.0, 0.03, len(x))
    frame = pd.DataFrame({"x1": x, "x2": x2, "y": y})

    path = ir.tsvd_path(frame, ["x1", "x2"], "y")
    require(list(path["rank"]) == [1, 2], "TSVD path did not enumerate retained ranks")
    r1 = ir.truncated_svd_regression(frame, ["x1", "x2"], "y", rank=1)
    r2 = ir.truncated_svd_regression(frame, ["x1", "x2"], "y", rank=2)
    require(r2["data_residual_norm"] <= r1["data_residual_norm"] + 1e-10, "retaining an additional singular component increased least-squares residual unexpectedly")
    require(len(r2["coefficients"]) == 3, "TSVD coefficient contract incorrect")

    gcv_path = ir.tikhonov_gcv_path(frame, ["x1", "x2"], "y", lambdas=np.logspace(-8, 3, 48))
    require(len(gcv_path) == 48, "GCV path length incorrect")
    require(np.isfinite(gcv_path["gcv"]).any(), "GCV path has no finite score")
    gcv = ir.gcv_choice(gcv_path)
    require(gcv["regularization"] > 0 and np.isfinite(gcv["gcv"]), "GCV candidate invalid")

    curved = ir.lcurve_curvature(gcv_path)
    require("lcurve_curvature" in curved.columns, "L-curve curvature column missing")
    choice = ir.lcurve_choice(gcv_path)
    require(choice["regularization"] > 0 and choice["curvature"] >= 0, "L-curve candidate invalid")
    require(np.isnan(curved.iloc[0]["lcurve_curvature"]) and np.isnan(curved.iloc[-1]["lcurve_curvature"]), "L-curve endpoint curvature should be unavailable")

    require("not proof of physical identifiability" in ir.BOUNDARY, "inverse regularization scientific boundary missing")

    ui_text = (UI / "physical_lab_inverse_regularization_ui.py").read_text(encoding="utf-8")
    require("start_sweep_job" not in ui_text, "analysis handoff must not start a sweep")
    require("pl_analysis_handoff_" in ui_text, "analysis handoff state contract missing")
    require("No execution or new evidence was created" in ui_text, "handoff boundary message missing")

    print("PASS: TSVD, GCV, L-curve diagnostics and view-only sweep handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
