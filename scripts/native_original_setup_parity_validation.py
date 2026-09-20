#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

RADIA_REPO = "lord-navy-crypto/radia-magnet-studio"
RADIA_REVISION = "3bceb02a5195a6eb14d01458cc44f7206ed6b40a"
RADIATION_REPO = "lord-navy-crypto/simulator-radiation-planfotm"
RADIATION_REVISION = "6d19b36304c9d30f9b608214f7cfb9fcbaf941d4"

RADIA_ORIGINAL_CONTROLS = [
    "Built-in preset","Type","Period λu (mm)","Number of periods","Magnetic gap (mm)",
    "Blocks per period","Block width x (mm)","Block height / radial thickness (mm)",
    "Longitudinal fill factor","Remanent induction Br (T)","Calibrate Br to target B0",
    "Target B0 (T)","B0 definition","Magnet model","μr parallel","μr perpendicular",
    "Magnet subdivision","Run RADIA relaxation","Relaxation precision (T)",
    "Relaxation max iterations","Ellipticity","APPLE-II magnetic row phase (deg)",
    "APPLE-II shift mode","Enable manufacturing errors","Field amplitude error σ (%)",
    "Longitudinal position error σ (mm)","Transverse position error σ (mm)",
    "Magnetization angle error σ (deg)","Gap asymmetry (mm)","Bank strength imbalance (%)",
    "Random seed","Compute ideal-vs-error comparison","On-axis samples",
    "Longitudinal field margin (periods)","Electron energy (GeV)",
    "Calculate 2D field slice","Calculate sparse 3D field map",
    "Transverse map half-width (mm)","Maximum blocks in 3D geometry viewer",
]

RADIATION_ORIGINAL_CONTROLS = [
    "Saved Stage-1 model used by Stage 2","Field model","Insertion device",
    "Third-harmonic field coefficient H3/H1","Fifth-harmonic field coefficient H5/H1",
    "Period λu (mm)","Generated field target","Manual target central B0 (T)","Gap (mm)",
    "Block tangential width (mm)","Block height / radial thickness (mm)","Ellipticity",
    "APPLE-II row phase (deg)","APPLE-II shift mode","RADIA magnet model","μr parallel",
    "μr perpendicular","Magnet subdivision","Map transverse half-width (mm)","Map Nx = Ny",
    "Map z samples / period","Fringe-field margin (periods)","Electron γ","Undulator periods",
    "Observer distance (m)","Observer θx (mrad)","Observer θy (mrad)",
    "Independent scan variable","Scalar scan points across selected range",
    "Representative full-analysis rows","Representative-row strategy","Scan plot set",
    "Tracking resolution","Error mode","Manufacturing-error seed","Field-amplitude σ (%)",
    "Longitudinal-position σ (µm)","Transverse-position σ (µm)",
    "Magnetization-angle σ (mrad)","Gap asymmetry (µm)","Bank imbalance (%)",
    "Field amplitude error","Longitudinal position / phase error","Transverse placement error",
    "Magnetization angle error","Gap / bank asymmetry","Bank strength imbalance",
    "Error source to sweep","Error-strength scan points","Maximum strength relative to nominal",
    "Also run ideal baseline","Core radiation summary","Spectrum + linewidth / Q",
    "Stokes polarization","Radiation harmonics H3/H1, H5/H1","3D electron trajectory",
    "Trajectory / phase diagnostics","Field quality diagnostics","1D angular scan",
    "2D angular map","One-error-at-a-time sensitivity","Numerical convergence",
    "Observer-distance validation","Energy accounting","Quantum χ monitor","Advanced chaos / MLE",
    "CSV magnetic period λu (mm)","Show single-device z-axis field preview",
    "Speed minimum β = v/c","Speed maximum β = v/c","γ min","γ max","K min","K max",
    "N min","N max","R min (m)","R max (m)","θx min (mrad)","θx max (mrad)",
    "Deep-analysis scan point",
]

native = Path("web/native-experiments.js").read_text(encoding="utf-8")
runner = Path("src-tauri/resources/native_experiment_runner.py").read_text(encoding="utf-8")
modules = Path("src-tauri/resources/modules.json").read_text(encoding="utf-8")


def schema_labels(experiment_id: str) -> list[str]:
    marker = f"  '{experiment_id}':["
    starts = [m.start() for m in re.finditer(re.escape(marker), native)]
    labels: list[str] = []
    for start in starts:
        end = native.find("  ],", start)
        if end < 0:
            raise AssertionError(f"schema block for {experiment_id} is unterminated")
        labels.extend(re.findall(r"label:'([^']+)'", native[start:end]))
    return sorted(set(labels))


def norm(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[σ()·↔/_\-–—]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def missing(original: list[str], current: list[str]) -> list[str]:
    current_norm = [norm(value) for value in current]
    out: list[str] = []
    for label in original:
        target = norm(label)
        if not any(target == value or target in value or value in target for value in current_norm):
            out.append(label)
    return out


radia_labels = schema_labels("radia-magnet-studio")
radiation_labels = schema_labels("radiation-platform")
radia_missing = missing(RADIA_ORIGINAL_CONTROLS, radia_labels)
radiation_missing = missing(RADIATION_ORIGINAL_CONTROLS, radiation_labels)

assert len(RADIA_ORIGINAL_CONTROLS) == 39
assert len(RADIATION_ORIGINAL_CONTROLS) == 81
assert not radia_missing, f"pinned RADIA setup controls missing natively: {radia_missing}"
assert not radiation_missing, f"pinned Radiation controls missing natively: {radiation_missing}"

for marker in (
    RADIA_REPO, RADIA_REVISION, RADIATION_REPO, RADIATION_REVISION,
):
    assert marker in modules, f"pinned module provenance missing: {marker}"

for marker in (
    "from radia_support import load_radia",
    "from devices.factory import build_device",
    "from solver.pipeline import solve_model",
    "from calibration.target_b0 import calibrate_br",
    '"pinned-radia-magnet-studio-full-core"',
    "import undulator_v11_radia_integrated_v9 as v11",
    "v11.make_default_undulator",
    "v11.run_sim_scalar",
    '"pinned-radiation-platform-full-core"',
):
    assert marker in runner, f"native Full-mode pinned-core marker missing: {marker}"

for marker in (
    "nativeExperimentResultsStatus",
    "nativeExperimentVerificationStatus",
    "renderNativeVerificationResult",
    "nativeExperimentResultById",
    "Latest native RADIA run",
    "applyNativeRadiaPreset",
):
    assert marker in native or marker in Path("web/index.html").read_text(encoding="utf-8"), marker

print(
    "Pinned Original Workspace setup parity: PASS "
    f"RADIA={len(RADIA_ORIGINAL_CONTROLS)}/{len(RADIA_ORIGINAL_CONTROLS)} "
    f"Radiation={len(RADIATION_ORIGINAL_CONTROLS)}/{len(RADIATION_ORIGINAL_CONTROLS)} "
    "missing=0"
)
print("Pinned Full-mode core migration validation: PASS RADIA Magnet Studio + Radiation Platform")
