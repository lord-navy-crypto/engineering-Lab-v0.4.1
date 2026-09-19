#!/usr/bin/env python3
"""Independent Engineering Lab validation of BetterBoard Magnet Bench 03 evidence.

This script intentionally recomputes BetterBoard field-comparison evidence
with Engineering Lab's canonical digital-twin core instead of trusting BetterBoard's
summary. It is a cross-application V&V step, not an automatic claim that the
measurement or RADIA model is physically correct.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_digital_twin.py"
spec = importlib.util.spec_from_file_location("physical_lab_digital_twin", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load Engineering Lab digital-twin core: {CORE_PATH}")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

SCALAR_KEYS = {
    "mae_uT": "mae",
    "rmse_uT": "rmse",
    "bias_uT": "bias",
    "max_abs_error_uT": "max_abs_error",
    "relative_rmse": "relative_rmse",
    "r2": "r2",
    "measured_peak_abs_uT": "measured_peak_abs",
    "model_peak_abs_uT": "model_peak_abs",
    "measured_integral_uT_mm": "measured_integral",
    "model_integral_uT_mm": "model_integral",
    "integral_difference_uT_mm": "integral_difference",
    "residual_standard_deviation_uT": "residual_standard_deviation",
}
AFFINE_KEYS = {
    "scale": "scale",
    "offset_uT": "offset",
    "rmse_before_uT": "rmse_before",
    "rmse_after_uT": "rmse_after",
    "r2_after": "r2_after",
}
BOUNDARY = (
    "PASS means Engineering Lab independently reproduced BetterBoard's numerical field-comparison metrics "
    "for the supplied rows. It does not prove sensor calibration, position registration, magnet geometry, "
    "material assumptions, or model validity."
)


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


def read_residual_csv(path: Path) -> tuple[list[float], list[float], list[float]]:
    position: list[float] = []
    measured: list[float] = []
    model: list[float] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"position_mm", "measured_uT", "model_uT"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError(f"Expected {sorted(expected)} in {path}; got {reader.fieldnames}")
        for row_number, row in enumerate(reader, start=2):
            try:
                x = float(row["position_mm"])
                m = float(row["measured_uT"])
                p = float(row["model_uT"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Residual CSV row {row_number} contains a non-numeric required value") from exc
            if not (math.isfinite(x) and math.isfinite(m) and math.isfinite(p)):
                raise ValueError(f"Residual CSV row {row_number} contains a non-finite required value")
            position.append(x)
            measured.append(m)
            model.append(p)
    if len(position) < 2:
        raise ValueError("At least two finite residual rows are required")
    return position, measured, model


def close(a: Any, b: Any, *, rtol: float = 1e-9, atol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        aa = float(a)
        bb = float(b)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(aa) or not math.isfinite(bb):
        return aa == bb
    return abs(aa - bb) <= atol + rtol * max(abs(aa), abs(bb))


def bridge_checks(source_bridge: Any, comparison: Any, affine: Any) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    if not isinstance(source_bridge, dict):
        return {"bridge_object": False}, ["Bridge root must be a JSON object"]

    summary = source_bridge.get("comparison")
    checks["comparison_object"] = isinstance(summary, dict)
    if not isinstance(summary, dict):
        return checks, ["Bridge must contain a comparison object"]

    missing_scalars = sorted(set(SCALAR_KEYS) - set(summary))
    checks["comparison_required_fields"] = not missing_scalars
    if missing_scalars:
        errors.append(f"Missing comparison fields: {', '.join(missing_scalars)}")

    for bridge_key, attr in SCALAR_KEYS.items():
        checks[bridge_key] = bridge_key in summary and close(summary.get(bridge_key), getattr(comparison, attr))

    fit = summary.get("affine_discrepancy_fit")
    checks["affine_object"] = isinstance(fit, dict)
    if not isinstance(fit, dict):
        errors.append("Bridge comparison must contain an affine_discrepancy_fit object")
        fit = {}

    missing_affine = sorted(set(AFFINE_KEYS) - set(fit))
    checks["affine_required_fields"] = not missing_affine
    if missing_affine:
        errors.append(f"Missing affine fields: {', '.join(missing_affine)}")

    for bridge_key, attr in AFFINE_KEYS.items():
        check_key = f"affine_{bridge_key.removesuffix('_uT')}"
        checks[check_key] = bridge_key in fit and close(fit.get(bridge_key), getattr(affine, attr))
    return checks, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("residual_csv", type=Path, help="BetterBoard magnet03_residuals.csv")
    parser.add_argument("--bridge", type=Path, help="optional BetterBoard physical_lab_field_bridge.json")
    parser.add_argument("--out", type=Path, default=Path("engineering_lab_magnet_bridge_validation.json"))
    args = parser.parse_args()

    base_evidence: dict[str, Any] = {
        "schema": "engineering-lab-betterboard-magnet-bridge-validation-v1",
        "source_residual_csv": str(args.residual_csv),
        "source_bridge": str(args.bridge) if args.bridge else None,
        "recomputed_with": "physical_lab_digital_twin.py",
        "boundary": BOUNDARY,
    }

    try:
        position, measured, model = read_residual_csv(args.residual_csv)
        comparison = core.compare_field_series(position, measured, model)
        affine = core.fit_model_affine(measured, model)
        suggestions = core.suggest_residual_measurement_points(position, measured, model, count=3) if len(position) >= 3 else []
    except (OSError, ValueError, TypeError) as exc:
        evidence = {
            **base_evidence,
            "input_integrity": "FAIL",
            "errors": [str(exc)],
            "recomputed": None,
            "cross_application_checks": {},
            "status": "FAIL",
        }
        write_evidence(args.out, evidence)
        return 1

    recomputed = {
        "field_comparison": comparison.to_dict(),
        "affine_model_fit": affine.to_dict(),
        "suggested_residual_measurement_points": suggestions,
    }

    checks: dict[str, bool] = {}
    errors: list[str] = []
    if args.bridge:
        try:
            source_bridge = json.loads(args.bridge.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Could not read bridge JSON: {exc}")
            checks["bridge_json"] = False
        else:
            checks["bridge_json"] = True
            contract_checks, contract_errors = bridge_checks(source_bridge, comparison, affine)
            checks.update(contract_checks)
            errors.extend(contract_errors)

    status = "PASS" if (not checks or all(checks.values())) and not errors else "FAIL"
    evidence = {
        **base_evidence,
        "input_integrity": "PASS",
        "errors": errors,
        "recomputed": recomputed,
        "cross_application_checks": checks,
        "status": status,
    }
    write_evidence(args.out, evidence)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
