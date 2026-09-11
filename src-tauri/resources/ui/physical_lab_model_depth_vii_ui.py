"""UI for inverse problems and system identification."""
from __future__ import annotations
from typing import Any
from physical_lab_model_depth_vii import damped_oscillator_inverse, frequency_response_identification, regularized_inverse_demo

def _plotly(): return __import__('plotly.graph_objects',fromlist=['graph_objects'])

def _render_inverse(st:Any)->None:
    st.markdown('### Inverse problems · parameter recovery and identifiability')
    tabs=st.tabs(['Free-decay fit','Complex FRF identification','Regularization'])
    with tabs[0]:
        c1,c2,c3=st.columns(3); wn=float(c1.number_input('True ω_n',0.2,10.0,3.2,0.1,key='pl_vii_wn')); z=float(c2.number_input('True damping ratio',0.0,0.8,0.08,0.01,key='pl_vii_z')); noise=float(c3.number_input('Noise σ',0.0,0.2,0.02,0.005,key='pl_vii_noise'))
        if st.button('Fit noisy free decay',type='primary',key='pl_vii_decay_run'): st.session_state['pl_vii_decay']=damped_oscillator_inverse(omega_n=wn,zeta=z,noise_std=noise)
        r=st.session_state.get('pl_vii_decay')
        if r:
            a,b,c=st.columns(3); a.metric('Estimated ω_n',f"{r['estimate']['omega_n']:.5g}"); b.metric('Estimated ζ',f"{r['estimate']['zeta']:.5g}"); c.metric('Jacobian condition',f"{r['jacobian_condition_number']:.3e}")
            go=_plotly(); f=go.Figure(); f.add_scatter(x=r['time_s'],y=r['observed_x'],mode='markers',marker={'size':3},name='Observed'); f.add_scatter(x=r['time_s'],y=r['fit_x'],mode='lines',name='Fit'); f.update_layout(title='Noisy free-decay inverse fit',xaxis_title='Time',yaxis_title='x',height=430); st.plotly_chart(f,width='stretch'); st.json({'truth':r['truth'],'estimate':r['estimate'],'standard_error':r['standard_error'],'rmse':r['rmse']}); st.caption(r['boundary'])
    with tabs[1]:
        c1,c2=st.columns(2); k=float(c1.number_input('True stiffness k',1.0,100.0,18.0,1.0,key='pl_vii_k')); damp=float(c2.number_input('True damping c',0.0,10.0,0.7,0.1,key='pl_vii_c'))
        if st.button('Identify from complex FRF',key='pl_vii_frf_run'): st.session_state['pl_vii_frf']=frequency_response_identification(stiffness=k,damping=damp)
        r=st.session_state.get('pl_vii_frf')
        if r:
            a,b,c=st.columns(3); a.metric('Estimated k',f"{r['estimate']['stiffness']:.5g}"); b.metric('Estimated c',f"{r['estimate']['damping']:.5g}"); c.metric('Jacobian condition',f"{r['jacobian_condition_number']:.3e}")
            go=_plotly(); import numpy as np
            obs=np.asarray(r['observed_real'])+1j*np.asarray(r['observed_imag']); fit=np.asarray(r['fit_real'])+1j*np.asarray(r['fit_imag']); f=go.Figure(); f.add_scatter(x=r['omega_rad_s'],y=np.abs(obs),mode='markers',name='Observed |H|'); f.add_scatter(x=r['omega_rad_s'],y=np.abs(fit),mode='lines',name='Fit |H|'); f.update_layout(title='Complex FRF identification',xaxis_title='ω',yaxis_title='|H|',height=430); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])
    with tabs[2]:
        if st.button('Run ill-conditioned ridge demo',key='pl_vii_ridge_run'): st.session_state['pl_vii_ridge']=regularized_inverse_demo()
        r=st.session_state.get('pl_vii_ridge')
        if r:
            st.metric('Design condition number',f"{r['design_condition_number']:.3e}"); st.dataframe(r['rows'],hide_index=True,width='stretch'); go=_plotly(); f=go.Figure(); f.add_scatter(x=[x['lambda'] for x in r['rows']],y=[x['parameter_error_norm'] for x in r['rows']],mode='lines+markers',name='Parameter error'); f.add_scatter(x=[x['lambda'] for x in r['rows']],y=[x['prediction_rmse_vs_truth'] for x in r['rows']],mode='lines+markers',name='Prediction RMSE'); f.update_layout(title='Ridge bias–variance / stability tradeoff',xaxis_type='log',xaxis_title='λ',height=430); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])

def render_model_depth_vii_workspace(st:Any,profile:str)->None:
    if profile not in {'oscillation-integration','numerical-methods'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Model Depth VII')
    _render_inverse(st)
