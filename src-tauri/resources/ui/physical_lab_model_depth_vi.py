"""Sixth-wave model-depth studies: modal energy transfer and Monte Carlo uncertainty.

Adds:
- Coupled two-DOF modal projection, modal energies, and detuning-dependent transfer efficiency.
- Bootstrap uncertainty for a bounded estimator.
- Crude Monte Carlo vs importance sampling for a Gaussian rare-event probability.

All outputs are finite computational diagnostics, not experimental calibration or universal efficiency claims.
"""
from __future__ import annotations
import math
from typing import Any, Iterable, Sequence


def _np():
    import numpy as np
    return np


def _plain(v: Any) -> Any:
    np = _np()
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return [_plain(x) for x in v.tolist()]
    if hasattr(v, "item"):
        try: return _plain(v.item())
        except Exception: pass
    return v


def _mass_normal_modes(m1: float, m2: float, k1: float, k2: float, kc: float):
    np = _np()
    M = np.diag([m1, m2])
    K = np.asarray([[k1+kc, -kc], [-kc, k2+kc]], dtype=float)
    Minvhalf = np.diag(1.0 / np.sqrt([m1, m2]))
    D = Minvhalf @ K @ Minvhalf
    evals, U = np.linalg.eigh(0.5*(D+D.T))
    order = np.argsort(evals); evals = evals[order]; U = U[:, order]
    Phi = Minvhalf @ U
    omega = np.sqrt(np.maximum(evals, 0.0))
    return M, K, Phi, omega


