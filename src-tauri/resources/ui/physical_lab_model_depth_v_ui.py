"""UI for fifth-wave stochastic and lattice localization studies."""
from __future__ import annotations
from typing import Any

from physical_lab_model_depth_v import (
    random_walk_diffusion_return_study,
    qmc_dimension_sensitivity,
    lattice_defect_localization_study,
)


def _go():
    return __import__("plotly.graph_objects", fromlist=["graph_objects"])


def _render_random(st: Any) -> None:
    st.markdown("### Random walk · diffusion scaling and first return")
    c1,c2=st.columns(2)
    walkers=int(c1.number_input("Diffusion walkers",1000,100000,12000,1000,key="pl_depthv_rw_n"))
    steps=int(c2.number_input("Diffusion horizon",100,10000,1200,100,key="pl_depthv_rw_steps"))
    if st.button("Run diffusion / return study",key="pl_depthv_rw_run"):
        with st.spinner("Simulating random-walk diffusion and return statistics..."):
            st.session_state['pl_depthv_rw']=random_walk_diffusion_return_study(walkers=walkers,steps=steps)
    r=st.session_state.get('pl_depthv_rw')
    if r:
        a,b,c=st.columns(3)
        a.metric('MSD log-log slope',f"{r['msd_loglog_slope']:.4f}")
        b.metric('Effective D (2-D)',f"{r['effective_diffusion_coefficient_2d']:.4f}")
        c.metric('Returned by horizon',f"{100*r['returned_fraction_by_horizon']:.2f}%")
        go=_go(); fig=go.Figure()
        fig.add_scatter(x=[x['step'] for x in r['rows']],y=[x['mean_square_displacement'] for x in r['rows']],mode='lines+markers',name='MSD')
        fig.update_layout(title='Mean-square displacement scaling',xaxis_title='Step',yaxis_title='⟨r²⟩',height=430); fig.update_xaxes(type='log'); fig.update_yaxes(type='log'); st.plotly_chart(fig,width='stretch')
        ret=go.Figure(); ret.add_scatter(x=[x['step'] for x in r['rows']],y=[x['origin_probability'] for x in r['rows']],mode='lines+markers',name='P(origin)'); ret.add_scatter(x=[x['step'] for x in r['rows']],y=[x['ever_returned_fraction'] for x in r['rows']],mode='lines+markers',name='ever returned'); ret.update_layout(title='Return diagnostics',xaxis_title='Step',yaxis_title='Fraction',height=430); st.plotly_chart(ret,width='stretch'); st.caption(r['boundary'])

    st.markdown("### QMC · dimension sensitivity")
    dims=st.text_input('Dimensions','2,4,8,16',key='pl_depthv_qmc_dims')
    power=int(st.select_slider('Samples = 2^p',options=[8,9,10,11,12],value=10,key='pl_depthv_qmc_power'))
    if st.button('Run dimension-sensitivity benchmark',key='pl_depthv_qmc_run'):
        try:
            dd=[int(x.strip()) for x in dims.split(',') if x.strip()]
            with st.spinner('Comparing MC and scrambled Sobol across dimensions...'):
                st.session_state['pl_depthv_qmc']=qmc_dimension_sensitivity(dimensions=dd,power=power)
        except Exception as exc: st.error(str(exc))
    q=st.session_state.get('pl_depthv_qmc')
    if q:
        go=_go(); fig=go.Figure(); fig.add_scatter(x=[x['dimension'] for x in q['rows']],y=[x['mc_median_abs_error'] for x in q['rows']],mode='lines+markers',name='MC'); fig.add_scatter(x=[x['dimension'] for x in q['rows']],y=[x['qmc_median_abs_error'] for x in q['rows']],mode='lines+markers',name='Scrambled Sobol'); fig.update_layout(title='Fixed-budget error vs dimension',xaxis_title='Dimension',yaxis_title='Median absolute error',height=440); fig.update_yaxes(type='log'); st.plotly_chart(fig,width='stretch'); st.dataframe(q['rows'],hide_index=True,width='stretch'); st.caption(q['boundary'])


def _render_localization(st: Any) -> None:
    st.markdown("### Honeycomb finite supercell · defect-mode localization")
    st.caption("Build a finite-cell numerical Hessian and compare pristine vs defective normal-mode participation; defects are intentionally excluded from the Bloch bulk reference and handled here instead.")
    c1,c2,c3=st.columns(3)
    n=int(c1.number_input('Localization cells x=y',2,4,3,1,key='pl_depthv_loc_n'))
    defect=c2.selectbox('Defect model',['mass','weak-bond','line-weak-bond'],key='pl_depthv_loc_def')
    strength=float(c3.number_input('Mass multiplier / bond-scale control',0.1,8.0,4.0,0.25,key='pl_depthv_loc_strength'))
    if st.button('Run defect-localization modes',key='pl_depthv_loc_run'):
        kwargs={'nx':n,'ny':n,'defect_mode':defect}
        if defect=='mass': kwargs['defect_mass_multiplier']=strength
        else: kwargs['defect_bond_scale']=min(strength,1.0)
        try:
            with st.spinner('Building finite-supercell Hessians and diagonalizing normal modes...'):
                st.session_state['pl_depthv_loc']=lattice_defect_localization_study(**kwargs)
        except Exception as exc: st.error(str(exc))
    r=st.session_state.get('pl_depthv_loc')
    if not r:return
    a,b,c=st.columns(3)
    a.metric('Pristine median participation',f"{r['pristine_median_participation_fraction']:.3f}")
    b.metric('Defect median participation',f"{r['defect_median_participation_fraction']:.3f}")
    c.metric('Most localized participation',f"{r['most_localized_defect_mode']['participation_ratio_fraction']:.3f}")
    go=_go(); fig=go.Figure(); fig.add_scatter(x=[x['frequency_cycles_per_time'] for x in r['pristine_modes']],y=[x['participation_ratio_fraction'] for x in r['pristine_modes']],mode='markers',name='pristine'); fig.add_scatter(x=[x['frequency_cycles_per_time'] for x in r['defect_modes']],y=[x['participation_ratio_fraction'] for x in r['defect_modes']],mode='markers',name='defect'); fig.update_layout(title='Normal-mode participation vs frequency',xaxis_title='Frequency (cycles / reduced time)',yaxis_title='Participation fraction',height=460); st.plotly_chart(fig,width='stretch')
    overlap=go.Figure(); overlap.add_scatter(x=[x['frequency_cycles_per_time'] for x in r['defect_modes']],y=[x['defect_overlap_fraction'] for x in r['defect_modes']],mode='markers',name='defect overlap'); overlap.update_layout(title='Mode weight on defect sites',xaxis_title='Frequency',yaxis_title='Defect overlap fraction',height=430); st.plotly_chart(overlap,width='stretch'); st.json({'mostLocalized':r['most_localized_defect_mode'],'largestDefectOverlap':r['largest_defect_overlap_mode']},expanded=False); st.caption(r['boundary'])


def render_model_depth_v_workspace(st: Any, profile: str) -> None:
    if profile not in {'random-walk-monte-carlo','oscillation-integration'}: return
    st.markdown('---'); st.markdown('## Physical Lab · Model Depth V')
    if profile=='random-walk-monte-carlo': _render_random(st)
    else: _render_localization(st)
