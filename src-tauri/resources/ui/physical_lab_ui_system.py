"""Shared visual and information-design system for Physical Lab Streamlit workspaces.

This module is intentionally display-only. It centralizes hierarchy, spacing,
status/boundary callouts and Plotly presentation so scientific modules do not
re-implement their own visual language. Solver inputs, equations, stored
evidence and numerical results are never modified here.
"""
from __future__ import annotations

import html
from typing import Any


PROFILE_LABELS = {
    "numerical-methods": "Numerical Reliability",
    "ising-monte-carlo": "Ising Monte Carlo",
    "random-walk-monte-carlo": "Random Walk & Monte Carlo",
    "nonlinear-chaos": "Nonlinear Dynamics & Chaos",
    "oscillation-integration": "Oscillation & Integration",
    "kerr-geodesics": "Kerr Black Hole Geodesics",
    "solar-system-dynamics": "Sun–Jupiter–Saturn Dynamics",
    "honeycomb-lattice": "Multilayer Honeycomb Lattice",
    "radiation-platform": "Radiation Platform",
    "radia-magnet-studio": "RADIA Magnet Studio",
}


DESIGN_CSS = r"""
<style>
/* Physical Lab visual system v3 */
:root {
  --pl-radius-sm: 9px;
  --pl-radius-md: 13px;
  --pl-radius-lg: 18px;
  --pl-border: rgba(128,128,128,.20);
  --pl-border-strong: rgba(128,128,128,.34);
  --pl-surface: color-mix(in srgb, var(--background-color, white) 97%, #94a3b8 3%);
  --pl-surface-strong: color-mix(in srgb, var(--background-color, white) 93%, #94a3b8 7%);
  --pl-muted: rgba(127,127,127,.82);
  --pl-grid: rgba(128,128,128,.14);
}

.block-container {
  max-width: 1500px !important;
  padding-top: 1.15rem !important;
  padding-left: clamp(1rem, 2.4vw, 2.4rem) !important;
  padding-right: clamp(1rem, 2.4vw, 2.4rem) !important;
  padding-bottom: 4.5rem !important;
}

section[data-testid="stSidebar"] {
  min-width: 318px !important;
  max-width: 360px !important;
  border-right: 1px solid var(--pl-border) !important;
}
section[data-testid="stSidebar"] > div { width:100% !important; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  line-height: 1.45 !important;
}

h1 {
  letter-spacing: -.03em !important;
  line-height: 1.08 !important;
  margin-bottom: .5rem !important;
}
h2 {
  letter-spacing: -.02em !important;
  margin-top: 1.75rem !important;
  margin-bottom: .45rem !important;
}
h3 {
  margin-top: 1.25rem !important;
  margin-bottom: .38rem !important;
}
hr {
  margin: 1.55rem 0 !important;
  border-color: var(--pl-border) !important;
}

div[data-testid="stHorizontalBlock"] {
  flex-wrap: wrap !important;
  gap: .72rem !important;
  align-items: stretch !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
  min-width: min(100%, 210px) !important;
  flex: 1 1 210px !important;
}

div[data-testid="stMetric"] {
  min-height: 104px !important;
  border: 1px solid var(--pl-border) !important;
  border-radius: var(--pl-radius-md) !important;
  padding: .78rem .9rem !important;
  background: var(--pl-surface) !important;
  box-shadow: none !important;
}
div[data-testid="stMetricLabel"] {
  white-space: normal !important;
  line-height: 1.2 !important;
  min-height: 1.8em !important;
  opacity: .78 !important;
}
div[data-testid="stMetricValue"] {
  font-size: clamp(1.16rem, 1.6vw, 1.58rem) !important;
  line-height: 1.18 !important;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  word-break: break-word !important;
}

div[data-testid="stPlotlyChart"],
div[data-testid="stPyplot"],
div[data-testid="stVegaLiteChart"] {
  margin-top: .5rem !important;
  margin-bottom: 1.35rem !important;
  border: 1px solid var(--pl-border) !important;
  border-radius: var(--pl-radius-md) !important;
  overflow: hidden !important;
  background: var(--pl-surface) !important;
}
div[data-testid="stDataFrame"] {
  margin-top: .45rem !important;
  margin-bottom: 1.25rem !important;
  border: 1px solid var(--pl-border) !important;
  border-radius: var(--pl-radius-md) !important;
  overflow: hidden !important;
}

div[data-baseweb="tab-list"] {
  gap: .22rem !important;
  flex-wrap: wrap !important;
  border-bottom: 1px solid var(--pl-border) !important;
}
button[data-baseweb="tab"] {
  min-height: 40px !important;
  padding: 0 .82rem !important;
  border-radius: 8px 8px 0 0 !important;
  font-weight: 600 !important;
}

div[role="radiogroup"] {
  gap: .28rem !important;
  flex-wrap: wrap !important;
}
div[role="radiogroup"] label {
  border-radius: 999px !important;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--pl-border) !important;
  border-radius: var(--pl-radius-md) !important;
  margin-bottom: .7rem !important;
  background: var(--pl-surface) !important;
}

.stButton > button,
.stDownloadButton > button {
  min-height: 40px !important;
  border-radius: 9px !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}
.stButton > button[kind="primary"] {
  font-weight: 700 !important;
}
[data-testid="stNumberInput"],
[data-testid="stSelectbox"],
[data-testid="stSlider"],
[data-testid="stTextInput"],
[data-testid="stTextArea"],
[data-testid="stMultiSelect"] {
  margin-bottom: .32rem !important;
}

div[data-testid="stAlert"] {
  border-radius: var(--pl-radius-md) !important;
  box-shadow: none !important;
}

.pl-lab-identity {
  border-bottom: 1px solid var(--pl-border);
  padding: .1rem 0 .78rem 0;
  margin: 0 0 .9rem 0;
}
.pl-lab-eyebrow {
  font-size: .73rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  opacity: .62;
  font-weight: 700;
}
.pl-lab-name {
  font-size: 1.05rem;
  font-weight: 730;
  margin-top: .18rem;
}
.pl-lab-subtitle {
  font-size: .84rem;
  line-height: 1.45;
  opacity: .68;
  margin-top: .24rem;
}

.pl-workbench-header {
  border: 1px solid var(--pl-border);
  border-radius: var(--pl-radius-lg);
  padding: 1rem 1.05rem;
  background: var(--pl-surface);
  margin: .65rem 0 1rem 0;
}
.pl-workbench-kicker {
  font-size: .72rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  opacity: .62;
  font-weight: 700;
}
.pl-workbench-title {
  font-size: 1.3rem;
  line-height: 1.2;
  font-weight: 760;
  margin-top: .26rem;
}
.pl-workbench-caption {
  font-size: .88rem;
  line-height: 1.5;
  opacity: .74;
  margin-top: .35rem;
  max-width: 1000px;
}

.pl-section-label {
  margin: 1.15rem 0 .5rem 0;
}
.pl-section-label b {
  font-size: .98rem;
}
.pl-section-label span {
  display:block;
  font-size:.82rem;
  opacity:.68;
  line-height:1.45;
  margin-top:.16rem;
}

.pl-result-grid {
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:.65rem;
  margin:.48rem 0 1.2rem 0;
}
.pl-result-card {
  border:1px solid var(--pl-border);
  border-radius:var(--pl-radius-md);
  padding:.75rem .82rem;
  min-width:0;
  background:var(--pl-surface);
}
.pl-result-label {
  font-size:.78rem;
  opacity:.7;
  line-height:1.2;
  margin-bottom:.28rem;
}
.pl-result-value {
  font-size:1.12rem;
  font-weight:700;
  line-height:1.22;
  overflow-wrap:anywhere;
}
.pl-result-unit {
  font-size:.76rem;
  opacity:.62;
  margin-top:.28rem;
  line-height:1.25;
}

.pl-boundary,
.pl-note,
.pl-provenance {
  border-radius: var(--pl-radius-sm);
  padding: .65rem .76rem;
  margin: .5rem 0 .82rem 0;
  font-size: .84rem;
  line-height: 1.48;
}
.pl-boundary {
  border-left: 4px solid rgba(124,58,237,.7);
  background: rgba(124,58,237,.07);
}
.pl-note {
  border-left: 4px solid rgba(59,130,246,.62);
  background: rgba(59,130,246,.06);
}
.pl-provenance {
  border-left: 4px solid rgba(34,197,94,.58);
  background: rgba(34,197,94,.055);
}

.pl-stage-rail {
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
  gap:.45rem;
  margin:.5rem 0 .95rem 0;
}
.pl-stage {
  border:1px solid var(--pl-border);
  border-radius:10px;
  padding:.55rem .62rem;
  background:var(--pl-surface);
}
.pl-stage-index {
  font-size:.68rem;
  letter-spacing:.09em;
  opacity:.58;
  text-transform:uppercase;
}
.pl-stage-name {
  font-size:.83rem;
  font-weight:650;
  margin-top:.12rem;
}

@media (max-width: 850px) {
  section[data-testid="stSidebar"] {
    min-width: 285px !important;
    max-width: 330px !important;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    min-width: min(100%, 180px) !important;
    flex-basis: 180px !important;
  }
  .block-container {
    padding-left: .9rem !important;
    padding-right: .9rem !important;
  }
}

/* Workshop information architecture v4 */
.pl-workshop-guidance{
  display:grid;
  grid-template-columns:minmax(130px,.35fr) minmax(260px,1.65fr);
  gap:.8rem 1.2rem;
  align-items:start;
  margin:.65rem 0 1.35rem;
  padding:.82rem 1rem;
  border:1px solid var(--pl-border);
  border-radius:var(--pl-radius-md);
  background:var(--pl-surface);
}
.pl-workshop-guidance b{font-size:.78rem;letter-spacing:.02em}
.pl-workshop-guidance span{font-size:.76rem;line-height:1.55;color:var(--pl-muted)}
div[data-testid="stTabs"]{margin-top:.65rem;margin-bottom:1.1rem}
div[data-testid="stTabs"] [data-baseweb="tab-list"]{
  gap:.35rem;
  padding:.32rem;
  border:1px solid var(--pl-border);
  border-radius:12px;
  background:var(--pl-surface);
}
div[data-testid="stTabs"] button[role="tab"]{
  border-radius:9px;
  padding:.52rem .78rem;
  font-size:.78rem;
}
div[data-testid="stExpander"]{
  border:1px solid var(--pl-border) !important;
  border-radius:12px !important;
  background:var(--pl-surface) !important;
  margin:.55rem 0 !important;
}
div[data-testid="stExpander"] summary{
  font-weight:650;
  letter-spacing:.01em;
}
div[data-testid="stForm"]{
  border:1px solid var(--pl-border) !important;
  border-radius:14px !important;
  padding:1rem !important;
  background:var(--pl-surface) !important;
}
[data-testid="stSidebar"] .pl-sidebar-section{
  margin:.8rem 0 .45rem;
  padding-top:.72rem;
  border-top:1px solid var(--pl-border);
}
[data-testid="stSidebar"] .pl-sidebar-section b{
  display:block;
  font-size:.72rem;
  letter-spacing:.06em;
  text-transform:uppercase;
  margin-bottom:.2rem;
}
[data-testid="stSidebar"] .pl-sidebar-section span{
  display:block;
  color:var(--pl-muted);
  font-size:.69rem;
  line-height:1.45;
}
@media(max-width:760px){
  .pl-workshop-guidance{grid-template-columns:1fr}
}
</style>
"""


