"""Seventh-wave model-depth studies: inverse problems and system identification."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
from scipy.optimize import least_squares


def _plain(v: Any) -> Any:
    if v is None or isinstance(v,(str,bool,int)): return v
    if isinstance(v,float): return v if math.isfinite(v) else None
    if isinstance(v,dict): return {str(k):_plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_plain(x) for x in v]
    if isinstance(v,np.ndarray): return [_plain(x) for x in v.tolist()]
    if hasattr(v,'item'):
        try:return _plain(v.item())
        except Exception:pass
    return v


def _svd_condition(jac: np.ndarray) -> tuple[float,list[float]]:
    s=np.linalg.svd(np.asarray(jac,float),compute_uv=False)
    cond=float('inf') if s[-1] <= 1e-15*max(s[0],1e-30) else float(s[0]/s[-1])
    return cond,[float(x) for x in s]


def damped_oscillator_inverse(*, omega_n:float=3.2,zeta:float=0.08,amplitude:float=1.0,phase:float=0.25,noise_std:float=0.02,duration:float=12.0,samples:int=500,seed:int=20260911)->dict[str,Any]:
    if not (omega_n>0 and 0<=zeta<1 and amplitude>0 and noise_std>=0): raise ValueError('invalid oscillator parameters')
    n=max(120,min(int(samples),5000)); t=np.linspace(0,float(duration),n); wd=omega_n*math.sqrt(max(1-zeta*zeta,1e-12))
    def signal(p):
        wn,zz,A,ph=map(float,p); wdd=wn*math.sqrt(max(1-zz*zz,1e-12)); return A*np.exp(-zz*wn*t)*np.cos(wdd*t+ph)
    truth=signal([omega_n,zeta,amplitude,phase]); rng=np.random.default_rng(seed); y=truth+rng.normal(scale=noise_std,size=n)
    guess=np.asarray([omega_n*0.85,min(0.3,zeta*1.5+0.01),amplitude*0.9,0.0])
    scale=max(noise_std,float(np.std(y))*1e-3,1e-6)
    sol=least_squares(lambda p:(signal(p)-y)/scale,guess,bounds=([0.1,0.0,1e-6,-2*math.pi],[20.0,0.95,10.0,2*math.pi]),method='trf')
    fit=signal(sol.x); cond,svals=_svd_condition(sol.jac)
    dof=max(n-len(sol.x),1); sigma2=float(np.sum((fit-y)**2)/dof); jtj=sol.jac.T@sol.jac
    cov=np.linalg.pinv(jtj)*sigma2/(scale*scale); stderr=np.sqrt(np.maximum(np.diag(cov),0.0))
    return _plain({'schema':'physical-lab-damped-oscillator-inverse-v1','time_s':t,'observed_x':y,'truth_x':truth,'fit_x':fit,'truth':{'omega_n':omega_n,'zeta':zeta,'amplitude':amplitude,'phase':phase},'estimate':dict(zip(['omega_n','zeta','amplitude','phase'],map(float,sol.x))),'standard_error':dict(zip(['omega_n','zeta','amplitude','phase'],map(float,stderr))),'jacobian_condition_number':cond,'jacobian_singular_values':svals,'rmse':float(np.sqrt(np.mean((fit-y)**2))),'success':bool(sol.success),'boundary':'Synthetic noisy underdamped free-decay identification. Jacobian conditioning is a local identifiability diagnostic, not proof of global parameter uniqueness or experimental validity.'})


def frequency_response_identification(*,mass:float=1.0,stiffness:float=18.0,damping:float=0.7,noise_fraction:float=0.015,points:int=90,seed:int=20260911)->dict[str,Any]:
    if min(mass,stiffness)<=0 or damping<0: raise ValueError('invalid SDOF parameters')
    wn=math.sqrt(stiffness/mass); w=np.linspace(0.25*wn,2.2*wn,max(30,min(int(points),600)))
    def H(k,c): return 1.0/(k-mass*w*w+1j*c*w)
    true=H(stiffness,damping); rng=np.random.default_rng(seed); sigma=noise_fraction*max(float(np.max(np.abs(true))),1e-12)
    obs=true+sigma*(rng.normal(size=len(w))+1j*rng.normal(size=len(w)))/math.sqrt(2)
    def residual(p):
        pred=H(float(p[0]),float(p[1])); d=(pred-obs)/sigma; return np.concatenate([d.real,d.imag])
    sol=least_squares(residual,[stiffness*0.8,max(damping*1.3,0.05)],bounds=([1e-4,0.0],[1e4,1e3]))
    est=H(*sol.x); cond,svals=_svd_condition(sol.jac)
    return _plain({'schema':'physical-lab-frf-identification-v1','omega_rad_s':w,'observed_real':obs.real,'observed_imag':obs.imag,'fit_real':est.real,'fit_imag':est.imag,'truth':{'mass':mass,'stiffness':stiffness,'damping':damping},'estimate':{'stiffness':float(sol.x[0]),'damping':float(sol.x[1])},'jacobian_condition_number':cond,'jacobian_singular_values':svals,'complex_rmse':float(np.sqrt(np.mean(np.abs(est-obs)**2))),'boundary':'Synthetic complex compliance FRF of a linear SDOF oscillator with known mass. Simultaneous real/imaginary fitting preserves phase information; it is not modal validation against measured hardware.'})


def regularized_inverse_demo(*,samples:int=80,noise_std:float=0.03,lambdas=(0.0,1e-6,1e-4,1e-2,1e-1,1.0),seed:int=20260911)->dict[str,Any]:
    n=max(30,min(int(samples),1000)); x=np.linspace(0,1,n); eps=1e-3
    A=np.column_stack([np.ones(n),x,x+eps*x*x]); theta=np.asarray([1.0,2.0,-1.5]); y0=A@theta; rng=np.random.default_rng(seed); y=y0+rng.normal(scale=noise_std,size=n)
    rows=[]
    for lam in [float(v) for v in lambdas]:
        lhs=A.T@A+lam*np.eye(3); est=np.linalg.solve(lhs,A.T@y); pred=A@est
        rows.append({'lambda':lam,'estimate':est,'parameter_error_norm':float(np.linalg.norm(est-theta)),'prediction_rmse_vs_noisy':float(np.sqrt(np.mean((pred-y)**2))),'prediction_rmse_vs_truth':float(np.sqrt(np.mean((pred-y0)**2))),'coefficient_norm':float(np.linalg.norm(est))})
    return _plain({'schema':'physical-lab-regularized-inverse-v1','design_condition_number':float(np.linalg.cond(A)),'truth_coefficients':theta,'rows':rows,'boundary':'Deliberately collinear linear inverse problem illustrating instability and ridge bias-variance tradeoff. The preferred lambda depends on prediction/parameter goals and is not selected automatically here.'})
