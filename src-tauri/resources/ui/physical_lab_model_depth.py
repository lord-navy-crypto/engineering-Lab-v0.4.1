"""Third-wave model-depth studies for non-accelerator Physical Lab science.

Adds three bounded studies:
- Ising integrated autocorrelation time / effective sample size.
- Duffing largest finite-time Lyapunov exponent from the tangent variational equation.
- Finite-cell q-resolved dynamic structure factor S(q,omega) for discrete supercell q modes.

These are computational diagnostics, not thermodynamic-limit, chaos-proof, or calibrated-material claims.
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
        try:
            return _plain(v.item())
        except Exception:
            pass
    return v


def integrated_autocorrelation_time(series: Sequence[float], max_lag: int | None = None) -> dict[str, Any]:
    """Estimate tau_int with a positive-sequence truncation of the normalized ACF."""
    np = _np()
    x = np.asarray(series, dtype=float)
    if x.ndim != 1 or len(x) < 64 or not np.all(np.isfinite(x)):
        raise ValueError("series must be finite 1-D data with at least 64 samples")
    x = x - np.mean(x)
    var = float(np.dot(x, x) / len(x))
    if var <= 1e-30:
        return {"tau_int": 0.5, "ess": float(len(x)), "acf": [1.0], "cutoff_lag": 0}
    n = len(x)
    nfft = 1 << (2*n - 1).bit_length()
    f = np.fft.rfft(x, n=nfft)
    acov = np.fft.irfft(f * np.conjugate(f), n=nfft)[:n]
    acov /= np.arange(n, 0, -1)
    acf = acov / acov[0]
    limit = min(n // 4, 1000) if max_lag is None else min(max(1, int(max_lag)), n - 1)
    tau = 0.5
    cutoff = 0
    for lag in range(1, limit + 1):
        rho = float(acf[lag])
        if rho <= 0.0:
            break
        tau += rho
        cutoff = lag
        # Conservative self-consistent window.
        if lag >= 6.0 * tau:
            break
    ess = n / max(2.0 * tau, 1.0)
    keep = min(limit + 1, max(cutoff + 2, 32))
    return _plain({"tau_int": tau, "ess": ess, "acf": acf[:keep], "cutoff_lag": cutoff})


def ising_autocorrelation_scan(
    *, L: int = 16, temperatures: Iterable[float] = (1.8, 2.1, 2.269, 2.4, 2.8),
    burn_sweeps: int = 500, sample_sweeps: int = 1800, seed: int = 20260911,
) -> dict[str, Any]:
    import physical_lab_remaining_science as base
    np = _np()
    L = int(L)
    temps = [float(t) for t in temperatures]
    if not (6 <= L <= 48):
        raise ValueError("L must be in [6,48]")
    if len(temps) < 3 or min(temps) <= 0:
        raise ValueError("provide at least three positive temperatures")
    burn = max(100, min(int(burn_sweeps), 4000))
    samples = max(300, min(int(sample_sweeps), 6000))
    rows = []
    for ti, T in enumerate(temps):
        rng = np.random.default_rng(int(seed) + 7919 * ti)
        spins = rng.choice(np.asarray([-1, 1], dtype=int), size=(L, L))
        beta = 1.0 / T
        for _ in range(burn):
            base._ising_sweep(spins, beta, rng)
        mags = []
        energies = []
        for _ in range(samples):
            base._ising_sweep(spins, beta, rng)
            e, m = base._ising_observables(spins)
            energies.append(e); mags.append(abs(m))
        ma = integrated_autocorrelation_time(mags)
        ea = integrated_autocorrelation_time(energies)
        rows.append({
            "temperature": T,
            "mean_abs_magnetization": float(np.mean(mags)),
            "magnetization_tau_int_sweeps": ma["tau_int"],
            "magnetization_effective_samples": ma["ess"],
            "energy_tau_int_sweeps": ea["tau_int"],
            "energy_effective_samples": ea["ess"],
            "magnetization_acf": ma["acf"],
        })
    peak = max(rows, key=lambda r: r["magnetization_tau_int_sweeps"])
    return _plain({
        "schema": "physical-lab-ising-autocorrelation-v1",
        "L": L, "sample_sweeps": samples, "rows": rows,
        "max_tau_temperature": peak["temperature"],
        "max_magnetization_tau_int_sweeps": peak["magnetization_tau_int_sweeps"],
        "boundary": "Finite single-spin Metropolis chains. Integrated autocorrelation time and ESS quantify serial dependence in these sampled chains; they do not establish asymptotic dynamic critical exponents or independent equilibrium truth.",
    })


def _rk4(rhs, t: float, y, dt: float):
    np = _np(); y = np.asarray(y, dtype=float)
    k1 = np.asarray(rhs(t, y), dtype=float)
    k2 = np.asarray(rhs(t+0.5*dt, y+0.5*dt*k1), dtype=float)
    k3 = np.asarray(rhs(t+0.5*dt, y+0.5*dt*k2), dtype=float)
    k4 = np.asarray(rhs(t+dt, y+dt*k3), dtype=float)
    return y + dt*(k1+2*k2+2*k3+k4)/6.0


def duffing_lyapunov_scan(
    *, amplitudes: Iterable[float] = (0.20,0.24,0.28,0.32,0.36,0.40,0.44,0.48),
    omega: float = 1.2, damping: float = 0.1, steps_per_period: int = 80,
    settle_periods: int = 80, analysis_periods: int = 80,
) -> dict[str, Any]:
    np = _np(); amps = [float(a) for a in amplitudes]
    if len(amps) < 4 or min(amps) < 0 or max(amps) > 1.5:
        raise ValueError("provide at least four amplitudes in [0,1.5]")
    w = float(omega); z = float(damping)
    if w <= 0 or z < 0:
        raise ValueError("omega must be positive and damping nonnegative")
    ppp = max(40, min(int(steps_per_period), 240))
    settle = max(20, min(int(settle_periods), 400))
    analyze = max(20, min(int(analysis_periods), 300))
    period = 2*math.pi/w; dt = period/ppp
    rows = []
    for amp in amps:
        def rhs(t, s):
            x,v,dx,dv = s
            return np.asarray([
                v,
                amp*math.cos(w*t)-2*z*v+x-x**3,
                dv,
                (1.0-3.0*x*x)*dx-2*z*dv,
            ], dtype=float)
        state = np.asarray([0.1,0.0,1.0,0.0], dtype=float)
        t = 0.0
        for _ in range(settle*ppp):
            state = _rk4(rhs,t,state,dt); t += dt
        tangent = state[2:4]
        norm = float(np.linalg.norm(tangent))
        if norm <= 1e-30:
            tangent = np.asarray([1.0,0.0]); norm = 1.0
        state[2:4] = tangent / norm
        log_sum = 0.0
        local = []
        for _ in range(analyze):
            for __ in range(ppp):
                state = _rk4(rhs,t,state,dt); t += dt
            tangent = state[2:4]
            norm = max(float(np.linalg.norm(tangent)), 1e-300)
            local.append(math.log(norm)/period)
            log_sum += math.log(norm)
            state[2:4] = tangent / norm
        ftle = log_sum / (analyze*period)
        rows.append({
            "drive_amplitude": amp,
            "largest_finite_time_lyapunov_per_time": ftle,
            "local_period_exponents": local,
            "classification": "positive-finite-time" if ftle > 1e-3 else ("negative-finite-time" if ftle < -1e-3 else "near-zero-finite-time"),
        })
    return _plain({
        "schema": "physical-lab-duffing-variational-lyapunov-v1",
        "omega_rad_s": w, "damping": z, "rows": rows,
        "max_ftle_per_time": max(r["largest_finite_time_lyapunov_per_time"] for r in rows),
        "boundary": "Largest finite-time exponent from the tangent variational equation of the driven Duffing system at fixed forcing phase. Positive finite-window values are chaos diagnostics, not a rigorous asymptotic proof; convergence should be checked against longer windows and time-step refinement.",
    })


def lattice_dynamic_structure_factor(
    *, nx: int = 4, ny: int = 4, layers: int = 1, steps: int = 2048, dt: float = 0.004,
    velocity_scale: float = 0.03, seed: int = 20260911,
    q_modes: Sequence[Sequence[int]] = ((1,0),(0,1),(1,1),(2,0)), stacking: str = "AA",
) -> dict[str, Any]:
    """Compute finite-cell classical S(q,omega) at allowed supercell reciprocal modes."""
    np = _np(); import physical_lab_lattice_dynamics as lattice
    nsteps = max(512, min(int(steps), 8192)); h = float(dt); scale = float(velocity_scale)
    if not (0.0005 <= h <= 0.02) or not (0 < scale <= 0.2):
        raise ValueError("dt or velocity_scale outside supported range")
    cfg = lattice.LatticeConfig(
        nx=int(nx), ny=int(ny), layers=int(layers), stacking=str(stacking),
        damping=0.0, interlayer_damping=0.0, drive_mode="none", drive_amplitude=0.0,
        stochastic_mode=False, temperature_reduced=0.0, initial_displacement=0.0,
        duration=max(1.0,nsteps*h), samples=nsteps, max_step=h,
    )
    model = lattice.build_lattice(cfg); n = len(model.positions)
    u = np.zeros((n,2),dtype=float)
    rng = np.random.default_rng(int(seed)); v = rng.normal(scale=scale,size=(n,2))
    com = np.sum(model.masses[:,None]*v,axis=0)/float(np.sum(model.masses)); v -= com
    def accel(uu,vv):
        return lattice.force_components(model,uu,vv,0.0,include_dissipation=False,include_external=False)["total"] / model.masses[:,None]
    a = accel(u,v)
    modes = []
    reciprocal = 2.0*math.pi*np.linalg.inv(model.cell).T
    qs = []
    for raw in q_modes:
        if len(raw)!=2: continue
        m1,m2=int(raw[0]),int(raw[1])
        if m1==0 and m2==0: continue
        q = reciprocal @ np.asarray([m1,m2],dtype=float)
        qs.append((m1,m2,q))
    if not qs:
        raise ValueError("provide at least one nonzero integer q mode")
    rho = np.zeros((len(qs),nsteps),dtype=np.complex128)
    energy0 = lattice.potential_energy(model,u) + 0.5*float(np.sum(model.masses[:,None]*v*v))
    max_drift = 0.0
    for step in range(nsteps):
        pos = model.positions + u
        for qi,(_,_,q) in enumerate(qs):
            rho[qi,step] = np.sum(np.exp(-1j*(pos@q))) / math.sqrt(n)
        vhalf = v + 0.5*h*a
        u = u + h*vhalf
        anew = accel(u,vhalf)
        v = vhalf + 0.5*h*anew
        a = anew
        if step % max(1,nsteps//64)==0:
            e = lattice.potential_energy(model,u)+0.5*float(np.sum(model.masses[:,None]*v*v))
            max_drift=max(max_drift,abs(e-energy0)/max(abs(energy0),1e-30))
    freq = np.fft.rfftfreq(nsteps,d=h)
    window = np.hanning(nsteps)
    for qi,(m1,m2,q) in enumerate(qs):
        fluct = rho[qi]-np.mean(rho[qi])
        spec = np.abs(np.fft.rfft(fluct*window))**2
        if len(spec)>0: spec[0]=0.0
        norm = float(np.max(spec)) if np.max(spec)>0 else 1.0
        sn = spec/norm
        peak = int(np.argmax(sn)) if len(sn) else 0
        modes.append({
            "mode_index": [m1,m2], "q_cart": q, "q_magnitude": float(np.linalg.norm(q)),
            "frequency_cycles_per_reduced_time": freq,
            "S_q_omega_normalized": sn,
            "dominant_frequency_cycles_per_reduced_time": float(freq[peak]),
        })
    return _plain({
        "schema": "physical-lab-lattice-dynamic-structure-v1",
        "config": {"nx":int(nx),"ny":int(ny),"layers":int(layers),"steps":nsteps,"dt":h,"seed":int(seed)},
        "modes": modes, "max_relative_energy_drift": max_drift,
        "boundary": "Classical finite-supercell density-fluctuation spectrum at reciprocal vectors allowed by the periodic simulation cell. This is q-resolved S(q,omega) for this reduced-unit model, not neutron/X-ray cross sections, phonon linewidth calibration, or ab-initio material spectroscopy.",
    })
