"""UI for sixth-wave model-depth studies."""
from __future__ import annotations
from typing import Any
from physical_lab_model_depth_vi import (
    coupled_modal_energy_transfer,
    coupled_detuning_scan,
    bootstrap_mean_uncertainty,
    gaussian_tail_importance_sampling,
)


def _plotly(): return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_modal(st: Any) -> None:
    st.markdown("### Coupled modes · modal energy and detuning")
    c1,c2,c3=st.columns(3)
    kc=float(c1.number_input("Coupling k",0.0,1.0,0.12,0.02,key="pl_vi_kc"))
    duration=float(c2.number_input("Duration",20.0,500.0,180.0,10.0,key="pl_vi_duration"))
    detspan=float(c3.number_input("Detuning span",0.05,0.9,0.5,0.05,key="pl_vi_detspan"))
    if st.button("Run modal-energy study",type="primary",key="pl_vi_modal_run"):
        import numpy as np
        with st.spinner("Projecting the physical motion into mass-normalized normal modes..."):
            st.session_state['pl_vi_modal']=coupled_modal_energy_transfer(coupling_k=kc,duration=duration)
            st.session_state['pl_vi_detuning']=coupled_detuning_scan(detunings=np.linspace(-detspan,detspan,9),coupling_k=kc,duration=min(duration,220.0))
    r=st.session_state.get('pl_vi_modal'); d=st.session_state.get('pl_vi_detuning')
    if r:
        a,b,c=st.columns(3)
        a.metric('ω₁',f"{r['normal_mode_omega_rad_s'][0]:.5g}")
        b.metric('ω₂',f"{r['normal_mode_omega_rad_s'][1]:.5g}")
        c.metric('Max transfer to oscillator 2',f"{100*r['max_oscillator2_energy_fraction']:.2f}%")
        go=_plotly(); fig=go.Figure()
        mf=r['modal_energy_fraction']; t=r['time_s']
        fig.add_scatter(x=t,y=[x[0] for x in mf],mode='lines',name='Mode 1 energy fraction')
        fig.add_scatter(x=t,y=[x[1] for x in mf],mode='lines',name='Mode 2 energy fraction')
        fig.update_layout(title='Modal energy fractions',xaxis_title='Time',yaxis_title='Fraction',height=430); st.plotly_chart(fig,width='stretch')
        ex=go.Figure(); ex.add_scatter(x=t,y=r['oscillator2_energy_fraction'],mode='lines',name='Oscillator 2 physical-energy fraction'); ex.update_layout(title='Physical energy exchange',xaxis_title='Time',yaxis_title='Energy fraction',height=430); st.plotly_chart(ex,width='stretch')
        st.caption(r['boundary'])
    if d:
        go=_plotly(); fig=go.Figure(); fig.add_scatter(x=[x['relative_detuning'] for x in d['rows']],y=[x['max_energy_transfer_to_oscillator2'] for x in d['rows']],mode='lines+markers'); fig.update_layout(title='Detuning suppresses/enhances finite-window transfer',xaxis_title='Relative k₂ detuning',yaxis_title='Max transfer fraction',height=420); st.plotly_chart(fig,width='stretch'); st.caption(d['boundary'])


def _render_mc(st: Any) -> None:
    st.markdown("### Monte Carlo · estimator uncertainty and rare events")
    tabs=st.tabs(["Bootstrap uncertainty","Rare-event importance sampling"])
    with tabs[0]:
        c1,c2=st.columns(2)
        n=int(c1.number_input('Sample size',30,5000,200,10,key='pl_vi_boot_n'))
        B=int(c2.number_input('Bootstrap replicates',200,10000,1500,100,key='pl_vi_boot_B'))
        if st.button('Run bootstrap uncertainty',key='pl_vi_boot_run'):
            st.session_state['pl_vi_boot']=bootstrap_mean_uncertainty(sample_size=n,bootstrap_replicates=B)
        r=st.session_state.get('pl_vi_boot')
        if r:
            a,b,c=st.columns(3); a.metric('Estimate',f"{r['estimate']:.6f}"); b.metric('Bootstrap SE',f"{r['bootstrap_standard_error']:.3e}"); c.metric('Reference in 95% interval',str(r['reference_inside_interval']))
            st.write({'95% percentile interval':r['percentile_95_interval'],'analytic reference':r['analytic_reference']}); st.caption(r['boundary'])
    with tabs[1]:
        c1,c2,c3=st.columns(3)
        threshold=float(c1.number_input('Tail threshold σ',1.5,7.0,4.0,0.25,key='pl_vi_tail_a'))
        samples=int(c2.number_input('Samples / replicate',1000,500000,50000,5000,key='pl_vi_tail_n'))
        reps=int(c3.number_input('Replicates',6,80,20,2,key='pl_vi_tail_rep'))
        if st.button('Compare crude MC and importance sampling',type='primary',key='pl_vi_tail_run'):
            with st.spinner('Estimating the same Gaussian tail with two sampling laws...'):
                st.session_state['pl_vi_tail']=gaussian_tail_importance_sampling(threshold=threshold,samples=samples,replicates=reps)
        r=st.session_state.get('pl_vi_tail')
        if r:
            a,b,c=st.columns(3); a.metric('Exact tail probability',f"{r['analytic_reference_probability']:.4e}"); b.metric('Crude replicate σ',f"{r['crude_mc']['replicate_std']:.3e}"); c.metric('IS σ reduction',f"{r['std_reduction_factor']:.2f}×")
            st.dataframe([
                {'method':'Crude MC',**r['crude_mc']},
                {'method':'Importance sampling',**r['importance_sampling']},
            ],hide_index=True,width='stretch'); st.caption(r['boundary'])


def render_model_depth_vi_workspace(st: Any, profile: str) -> None:
    if profile not in {'oscillation-integration','random-walk-monte-carlo'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Model Depth VI')
    if profile=='oscillation-integration': _render_modal(st)
    else: _render_mc(st)
