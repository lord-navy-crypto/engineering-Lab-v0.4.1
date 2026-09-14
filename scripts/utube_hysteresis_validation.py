#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_utube_experiment as u
    import physical_lab_utube_hysteresis as h

    base = h.dynamic_branch_thresholds(250.0, 0.0, response_tau_s=0.8, quasi_static_halfwidth_rpm=2.0)
    require(abs(float(base["up_threshold_rpm"]) - 252.0) < 1e-12, "zero-rate spin-up branch changed")
    require(abs(float(base["down_threshold_rpm"]) - 248.0) < 1e-12, "zero-rate spin-down branch changed")
    require(abs(float(base["loop_center_rpm"]) - 250.0) < 1e-12, "dynamic branches must remain centered on static threshold")

    H_TRUE = 1.75
    TAU_TRUE = 0.65
    volumes = [2.5, 2.5, 2.5, 3.0, 3.0, 3.0]
    rates = [0.0, 2.0, 5.0, 0.0, 2.0, 5.0]
    ups = []
    downs = []
    for volume, rate in zip(volumes, rates):
        ng = u.threshold(volume, nq=32)
        row = h.dynamic_branch_thresholds(ng, rate, response_tau_s=TAU_TRUE, quasi_static_halfwidth_rpm=H_TRUE)
        ups.append(float(row["up_threshold_rpm"]))
        downs.append(float(row["down_threshold_rpm"]))

    fit = h.analyze_hysteresis_sweeps(volumes, rates, ups, downs, nq=32)
    require(abs(fit["fit"]["response_tau_s"] - TAU_TRUE) < 1e-10, "synthetic rate-lag tau was not recovered")
    require(abs(fit["fit"]["quasi_static_halfwidth_rpm"] - H_TRUE) < 1e-10, "synthetic quasi-static half-width was not recovered")
    require(fit["fit"]["halfwidth_rmse_rpm"] < 1e-10, "self-consistent hysteresis half-width residual should vanish")
    require(fit["fit"]["center_model_rmse_rpm"] < 1e-8, "self-consistent loop centers should match the static 3-D model")
    require(fit["fit"]["halfwidth_r2"] is not None and fit["fit"]["halfwidth_r2"] > 0.999999999, "synthetic half-width fit lost explanatory power")

    frame = fit["frame"]
    require(len(frame) == 6, "paired hysteresis row count changed")
    require(np.allclose(frame["loop_center_rpm"], frame["model_static_threshold_rpm"], atol=1e-8), "loop-center/static separation changed")
    require(np.all(frame["up_threshold_rpm"] >= frame["down_threshold_rpm"]), "branch ordering invalid")

    envelope = h.rate_sweep_prediction(
        3.0, [0.0, 1.0, 4.0, 10.0], response_tau_s=TAU_TRUE,
        quasi_static_halfwidth_rpm=H_TRUE, nq=32,
    )
    require(len(envelope) == 4, "rate sweep prediction row count changed")
    require(envelope["ramp_rate_rpm_s"].is_monotonic_increasing, "rate sweep prediction is not ordered")
    expected_width = 2.0 * (H_TRUE + TAU_TRUE * envelope["ramp_rate_rpm_s"].to_numpy(float))
    require(np.allclose(envelope["loop_width_rpm"], expected_width, atol=1e-10), "rate-envelope width law changed")

    try:
        h.analyze_hysteresis_sweeps([3, 3, 3], [2, 2, 2], [260, 261, 262], [250, 251, 252], nq=24)
    except ValueError as exc:
        require("ramp-rate variation" in str(exc), "constant-rate identifiability boundary changed")
    else:
        raise AssertionError("constant ramp rate must not identify tau")

    boundary = h.BOUNDARY.lower()
    for phrase in ["not be interpreted as contact-angle hysteresis", "viscosity", "hardware safety margin", "transient fluid-dynamics"]:
        require(phrase in boundary, f"scientific boundary weakened: {phrase}")

    print("PASS: U-tube reduced-order dynamic threshold, hysteresis fitting and rate-envelope validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
