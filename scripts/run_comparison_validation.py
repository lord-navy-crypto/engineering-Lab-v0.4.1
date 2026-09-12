from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_environment_manifest import build_environment_manifest
from physical_lab_project_interop import build_reproducibility_pack
from physical_lab_project_kernel import create_project
from physical_lab_run_comparison import build_run_snapshot, compare_runs, staleness_report
from physical_lab_run_snapshot_store import freeze_if_missing, list_run_snapshots


def wave_result(scale: float = 1.0):
    return {
        "schema": "physical-lab-wave-fd-v1",
        "x": [0.0, 0.5, 1.0],
        "numerical": [0.0, 1.0 * scale, 0.0],
        "analytic": [0.0, 1.0, 0.0],
        "dx": 0.5,
        "dt": 0.1,
        "cfl": 0.2,
        "l2_error": abs(scale - 1.0),
        "max_relative_energy_drift": 0.001,
        "boundary": "synthetic validation fixture",
    }


def heat_result():
    return {
        "schema": "physical-lab-heat-cn-v1",
        "x": [0.0, 0.5, 1.0],
        "numerical": [0.0, 0.5, 0.0],
        "analytic": [0.0, 0.5, 0.0],
        "dx": 0.5,
        "dt": 0.1,
        "fourier_number": 0.2,
        "l2_error": 0.0,
        "max_error": 0.0,
        "boundary": "synthetic validation fixture",
    }


def main():
    old_commit = os.environ.get("PHYSICAL_LAB_SOURCE_COMMIT")
    try:
        os.environ["PHYSICAL_LAB_SOURCE_COMMIT"] = "commit-a"
        env_a = build_environment_manifest(extra={"validation": True})
        a = build_run_snapshot(
            run_id="run-a", source_kind="fixture", result=wave_result(1.0), profile="numerical-methods",
            experiment_sha256="exp-same", source_commit="commit-a", environment=env_a,
            runtime_s=1.0, parameters={"nx": 10},
        )
        b = build_run_snapshot(
            run_id="run-b", source_kind="fixture", result=wave_result(1.01), profile="numerical-methods",
            experiment_sha256="exp-same", source_commit="commit-a", environment=env_a,
            runtime_s=1.2, parameters={"nx": 10},
        )
        comp = compare_runs(a, b, current_environment=env_a)
        assert comp["comparability"] == "COMPARABLE", comp["comparability"]
        assert any(r["metric"] == "l2_error" for r in comp["metric_differences"])

        os.environ["PHYSICAL_LAB_SOURCE_COMMIT"] = "commit-b"
        env_b = build_environment_manifest(extra={"validation": True})
        b_env = dict(b)
        b_env["environment"] = env_b
        b_env["environment_sha256"] = env_b["environment_sha256"]
        comp_env = compare_runs(a, b_env, current_environment=env_b)
        assert comp_env["comparability"] == "COMPARABLE-WITH-ENV-DRIFT", comp_env["comparability"]

        h = build_run_snapshot(
            run_id="run-h", source_kind="fixture", result=heat_result(), profile="numerical-methods",
            experiment_sha256="exp-same", source_commit="commit-a", environment=env_a,
        )
        comp_schema = compare_runs(a, h, current_environment=env_a)
        assert comp_schema["comparability"] == "INCOMPATIBLE-SCHEMA"

        stale = staleness_report(a, current_environment=env_b)
        assert stale["status"] == "STALE", stale
        assert any(r["code"] == "SOURCE_COMMIT_CHANGED" for r in stale["reasons"])

        with tempfile.TemporaryDirectory() as td:
            os.environ["PHYSICAL_LAB_DATA_DIR"] = td
            project_dir, _ = create_project("Run Comparison Validation")
            frozen = freeze_if_missing(project_dir, a)
            changed = dict(a)
            changed["contract_sha256"] = "changed-contract"
            changed["snapshot_sha256"] = "changed-snapshot"
            frozen_again = freeze_if_missing(project_dir, changed)
            assert frozen_again["snapshot_sha256"] == frozen["snapshot_sha256"]
            rows = list_run_snapshots(project_dir, run_id="run-a")
            assert len(rows) == 1
            pack = build_reproducibility_pack(project_dir)
            packed_paths = {row["path"] for row in pack["manifest"]["files"]}
            assert any(p.startswith("run-snapshots/") for p in packed_paths), packed_paths

        print("Run Comparison validation PASS")
        print({"comparable": comp["comparability"], "env_drift": comp_env["comparability"], "schema": comp_schema["comparability"], "stale": stale["status"]})
    finally:
        if old_commit is None:
            os.environ.pop("PHYSICAL_LAB_SOURCE_COMMIT", None)
        else:
            os.environ["PHYSICAL_LAB_SOURCE_COMMIT"] = old_commit


if __name__ == "__main__":
    main()
