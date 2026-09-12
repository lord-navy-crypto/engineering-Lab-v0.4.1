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


def make_packet(finalize_packet, measurement_dir: Path, *, tamper: bool = False) -> dict:
    csv_bytes = b"time_s,voltage_v\n0.0,1.0\n0.1,1.2\n0.2,1.1\n"
    (measurement_dir / "data.csv").write_bytes(csv_bytes if not tamper else csv_bytes + b"0.3,9.9\n")
    metadata = {
        "schema": "betterboard.measurement/0.2",
        "created_at_utc": "2026-09-12T00:00:00+00:00",
        "producer": "BetterBoard Studio test",
        "acquisition_mode": "serial-capture",
        "recipe_id": "analog",
        "recipe_title": "Analog Test",
        "board_profile": "arduino:avr:uno",
        "port": "/dev/cu.test",
        "baud": 115200,
        "columns": ["time_s", "voltage_v"],
        "units": ["s", "V"],
        "primary_column": "voltage_v",
        "sample_rate_hz": 10.0,
        "sample_count": 3,
        "firmware_sha256": "f" * 64,
        "recipe_parameters": {},
    }
    (measurement_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    source_bytes = csv_bytes
    packet = finalize_packet({
        "schema": "labbridge.measurement-asset/v1",
        "bridge_version": "1.0",
        "packet_type": "measurement_asset",
        "source_app": {"name": "BetterBoard", "product": "BetterBoard Studio", "version": "test", "role": "real-world-ingress"},
        "created_at_utc": metadata["created_at_utc"],
        "dataset": {
            "path": "data.csv", "format": "text/csv", "sha256": hashlib.sha256(source_bytes).hexdigest(), "rows": 3,
            "columns": [
                {"name": "time_s", "unit": "s", "role": "coordinate"},
                {"name": "voltage_v", "unit": "V", "role": "primary-observable"},
            ],
        },
        "device": {"board_profile": metadata["board_profile"], "port": metadata["port"], "baud": 115200, "firmware_sha256": "f" * 64},
        "acquisition": {"mode": "serial-capture", "recipe_id": "analog", "recipe_title": "Analog Test", "sample_rate_hz": 10.0, "recipe_parameters": {}},
        "primary_observable": "voltage_v",
        "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
        "scientific_boundary": "Synthetic BetterBoard discovery validation packet.",
    }, prefix="measurement")
    (measurement_dir / "labbridge_measurement_asset.json").write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    return packet


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        import physical_lab_project_kernel as projects
        from physical_lab_betterboard_discovery import discover_betterboard_measurements, load_discovered_measurement
        from physical_lab_labbridge import finalize_packet, ingest_measurement_asset

        project_dir, _ = projects.create_project("BetterBoard Discovery Validation")
        bb_root = Path(tmp) / "betterboard-measurements"
        bb_root.mkdir()

        valid_dir = bb_root / "analog-valid"
        valid_dir.mkdir()
        valid_packet = make_packet(finalize_packet, valid_dir, tamper=False)

        tampered_dir = bb_root / "analog-tampered"
        tampered_dir.mkdir()
        make_packet(finalize_packet, tampered_dir, tamper=True)

        rows = discover_betterboard_measurements(project_dir, root=bb_root, limit=20)
        require(len(rows) == 2, f"expected two discovered sessions, got {len(rows)}")
        by_name = {row["session_name"]: row for row in rows}
        require(by_name["analog-valid"]["labbridge_valid"], "valid BetterBoard session was not accepted")
        require(not by_name["analog-tampered"]["labbridge_valid"], "tampered BetterBoard data.csv was accepted")
        require(not by_name["analog-valid"]["already_ingested"], "fresh source incorrectly marked already ingested")

        packet, data = load_discovered_measurement(by_name["analog-valid"])
        require(packet["packet_id"] == valid_packet["packet_id"], "loaded packet identity changed")
        ingest_measurement_asset(project_dir, packet=packet, dataset_bytes=data, profile="validation")

        rows_after = discover_betterboard_measurements(project_dir, root=bb_root, limit=20)
        by_name_after = {row["session_name"]: row for row in rows_after}
        require(by_name_after["analog-valid"]["already_ingested"], "ingested source was not recognized by packet SHA")
        require(not by_name_after["analog-tampered"]["already_ingested"], "tampered source incorrectly marked ingested")

    print("PASS: BetterBoard local discovery, integrity rejection and packet-SHA deduplication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
