#!/usr/bin/env python3
"""Deterministic CI contract for the BetterBoard Magnet Bench 03 bridge.

The production bridge validator recomputes BetterBoard field-comparison evidence
with Engineering Lab's canonical digital-twin core. This contract exercises that
CLI end to end with a small analytic fixture and, critically, verifies that a
numerically tampered bridge is rejected rather than silently accepted.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "betterboard_magnet_bridge_validation.py"


def run_validator(residual_csv: Path, bridge: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(residual_csv),
            "--bridge",
            str(bridge),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="physical-lab-betterboard-bridge-") as temp_dir:
        temp = Path(temp_dir)
        residual_csv = temp / "magnet03_residuals.csv"
        bridge = temp / "physical_lab_field_bridge.json"
        out = temp / "engineering_lab_magnet_bridge_validation.json"

        # Analytic identity fixture: measured == model at z = 0, 1, 2 mm.
        # The residual metrics are exactly zero, both trapezoidal integrals are 4,
        # the field-series R^2 is 1, and the affine discrepancy fit is identity.
        with residual_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["position_mm", "measured_uT", "model_uT"])
            writer.writeheader()
            writer.writerows(
                [
                    {"position_mm": 0.0, "measured_uT": 1.0, "model_uT": 1.0},
                    {"position_mm": 1.0, "measured_uT": 2.0, "model_uT": 2.0},
                    {"position_mm": 2.0, "measured_uT": 3.0, "model_uT": 3.0},
                ]
            )

        comparison = {
            "mae_uT": 0.0,
            "rmse_uT": 0.0,
            "bias_uT": 0.0,
            "max_abs_error_uT": 0.0,
            "relative_rmse": 0.0,
            "r2": 1.0,
            "measured_peak_abs_uT": 3.0,
            "model_peak_abs_uT": 3.0,
            "measured_integral_uT_mm": 4.0,
            "model_integral_uT_mm": 4.0,
            "integral_difference_uT_mm": 0.0,
            "residual_standard_deviation_uT": 0.0,
            "affine_discrepancy_fit": {
                "scale": 1.0,
                "offset_uT": 0.0,
                "rmse_before_uT": 0.0,
                "rmse_after_uT": 0.0,
                "r2_after": 1.0,
            },
        }
        bridge.write_text(json.dumps({"comparison": comparison}, indent=2) + "\n", encoding="utf-8")

        passing = run_validator(residual_csv, bridge, out)
        if passing.returncode != 0:
            print("Expected untampered BetterBoard bridge to PASS.", file=sys.stderr)
            print(passing.stdout, file=sys.stderr)
            print(passing.stderr, file=sys.stderr)
            return 1
        passing_evidence = json.loads(out.read_text(encoding="utf-8"))
        if passing_evidence.get("status") != "PASS" or not all(
            passing_evidence.get("cross_application_checks", {}).values()
        ):
            print("Untampered bridge did not produce complete PASS evidence.", file=sys.stderr)
            return 1

        # Negative control: alter one claimed BetterBoard metric while leaving the
        # residual rows unchanged. Engineering Lab must fail closed on the mismatch.
        tampered = json.loads(bridge.read_text(encoding="utf-8"))
        tampered["comparison"]["rmse_uT"] = 0.5
        bridge.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

        failing = run_validator(residual_csv, bridge, out)
        if failing.returncode == 0:
            print("Expected tampered BetterBoard bridge to FAIL.", file=sys.stderr)
            return 1
        failing_evidence = json.loads(out.read_text(encoding="utf-8"))
        checks = failing_evidence.get("cross_application_checks", {})
        if failing_evidence.get("status") != "FAIL" or checks.get("rmse_uT") is not False:
            print("Tampered bridge failed for the wrong reason or did not expose rmse_uT mismatch.", file=sys.stderr)
            return 1

    print("BetterBoard magnet bridge contract: PASS (valid evidence accepted; tampering rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
