"""Fourth-wave non-accelerator model-depth studies for Physical Lab.

Adds:
- Sun-Jupiter-Saturn secular diagnostics from osculating eccentricity vectors.
- Linear-system conditioning / residual-vs-solution-error experiments.
- Stiff ODE explicit-vs-implicit solver comparison against an analytic reference.
- Long-time harmonic-oscillator comparison of velocity-Verlet and RK4 energy behavior.

All studies are bounded numerical diagnostics, not observational or experimental validation.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


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
        try:
            return _plain(v.item())
        except Exception:
            pass
    return v


def _eccentricity_vector(r, v, mu: float):
    np = _np()
    rr = np.asarray(r, dtype=float); vv = np.asarray(v, dtype=float)
    rn = float(np.linalg.norm(rr))
    if rn <= 0:
        return np.full(3, np.nan)
    h = np.cross(rr, vv)
    return np.cross(vv, h) / float(mu) - rr / rn


def _slow_spectrum(time, values) -> dict[str, Any]:
    np = _np()
    t = np.asarray(time, dtype=float); y = np.asarray(values, dtype=float)
    mask = np.isfinite(t) & np.isfinite(y)
    t = t[mask]; y = y[mask]
    if len(t) < 64:
        return {"dominant_frequency_per_year": None, "dominant_period_years": None}
    dt = float(np.median(np.diff(t)))
    yc = y - np.mean(y)
    # Remove linear secular trend before looking for bounded modulation.
    x = t - np.mean(t)
    denom = float(np.dot(x, x))
    if denom > 0:
        yc = yc - (float(np.dot(x, yc)) / denom) * x
    win = np.hanning(len(yc))
    spec = np.abs(np.fft.rfft(yc * win)) ** 2
    freq = np.fft.rfftfreq(len(yc), d=dt)
    if len(spec) <= 1:
        return {"dominant_frequency_per_year": None, "dominant_period_years": None}
    spec[0] = 0.0
    peak = int(np.argmax(spec))
    f = float(freq[peak])
    return {
        "dominant_frequency_per_year": f,
        "dominant_period_years": None if f <= 0 else 1.0 / f,
        "frequency_per_year": freq,
        "power_normalized": spec / max(float(np.max(spec)), 1e-30),
    }


def solar_secular_dynamics(
    *, duration_years: float = 180.0, samples: int = 3600,
    inclination_jupiter_deg: float = 2.0, solar_1pn: bool = False,
) -> dict[str, Any]:
    """Extract slow orbital signatures from the existing Sun-Jupiter-Saturn model."""
    np = _np(); import physical_lab_solar_system_dynamics as solar
    duration = float(duration_years)
    if not (40.0 <= duration <= 600.0):
        raise ValueError("duration_years must be in [40,600]")
    n = max(800, min(int(samples), 12000))
    cfg = solar.SolarSystemConfig(
        duration_years=duration, samples=n,
        inclination_jupiter_deg=float(inclination_jupiter_deg),
        saturn_inclination_factor=0.25, saturn_backreaction=True,
        solar_1pn=bool(solar_1pn), velocity_cross=False, radial_drag=False,
        rtol=1e-10, atol=1e-12, max_step_years=0.03,
    )
    result = solar.integrate_case(cfg)
    t = np.asarray(result["time_years"], dtype=float)
    r = np.asarray(result["positions_AU"], dtype=float)
    v = np.asarray(result["velocities_AU_per_yr"], dtype=float)
    rel_j_r = r[:,1]-r[:,0]; rel_j_v = v[:,1]-v[:,0]
    rel_s_r = r[:,2]-r[:,0]; rel_s_v = v[:,2]-v[:,0]
    mu_j = solar.G * (solar.M_SUN + solar.M_JUPITER)
    mu_s = solar.G * (solar.M_SUN + solar.M_SATURN)
    ej = np.asarray([_eccentricity_vector(rr,vv,mu_j) for rr,vv in zip(rel_j_r,rel_j_v)])
    es = np.asarray([_eccentricity_vector(rr,vv,mu_s) for rr,vv in zip(rel_s_r,rel_s_v)])
    ej_mag = np.linalg.norm(ej,axis=1); es_mag = np.linalg.norm(es,axis=1)
    # Projected longitude of eccentricity vector in the model's reference x-y plane.
    varpi_j = np.unwrap(np.arctan2(ej[:,1],ej[:,0]))
    varpi_s = np.unwrap(np.arctan2(es[:,1],es[:,0]))
    dvarpi = np.unwrap(varpi_s-varpi_j)

    def slope(rad):
        x=t-np.mean(t); y=np.asarray(rad)-np.mean(rad)
        return float(np.dot(x,y)/max(float(np.dot(x,x)),1e-30))

    diag = result["diagnostics"]
    ratio = np.asarray(diag["period_ratio_saturn_over_jupiter"],dtype=float)
    dev = ratio-2.5
    j_spec = _slow_spectrum(t,ej_mag)
    s_spec = _slow_spectrum(t,es_mag)
    dev_spec = _slow_spectrum(t,dev)
    return _plain({
        "schema":"physical-lab-solar-secular-v1",
        "time_years":t,
        "jupiter_eccentricity":ej_mag,
        "saturn_eccentricity":es_mag,
        "jupiter_projected_varpi_deg":np.degrees(varpi_j),
        "saturn_projected_varpi_deg":np.degrees(varpi_s),
        "relative_projected_apsidal_angle_deg":np.degrees(dvarpi),
        "jupiter_projected_apsidal_rate_deg_per_year":math.degrees(slope(varpi_j)),
        "saturn_projected_apsidal_rate_deg_per_year":math.degrees(slope(varpi_s)),
        "relative_apsidal_rate_deg_per_year":math.degrees(slope(dvarpi)),
        "period_ratio_saturn_over_jupiter":ratio,
        "resonance_deviation_5_2":dev,
        "jupiter_eccentricity_slow_spectrum":j_spec,
        "saturn_eccentricity_slow_spectrum":s_spec,
        "five_two_deviation_slow_spectrum":dev_spec,
        "relative_energy_drift":diag.get("relative_energy_drift"),
        "boundary":(
            "Secular diagnostics are extracted from the simplified three-body Physical Lab model. "
            "Projected apsidal angles use the model x-y reference plane; low-frequency peaks are finite-window signatures, "
            "not JPL ephemerides or a precision reconstruction of the Jupiter-Saturn Great Inequality."
        ),
    })


def conditioning_study(*, sizes: Iterable[int] = (5,8,12), perturbation: float = 1e-10) -> dict[str, Any]:
    """Compare residual and solution sensitivity for Hilbert-like ill-conditioned systems."""
    np = _np(); rows=[]; eps=float(perturbation)
    if not (1e-14 <= eps <= 1e-4):
        raise ValueError("perturbation must be in [1e-14,1e-4]")
    for raw_n in sizes:
        n=int(raw_n)
        if not (3 <= n <= 16):
            raise ValueError("sizes must lie in [3,16]")
        i=np.arange(n)[:,None]; j=np.arange(n)[None,:]
        A=1.0/(i+j+1.0)
        x_true=np.ones(n)
        b=A@x_true
        x=np.linalg.solve(A,b)
        perturb=np.zeros(n); perturb[-1]=eps*max(float(np.linalg.norm(b)),1.0)
        xp=np.linalg.solve(A,b+perturb)
        residual=float(np.linalg.norm(A@x-b)/np.linalg.norm(b))
        rel_error=float(np.linalg.norm(x-x_true)/np.linalg.norm(x_true))
        rhs_rel=float(np.linalg.norm(perturb)/np.linalg.norm(b))
        sol_rel=float(np.linalg.norm(xp-x)/max(float(np.linalg.norm(x)),1e-30))
        rows.append({
            "n":n,"condition_2":float(np.linalg.cond(A,2)),
            "relative_residual":residual,"relative_solution_error":rel_error,
            "rhs_relative_perturbation":rhs_rel,"solution_relative_change":sol_rel,
            "amplification":sol_rel/max(rhs_rel,1e-30),
        })
    return _plain({
        "schema":"physical-lab-conditioning-v1","rows":rows,
        "boundary":"Small residual does not imply a small forward solution error for ill-conditioned systems. Condition number provides a worst-case sensitivity scale, not a guarantee that every perturbation is maximally amplified."
    })


def stiff_ode_comparison(*, stiffness: float = 1000.0, duration: float = 8.0) -> dict[str, Any]:
    """Compare RK45, Radau and BDF on y'=-lambda(y-cos t)-sin t, exact y=cos t."""
    np=_np(); from scipy.integrate import solve_ivp
    lam=float(stiffness); end=float(duration)
    if not (10 <= lam <= 1e6) or not (1 <= end <= 50):
        raise ValueError("stiffness or duration outside supported range")
    def rhs(t,y): return [-lam*(y[0]-math.cos(t))-math.sin(t)]
    t_eval=np.linspace(0,end,600); rows=[]
    for method in ("RK45","Radau","BDF"):
        sol=solve_ivp(rhs,(0,end),[1.0],method=method,t_eval=t_eval,rtol=1e-7,atol=1e-9)
        err=float(np.max(np.abs(sol.y[0]-np.cos(sol.t))))
        rows.append({"method":method,"success":bool(sol.success),"nfev":int(sol.nfev),"njev":int(getattr(sol,"njev",0)),"nlu":int(getattr(sol,"nlu",0)),"max_abs_error":err})
    return _plain({
        "schema":"physical-lab-stiff-ode-v1","stiffness_lambda":lam,"duration":end,"rows":rows,
        "boundary":"This analytically soluble scalar relaxation problem isolates stiffness-related work. Solver evaluation counts on one problem do not establish universal method rankings."
    })


