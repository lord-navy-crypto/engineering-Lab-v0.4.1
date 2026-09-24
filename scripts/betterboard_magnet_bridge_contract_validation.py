#!/usr/bin/env python3
"""Deterministic CI contract for the BetterBoard Magnet Bench 03 bridge.

The production bridge validator recomputes BetterBoard field-comparison evidence
with Engineering Lab's canonical digital-twin core. This contract exercises that
CLI end to end and verifies fail-closed behavior for tampered, malformed, and
non-finite evidence.
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
        [sys.executable, str(VALIDATOR), str(residual_csv), "--bridge", str(bridge), "--out", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def load_evidence(out: Path) -> dict:
    return json.loads(out.read_text(encoding="utf-8"))


def require_failure(result: subprocess.CompletedProcess[str], out: Path, label: str) -> dict:
    if result.returncode == 0:
        raise AssertionError(f"Expected {label} to FAIL")
    evidence = load_evidence(out)
    if evidence.get("status") != "FAIL":
        raise AssertionError(f"{label} did not emit structured FAIL evidence")
    return evidence


def write_fixture(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["position_mm", "measured_uT", "model_uT"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="physical-lab-betterboard-bridge-") as temp_dir:
            temp = Path(temp_dir)
            residual_csv = temp / "magnet03_residuals.csv"
            bridge = temp / "physical_lab_field_bridge.json"
            out = temp / "engineering_lab_magnet_bridge_validation.json"

            valid_rows = [
                {"position_mm": 0.0, "measured_uT": 1.0, "model_uT": 1.0},
                {"position_mm": 1.0, "measured_uT": 2.0, "model_uT": 2.0},
                {"position_mm": 2.0, "measured_uT": 3.0, "model_uT": 3.0},
            ]
            write_fixture(residual_csv, valid_rows)

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
            canonical_bridge = {"comparison": comparison}
            bridge.write_text(json.dumps(canonical_bridge, indent=2) + "\n", encoding="utf-8")

            passing = run_validator(residual_csv, bridge, out)
            if passing.returncode != 0:
                raise AssertionError(f"Expected untampered bridge to PASS: {passing.stdout} {passing.stderr}")
            passing_evidence = load_evidence(out)
            if passing_evidence.get("status") != "PASS" or passing_evidence.get("input_integrity") != "PASS":
                raise AssertionError("Untampered bridge did not produce complete PASS evidence")
            if not all(passing_evidence.get("cross_application_checks", {}).values()):
                raise AssertionError("Untampered bridge contains a failed contract check")

            # Numeric tampering must be detected against the independent recomputation.
            tampered = json.loads(json.dumps(canonical_bridge))
            tampered["comparison"]["rmse_uT"] = 0.5
            bridge.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
            evidence = require_failure(run_validator(residual_csv, bridge, out), out, "tampered metric")
            if evidence.get("cross_application_checks", {}).get("rmse_uT") is not False:
                raise AssertionError("Tampered rmse_uT was not identified")

            # Schema drift/missing evidence must fail explicitly, not masquerade as a numerical mismatch.
            missing = json.loads(json.dumps(canonical_bridge))
            del missing["comparison"]["bias_uT"]
            bridge.write_text(json.dumps(missing, indent=2) + "\n", encoding="utf-8")
            evidence = require_failure(run_validator(residual_csv, bridge, out), out, "missing bridge field")
            checks = evidence.get("cross_application_checks", {})
            if checks.get("comparison_required_fields") is not False or checks.get("bias_uT") is not False:
                raise AssertionError("Missing bridge field was not exposed as contract failure")
            if not any("bias_uT" in error for error in evidence.get("errors", [])):
                raise AssertionError("Missing bridge field did not produce a diagnostic error")

            # A non-finite measurement row must invalidate the input rather than be silently dropped.
            bridge.write_text(json.dumps(canonical_bridge, indent=2) + "\n", encoding="utf-8")
            nonfinite_rows = list(valid_rows)
            nonfinite_rows[1] = {"position_mm": 1.0, "measured_uT": "NaN", "model_uT": 2.0}
            write_fixture(residual_csv, nonfinite_rows)
            evidence = require_failure(run_validator(residual_csv, bridge, out), out, "non-finite residual row")
            if evidence.get("input_integrity") != "FAIL":
                raise AssertionError("Non-finite residual row did not fail input integrity")
            if not any("non-finite" in error for error in evidence.get("errors", [])):
                raise AssertionError("Non-finite residual row did not produce a diagnostic error")

    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("BetterBoard magnet bridge contract: PASS (valid evidence accepted; tampering/schema drift/non-finite input rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
