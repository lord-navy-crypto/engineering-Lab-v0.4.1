#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

import physical_lab_project_kernel as projects
from physical_lab_environment_manifest import build_environment_manifest, save_environment_manifest
from physical_lab_model_depth_ix import wave_equation_1d
from physical_lab_project_interop import build_reproducibility_pack
from physical_lab_result_contracts import (
    annotate_inventory,
    get_contract,
    make_uncertainty,
    validate_contract_inventory,
    validate_uncertainty,
)
from physical_lab_result_inspector import inspect_result


def main() -> int:
    wave = wave_equation_1d(final_time=0.4, points=81, cfl=0.8)
    inspection = inspect_result(wave)
    contract = get_contract(wave["schema"])
    assert contract is not None
    assert contract["fields"]["cfl"]["role"] == "stability-diagnostic"
    annotated = annotate_inventory(wave["schema"], inspection["inventory"])
    cfl_row = next(row for row in annotated["inventory"] if row.get("path") == "cfl")
    assert cfl_row["unit"] == "1"
    assert cfl_row["quantity"] == "Courant number"
    conformance = validate_contract_inventory(wave["schema"], inspection["inventory"])
    assert conformance["status"] == "PASS", conformance

    unknown = annotate_inventory("physical-lab-unknown-v1", inspection["inventory"])
    assert unknown["registered"] is False

    u1 = make_uncertainty(
        estimate=1.23,
        unit="m",
        standard_uncertainty=0.04,
        coverage_factor=2.0,
        interval=(1.15, 1.31),
        coverage_probability=0.95,
        method="validation synthetic standard uncertainty",
        components=[{"name":"sampling","standard_uncertainty":0.04}],
    )
    u2 = make_uncertainty(
        estimate=1.23,
        unit="m",
        standard_uncertainty=0.04,
        coverage_factor=2.0,
        interval=(1.15, 1.31),
        coverage_probability=0.95,
        method="validation synthetic standard uncertainty",
        components=[{"name":"sampling","standard_uncertainty":0.04}],
    )
    assert u1["uncertainty_sha256"] == u2["uncertainty_sha256"]
    assert validate_uncertainty(u1)["valid"]
    try:
        make_uncertainty(estimate=1.0, standard_uncertainty=-0.1, method="invalid")
    except ValueError:
        pass
    else:
        raise AssertionError("negative standard uncertainty must fail")

    os.environ["PHYSICAL_LAB_SOURCE_COMMIT"] = "validation-commit"
    e1 = build_environment_manifest(extra={"active_profile":"numerical-methods"})
    e2 = build_environment_manifest(extra={"active_profile":"numerical-methods"})
    assert e1["environment_sha256"] == e2["environment_sha256"]
    assert e1["physical_lab"]["source_commit"] == "validation-commit"

    with tempfile.TemporaryDirectory() as td:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = td
        project_path, _ = projects.create_project("Result Contract Validation", research_question="Can result metadata and software provenance remain explicit and reproducible?")
        saved = save_environment_manifest(project_path, extra={"active_profile":"numerical-methods"})
        assert saved["environment_sha256"] == e1["environment_sha256"]
        pack = build_reproducibility_pack(project_path)
        paths = {row["path"] for row in pack["manifest"]["files"]}
        assert any(path.startswith("environments/environment-") for path in paths), paths

    print("PASS: result contracts, explicit uncertainty, environment fingerprint, and pack inclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
