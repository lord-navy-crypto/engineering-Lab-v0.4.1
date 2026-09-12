#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

import physical_lab_project_kernel as projects
from physical_lab_project_interop import build_reproducibility_pack
from physical_lab_result_inspector import (
    inspect_result,
    materialize_result,
    numerical_sanity_report,
)


def wave(cfl: float = 0.8):
    return {
        "schema": "physical-lab-wave-fd-v1",
        "time_s": [0.0, 0.1, 0.2],
        "numerical": [0.0, 0.5, 0.0],
        "analytic": [0.0, 0.49, 0.0],
        "cfl": cfl,
        "l2_error": 0.01,
        "max_relative_energy_drift": 0.002,
        "boundary": "synthetic validation fixture",
    }


def main() -> int:
    good = wave(0.8)
    inspection = inspect_result(good)
    inventory = {row["path"]: row for row in inspection["inventory"]}
    assert inventory["time_s"]["kind"] == "vector"
    assert inventory["l2_error"]["role"] == "numerical-quality"
    assert numerical_sanity_report(good)["status"] == "PASS"
    bad = wave(1.2)
    bad_report = numerical_sanity_report(bad)
    assert bad_report["status"] == "FAIL"
    assert any(row["code"] == "WAVE_CFL" for row in bad_report["checks"])

    with tempfile.TemporaryDirectory() as td:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = td
        project_path, _ = projects.create_project(
            "Result Inspector Validation",
            research_question="Can persisted results be materialized with stable provenance?",
        )
        identity = {"id": "synthetic:wave:1", "kind": "validation-fixture"}
        rules = [
            {"path": "time_s", "reducer": "series", "column_name": "time_s", "unit": "s"},
            {"path": "numerical", "reducer": "series", "column_name": "response", "unit": ""},
            {"path": "l2_error", "reducer": "mean", "column_name": "l2_error", "unit": ""},
        ]
        first = materialize_result(
            project_path,
            result=good,
            source_identity=identity,
            name="wave materialization",
            profile="numerical-methods",
            rules=rules,
            notes="validation",
        )
        second = materialize_result(
            project_path,
            result=good,
            source_identity=identity,
            name="wave materialization",
            profile="numerical-methods",
            rules=rules,
            notes="validation",
        )
        dataset = first["dataset"]
        assert dataset["row_count"] == 3
        assert dataset["columns"]["time_s"] == [0.0, 0.1, 0.2]
        assert dataset["columns"]["response"] == [0.0, 0.5, 0.0]
        assert dataset["columns"]["l2_error"] == [0.01, 0.01, 0.01]
        assert first["provenance"]["materialization_id"] == second["provenance"]["materialization_id"]
        assert first["provenance"]["relations"]["wasDerivedFrom"][dataset["dataset_id"]] == "synthetic:wave:1"
        assert first["provenance"]["source_entity"]["sha256"]

        pack = build_reproducibility_pack(project_path)
        paths = {row["path"] for row in pack["manifest"]["files"]}
        assert any(p.startswith("datasets/") for p in paths), paths
        assert any(p.startswith("provenance/materializations/") for p in paths), paths

    print("PASS: unified result inspection, numerical sanity and PROV-inspired materialization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
