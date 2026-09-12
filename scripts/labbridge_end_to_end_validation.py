#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="physical-lab-labbridge-e2e-") as tmp:
        tmp_path = Path(tmp)
        os.environ["PHYSICAL_LAB_DATA_DIR"] = str(tmp_path / "physical-lab-data")

        import physical_lab_project_kernel as projects
        from physical_lab_betterboard_discovery import load_discovered_measurement
        from physical_lab_labbridge import (
            AI_SUGGESTION_SCHEMA,
            MEASUREMENT_SCHEMA,
            build_ai_context_packet,
            finalize_packet,
            ingest_measurement_asset,
            record_ai_advisory,
        )
        from physical_lab_labbridge_link import sync_betterboard_link
        from physical_lab_project_interop import list_canonical_datasets

        project_dir, _ = projects.create_project(
            "LabBridge end-to-end validation",
            research_question="Can BetterBoard evidence move through Engineering Lab without losing authority boundaries?",
        )

        measurement_root = tmp_path / "betterboard-measurements"
        session = measurement_root / "synthetic-20260912T000000Z"
        session.mkdir(parents=True)
        data_path = session / "data.csv"
        metadata_path = session / "metadata.json"
        packet_path = session / "labbridge_measurement_asset.json"

        data_bytes = b"time_s,voltage_v\n0.0,1.0\n0.1,1.1\n0.2,1.2\n"
        data_path.write_bytes(data_bytes)
        metadata = {
            "schema": "betterboard.measurement/0.2",
            "created_at_utc": "2026-09-12T00:00:00Z",
            "producer": "BetterBoard Studio e2e fixture",
            "acquisition_mode": "validation-fixture",
            "recipe_id": "synthetic",
            "recipe_title": "Synthetic Signal",
            "board_profile": "arduino:avr:uno",
            "port": "/dev/cu.validation-fixture",
            "baud": 115200,
            "columns": ["time_s", "voltage_v"],
            "units": ["s", "V"],
            "primary_column": "voltage_v",
            "sample_rate_hz": 10.0,
            "sample_count": 3,
            "firmware_sha256": "f" * 64,
            "recipe_parameters": {},
            "physical_lab_targets": ["Engineering Lab"],
            "scientific_boundary": "Synthetic CI fixture only; no calibration or validation claim.",
        }
        metadata_bytes = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8")
        metadata_path.write_bytes(metadata_bytes)

        packet = finalize_packet(
            {
                "schema": MEASUREMENT_SCHEMA,
                "bridge_version": "1.0",
                "packet_type": "measurement_asset",
                "source_app": {
                    "name": "BetterBoard",
                    "product": "BetterBoard Studio",
                    "version": "validation-fixture",
                    "role": "real-world-ingress",
                },
                "created_at_utc": metadata["created_at_utc"],
                "dataset": {
                    "path": "data.csv",
                    "format": "text/csv",
                    "sha256": sha_bytes(data_bytes),
                    "rows": 3,
                    "columns": [
                        {"name": "time_s", "unit": "s", "role": "coordinate"},
                        {"name": "voltage_v", "unit": "V", "role": "primary-observable"},
                    ],
                },
                "device": {
                    "board_profile": metadata["board_profile"],
                    "port": metadata["port"],
                    "baud": metadata["baud"],
                    "firmware_sha256": metadata["firmware_sha256"],
                },
                "acquisition": {
                    "mode": metadata["acquisition_mode"],
                    "recipe_id": metadata["recipe_id"],
                    "recipe_title": metadata["recipe_title"],
                    "sample_rate_hz": metadata["sample_rate_hz"],
                    "recipe_parameters": {},
                },
                "primary_observable": "voltage_v",
                "provenance": {
                    "metadata_path": "metadata.json",
                    "metadata_sha256": sha_bytes(metadata_bytes),
                    "firmware_sha256": metadata["firmware_sha256"],
                },
                "intended_consumer": {
                    "name": "Engineering Lab",
                    "role": "scientific-computation-and-evidence-core",
                },
                "scientific_boundary": "Synthetic CI fixture; integrity is not scientific validation.",
            },
            prefix="measurement",
        )
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

        source_fingerprints = {
            path.name: sha_bytes(path.read_bytes())
            for path in (data_path, metadata_path, packet_path)
        }

        discovered = sync_betterboard_link(project_dir, measurement_root=measurement_root, limit=10)
        assert len(discovered["valid_new"]) == 1, discovered
        assert discovered["counts"]["new"] == 1, discovered["counts"]
        assert discovered["policy"]["auto_ingest"] is False
        assert list_canonical_datasets(project_dir) == [], "discovery must not auto-ingest BetterBoard evidence"

        measurement_packet, measurement_bytes = load_discovered_measurement(discovered["valid_new"][0])
        ingested = ingest_measurement_asset(
            project_dir,
            packet=measurement_packet,
            dataset_bytes=measurement_bytes,
            notes="Explicit CI ingest proving the canonical bridge path.",
        )
        dataset_id = str(ingested["dataset"]["dataset_id"])
        assert dataset_id
        assert ingested["validation"]["valid"] is True

        after_ingest = sync_betterboard_link(project_dir, measurement_root=measurement_root, limit=10)
        assert after_ingest["counts"]["ingested"] == 1, after_ingest["counts"]
        assert not after_ingest["valid_new"], "explicitly ingested packet must leave the NEW queue"

        context = build_ai_context_packet(project_dir, profile="measurement-bridge", focus="synthetic voltage evidence")
        assert context["schema"] == "labbridge.ai-context/v1"
        assert context["authority"]["scientific_record"] == "Engineering Lab"
        assert any(str(row.get("dataset_id")) == dataset_id for row in context.get("datasets", []))

        suggestion = finalize_packet(
            {
                "schema": AI_SUGGESTION_SCHEMA,
                "bridge_version": "1.0",
                "packet_type": "ai_suggestion",
                "source_app": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
                "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
                "title": "Synthetic LabBridge advisory",
                "summary": "Review the imported voltage series; this fixture makes no physical claim.",
                "question": "What should be reviewed next?",
                "evidence_refs": [context["packet_id"], dataset_id],
                "executed": False,
            },
            prefix="ai-suggestion",
        )
        recorded = record_ai_advisory(project_dir, suggestion)
        assert recorded["executed"] is False
        assert recorded["validation"]["valid"] is True
        advisory_path = project_dir / "provenance" / "ai-proposals" / f"{suggestion['packet_id']}.json"
        assert advisory_path.is_file()

        final_fingerprints = {
            path.name: sha_bytes(path.read_bytes())
            for path in (data_path, metadata_path, packet_path)
        }
        assert final_fingerprints == source_fingerprints, "Engineering Lab must not mutate BetterBoard source evidence"

        print("PASS: BetterBoard -> discovery/inbox -> explicit canonical ingest -> AIContext -> OpenPenguin advisory provenance")
        print("PASS: BetterBoard source evidence remained byte-for-byte unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
