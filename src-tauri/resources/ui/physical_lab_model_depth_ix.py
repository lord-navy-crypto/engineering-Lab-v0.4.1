"""Ninth-wave model-depth studies: control systems and PDE field physics."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import solve_continuous_are, solve_discrete_are
from scipy import signal, sparse
from scipy.sparse.linalg import spsolve


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


def pid_step_response(*, mass:float=1.0, damping:float=0.8, stiffness:float=4.0, kp:float=8.0, ki:float=2.0, kd:float=2.0, reference:float=1.0, duration:float=12.0, samples:int=1200)->dict[str,Any]:
    if min(mass,stiffness,duration)>0 and damping>=0 and min(kp,ki,kd)>=0:
        pass
    else: raise ValueError('invalid PID/plant parameters')
    n=max(300,min(int(samples),10000)); t=np.linspace(0,duration,n)
    def rhs(_t,s):
        x,v,inte=s; err=reference-x; u=kp*err+ki*inte-kd*v
        return [v,(u-damping*v-stiffness*x)/mass,err]
    sol=solve_ivp(rhs,(0,duration),[0,0,0],t_eval=t,rtol=1e-9,atol=1e-11)
    x,v,inte=sol.y; err=reference-x; u=kp*err+ki*inte-kd*v
    overshoot=max(0.0,(float(np.max(x))-reference)/max(abs(reference),1e-12)*100.0)
    tol=0.02*max(abs(reference),1.0); settling=None
    outside=np.where(np.abs(err)>tol)[0]
    if len(outside)==0: settling=0.0
    elif outside[-1] < len(t)-1: settling=float(t[outside[-1]+1])
    return _plain({'schema':'physical-lab-pid-step-v1','time_s':t,'position':x,'velocity':v,'control':u,'reference':reference,'overshoot_pct':overshoot,'settling_time_s':settling,'iae':float(np.trapz(np.abs(err),t)),'control_rms':float(np.sqrt(np.mean(u*u))),'boundary':'Linear SDOF plant with ideal continuous PID and no actuator saturation, delay, quantization, or derivative filtering. Performance metrics are model-local, not hardware guarantees.'})


def lqr_kalman_demo(*, mass:float=1.0, damping:float=0.5, stiffness:float=2.0, dt:float=0.02, duration:float=12.0, process_noise:float=0.02, measurement_noise:float=0.08, seed:int=20260911)->dict[str,Any]:
    if min(mass,stiffness,dt,duration)>0 and damping>=0 and min(process_noise,measurement_noise)>=0: pass
    else: raise ValueError('invalid LQR/Kalman parameters')
    A=np.array([[0.,1.],[-stiffness/mass,-damping/mass]]); B=np.array([[0.],[1./mass]]); C=np.array([[1.,0.]])
    Q=np.diag([12.,1.]); R=np.array([[0.7]])
    P=solve_continuous_are(A,B,Q,R); K=np.linalg.solve(R,B.T@P)
    Ad,Bd,Cd,Dd,_=signal.cont2discrete((A,B,C,np.zeros((1,1))),dt)
    W=(process_noise**2)*np.eye(2); V=np.array([[max(measurement_noise**2,1e-12)]])
    Pe=solve_discrete_are(Ad.T,Cd.T,W,V); L=Pe@Cd.T@np.linalg.inv(Cd@Pe@Cd.T+V)
    steps=max(200,min(int(duration/dt),20000)); rng=np.random.default_rng(seed)
    x=np.array([1.0,0.0]); xh=np.zeros(2); xs=[]; xhs=[]; us=[]; ys=[]
    for _ in range(steps):
        u=float(-(K@xh)[0]); w=rng.normal(scale=process_noise,size=2); x=Ad@x+Bd[:,0]*u+w
        y=float((Cd@x)[0]+rng.normal(scale=measurement_noise)); xpred=Ad@xh+Bd[:,0]*u; xh=xpred+(L@(np.array([y])-Cd@xpred))
        xs.append(x.copy()); xhs.append(xh.copy()); us.append(u); ys.append(y)
    xs=np.asarray(xs); xhs=np.asarray(xhs); t=np.arange(steps)*dt
    return _plain({'schema':'physical-lab-lqr-kalman-v1','time_s':t,'state':xs,'state_estimate':xhs,'measurement':ys,'control':us,'lqr_gain':K,'kalman_gain':L,'closed_loop_eigenvalues_real':np.real(np.linalg.eigvals(A-B@K)),'closed_loop_eigenvalues_imag':np.imag(np.linalg.eigvals(A-B@K)),'position_estimation_rmse':float(np.sqrt(np.mean((xs[:,0]-xhs[:,0])**2))),'velocity_estimation_rmse':float(np.sqrt(np.mean((xs[:,1]-xhs[:,1])**2))),'control_rms':float(np.sqrt(np.mean(np.asarray(us)**2))),'boundary':'Linear-Gaussian benchmark with known plant matrices, full model structure and synthetic white process/measurement noise. Kalman/LQR optimality applies only to this assumed model and cost/noise structure.'})


def heat_equation_1d(*, diffusivity:float=0.2, final_time:float=0.2, points:int=81, time_steps:int=400)->dict[str,Any]:
    n=max(21,min(int(points),801)); nt=max(20,min(int(time_steps),20000)); a=float(diffusivity)
    if a<=0 or final_time<=0: raise ValueError('invalid heat parameters')
    x=np.linspace(0,1,n); dx=x[1]-x[0]; dt=final_time/nt; r=a*dt/dx**2
    u=np.sin(math.pi*x); ui=u[1:-1].copy(); m=n-2
    main=(1+r)*np.ones(m); off=(-0.5*r)*np.ones(m-1); A=sparse.diags([off,main,off],[-1,0,1],format='csc')
    B=sparse.diags([0.5*r*np.ones(m-1),(1-r)*np.ones(m),0.5*r*np.ones(m-1)],[-1,0,1],format='csc')
    for _ in range(nt): ui=spsolve(A,B@ui)
    u=np.zeros(n); u[1:-1]=ui; exact=np.exp(-a*math.pi**2*final_time)*np.sin(math.pi*x)
    return _plain({'schema':'physical-lab-heat-cn-v1','x':x,'numerical':u,'analytic':exact,'dx':dx,'dt':dt,'fourier_number':r,'l2_error':float(np.sqrt(np.mean((u-exact)**2))),'max_error':float(np.max(np.abs(u-exact))),'boundary':'1-D heat equation on [0,1] with zero Dirichlet boundaries, sine initial mode, constant diffusivity, and Crank-Nicolson time stepping.'})


def wave_equation_1d(*, wave_speed:float=1.0, final_time:float=2.0, points:int=161, cfl:float=0.8)->dict[str,Any]:
    n=max(41,min(int(points),1201)); c=float(wave_speed)
    if c<=0 or final_time<=0 or not (0<cfl<=1): raise ValueError('invalid wave parameters')
    x=np.linspace(0,1,n); dx=x[1]-x[0]; dt=cfl*dx/c; nt=max(2,int(math.ceil(final_time/dt))); dt=final_time/nt; lam=c*dt/dx
    u0=np.sin(math.pi*x); um=u0.copy(); up=u0.copy(); up[1:-1]=u0[1:-1]+0.5*lam**2*(u0[2:]-2*u0[1:-1]+u0[:-2])
    energies=[]
    for _ in range(1,nt):
        un=np.zeros_like(u0); un[1:-1]=2*up[1:-1]-um[1:-1]+lam**2*(up[2:]-2*up[1:-1]+up[:-2])
        vel=(un-um)/(2*dt); grad=np.diff(up)/dx; energies.append(0.5*(float(np.mean(vel**2))+c*c*float(np.mean(grad**2))))
        um,up=up,un
    exact=np.cos(math.pi*c*final_time)*np.sin(math.pi*x); e=np.asarray(energies)
    drift=0.0 if len(e)<2 else float(np.max(np.abs(e-e[0]))/max(abs(e[0]),1e-30))
    return _plain({'schema':'physical-lab-wave-fd-v1','x':x,'numerical':up,'analytic':exact,'dx':dx,'dt':dt,'cfl':lam,'l2_error':float(np.sqrt(np.mean((up-exact)**2))),'max_relative_energy_drift':drift,'boundary':'1-D wave equation with fixed ends, sine displacement, zero initial velocity, and explicit centered leapfrog under CFL<=1.'})


def poisson_equation_2d(*, points:int=41)->dict[str,Any]:
    n=max(11,min(int(points),151)); x=np.linspace(0,1,n); h=x[1]-x[0]; ni=n-2
    xx,yy=np.meshgrid(x[1:-1],x[1:-1],indexing='ij'); exact_i=np.sin(math.pi*xx)*np.sin(math.pi*yy); f=2*math.pi**2*exact_i
    T=sparse.diags([-np.ones(ni-1),2*np.ones(ni),-np.ones(ni-1)],[-1,0,1]); I=sparse.eye(ni); A=(sparse.kron(I,T)+sparse.kron(T,I))/h**2
    rhs=f.reshape(-1); sol=spsolve(A.tocsc(),rhs); ui=sol.reshape((ni,ni)); u=np.zeros((n,n)); u[1:-1,1:-1]=ui
    exact=np.sin(math.pi*np.outer(x,np.ones(n)))*np.sin(math.pi*np.outer(np.ones(n),x)); res=A@sol-rhs
    return _plain({'schema':'physical-lab-poisson-fd-v1','x':x,'y':x,'solution':u,'analytic':exact,'grid_spacing':h,'l2_error':float(np.sqrt(np.mean((u-exact)**2))),'max_error':float(np.max(np.abs(u-exact))),'relative_residual':float(np.linalg.norm(res)/max(np.linalg.norm(rhs),1e-30)),'boundary':'2-D manufactured Poisson problem -∇²u=f on the unit square with zero Dirichlet boundaries and a five-point finite-difference stencil.'})