PLOTLY_COLORWAY = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756",
    "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D",
]


def profile_label(profile: str) -> str:
    return PROFILE_LABELS.get(profile, profile.replace("-", " ").title())


WORKSHOP_PURPOSE = {
    "numerical-methods": "Study numerical accuracy, floating-point failure, convergence, and reference agreement.",
    "ising-monte-carlo": "Configure a statistical-physics model, run finite-sample experiments, and inspect criticality and sampling quality.",
    "random-walk-monte-carlo": "Run stochastic transport and estimator experiments, then compare scaling, uncertainty, and computational efficiency.",
    "nonlinear-chaos": "Explore nonlinear dynamics through trajectories, sensitivity, Lyapunov behavior, and finite-window diagnostics.",
    "oscillation-integration": "Compare dynamical response and numerical integrators while checking convergence and energy/work consistency.",
    "kerr-geodesics": "Explore relativistic trajectories and derived orbital structure with explicit numerical checks.",
    "solar-system-dynamics": "Run controlled orbital-dynamics experiments and inspect long-horizon numerical and physical diagnostics.",
    "honeycomb-lattice": "Explore lattice dynamics, modes, defects, and transport-oriented quantities in a structured computational workflow.",
    "radiation-platform": "Connect trajectory and field inputs to radiation analysis, scans, references, and engineering interpretation.",
    "radia-magnet-studio": "Configure a magnet model, solve the field, inspect trajectory/field metrics, and study manufacturing sensitivity.",
}


