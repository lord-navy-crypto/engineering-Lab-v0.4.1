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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        import physical_lab_project_kernel as projects
        from physical_lab_lab_journey import append_event, verify_journey
        from physical_lab_labbridge import (
            ACTION_PROPOSAL_SCHEMA,
            MEASUREMENT_SCHEMA,
            build_ai_context_packet,
            finalize_packet,
            ingest_measurement_asset,
            record_ai_advisory,
            validate_measurement_asset,
        )
        from physical_lab_project_interop import build_reproducibility_pack

        project_dir, project = projects.create_project("LabBridge Validation")
        csv_bytes = b"time_s,voltage_v\n0.0,1.0\n0.1,1.2\n0.2,1.1\n"
        data_sha = hashlib.sha256(csv_bytes).hexdigest()
        packet = finalize_packet({
            "schema": MEASUREMENT_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "measurement_asset",
            "source_app": {"name": "BetterBoard", "version": "test", "role": "real-world-ingress"},
            "created_at_utc": "2026-09-12T00:00:00+00:00",
            "dataset": {
                "path": "data.csv", "format": "text/csv", "sha256": data_sha, "rows": 3,
                "columns": [
                    {"name": "time_s", "unit": "s", "role": "coordinate"},
                    {"name": "voltage_v", "unit": "V", "role": "primary-observable"},
                ],
            },
            "device": {"board_profile": "arduino:avr:uno", "port": "/dev/cu.test", "baud": 115200, "firmware_sha256": "f" * 64},
            "acquisition": {"mode": "serial-capture", "recipe_id": "analog", "recipe_title": "Analog Test", "sample_rate_hz": 10.0, "recipe_parameters": {}},
            "primary_observable": "voltage_v",
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "scientific_boundary": "Synthetic validation packet; calibration remains separate.",
        }, prefix="measurement")

        check = validate_measurement_asset(packet, csv_bytes)
        require(check["valid"], f"valid measurement packet rejected: {check}")
        require(not validate_measurement_asset(packet, csv_bytes + b"9,9\n")["valid"], "dataset SHA mismatch was accepted")

        ingested = ingest_measurement_asset(project_dir, packet=packet, dataset_bytes=csv_bytes, profile="validation")
        dataset = ingested["dataset"]
        require(dataset["row_count"] == 3, "ingested dataset row count mismatch")
        require(dataset["units"]["time_s"] == "s" and dataset["units"]["voltage_v"] == "V", "units not preserved")
        require(dataset["columns"]["voltage_v"] == [1.0, 1.2, 1.1], "measurement values changed during ingest")

        human = append_event(project_dir, event_type="observation", source_role="human", title="Observed stable voltage", evidence_refs=[dataset["dataset_id"]])
        chain = verify_journey(project_dir)
        require(chain["valid"], f"journey chain invalid: {chain}")
        require(chain["verified_events"] == 2, "expected measurement import + human observation")
        require(human["previous_event_sha256"] == ingested["journey_event"]["event_sha256"], "journey hash linkage mismatch")

        context = build_ai_context_packet(project_dir, profile="validation", focus="check stability")
        require(context["schema"] == "labbridge.ai-context/v1", "wrong AI context schema")
        require(context["source_app"]["name"] == "Engineering Lab", "wrong AI context authority")
        require(context["intended_consumer"]["name"] == "OpenPenguin", "wrong AI context consumer")
        require(len(context["journey_events"]) == 2, "AI context did not include journey evidence")

        proposal = finalize_packet({
            "schema": ACTION_PROPOSAL_SCHEMA,
            "bridge_version": "1.0",
            "packet_type": "action_proposal",
            "source_app": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "title": "Test a higher sampling rate",
            "summary": "Repeat the acquisition at a higher sampling rate to test whether apparent variation is bandwidth-related.",
            "target": "acquisition.sample_rate_hz",
            "rationale": "Resolve whether sampling affects observed variation.",
            "expected_effect": "Higher temporal resolution if the device supports it.",
            "falsification_observable": "Voltage variation remains statistically unchanged after matched-condition repeat.",
            "evidence_refs": [dataset["dataset_id"]],
            "executed": False,
        }, prefix="action-proposal")
        advisory = record_ai_advisory(project_dir, proposal)
        require(advisory["executed"] is False, "AI proposal unexpectedly executed")
        require(advisory["journey_event"]["source_role"] == "openguin", "AI proposal journey source wrong")
        require(verify_journey(project_dir)["valid"], "journey invalid after AI proposal")

        pack = build_reproducibility_pack(project_dir)
        packed_paths = {row["path"] for row in pack["manifest"]["files"]}
        require(any(p.startswith("journey/events/") for p in packed_paths), "journey events missing from reproducibility pack")
        require(any(p.startswith("provenance/labbridge-ingest/") for p in packed_paths), "LabBridge ingest provenance missing from pack")
        require(any(p.startswith("provenance/ai-proposals/") for p in packed_paths), "OpenPenguin proposal provenance missing from pack")

        # Tamper with the first event and ensure the chain detects it.
        event_files = sorted((Path(project_dir) / "journey" / "events").glob("*.json"))
        first = json.loads(event_files[0].read_text())
        first["title"] = "tampered"
        event_files[0].write_text(json.dumps(first, indent=2, sort_keys=True))
        require(not verify_journey(project_dir)["valid"], "journey tampering was not detected")

    print("PASS: LabBridge measurement ingest, Lab Journey chain, AI advisory boundary and reproducibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
