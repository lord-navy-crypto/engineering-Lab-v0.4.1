#!/usr/bin/env python3
"""Regression validation for ActionProposal -> human approval -> manifest authorization.

The test intentionally verifies that approval remains non-executing and that a
separately authored valid Experiment Manifest is required before authorization.
"""
from __future__ import annotations

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
    from physical_lab_action_approval import (
        authorize_experiment_manifest,
        latest_action_decision,
        review_action_proposal,
    )
    from physical_lab_experiment_kernel import build_experiment_manifest
    from physical_lab_labbridge import finalize_packet
    import physical_lab_project_kernel as projects

    with tempfile.TemporaryDirectory(prefix="labbridge-approval-") as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        project_dir, _ = projects.create_project(
            "Approval Gate Validation",
            research_question="Can an AI proposal become an experiment only after explicit review?",
        )

        proposal = finalize_packet({
            "schema": "labbridge.action-proposal/v1",
            "bridge_version": "1.0",
            "packet_type": "action_proposal",
            "source_app": {"name": "OpenPenguin", "role": "local-ai-advisory-layer"},
            "intended_consumer": {"name": "Engineering Lab", "role": "scientific-computation-and-evidence-core"},
            "title": "Test a denser numerical grid",
            "summary": "Consider a denser grid and compare convergence behavior.",
            "target": "numerical-methods experiment",
            "rationale": "The current evidence shows a resolution-sensitive trend worth checking.",
            "expected_effect": "A denser grid may clarify whether the trend converges.",
            "falsification_observable": "The trend fails to stabilize or reverses at higher resolution.",
            "evidence_refs": ["dataset-test-001"],
            "executed": False,
        }, prefix="action-proposal")

        rejected = review_action_proposal(
            project_dir,
            proposal=proposal,
            decision="rejected",
            reviewer="human-reviewer",
            reason="The proposed experiment needs a clearer parameter range.",
        )
        require(rejected["executed"] is False, "review must never execute an ActionProposal")
        require(rejected["approval"]["decision"] == "rejected", "rejection must be persisted")

        manifest = build_experiment_manifest(
            "numerical-methods",
            parameters={"grid_points": 128},
            execution={"mode": "interactive-session"},
            provenance={"source_profile": "numerical-methods", "engine_mode": "safe"},
        )

        blocked = False
        try:
            authorize_experiment_manifest(
                project_dir,
                proposal=proposal,
                manifest=manifest,
                reviewer="human-reviewer",
            )
        except PermissionError:
            blocked = True
        require(blocked, "rejected proposal must not authorize an Experiment Manifest")

        approved = review_action_proposal(
            project_dir,
            proposal=proposal,
            decision="approved",
            reviewer="human-reviewer",
            reason="Parameter scope has now been reviewed and is acceptable for a bounded numerical test.",
        )
        require(approved["executed"] is False, "approval must remain non-executing")
        latest = latest_action_decision(project_dir, proposal["packet_id"])
        require(latest is not None and latest["decision"] == "approved", "latest explicit decision must be approval")

        authorization = authorize_experiment_manifest(
            project_dir,
            proposal=proposal,
            manifest=manifest,
            reviewer="human-reviewer",
        )
        record = authorization["authorization"]
        require(record["experiment_sha256"] == manifest["experiment_sha256"], "authorization must bind exact manifest fingerprint")
        require(record["registered"] is False, "authorization must not silently register the experiment")
        require(record["queued"] is False, "authorization must not silently queue the experiment")
        require(record["executed"] is False, "authorization must not silently execute the experiment")
        require(authorization["executed"] is False, "return contract must preserve executed=false")

        approvals = list((project_dir / "provenance" / "action-approvals").glob("*.json"))
        authorizations = list((project_dir / "provenance" / "experiment-authorizations").glob("*.json"))
        require(len(approvals) == 2, "both rejection and approval decisions should remain auditable")
        require(len(authorizations) == 1, "exactly one explicit manifest authorization expected")

    print("PASS: ActionProposal requires explicit human review; approval binds a valid manifest without registering, queueing, or executing it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
