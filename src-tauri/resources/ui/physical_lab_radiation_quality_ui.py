"""UI for manufacturing-seed radiation quality degradation analysis."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
from typing import Any


def _load_core():
    try:
        import physical_lab_radiation_quality as core
        return core
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radiation_quality.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_quality", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        core = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_quality", core)
        spec.loader.exec_module(core)
        return core


def render_radiation_quality_workspace(st: Any, profile: str) -> None:
    if profile != "radia-magnet-studio":
        return
    result = st.session_state.get("pl_rrp_result")
    if not result:
        return

    core = _load_core()
    try:
        summary = core.summarize_radiation_quality(result.get("nominal") or {}, result.get("members") or [])
    except Exception as exc:
        st.warning(f"Radiation-quality degradation analysis could not be formed: {exc}")
        return

    import pandas as pd
    import plotly.graph_objects as go

    st.markdown("---")
    st.markdown("## Physical Lab · Manufacturing → Radiation Quality Degradation")
    st.caption(
        "Reuse the completed RADIA → trajectory → radiation manufacturing ensemble to compare polarization, harmonic contamination, linewidth and photon-energy changes against the nominal device."
    )

    metric_rows = []
    for metric, row in summary.get("metrics", {}).items():
        metric_rows.append({"metric": metric, **row})
    if metric_rows:
        st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)

    frame = pd.DataFrame(summary.get("members") or [])
    if not frame.empty:
        available = [m for m in core.QUALITY_METRICS if m in frame.columns and pd.to_numeric(frame[m], errors="coerce").notna().any()]
        if available:
            metric = st.selectbox("Radiation-quality observable", available, key="pl_rad_quality_metric")
            y = pd.to_numeric(frame[metric], errors="coerce")
            nominal = summary.get("nominal", {}).get(metric)
            fig = go.Figure()
            fig.add_scatter(x=frame["seed"], y=y, mode="lines+markers", name="manufacturing realization")
            if nominal is not None:
                fig.add_hline(y=float(nominal), line_dash="dash", annotation_text="nominal")
            fig.update_layout(title=f"Manufacturing error → {metric}", xaxis_title="Manufacturing seed", yaxis_title=metric, height=480)
            st.plotly_chart(fig, width="stretch")

    ranking = pd.DataFrame(summary.get("diagnosticRanking") or [])
    if not ranking.empty:
        st.markdown("#### Seeds ranked by multi-observable deviation")
        st.dataframe(ranking, width="stretch", hide_index=True)
        st.caption(
            "The deviation score is deliberately not labeled a quality score: it only ranks these simulated seeds by combined departure from nominal across available polarization/harmonic/linewidth diagnostics."
        )

    st.caption(summary.get("boundary", ""))
