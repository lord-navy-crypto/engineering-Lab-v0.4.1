#!/usr/bin/env python3
# Final 14/14 native execution gate: every adapter must return finite structured results.
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
    "numerical-methods": {"xMin": -1.5, "xMax": 1.5, "points": 61, "method": "range_reduced", "maxTerms": 40, "referencePrecisionDigits": 50},
    "ising-monte-carlo": {"size": 6, "temperature": 2.269, "seed": 7, "equilibrationSweeps": 8, "measurementSweeps": 12, "measureEvery": 1, "recordEvery": 2, "scanMethod": "metropolis"},
    "random-walk-monte-carlo": {"steps": 30, "walkers": 120, "dimension": 2, "seed": 7, "trajectorySteps": 20},
    "nonlinear-chaos": {"duration": 1.5, "dt": 0.02, "damping": 0.0, "mass1": 1.0, "mass2": 1.0, "length1": 1.0, "length2": 1.0},
    "oscillation-integration": {"duration": 2, "dt": 0.02, "omega0": 2, "gamma": 0.08, "force": 0.2, "driveOmega": 1.6, "method": "rk4"},
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

TOOL_CASES = [
    ("numerical-methods", "single-point-convergence", {"singleX": 1.0, "convergenceTerms": 20, "method": "range_reduced", "maxTerms": 40, "referencePrecisionDigits": 50}),
    ("numerical-methods", "method-comparison", {"xMin": -1.0, "xMax": 1.0, "points": 31, "maxTerms": 40, "referencePrecisionDigits": 50}),
    ("ising-monte-carlo", "multi-chain", {"size": 4, "temperature": 2.5, "seed": 3, "equilibrationSweeps": 4, "measurementSweeps": 8, "measureEvery": 1, "scanMethod": "metropolis"}),
    ("random-walk-monte-carlo", "convergence-scan", {"sampleCounts": "50,100", "trialsPerCount": 3, "seed": 3}),
    ("random-walk-monte-carlo", "reproducibility", {"dimension": 2, "multiSeedSteps": 20, "walkersPerSeed": 40, "independentSeeds": 3, "seed": 3, "auditStepModel": "fixed", "fixedStep": 1.0}),
    ("nonlinear-chaos", "lyapunov-convergence", {"mass1": 1.0, "mass2": 1.0, "length1": 1.0, "length2": 1.0, "gravity": 9.81, "damping": 0.0, "theta1": 1.0, "theta2": 0.8, "lyapunovDuration": 1.0, "lyapunovDt": 0.02}),
    ("oscillation-integration", "timestep-scan", {"mass": 1.0, "omega0": 2.0, "gamma": 0.0, "force": 0.0, "driveOmega": 1.6, "x0": 1.0, "v0": 0.0, "duration": 1.0, "dtMin": 0.01, "dtMax": 0.04, "scanPoints": 4, "method": "rk4"}),
    ("kerr-geodesics", "refinement", {"spin": 0.5, "inclinationDeg": 10, "particleType": "massive", "periapsis": 7, "apoapsis": 9, "lambdaMax": 2, "samples": 200}),
    ("solar-system-dynamics", "ftle", {"durationYears": 0.2, "samples": 100, "inclinationDeg": 5, "maxStepYears": 0.01, "ftleSegmentYears": 0.05, "ftleMaxYears": 0.2}),
    ("honeycomb-lattice", "normal-modes", {"nx": 2, "ny": 2, "layers": 1, "stacking": "AA"}),
    ("honeycomb-lattice", "phonon-dos", {"nx": 2, "ny": 2, "layers": 1, "stacking": "AA", "phononQGrid": 4, "phononBins": 16}),
    ("undulator-spectrum", "beam-broadening", {"periodMm": 50, "gamma": 1000, "K": 0.7, "harmonic": 1, "beamSamples": 2000, "beamBins": 40}),
    ("frequency-response", "duffing", {"omega0": 1, "zeta": 0.05, "force": 0.3, "cubicStiffness": 1, "frequencyStart": 0.8, "frequencyStop": 1.2, "frequencyPoints": 7, "settleCycles": 4, "observeCycles": 3, "pointsPerCycle": 32}),
    ("utube-studio", "operating-state", {"volumeMl": 1.0, "rpm": 260, "rinMm": 15.12, "radiusMm": 7.48, "nq": 12}),
    ("utube-studio", "elasticity", {"volumeMl": 1.0, "rpm": 260, "rinMm": 15.12, "radiusMm": 7.48, "nq": 12}),
    ("utube-studio", "scan-plan", {"volumeMl": 1.0, "rpm": 260, "rinMm": 15.12, "radiusMm": 7.48, "nq": 12}),
    ("utube-studio", "uncertainty", {"volumeMl": 1.0, "rpm": 260, "rinMm": 15.12, "radiusMm": 7.48, "nq": 12, "uncertaintySamples": 50}),
]

for experiment_id, tool, params in TOOL_CASES:
    payload = runner.run_experiment_tool(experiment_id, tool, params, "safe")
    assert payload["schema"] == runner.SCHEMA
    assert payload["experimentId"] == experiment_id
    assert isinstance(payload.get("metrics"), dict)
    assert isinstance(payload.get("series"), list)
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip()
    for series in payload["series"]:
        xs, ys = series.get("x", []), series.get("y", [])
        assert len(xs) == len(ys), f"{experiment_id}/{tool}/{series.get('id')}: mismatched series length"
        assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in xs)
        assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in ys)
    print(f"PASS TOOL {experiment_id}/{tool}: {payload['backend']}")

print(f"Native deep-tool smoke suite: PASS {len(TOOL_CASES)}/{len(TOOL_CASES)}")



