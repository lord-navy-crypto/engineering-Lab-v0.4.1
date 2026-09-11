"""UI for manufacturing-seed radiation quality degradation analysis."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
from typing import Any, Mapping


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


def _load_sensitivity():
    try:
        import physical_lab_radiation_sensitivity as mod
        return mod
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radiation_sensitivity.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_sensitivity", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_sensitivity", mod)
        spec.loader.exec_module(mod)
        return mod


def _render_sensitivity(st: Any, namespace: Mapping[str, Any] | None) -> None:
    if not namespace:
        return
    sens = _load_sensitivity()
    params = dict(namespace.get("current_params") or {})
    magnitudes = {k: float(params.get(k, 0.0) or 0.0) for k in sens.ERROR_KEYS}
    active = [k for k, v in magnitudes.items() if abs(v) > 0.0]

    st.markdown("### Manufacturing Error → Radiation Sensitivity")
    st.caption(
        "One-factor-at-a-time screening: keep one configured manufacturing-error family active, set the other error magnitudes to zero, rebuild the real RADIA field for fixed seeds, then propagate through the pinned scalar trajectory/radiation solver."
    )
    if not active:
        st.info("Configure at least one non-zero RADIA manufacturing-error magnitude to run sensitivity screening.")
        return

    st.write("Active configured error families: " + ", ".join(active))
    c1, c2, c3 = st.columns(3)
    with c1:
        gamma = st.number_input("Sensitivity electron γ", min_value=2.0, max_value=100000.0, value=200.0, step=10.0, key="pl_rad_sens_gamma")
    with c2:
        seed_start = st.number_input("Sensitivity seed start", min_value=0, max_value=100000000, value=31001, step=1, key="pl_rad_sens_seed")
    with c3:
        seed_count = st.selectbox("Seeds per error family", [2, 3], index=0, key="pl_rad_sens_seed_count")

    if st.button("Run one-factor radiation sensitivity", key="pl_run_rad_sensitivity", type="secondary"):
        try:
            with st.spinner("Rebuilding isolated RADIA error families and propagating radiation..."):
                result = sens.run_one_factor_sensitivity(
                    namespace,
                    seeds=[int(seed_start) + i for i in range(int(seed_count))],
                    gamma=float(gamma),
                    transverse_points=3,
                    z_samples_per_period=8,
                    tracking_points_per_period=24,
                )
            st.session_state["pl_rad_sensitivity_result"] = result
        except Exception as exc:
            st.error(f"Radiation sensitivity screening failed: {exc}")

    result = st.session_state.get("pl_rad_sensitivity_result")
    if not result:
        return

    import pandas as pd
    import plotly.graph_objects as go

    summary = result.get("summary") or {}
    rows = pd.DataFrame(summary.get("rows") or [])
    leaders = summary.get("leadersByMetric") or {}
    if leaders:
        leader_rows = [{"metric": metric, **info} for metric, info in leaders.items()]
        st.markdown("#### Largest median |Δ| at the configured perturbation magnitude")
        st.dataframe(pd.DataFrame(leader_rows), width="stretch", hide_index=True)

    if not rows.empty:
        metric_options = sorted(rows["metric"].dropna().unique().tolist())
        metric = st.selectbox("Sensitivity observable", metric_options, key="pl_rad_sens_metric")
        sub = rows[rows["metric"] == metric].copy()
        st.dataframe(sub, width="stretch", hide_index=True)
        fig = go.Figure()
        fig.add_bar(x=sub["error"], y=sub["medianAbsDelta"], name="median |Δ|")
        fig.add_scatter(x=sub["error"], y=sub["maxAbsDelta"], mode="markers", name="max |Δ|")
        fig.update_layout(
            title=f"Configured manufacturing perturbation → {metric}",
            xaxis_title="Isolated manufacturing-error family",
            yaxis_title=f"absolute Δ {metric}",
            height=460,
        )
        st.plotly_chart(fig, width="stretch")

    st.caption(result.get("boundary", ""))


def render_radiation_quality_workspace(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
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
    st.markdown("---")
    _render_sensitivity(st, namespace)
