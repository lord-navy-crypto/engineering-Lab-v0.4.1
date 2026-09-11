"""Advanced science studies for Physical Lab's remaining model families.

This module strengthens four model families without duplicating existing campaign
infrastructure:

- Ising: finite-size temperature sweeps with heat capacity, susceptibility and
  Binder cumulant diagnostics.
- Random Walk / QMC: first-passage survival statistics and MC vs scrambled-Sobol
  convergence for a bounded reference integral.
- Nonlinear Dynamics: Duffing stroboscopic bifurcation-style sweep across drive
  amplitude, including branch-count and finite-time divergence diagnostics.
- Oscillation / Integration: coupled two-DOF modal dynamics with analytic normal
  mode frequencies and time-domain beating verification.

All studies are bounded computational evidence, not experimental validation.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


def _np():
    import numpy as np
    return np


def _plain(value: Any) -> Any:
    np = _np()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except Exception:
            pass
    return value


# ---------------------------------------------------------------------------
# Ising finite-size thermodynamics
# ---------------------------------------------------------------------------

def _ising_sweep(spins, beta: float, rng) -> None:
    L = int(spins.shape[0])
    for _ in range(L * L):
        i = int(rng.integers(L)); j = int(rng.integers(L))
        nn = spins[(i + 1) % L, j] + spins[(i - 1) % L, j] + spins[i, (j + 1) % L] + spins[i, (j - 1) % L]
        de = 2 * spins[i, j] * nn
        if de <= 0 or rng.random() < math.exp(-beta * de):
            spins[i, j] *= -1


def _ising_observables(spins) -> tuple[float, float]:
    np = _np(); s = np.asarray(spins, dtype=int); n = s.size
    energy = -float(np.sum(s * (np.roll(s, 1, axis=0) + np.roll(s, 1, axis=1)))) / n
    magnetization = float(np.mean(s))
    return energy, magnetization


def ising_finite_size_scan(
    *, sizes: Iterable[int] = (8, 12, 16), temperatures: Iterable[float] = (1.8, 2.0, 2.15, 2.25, 2.269, 2.35, 2.5, 2.8),
    burn_sweeps: int = 250, sample_sweeps: int = 700, thin: int = 2, seed: int = 20260911,
) -> dict[str, Any]:
    np = _np()
    sizes = sorted({int(v) for v in sizes})
    temps = sorted({float(v) for v in temperatures})
    if not sizes or min(sizes) < 4 or max(sizes) > 48:
        raise ValueError("Ising sizes must lie in [4,48]")
    if len(temps) < 4 or min(temps) <= 0:
        raise ValueError("provide at least four positive temperatures")
    burn = max(50, min(int(burn_sweeps), 3000)); samples = max(100, min(int(sample_sweeps), 5000)); thin = max(1, min(int(thin), 20))
    rows: list[dict[str, Any]] = []
    for li, L in enumerate(sizes):
        for ti, temperature in enumerate(temps):
            rng = np.random.default_rng(int(seed) + 1009 * li + 9176 * ti)
            spins = rng.choice(np.asarray([-1, 1], dtype=int), size=(L, L))
            beta = 1.0 / temperature
            for _ in range(burn):
                _ising_sweep(spins, beta, rng)
            energies: list[float] = []; mags: list[float] = []
            for _ in range(samples):
                for __ in range(thin): _ising_sweep(spins, beta, rng)
                e, m = _ising_observables(spins); energies.append(e); mags.append(m)
            e = np.asarray(energies, dtype=float); m = np.asarray(mags, dtype=float); n = L * L
            mean_e = float(np.mean(e)); mean_abs_m = float(np.mean(np.abs(m)))
            heat_capacity = float(n * (np.mean(e * e) - np.mean(e) ** 2) / (temperature ** 2))
            susceptibility = float(n * (np.mean(m * m) - np.mean(np.abs(m)) ** 2) / temperature)
            m2 = float(np.mean(m * m)); m4 = float(np.mean(m ** 4))
            binder = 1.0 - m4 / max(3.0 * m2 * m2, 1e-15)
            rows.append({
                "L": L, "temperature": temperature, "mean_energy_per_spin": mean_e,
                "mean_abs_magnetization": mean_abs_m, "heat_capacity_per_spin": heat_capacity,
                "susceptibility_per_spin": susceptibility, "binder_cumulant": float(binder),
            })
    by_size: dict[int, list[dict[str, Any]]] = {L: [r for r in rows if r["L"] == L] for L in sizes}
    peaks = []
    for L in sizes:
        peak_c = max(by_size[L], key=lambda r: r["heat_capacity_per_spin"])
        peak_x = max(by_size[L], key=lambda r: r["susceptibility_per_spin"])
        peaks.append({"L": L, "heat_capacity_peak_temperature": peak_c["temperature"], "susceptibility_peak_temperature": peak_x["temperature"]})
    crossing_candidates: list[dict[str, Any]] = []
    for a, b in zip(sizes[:-1], sizes[1:]):
        da = {r["temperature"]: r["binder_cumulant"] for r in by_size[a]}; db = {r["temperature"]: r["binder_cumulant"] for r in by_size[b]}
        common = sorted(set(da).intersection(db))
        if common:
            t = min(common, key=lambda x: abs(da[x] - db[x]))
            crossing_candidates.append({"sizes": [a, b], "temperature": t, "binder_gap": abs(da[t] - db[t])})
    return _plain({
        "schema": "physical-lab-ising-finite-size-v1", "rows": rows, "peaks": peaks,
        "binder_crossing_candidates": crossing_candidates,
        "onsager_critical_temperature_reduced": 2.0 / math.log(1.0 + math.sqrt(2.0)),
        "boundary": "Finite Metropolis samples on small periodic lattices. Peak locations and Binder crossings are finite-size diagnostics, not an infinite-volume critical-point proof.",
    })


# ---------------------------------------------------------------------------
# Random walk first-passage and QMC convergence
# ---------------------------------------------------------------------------

def random_walk_first_passage(
    *, walkers: int = 8000, boundary_radius: float = 12.0, max_steps: int = 1500, seed: int = 20260911,
) -> dict[str, Any]:
    np = _np(); n = max(500, min(int(walkers), 100000)); steps = max(20, min(int(max_steps), 20000)); radius = float(boundary_radius)
    if radius <= 1.0: raise ValueError("boundary_radius must exceed 1")
    rng = np.random.default_rng(int(seed)); x = np.zeros(n, dtype=int); y = np.zeros(n, dtype=int)
    alive = np.ones(n, dtype=bool); hit = np.full(n, -1, dtype=int); checkpoints = sorted(set([1, 5, 10, 20, 50, 100, 200, 500, 1000, steps]))
    survival: list[dict[str, Any]] = []
    r2_limit = radius * radius
    for step in range(1, steps + 1):
        idx = np.where(alive)[0]
        if idx.size:
            directions = rng.integers(0, 4, size=idx.size)
            x[idx] += (directions == 0).astype(int) - (directions == 1).astype(int)
            y[idx] += (directions == 2).astype(int) - (directions == 3).astype(int)
            newly = idx[(x[idx] * x[idx] + y[idx] * y[idx]) >= r2_limit]
            hit[newly] = step; alive[newly] = False
        if step in checkpoints:
            survival.append({"step": step, "survival_fraction": float(np.mean(alive)), "hit_fraction": float(np.mean(hit >= 0))})
    observed = hit[hit >= 0]
    return _plain({
        "schema": "physical-lab-random-walk-first-passage-v1", "walkers": n, "boundary_radius": radius,
        "max_steps": steps, "survival_curve": survival, "hit_fraction": float(np.mean(hit >= 0)),
        "median_first_passage_step": None if observed.size == 0 else float(np.median(observed)),
        "mean_first_passage_step_conditional": None if observed.size == 0 else float(np.mean(observed)),
        "boundary": "Discrete 2-D nearest-neighbor walk with a radial absorbing boundary. Conditional first-passage summaries exclude walkers that did not hit by max_steps.",
    })


def qmc_convergence_study(*, powers: Iterable[int] = (6, 7, 8, 9, 10, 11), replicates: int = 10, seed: int = 20260911) -> dict[str, Any]:
    np = _np(); from scipy.stats import qmc
    pows = sorted({int(v) for v in powers}); reps = max(4, min(int(replicates), 40))
    if not pows or min(pows) < 4 or max(pows) > 18: raise ValueError("powers must lie in [4,18]")
    # Integral of exp(-(x^2+y^2)) over [0,1]^2; separable analytic reference.
    reference = (0.5 * math.sqrt(math.pi) * math.erf(1.0)) ** 2
    rows: list[dict[str, Any]] = []
    for p in pows:
        n = 1 << p; mc_errors = []; qmc_errors = []
        for rep in range(reps):
            rng = np.random.default_rng(int(seed) + 313 * p + rep)
            xy = rng.random((n, 2)); vals = np.exp(-np.sum(xy * xy, axis=1)); mc_errors.append(abs(float(np.mean(vals)) - reference))
            sobol = qmc.Sobol(d=2, scramble=True, seed=int(seed) + 10007 * p + rep)
            qxy = sobol.random_base2(m=p); qvals = np.exp(-np.sum(qxy * qxy, axis=1)); qmc_errors.append(abs(float(np.mean(qvals)) - reference))
        rows.append({
            "samples": n, "mc_median_abs_error": float(np.median(mc_errors)), "qmc_median_abs_error": float(np.median(qmc_errors)),
            "mc_p90_abs_error": float(np.quantile(mc_errors, 0.9)), "qmc_p90_abs_error": float(np.quantile(qmc_errors, 0.9)),
            "median_improvement_factor": float(np.median(mc_errors) / max(float(np.median(qmc_errors)), 1e-18)),
        })
    def slope(key: str) -> float:
        x = np.log([r["samples"] for r in rows]); y = np.log([max(r[key], 1e-18) for r in rows]); xc = x - np.mean(x)
        return float(np.dot(xc, y - np.mean(y)) / np.dot(xc, xc))
    return _plain({
        "schema": "physical-lab-qmc-convergence-v1", "reference_integral": reference, "rows": rows,
        "mc_loglog_error_slope": slope("mc_median_abs_error"), "qmc_loglog_error_slope": slope("qmc_median_abs_error"),
        "boundary": "Scrambled Sobol and ordinary Monte Carlo are compared on one smooth two-dimensional integral. This finite benchmark does not establish universal QMC superiority.",
    })


# ---------------------------------------------------------------------------
# Duffing stroboscopic bifurcation-style sweep
# ---------------------------------------------------------------------------

def _rk4_step(rhs, t: float, state, dt: float):
    np = _np(); y = np.asarray(state, dtype=float)
    k1 = np.asarray(rhs(t, y)); k2 = np.asarray(rhs(t + 0.5*dt, y + 0.5*dt*k1)); k3 = np.asarray(rhs(t + 0.5*dt, y + 0.5*dt*k2)); k4 = np.asarray(rhs(t + dt, y + dt*k3))
    return y + dt * (k1 + 2*k2 + 2*k3 + k4) / 6.0


def duffing_bifurcation_sweep(
    *, amplitudes: Iterable[float] = tuple(round(0.18 + 0.02*i, 3) for i in range(18)), omega: float = 1.2,
    damping: float = 0.1, steps_per_period: int = 72, settle_periods: int = 100, sample_periods: int = 48,
) -> dict[str, Any]:
    np = _np(); amps = [float(v) for v in amplitudes]
    if len(amps) < 5 or min(amps) < 0 or max(amps) > 1.5: raise ValueError("provide at least five amplitudes in [0,1.5]")
    w = float(omega); z = float(damping); ppp = max(32, min(int(steps_per_period), 240)); settle = max(20, min(int(settle_periods), 500)); samples = max(12, min(int(sample_periods), 120))
    if w <= 0 or z < 0: raise ValueError("omega must be positive and damping nonnegative")
    period = 2.0 * math.pi / w; dt = period / ppp; rows = []
    for amp in amps:
        def rhs(t, state):
            x, v = state; return np.asarray([v, amp * math.cos(w*t) - 2.0*z*v + x - x**3], dtype=float)
        state = np.asarray([0.1, 0.0], dtype=float); t = 0.0; strobes = []
        total_periods = settle + samples
        for period_index in range(total_periods):
            for _ in range(ppp): state = _rk4_step(rhs, t, state, dt); t += dt
            if period_index >= settle: strobes.append(float(state[0]))
        arr = np.asarray(strobes); scale = max(float(np.std(arr)), 1e-6); tol = max(2e-3, 0.03 * scale)
        centers: list[float] = []
        for value in sorted(arr.tolist()):
            if not centers or abs(value - centers[-1]) > tol: centers.append(value)
            else: centers[-1] = 0.5 * (centers[-1] + value)
        # Nearby-initial-condition finite-time stroboscopic separation.
        s1 = np.asarray([0.1, 0.0]); s2 = np.asarray([0.1000001, 0.0]); tt = 0.0
        for _ in range(30 * ppp): s1 = _rk4_step(rhs, tt, s1, dt); s2 = _rk4_step(rhs, tt, s2, dt); tt += dt
        separation_gain = float(np.linalg.norm(s2 - s1) / 1e-7)
        rows.append({"drive_amplitude": amp, "stroboscopic_x": strobes, "resolved_branch_count": len(centers), "stroboscopic_std": float(np.std(arr)), "nearby_state_separation_gain": separation_gain})
    return _plain({
        "schema": "physical-lab-duffing-bifurcation-v1", "omega_rad_s": w, "rows": rows,
        "max_resolved_branch_count": max(r["resolved_branch_count"] for r in rows),
        "max_nearby_state_separation_gain": max(r["nearby_state_separation_gain"] for r in rows),
        "boundary": "Finite stroboscopic continuation-like sweep. Resolved branch count depends on settling, sampling window and clustering tolerance; it is not a complete bifurcation proof or universal chaos classifier.",
    })


# ---------------------------------------------------------------------------
# Coupled two-DOF modal oscillator
# ---------------------------------------------------------------------------

def coupled_mode_study(
    *, mass1: float = 1.0, mass2: float = 1.0, ground_k1: float = 1.0, ground_k2: float = 1.0,
    coupling_k: float = 0.12, duration: float = 180.0, dt: float = 0.02,
) -> dict[str, Any]:
    np = _np(); m1 = float(mass1); m2 = float(mass2); k1 = float(ground_k1); k2 = float(ground_k2); kc = float(coupling_k)
    if min(m1,m2) <= 0 or min(k1,k2,kc) < 0: raise ValueError("masses must be positive and stiffnesses nonnegative")
    M = np.diag([m1,m2]); K = np.asarray([[k1+kc,-kc],[-kc,k2+kc]], dtype=float)
    evals, evecs = np.linalg.eig(np.linalg.solve(M,K)); order = np.argsort(evals); evals = np.real(evals[order]); evecs = np.real(evecs[:,order]); omega = np.sqrt(np.maximum(evals,0.0))
    total = max(1000, min(int(round(float(duration)/float(dt))), 200000)); dt = float(duration)/total
    x = np.asarray([1.0,0.0], dtype=float); v = np.zeros(2); times=[]; x1=[]; x2=[]; energy=[]
    def accel(xx): return -np.linalg.solve(M, K @ xx)
    a = accel(x)
    for step in range(total+1):
        if step % max(1,total//5000) == 0:
            times.append(step*dt); x1.append(float(x[0])); x2.append(float(x[1])); energy.append(float(0.5*v@M@v + 0.5*x@K@x))
        if step == total: break
        xn = x + v*dt + 0.5*a*dt*dt; an = accel(xn); vn = v + 0.5*(a+an)*dt; x,v,a = xn,vn,an
    e = np.asarray(energy); beat = abs(float(omega[1]-omega[0])); beat_period = None if beat <= 1e-15 else 2.0*math.pi/beat
    return _plain({
        "schema": "physical-lab-coupled-modes-v1", "normal_mode_omega_rad_s": omega, "mode_shapes": evecs,
        "beat_angular_frequency_rad_s": beat, "beat_period_s": beat_period, "time_s": times, "x1": x1, "x2": x2,
        "relative_energy_drift_max": float(np.max(np.abs(e-e[0]))/max(abs(float(e[0])),1e-15)),
        "boundary": "Linear two-degree-of-freedom lumped oscillator with ideal springs and no damping. Normal modes are exact for this model, not a calibrated structural modal test.",
    })