base_context = runner.HANDLERS["numerical-methods"]({"xMin": -1.5, "xMax": 1.5, "points": 61, "method": "range_reduced", "maxTerms": 40, "referencePrecisionDigits": 50}, "safe")
GLOBAL_TOOL_CASES = [
    ("result-inspector", {}),
    ("bootstrap", {"bootstrapResamples": 200, "bootstrapConfidence": 0.95, "analysisSeed": 7}),
    ("regression", {}),
    ("robust-regression", {"huberDelta": 1.345}),
    ("convergence-diagnostics", {}),
]
for tool, extra in GLOBAL_TOOL_CASES:
    params = {"contextResult": base_context, **extra}
    payload = runner.run_global_analysis_tool("numerical-methods", tool, params)
    assert payload["schema"] == runner.SCHEMA
    assert payload["experimentId"] == "numerical-methods"
    assert isinstance(payload.get("metrics"), dict) and payload["metrics"], tool
    assert isinstance(payload.get("series"), list)
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip()
    print(f"PASS GLOBAL TOOL {tool}: {payload['backend']}")
print(f"Native global analysis smoke suite: PASS {len(GLOBAL_TOOL_CASES)}/{len(GLOBAL_TOOL_CASES)}")


WORKFLOW_TOOL_CASES = [
    ("visualization-summary", {}),
    ("visualization-transform", {"transformMode": "z-score"}),
    ("local-sensitivity", {}),
    ("elasticity-sensitivity", {}),
    ("standardized-sensitivity", {}),
]
workflow_context = runner.HANDLERS["numerical-methods"]({"xMin": -1.5, "xMax": 1.5, "points": 61, "method": "range_reduced", "maxTerms": 40, "referencePrecisionDigits": 50}, "safe")
for tool, extra in WORKFLOW_TOOL_CASES:
    payload = runner.run_global_analysis_tool("numerical-methods", tool, {"contextResult": workflow_context, **extra})
    assert payload["schema"] == runner.SCHEMA
    assert payload["experimentId"] == "numerical-methods"
    assert isinstance(payload.get("metrics"), dict) and payload["metrics"], tool
    assert isinstance(payload.get("series"), list)
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip()
    print(f"PASS WORKFLOW TOOL {tool}: {payload['backend']}")
print(f"Native workflow analysis smoke suite: PASS {len(WORKFLOW_TOOL_CASES)}/{len(WORKFLOW_TOOL_CASES)}")


FINAL_RESTORATION_UTUBE_TOOLS = [
    "dimensionless-groups","inverse-geometry","design-space","robust-design","adaptive-plan",
    "verification-requirements","research-questions","uncertainty-budget",
    "hysteresis-analysis","rate-sweep","digital-twin-calibration","digital-twin-field","beam-phase-space"
]
for tool in FINAL_RESTORATION_UTUBE_TOOLS:
    payload = runner.run_experiment_tool("utube-studio", tool, {
        "volumeMl":3.0,"rpm":260.0,"rinMm":15.12,"radiusMm":7.48,"nq":24,
        "rhoKgM3":997.8,"gammaMnM":72.0,"thetaDeg":0.0,
        "uVolumeMl":0.05,"uRpm":1.0,"uRinMm":0.2,"uRadiusMm":0.1,
        "targetThresholdRpm":250.0,"responseTau":0.2,"quasiStaticHalfwidth":1.0,
        "betaGamma":1.0
    }, "safe")
    assert payload["schema"] == runner.SCHEMA, tool
    assert payload["experimentId"] == "utube-studio", tool
    assert isinstance(payload.get("metrics"), dict), tool
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip(), tool
    print(f"PASS FINAL RESTORATION TOOL {tool}: {payload['backend']}")
print(f"Final restoration U-Tube smoke suite: PASS {len(FINAL_RESTORATION_UTUBE_TOOLS)}/{len(FINAL_RESTORATION_UTUBE_TOOLS)}")


NATIVE_ANALYSIS_BATCH_TOOLS = [
    "polynomial-regression",
    "monte-carlo-propagation",
    "doe-design",
    "parameter-estimation",
    "polynomial-cv",
    "pca-svd",
    "conditioning-diagnostics",
    "tikhonov",
    "tsvd",
    "correlation-matrix",
    "pareto-frontier",
    "robust-sensitivity",
    "run-comparison",
    "morris-design",
]
analysis_context = runner.HANDLERS["numerical-methods"]({"xMin": -2.0, "xMax": 2.0, "points": 81, "method": "range_reduced", "maxTerms": 40, "referencePrecisionDigits": 50}, "safe")
for tool in NATIVE_ANALYSIS_BATCH_TOOLS:
    payload = runner.run_global_analysis_tool("numerical-methods", tool, {
        "contextResult": analysis_context,
        "analysisSeed": 11,
        "monteCarloSamples": 1200,
        "doeSamples": 16,
        "morrisTrajectories": 4,
        "morrisLevels": 6,
        "polynomialDegree": 2,
        "regularization": 1e-3,
        "tsvdRank": 1,
    })
    assert payload["schema"] == runner.SCHEMA, tool
    assert payload["experimentId"] == "numerical-methods", tool
    assert isinstance(payload.get("metrics"), dict), tool
    assert isinstance(payload.get("series"), list), tool
    assert isinstance(payload.get("boundary"), str) and payload["boundary"].strip(), tool
    print(f"PASS NATIVE ANALYSIS TOOL {tool}: {payload['backend']}")
print(f"Native audit/deep-analysis smoke suite: PASS {len(NATIVE_ANALYSIS_BATCH_TOOLS)}/{len(NATIVE_ANALYSIS_BATCH_TOOLS)}")
