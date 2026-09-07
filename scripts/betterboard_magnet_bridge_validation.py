#!/usr/bin/env python3
"""Independent Engineering Lab validation of BetterBoard Magnet Bench 03 evidence.

This script intentionally recomputes the field-comparison metrics with
Engineering Lab's canonical digital-twin core instead of trusting BetterBoard's
summary. It is a cross-application V&V step, not an automatic claim that the
measurement or RADIA model is physically correct.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_digital_twin.py"
spec = importlib.util.spec_from_file_location("physical_lab_digital_twin", CORE_PATH)
core = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(core)


def read_residual_csv(path: Path) -> tuple[list[float], list[float], list[float]]:
    position: list[float] = []
    measured: list[float] = []
    model: list[float] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {"position_mm", "measured_uT", "model_uT"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError(f"Expected {sorted(expected)} in {path}; got {reader.fieldnames}")
        for row in reader:
            x = float(row["position_mm"])
            m = float(row["measured_uT"])
            p = float(row["model_uT"])
            if math.isfinite(x) and math.isfinite(m) and math.isfinite(p):
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("residual_csv", type=Path, help="BetterBoard magnet03_residuals.csv")
    parser.add_argument("--bridge", type=Path, help="optional BetterBoard physical_lab_field_bridge.json")
    parser.add_argument("--out", type=Path, default=Path("engineering_lab_magnet_bridge_validation.json"))
    args = parser.parse_args()

    position, measured, model = read_residual_csv(args.residual_csv)
    comparison = core.compare_field_series(position, measured, model)
    affine = core.fit_model_affine(measured, model)
    suggestions = core.suggest_residual_measurement_points(position, measured, model, count=3) if len(position) >= 3 else []

    recomputed = {
        "field_comparison": comparison.to_dict(),
        "affine_model_fit": affine.to_dict(),
        "suggested_residual_measurement_points": suggestions,
    }

    checks: dict[str, bool] = {}
    source_bridge = None
    if args.bridge:
        source_bridge = json.loads(args.bridge.read_text(encoding="utf-8"))
        summary = source_bridge.get("comparison", {})
        mapping = {
            "mae_uT": comparison.mae,
            "rmse_uT": comparison.rmse,
            "bias_uT": comparison.bias,
            "max_abs_error_uT": comparison.max_abs_error,
            "relative_rmse": comparison.relative_rmse,
            "r2": comparison.r2,
            "measured_peak_abs_uT": comparison.measured_peak_abs,
            "model_peak_abs_uT": comparison.model_peak_abs,
            "measured_integral_uT_mm": comparison.measured_integral,
            "model_integral_uT_mm": comparison.model_integral,
            "integral_difference_uT_mm": comparison.integral_difference,
            "residual_standard_deviation_uT": comparison.residual_standard_deviation,
        }
        for key, expected in mapping.items():
            checks[key] = close(summary.get(key), expected)
        fit = summary.get("affine_discrepancy_fit", {})
        checks["affine_scale"] = close(fit.get("scale"), affine.scale)
        checks["affine_offset"] = close(fit.get("offset_uT"), affine.offset)
        checks["affine_rmse_before"] = close(fit.get("rmse_before_uT"), affine.rmse_before)
        checks["affine_rmse_after"] = close(fit.get("rmse_after_uT"), affine.rmse_after)
        checks["affine_r2_after"] = close(fit.get("r2_after"), affine.r2_after)

    status = "PASS" if (not checks or all(checks.values())) else "FAIL"
    evidence = {
        "schema": "engineering-lab-betterboard-magnet-bridge-validation-v1",
        "source_residual_csv": str(args.residual_csv),
        "source_bridge": str(args.bridge) if args.bridge else None,
        "recomputed_with": "physical_lab_digital_twin.py",
        "recomputed": recomputed,
        "cross_application_checks": checks,
        "status": status,
        "boundary": (
            "PASS means Engineering Lab independently reproduced BetterBoard's numerical field-comparison metrics "
            "for the supplied rows. It does not prove sensor calibration, position registration, magnet geometry, "
            "material assumptions, or model validity."
        ),
    }
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