def coupled_modal_energy_transfer(
    *, mass1: float = 1.0, mass2: float = 1.0, ground_k1: float = 1.0, ground_k2: float = 1.0,
    coupling_k: float = 0.12, duration: float = 180.0, dt: float = 0.02,
    initial_x: Sequence[float] = (1.0, 0.0), initial_v: Sequence[float] = (0.0, 0.0),
) -> dict[str, Any]:
    np = _np(); m1=float(mass1); m2=float(mass2); k1=float(ground_k1); k2=float(ground_k2); kc=float(coupling_k)
    if min(m1,m2) <= 0 or min(k1,k2,kc) < 0: raise ValueError("invalid masses or stiffnesses")
    if duration <= 0 or dt <= 0: raise ValueError("duration and dt must be positive")
    M,K,Phi,omega = _mass_normal_modes(m1,m2,k1,k2,kc)
    x=np.asarray(initial_x,dtype=float).reshape(2); v=np.asarray(initial_v,dtype=float).reshape(2)
    # Phi^T M Phi = I, hence q = Phi^T M x.
    def modal(xx,vv):
        q = Phi.T @ M @ xx; qd = Phi.T @ M @ vv
        E = 0.5*qd*qd + 0.5*(omega*omega)*q*q
        return q, qd, E
    def accel(xx): return -np.linalg.solve(M, K@xx)
    total=max(500,min(int(round(duration/dt)),200000)); h=duration/total; a=accel(x)
    times=[]; modal_f=[]; phys1=[]; phys2=[]; exchange=[]; max_transfer=0.0
    e0_total = 0.5*v@M@v + 0.5*x@K@x
    for step in range(total+1):
        if step % max(1,total//4000)==0:
            q,qd,Em=modal(x,v); Et=max(float(np.sum(Em)),1e-30)
            mf=(Em/Et).astype(float)
            # Assign half coupling spring energy to each physical oscillator for a symmetric transfer diagnostic.
            ec=0.5*kc*(x[0]-x[1])**2
            e1=0.5*m1*v[0]**2+0.5*k1*x[0]**2+0.5*ec
            e2=0.5*m2*v[1]**2+0.5*k2*x[1]**2+0.5*ec
            frac2=float(e2/max(e1+e2,1e-30)); max_transfer=max(max_transfer,frac2)
            times.append(step*h); modal_f.append(mf); phys1.append(float(e1)); phys2.append(float(e2)); exchange.append(frac2)
        if step==total: break
        xn=x+v*h+0.5*a*h*h; an=accel(xn); vn=v+0.5*(a+an)*h; x,v,a=xn,vn,an
    efinal=0.5*v@M@v+0.5*x@K@x
    return _plain({
        "schema":"physical-lab-coupled-modal-energy-v1",
        "normal_mode_omega_rad_s":omega,"mode_shapes_mass_normalized":Phi,
        "time_s":times,"modal_energy_fraction":modal_f,"physical_energy_1":phys1,"physical_energy_2":phys2,
        "oscillator2_energy_fraction":exchange,"max_oscillator2_energy_fraction":max_transfer,
        "relative_total_energy_change":abs(float(efinal-e0_total))/max(abs(float(e0_total)),1e-30),
        "boundary":"Linear conservative two-DOF model. Modal energies are exact for the model's mass-normalized eigenbasis; physical-oscillator energy partition uses a symmetric half-coupling convention and is a diagnostic, not a unique observable decomposition."
    })


def coupled_detuning_scan(
    *, detunings: Iterable[float] = (-0.5,-0.3,-0.15,0.0,0.15,0.3,0.5), coupling_k: float = 0.12,
    base_ground_k: float = 1.0, duration: float = 160.0, dt: float = 0.025,
) -> dict[str, Any]:
    rows=[]
    for d in [float(x) for x in detunings]:
        k2=float(base_ground_k)*(1.0+d)
        if k2 <= 0: continue
        r=coupled_modal_energy_transfer(ground_k1=float(base_ground_k),ground_k2=k2,coupling_k=float(coupling_k),duration=float(duration),dt=float(dt))
        rows.append({"relative_detuning":d,"ground_k2":k2,"max_energy_transfer_to_oscillator2":r["max_oscillator2_energy_fraction"],"omega1":r["normal_mode_omega_rad_s"][0],"omega2":r["normal_mode_omega_rad_s"][1]})
    if len(rows)<3: raise ValueError("need at least three valid detuning points")
    best=max(rows,key=lambda x:x["max_energy_transfer_to_oscillator2"])
    return _plain({"schema":"physical-lab-coupled-detuning-v1","rows":rows,"best_detuning":best["relative_detuning"],"best_transfer_fraction":best["max_energy_transfer_to_oscillator2"],"boundary":"Finite-time transfer efficiency in an ideal linear two-oscillator model. The optimum depends on the observation window, initial condition and coupling; it is not a universal resonance criterion."})


def bootstrap_mean_uncertainty(
    *, sample_size: int = 200, bootstrap_replicates: int = 1500, seed: int = 20260911,
) -> dict[str, Any]:
    np=_np(); n=max(30,min(int(sample_size),5000)); B=max(200,min(int(bootstrap_replicates),10000)); rng=np.random.default_rng(int(seed))
    # Bounded beta-like sample with known analytic mean 2/(2+5)=2/7.
    x=rng.beta(2.0,5.0,size=n); estimate=float(np.mean(x)); truth=2.0/7.0
    boot=np.empty(B,dtype=float)
    for b in range(B): boot[b]=float(np.mean(x[rng.integers(0,n,size=n)]))
    lo,hi=np.quantile(boot,[0.025,0.975]); se=float(np.std(boot,ddof=1))
    return _plain({"schema":"physical-lab-bootstrap-mean-v1","sample_size":n,"bootstrap_replicates":B,"estimate":estimate,"analytic_reference":truth,"bootstrap_standard_error":se,"percentile_95_interval":[float(lo),float(hi)],"reference_inside_interval":bool(lo<=truth<=hi),"boundary":"Nonparametric bootstrap uncertainty for one finite bounded sample. The percentile interval is a finite-sample diagnostic, not guaranteed exact coverage for arbitrary estimators or distributions."})


def gaussian_tail_importance_sampling(
    *, threshold: float = 4.0, samples: int = 50000, replicates: int = 20, proposal_mean: float | None = None, seed: int = 20260911,
) -> dict[str, Any]:
    np=_np(); a=float(threshold); n=max(1000,min(int(samples),500000)); reps=max(6,min(int(replicates),80)); mu=float(a if proposal_mean is None else proposal_mean)
    if not (1.5 <= a <= 7.0): raise ValueError("threshold must be in [1.5,7]")
    # Exact standard-normal upper-tail probability.
    reference=0.5*math.erfc(a/math.sqrt(2.0)); crude=[]; imp=[]
    for r in range(reps):
        rng=np.random.default_rng(int(seed)+7919*r)
        z=rng.normal(size=n); crude.append(float(np.mean(z>a)))
        y=rng.normal(loc=mu,scale=1.0,size=n)
        # phi(y)/phi(y-mu) = exp(-mu*y + mu^2/2)
        w=np.exp(-mu*y+0.5*mu*mu)
        imp.append(float(np.mean((y>a)*w)))
    def stats(vals):
        arr=np.asarray(vals,dtype=float); mean=float(np.mean(arr)); sd=float(np.std(arr,ddof=1)); rel=sd/max(reference,1e-300)
        return {"mean":mean,"replicate_std":sd,"relative_replicate_std_vs_reference":rel,"abs_bias":abs(mean-reference)}
    cs=stats(crude); ins=stats(imp)
    improvement=cs["replicate_std"]/max(ins["replicate_std"],1e-300)
    return _plain({"schema":"physical-lab-gaussian-tail-importance-v1","threshold_sigma":a,"samples_per_replicate":n,"replicates":reps,"proposal_mean":mu,"analytic_reference_probability":reference,"crude_mc":cs,"importance_sampling":ins,"std_reduction_factor":improvement,"boundary":"Importance sampling comparison for one Gaussian upper-tail event and one shifted-normal proposal. Variance reduction is proposal- and event-specific; this is not a universal rare-event guarantee."})
