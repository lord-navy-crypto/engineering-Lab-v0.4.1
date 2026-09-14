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
    import physical_lab_utube_experiment_ui as v

    geom = v._reference_geometry(bend_points=121)
    require(set(geom["segment"]) == {"left-leg", "bend", "right-leg"}, "geometry segments missing")
    bend = geom[geom["segment"] == "bend"]
    require(len(bend) == 121, "bend point count changed")
    require(np.isfinite(bend[["x_m", "z_m"]].to_numpy()).all(), "geometry contains non-finite coordinates")
    require(abs(float(bend.iloc[0]["x_m"]) + u.geometry()["R_m"]) < 1e-12, "left bend endpoint mismatch")
    require(abs(float(bend.iloc[-1]["x_m"]) - u.geometry()["R_m"]) < 1e-12, "right bend endpoint mismatch")

    profile = v._effective_potential_profile(260.0, points=241)
    require(len(profile) == 241, "effective-potential point count changed")
    require(profile["relative_potential_J_kg"].min() >= -1e-12, "relative potential must be shifted non-negative")
    require(np.isfinite(profile["relative_potential_J_kg"]).all(), "potential contains non-finite values")

    state = v._capacity_decomposition(3.0, 260.0, nq=40)
    require(state["capacity_total_ml"] > 0, "total capacity invalid")
    require(abs(state["capacity_total_ml"] - state["capacity_curved_ml"] - state["capacity_legs_ml"]) < 1e-9, "capacity decomposition is inconsistent")
    require(abs(state["capacity_margin_ml"] - (state["capacity_total_ml"] - 3.0)) < 1e-12, "capacity margin mismatch")
    require(abs(state["threshold_margin_rpm"] - (260.0 - state["threshold_rpm"])) < 1e-12, "threshold margin mismatch")

    nc = u.critical_speed()
    ng = u.threshold(3.0, nq=32)
    phase = v._threshold_phase_map([3.0], [max(1.0, nc - 5.0), 0.5 * (nc + ng), ng, ng + 10.0], nq=32, near_threshold_band_rpm=1.0)
    regimes = list(phase["regime"])
    require(regimes[0] == "below-angular-bifurcation", "n_c regime classification failed")
    require(regimes[1] == "between-nc-and-ng", "between-threshold regime classification failed")
    require(regimes[2] == "near-finite-volume-threshold", "near n_g regime classification failed")
    require(regimes[3] == "above-finite-volume-threshold", "above n_g regime classification failed")
    require("not experimental observations" in v.VISUALIZATION_BOUNDARY, "visualization evidence boundary weakened")

    print("PASS: U-tube reference geometry, effective potential, capacity anatomy and threshold phase map")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
