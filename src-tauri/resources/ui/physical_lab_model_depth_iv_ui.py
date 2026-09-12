"""UI for fourth-wave non-accelerator model-depth studies."""
from __future__ import annotations
from typing import Any

from physical_lab_model_depth_iv import (
    solar_secular_dynamics,
    conditioning_study,
    stiff_ode_comparison,
    long_time_oscillator_integrators,
)


def _go():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _solar(st: Any) -> None:
    st.markdown("### Solar-system · secular dynamics")
    st.caption("Extract slow eccentricity-vector precession and modulation from the existing Sun–Jupiter–Saturn N-body model.")
    c1,c2,c3=st.columns(3)
    years=float(c1.number_input("Duration (years)",40.0,600.0,180.0,20.0,key="pl_depth4_sol_years"))
    samples=int(c2.number_input("Samples",800,12000,3600,400,key="pl_depth4_sol_samples"))
    inc=float(c3.number_input("Jupiter inclination (deg)",0.0,20.0,2.0,0.5,key="pl_depth4_sol_inc"))
    if st.button("Run secular diagnostics",type="primary",key="pl_depth4_sol_run"):
        try:
            with st.spinner("Integrating long-horizon Sun–Jupiter–Saturn dynamics..."):
                st.session_state["pl_depth4_sol"] = solar_secular_dynamics(duration_years=years,samples=samples,inclination_jupiter_deg=inc)
        except Exception as exc: st.error(str(exc))
    r=st.session_state.get("pl_depth4_sol")
    if not r:return
    a,b,c=st.columns(3)
    a.metric("Jupiter projected apsidal rate",f"{r['jupiter_projected_apsidal_rate_deg_per_year']:.4g}°/yr")
    b.metric("Saturn projected apsidal rate",f"{r['saturn_projected_apsidal_rate_deg_per_year']:.4g}°/yr")
    p=(r.get('five_two_deviation_slow_spectrum') or {}).get('dominant_period_years')
    c.metric("5:2-deviation slow period","—" if p is None else f"{p:.3g} yr")
    go=_go(); fig=go.Figure()
    fig.add_scatter(x=r['time_years'],y=r['jupiter_eccentricity'],mode='lines',name='Jupiter e')
    fig.add_scatter(x=r['time_years'],y=r['saturn_eccentricity'],mode='lines',name='Saturn e')
    fig.update_layout(title='Osculating eccentricity modulation',xaxis_title='Years',yaxis_title='e',height=430); st.plotly_chart(fig,width='stretch')
    fig2=go.Figure()
    fig2.add_scatter(x=r['time_years'],y=r['jupiter_projected_varpi_deg'],mode='lines',name='Jupiter ϖ_proj')
    fig2.add_scatter(x=r['time_years'],y=r['saturn_projected_varpi_deg'],mode='lines',name='Saturn ϖ_proj')
    fig2.update_layout(title='Unwrapped projected eccentricity-vector angle',xaxis_title='Years',yaxis_title='Angle (deg)',height=430); st.plotly_chart(fig2,width='stretch')
    fig3=go.Figure(); fig3.add_scatter(x=r['time_years'],y=r['resonance_deviation_5_2'],mode='lines')
    fig3.update_layout(title='Saturn/Jupiter period ratio − 5/2',xaxis_title='Years',yaxis_title='Δ(Ps/Pj)',height=400); st.plotly_chart(fig3,width='stretch')
    st.caption(r['boundary'])


def _numerical(st: Any) -> None:
    st.markdown("### Numerical Structure Lab")
    st.caption("Structural numerical behavior beyond scalar error tables: conditioning, stiffness, and long-time geometric integration.")
    tabs=st.tabs(["Ill-conditioning","Stiff ODE","Long-time integrators"])
    with tabs[0]:
        eps=st.select_slider("RHS perturbation",options=[1e-12,1e-11,1e-10,1e-9,1e-8],value=1e-10,key="pl_depth4_cond_eps")
        if st.button("Run conditioning study",key="pl_depth4_cond_run"):
            st.session_state['pl_depth4_cond']=conditioning_study(perturbation=float(eps))
        r=st.session_state.get('pl_depth4_cond')
        if r:
            import pandas as pd
            st.dataframe(pd.DataFrame(r['rows']),hide_index=True,width='stretch')
            go=_go(); f=go.Figure(); f.add_scatter(x=[x['condition_2'] for x in r['rows']],y=[x['amplification'] for x in r['rows']],mode='lines+markers'); f.update_layout(title='Observed perturbation amplification vs condition number',xaxis_type='log',yaxis_type='log',xaxis_title='κ₂(A)',yaxis_title='Observed amplification',height=430); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])
    with tabs[1]:
        lam=st.select_slider("Stiffness λ",options=[100.0,300.0,1000.0,3000.0,10000.0],value=1000.0,key="pl_depth4_stiff_lam")
        if st.button("Run stiff-solver comparison",key="pl_depth4_stiff_run"):
            st.session_state['pl_depth4_stiff']=stiff_ode_comparison(stiffness=float(lam))
        r=st.session_state.get('pl_depth4_stiff')
        if r:
            import pandas as pd
            st.dataframe(pd.DataFrame(r['rows']),hide_index=True,width='stretch'); st.caption(r['boundary'])
    with tabs[2]:
        c1,c2=st.columns(2)
        periods=int(c1.number_input("Periods",50,3000,600,50,key="pl_depth4_int_periods")); dt=float(c2.number_input("dt",0.005,0.3,0.08,0.005,key="pl_depth4_int_dt"))
        if st.button("Run long-time integrator comparison",key="pl_depth4_int_run"):
            st.session_state['pl_depth4_int']=long_time_oscillator_integrators(periods=periods,dt=dt)
        r=st.session_state.get('pl_depth4_int')
        if r:
            a,b=st.columns(2); a.metric('Verlet max |ΔE/E|',f"{r['verlet_max_abs_relative_energy_error']:.3e}"); b.metric('RK4 final ΔE/E',f"{r['rk4_final_relative_energy_error']:.3e}")
            go=_go(); f=go.Figure(); f.add_scatter(x=r['time'],y=r['verlet_relative_energy_error'],mode='lines',name='Velocity-Verlet'); f.add_scatter(x=r['time'],y=r['rk4_relative_energy_error'],mode='lines',name='RK4'); f.update_layout(title='Long-time harmonic-oscillator energy error',xaxis_title='Time',yaxis_title='Relative energy error',height=450); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])


def render_model_depth_iv_workspace(st: Any, profile: str) -> None:
    if profile not in {'nonlinear-chaos','numerical-methods'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Model Depth IV')
    if profile=='nonlinear-chaos': _solar(st)
    else: _numerical(st)
