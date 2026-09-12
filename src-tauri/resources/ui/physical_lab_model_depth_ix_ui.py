"""UI for ninth-wave control-systems and PDE field-physics studies."""
from __future__ import annotations
from typing import Any
from physical_lab_model_depth_ix import pid_step_response,lqr_kalman_demo,heat_equation_1d,wave_equation_1d,poisson_equation_2d

def _plotly(): return __import__('plotly.graph_objects',fromlist=['graph_objects'])

def _render_control(st:Any)->None:
    st.markdown('### Control Systems Lab · feedback, estimation, and control effort')
    tabs=st.tabs(['PID step response','LQR + Kalman'])
    with tabs[0]:
        c1,c2,c3=st.columns(3); kp=float(c1.number_input('Kp',0.0,50.0,8.0,0.5,key='pl_ix_kp')); ki=float(c2.number_input('Ki',0.0,20.0,2.0,0.25,key='pl_ix_ki')); kd=float(c3.number_input('Kd',0.0,20.0,2.0,0.25,key='pl_ix_kd'))
        if st.button('Run PID closed-loop step',type='primary',key='pl_ix_pid_run'): st.session_state['pl_ix_pid']=pid_step_response(kp=kp,ki=ki,kd=kd)
        r=st.session_state.get('pl_ix_pid')
        if r:
            a,b,c=st.columns(3); a.metric('Overshoot',f"{r['overshoot_pct']:.3g}%"); b.metric('Settling time','—' if r['settling_time_s'] is None else f"{r['settling_time_s']:.3g} s"); c.metric('Control RMS',f"{r['control_rms']:.3g}")
            go=_plotly(); f=go.Figure(); f.add_scatter(x=r['time_s'],y=r['position'],mode='lines',name='x(t)'); f.add_scatter(x=r['time_s'],y=[r['reference']]*len(r['time_s']),mode='lines',name='reference'); f.update_layout(title='PID closed-loop tracking',xaxis_title='Time (s)',yaxis_title='Position',height=420); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])
    with tabs[1]:
        c1,c2=st.columns(2); q=float(c1.number_input('Process noise σ',0.0,0.2,0.02,0.005,key='pl_ix_q')); rn=float(c2.number_input('Measurement noise σ',0.0,0.5,0.08,0.01,key='pl_ix_r'))
        if st.button('Run LQR + Kalman benchmark',key='pl_ix_lqg_run'): st.session_state['pl_ix_lqg']=lqr_kalman_demo(process_noise=q,measurement_noise=rn)
        r=st.session_state.get('pl_ix_lqg')
        if r:
            a,b,c=st.columns(3); a.metric('Position estimate RMSE',f"{r['position_estimation_rmse']:.4g}"); b.metric('Velocity estimate RMSE',f"{r['velocity_estimation_rmse']:.4g}"); c.metric('Control RMS',f"{r['control_rms']:.4g}")
            go=_plotly(); f=go.Figure(); f.add_scatter(x=r['time_s'],y=[x[0] for x in r['state']],mode='lines',name='true x'); f.add_scatter(x=r['time_s'],y=[x[0] for x in r['state_estimate']],mode='lines',name='estimated x'); f.update_layout(title='Kalman state estimation under LQR feedback',xaxis_title='Time (s)',yaxis_title='Position',height=420); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])

def _render_pde(st:Any)->None:
    st.markdown('### Field PDE Lab · heat, waves, and Poisson fields')
    tabs=st.tabs(['Heat equation','Wave equation','Poisson 2-D'])
    with tabs[0]:
        n=int(st.select_slider('Heat grid points',options=[41,81,161,321],value=81,key='pl_ix_heat_n'))
        if st.button('Solve heat equation',key='pl_ix_heat_run'): st.session_state['pl_ix_heat']=heat_equation_1d(points=n)
        r=st.session_state.get('pl_ix_heat')
        if r:
            st.metric('L2 error',f"{r['l2_error']:.3e}"); go=_plotly(); f=go.Figure(); f.add_scatter(x=r['x'],y=r['analytic'],mode='lines',name='analytic'); f.add_scatter(x=r['x'],y=r['numerical'],mode='lines',name='Crank–Nicolson'); f.update_layout(title='1-D diffusion field',height=400); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])
    with tabs[1]:
        n=int(st.select_slider('Wave grid points',options=[81,161,321,641],value=161,key='pl_ix_wave_n'))
        if st.button('Solve wave equation',key='pl_ix_wave_run'): st.session_state['pl_ix_wave']=wave_equation_1d(points=n)
        r=st.session_state.get('pl_ix_wave')
        if r:
            a,b=st.columns(2); a.metric('L2 error',f"{r['l2_error']:.3e}"); b.metric('Max relative energy drift',f"{r['max_relative_energy_drift']:.3e}"); go=_plotly(); f=go.Figure(); f.add_scatter(x=r['x'],y=r['analytic'],mode='lines',name='analytic'); f.add_scatter(x=r['x'],y=r['numerical'],mode='lines',name='finite difference'); f.update_layout(title='1-D wave field',height=400); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])
    with tabs[2]:
        n=int(st.select_slider('Poisson grid points',options=[21,31,41,61,81],value=41,key='pl_ix_poisson_n'))
        if st.button('Solve 2-D Poisson field',key='pl_ix_poisson_run'): st.session_state['pl_ix_poisson']=poisson_equation_2d(points=n)
        r=st.session_state.get('pl_ix_poisson')
        if r:
            a,b=st.columns(2); a.metric('L2 error',f"{r['l2_error']:.3e}"); b.metric('Relative linear-system residual',f"{r['relative_residual']:.3e}")
            go=_plotly(); f=go.Figure(data=go.Heatmap(z=r['solution'],x=r['x'],y=r['y'])); f.update_layout(title='2-D Poisson solution field',xaxis_title='x',yaxis_title='y',height=500); st.plotly_chart(f,width='stretch'); st.caption(r['boundary'])

def render_model_depth_ix_workspace(st:Any,profile:str)->None:
    if profile not in {'oscillation-integration','numerical-methods'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Model Depth IX')
    if profile=='oscillation-integration': _render_control(st)
    if profile=='numerical-methods': _render_pde(st)
