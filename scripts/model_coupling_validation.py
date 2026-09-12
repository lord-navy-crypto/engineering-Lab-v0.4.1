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
from physical_lab_model_coupling import build_parameter_packet, save_pipeline, list_pipelines, queue_packet
from physical_lab_project_interop import save_canonical_dataset, build_reproducibility_pack


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = td
        project_path, _ = projects.create_project("Coupling Validation", research_question="Can explicit dataset-to-model mappings remain reproducible?")
        dataset = save_canonical_dataset(
            project_path,
            name="identified plant",
            profile="oscillation-integration",
            columns={"mass_g": [1000.0, 1000.0, 1000.0], "damping": [0.4, 0.6, 0.8]},
            units={"mass_g": "g_mass"},
            source="synthetic",
        )
        mappings = [
            {"source_column":"mass_g","reducer":"mean","source_unit":"g_mass","target_unit":"kg","scale":1.0,"offset":0.0,"target_parameter":"mass"},
            {"source_column":"damping","reducer":"mean","source_unit":"","target_unit":"","scale":2.0,"offset":0.1,"target_parameter":"damping"},
        ]
        packet1 = build_parameter_packet(dataset, adapter_id="pid-step", target_profile="oscillation-integration", mappings=mappings)
        packet2 = build_parameter_packet(dataset, adapter_id="pid-step", target_profile="oscillation-integration", mappings=mappings)
        assert abs(packet1["parameters"]["mass"] - 1.0) < 1e-12, packet1
        assert abs(packet1["parameters"]["damping"] - 1.3) < 1e-12, packet1
        assert packet1["packet_sha256"] == packet2["packet_sha256"]
        assert packet1["source_dataset_sha256"] == dataset["sha256"]
        assert packet1["mappings"][0]["conversion"] == {"from":"g_mass","to":"kg"}

        p1 = save_pipeline(project_path, name="identified plant to PID", packet=packet1, notes="validation")
        p2 = save_pipeline(project_path, name="identified plant to PID", packet=packet2, notes="validation")
        assert p1["pipeline_id"] == p2["pipeline_id"]
        assert len(list_pipelines(project_path)) == 1

        job = queue_packet(packet1)
        assert job["profile"] == "oscillation-integration"
        assert job["adapter"] == "pid-step"
        assert job["point_count"] == 1

        pack = build_reproducibility_pack(project_path)
        paths = {row["path"] for row in pack["manifest"]["files"]}
        assert any(path.startswith("pipelines/") for path in paths), paths
        assert any(path.startswith("datasets/") for path in paths), paths

        # Duplicate target parameters must fail closed.
        bad = [dict(mappings[0]), dict(mappings[0])]
        failed = False
        try:
            build_parameter_packet(dataset, adapter_id="pid-step", target_profile="oscillation-integration", mappings=bad)
        except ValueError:
            failed = True
        assert failed

        print("PASS: model coupling mapping, unit conversion, provenance, queue handoff, and pack inclusion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
