#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
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
    import physical_lab_applied_analysis as aa

    frame = pd.DataFrame({
        "x": np.arange(1.0, 11.0),
        "z": np.arange(1.0, 11.0) ** 2,
        "y": 2.0 + 3.0 * np.arange(1.0, 11.0),
    })
    reg = aa.regression_diagnostics(frame, ["x"], "y")
    require(reg["r2"] > 0.999999, "linear regression fit failed")
    slope = next(x for x in reg["coefficients"] if x["term"] == "x")["estimate"]
    require(abs(slope - 3.0) < 1e-10, "linear regression coefficient failed")
    require({"residual", "leverage", "cooks_distance"}.issubset(reg["diagnostics"].columns), "regression diagnostics missing")

    poly = aa.polynomial_regression(frame, "x", "z", degree=2)
    require(poly["r2"] > 0.999999, "polynomial regression failed")

    boot1 = aa.bootstrap_statistic(frame["y"], statistic="mean", resamples=500, seed=7)
    boot2 = aa.bootstrap_statistic(frame["y"], statistic="mean", resamples=500, seed=7)
    require(boot1["interval"] == boot2["interval"], "bootstrap seed is not deterministic")
    require(boot1["interval"][0] <= boot1["estimate"] <= boot1["interval"][1], "bootstrap interval does not contain fixture estimate")

    mc = aa.monte_carlo_propagation(means=[1.0, 2.0], standard_uncertainties=[0.1, 0.2], coefficients=[2.0, -1.0], samples=1000, seed=3)
    require(abs(mc["mean"]) < 0.05, "Monte Carlo propagated mean is inconsistent with fixture")

    factors = [{"name": "a", "low": 0.0, "high": 1.0}, {"name": "b", "low": 10.0, "high": 20.0}]
    factorial = aa.design_experiment(factors, method="full-factorial")
    require(factorial["row_count"] == 4, "2-factor full factorial should have four rows")
    lhs1 = aa.design_experiment(factors, method="latin-hypercube", samples=8, seed=9)
    lhs2 = aa.design_experiment(factors, method="latin-hypercube", samples=8, seed=9)
    require(lhs1["design"].equals(lhs2["design"]), "Latin hypercube seed is not deterministic")
    require(lhs1["design"]["a"].between(0.0, 1.0).all(), "DOE escaped factor bounds")

    fit = aa.estimate_parameters(frame, "x", "y", model="linear")
    fitted_slope = next(x for x in fit["parameters"] if x["name"] == "slope")["estimate"]
    require(abs(fitted_slope - 3.0) < 1e-8, "safe parameter estimation failed")
    try:
        aa.estimate_parameters(frame, "x", "y", model="arbitrary-python")
    except ValueError:
        pass
    else:
        raise AssertionError("arbitrary model execution was accepted")

    with tempfile.TemporaryDirectory() as tmp:
        saved = aa.save_analysis_artifact(Path(tmp), kind="regression", source_identity={"id": "fixture"}, configuration={"x": "x", "y": "y"}, summary={"r2": reg["r2"]})
        path = Path(saved["path"])
        require(path.exists(), "applied-analysis artifact not written")
        record = json.loads(path.read_text(encoding="utf-8"))
        require(record["schema"] == aa.APPLIED_ANALYSIS_SCHEMA, "applied-analysis artifact schema mismatch")

    require("do not by themselves establish causality" in aa.BOUNDARY, "scientific boundary missing")
    print("PASS: regression, residual diagnostics, bootstrap, Monte Carlo, DOE, safe parameter estimation and reproducible artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
