"""Scoped OpenPenguin advisory controls for Engineering Lab scientific objects."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from physical_lab_analysis_plan_store import save_analysis_plan
from physical_lab_science_protocol import (
    SCIENCE_BOUNDARY,
    build_scientific_context_packet,
    request_analysis_plan,
    request_scientific_explanation,
)
from physical_lab_visual_analytics_ui import _sources


HANDOFF_SCHEMA = "engineering-lab-analysis-plan-handoff-v1"


def _prepare_handoff(plan: Mapping[str, Any], context_packet: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    scientific = context_packet.get("scientific_context") if isinstance(context_packet.get("scientific_context"), Mapping) else {}
    return {
        "schema": HANDOFF_SCHEMA,
        "source_id": str(source.get("id") or ""),
        "source_identity": dict(source.get("identity") or {}) if isinstance(source.get("identity"), Mapping) else {},
        "context_packet_id": str(context_packet.get("packet_id") or ""),
        "active_object": scientific.get("active_object"),
        "plan": dict(plan),
        "executed": False,
        "mutation_authority": False,
        "boundary": "Prepared controls are an advisory handoff only. Engineering Lab must still validate and explicitly execute any analysis step.",
    }


def render_science_protocol_ui(st: Any, profile: str, project_path: str | Path) -> None:
    project = Path(project_path)
    st.markdown("#### OpenPenguin Scientific Advisory")
    st.caption(
        "Ask OpenPenguin about one bounded Engineering Lab scientific object. Eligible analyses are determined by Engineering Lab first; "
        "OpenPenguin may explain or propose a plan, but cannot execute analyses or create scientific evidence."
    )

    sources = _sources(project)
    external_source = st.session_state.get(f"pl_utube_science_source_{profile}")
    if isinstance(external_source, Mapping):
        sources.append(dict(external_source))
    if not sources:
        st.info("No project Result, completed Sweep, canonical Dataset, or registered experiment source is currently available for scoped scientific advisory.")
        return

    labels = [str(row.get("label") or row.get("id")) for row in sources]
    selected_label = st.selectbox("Scientific object", labels, key=f"pl_op_science_source_{profile}")
    source = sources[labels.index(selected_label)]
    context = build_scientific_context_packet(project, profile=profile, focus="science-analysis", source=source)
    scientific = context.get("scientific_context") if isinstance(context.get("scientific_context"), Mapping) else {}
    capabilities = [str(row.get("capability_id")) for row in scientific.get("capabilities", []) if isinstance(row, Mapping)]

    a, b, c = st.columns(3)
    a.metric("Source kind", str(source.get("kind") or "unknown"))
    b.metric("Rows", int((scientific.get("active_object") or {}).get("rows") or 0))
    c.metric("Eligible analyses", len(capabilities))
    with st.expander("Scientific context / eligibility", expanded=False):
        st.json({
            "packet_id": context.get("packet_id"),
            "active_object": scientific.get("active_object"),
            "eligible_capabilities": capabilities,
            "authority": scientific.get("authority"),
            "interpretation_constraints": scientific.get("interpretation_constraints"),
        })

    question = st.text_area(
        "Question for OpenPenguin",
        placeholder="e.g. Which analysis should I use to understand parameter influence, and what assumptions should I check?",
        key=f"pl_op_science_question_{profile}",
    )
    col_explain, col_plan = st.columns(2)
    if col_explain.button("Ask OpenPenguin about this", disabled=not question.strip(), key=f"pl_op_science_explain_{profile}"):
        st.session_state[f"pl_op_science_answer_{profile}"] = request_scientific_explanation(context, question=question)
    if col_plan.button("Request Analysis Plan", disabled=not question.strip(), key=f"pl_op_science_plan_{profile}"):
        st.session_state[f"pl_op_science_plan_result_{profile}"] = request_analysis_plan(context, question=question)
        st.session_state[f"pl_op_science_plan_context_{profile}"] = context
        st.session_state[f"pl_op_science_plan_source_{profile}"] = source

    answer = st.session_state.get(f"pl_op_science_answer_{profile}")
    if isinstance(answer, Mapping):
        st.markdown("##### OpenPenguin explanation")
        st.write(str(answer.get("summary") or answer.get("answer") or "No advisory text returned."))
        st.caption("Advisory interpretation only · not scientific evidence · no execution authority")

    plan_result = st.session_state.get(f"pl_op_science_plan_result_{profile}")
    plan_context = st.session_state.get(f"pl_op_science_plan_context_{profile}")
    plan_source = st.session_state.get(f"pl_op_science_plan_source_{profile}")
    if isinstance(plan_result, Mapping):
        st.markdown("##### Proposed Analysis Plan")
        if plan_result.get("valid") and isinstance(plan_result.get("plan"), Mapping):
            plan = plan_result["plan"]
            st.success("Plan passed Engineering Lab capability/authority validation. It has not been executed.")
            st.json(plan)
            x, y = st.columns(2)
            if x.button("Prepare in Engineering Lab", key=f"pl_op_science_prepare_{profile}"):
                handoff = _prepare_handoff(plan, plan_context if isinstance(plan_context, Mapping) else context, plan_source if isinstance(plan_source, Mapping) else source)
                st.session_state[f"pl_science_analysis_handoff_{profile}"] = handoff
                st.success("Prepared an advisory handoff. No analysis was executed and no scientific record was mutated.")
            if y.button("Record plan provenance", key=f"pl_op_science_record_{profile}"):
                rec = save_analysis_plan(project, plan=plan, context_packet=plan_context if isinstance(plan_context, Mapping) else context)
                st.success(f"Recorded {rec['plan_record_id']} · sha256 {rec['sha256'][:16]}…")
        else:
            st.warning("The proposed plan did not pass Engineering Lab validation.")
            st.json({"errors": list(plan_result.get("errors") or []), "executed": False, "mutation_authority": False})

    prepared = st.session_state.get(f"pl_science_analysis_handoff_{profile}")
    if isinstance(prepared, Mapping):
        with st.expander("Prepared Engineering Lab handoff", expanded=False):
            st.json(prepared)
            st.caption("Prepared ≠ executed. The target Engineering Lab workspace remains responsible for deterministic execution and result provenance.")

    st.caption(SCIENCE_BOUNDARY)
