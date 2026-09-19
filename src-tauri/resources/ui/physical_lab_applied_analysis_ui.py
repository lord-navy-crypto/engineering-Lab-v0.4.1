"""Applied Mathematics & Statistics workbench for Engineering Lab."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import physical_lab_project_kernel as projects
from physical_lab_visual_analytics_ui import _sources
from physical_lab_visualization_studio import numeric_columns
from physical_lab_applied_analysis import (
    BOUNDARY,
    bootstrap_statistic,
    design_experiment,
    estimate_parameters,
    monte_carlo_propagation,
    polynomial_regression,
    regression_diagnostics,
    save_analysis_artifact,
)


def _source_identity(source: dict[str, Any]) -> dict[str, Any]:
    identity = dict(source.get("identity") or {})
    identity.setdefault("source_id", source.get("id"))
    identity.setdefault("source_kind", source.get("kind"))
    return identity


def _save(st: Any, project_path: Path, source: dict[str, Any], *, kind: str, configuration: dict[str, Any], summary: dict[str, Any], key: str) -> None:
    if st.button("Save Applied Analysis Artifact", key=key):
        try:
            saved = save_analysis_artifact(project_path, kind=kind, source_identity=_source_identity(source), configuration=configuration, summary=summary)
            st.success(f"Saved {saved['artifact_id']} · sha256 {saved['sha256'][:16]}…")
        except Exception as exc:
            st.error(f"Could not save analysis artifact: {exc}")


def _regression_tab(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Regression requires at least two numeric fields.")
        return
    mode = st.radio("Regression family", ["Multiple linear", "Single-variable polynomial"], horizontal=True, key=f"pl_applied_reg_mode_{profile}")
    if mode == "Multiple linear":
        response = st.selectbox("Response Y", numeric, index=len(numeric)-1, key=f"pl_applied_reg_y_{profile}")
        candidates = [c for c in numeric if c != response]
        predictors = st.multiselect("Predictors X", candidates, default=candidates[:min(3, len(candidates))], key=f"pl_applied_reg_x_{profile}")
        include_intercept = st.checkbox("Include intercept", value=True, key=f"pl_applied_reg_intercept_{profile}")
        if not predictors:
            st.info("Select at least one predictor.")
            return
        try:
            result = regression_diagnostics(frame, predictors, response, include_intercept=include_intercept)
        except Exception as exc:
            st.warning(f"Regression unavailable: {exc}")
            return
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("n", result["n"]); m2.metric("R²", f"{result['r2']:.4g}"); m3.metric("RMSE", f"{result['rmse']:.4g}"); m4.metric("Condition #", f"{result['condition_number']:.4g}")
        st.dataframe(result["coefficients"], hide_index=True, width="stretch")
        diag = result["diagnostics"]
        c1, c2 = st.columns(2)
        with c1:
            fig = px.scatter(diag, x="predicted", y="residual", title="Residual vs fitted")
            fig.add_hline(y=0)
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        with c2:
            fig = px.scatter(diag, x="leverage", y="cooks_distance", title="Influence diagnostics")
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.dataframe(diag.sort_values("cooks_distance", ascending=False).head(25), hide_index=True, width="stretch")
        st.caption("R², residuals and influence diagnostics describe this fitted model; they do not establish causality or physical correctness.")
        _save(st, project_path, source, kind="linear-regression", configuration={"response": response, "predictors": predictors, "include_intercept": include_intercept}, summary={k: result[k] for k in ("n", "r2", "adjusted_r2", "rmse", "mae", "condition_number", "coefficients")}, key=f"pl_applied_save_reg_{profile}")
    else:
        a, b, c = st.columns([1, 1, 0.7])
        x = a.selectbox("Predictor X", numeric, key=f"pl_applied_poly_x_{profile}")
        y = b.selectbox("Response Y", [v for v in numeric if v != x], key=f"pl_applied_poly_y_{profile}")
        degree = int(c.number_input("Degree", min_value=1, max_value=6, value=2, step=1, key=f"pl_applied_poly_degree_{profile}"))
        try:
            result = polynomial_regression(frame, x, y, degree=degree)
        except Exception as exc:
            st.warning(f"Polynomial regression unavailable: {exc}")
            return
        diag = result["diagnostics"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=diag[x], y=diag["observed"], mode="markers", name="Observed"))
        fig.add_trace(go.Scatter(x=diag[x], y=diag["predicted"], mode="lines", name="Fitted"))
        fig.update_layout(title=f"Degree-{degree} polynomial fit", xaxis_title=x, yaxis_title=y, height=560)
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.dataframe(result["coefficients"], hide_index=True, width="stretch")
        st.caption(f"R²={result['r2']:.5g} · RMSE={result['rmse']:.5g}. Higher degree is not automatically a better physical model.")
        _save(st, project_path, source, kind="polynomial-regression", configuration={"x": x, "y": y, "degree": degree}, summary={"r2": result["r2"], "rmse": result["rmse"], "coefficients": result["coefficients"]}, key=f"pl_applied_save_poly_{profile}")


def _bootstrap_tab(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if not numeric:
        st.info("Bootstrap requires a numeric field.")
        return
    method = st.radio(
        "Uncertainty method",
        ["Bootstrap", "Monte Carlo propagation"],
        horizontal=True,
        key=f"pl_applied_uncertainty_method_{profile}",
    )
    if method == "Bootstrap":
        c1, c2, c3 = st.columns(3)
        field = c1.selectbox("Field", numeric, key=f"pl_applied_boot_field_{profile}")
        statistic = c2.selectbox("Statistic", ["mean", "median", "std"], key=f"pl_applied_boot_stat_{profile}")
        resamples = int(c3.number_input("Resamples", min_value=100, max_value=20000, value=2000, step=100, key=f"pl_applied_boot_n_{profile}"))
        c4, c5 = st.columns(2)
        confidence = float(c4.slider("Confidence", min_value=0.80, max_value=0.99, value=0.95, step=0.01, key=f"pl_applied_boot_conf_{profile}"))
        seed = int(c5.number_input("Seed", min_value=0, value=0, step=1, key=f"pl_applied_boot_seed_{profile}"))
        try:
            result = bootstrap_statistic(frame[field].tolist(), statistic=statistic, resamples=resamples, confidence=confidence, seed=seed)
        except Exception as exc:
            st.warning(f"Bootstrap unavailable: {exc}")
            return
        m1, m2, m3 = st.columns(3)
        m1.metric("Estimate", f"{result['estimate']:.6g}"); m2.metric("Bootstrap SE", f"{result['bootstrap_standard_error']:.6g}"); m3.metric("Interval", f"[{result['interval'][0]:.6g}, {result['interval'][1]:.6g}]")
        fig = px.histogram(x=result["distribution"], nbins=50, title=f"Bootstrap distribution · {statistic}({field})")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.caption("This is a percentile bootstrap interval under resampling of the observed rows; dependence, bias and sampling design remain separate assumptions.")
        _save(st, project_path, source, kind="bootstrap", configuration={"field": field, "statistic": statistic, "resamples": resamples, "confidence": confidence, "seed": seed}, summary={k: result[k] for k in ("n", "estimate", "bootstrap_standard_error", "interval")}, key=f"pl_applied_save_boot_{profile}")
        return

    selected = st.multiselect("Input fields", numeric, default=numeric[:min(3, len(numeric))], key=f"pl_applied_mc_fields_{profile}")
    if not selected:
        st.info("Select at least one input field.")
        return
    st.caption("For this first version, each selected field uses its observed sample mean and sample standard deviation as an explicit Normal input assumption. Coefficients define a linear output y = Σ cᵢxᵢ.")
    coeff_text = st.text_input("Coefficients (comma-separated)", value=",".join(["1"] * len(selected)), key=f"pl_applied_mc_coeff_{profile}")
    try:
        coefficients = [float(x.strip()) for x in coeff_text.split(",") if x.strip()]
    except ValueError:
        coefficients = []
    if len(coefficients) != len(selected):
        st.warning("Provide exactly one coefficient per selected field.")
        return
    work = frame[selected].apply(pd.to_numeric, errors="coerce")
    means = [float(work[c].mean()) for c in selected]
    stds = [float(work[c].std(ddof=1)) for c in selected]
    samples = int(st.number_input("Monte Carlo samples", min_value=100, max_value=20000, value=5000, step=100, key=f"pl_applied_mc_n_{profile}"))
    seed = int(st.number_input("Monte Carlo seed", min_value=0, value=0, step=1, key=f"pl_applied_mc_seed_{profile}"))
    try:
        result = monte_carlo_propagation(means=means, standard_uncertainties=stds, coefficients=coefficients, samples=samples, seed=seed)
    except Exception as exc:
        st.warning(f"Monte Carlo propagation unavailable: {exc}")
        return
    st.dataframe([{"field": f, "assumed_mean": m, "assumed_std": s, "coefficient": c} for f, m, s, c in zip(selected, means, stds, coefficients)], hide_index=True, width="stretch")
    fig = px.histogram(x=result["distribution"], nbins=60, title="Propagated output distribution")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption(f"Mean={result['mean']:.6g} · SD={result['standard_deviation']:.6g} · 95% percentile interval={result['percentile_95']}. Normality and independence are explicit assumptions here, not inferred truths.")
    _save(st, project_path, source, kind="monte-carlo-propagation", configuration={"fields": selected, "coefficients": coefficients, "samples": samples, "seed": seed, "assumption": "independent-normal-inputs-using-observed-sample-mean-sd"}, summary={k: result[k] for k in ("mean", "standard_deviation", "percentile_95", "median")}, key=f"pl_applied_save_mc_{profile}")


def _doe_tab(st: Any, project_path: Path, profile: str) -> None:
    st.markdown("#### Prospective Design of Experiments")
    st.caption("Enter one factor per line as `name, low, high`. Designs are proposals only; they do not run a simulation or instrument.")
    factor_text = st.text_area("Factors", value="factor_a,0,1\nfactor_b,0,1", height=130, key=f"pl_applied_doe_factors_{profile}")
    factors = []
    try:
        for line in factor_text.splitlines():
            if not line.strip(): continue
            name, low, high = [x.strip() for x in line.split(",", 2)]
            factors.append({"name": name, "low": float(low), "high": float(high)})
    except Exception:
        st.warning("Factor syntax must be `name, low, high`, one factor per line.")
        return
    c1, c2, c3 = st.columns(3)
    method = c1.selectbox("Design", ["latin-hypercube", "full-factorial", "central-composite", "random"], key=f"pl_applied_doe_method_{profile}")
    samples = int(c2.number_input("Samples (where applicable)", min_value=2, max_value=5000, value=32, step=1, key=f"pl_applied_doe_samples_{profile}"))
    seed = int(c3.number_input("Seed", min_value=0, value=0, step=1, key=f"pl_applied_doe_seed_{profile}"))
    try:
        result = design_experiment(factors, method=method, samples=samples, seed=seed)
    except Exception as exc:
        st.warning(f"DOE design unavailable: {exc}")
        return
    design = result["design"]
    st.metric("Proposed runs", result["row_count"])
    st.dataframe(design.head(500), hide_index=True, width="stretch")
    st.download_button("Download DOE CSV", data=design.to_csv(index=False).encode("utf-8"), file_name=f"doe-{method}.csv", mime="text/csv", key=f"pl_applied_doe_download_{profile}")
    if st.button("Save DOE proposal", key=f"pl_applied_doe_save_{profile}"):
        source = {"source_id": "prospective-doe", "source_kind": "design"}
        config = {"method": method, "seed": seed, "samples": samples, "factors": factors}
        summary = {"schema": result["schema"], "row_count": result["row_count"], "preview": design.head(50).to_dict("records")}
        try:
            saved = save_analysis_artifact(project_path, kind="doe-proposal", source_identity=source, configuration=config, summary=summary)
            st.success(f"Saved {saved['artifact_id']} · proposal only; no execution occurred.")
        except Exception as exc:
            st.error(f"Could not save DOE proposal: {exc}")


def _parameter_tab(st: Any, project_path: Path, source: dict[str, Any], profile: str) -> None:
    frame: pd.DataFrame = source["frame"]
    numeric = numeric_columns(frame)
    if len(numeric) < 2:
        st.info("Parameter estimation requires at least two numeric fields.")
        return
    c1, c2, c3 = st.columns(3)
    x = c1.selectbox("Independent variable X", numeric, key=f"pl_applied_fit_x_{profile}")
    y = c2.selectbox("Observed response Y", [c for c in numeric if c != x], key=f"pl_applied_fit_y_{profile}")
    model = c3.selectbox("Allow-listed model", ["linear", "quadratic", "exponential"], key=f"pl_applied_fit_model_{profile}")
    try:
        result = estimate_parameters(frame, x, y, model=model)
    except Exception as exc:
        st.warning(f"Parameter estimation unavailable: {exc}")
        return
    st.dataframe(result["parameters"], hide_index=True, width="stretch")
    diag = result["diagnostics"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=diag[x], y=diag["observed"], mode="markers", name="Observed"))
    fig.add_trace(go.Scatter(x=diag[x], y=diag["predicted"], mode="lines", name="Fitted model"))
    fig.update_layout(title=f"Parameter estimation · {model}", xaxis_title=x, yaxis_title=y, height=560)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption(f"RMSE={result['rmse']:.6g} · MAE={result['mae']:.6g}. Standard errors come from the local covariance approximation; model-form adequacy must be checked separately.")
    _save(st, project_path, source, kind="parameter-estimation", configuration={"x": x, "y": y, "model": model}, summary={"parameters": result["parameters"], "rmse": result["rmse"], "mae": result["mae"], "n": result["n"]}, key=f"pl_applied_save_fit_{profile}")


def render_applied_analysis(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        st.info("Open an Engineering Lab project to use Applied Analysis.")
        return
    project_path = Path(active)
    sources = _sources(project_path)
    st.markdown("### Applied Mathematics & Statistics")
    st.caption("Regression diagnostics, resampling, uncertainty propagation, experiment design and safe parameter estimation over existing Engineering Lab data.")
    if not sources:
        st.info("No project result, completed sweep or canonical dataset is available yet. DOE can still be designed prospectively below.")
        _doe_tab(st, project_path, profile)
        st.caption(BOUNDARY)
        return

    task = st.radio(
        "Analysis task",
        ["Regression + Diagnostics", "Bootstrap + Monte Carlo", "Design of Experiments", "Parameter Estimation"],
        horizontal=True,
        key=f"pl_applied_task_{profile}",
    )
    if task == "Design of Experiments":
        _doe_tab(st, project_path, profile)
        st.caption(BOUNDARY)
        return

    labels = {s["id"]: s["label"] for s in sources}
    selected_id = st.selectbox("Analysis source", [s["id"] for s in sources], format_func=lambda x: labels.get(x, x), key=f"pl_applied_source_{profile}")
    source = next(s for s in sources if s["id"] == selected_id)
    if task == "Regression + Diagnostics":
        _regression_tab(st, project_path, source, profile)
    elif task == "Bootstrap + Monte Carlo":
        _bootstrap_tab(st, project_path, source, profile)
    else:
        _parameter_tab(st, project_path, source, profile)
    st.caption(BOUNDARY)