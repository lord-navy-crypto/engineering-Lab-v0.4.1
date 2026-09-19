#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_science_protocol as sp

    sweep = {
        "id": "sweep-test",
        "label": "Morris sweep",
        "kind": "sweep",
        "frame": pd.DataFrame({
            "__trajectory": [0, 0, 0],
            "__step": [0, 1, 2],
            "__changed_factor": ["", "a", "b"],
            "param:a": [0.0, 1.0, 1.0],
            "param:b": [0.0, 0.0, 1.0],
            "metric:y": [0.0, 2.0, 5.0],
        }),
        "units": {"param:a": "m", "param:b": "s"},
        "identity": {"job_id": "sweep-test"},
    }
    eligible = {r["capability_id"] for r in sp.eligible_capabilities(sweep)}
    require("morris-effects" in eligible, "Morris capability should be eligible when metadata is present")
    require("response-surface" in eligible, "response surface should be eligible for a multi-parameter sweep")
    require("sensitivity-screening" in eligible, "sensitivity screening should be eligible")
    require("doe-proposal" in eligible, "DOE proposal should be eligible")

    context = {
        "scientific_context": {
            "capabilities": [{"capability_id": x} for x in sorted(eligible)]
        }
    }
    good = {
        "schema": sp.ANALYSIS_PLAN_SCHEMA,
        "question": "What should I run next?",
        "steps": [{"capability": "morris-effects", "reason": "metadata is present", "arguments": {}, "execute": False}],
        "assumptions": [],
        "executed": False,
        "mutation_authority": False,
    }
    require(sp.validate_analysis_plan(good, context=context)["valid"], "valid advisory plan was rejected")

    bad = {**good, "steps": [{"capability": "unknown-tool", "execute": False}]}
    require(not sp.validate_analysis_plan(bad, context=context)["valid"], "unknown capability was accepted")
    bad_exec = {**good, "executed": True}
    require(not sp.validate_analysis_plan(bad_exec, context=context)["valid"], "executed plan was accepted")

    parsed = sp._extract_json_object("```json\n" + __import__("json").dumps(good) + "\n```")
    require(parsed and parsed["schema"] == sp.ANALYSIS_PLAN_SCHEMA, "fenced JSON plan was not parsed")

    claim = sp.claim_record(text="Computed value", claim_type="computed", evidence_refs=["result-1"])
    require(claim["executed"] is False and claim["mutation_authority"] is False, "claim authority boundary incorrect")
    try:
        sp.claim_record(text="Unsupported observation", claim_type="observation", evidence_refs=[])
    except ValueError:
        pass
    else:
        raise AssertionError("observation without evidence reference was accepted")

    require(all(r["creates_evidence"] is False for r in sp.scientific_capabilities()), "capability registry must not grant AI evidence creation")
    require(all(r["execution_authority"] != "openpenguin" for r in sp.scientific_capabilities()), "OpenPenguin execution authority leaked into registry")
    print("PASS: scientific context capabilities, plan validation, claims, and OpenPenguin authority boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
