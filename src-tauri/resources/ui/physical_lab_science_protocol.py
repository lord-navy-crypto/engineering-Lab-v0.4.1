"""Scientific protocol between Engineering Lab and OpenPenguin.

Engineering Lab remains the scientific computation/evidence authority. OpenPenguin may
reason over bounded scientific context, propose analyses, and explain deterministic
results, but it never becomes measurement evidence and never gains execution authority.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from physical_lab_labbridge import AI_CONTEXT_SCHEMA, build_ai_context_packet, finalize_packet
from physical_lab_openguin_adapter import request_advisory
from physical_lab_visualization_studio import numeric_columns

SCIENCE_CONTEXT_SCHEMA = "engineering-lab-scientific-context-v1"
ANALYSIS_PLAN_SCHEMA = "engineering-lab-analysis-plan-v1"
CLAIM_SCHEMA = "engineering-lab-evidence-claim-v1"

SCIENCE_BOUNDARY = (
    "OpenPenguin may interpret bounded Engineering Lab scientific objects and propose deterministic analyses. "
    "It must not invent measurements, alter scientific records, claim validation, or execute analysis/model/experiment steps. "
    "Engineering Lab remains the scientific computation and evidence authority."
)

CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "correlation": {
        "category": "statistical",
        "label": "Correlation matrix",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["correlation does not establish causality"],
    },
    "regression-diagnostics": {
        "category": "statistical",
        "label": "Regression + residual diagnostics",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["fit quality does not establish the correct physical law"],
    },
    "robust-regression": {
        "category": "statistical",
        "label": "Huber robust regression",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["downweighted observations are not automatically invalid measurements"],
    },
    "bootstrap": {
        "category": "statistical",
        "label": "Bootstrap resampling",
        "minimum_numeric_columns": 1,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["bootstrap intervals inherit sampling/data assumptions"],
    },
    "pca-svd": {
        "category": "linear-algebra",
        "label": "PCA / SVD",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["principal components are not automatically physical latent variables"],
    },
    "conditioning": {
        "category": "linear-algebra",
        "label": "Conditioning diagnostics",
        "minimum_numeric_columns": 1,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["ill-conditioning indicates numerical sensitivity, not physical invalidity"],
    },
    "tsvd": {
        "category": "inverse",
        "label": "Truncated SVD inverse solve",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["retained rank is a numerical regularization choice, not a physical dimension claim"],
    },
    "tikhonov-gcv": {
        "category": "inverse",
        "label": "Tikhonov + GCV / L-curve",
        "minimum_numeric_columns": 2,
        "source_kinds": ["result", "sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["GCV/L-curve choices are numerical candidates, not physically correct constants"],
    },
    "sensitivity-screening": {
        "category": "sensitivity",
        "label": "Sensitivity screening",
        "minimum_numeric_columns": 2,
        "source_kinds": ["sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["sensitivity screening does not establish causality or global importance"],
    },
    "morris-effects": {
        "category": "sensitivity",
        "label": "Morris elementary effects",
        "minimum_numeric_columns": 2,
        "source_kinds": ["sweep", "dataset"],
        "required_columns": ["__trajectory", "__step", "__changed_factor"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["mu* is a screening magnitude, not a causal effect estimate"],
    },
    "factorial-effects": {
        "category": "design-analysis",
        "label": "Two-level factorial effects",
        "minimum_numeric_columns": 2,
        "source_kinds": ["sweep", "dataset"],
        "requires_two_level_parameter": True,
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["factorial effects describe observed design contrasts and do not establish causality"],
    },
    "response-surface": {
        "category": "sensitivity",
        "label": "Response surface",
        "minimum_numeric_columns": 3,
        "source_kinds": ["sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["response surfaces describe sampled structure and do not validate interpolation or causality"],
    },
    "pareto": {
        "category": "decision-support",
        "label": "Pareto frontier",
        "minimum_numeric_columns": 2,
        "source_kinds": ["sweep", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["non-dominance is not physical optimality or feasibility"],
    },
    "unit-aware-compare": {
        "category": "comparison",
        "label": "Unit-aware comparison",
        "minimum_numeric_columns": 1,
        "source_kinds": ["result", "dataset"],
        "creates_evidence": False,
        "execution_authority": "engineering-lab-only",
        "interpretation_constraints": ["unit compatibility does not establish calibration or experimental equivalence"],
    },
    "doe-proposal": {
        "category": "design",
        "label": "Design of experiments proposal",
        "minimum_numeric_columns": 0,
        "source_kinds": ["result", "sweep", "dataset", "project"],
        "creates_evidence": False,
        "execution_authority": "proposal-only",
        "interpretation_constraints": ["a DOE proposal is not an experiment, measurement, or evidence"],
    },
}


def scientific_capabilities() -> list[dict[str, Any]]:
    return [{"capability_id": key, **dict(value)} for key, value in sorted(CAPABILITY_REGISTRY.items())]


def source_descriptor(source: Mapping[str, Any]) -> dict[str, Any]:
    frame = source.get("frame") if isinstance(source.get("frame"), pd.DataFrame) else pd.DataFrame()
    kind = str(source.get("kind") or "unknown")
    units = dict(source.get("units") or {}) if isinstance(source.get("units"), Mapping) else {}
    numeric = numeric_columns(frame) if not frame.empty else []
    columns = [str(c) for c in frame.columns]
    return {
        "source_id": str(source.get("id") or ""),
        "label": str(source.get("label") or source.get("id") or "Scientific source"),
        "kind": kind,
        "rows": int(len(frame)),
        "columns": columns[:250],
        "numeric_columns": numeric[:250],
        "units": {str(k): str(v) for k, v in units.items()},
        "identity": dict(source.get("identity") or {}) if isinstance(source.get("identity"), Mapping) else {},
    }


def eligible_capabilities(source: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if source is None:
        return [row for row in scientific_capabilities() if "project" in row.get("source_kinds", [])]
    desc = source_descriptor(source)
    kind = desc["kind"]
    numeric_count = len(desc["numeric_columns"])
    columns = set(desc["columns"])
    frame = source.get("frame") if isinstance(source.get("frame"), pd.DataFrame) else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for capability_id, spec in CAPABILITY_REGISTRY.items():
        if kind not in spec.get("source_kinds", []):
            continue
        if numeric_count < int(spec.get("minimum_numeric_columns") or 0):
            continue
        required = set(spec.get("required_columns") or [])
        if not required.issubset(columns):
            continue
        if spec.get("requires_two_level_parameter"):
            found = False
            for column in desc["numeric_columns"]:
                series = pd.to_numeric(frame[column], errors="coerce").dropna()
                if int(series.nunique()) == 2:
                    found = True
                    break
            if not found:
                continue
        rows.append({"capability_id": capability_id, **dict(spec)})
    return rows


def build_scientific_context_packet(
    project_dir: str | Path,
    *,
    profile: str = "",
    focus: str = "",
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = build_ai_context_packet(project_dir, profile=profile, focus=focus)
    stable = {k: v for k, v in base.items() if k not in {"packet_id", "content_sha256"}}
    desc = source_descriptor(source) if source is not None else None
    eligible = eligible_capabilities(source)
    constraints: list[str] = []
    for row in eligible:
        constraints.extend(str(x) for x in row.get("interpretation_constraints", []))
    stable["scientific_context"] = {
        "schema": SCIENCE_CONTEXT_SCHEMA,
        "base_context_packet_id": base.get("packet_id"),
        "active_object": desc,
        "capabilities": eligible,
        "claim_types": ["observation", "computed", "interpretation", "hypothesis", "recommendation"],
        "interpretation_constraints": sorted(set(constraints)),
        "authority": {
            "scientific_computation": "Engineering Lab only",
            "evidence_record": "Engineering Lab only",
            "openpenguin": "planning/explanation/advisory only",
            "execution": False,
            "mutation_authority": False,
        },
        "boundary": SCIENCE_BOUNDARY,
    }
    return finalize_packet(stable, prefix="ai-context")


def validate_analysis_plan(plan: Mapping[str, Any], *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if plan.get("schema") != ANALYSIS_PLAN_SCHEMA:
        errors.append(f"schema must be {ANALYSIS_PLAN_SCHEMA}")
    if plan.get("executed") is not False:
        errors.append("analysis plan must set executed=false")
    if plan.get("mutation_authority") is not False:
        errors.append("analysis plan must set mutation_authority=false")
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    if not steps:
        errors.append("analysis plan requires at least one step")
    allowed = set(CAPABILITY_REGISTRY)
    eligible = None
    if context and isinstance(context.get("scientific_context"), Mapping):
        eligible = {str(x.get("capability_id")) for x in context["scientific_context"].get("capabilities", []) if isinstance(x, Mapping)}
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"step {index} must be an object")
            continue
        capability = str(step.get("capability") or "")
        if capability not in allowed:
            errors.append(f"step {index} uses unknown capability {capability!r}")
        elif eligible is not None and capability not in eligible:
            errors.append(f"step {index} capability {capability!r} is not eligible for the active scientific object")
        if step.get("execute") is True:
            errors.append(f"step {index} cannot request execute=true")
    return {
        "valid": not errors,
        "errors": errors,
        "boundary": SCIENCE_BOUNDARY,
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    if not value:
        return None
    candidates = [value]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)
    first = value.find("{")
    last = value.rfind("}")
    if first >= 0 and last > first:
        candidates.append(value[first:last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def request_scientific_explanation(
    context_packet: Mapping[str, Any],
    *,
    question: str,
    model: str = "auto",
    temperature: float = 0.2,
) -> dict[str, Any]:
    prompt = (
        "You are OpenPenguin acting only as a scientific reasoning/advisory layer. "
        "Use the Engineering Lab scientific_context and its interpretation_constraints. "
        "Separate statements into observation/computed/interpretation/hypothesis/recommendation where useful. "
        "Do not claim execution, validation, causality, or evidence beyond cited Engineering Lab objects.\n\n"
        f"User question: {question}"
    )
    return request_advisory(context_packet, question=prompt, model=model, temperature=temperature)


def request_analysis_plan(
    context_packet: Mapping[str, Any],
    *,
    question: str,
    model: str = "auto",
    temperature: float = 0.1,
) -> dict[str, Any]:
    eligible = []
    scientific = context_packet.get("scientific_context") if isinstance(context_packet.get("scientific_context"), Mapping) else {}
    for row in scientific.get("capabilities", []):
        if isinstance(row, Mapping):
            eligible.append(str(row.get("capability_id")))
    prompt = (
        "Return ONLY a JSON object matching engineering-lab-analysis-plan-v1. "
        "The plan is advisory and must set executed=false and mutation_authority=false. "
        "Every step must use one of the eligible capability IDs below and must set execute=false. "
        "Do not include code or arbitrary tool names.\n"
        f"Eligible capabilities: {eligible}\n"
        "Required shape: {\"schema\":\"engineering-lab-analysis-plan-v1\",\"question\":\"...\","
        "\"steps\":[{\"capability\":\"...\",\"reason\":\"...\",\"arguments\":{},\"execute\":false}],"
        "\"assumptions\":[],\"executed\":false,\"mutation_authority\":false}.\n\n"
        f"User question: {question}"
    )
    advisory = request_advisory(context_packet, question=prompt, model=model, temperature=temperature)
    plan = _extract_json_object(str(advisory.get("summary") or ""))
    if plan is None:
        return {
            "valid": False,
            "errors": ["OpenPenguin did not return a parseable JSON analysis plan"],
            "advisory": advisory,
            "plan": None,
            "executed": False,
            "mutation_authority": False,
        }
    check = validate_analysis_plan(plan, context=context_packet)
    return {
        **check,
        "advisory": advisory,
        "plan": plan,
        "executed": False,
        "mutation_authority": False,
    }


def claim_record(*, text: str, claim_type: str, evidence_refs: Sequence[str], support_level: str = "supported") -> dict[str, Any]:
    claim_type = str(claim_type)
    if claim_type not in {"observation", "computed", "interpretation", "hypothesis", "recommendation"}:
        raise ValueError("unsupported claim_type")
    refs = [str(x) for x in evidence_refs if str(x)]
    if claim_type in {"observation", "computed"} and not refs:
        raise ValueError("observation/computed claims require evidence refs")
    return {
        "schema": CLAIM_SCHEMA,
        "claim_type": claim_type,
        "text": str(text),
        "evidence_refs": refs,
        "support_level": str(support_level),
        "executed": False,
        "mutation_authority": False,
    }
