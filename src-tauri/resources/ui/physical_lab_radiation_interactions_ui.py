"""UI for bounded pairwise manufacturing-error radiation interaction screening."""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path
import sys
from typing import Any, Mapping


def _load_core():
    try:
        import physical_lab_radiation_interactions as core
        return core
    except ModuleNotFoundError:
        path = Path(__file__).with_name("physical_lab_radiation_interactions.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_interactions", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        core = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_interactions", core)
        spec.loader.exec_module(core)
        return core


def _load_response_surface_ui():
    try:
        import physical_lab_radiation_response_surface_ui as mod
        return mod
    except ModuleNotFoundError:
        core_path = Path(__file__).with_name("physical_lab_radiation_response_surface.py")
        core_spec = importlib.util.spec_from_file_location("physical_lab_radiation_response_surface", core_path)
        if core_spec is None or core_spec.loader is None:
            raise ImportError(f"Unable to load {core_path}")
        core = importlib.util.module_from_spec(core_spec)
        sys.modules.setdefault("physical_lab_radiation_response_surface", core)
        core_spec.loader.exec_module(core)
        path = Path(__file__).with_name("physical_lab_radiation_response_surface_ui.py")
        spec = importlib.util.spec_from_file_location("physical_lab_radiation_response_surface_ui", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("physical_lab_radiation_response_surface_ui", mod)
        spec.loader.exec_module(mod)
        return mod


def render_radiation_interactions_workspace(st: Any, profile: str, namespace: Mapping[str, Any] | None = None) -> None:
    if profile != "radia-magnet-studio" or not namespace:
        return
    core = _load_core()
    params = dict(namespace.get("current_params") or {})
    magnitudes = {k: float(params.get(k, 0.0) or 0.0) for k in core.ERROR_KEYS}
    active = [k for k, v in magnitudes.items() if abs(v) > 0.0]
    if len(active) < 2:
        return

    st.markdown("---")
    st.markdown("### Manufacturing Error Pair → Radiation Interaction")
    st.caption(
        "Two-factor local screening. For each selected pair A,B and fixed seed, run nominal / A-only / B-only / A+B and compute the second-order contrast y(A+B)-y(A)-y(B)+y(0). This measures non-additivity after removing the two main effects."
    )

    pair_labels = [f"{a} × {b}" for a, b in itertools.combinations(active, 2)]
    label_to_pair = {f"{a} × {b}": (a, b) for a, b in itertools.combinations(active, 2)}
    selected = st.multiselect(
        "Error pairs (max 3)",
        pair_labels,
        default=pair_labels[: min(2, len(pair_labels))],
        max_selections=3,
        key="pl_rad_interaction_pairs",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        gamma = st.number_input("Interaction electron γ", min_value=2.0, max_value=100000.0, value=200.0, step=10.0, key="pl_rad_interaction_gamma")
    with c2:
        seed = st.number_input("Interaction seed", min_value=0, max_value=100000000, value=41001, step=1, key="pl_rad_interaction_seed")
    with c3:
        second_seed = st.checkbox("Use second seed", value=False, key="pl_rad_interaction_second_seed")

    if st.button("Run pairwise interaction screening", key="pl_run_rad_interactions", type="secondary"):
        if not selected:
            st.warning("Select at least one manufacturing-error pair.")
        else:
            try:
                seeds = [int(seed), int(seed) + 1] if second_seed else [int(seed)]
                with st.spinner("Running nominal / A / B / A+B RADIA → radiation contrasts..."):
                    result = core.run_pair_interactions(
                        namespace,
                        pairs=[label_to_pair[label] for label in selected],
                        seeds=seeds,
                        gamma=float(gamma),
                        transverse_points=3,
                        z_samples_per_period=8,
                        tracking_points_per_period=24,
                    )
                st.session_state["pl_rad_interaction_result"] = result
            except Exception as exc:
                st.error(f"Pairwise radiation interaction screening failed: {exc}")

    result = st.session_state.get("pl_rad_interaction_result")
    if result:
        import pandas as pd
        import plotly.graph_objects as go

        summary = result.get("summary") or {}
        grouped = pd.DataFrame(summary.get("grouped") or [])
        leaders = summary.get("leadersByMetric") or {}
        if leaders:
            st.markdown("#### Largest pairwise non-additivity by observable")
            st.dataframe(pd.DataFrame([{"metric": m, **v} for m, v in leaders.items()]), width="stretch", hide_index=True)

        if not grouped.empty:
            metrics = sorted(grouped["metric"].dropna().unique().tolist())
            metric = st.selectbox("Interaction observable", metrics, key="pl_rad_interaction_metric")
            sub = grouped[grouped["metric"] == metric].copy()
            sub["pair"] = sub["errorA"] + " × " + sub["errorB"]
            st.dataframe(sub, width="stretch", hide_index=True)
            fig = go.Figure()
            fig.add_bar(x=sub["pair"], y=sub["medianAbsInteractionResidual"], name="median |interaction|")
            fig.add_scatter(x=sub["pair"], y=sub["maxAbsInteractionResidual"], mode="markers", name="max |interaction|")
            fig.update_layout(
                title=f"Pairwise non-additivity → {metric}",
                xaxis_title="Manufacturing-error pair",
                yaxis_title=f"interaction residual in {metric}",
                height=460,
            )
            st.plotly_chart(fig, width="stretch")
        st.caption(result.get("boundary", ""))

    try:
        _load_response_surface_ui().render_radiation_response_surface_workspace(st, profile, namespace)
    except Exception as exc:
        st.warning(f"Local radiation response-surface workspace could not load: {exc}")
