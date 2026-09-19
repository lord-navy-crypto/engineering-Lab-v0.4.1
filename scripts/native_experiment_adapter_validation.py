#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "src-tauri" / "resources" / "native_experiment_runner.py"
spec = importlib.util.spec_from_file_location("native_experiment_runner", RUNNER)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

CASES = {
    "numerical-methods": {"xMax": 1.5, "order": 7, "points": 101},
    "ising-monte-carlo": {"size": 8, "temperature": 2.269, "sweeps": 20, "seed": 7},
    "random-walk-monte-carlo": {"steps": 30, "walkers": 120, "dimension": 2, "seed": 7},
    "nonlinear-chaos": {"duration": 5, "dt": 0.05, "damping": 0.2, "drive": 1.2, "driveOmega": 0.6666667},
    "oscillation-integration": {"duration": 3, "dt": 0.02, "omega0": 2, "zeta": 0.08, "force": 0.6, "driveOmega": 1.6},
    "radia-magnet-studio": {"periodMm": 50, "b0T": 0.15, "periods": 5, "samples": 81},
    "radiation-platform": {"periodMm": 50, "K": 0.7, "energyGeV": 3, "harmonic": 1, "periods": 10},
    "kerr-geodesics": {"spin": 0.5, "inclinationDeg": 10, "particleType": "massive", "periapsis": 7, "apoapsis": 9, "lambdaMax": 2, "samples": 200},
    "solar-system-dynamics": {"durationYears": 0.1, "samples": 100, "inclinationDeg": 5, "maxStepYears": 0.01},
    "honeycomb-lattice": {"nx": 2, "ny": 2, "layers": 1, "stacking": "AA", "duration": 1, "samples": 100, "driveAmplitude": 0.02},
    "utube-studio": {"volumeMl": 1.0, "rpm": 260, "rinMm": 15.12, "radiusMm": 7.48, "nq": 12},
    "kerr-shadow": {"spin": 0.7, "inclinationDeg": 45, "curveSamples": 120},
    "undulator-spectrum": {"periodMm": 50, "gamma": 1000, "K": 0.7, "periods": 10, "harmonic": 1, "thetaMaxMrad": 0.5},
    "frequency-response": {"omegaN": 2, "zeta": 0.05, "force": 1, "frequencyStart": 1.0, "frequencyStop": 2.8, "frequencyPoints": 7, "settleCycles": 4, "observeCycles": 3, "pointsPerCycle": 32},
}

assert set(CASES) == set(runner.HANDLERS), (set(CASES), set(runner.HANDLERS))

for experiment_id, params in CASES.items():
    payload = runner.HANDLERS[experiment_id](params, "safe")
    assert payload["schema"] == runner.SCHEMA
    assert payload["experimentId"] == experiment_id
    assert isinstance(payload.get("metrics"), dict)
    assert isinstance(payload.get("series"), list) and payload["series"], f"{experiment_id}: no series"
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip()
    for series in payload["series"]:
        xs, ys = series.get("x", []), series.get("y", [])
        assert len(xs) == len(ys) and len(xs) >= 2, f"{experiment_id}/{series.get('id')}: invalid series length"
        assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in xs), f"{experiment_id}: non-finite x"
        assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in ys), f"{experiment_id}: non-finite y"
    print(f"PASS {experiment_id}: {payload['backend']}")

print("Native experiment adapter smoke suite: PASS 14/14")
