#!/usr/bin/env python3
"""Serverless native experiment adapters for Engineering Lab.

stdin: JSON object of parameters.
stdout: exactly one JSON result object.
No HTTP server, Streamlit, browser, or iframe is involved.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))

import numpy as np

SCHEMA = "engineering-lab-native-experiment-result/v1"
HC_EV_M = 1.2398419843320026e-6
E_REST_GEV = 0.00051099895


def f(p: dict[str, Any], name: str, default: float, lo: float | None = None, hi: float | None = None) -> float:
    try:
        value = float(p.get(name, default))
    except (TypeError, ValueError):
        value = float(default)
    if not math.isfinite(value):
        value = float(default)
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def i(p: dict[str, Any], name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        value = int(float(p.get(name, default)))
    except (TypeError, ValueError):
        value = int(default)
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def b(p: dict[str, Any], name: str, default: bool = False) -> bool:
    value = p.get(name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def ds(values: Any, limit: int = 900) -> list[float]:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size <= limit:
        return [float(x) for x in arr]
    idx = np.linspace(0, arr.size - 1, limit).astype(int)
    return [float(x) for x in arr[idx]]


def xy_series(
    series_id: str,
    label: str,
    x: Any,
    y: Any,
    *,
    x_label: str,
    y_label: str,
    chart: str = "line",
) -> dict[str, Any]:
    xa = np.asarray(x, dtype=float).reshape(-1)
    ya = np.asarray(y, dtype=float).reshape(-1)
    n = min(len(xa), len(ya))
    xa, ya = xa[:n], ya[:n]
    mask = np.isfinite(xa) & np.isfinite(ya)
    xa, ya = xa[mask], ya[mask]
    if len(xa) > 900:
        idx = np.linspace(0, len(xa) - 1, 900).astype(int)
        xa, ya = xa[idx], ya[idx]
    return {
        "id": series_id,
        "label": label,
        "chart": chart,
        "xLabel": x_label,
        "yLabel": y_label,
        "x": [float(v) for v in xa],
        "y": [float(v) for v in ya],
    }


def clean(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def result(experiment_id: str, backend: str, parameters: dict[str, Any], metrics: dict[str, Any], series: list[dict[str, Any]], boundary: str, tables: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return clean({
        "schema": SCHEMA,
        "experimentId": experiment_id,
        "backend": backend,
        "parameters": parameters,
        "metrics": metrics,
        "series": series,
        "tables": tables or [],
        "boundary": boundary,
    })


def numerical_methods(p: dict[str, Any], mode: str) -> dict[str, Any]:
    xmax = f(p, "xMax", 2.5, 0.2, 8.0)
    order = i(p, "order", 9, 1, 19)
    if order % 2 == 0:
        order -= 1
    points = i(p, "points", 401, 81, 2001)
    x = np.linspace(-xmax, xmax, points)
    approx = np.zeros_like(x)
    for k in range((order + 1) // 2):
        approx += ((-1.0) ** k) * x ** (2 * k + 1) / math.factorial(2 * k + 1)
    exact = np.sin(x)
    err = np.abs(exact - approx)
    orders = list(range(1, order + 1, 2))
    at_x = min(1.5, xmax)
    conv = []
    for n in orders:
        val = sum(((-1.0) ** k) * at_x ** (2 * k + 1) / math.factorial(2 * k + 1) for k in range((n + 1) // 2))
        conv.append(abs(math.sin(at_x) - val))
    return result(
        "numerical-methods",
        "native-numpy-series",
        {"xMax": xmax, "order": order, "points": points},
        {"maxAbsoluteError": float(np.max(err)), "rmsAbsoluteError": float(np.sqrt(np.mean(err * err))), "referenceX": at_x},
        [
            xy_series("approx", f"T{order}(x)", x, approx, x_label="x", y_label="value"),
            xy_series("exact", "sin(x)", x, exact, x_label="x", y_label="value"),
            xy_series("error", "absolute error", x, err, x_label="x", y_label="|error|"),
            xy_series("convergence", "error vs Taylor order", orders, conv, x_label="Taylor order", y_label="absolute error"),
        ],
        "Maclaurin sine-series experiment. Error behavior is specific to the selected function, interval, arithmetic and truncation order; it is not a universal floating-point accuracy guarantee.",
    )


def ising_monte_carlo(p: dict[str, Any], mode: str) -> dict[str, Any]:
    L = i(p, "size", 24, 6, 64)
    temp = f(p, "temperature", 2.269, 0.05, 8.0)
    sweeps = i(p, "sweeps", 160, 20, 1200)
    seed = i(p, "seed", 12345, 0, 2_147_483_647)
    rng = np.random.default_rng(seed)
    spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(L, L))
    beta = 1.0 / temp
    mags, energies, accepts = [], [], []
    accepted_total = 0
    attempts_total = 0

    def energy_per_spin() -> float:
        return float(-np.sum(spins * (np.roll(spins, 1, 0) + np.roll(spins, 1, 1))) / (L * L))

    for sweep in range(sweeps):
        accepted = 0
        for _ in range(L * L):
            r = int(rng.integers(0, L)); c = int(rng.integers(0, L))
            s = int(spins[r, c])
            nn = int(spins[(r + 1) % L, c] + spins[(r - 1) % L, c] + spins[r, (c + 1) % L] + spins[r, (c - 1) % L])
            dE = 2 * s * nn
            if dE <= 0 or rng.random() < math.exp(-beta * dE):
                spins[r, c] = -s
                accepted += 1
        accepted_total += accepted
        attempts_total += L * L
        mags.append(float(np.mean(spins)))
        energies.append(energy_per_spin())
        accepts.append(accepted / (L * L))
    x = np.arange(1, sweeps + 1)
    burn = max(1, sweeps // 3)
    m = np.asarray(mags[burn:])
    e = np.asarray(energies[burn:])
    return result(
        "ising-monte-carlo",
        "native-numpy-metropolis-2d",
        {"size": L, "temperature": temp, "sweeps": sweeps, "seed": seed},
        {
            "meanMagnetization": float(np.mean(m)),
            "meanAbsMagnetization": float(np.mean(np.abs(m))),
            "meanEnergyPerSpin": float(np.mean(e)),
            "acceptanceFraction": accepted_total / max(attempts_total, 1),
            "finalMagnetization": mags[-1],
        },
        [
            xy_series("magnetization", "magnetization", x, mags, x_label="Monte Carlo sweep", y_label="m"),
            xy_series("energy", "energy per spin", x, energies, x_label="Monte Carlo sweep", y_label="E/N"),
            xy_series("acceptance", "acceptance fraction", x, accepts, x_label="Monte Carlo sweep", y_label="accepted / attempted"),
        ],
        "Finite 2-D square-lattice nearest-neighbor Ising Metropolis run with seeded pseudorandom updates. Finite-size, burn-in and autocorrelation matter; one run is not a thermodynamic-limit criticality measurement.",
    )


def random_walk(p: dict[str, Any], mode: str) -> dict[str, Any]:
    steps = i(p, "steps", 400, 20, 5000)
    walkers = i(p, "walkers", 1500, 50, 12000)
    seed = i(p, "seed", 20260919, 0, 2_147_483_647)
    dimension = i(p, "dimension", 2, 1, 3)
    rng = np.random.default_rng(seed)
    pos = np.zeros((walkers, dimension), dtype=float)
    msd = np.zeros(steps + 1, dtype=float)
    mean_r = np.zeros(steps + 1, dtype=float)
    sample_path = np.zeros((steps + 1, dimension), dtype=float)
    for n in range(1, steps + 1):
        axis = rng.integers(0, dimension, size=walkers)
        sign = rng.choice(np.array([-1.0, 1.0]), size=walkers)
        pos[np.arange(walkers), axis] += sign
        sample_path[n] = pos[0]
        r2 = np.sum(pos * pos, axis=1)
        msd[n] = float(np.mean(r2))
        mean_r[n] = float(np.mean(np.sqrt(r2)))
    n = np.arange(steps + 1)
    fit = np.polyfit(n[max(2, steps // 10):], msd[max(2, steps // 10):], 1)
    series = [
        xy_series("msd", "ensemble MSD", n, msd, x_label="steps", y_label="⟨r²⟩"),
        xy_series("mean-radius", "mean radius", n, mean_r, x_label="steps", y_label="⟨r⟩"),
    ]
    if dimension >= 2:
        series.append(xy_series("sample-path", "sample walker path", sample_path[:, 0], sample_path[:, 1], x_label="x", y_label="y", chart="scatter"))
    return result(
        "random-walk-monte-carlo",
        "native-numpy-random-walk",
        {"steps": steps, "walkers": walkers, "dimension": dimension, "seed": seed},
        {"finalMSD": float(msd[-1]), "expectedMSD": float(steps), "msdSlope": float(fit[0]), "relativeFinalError": float(abs(msd[-1] - steps) / max(steps, 1))},
        series,
        "Unbiased lattice random walk with unit steps and a finite seeded ensemble. Monte Carlo variation is expected; agreement of MSD with N is a statistical reference, not proof of RNG quality.",
    )


def _rk4(rhs, state: np.ndarray, t: float, dt: float) -> np.ndarray:
    k1 = np.asarray(rhs(t, state), float)
    k2 = np.asarray(rhs(t + 0.5 * dt, state + 0.5 * dt * k1), float)
    k3 = np.asarray(rhs(t + 0.5 * dt, state + 0.5 * dt * k2), float)
    k4 = np.asarray(rhs(t + dt, state + dt * k3), float)
    return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0


def nonlinear_chaos(p: dict[str, Any], mode: str) -> dict[str, Any]:
    duration = f(p, "duration", 80.0, 5.0, 400.0)
    dt = f(p, "dt", 0.02, 0.001, 0.1)
    damping = f(p, "damping", 0.2, 0.0, 4.0)
    drive = f(p, "drive", 1.2, 0.0, 5.0)
    omega = f(p, "driveOmega", 2.0 / 3.0, 0.05, 5.0)
    theta0 = f(p, "theta0", 0.2, -math.pi, math.pi)
    delta0 = f(p, "perturbation", 1e-7, 1e-12, 1e-2)
    count = min(40000, max(200, int(duration / dt) + 1))
    t = np.linspace(0.0, dt * (count - 1), count)
    a = np.array([theta0, 0.0], float)
    c = np.array([theta0 + delta0, 0.0], float)
    theta = np.zeros(count); velocity = np.zeros(count); sep = np.zeros(count)
    poincare_x, poincare_y = [], []
    period = 2 * math.pi / omega
    next_sample = period

    def rhs(tt: float, y: np.ndarray) -> np.ndarray:
        return np.array([y[1], -damping * y[1] - math.sin(y[0]) + drive * math.cos(omega * tt)])

    for k, tt in enumerate(t):
        theta[k] = a[0]; velocity[k] = a[1]
        sep[k] = float(np.linalg.norm(c - a))
        if tt + 0.5 * dt >= next_sample:
            poincare_x.append(((a[0] + math.pi) % (2 * math.pi)) - math.pi)
            poincare_y.append(a[1])
            next_sample += period
        if k + 1 < count:
            a = _rk4(rhs, a, tt, dt)
            c = _rk4(rhs, c, tt, dt)
    valid = sep[(sep > delta0 * 2) & (sep < 0.2)]
    lyap = None
    if len(valid) >= 5:
        idx = np.where((sep > delta0 * 2) & (sep < 0.2))[0]
        coeff = np.polyfit(t[idx], np.log(sep[idx] / delta0), 1)
        lyap = float(coeff[0])
    series = [
        xy_series("theta", "angle", t, theta, x_label="time", y_label="θ (rad)"),
        xy_series("phase", "phase portrait", theta, velocity, x_label="θ (rad)", y_label="ω (rad/time)", chart="scatter"),
        xy_series("separation", "paired-trajectory separation", t, sep, x_label="time", y_label="phase-space separation"),
    ]
    if len(poincare_x) >= 2:
        series.append(xy_series("poincare", "Poincaré section", poincare_x, poincare_y, x_label="θ mod 2π", y_label="ω", chart="scatter"))
    return result(
        "nonlinear-chaos",
        "native-rk4-driven-pendulum",
        {"duration": duration, "dt": dt, "damping": damping, "drive": drive, "driveOmega": omega, "theta0": theta0, "perturbation": delta0},
        {"maxAbsTheta": float(np.max(np.abs(theta))), "maxAbsVelocity": float(np.max(np.abs(velocity))), "finiteWindowDivergenceRate": lyap, "poincareSamples": len(poincare_x)},
        series,
        "Driven damped pendulum integrated with fixed-step RK4. The finite-window divergence estimate is diagnostic only and is not an asymptotic Lyapunov proof without convergence and renormalization checks.",
    )


def oscillation(p: dict[str, Any], mode: str) -> dict[str, Any]:
    duration = f(p, "duration", 30.0, 1.0, 300.0)
    dt = f(p, "dt", 0.01, 0.0005, 0.1)
    omega0 = f(p, "omega0", 2.0, 0.05, 20.0)
    zeta = f(p, "zeta", 0.08, 0.0, 2.0)
    force = f(p, "force", 0.6, 0.0, 20.0)
    drive_omega = f(p, "driveOmega", 1.6, 0.0, 20.0)
    x0 = f(p, "x0", 1.0, -100.0, 100.0)
    count = min(50000, max(100, int(duration / dt) + 1))
    t = np.linspace(0.0, dt * (count - 1), count)
    state = np.array([x0, 0.0], float)
    x = np.zeros(count); v = np.zeros(count); energy = np.zeros(count)

    def rhs(tt: float, y: np.ndarray) -> np.ndarray:
        return np.array([y[1], force * math.cos(drive_omega * tt) - 2 * zeta * omega0 * y[1] - omega0 * omega0 * y[0]])

    for k, tt in enumerate(t):
        x[k], v[k] = state
        energy[k] = 0.5 * v[k] ** 2 + 0.5 * omega0 ** 2 * x[k] ** 2
        if k + 1 < count:
            state = _rk4(rhs, state, tt, dt)
    tail = x[max(0, count // 2):]
    return result(
        "oscillation-integration",
        "native-rk4-linear-oscillator",
        {"duration": duration, "dt": dt, "omega0": omega0, "zeta": zeta, "force": force, "driveOmega": drive_omega, "x0": x0},
        {"maxAbsDisplacement": float(np.max(np.abs(x))), "rmsTailDisplacement": float(np.sqrt(np.mean(tail * tail))), "finalEnergy": float(energy[-1]), "steps": count - 1},
        [
            xy_series("displacement", "displacement", t, x, x_label="time", y_label="x"),
            xy_series("velocity", "velocity", t, v, x_label="time", y_label="dx/dt"),
            xy_series("phase", "phase portrait", x, v, x_label="x", y_label="dx/dt", chart="scatter"),
            xy_series("energy", "mechanical energy", t, energy, x_label="time", y_label="E"),
        ],
        "Single-degree-of-freedom linearly damped, harmonically forced oscillator integrated with fixed-step RK4. Real structural modes and experimental uncertainty are outside this adapter result.",
    )


def radia_magnet(p: dict[str, Any], mode: str) -> dict[str, Any]:
    period_mm = f(p, "periodMm", 50.0, 1.0, 1000.0)
    b0 = f(p, "b0T", 0.15, 0.0, 20.0)
    periods = i(p, "periods", 20, 1, 500)
    samples = i(p, "samples", 401, 81, 3001)
    z = np.linspace(-period_mm, period_mm, samples)
    by = b0 * np.sin(2 * math.pi * z / period_mm)
    k = 0.934 * b0 * (period_mm / 10.0)
    return result(
        "radia-magnet-studio",
        "native-analytic-safe" if mode != "full" else "native-analytic-full-fallback",
        {"periodMm": period_mm, "b0T": b0, "periods": periods, "samples": samples, "requestedMode": mode},
        {"undulatorK": k, "magneticLengthM": period_mm / 1000 * periods, "peakFieldT": b0},
        [xy_series("field", "ideal on-axis B_y", z, by, x_label="z (mm)", y_label="B_y (T)")],
        "Ideal planar-undulator analytical adapter. It preserves a native no-server workflow but does not replace finite RADIA geometry, material relaxation, fringe fields, manufacturing errors or a 3-D field solve. Full RADIA remains an authoritative backend to be invoked through its solver adapter when available.",
    )


def radiation_platform(p: dict[str, Any], mode: str) -> dict[str, Any]:
    period_mm = f(p, "periodMm", 50.0, 1.0, 1000.0)
    K = f(p, "K", 0.7003, 0.0, 50.0)
    energy_gev = f(p, "energyGeV", 3.0, 0.001, 1000.0)
    harmonic = i(p, "harmonic", 1, 1, 99)
    periods = i(p, "periods", 20, 2, 500)
    gamma = energy_gev / E_REST_GEV
    period_m = period_mm / 1000.0
    theta = np.linspace(0.0, max(0.5, 2.0 / gamma * 1000), 201)
    theta_rad = theta / 1000.0
    lam = period_m * (1 + K * K / 2 + (gamma * theta_rad) ** 2) / (2 * gamma * gamma * harmonic)
    photon = HC_EV_M / lam
    center = float(photon[0])
    ef = np.linspace(center * 0.82, center * 1.18, 801)
    detune = periods * (ef / center - 1.0)
    intensity = np.sinc(detune) ** 2
    return result(
        "radiation-platform",
        "native-analytic-resonance",
        {"periodMm": period_mm, "K": K, "energyGeV": energy_gev, "harmonic": harmonic, "periods": periods, "requestedMode": mode},
        {"lorentzGamma": gamma, "onAxisPhotonEnergyEV": center, "onAxisWavelengthNm": HC_EV_M / center * 1e9, "finiteNRelativeWidth": 1.0 / periods},
        [
            xy_series("angle", "resonance energy vs angle", theta, photon, x_label="observation angle (mrad)", y_label="photon energy (eV)"),
            xy_series("spectrum", "finite-N resonance envelope", ef, intensity, x_label="photon energy (eV)", y_label="relative intensity"),
        ],
        "Ideal planar-undulator resonance/interference adapter. It does not replace the full field-map → trajectory → Liénard-Wiechert radiation workflow, beam effects, optics or detector response.",
    )


def kerr_geodesics(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_kerr_geodesics import KerrOrbitConfig, integrate_case, result_summary, oblate_xyz
    particle = str(p.get("particleType", "massive")).lower()
    cfg = KerrOrbitConfig(
        spin=f(p, "spin", 0.7, 0.0, 0.995),
        inclination_deg=f(p, "inclinationDeg", 25.0, 0.0, 89.0),
        particle_type="photon" if particle == "photon" else "massive",
        periapsis=f(p, "periapsis", 6.5, 2.1, 80.0),
        apoapsis=f(p, "apoapsis", 10.0, 2.2, 150.0),
        lam_max=f(p, "lambdaMax", 16.0, 1.0, 80.0),
        samples=i(p, "samples", 1000, 200, 4000),
        rtol=1e-9,
        atol=1e-11,
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    lam = np.asarray(out["lambda"])
    state = np.asarray(out["state"])
    r = state[1]; theta = state[2]; phi = state[3]
    ox, oy, oz = oblate_xyz(r, theta, phi, cfg.spin)
    return result(
        "kerr-geodesics",
        "physical_lab_kerr_geodesics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("radius", "Boyer-Lindquist radius", lam, r, x_label="Mino parameter λ", y_label="r/M"),
            xy_series("orbit", "oblate x-y trajectory", ox, oy, x_label="x/M", y_label="y/M", chart="scatter"),
            xy_series("polar", "polar angle", lam, np.degrees(theta), x_label="Mino parameter λ", y_label="θ (deg)"),
        ],
        "Kerr geodesic benchmark in geometric units G=c=M=1 using the existing Physical Lab Carter-Mino integrator. Integrability, solver residuals and horizon guards remain part of the interpretation boundary.",
    )


def solar_system(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_solar_system_dynamics import SolarSystemConfig, integrate_case, result_summary
    cfg = SolarSystemConfig(
        duration_years=f(p, "durationYears", 30.0, 0.05, 200.0),
        samples=i(p, "samples", 900, 100, 5000),
        inclination_jupiter_deg=f(p, "inclinationDeg", 10.0, 0.0, 60.0),
        saturn_backreaction=b(p, "saturnBackreaction", True),
        solar_1pn=b(p, "solar1pn", False),
        max_step_years=f(p, "maxStepYears", 0.04, 0.001, 0.5),
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    t = np.asarray(out["time_years"])
    pos = np.asarray(out["positions_AU"])
    diag = out["diagnostics"]
    relj = pos[:, 1] - pos[:, 0]
    rels = pos[:, 2] - pos[:, 0]
    return result(
        "solar-system-dynamics",
        "physical_lab_solar_system_dynamics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("jupiter-orbit", "Jupiter heliocentric path", relj[:, 0], relj[:, 1], x_label="x (AU)", y_label="y (AU)", chart="scatter"),
            xy_series("saturn-orbit", "Saturn heliocentric path", rels[:, 0], rels[:, 1], x_label="x (AU)", y_label="y (AU)", chart="scatter"),
            xy_series("period-ratio", "Saturn/Jupiter period ratio", t, diag["period_ratio_saturn_over_jupiter"], x_label="time (yr)", y_label="T_S/T_J"),
            xy_series("separation", "Jupiter-Saturn separation", t, diag["jupiter_saturn_separation_AU"], x_label="time (yr)", y_label="separation (AU)"),
        ],
        "Barycentric point-mass Sun-Jupiter-Saturn dynamics. The optional solar 1PN term is a bounded central-Sun approximation rather than a complete EIH N-body 1PN model.",
    )


def honeycomb_lattice(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_lattice_dynamics import LatticeConfig, integrate_case, result_summary
    cfg = LatticeConfig(
        nx=i(p, "nx", 3, 2, 7),
        ny=i(p, "ny", 3, 2, 7),
        layers=i(p, "layers", 2, 1, 4),
        stacking=str(p.get("stacking", "ABA")).upper() if str(p.get("stacking", "ABA")).upper() in {"AA", "ABA", "ABC"} else "ABA",
        strain_x=f(p, "strainX", 0.0, -0.2, 0.2),
        damping=f(p, "damping", 0.02, 0.0, 1.0),
        drive_amplitude=f(p, "driveAmplitude", 0.08, 0.0, 1.0),
        drive_frequency=f(p, "driveFrequency", 1.0, 0.01, 10.0),
        duration=f(p, "duration", 8.0, 1.0, 40.0),
        samples=i(p, "samples", 420, 100, 1800),
        max_step=f(p, "maxStep", 0.03, 0.002, 0.1),
    )
    out = integrate_case(cfg)
    summary = result_summary(out)
    t = np.asarray(out["time"])
    analysis = out["analysis"]
    disp = np.asarray(analysis["displacement"])
    site = 0
    return result(
        "honeycomb-lattice",
        "physical_lab_lattice_dynamics.integrate_case",
        clean(cfg.__dict__),
        summary,
        [
            xy_series("site-y", "site-0 y displacement", t, disp[:, site, 1], x_label="time", y_label="u_y"),
            xy_series("energy", "total energy", t, analysis["total_energy"], x_label="time", y_label="E"),
            xy_series("anisotropy", "velocity anisotropy", t, analysis["anisotropy"], x_label="time", y_label="anisotropy"),
            xy_series("layer-ke", "top-layer kinetic energy", t, np.asarray(analysis["layer_kinetic_energy"])[:, -1], x_label="time", y_label="K_layer"),
        ],
        summary["scientific_boundary"],
    )


def utube(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_utube_experiment import critical_speed, threshold, capacity, DEFAULT_R_IN_M, DEFAULT_A_M
    volume = f(p, "volumeMl", 3.0, 0.05, 30.0)
    rpm = f(p, "rpm", 260.0, 1.0, 1000.0)
    rin = f(p, "rinMm", DEFAULT_R_IN_M * 1000, 1.0, 100.0) / 1000.0
    radius = f(p, "radiusMm", DEFAULT_A_M * 1000, 0.1, 50.0) / 1000.0
    nq = i(p, "nq", 48, 12, 128)
    nc = critical_speed(rin, radius)
    ng = threshold(volume, rin=rin, a=radius, nq=nq)
    total, arc, legs = capacity(rpm, rin=rin, a=radius, nq=nq)
    vols = np.linspace(max(0.2, 0.35 * volume), max(6.0, 1.75 * volume), 25)
    thresholds = [threshold(float(v), rin=rin, a=radius, nq=nq) for v in vols]
    return result(
        "utube-studio",
        "physical_lab_utube_experiment",
        {"volumeMl": volume, "rpm": rpm, "rinMm": rin * 1000, "radiusMm": radius * 1000, "nq": nq},
        {"criticalSpeedRpm": nc, "thresholdRpm": ng, "operatingMarginRpm": rpm - ng, "capacityTotalMl": total, "capacityArcMl": arc, "capacityLegsMl": legs},
        [xy_series("threshold", "n_g(V)", vols, thresholds, x_label="volume (mL)", y_label="threshold (rpm)")],
        "Existing deterministic U-tube 3-D-potential model. Numerical convergence does not establish physical validity and theory/measurement agreement is validation evidence rather than proof.",
    )


def kerr_shadow(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_kerr_shadow_sweep import kerr_shadow_morphology_sweep
    spin = f(p, "spin", 0.9, 0.0, 0.98)
    inc = f(p, "inclinationDeg", 60.0, 0.5, 90.0)
    sweep = kerr_shadow_morphology_sweep(spins=[0.0, spin], inclinations_deg=[inc], curve_samples=i(p, "curveSamples", 320, 120, 1200))
    rows = sweep["rows"]
    x = [r["spin_a_over_M"] for r in rows]
    return result(
        "kerr-shadow",
        "physical_lab_kerr_shadow_sweep",
        {"spin": spin, "inclinationDeg": inc},
        {"maxAbsHorizontalShiftOverM": sweep["max_abs_horizontal_shift_over_M"], "maxAbsSignedFlattening": sweep["max_abs_signed_flattening"]},
        [
            xy_series("shift", "horizontal shift", x, [r["horizontal_shift_over_M"] for r in rows], x_label="spin a/M", y_label="shift / M"),
            xy_series("flattening", "signed flattening", x, [r["signed_flattening"] for r in rows], x_label="spin a/M", y_label="flattening"),
            xy_series("diameter", "mean diameter", x, [r["mean_diameter_over_M"] for r in rows], x_label="spin a/M", y_label="diameter / M"),
        ],
        sweep["boundary"],
        [{"id": "morphology", "label": "Morphology cases", "rows": rows}],
    )


def undulator_spectrum(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_undulator_spectrum import harmonic_spectrum, angular_harmonic_map
    period_m = f(p, "periodMm", 50.0, 1.0, 1000.0) / 1000.0
    gamma = f(p, "gamma", 6000.0, 2.0, 1e7)
    K = f(p, "K", 0.7, 0.0, 20.0)
    periods = i(p, "periods", 20, 2, 500)
    harmonic = i(p, "harmonic", 1, 1, 15)
    spec = harmonic_spectrum(period_m=period_m, gamma=gamma, K=K, n_periods=periods, harmonics=(1, 3, 5, 7), points=1200)
    amap = angular_harmonic_map(period_m=period_m, gamma=gamma, K=K, harmonic=harmonic, theta_max_mrad=f(p, "thetaMaxMrad", 1.0, 0.05, 10.0), points=51)
    axis = np.asarray(amap["theta_axis_mrad"])
    center_line = np.asarray(amap["resonance_energy_eV"])[len(axis)//2]
    return result(
        "undulator-spectrum",
        "physical_lab_undulator_spectrum",
        {"periodMm": period_m * 1000, "gamma": gamma, "K": K, "periods": periods, "harmonic": harmonic},
        {"onAxisEnergyEV": amap["on_axis_energy_eV"], "edgeEnergyEV": amap["edge_energy_eV"], "minimumEnergyEV": amap["minimum_energy_eV"], "maximumEnergyEV": amap["maximum_energy_eV"]},
        [
            xy_series("spectrum", "harmonic spectrum", spec["energy_eV"], spec["relative_intensity"], x_label="photon energy (eV)", y_label="relative intensity"),
            xy_series("angle-cut", "angular resonance cut", axis, center_line, x_label="θ_x (mrad)", y_label="resonance energy (eV)"),
        ],
        spec["boundary"] + " " + amap["boundary"],
        [{"id": "harmonics", "label": "Harmonic centers", "rows": spec["harmonics"]}],
    )


def frequency_response(p: dict[str, Any], mode: str) -> dict[str, Any]:
    from physical_lab_frequency_response import linear_forced_response_sweep
    out = linear_forced_response_sweep(
        omega_n=f(p, "omegaN", 2.0, 0.1, 20.0),
        zeta=f(p, "zeta", 0.05, 0.0, 1.0),
        force_amplitude=f(p, "force", 1.0, 0.0, 20.0),
        frequency_start=f(p, "frequencyStart", 0.6, 0.05, 20.0),
        frequency_stop=f(p, "frequencyStop", 3.2, 0.1, 30.0),
        frequency_points=i(p, "frequencyPoints", 17, 7, 41),
        settle_cycles=i(p, "settleCycles", 12, 4, 40),
        observe_cycles=i(p, "observeCycles", 5, 3, 20),
        points_per_cycle=i(p, "pointsPerCycle", 48, 32, 120),
    )
    rows = out["rows"]
    omega = [r["omega_rad_s"] for r in rows]
    return result(
        "frequency-response",
        "physical_lab_frequency_response.linear_forced_response_sweep",
        out["inputs"],
        {
            "numericalPeakFrequencyRadS": out["numerical_peak_frequency_rad_s"],
            "numericalPeakAmplitude": out["numerical_peak_amplitude"],
            "theoreticalResonanceFrequencyRadS": out["theoretical_resonance_frequency_rad_s"],
            "maxAmplitudeRelativeError": out["max_amplitude_relative_error"],
            "maxPhaseAbsoluteErrorRad": out["max_phase_absolute_error_rad"],
        },
        [
            xy_series("numerical-amplitude", "numerical amplitude", omega, [r["fundamental_amplitude"] for r in rows], x_label="ω (rad/s)", y_label="amplitude"),
            xy_series("analytic-amplitude", "analytic amplitude", omega, [r["analytic_amplitude"] for r in rows], x_label="ω (rad/s)", y_label="amplitude"),
            xy_series("phase", "phase lag", omega, [r["phase_lag_rad"] for r in rows], x_label="ω (rad/s)", y_label="phase lag (rad)"),
            xy_series("amplitude-error", "amplitude relative error", omega, [r["amplitude_relative_error"] for r in rows], x_label="ω (rad/s)", y_label="relative error"),
        ],
        out["boundary"],
        [{"id": "frequency-rows", "label": "Frequency sweep", "rows": rows}],
    )


HANDLERS = {
    "numerical-methods": numerical_methods,
    "ising-monte-carlo": ising_monte_carlo,
    "random-walk-monte-carlo": random_walk,
    "nonlinear-chaos": nonlinear_chaos,
    "oscillation-integration": oscillation,
    "radia-magnet-studio": radia_magnet,
    "radiation-platform": radiation_platform,
    "kerr-geodesics": kerr_geodesics,
    "solar-system-dynamics": solar_system,
    "honeycomb-lattice": honeycomb_lattice,
    "utube-studio": utube,
    "kerr-shadow": kerr_shadow,
    "undulator-spectrum": undulator_spectrum,
    "frequency-response": frequency_response,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, choices=sorted(HANDLERS))
    parser.add_argument("--mode", default="safe", choices=("safe", "full"))
    args = parser.parse_args()
    try:
        raw = sys.stdin.read().strip()
        parameters = json.loads(raw) if raw else {}
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a JSON object")
        payload = HANDLERS[args.experiment](parameters, args.mode)
        sys.stdout.write(json.dumps(clean(payload), separators=(",", ":"), allow_nan=False))
        return 0
    except Exception as exc:
        error = {"schema": SCHEMA, "experimentId": args.experiment, "error": str(exc), "errorType": exc.__class__.__name__}
        sys.stdout.write(json.dumps(error, separators=(",", ":"), allow_nan=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
