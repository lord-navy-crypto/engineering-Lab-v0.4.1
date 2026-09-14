"""UI for provenance-preserving Morris design → Sweep integration."""
from __future__ import annotations

from typing import Any

import pandas as pd

import physical_lab_sweep_executor as sweeps
from physical_lab_applied_analysis_advanced import adapter_parameter_names, morris_design
from physical_lab_sweep_design_bridge import BOUNDARY, prepare_rows_preserving_metadata, queue_design_with_metadata


def _factors(st: Any, profile: str) -> list[dict[str, Any]] | None:
    text = st.text_area(
        "Morris factors (`name, low, high`)",
        value="factor_a,0,1\nfactor_b,0,1",
        height=120,
        key=f"pl_morris_bridge_factors_{profile}",
    )
    out = []
    try:
        for line in text.splitlines():
            if not line.strip():
                continue
            name, low, high = [x.strip() for x in line.split(",", 2)]
            out.append({"name": name, "low": float(low), "high": float(high)})
    except Exception:
        st.warning("Factor syntax must be `name, low, high`, one factor per line.")
        return None
    return out


def render_sweep_design_bridge(st: Any, profile: str) -> None:
    st.markdown("#### Morris → Sweep · Provenance Bridge")
    st.caption("Reserved trajectory metadata is preserved through execution and returned to downstream Morris analysis. Queueing never starts computation automatically.")
    factors = _factors(st, profile)
    if not factors:
        return
    adapters = sweeps.available_adapters(profile)
    if not adapters:
        st.info("No allow-listed Sweep adapter is registered for the current profile.")
        return
    ids = [a["id"] for a in adapters]
    labels = {a["id"]: a["label"] for a in adapters}
    c1, c2, c3, c4 = st.columns(4)
    adapter = c1.selectbox("Adapter", ids, format_func=lambda x: labels.get(x, x), key=f"pl_morris_bridge_adapter_{profile}")
    trajectories = int(c2.number_input("Trajectories", min_value=2, max_value=100, value=8, key=f"pl_morris_bridge_t_{profile}"))
    levels = int(c3.number_input("Levels", min_value=4, max_value=20, value=6, key=f"pl_morris_bridge_l_{profile}"))
    seed = int(c4.number_input("Seed", min_value=0, value=0, key=f"pl_morris_bridge_seed_{profile}"))
    try:
        accepted = adapter_parameter_names(profile, adapter)
        design = morris_design(factors, trajectories=trajectories, levels=levels, seed=seed)
        prepared = prepare_rows_preserving_metadata(profile, adapter, design["rows"])
    except Exception as exc:
        st.warning(f"Morris design is not compatible with this adapter: {exc}")
        return
    st.caption(f"Adapter parameters: {', '.join(accepted)}")
    table = pd.DataFrame(prepared)
    st.dataframe(table.head(500), hide_index=True, width="stretch")
    st.caption("Morris provenance fields `__trajectory`, `__step`, and `__changed_factor` are preserved as analysis metadata; columns beginning with `__` are never passed as model parameters.")
    if st.button("Queue Morris design as Sweep", type="primary", key=f"pl_morris_bridge_queue_{profile}"):
        try:
            job = queue_design_with_metadata(profile, adapter, prepared)
            st.session_state[f"pl_morris_bridge_job_{profile}"] = job
            st.success(f"Queued {job['id']} · {job['point_count']} points. Execution has NOT started; trajectory metadata will be preserved.")
        except Exception as exc:
            st.error(f"Could not queue Morris sweep: {exc}")
    job = st.session_state.get(f"pl_morris_bridge_job_{profile}")
    if job:
        st.json({k: job.get(k) for k in ("id", "adapter", "point_count", "status", "execution_started", "design_metadata_preserved", "boundary")})
        if st.button("Explicitly start Morris Sweep", key=f"pl_morris_bridge_start_{profile}"):
            try:
                started = sweeps.start_sweep_job(str(job["id"]))
                st.session_state[f"pl_morris_bridge_job_{profile}"] = {**job, **started, "execution_started": True}
                st.success(f"Started {started['id']} · status {started['status']}")
            except Exception as exc:
                st.error(f"Could not start Morris sweep: {exc}")
    st.caption(BOUNDARY)
