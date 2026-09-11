"""Global Research Orchestrator UI for reusable sweep/data/convergence workflows."""
from __future__ import annotations

import csv
import io
from typing import Any

from physical_lab_research_orchestrator import (
    cartesian_parameter_grid,
    compare_numeric_runs,
    convergence_diagnostics,
    parse_numeric_table,
)


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader(); writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _render_sweep(st: Any, profile: str) -> None:
    st.markdown("### Parameter Sweep Designer")
    st.caption("Build a bounded Cartesian design that can be reused by any model. This designs runs; it does not execute arbitrary code.")
    axis_count = int(st.selectbox("Number of sweep parameters", [1, 2, 3], index=1, key=f"pl_orch_axes_{profile}"))
    defaults = [("parameter_a", 0.0, 1.0, 5), ("parameter_b", 0.0, 1.0, 5), ("parameter_c", 0.1, 10.0, 4)]
    axes = []
    for i in range(axis_count):
        name0, lo0, hi0, n0 = defaults[i]
        c1,c2,c3,c4,c5 = st.columns([1.4,1,1,0.8,0.9])
        name = c1.text_input(f"Axis {i+1} name", value=name0, key=f"pl_orch_name_{profile}_{i}")
        low = float(c2.number_input("Low", value=float(lo0), key=f"pl_orch_low_{profile}_{i}"))
        high = float(c3.number_input("High", value=float(hi0), key=f"pl_orch_high_{profile}_{i}"))
        count = int(c4.number_input("Count", min_value=1, max_value=101, value=int(n0), step=1, key=f"pl_orch_count_{profile}_{i}"))
        scale = c5.selectbox("Scale", ["linear", "log"], index=0, key=f"pl_orch_scale_{profile}_{i}")
        axes.append({"name":name,"low":low,"high":high,"count":count,"scale":scale})
    if st.button("Build bounded sweep design", type="primary", key=f"pl_orch_build_{profile}"):
        st.session_state[f"pl_orch_design_{profile}"] = cartesian_parameter_grid(axes)
    r = st.session_state.get(f"pl_orch_design_{profile}")
    if r:
        st.metric("Design points", r["point_count"])
        st.dataframe(r["rows"][:200], hide_index=True, width="stretch")
        st.download_button("Download sweep design CSV", data=_csv_bytes(r["rows"]), file_name=f"physical_lab_{profile}_sweep.csv", mime="text/csv", key=f"pl_orch_download_{profile}")
        st.caption(r["boundary"])


def _render_table_and_convergence(st: Any, profile: str) -> None:
    st.markdown("### Measurement / Result Table")
    upload = st.file_uploader("CSV or TSV numeric table", type=["csv","tsv"], key=f"pl_orch_table_upload_{profile}")
    if upload is not None and st.button("Parse numeric table", key=f"pl_orch_parse_{profile}"):
        st.session_state[f"pl_orch_table_{profile}"] = parse_numeric_table(upload.getvalue(), filename=upload.name)
    r = st.session_state.get(f"pl_orch_table_{profile}")
    if not r:
        return
    a,b,c = st.columns(3); a.metric("Rows", r["row_count"]); b.metric("Columns", len(r["columns"])); c.metric("Numeric columns", len(r["numeric_columns"]))
    st.dataframe(r["summaries"], hide_index=True, width="stretch")
    if r["preview"]: st.dataframe(r["preview"], hide_index=True, width="stretch")
    st.caption(r["boundary"])

    numeric = list(r["numeric_columns"])
    if len(numeric) >= 2:
        st.markdown("#### Automatic convergence study")
        c1,c2 = st.columns(2)
        hx = c1.selectbox("Resolution / step-size column", numeric, key=f"pl_orch_h_{profile}")
        ey = c2.selectbox("Positive error column", numeric, index=min(1,len(numeric)-1), key=f"pl_orch_e_{profile}")
        if st.button("Estimate observed convergence order", key=f"pl_orch_conv_{profile}"):
            h=[]; e=[]
            for hv,ev in zip(r["column_data"][hx], r["column_data"][ey]):
                if hv is not None and ev is not None:
                    h.append(hv); e.append(ev)
            st.session_state[f"pl_orch_conv_result_{profile}"] = convergence_diagnostics(h,e)
        conv = st.session_state.get(f"pl_orch_conv_result_{profile}")
        if conv:
            a,b,c = st.columns(3)
            a.metric("Observed order p", f"{conv['observed_order']:.5g}")
            b.metric("log-log R²", f"{conv['loglog_r2']:.5f}")
            c.metric("Finest error", f"{conv['finest_error']:.4e}")
            st.dataframe([{"resolution":h,"error":e} for h,e in zip(conv["resolution"],conv["error"])], hide_index=True, width="stretch")
            st.caption(conv["boundary"])

    if len(numeric) >= 1 and r["row_count"] >= 2:
        st.markdown("#### Baseline run comparison")
        selected = st.multiselect("Metrics to compare", numeric, default=numeric[:min(4,len(numeric))], key=f"pl_orch_metrics_{profile}")
        baseline = int(st.number_input("Baseline row index", min_value=0, max_value=max(0,r["row_count"]-1), value=0, step=1, key=f"pl_orch_base_{profile}"))
        if selected and st.button("Compare rows to baseline", key=f"pl_orch_compare_{profile}"):
            rows=[]
            for i in range(r["row_count"]):
                row={k:r["column_data"][k][i] for k in selected}
                if all(v is not None for v in row.values()): rows.append(row)
            if len(rows) >= 2:
                bidx = min(baseline, len(rows)-1)
                st.session_state[f"pl_orch_compare_result_{profile}"] = compare_numeric_runs(rows, baseline_index=bidx)
        comp = st.session_state.get(f"pl_orch_compare_result_{profile}")
        if comp:
            st.dataframe(comp["rows"], hide_index=True, width="stretch")
            st.caption(comp["boundary"])


def render_research_orchestrator(st: Any, profile: str) -> None:
    st.markdown("---")
    with st.expander("Physical Lab · Research Orchestrator", expanded=False):
        st.caption("Reusable platform tools for designing sweeps, turning tables into numeric evidence, estimating convergence, and comparing runs across the active model profile.")
        tabs = st.tabs(["Sweep Designer", "Data / Convergence / Compare"])
        with tabs[0]: _render_sweep(st, profile)
        with tabs[1]: _render_table_and_convergence(st, profile)
