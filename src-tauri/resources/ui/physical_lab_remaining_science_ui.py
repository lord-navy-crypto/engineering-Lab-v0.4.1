"""Streamlit UI for advanced remaining Physical Lab science studies."""
from __future__ import annotations
from typing import Any

from physical_lab_remaining_science import (
    ising_finite_size_scan,
    random_walk_first_passage,
    qmc_convergence_study,
    duffing_bifurcation_sweep,
    coupled_mode_study,
)


def _plotly():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_ising(st: Any) -> None:
    st.markdown("### Ising · finite-size thermodynamics")
    st.caption("Temperature sweeps resolve energy, |M|, heat capacity, susceptibility and Binder cumulant across several finite periodic lattices.")
    c1,c2,c3 = st.columns(3)
    sizes_text = c1.text_input("L values", "8,12,16", key="pl_rem_ising_sizes")
    burn = c2.select_slider("Burn sweeps", options=[100,150,250,400,600], value=250, key="pl_rem_ising_burn")
    samples = c3.select_slider("Sample sweeps", options=[300,500,700,1000,1500], value=700, key="pl_rem_ising_samples")
    temps_text = st.text_input("Temperatures", "1.8,2.0,2.15,2.25,2.269,2.35,2.5,2.8", key="pl_rem_ising_temps")
    if st.button("Run finite-size Ising scan", type="primary", key="pl_rem_ising_run"):
        try:
            sizes=[int(x.strip()) for x in sizes_text.split(',') if x.strip()]; temps=[float(x.strip()) for x in temps_text.split(',') if x.strip()]
            with st.spinner("Running finite-size Metropolis sweeps..."):
                st.session_state["pl_rem_ising"] = ising_finite_size_scan(sizes=sizes,temperatures=temps,burn_sweeps=int(burn),sample_sweeps=int(samples))
        except Exception as exc: st.error(str(exc))
    result=st.session_state.get("pl_rem_ising")
    if not result: return
    st.metric("Exact 2-D Ising T_c", f"{result['onsager_critical_temperature_reduced']:.6f}")
    go=_plotly(); rows=result['rows']
    f=go.Figure()
    for L in sorted({r['L'] for r in rows}):
        rr=[r for r in rows if r['L']==L]; f.add_scatter(x=[r['temperature'] for r in rr],y=[r['binder_cumulant'] for r in rr],mode='lines+markers',name=f'L={L}')
    f.update_layout(title='Binder cumulant finite-size comparison',xaxis_title='Temperature',yaxis_title='U4',height=430); st.plotly_chart(f,width='stretch')
    c=go.Figure()
    for L in sorted({r['L'] for r in rows}):
        rr=[r for r in rows if r['L']==L]; c.add_scatter(x=[r['temperature'] for r in rr],y=[r['heat_capacity_per_spin'] for r in rr],mode='lines+markers',name=f'C, L={L}')
    c.update_layout(title='Heat-capacity response',xaxis_title='Temperature',yaxis_title='C/N',height=430); st.plotly_chart(c,width='stretch')
    st.dataframe(result['peaks'],hide_index=True,width='stretch'); st.caption(result['boundary'])


def _render_random(st: Any) -> None:
    tabs=st.tabs(["First passage","MC ↔ Sobol QMC"])
    with tabs[0]:
        c1,c2,c3=st.columns(3)
        walkers=c1.number_input("Walkers",500,50000,8000,500,key="pl_rem_rw_walkers")
        radius=c2.number_input("Absorbing radius",2.0,40.0,12.0,1.0,key="pl_rem_rw_radius")
        steps=c3.number_input("Max steps",50,10000,1500,50,key="pl_rem_rw_steps")
        if st.button("Run first-passage study",type="primary",key="pl_rem_rw_run"):
            with st.spinner("Simulating first-passage ensemble..."):
                st.session_state['pl_rem_rw']=random_walk_first_passage(walkers=int(walkers),boundary_radius=float(radius),max_steps=int(steps))
        r=st.session_state.get('pl_rem_rw')
        if r:
            a,b,c=st.columns(3); a.metric('Hit fraction',f"{100*r['hit_fraction']:.2f}%"); b.metric('Median hit step','—' if r['median_first_passage_step'] is None else f"{r['median_first_passage_step']:.1f}"); c.metric('Conditional mean','—' if r['mean_first_passage_step_conditional'] is None else f"{r['mean_first_passage_step_conditional']:.1f}")
            go=_plotly(); fig=go.Figure(); fig.add_scatter(x=[x['step'] for x in r['survival_curve']],y=[x['survival_fraction'] for x in r['survival_curve']],mode='lines+markers'); fig.update_layout(title='Survival probability',xaxis_title='Step',yaxis_title='Survival fraction',height=420); st.plotly_chart(fig,width='stretch'); st.caption(r['boundary'])
    with tabs[1]:
        if st.button("Run MC / scrambled-Sobol convergence",key="pl_rem_qmc_run"):
            with st.spinner("Comparing ordinary MC and scrambled Sobol..."):
                st.session_state['pl_rem_qmc']=qmc_convergence_study()
        q=st.session_state.get('pl_rem_qmc')
        if q:
            a,b=st.columns(2); a.metric('MC log-log slope',f"{q['mc_loglog_error_slope']:.3f}"); b.metric('Sobol log-log slope',f"{q['qmc_loglog_error_slope']:.3f}")
            go=_plotly(); fig=go.Figure(); fig.add_scatter(x=[r['samples'] for r in q['rows']],y=[r['mc_median_abs_error'] for r in q['rows']],mode='lines+markers',name='MC'); fig.add_scatter(x=[r['samples'] for r in q['rows']],y=[r['qmc_median_abs_error'] for r in q['rows']],mode='lines+markers',name='Scrambled Sobol'); fig.update_layout(title='Estimator convergence',xaxis_type='log',yaxis_type='log',xaxis_title='Samples',yaxis_title='Median absolute error',height=440); st.plotly_chart(fig,width='stretch'); st.caption(q['boundary'])


