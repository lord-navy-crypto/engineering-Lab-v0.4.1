#!/usr/bin/env python3
from __future__ import annotations

import json
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
    import physical_lab_analysis_plan_store as store
    import physical_lab_science_protocol as sp

    context = {
        "packet_id": "ai-context-123",
        "content_sha256": "a" * 64,
        "scientific_context": {
            "active_object": {"source_id": "sweep-1", "kind": "sweep"},
            "capabilities": [
                {"capability_id": "morris-effects"},
                {"capability_id": "response-surface"},
            ],
        },
    }
    plan = {
        "schema": sp.ANALYSIS_PLAN_SCHEMA,
        "question": "Which analysis should I inspect next?",
        "steps": [
            {
                "capability": "morris-effects",
                "reason": "trajectory metadata is present",
                "arguments": {"response": "metric:y"},
                "execute": False,
            }
        ],
        "assumptions": [],
        "executed": False,
        "mutation_authority": False,
    }

    first = store.analysis_plan_record(plan=plan, context_packet=context)
    second = store.analysis_plan_record(plan=plan, context_packet=context)
    require(first["plan_record_id"] == second["plan_record_id"], "analysis-plan identity is not deterministic")
    require(first["sha256"] == second["sha256"], "analysis-plan SHA is not deterministic")
    require(first["authority"]["scientific_evidence"] is False, "AI plan incorrectly became scientific evidence")
    require(first["authority"]["executed"] is False, "AI plan incorrectly claims execution")
    require(first["authority"]["mutation_authority"] is False, "AI plan incorrectly has mutation authority")
    require(store.verify_analysis_plan_record(first)["valid"], "valid plan record failed verification")

    tampered = json.loads(json.dumps(first))
    tampered["authority"]["executed"] = True
    require(not store.verify_analysis_plan_record(tampered)["valid"], "executed=true tampering was accepted")

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "project.json").write_text("{}", encoding="utf-8")
        saved = store.save_analysis_plan(project, plan=plan, context_packet=context)
        target = Path(saved["path"])
        require(target.exists(), "analysis-plan provenance was not written")
        loaded = json.loads(target.read_text(encoding="utf-8"))
        require(store.verify_analysis_plan_record(loaded)["valid"], "saved analysis-plan provenance failed verification")
        require("provenance/ai-analysis-plans" in target.as_posix(), "analysis plan was stored outside provenance")

    invalid = {**plan, "executed": True}
    try:
        store.analysis_plan_record(plan=invalid, context_packet=context)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid executed plan was stored")

    print("PASS: content-addressed OpenPenguin analysis-plan provenance remains advisory and unexecuted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
