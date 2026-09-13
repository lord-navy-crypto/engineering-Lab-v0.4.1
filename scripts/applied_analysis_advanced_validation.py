#!/usr/bin/env python3
from __future__ import annotations

import os
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
    import physical_lab_applied_analysis_advanced as aa

    x = np.linspace(-2.0, 2.0, 31)
    y = 1.5 + 2.0 * x
    y[-1] += 30.0
    frame = pd.DataFrame({"x": x, "y": y})
    robust = aa.robust_regression_huber(frame, ["x"], "y")
    require(robust["converged"], "Huber regression did not converge")
    require(robust["downweighted_fraction"] > 0, "Huber regression did not downweight the injected outlier")
    slope = next(r["estimate"] for r in robust["coefficients"] if r["term"] == "x")
    require(abs(slope - 2.0) < 0.15, "Huber slope failed to recover the underlying trend")

    x2 = np.linspace(-3.0, 3.0, 80)
    y2 = 2.0 + 0.5 * x2 + 1.25 * x2 * x2
    cv = aa.cross_validate_polynomials(pd.DataFrame({"x": x2, "y": y2}), "x", "y", degrees=[1, 2, 3], folds=5, seed=7)
    require(not cv.empty and int(cv.iloc[0]["degree"]) in {2, 3}, "cross-validation failed to prefer a quadratic-capable model")

    factorial = pd.DataFrame({
        "a": [-1, -1, 1, 1] * 2,
        "b": [-1, 1, -1, 1] * 2,
    })
    factorial["y"] = 10.0 + 3.0 * factorial["a"] - 2.0 * factorial["b"] + 4.0 * factorial["a"] * factorial["b"]
    effects = aa.factorial_effects(factorial, ["a", "b"], "y", include_interactions=True)
    by_term = {r["term"]: r["effect"] for r in effects["effects"]}
    require(abs(by_term["a"] - 6.0) < 1e-10, "factor A effect incorrect")
    require(abs(by_term["b"] + 4.0) < 1e-10, "factor B effect incorrect")
    require(abs(by_term["a:b"] - 8.0) < 1e-10, "interaction effect incorrect")

    factors = [{"name": "p", "low": 1.0, "high": 3.0}, {"name": "q", "low": 0.0, "high": 2.0}]
    design1 = aa.morris_design(factors, trajectories=5, levels=6, seed=11)
    design2 = aa.morris_design(factors, trajectories=5, levels=6, seed=11)
    require(design1["rows"] == design2["rows"], "Morris design is not deterministic for a fixed seed")
    require(len(design1["rows"]) == 15, "Morris row count must be trajectories * (k + 1)")
    morris_frame = pd.DataFrame(design1["rows"])
    morris_frame["response"] = 4.0 * morris_frame["p"] + 0.5 * morris_frame["q"]
    screened = aa.morris_effects(morris_frame, "response", ["p", "q"])
    require(set(screened["factor"]) == {"p", "q"}, "Morris effects missing factors")
    mu = {r["factor"]: r["mu_star"] for r in screened.to_dict("records")}
    require(mu["p"] > mu["q"], "Morris screening failed to rank the stronger linear factor")

    accepted = aa.adapter_parameter_names("numerical-methods", "heat-1d")
    require(len(accepted) > 0, "allow-listed adapter signature was not discovered")
    prepared = aa.prepare_sweep_rows("numerical-methods", "heat-1d", [{"design_index": 0}])
    require(prepared == [{"design_index": 0}], "minimal queued design was altered unexpectedly")
    try:
        aa.prepare_sweep_rows("numerical-methods", "heat-1d", [{"design_index": 0, "not_a_real_parameter": 1.0}])
    except ValueError:
        pass
    else:
        raise AssertionError("unknown adapter parameter was accepted")

    previous = os.environ.get("PHYSICAL_LAB_DATA_DIR")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        queued = aa.queue_design_as_sweep("numerical-methods", "heat-1d", [{"design_index": 0}])
        require(queued["status"] == "queued", "DOE bridge did not create a queued job")
        require(queued["execution_started"] is False, "DOE bridge started execution implicitly")
        require(queued.get("pid") is None, "queued DOE job unexpectedly has a worker PID")
    if previous is None:
        os.environ.pop("PHYSICAL_LAB_DATA_DIR", None)
    else:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = previous

    require("do not establish causality" in aa.BOUNDARY, "advanced scientific boundary missing")
    print("PASS: robust regression, CV, factorial/Morris screening, and queue-only DOE→Sweep boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
