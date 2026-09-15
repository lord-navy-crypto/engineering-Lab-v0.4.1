"""Advanced Applied Math & Statistics UI for Engineering Lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
import physical_lab_sweep_executor as sweeps
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_applied_analysis import design_experiment
from physical_lab_applied_analysis_advanced import (
    BOUNDARY,
    adapter_parameter_names,
    cross_validate_polynomials,
    factorial_effects,
    morris_design,
    morris_effects,
    prepare_sweep_rows,
    queue_design_as_sweep,
    robust_regression_huber,
)


def _factor_text(st: Any, profile: str, key_suffix: str = "advanced") -> list[dict[str, float | str]] | None:
    text = st.text_area(
        "Factors (`name, low, high`)",
        value="factor_a,0,1\nfactor_b,0,1",
        height=120,
        key=f"pl_adv_factors_{profile}_{key_suffix}",
    )
    factors = []
    try:
        for line in text.splitlines():
            if not line.strip():
                continue
            name, low, high = [x.strip() for x in line.split(",", 2)]
            factors.append({"name": name, "low": float(low), "high": float(high)})
    except Exception:
        st.warning("Factor syntax must be `name, low, high`, one factor per line.")
        return None
    return factors


def _robust_tab(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Robust regression requires at least two numeric fields.")
        return
    response = st.selectbox("Response Y", numeric, index=len(numeric)-1, key=f"pl_adv_robust_y_{profile}")
    candidates = [c for c in numeric if c != response]
    predictors = st.multiselect("Predictors", candidates, default=candidates[:min(3, len(candidates))], key=f"pl_adv_robust_x_{profile}")
    delta = float(st.slider("Huber delta", 0.5, 3.0, 1.345, 0.05, key=f"pl_adv_robust_delta_{profile}"))
    if not predictors:
        st.info("Select at least one predictor.")
        return
    try:
        result = robust_regression_huber(frame, predictors, response, delta=delta)
    except Exception as exc:
        st.warning(f"Robust regression unavailable: {exc}")
        return
    a, b, c, d = st.columns(4)
    a.metric("Converged", "yes" if result["converged"] else "no")
    b.metric("Iterations", result["iterations"])
    c.metric("RMSE", f"{result['rmse']:.5g}")
    d.metric("Downweighted", f"{100*result['downweighted_fraction']:.1f}%")
    st.dataframe(result["coefficients"], hide_index=True, width="stretch")
    diag = result["diagnostics"]
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(diag, x="predicted", y="residual", title="Robust residual vs fitted")
        fig.add_hline(y=0)
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    with c2:
        fig = px.scatter(diag, x="residual", y="weight", title="Huber weights")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption("Downweighting reduces sensitivity to large residuals; it does not prove that downweighted observations are mistakes or outliers.")


def _cv_tab(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Model selection requires at least two numeric fields.")
        return
    a, b, c, d = st.columns([1, 1, 1, 1])
    x = a.selectbox("Predictor X", numeric, key=f"pl_adv_cv_x_{profile}")
    y = b.selectbox("Response Y", [v for v in numeric if v != x], key=f"pl_adv_cv_y_{profile}")
    max_degree = int(c.number_input("Max degree", min_value=1, max_value=6, value=4, key=f"pl_adv_cv_degree_{profile}"))
    folds = int(d.number_input("Folds", min_value=2, max_value=min(20, max(len(frame), 2)), value=min(5, max(len(frame), 2)), key=f"pl_adv_cv_folds_{profile}"))
    seed = int(st.number_input("CV seed", min_value=0, value=0, step=1, key=f"pl_adv_cv_seed_{profile}"))
    try:
        result = cross_validate_polynomials(frame, x, y, degrees=range(1, max_degree + 1), folds=folds, seed=seed)
    except Exception as exc:
        st.warning(f"Cross-validation unavailable: {exc}")
        return
    if result.empty:
        st.info("No valid fold/model combinations were available.")
        return
    fig = px.line(result.sort_values("degree"), x="degree", y="cv_rmse_mean", error_y="cv_rmse_std", markers=True, title="K-fold CV error by polynomial degree")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.dataframe(result, hide_index=True, width="stretch")
    best = result.iloc[0]
    st.success(f"Lowest observed CV RMSE: degree {int(best['degree'])} · {best['cv_rmse_mean']:.6g}")
    st.caption("Lowest cross-validation error is a model-selection signal, not proof that the selected polynomial is the correct physical law.")


def _factorial_morris_tab(st: Any, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    method = st.radio(
        "Screening method",
        ["Two-level factorial effects", "Morris design", "Morris effects"],
        horizontal=True,
        key=f"pl_adv_screening_method_{profile}",
    )

    if method == "Two-level factorial effects":
        if len(numeric) < 2:
            st.info("Factorial effects require factors and a numeric response.")
            return
        response = st.selectbox("Response", numeric, index=len(numeric)-1, key=f"pl_adv_fact_y_{profile}")
        factors = st.multiselect("Two-level factors", [c for c in numeric if c != response], key=f"pl_adv_fact_x_{profile}")
        interactions = st.checkbox("Include pairwise interactions", value=True, key=f"pl_adv_fact_inter_{profile}")
        if not factors:
            return
        try:
            result = factorial_effects(frame, factors, response, include_interactions=interactions)
            effects = pd.DataFrame(result["effects"])
            fig = px.bar(effects, x="term", y="effect", color="kind", title=f"Factorial effects → {response}")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(effects, hide_index=True, width="stretch")
            st.caption(result["boundary"])
        except Exception as exc:
            st.warning(f"Factorial effects unavailable: {exc}")
        return

    if method == "Morris design":
        factors = _factor_text(st, profile, "morris")
        if not factors:
            return
        a, b, c = st.columns(3)
        trajectories = int(a.number_input("Trajectories", min_value=2, max_value=100, value=8, key=f"pl_adv_morris_t_{profile}"))
        levels = int(b.number_input("Grid levels", min_value=4, max_value=20, value=6, key=f"pl_adv_morris_l_{profile}"))
        seed = int(c.number_input("Seed", min_value=0, value=0, key=f"pl_adv_morris_seed_{profile}"))
        try:
            design = morris_design(factors, trajectories=trajectories, levels=levels, seed=seed)
            table = pd.DataFrame(design["rows"])
            st.metric("Proposed runs", len(table))
            st.dataframe(table.head(500), hide_index=True, width="stretch")
            st.download_button("Download Morris design CSV", data=table.to_csv(index=False).encode(), file_name="morris-design.csv", mime="text/csv", key=f"pl_adv_morris_dl_{profile}")
            st.caption(design["boundary"])
        except Exception as exc:
            st.warning(f"Morris design unavailable: {exc}")
        return

    meta = {"__trajectory", "__step", "__changed_factor"}
    if not meta.issubset(frame.columns):
        st.info("This source is not a completed Morris table; it must preserve __trajectory, __step and __changed_factor metadata plus a response column.")
        return
    response = st.selectbox("Morris response", [c for c in numeric if c not in {"__trajectory", "__step"}], key=f"pl_adv_morris_y_{profile}")
    factors = st.multiselect("Morris factor columns", [c for c in numeric if c not in {"__trajectory", "__step", response}], key=f"pl_adv_morris_fx_{profile}")
    if not factors:
        return
    try:
        effects = morris_effects(frame, response, factors)
        if not effects.empty:
            fig = px.scatter(effects, x="mu_star", y="sigma", text="factor", size="elementary_effects", title="Morris screening · μ* vs σ")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.dataframe(effects, hide_index=True, width="stretch")
            st.caption("μ* screens overall elementary-effect magnitude; σ indicates variation/nonlinearity/interactions. Neither is a causal effect estimate.")
    except Exception as exc:
        st.warning(f"Morris effects unavailable: {exc}")


def _doe_sweep_tab(st: Any, profile: str) -> None:
    st.markdown("#### Design → Queue → Explicit Start")
    st.caption("This bridge creates a queued allow-listed Sweep job only. It never starts computation automatically.")
    factors = _factor_text(st, profile, "sweep")
    if not factors:
        return
    adapters = sweeps.available_adapters(profile)
    if not adapters:
        st.info("No allow-listed Sweep Executor adapter is registered for the current profile.")
        return
    adapter_ids = [a["id"] for a in adapters]; labels = {a["id"]: a["label"] for a in adapters}
    adapter = st.selectbox("Allow-listed adapter", adapter_ids, format_func=lambda x: labels.get(x, x), key=f"pl_adv_sweep_adapter_{profile}")
    method = st.selectbox("Design method", ["latin-hypercube", "full-factorial", "central-composite", "random"], key=f"pl_adv_sweep_method_{profile}")
    samples = int(st.number_input("Design points", min_value=2, max_value=500, value=24, key=f"pl_adv_sweep_n_{profile}"))
    seed = int(st.number_input("Design seed", min_value=0, value=0, key=f"pl_adv_sweep_seed_{profile}"))
    try:
        accepted = adapter_parameter_names(profile, adapter)
        design = design_experiment(factors, method=method, samples=samples, seed=seed)
        rows = design["design"].rename(columns={"design_run": "design_index"}).to_dict("records")
        prepared = prepare_sweep_rows(profile, adapter, rows)
    except Exception as exc:
        st.warning(f"Design is not compatible with the selected adapter: {exc}")
        return
    st.caption(f"Adapter accepts: {', '.join(accepted)}")
    st.dataframe(pd.DataFrame(prepared).head(500), hide_index=True, width="stretch")
    if st.button("Queue DOE as Sweep job", type="primary", key=f"pl_adv_sweep_queue_{profile}"):
        try:
            job = queue_design_as_sweep(profile, adapter, prepared)
            st.session_state[f"pl_adv_queued_job_{profile}"] = job
            st.success(f"Queued {job['id']} · {job['point_count']} points. Execution has NOT started.")
        except Exception as exc:
            st.error(f"Could not queue sweep: {exc}")
    job = st.session_state.get(f"pl_adv_queued_job_{profile}")
    if job:
        st.json({k: job.get(k) for k in ("id", "adapter", "point_count", "status", "execution_started", "boundary")})
        if st.button("Explicitly start queued Sweep", key=f"pl_adv_sweep_start_{profile}"):
            try:
                started = sweeps.start_sweep_job(str(job["id"]))
                st.session_state[f"pl_adv_queued_job_{profile}"] = {**job, **started, "execution_started": True}
                st.success(f"Started {started['id']} · status {started['status']}")
            except Exception as exc:
                st.error(f"Could not start sweep: {exc}")


def render_applied_analysis_advanced(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("#### Advanced Applied Analysis")
    st.caption("Robust fitting, cross-validation, factorial/Morris screening, and a guarded DOE → Sweep bridge.")

    tasks = ["Robust Regression", "Model Selection", "Factorial + Morris", "DOE → Sweep"] if sources else ["DOE → Sweep"]
    task = st.radio(
        "Advanced analysis task",
        tasks,
        horizontal=True,
        key=f"pl_adv_task_{profile}",
    )

    if task == "DOE → Sweep":
        if not sources:
            st.info("No existing data source is available; the guarded DOE → Sweep bridge remains available because it is prospective and source-independent.")
        _doe_sweep_tab(st, profile)
        st.caption(BOUNDARY)
        return

    if not sources:
        st.info("No existing data source is available for this analysis task.")
        st.caption(BOUNDARY)
        return

    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Advanced-analysis source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_adv_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)

    if task == "Robust Regression":
        _robust_tab(st, source, profile)
    elif task == "Model Selection":
        _cv_tab(st, source, profile)
    else:
        _factorial_morris_tab(st, source, profile)
    st.caption(BOUNDARY)
