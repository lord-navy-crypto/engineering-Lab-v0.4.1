#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "web" / "native-experiments.js").read_text(encoding="utf-8")
UTUBE = (ROOT / "web" / "utube-native.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
RUNNER = (ROOT / "src-tauri" / "resources" / "native_experiment_runner.py").read_text(encoding="utf-8")


def object_block(name: str, next_name: str | None = None) -> str:
    start = NATIVE.index(f"const {name} = Object.freeze(")
    if next_name:
        end = NATIVE.index(f"const {next_name} = Object.freeze(", start)
    else:
        end = len(NATIVE)
    return NATIVE[start:end]


PRIMARY = object_block("NATIVE_PARAMETER_SCHEMAS", "NATIVE_ADVANCED_PARAMETER_SCHEMAS")
ADVANCED = object_block("NATIVE_ADVANCED_PARAMETER_SCHEMAS", "NATIVE_GLOBAL_TOOL_SPECS")
TOOLS = object_block("NATIVE_TOOL_SPECS", None)
VERIFY = object_block("NATIVE_VERIFICATION_TOOL_MAP", "NATIVE_TOOL_SPECS")


def entry(block: str, experiment_id: str) -> str:
    marker = f"  '{experiment_id}':["
    start = block.find(marker)
    if start < 0:
        return ""
    next_entry = block.find("\n  '", start + len(marker))
    end = next_entry if next_entry >= 0 else len(block)
    return block[start:end]


def field_names(experiment_id: str) -> set[str]:
    text = entry(PRIMARY, experiment_id) + "\n" + entry(ADVANCED, experiment_id)
    return set(re.findall(r"name:'([^']+)'", text))


def tool_ids(experiment_id: str) -> set[str]:
    return set(re.findall(r"id:'([^']+)'", entry(TOOLS, experiment_id)))


REQUIRED_FIELDS = {
    "numerical-methods": {
        "method","dtype","referenceBackend","referencePrecisionDigits","toleranceMultiplier","maxTerms",
        "xMin","xMax","points","singleX","convergenceTerms",
    },
    "ising-monte-carlo": {
        "dimension","size","coupling","field","temperature","seed","equilibrationSweeps","measurementSweeps",
        "measureEvery","scanMethod","comparisonEquilibration","comparisonMeasurement","diagnosticCycles",
        "recordEvery","tMin","tMax","scanPoints","useNotebookMesh","latticeSizes","initialCondition","snapshotSweeps",
    },
    "random-walk-monte-carlo": {
        "seed","dimension","steps","walkers","stepModel","trajectorySteps","baseStepModel","scanVariable","scanValues",
        "baseDimension","baseSteps","baseWalkers","baseFixedStep","baseUniformA","baseUniformB","samplesPerTrial",
        "independentTrials","sampleCounts","trialsPerCount","pseudoRandomSamples","qmcPower","qmcScrambles","horizon",
        "independentTrajectories","boundaryMagnitude","trials","maxSteps","grid2d","grid3d","multiSeedSteps",
        "walkersPerSeed","independentSeeds","auditStepModel","fixedStep","uniformA","uniformB","presetJson",
    },
    "nonlinear-chaos": {
        "mass1","mass2","length1","length2","gravity","theta1","omega1","theta2","omega2","driveMin","driveMax",
        "amplitudeScanPoints","drivePeriods","discardPeriods","rk4StepsPerPeriod","kapitzaMaxAmplitude",
        "driveFrequency","damping","kapitzaTotalPeriods","kapitzaDiscardedPeriods","duration","dt","mass1Min",
        "mass1Max","massScanPoints","massScanDuration","massScanDt","lyapunovDuration","lyapunovDt",
        "flipGrid","flipMaxTime","flipDt",
    },
    "oscillation-integration": {
        "mass","omega0","gamma","force","driveOmega","x0","v0","duration","dt","method","dtMin","dtMax","scanPoints",
        "resonanceGamma","resonanceForce","frequencyScanPoints","omegaRatioMin","omegaRatioMax","maxInitialAngle",
        "amplitudeScanPoints","singleNonlinearTheta0",
    },
    "radia-magnet-studio": {
        "builtInPreset","device","periodMm","periods","gapMm","blocksPerPeriod","blockWidthMm","blockHeightMm",
        "longitudinalFill","brT","targetB0Enabled","targetB0T","b0Definition","materialMode","muParallel",
        "muPerpendicular","segmentation","relax","precision","maxIter","ellipticity","applePhaseDeg","appleShiftMode",
        "errorsEnabled","fieldErrorPct","longitudinalErrorMm","transverseErrorMm","angleErrorDeg","gapAsymmetryMm",
        "bankImbalancePct","errorSeed","compareIdeal","axisSamples","fieldMarginPeriods","electronEnergyGeV",
        "calculate2d","calculate3d","transverseHalfWidthMm","geometryLimit",
    },
    "radiation-platform": {
        "fieldModel","devicePreset","periodMm","gamma","periods","observerDistanceM","thetaXMrad","thetaYMrad",
        "scanVariable","scanPoints","representativeCount","trackingPointsPerPeriod","errorMode","manufacturingSeed",
        "fieldSigmaPct","longitudinalSigmaUm","transverseSigmaUm","angleSigmaMrad","gapAsymmetryUm","bankSigmaPct",
        "showCore","showSpectrum","showPolarization","showHarmonics","showTrajectory","showPhase","showFieldQuality",
        "showAngular1d","showAngular2d","showErrorRanking","showConvergence","showFarfield","showEnergy","showQuantum",
        "showChaos","deepAnalysisScanPoint",
    },
    "kerr-geodesics": {
        "spin","inclinationDeg","particleType","periapsis","apoapsis","lambdaMax","samples","comparisonSpin",
        "comparisonInclinationDeg","sweepParticle","sweepSpinsText","sweepInclinationDeg","rtol","atol",
    },
    "solar-system-dynamics": {
        "durationYears","samples","inclinationDeg","saturnBackreaction","solar1pn","maxStepYears","velocityCross",
        "radialDrag","velocityCrossStrength","radialDragStrength","rtol","atol","ftleD0","ftleSegmentYears","ftleMaxYears",
    },
    "honeycomb-lattice": {
        "nx","ny","layers","stacking","strainX","driveAmplitude","driveFrequency","duration","bondLength","layerSpacing",
        "mass","kIn","alpha","kInter","betaInter","interlayerDamping","defectMode","defectMassMultiplier",
        "defectBondScale","driveMode","uniformForceX","stochasticMode","temperatureReduced","seed","initialDisplacement",
        "samples","rtol","atol","maxStep","langevinDt","phononPointsPerSegment","phononQGrid","phononBins",
    },
    "kerr-shadow": {"sweepDepth","observerInclinationsText","spin","inclinationDeg","curveSamples"},
    "undulator-spectrum": {
        "periodMm","gamma","K","periods","harmonic","thetaMaxMrad","observationAngleMrad","harmonicsText",
        "angularPoints","relativeEnergySpreadRms","angularDivergenceRmsMrad","beamSamples","beamSeed","beamBins",
    },
    "frequency-response": {
        "omegaN","zeta","force","linearStartRatio","linearStopRatio","linearSweepQuality","omega0","cubicStiffness",
        "duffingForce","duffingStartRatio","duffingStopRatio","duffingSweepQuality","settleCycles","observeCycles",
        "pointsPerCycle",
    },
}

REQUIRED_TOOLS = {
    "numerical-methods": {"parameter-scan","single-point-convergence","method-comparison","compliance"},
    "ising-monte-carlo": {"method-comparison","equilibration","multi-chain","scan-1d","scan-2d","finite-size","snapshot","compliance"},
    "random-walk-monte-carlo": {"ensemble","trajectory","parameter-scan","repeated-mc","convergence-scan","high-d-mc","qmc","theory-volume","return-probability","first-passage","grid-vs-mc","reproducibility","validate-preset"},
    "nonlinear-chaos": {"driven-scan","kapitza-scan","double-trajectory","mass-response","lyapunov","lyapunov-convergence","flip-map","compliance"},
    "oscillation-integration": {"method-comparison","timestep-scan","damping-regimes","resonance-scan","beat-analysis","nonlinear-amplitude","compliance"},
    "kerr-geodesics": {"refinement","comparison","spin-sweep"},
    "solar-system-dynamics": {"refinement","ftle"},
    "honeycomb-lattice": {"normal-modes","phonon-dispersion","phonon-dos"},
    "kerr-shadow": {"morphology-sweep"},
    "undulator-spectrum": {"angular-map","beam-broadening"},
    "frequency-response": {"duffing"},
}

BACKEND_MARKERS = {
    "numerical-methods": "pinned-numerical_lab.scan_sine",
    "ising-monte-carlo": "pinned-ising_lab.simulate",
    "random-walk-monte-carlo": "pinned-rw_mc_studio.simulate_endpoints",
    "nonlinear-chaos": "pinned-chaos_lab.simulate_double_pendulum",
    "oscillation-integration": "pinned-oscillation_lab.simulate_fixed",
    "radia-magnet-studio": "pinned-radia-magnet-studio-full-core",
    "radiation-platform": "pinned-radiation-platform-full-core",
    "kerr-geodesics": "physical_lab_kerr_geodesics",
    "solar-system-dynamics": "physical_lab_solar_system_dynamics",
    "honeycomb-lattice": "physical_lab_lattice_dynamics",
    "utube-studio": "physical_lab_utube_experiment",
    "kerr-shadow": "physical_lab_kerr_shadow",
    "undulator-spectrum": "physical_lab_undulator_spectrum",
    "frequency-response": "physical_lab_frequency_response",
}

errors: list[str] = []

for experiment_id, required in REQUIRED_FIELDS.items():
    current = field_names(experiment_id)
    missing = sorted(required - current)
    if missing:
        errors.append(f"{experiment_id}: missing Setup fields {missing}")

for experiment_id, required in REQUIRED_TOOLS.items():
    current = tool_ids(experiment_id)
    missing = sorted(required - current)
    if missing:
        errors.append(f"{experiment_id}: missing experiment tools {missing}")

for experiment_id in REQUIRED_FIELDS:
    if experiment_id == "utube-studio":
        continue
    if f"'{experiment_id}':[" not in VERIFY:
        errors.append(f"{experiment_id}: missing verification-map entry")

for experiment_id, marker in BACKEND_MARKERS.items():
    if marker not in RUNNER:
        errors.append(f"{experiment_id}: backend provenance marker missing: {marker}")

UTUBE_GROUPS = [
    "Experiment scan & DOE","Research physics & inverse design","Uncertainty & theory ↔ experiment",
    "Robust design & adaptive experiment","Digital twin","Hysteresis & rate envelope",
]
for group in UTUBE_GROUPS:
    if group not in UTUBE:
        errors.append(f"utube-studio: missing setup group {group}")

UTUBE_REQUIRED_FIELDS = {
    "dataRole","volumeMinMl","volumeMaxMl","volumeSamples","speedMinRpm","speedMaxRpm","speedSamples",
    "convergenceVolumesMl","doeFactors","doeMethod","doeSamples","doeSeed","researchDataset","xColumn","yColumn",
    "overlayTheory","modelRinM","modelAM","modelNq","nearThresholdBandRpm","targetThresholdRpm","inverseVolumeMl",
    "solveFor","geometryLowerM","geometryUpperM","designVolumesMl","planningNq","mcSamplesOriginal","mcSeedOriginal",
    "predictiveOutput","budgetOutput","nominalVText","nominalRinText","nominalAText","tolVMl","tolRinM","tolAM",
    "robustTargetRpm","empiricalBracketRpm","observedClassifications","thresholdToleranceRpm","minGapRpm",
    "maxNumericalDeltaRpm","twinDataset","twinRinM","twinAM","twinNq","tauMinS","tauMaxS","rampDataset",
    "hystRinM","hystAM","hystNq","predictionVMl","empiricalHRpm","rateLagTauS","rampRatesText","predictionNq",
}
utube_fields = set(re.findall(r"name:'([^']+)'", UTUBE))
utube_missing = sorted(UTUBE_REQUIRED_FIELDS - utube_fields)
if utube_missing:
    errors.append(f"utube-studio: missing restored setup fields {utube_missing}")

for forbidden in ("full-original-strip", "nativeExperimentOpenOriginalVerification", "utOpenFullOriginal", "utVerificationOpenOriginal"):
    if forbidden in NATIVE or forbidden in INDEX:
        errors.append(f"fallback UI marker still present: {forbidden}")

if "nativeExperimentVerificationActions" not in INDEX:
    errors.append("generic native verification action host missing")

if errors:
    raise AssertionError("\n".join(errors))

field_total = sum(len(v) for v in REQUIRED_FIELDS.values()) + len(UTUBE_REQUIRED_FIELDS)
tool_total = sum(len(v) for v in REQUIRED_TOOLS.values())
print(
    "All-14 Original→Native parity gate: PASS "
    f"experiments=14 required_setup_fields={field_total} required_experiment_tools={tool_total} missing=0"
)
print("All-14 backend provenance gate: PASS 14/14")
print("Original Workspace fallback gate: PASS fallback_markers=0")
