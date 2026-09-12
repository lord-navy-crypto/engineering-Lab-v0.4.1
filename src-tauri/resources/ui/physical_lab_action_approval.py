"""Human review gate for LabBridge ActionProposal records.

This module deliberately separates AI suggestion from scientific authorization.
An OpenPenguin ActionProposal may be reviewed, approved, or rejected, but approval
never executes hardware, starts a solver, mutates parameters, or silently creates
measurement evidence. A separately supplied Experiment Manifest must still pass
the Engineering Lab experiment-kernel contract before it can be linked to an
approved proposal.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import physical_lab_project_kernel as projects
from physical_lab_experiment_kernel import plain, sha256_json, utc_now, validate_manifest
from physical_lab_lab_journey import append_event
from physical_lab_labbridge import ACTION_PROPOSAL_SCHEMA, validate_ai_advisory

APPROVAL_SCHEMA = "engineering-lab-action-approval/v1"
AUTHORIZATION_SCHEMA = "engineering-lab-experiment-authorization/v1"
DECISIONS = {"approved", "rejected"}


def _canonical_sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(plain(dict(value)), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _approval_root(project_dir: Path) -> Path:
    root = project_dir / "provenance" / "action-approvals"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _authorization_root(project_dir: Path) -> Path:
    root = project_dir / "provenance" / "experiment-authorizations"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(plain(dict(value)), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def review_action_proposal(
    project_dir: str | Path,
    *,
    proposal: Mapping[str, Any],
    decision: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    """Record an explicit human review decision without executing the proposal."""
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)

    check = validate_ai_advisory(proposal)
    if not check.get("valid"):
        raise ValueError("invalid ActionProposal: " + "; ".join(check.get("errors") or []))
    if proposal.get("schema") != ACTION_PROPOSAL_SCHEMA:
        raise ValueError("human approval accepts only labbridge.action-proposal/v1")
    if proposal.get("executed") is True:
        raise ValueError("ActionProposal must remain executed=false before review")

    normalized_decision = str(decision).strip().lower()
    if normalized_decision not in DECISIONS:
        raise ValueError("decision must be approved or rejected")
    reviewer = str(reviewer).strip()
    reason = str(reason).strip()
    if not reviewer:
        raise ValueError("reviewer is required")
    if not reason:
        raise ValueError("review reason is required")

    proposal_id = str(proposal.get("packet_id") or "")
    proposal_sha = str(proposal.get("content_sha256") or "")
    stable = {
        "schema": APPROVAL_SCHEMA,
        "project_id": project["project_id"],
        "proposal_id": proposal_id,
        "proposal_sha256": proposal_sha,
        "decision": normalized_decision,
        "reviewer": reviewer,
        "reason": reason,
        "reviewed_at": utc_now(),
        "executed": False,
        "boundary": (
            "Approval is a human authorization record only. It does not execute hardware, run a solver, mutate parameters, "
            "or create measurement evidence. A valid Experiment Manifest is still required for any downstream experiment."
        ),
    }
    digest = _canonical_sha(stable)
    record = {**stable, "approval_id": f"action-approval-{digest[:20]}", "sha256": digest}
    target = _approval_root(path) / f"{record['approval_id']}.json"
    _atomic_json(target, record)

    event = append_event(
        path,
        event_type="action_proposal_review",
        source_role="human",
        title=f"ActionProposal {normalized_decision}: {proposal.get('title') or proposal.get('summary') or proposal_id}",
        body=reason,
        evidence_refs=[proposal_id, proposal_sha, record["approval_id"]],
        payload={
            "decision": normalized_decision,
            "reviewer": reviewer,
            "approval_sha256": digest,
            "executed": False,
        },
    )
    return {"approval": record, "journey_event": event, "executed": False}


def list_action_approvals(project_dir: str | Path, *, proposal_id: str = "") -> list[dict[str, Any]]:
    path = Path(project_dir).expanduser().resolve()
    projects.open_project(path)
    rows: list[dict[str, Any]] = []
    for file in _approval_root(path).glob("*.json"):
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(value, dict) or value.get("schema") != APPROVAL_SCHEMA:
            continue
        if proposal_id and str(value.get("proposal_id") or "") != proposal_id:
            continue
        rows.append(value)
    rows.sort(key=lambda row: str(row.get("reviewed_at") or ""), reverse=True)
    return rows


def latest_action_decision(project_dir: str | Path, proposal_id: str) -> dict[str, Any] | None:
    rows = list_action_approvals(project_dir, proposal_id=proposal_id)
    return rows[0] if rows else None


def authorize_experiment_manifest(
    project_dir: str | Path,
    *,
    proposal: Mapping[str, Any],
    manifest: Mapping[str, Any],
    reviewer: str,
) -> dict[str, Any]:
    """Link an approved ActionProposal to a separately authored valid manifest.

    This function intentionally does not register, queue, run, or execute the
    manifest. It creates a provenance authorization record that downstream UI or
    orchestration may require before offering an explicit run action.
    """
    path = Path(project_dir).expanduser().resolve()
    project = projects.open_project(path)

    proposal_check = validate_ai_advisory(proposal)
    if not proposal_check.get("valid") or proposal.get("schema") != ACTION_PROPOSAL_SCHEMA:
        raise ValueError("a valid labbridge.action-proposal/v1 packet is required")
    proposal_id = str(proposal.get("packet_id") or "")
    decision = latest_action_decision(path, proposal_id)
    if not decision or decision.get("decision") != "approved":
        raise PermissionError("ActionProposal has not been explicitly approved")
    if str(decision.get("proposal_sha256") or "") != str(proposal.get("content_sha256") or ""):
        raise ValueError("approved proposal fingerprint does not match supplied proposal")

    manifest_check = validate_manifest(manifest)
    if not manifest_check.get("valid"):
        raise ValueError("invalid Experiment Manifest: " + "; ".join(manifest_check.get("errors") or []))
    manifest_sha = str(manifest.get("experiment_sha256") or manifest_check.get("calculated_sha256") or "")
    if not manifest_sha:
        raise ValueError("Experiment Manifest fingerprint is unavailable")

    stable = {
        "schema": AUTHORIZATION_SCHEMA,
        "project_id": project["project_id"],
        "proposal_id": proposal_id,
        "proposal_sha256": str(proposal.get("content_sha256") or ""),
        "approval_id": str(decision.get("approval_id") or ""),
        "approval_sha256": str(decision.get("sha256") or ""),
        "experiment_sha256": manifest_sha,
        "profile": str(manifest.get("profile") or ""),
        "reviewer": str(reviewer).strip() or str(decision.get("reviewer") or ""),
        "authorized_at": utc_now(),
        "registered": False,
        "queued": False,
        "executed": False,
        "boundary": (
            "This record authorizes a specific Experiment Manifest fingerprint for later explicit registration/run handling. "
            "It does not itself register, queue, execute, or certify the experiment."
        ),
    }
    digest = _canonical_sha(stable)
    record = {**stable, "authorization_id": f"experiment-authorization-{digest[:20]}", "sha256": digest}
    target = _authorization_root(path) / f"{record['authorization_id']}.json"
    _atomic_json(target, record)

    event = append_event(
        path,
        event_type="experiment_manifest_authorized",
        source_role="human",
        title=f"Approved ActionProposal linked to Experiment Manifest · {manifest.get('profile')}",
        body="Human approval was linked to a specific validated Experiment Manifest fingerprint. No execution occurred.",
        evidence_refs=[proposal_id, record["approval_id"], manifest_sha, record["authorization_id"]],
        payload={"profile": manifest.get("profile"), "experiment_sha256": manifest_sha, "executed": False},
    )
    return {"authorization": record, "journey_event": event, "executed": False}
