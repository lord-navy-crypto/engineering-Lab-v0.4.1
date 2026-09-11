"""UI for third-wave non-accelerator model-depth studies."""
from __future__ import annotations
from typing import Any

from physical_lab_model_depth import (
    ising_autocorrelation_scan,
    duffing_lyapunov_scan,
    lattice_dynamic_structure_factor,
)


def _plotly():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_ising(st: Any) -> None:
    st.markdown("### Ising · autocorrelation and effective sample size")
    st.caption("Quantify serial dependence of Metropolis samples instead of treating every recorded sweep as independent evidence.")
    c1,c2,c3=st.columns(3)
    L=int(c1.number_input("Autocorrelation lattice L",6,48,16,2,key="pl_depth_ising_L"))
    burn=int(c2.number_input("Autocorrelation burn sweeps",100,4000,500,100,key="pl_depth_ising_burn"))
    samples=int(c3.number_input("Autocorrelation sample sweeps",300,6000,1800,100,key="pl_depth_ising_samples"))
    temps_text=st.text_input("Autocorrelation temperatures","1.8,2.1,2.269,2.4,2.8",key="pl_depth_ising_temps")
    if st.button("Run Ising autocorrelation study",key="pl_depth_ising_run"):
        try:
            temps=[float(x.strip()) for x in temps_text.split(',') if x.strip()]
            with st.spinner("Running correlated Metropolis chains..."):
                st.session_state['pl_depth_ising']=ising_autocorrelation_scan(L=L,temperatures=temps,burn_sweeps=burn,sample_sweeps=samples)
        except Exception as exc: st.error(str(exc))
    r=st.session_state.get('pl_depth_ising')
    if not r:return
    a,b=st.columns(2); a.metric('Largest τ_int',f"{r['max_magnetization_tau_int_sweeps']:.3g} sweeps"); b.metric('Temperature at max τ_int',f"{r['max_tau_temperature']:.5g}")
    go=_plotly(); fig=go.Figure()
    fig.add_scatter(x=[x['temperature'] for x in r['rows']],y=[x['magnetization_tau_int_sweeps'] for x in r['rows']],mode='lines+markers',name='|M| τ_int')
    fig.add_scatter(x=[x['temperature'] for x in r['rows']],y=[x['energy_tau_int_sweeps'] for x in r['rows']],mode='lines+markers',name='Energy τ_int')
    fig.update_layout(title='Metropolis autocorrelation time vs temperature',xaxis_title='Temperature',yaxis_title='Integrated autocorrelation time (sweeps)',height=440); st.plotly_chart(fig,width='stretch')
    st.dataframe([{k:v for k,v in row.items() if k!='magnetization_acf'} for row in r['rows']],hide_index=True,width='stretch'); st.caption(r['boundary'])


def _render_duffing(st: Any) -> None:
    st.markdown("### Duffing · tangent-equation finite-time Lyapunov exponent")
    c1,c2,c3=st.columns(3)
    start=float(c1.number_input('Lyapunov amplitude start',0.0,1.0,0.20,0.02,key='pl_depth_duf_start'))
    stop=float(c2.number_input('Lyapunov amplitude stop',0.05,1.5,0.48,0.02,key='pl_depth_duf_stop'))
    points=int(c3.select_slider('Lyapunov amplitude points',options=[6,8,10,12],value=8,key='pl_depth_duf_points'))
    if st.button('Run Duffing variational Lyapunov study',key='pl_depth_duf_run'):
        import numpy as np
        if stop<=start: st.error('Stop must exceed start.')
        else:
            with st.spinner('Integrating Duffing state + tangent dynamics...'):
                st.session_state['pl_depth_duf']=duffing_lyapunov_scan(amplitudes=np.linspace(start,stop,points))
    r=st.session_state.get('pl_depth_duf')
    if not r:return
    st.metric('Largest finite-time exponent',f"{r['max_ftle_per_time']:.5g} / time")
    go=_plotly(); fig=go.Figure(); fig.add_scatter(x=[x['drive_amplitude'] for x in r['rows']],y=[x['largest_finite_time_lyapunov_per_time'] for x in r['rows']],mode='lines+markers')
    fig.add_hline(y=0.0,line_dash='dash'); fig.update_layout(title='Duffing variational finite-time Lyapunov exponent',xaxis_title='Drive amplitude',yaxis_title='Largest FTLE / time',height=450); st.plotly_chart(fig,width='stretch')
    st.dataframe([{k:v for k,v in row.items() if k!='local_period_exponents'} for row in r['rows']],hide_index=True,width='stretch'); st.caption(r['boundary'])


