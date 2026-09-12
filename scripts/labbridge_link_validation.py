#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_labbridge_link.py"
ADAPTER = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_openguin_adapter.py"
CLI = ROOT / "scripts" / "labbridge_link.py"


def main() -> int:
    source = MODULE.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")
    cli = CLI.read_text(encoding="utf-8")
    ast.parse(source)
    ast.parse(adapter)
    ast.parse(cli)

    required = [
        "sync_betterboard_link",
        "ask_openguin_about_project",
        "bridge_status",
        "discover_betterboard_measurements",
        "sync_discovery",
        "build_ai_context_packet",
        "record_ai_advisory",
        "probe_openguin",
        "request_advisory",
        '"auto_ingest": False',
        '"measurement_ingest": False',
        '"ai_recording": False',
        '"action_proposal_execution": False',
        '"executed": False',
    ]
    missing = [token for token in required if token not in source]
    assert not missing, f"missing coordinator boundary token(s): {missing}"

    adapter_required = [
        "labbridge-openguin-api/v1",
        "/labbridge/v1/capabilities",
        "/labbridge/v1/advisory",
        "127.0.0.1:11435",
        "native-labbridge",
        "ollama-compat",
        'packet["executed"] = False',
    ]
    missing_adapter = [token for token in adapter_required if token not in adapter]
    assert not missing_adapter, f"missing OpenPenguin adapter contract token(s): {missing_adapter}"

    forbidden = [
        "ingest_measurement_asset(",
        '"executed": True',
        "http://0.0.0.0",
        "https://",
    ]
    present = [token for token in forbidden if token in source]
    assert not present, f"coordinator introduced unsafe automatic behavior: {present}"

    assert "--record" in cli, "AI recording must remain explicit opt-in"
    assert "--allow-ollama-fallback" in cli, "external runtime fallback must remain explicit opt-in"
    assert "--watch" in cli, "local live link watcher is missing"
    print("PASS: BetterBoard discovery, Engineering Lab record ownership and unified OpenPenguin advisory boundaries are preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