def long_time_oscillator_integrators(*, periods: int = 600, dt: float = 0.08) -> dict[str, Any]:
    """Compare velocity-Verlet with classical RK4 on x''=-x over many periods."""
    np=_np(); p=max(50,min(int(periods),3000)); h=float(dt)
    if not (0.005 <= h <= 0.3): raise ValueError("dt must be in [0.005,0.3]")
    total=2*math.pi*p; steps=int(round(total/h)); h=total/steps
    stride=max(1,steps//4000)
    def energy(x,v): return 0.5*(x*x+v*v)
    # Verlet
    xv=1.0; vv=0.0; ev=[]; tv=[]
    # RK4 first-order state
    xr=1.0; vr=0.0; er=[]
    e0=0.5
    for k in range(steps+1):
        if k%stride==0 or k==steps:
            tv.append(k*h); ev.append((energy(xv,vv)-e0)/e0); er.append((energy(xr,vr)-e0)/e0)
        if k==steps: break
        vhalf=vv-0.5*h*xv; xv=xv+h*vhalf; vv=vhalf-0.5*h*xv
        def f(x,v): return v,-x
        k1x,k1v=f(xr,vr); k2x,k2v=f(xr+.5*h*k1x,vr+.5*h*k1v); k3x,k3v=f(xr+.5*h*k2x,vr+.5*h*k2v); k4x,k4v=f(xr+h*k3x,vr+h*k3v)
        xr += h*(k1x+2*k2x+2*k3x+k4x)/6; vr += h*(k1v+2*k2v+2*k3v+k4v)/6
    return _plain({
        "schema":"physical-lab-long-time-integrators-v1","periods":p,"dt":h,"time":tv,
        "verlet_relative_energy_error":ev,"rk4_relative_energy_error":er,
        "verlet_max_abs_relative_energy_error":max(abs(x) for x in ev),
        "rk4_max_abs_relative_energy_error":max(abs(x) for x in er),
        "verlet_final_relative_energy_error":ev[-1],"rk4_final_relative_energy_error":er[-1],
        "boundary":"The unit harmonic oscillator is a structural long-time benchmark. Velocity-Verlet is symplectic and typically shows bounded oscillatory energy error; RK4 can be more accurate per step yet is not symplectic. This benchmark is not a universal solver ranking."
    })