def _render_lattice(st: Any) -> None:
    st.markdown("### Honeycomb lattice · q-resolved S(q,ω)")
    st.caption("Use only reciprocal vectors allowed by the periodic finite supercell; no fake continuous-q path is introduced.")
    c1,c2,c3=st.columns(3)
    nx=int(c1.number_input('S(q,ω) cells x',2,8,4,1,key='pl_depth_sq_nx'))
    ny=int(c2.number_input('S(q,ω) cells y',2,8,4,1,key='pl_depth_sq_ny'))
    steps=int(c3.select_slider('S(q,ω) trajectory steps',options=[1024,2048,4096],value=2048,key='pl_depth_sq_steps'))
    q_text=st.text_input('Allowed integer q modes','1,0; 0,1; 1,1; 2,0',key='pl_depth_sq_modes')
    if st.button('Run q-resolved lattice spectrum',key='pl_depth_sq_run'):
        try:
            modes=[]
            for item in q_text.split(';'):
                vals=[int(x.strip()) for x in item.split(',') if x.strip()]
                if len(vals)==2:modes.append(vals)
            with st.spinner('Running conservative lattice trajectory and density-fluctuation spectra...'):
                st.session_state['pl_depth_sq']=lattice_dynamic_structure_factor(nx=nx,ny=ny,steps=steps,q_modes=modes)
        except Exception as exc: st.error(str(exc))
    r=st.session_state.get('pl_depth_sq')
    if not r:return
    st.metric('Max relative energy drift',f"{r['max_relative_energy_drift']:.2e}")
    go=_plotly(); fig=go.Figure()
    for row in r['modes']:
        label=f"q={tuple(row['mode_index'])}"
        fig.add_scatter(x=row['frequency_cycles_per_reduced_time'],y=row['S_q_omega_normalized'],mode='lines',name=label)
    fig.update_layout(title='Finite-cell q-resolved dynamic structure factor',xaxis_title='Frequency (cycles / reduced time)',yaxis_title='Normalized S(q,ω)',height=470); st.plotly_chart(fig,width='stretch')
    st.dataframe([{'q_mode':row['mode_index'],'|q|':row['q_magnitude'],'dominant_frequency':row['dominant_frequency_cycles_per_reduced_time']} for row in r['modes']],hide_index=True,width='stretch'); st.caption(r['boundary'])


def _render_depth_iv(st: Any, profile: str) -> None:
    try:
        from physical_lab_model_depth_iv_ui import render_model_depth_iv_workspace
        render_model_depth_iv_workspace(st, profile)
    except Exception as exc:
        st.warning(f"Physical Lab Model Depth IV could not load: {exc}")


def render_model_depth_workspace(st: Any, profile: str) -> None:
    if profile not in {'ising-monte-carlo','nonlinear-chaos','oscillation-integration','numerical-methods'}: return
    if profile in {'ising-monte-carlo','nonlinear-chaos','oscillation-integration'}:
        st.markdown('---'); st.markdown('## Physical Lab · Model Depth III')
        if profile=='ising-monte-carlo': _render_ising(st)
        elif profile=='nonlinear-chaos': _render_duffing(st)
        else: _render_lattice(st)
    if profile in {'nonlinear-chaos','numerical-methods'}:
        _render_depth_iv(st, profile)
