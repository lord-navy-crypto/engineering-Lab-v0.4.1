#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_utube_uncertainty as uq

    means = {
        "volume_ml": 3.0,
        "n_rpm": 260.0,
        "rin_m": 0.01512,
        "a_m": 0.00748,
        "rho_kg_m3": 997.8,
        "gamma_mN_m": 54.54,
        "theta_deg": 48.9,
    }
    std = {
        "volume_ml": 0.02,
        "n_rpm": 0.5,
        "rin_m": 2e-5,
        "a_m": 1e-5,
        "rho_kg_m3": 0.2,
        "gamma_mN_m": 0.2,
        "theta_deg": 0.2,
    }
    a = uq.propagate_uncertainty(means, std, samples=32, seed=7, nq=32)
    b = uq.propagate_uncertainty(means, std, samples=32, seed=7, nq=32)
    require(a["samples_succeeded"] > 0, "Monte Carlo propagation produced no samples")
    require(a["outputs"]["n_g_rpm"]["sd"] is not None and a["outputs"]["n_g_rpm"]["sd"] > 0, "n_g uncertainty did not propagate")
    require(a["outputs"]["n_g_rpm"] == b["outputs"]["n_g_rpm"], "seeded propagation is not deterministic")
    require(a["assumptions"]["input_distributions"] == "independent Normal", "distribution assumption missing")

    budget = uq.local_uncertainty_budget(means, std, output="n_g_rpm", nq=32)
    require(not budget.empty, "uncertainty budget is empty")
    require(abs(float(budget["fraction_of_variance_proxy"].sum()) - 1.0) < 1e-10, "budget fractions do not normalize")
    require(set(budget["parameter"]).issubset(set(means)), "budget contains unknown parameter")

    pred = [row["n_g_rpm"] for row in a["records"] if "n_g_rpm" in row]
    check = uq.predictive_interval_check([250.0, 251.0, 249.5], pred)
    require(check["predictive_p2_5"] <= check["predictive_p97_5"], "predictive interval is inverted")
    require("model-form" in uq.BOUNDARY, "model-form uncertainty boundary missing")

    print("PASS: U-tube Monte Carlo uncertainty, local budget and predictive interval comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