def _render_duffing(st: Any) -> None:
    st.markdown("### Duffing · stroboscopic bifurcation sweep")
    c1,c2,c3=st.columns(3)
    start=c1.number_input('Drive amplitude start',0.0,1.0,0.18,0.02,key='pl_rem_duf_start'); stop=c2.number_input('Drive amplitude stop',0.05,1.5,0.52,0.02,key='pl_rem_duf_stop'); points=c3.select_slider('Amplitude points',options=[10,14,18,24,30],value=18,key='pl_rem_duf_points')
    if st.button('Run stroboscopic sweep',type='primary',key='pl_rem_duf_run'):
        import numpy as np
        if float(stop)<=float(start): st.error('Stop must exceed start.')
        else:
            with st.spinner('Resolving stroboscopic branches...'):
                st.session_state['pl_rem_duf']=duffing_bifurcation_sweep(amplitudes=np.linspace(float(start),float(stop),int(points)))
    r=st.session_state.get('pl_rem_duf')
    if not r: return
    a,b=st.columns(2); a.metric('Max resolved branches',str(r['max_resolved_branch_count'])); b.metric('Max nearby-state gain',f"{r['max_nearby_state_separation_gain']:.3g}×")
    go=_plotly(); fig=go.Figure()
    for row in r['rows']:
        fig.add_scatter(x=[row['drive_amplitude']]*len(row['stroboscopic_x']),y=row['stroboscopic_x'],mode='markers',marker={'size':3},showlegend=False)
    fig.update_layout(title='Duffing stroboscopic response cloud',xaxis_title='Drive amplitude',yaxis_title='x sampled once per drive period',height=500); st.plotly_chart(fig,width='stretch'); st.caption(r['boundary'])


def _render_modes(st: Any) -> None:
    st.markdown('### Coupled oscillators · normal modes and beating')
    c1,c2,c3=st.columns(3)
    kc=c1.number_input('Coupling stiffness',0.0,2.0,0.12,0.02,key='pl_rem_modes_kc'); duration=c2.number_input('Duration',20.0,500.0,180.0,10.0,key='pl_rem_modes_duration'); dt=c3.number_input('dt',0.002,0.1,0.02,0.002,key='pl_rem_modes_dt')
    if st.button('Run coupled-mode study',type='primary',key='pl_rem_modes_run'):
        st.session_state['pl_rem_modes']=coupled_mode_study(coupling_k=float(kc),duration=float(duration),dt=float(dt))
    r=st.session_state.get('pl_rem_modes')
    if not r:return
    a,b,c=st.columns(3); a.metric('ω₁',f"{r['normal_mode_omega_rad_s'][0]:.5g} rad/s"); b.metric('ω₂',f"{r['normal_mode_omega_rad_s'][1]:.5g} rad/s"); c.metric('Energy drift',f"{r['relative_energy_drift_max']:.2e}")
    if r['beat_period_s'] is not None: st.metric('Beat period',f"{r['beat_period_s']:.5g} s")
    go=_plotly(); fig=go.Figure(); fig.add_scatter(x=r['time_s'],y=r['x1'],mode='lines',name='x1'); fig.add_scatter(x=r['time_s'],y=r['x2'],mode='lines',name='x2'); fig.update_layout(title='Energy exchange / beating',xaxis_title='Time',yaxis_title='Displacement',height=450); st.plotly_chart(fig,width='stretch'); st.caption(r['boundary'])


def render_remaining_science_workspace(st: Any, profile: str) -> None:
    if profile not in {'ising-monte-carlo','random-walk-monte-carlo','nonlinear-chaos','oscillation-integration'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Advanced Model Science')
    st.caption('Second-wave model-content studies: phase transitions, first passage/QMC, nonlinear stroboscopic structure, and coupled modes.')
    if profile=='ising-monte-carlo': _render_ising(st)
    elif profile=='random-walk-monte-carlo': _render_random(st)
    elif profile=='nonlinear-chaos': _render_duffing(st)
    else: _render_modes(st)
