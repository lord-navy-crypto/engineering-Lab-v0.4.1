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
    import physical_lab_utube_experiment as u

    geom = u.geometry()
    require(abs(geom["R_in_m"] - 15.12e-3) < 1e-12, "R_in fixture changed")
    require(abs(geom["a_m"] - 7.48e-3) < 1e-12, "tube radius fixture changed")
    require(abs(geom["ell_m"] - 30.08e-3) < 1e-12, "outer geometry fixture changed")
    require(abs(u.critical_speed() - 172.42204982235918) < 1e-8, "critical-speed fixture changed")

    angles = pd.DataFrame({"n_rpm": [200, 210], "theta_deg": [-30.0, 40.0]})
    views = u.angle_views(angles)
    require(views["theta_deg_signed"].tolist() == [-30.0, 40.0], "signed angle was not preserved")
    require(views["theta_deg_magnitude"].tolist() == [30.0, 40.0], "angle magnitude was not explicit")
    require(views["theta_deg"].tolist() == [-30.0, 40.0], "source angle field was mutated")

    contract = u.validate_dataset(angles, role="equilibrium-angle-micro")
    contract2 = u.validate_dataset(angles.copy(), role="equilibrium-angle-micro")
    require(contract["sha256"] == contract2["sha256"], "dataset identity is not deterministic")
    require(contract["units"]["theta_deg"] == "deg", "angle unit contract missing")

    total, curved, legs = u.capacity(260.0, nq=48)
    require(total > 0 and curved >= 0 and legs >= 0, "capacity components must be nonnegative")
    require(abs(total - (curved + legs)) < 1e-8, "capacity decomposition does not close")
    n3 = u.threshold(3.0, nq=48)
    require(n3 > u.critical_speed(), "3 mL capacity threshold must exceed angular bifurcation")
    require(abs(u.capacity(n3, nq=48)[0] - 3.0) < 1e-7, "threshold root does not reproduce requested volume")

    crossing = u.vstar(260.0, 54.54, 48.9)
    require(crossing > 0, "V* must be positive")
    require(abs(float(u.delta_free_energy(crossing, 260.0, 54.54, 48.9))) < 1e-12, "ΔF(V*) must be zero within numerical precision")

    convergence = u.quadrature_convergence([1.0, 3.0], nq_values=(32, 48, 64))
    require(len(convergence) == 6, "convergence table row count mismatch")
    require(set(convergence.columns) >= {"V_mL", "nq", "threshold_rpm", "delta_from_previous_rpm"}, "convergence contract incomplete")

    obj = u.scientific_object({"fixture": "validation"})
    require(obj["authority"]["ai_execution"] is False, "OpenPenguin execution authority leaked into U-tube object")
    require(obj["authority"]["mutation_authority"] is False, "OpenPenguin mutation authority leaked into U-tube object")
    require(any("Signed" in rule or "signed" in rule for rule in obj["interpretation_constraints"]), "signed-angle interpretation boundary missing")
    require("Numerical convergence" in u.BOUNDARY, "numerical/physical validation boundary missing")

    print("PASS: U-tube contracts, signed-angle semantics, 3D capacity, threshold root, free-energy crossing and numerical convergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