def render_workshop_overview(st: Any, profile: str) -> None:
    """Render a compact, display-only workflow scaffold above the upstream Lab UI."""
    render_workbench_header(
        st,
        profile_label(profile),
        WORKSHOP_PURPOSE.get(profile, "Computational physics and engineering workshop."),
        kicker="Engineering Lab workshop",
    )
    render_stage_rail(st, [
        ("Overview", "question & model"),
        ("Setup", "physical parameters"),
        ("Run", "numerical experiment"),
        ("Results", "primary outputs"),
        ("Analysis", "sensitivity & interpretation"),
        ("Verification", "checks & provenance"),
    ])
    st.markdown(
        '<div class="pl-workshop-guidance">'
        '<b>Recommended flow</b>'
        '<span>Set the physical model first, choose numerical quality second, run the core experiment, '
        'then use the post-run Research Workbench for deeper analysis and verification.</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_lab_identity(st: Any, profile: str, subtitle: str = "Computational physics & engineering workbench") -> None:
    label = html.escape(profile_label(profile))
    subtitle_html = html.escape(subtitle)
    st.markdown(
        f'<div class="pl-lab-identity">'
        f'<div class="pl-lab-eyebrow">Physical Lab</div>'
        f'<div class="pl-lab-name">{label}</div>'
        f'<div class="pl-lab-subtitle">{subtitle_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_workbench_header(st: Any, title: str, caption: str, *, kicker: str = "Research workspace") -> None:
    st.markdown(
        f'<div class="pl-workbench-header">'
        f'<div class="pl-workbench-kicker">{html.escape(kicker)}</div>'
        f'<div class="pl-workbench-title">{html.escape(title)}</div>'
        f'<div class="pl-workbench-caption">{html.escape(caption)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_section_label(st: Any, title: str, caption: str = "") -> None:
    st.markdown(
        f'<div class="pl-section-label"><b>{html.escape(title)}</b>'
        f'<span>{html.escape(caption)}</span></div>',
        unsafe_allow_html=True,
    )


def render_boundary(st: Any, text: str, *, kind: str = "boundary") -> None:
    css_class = {
        "boundary": "pl-boundary",
        "note": "pl-note",
        "provenance": "pl-provenance",
    }.get(kind, "pl-boundary")
    st.markdown(f'<div class="{css_class}">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_stage_rail(st: Any, stages: list[tuple[str, str]]) -> None:
    items = []
    for index, (name, detail) in enumerate(stages, 1):
        items.append(
            f'<div class="pl-stage"><div class="pl-stage-index">{index:02d}</div>'
            f'<div class="pl-stage-name">{html.escape(name)}</div>'
            f'<div class="pl-lab-subtitle">{html.escape(detail)}</div></div>'
        )
    st.markdown('<div class="pl-stage-rail">' + ''.join(items) + '</div>', unsafe_allow_html=True)


def apply_plotly_design(fig: Any) -> Any:
    """Apply the shared Physical Lab chart language without changing data."""
    try:
        layout = getattr(fig, "layout", None)
        current_height = getattr(layout, "height", None)
        update = {
            "autosize": True,
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "margin": {"l": 62, "r": 26, "t": 72, "b": 58},
            "font": {
                "family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
                "size": 13,
            },
            "title": {
                "x": 0.01,
                "xanchor": "left",
                "font": {"size": 18},
            },
            "hoverlabel": {"font": {"size": 13}, "namelength": -1},
            "colorway": PLOTLY_COLORWAY,
        }
        if not current_height or current_height < 430:
            update["height"] = 500
        fig.update_layout(**update)

        fig.update_xaxes(
            showgrid=True,
            gridcolor="rgba(128,128,128,.14)",
            zerolinecolor="rgba(128,128,128,.24)",
            linecolor="rgba(128,128,128,.28)",
            automargin=True,
            title_standoff=10,
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor="rgba(128,128,128,.14)",
            zerolinecolor="rgba(128,128,128,.24)",
            linecolor="rgba(128,128,128,.28)",
            automargin=True,
            title_standoff=10,
        )

        data = list(getattr(fig, "data", ()) or ())
        if len(data) > 1:
            legend = getattr(fig.layout, "legend", None)
            orientation = getattr(legend, "orientation", None) if legend is not None else None
            if not orientation:
                fig.update_layout(
                    legend={
                        "orientation": "h",
                        "y": 1.08,
                        "yanchor": "bottom",
                        "x": 0,
                        "xanchor": "left",
                        "title": {"text": ""},
                    }
                )

        # Keep 3D plots visually consistent without changing camera or geometry.
        try:
            scene = getattr(fig.layout, "scene", None)
            if scene is not None:
                fig.update_layout(scene={
                    "xaxis": {"backgroundcolor": "rgba(0,0,0,0)", "gridcolor": "rgba(128,128,128,.14)"},
                    "yaxis": {"backgroundcolor": "rgba(0,0,0,0)", "gridcolor": "rgba(128,128,128,.14)"},
                    "zaxis": {"backgroundcolor": "rgba(0,0,0,0)", "gridcolor": "rgba(128,128,128,.14)"},
                })
        except Exception:
            pass
    except Exception:
        pass
    return fig
