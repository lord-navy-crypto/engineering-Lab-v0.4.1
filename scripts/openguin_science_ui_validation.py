#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_science_protocol_ui as ui

    plan = {
        "schema": "engineering-lab-analysis-plan-v1",
        "question": "What should I inspect next?",
        "steps": [{"capability": "correlation", "reason": "two numeric fields", "arguments": {}, "execute": False}],
        "assumptions": [],
        "executed": False,
        "mutation_authority": False,
    }
    context = {
        "packet_id": "ai-context-test",
        "scientific_context": {"active_object": {"source_id": "dataset:test", "kind": "dataset"}},
    }
    source = {"id": "dataset:test", "identity": {"dataset_id": "test", "sha256": "abc"}}
    handoff = ui._prepare_handoff(plan, context, source)
    require(handoff["schema"] == ui.HANDOFF_SCHEMA, "handoff schema mismatch")
    require(handoff["source_id"] == "dataset:test", "source identity missing")
    require(handoff["context_packet_id"] == "ai-context-test", "context packet identity missing")
    require(handoff["executed"] is False, "prepared handoff cannot claim execution")
    require(handoff["mutation_authority"] is False, "prepared handoff cannot gain mutation authority")
    require(handoff["plan"]["steps"][0]["execute"] is False, "plan step execution boundary changed")

    text = (UI / "physical_lab_science_protocol_ui.py").read_text(encoding="utf-8")
    for phrase in (
        "Ask OpenPenguin about this",
        "Request Analysis Plan",
        "Prepare in Engineering Lab",
        "Record plan provenance",
        "Prepared ≠ executed",
    ):
        require(phrase in text, f"missing UI contract phrase: {phrase}")

    print("PASS: OpenPenguin science advisory UI handoff remains non-executing and provenance-aware")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
