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
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        horizon_pad=f(p, "horizonPad", 1e-4, 1e-8, 0.1),
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
        saturn_inclination_factor=f(p, "saturnInclinationFactor", 0.25, 0.0, 1.0),
        saturn_backreaction=b(p, "saturnBackreaction", True),
        solar_1pn=b(p, "solar1pn", False),
        velocity_cross=b(p, "velocityCross", False),
        radial_drag=b(p, "radialDrag", False),
        velocity_cross_strength=f(p, "velocityCrossStrength", 1e-4, 0.0, 1e-2),
        radial_drag_strength=f(p, "radialDragStrength", 1e-8, 0.0, 1e-5),
        omega_z_per_year=f(p, "omegaZPerYear", 0.1, 0.0, 10.0),
        rtol=f(p, "rtol", 1e-10, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-12, 1e-15, 1e-7),
        max_step_years=f(p, "maxStepYears", 0.04, 0.0001, 1.0),
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
        nx=i(p, "nx", 3, 2, 10),
        ny=i(p, "ny", 3, 2, 10),
        layers=i(p, "layers", 2, 1, 5),
        stacking=str(p.get("stacking", "ABA")).upper() if str(p.get("stacking", "ABA")).upper() in {"AA", "ABA", "ABC"} else "ABA",
        bond_length=f(p, "bondLength", 1.0, 0.05, 20.0),
        layer_spacing=f(p, "layerSpacing", 0.35, 0.01, 10.0),
        strain_x=f(p, "strainX", 0.0, -0.25, 0.25),
        mass=f(p, "mass", 1.0, 1e-6, 1e6),
        k_in=f(p, "kIn", 10.0, 1e-6, 1e6),
        alpha=f(p, "alpha", 2.0, 0.0, 1e4),
        k_inter=f(p, "kInter", 3.0, 1e-6, 1e6),
        beta_inter=f(p, "betaInter", 1.0, 0.0, 1e4),
        damping=f(p, "damping", 0.02, 0.0, 10.0),
        interlayer_damping=f(p, "interlayerDamping", 0.01, 0.0, 10.0),
        defect_mode=str(p.get("defectMode", "none")) if str(p.get("defectMode", "none")) in {"none","mass","weak-bond","line-weak-bond"} else "none",
        defect_mass_multiplier=f(p, "defectMassMultiplier", 2.0, 0.0, 100.0),
        defect_bond_scale=f(p, "defectBondScale", 0.4, 0.0, 10.0),
        drive_mode=str(p.get("driveMode", "sin")) if str(p.get("driveMode", "sin")) in {"none","sin","pulse","beat","chirp"} else "sin",
        drive_amplitude=f(p, "driveAmplitude", 0.08, 0.0, 10.0),
        drive_frequency=f(p, "driveFrequency", 1.0, 0.0, 100.0),
        uniform_force_x=f(p, "uniformForceX", 0.0, -100.0, 100.0),
        stochastic_mode=b(p, "stochasticMode", False),
        temperature_reduced=f(p, "temperatureReduced", 0.0, 0.0, 100.0),
        seed=i(p, "seed", 12345, 0, 2147483647),
        initial_displacement=f(p, "initialDisplacement", 0.01, 0.0, 10.0),
        duration=f(p, "duration", 8.0, 1.0, 200.0),
        samples=i(p, "samples", 420, 64, 20000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        max_step=f(p, "maxStep", 0.03, 0.0001, 1.0),
        langevin_dt=f(p, "langevinDt", 0.005, 1e-5, 0.2),
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



def _kerr_config_from_params(p: dict[str, Any]):
    from physical_lab_kerr_geodesics import KerrOrbitConfig
    particle = str(p.get("particleType", "massive")).lower()
    return KerrOrbitConfig(
        spin=f(p, "spin", 0.7, 0.0, 0.995),
        inclination_deg=f(p, "inclinationDeg", 25.0, 0.0, 89.0),
        particle_type="photon" if particle == "photon" else "massive",
        periapsis=f(p, "periapsis", 6.5, 2.1, 80.0),
        apoapsis=f(p, "apoapsis", 10.0, 2.2, 150.0),
        lam_max=f(p, "lambdaMax", 16.0, 1.0, 80.0),
        samples=i(p, "samples", 1000, 200, 4000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        horizon_pad=f(p, "horizonPad", 1e-4, 1e-8, 0.1),
    )


def _solar_config_from_params(p: dict[str, Any]):
    from physical_lab_solar_system_dynamics import SolarSystemConfig
    return SolarSystemConfig(
        duration_years=f(p, "durationYears", 30.0, 0.05, 1000.0),
        samples=i(p, "samples", 900, 100, 50000),
        inclination_jupiter_deg=f(p, "inclinationDeg", 10.0, 0.0, 60.0),
        saturn_inclination_factor=f(p, "saturnInclinationFactor", 0.25, 0.0, 1.0),
        saturn_backreaction=b(p, "saturnBackreaction", True),
        solar_1pn=b(p, "solar1pn", False),
        velocity_cross=b(p, "velocityCross", False),
        radial_drag=b(p, "radialDrag", False),
        velocity_cross_strength=f(p, "velocityCrossStrength", 1e-4, 0.0, 1e-2),
        radial_drag_strength=f(p, "radialDragStrength", 1e-8, 0.0, 1e-5),
        omega_z_per_year=f(p, "omegaZPerYear", 0.1, 0.0, 10.0),
        rtol=f(p, "rtol", 1e-10, 1e-13, 1e-5),
        atol=f(p, "atol", 1e-12, 1e-15, 1e-7),
        max_step_years=f(p, "maxStepYears", 0.04, 0.0001, 1.0),
    )


def _lattice_config_from_params(p: dict[str, Any]):
    from physical_lab_lattice_dynamics import LatticeConfig
    stacking=str(p.get("stacking", "ABA")).upper()
    defect=str(p.get("defectMode", "none"))
    drive=str(p.get("driveMode", "sin"))
    return LatticeConfig(
        nx=i(p, "nx", 3, 2, 10), ny=i(p, "ny", 3, 2, 10), layers=i(p, "layers", 2, 1, 5),
        stacking=stacking if stacking in {"AA","ABA","ABC"} else "ABA",
        bond_length=f(p, "bondLength", 1.0, 0.05, 20.0),
        layer_spacing=f(p, "layerSpacing", 0.35, 0.01, 10.0),
        strain_x=f(p, "strainX", 0.0, -0.25, 0.25),
        mass=f(p, "mass", 1.0, 1e-6, 1e6), k_in=f(p, "kIn", 10.0, 1e-6, 1e6),
        alpha=f(p, "alpha", 2.0, 0.0, 1e4), k_inter=f(p, "kInter", 3.0, 1e-6, 1e6),
        beta_inter=f(p, "betaInter", 1.0, 0.0, 1e4),
        damping=f(p, "damping", 0.02, 0.0, 10.0), interlayer_damping=f(p, "interlayerDamping", 0.01, 0.0, 10.0),
        defect_mode=defect if defect in {"none","mass","weak-bond","line-weak-bond"} else "none",
        defect_mass_multiplier=f(p, "defectMassMultiplier", 2.0, 0.0, 100.0),
        defect_bond_scale=f(p, "defectBondScale", 0.4, 0.0, 10.0),
        drive_mode=drive if drive in {"none","sin","pulse","beat","chirp"} else "sin",
        drive_amplitude=f(p, "driveAmplitude", 0.08, 0.0, 10.0),
        drive_frequency=f(p, "driveFrequency", 1.0, 0.0, 100.0),
        uniform_force_x=f(p, "uniformForceX", 0.0, -100.0, 100.0),
        stochastic_mode=b(p, "stochasticMode", False), temperature_reduced=f(p, "temperatureReduced", 0.0, 0.0, 100.0),
        seed=i(p, "seed", 12345, 0, 2147483647), initial_displacement=f(p, "initialDisplacement", 0.01, 0.0, 10.0),
        duration=f(p, "duration", 8.0, 1.0, 200.0), samples=i(p, "samples", 420, 64, 20000),
        rtol=f(p, "rtol", 1e-9, 1e-13, 1e-5), atol=f(p, "atol", 1e-11, 1e-15, 1e-7),
        max_step=f(p, "maxStep", 0.03, 0.0001, 1.0), langevin_dt=f(p, "langevinDt", 0.005, 1e-5, 0.2),
    )



def _context_result(p: dict[str, Any]) -> dict[str, Any]:
    value = p.get("contextResult")
    if not isinstance(value, dict):
        raise ValueError("Run the experiment first so this analysis tool has a current structured result.")
    return value


def _first_numeric_series(context: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    for series in context.get("series") or []:
        if not isinstance(series, dict):
            continue
        x = np.asarray(series.get("x") or [], dtype=float).reshape(-1)
        y = np.asarray(series.get("y") or [], dtype=float).reshape(-1)
        n = min(len(x), len(y))
        if n >= 3:
            x, y = x[:n], y[:n]
            mask = np.isfinite(x) & np.isfinite(y)
            if int(np.count_nonzero(mask)) >= 3:
                return x[mask], y[mask], series
    raise ValueError("The current result has no numeric x/y series with at least three finite points.")



def _result_frame_and_numeric_columns(context: dict[str, Any]):
    from physical_lab_visualization_studio import result_frame, numeric_columns
    frame = result_frame(context)
    columns = numeric_columns(frame)
    return frame, columns


def _varying_numeric_columns(frame, columns):
    import pandas as pd
    out = []
    for col in columns:
        values = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(values) >= 3 and int(values.nunique()) >= 2:
            out.append(col)
    return out


def run_global_analysis_tool(experiment_id: str, tool: str, p: dict[str, Any]) -> dict[str, Any]:
    context = _context_result(p)

    if tool in {"visualization-summary", "visualization-transform", "local-sensitivity", "elasticity-sensitivity", "standardized-sensitivity"}:
        import pandas as pd
        from physical_lab_visualization_studio import summary as visualization_summary, transform as visualization_transform
        from physical_lab_visual_analytics import local_sensitivity, elasticity_sensitivity, standardized_sensitivity
        frame, columns = _result_frame_and_numeric_columns(context)
        usable = [c for c in columns if c != "index"]
        if not usable:
            usable = list(columns)
        if tool == "visualization-summary":
            rows = visualization_summary(frame, columns)
            return result(experiment_id, "physical_lab_visualization_studio.summary", p,
                          {"rowCount": len(frame), "numericColumnCount": len(columns), "summaryFieldCount": len(rows)},
                          [], "Descriptive statistics summarize finite numeric fields in the current structured result; they do not add scientific validation.",
                          [{"id":"visual-summary","label":"Visualization summary","rows":rows}])
        if tool == "visualization-transform":
            chosen = usable[:min(4, len(usable))]
            mode = str(p.get("transformMode", "z-score"))
            if mode not in {"z-score","min-max","absolute","none"}:
                mode = "z-score"
            out = visualization_transform(frame, chosen, mode)
            series = []
            x = np.arange(len(out), dtype=float)
            for col in chosen:
                y = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=float)
                mask = np.isfinite(y)
                if int(np.count_nonzero(mask)) >= 2:
                    series.append(xy_series(f"transform-{col}", f"{col} · {mode}", x[mask], y[mask], x_label="row", y_label=col))
            return result(experiment_id, "physical_lab_visualization_studio.transform", p,
                          {"rowCount": len(out), "transformedColumns": len(chosen), "mode": mode},
                          series, "Transforms are visualization/analysis conveniences applied to a copy of the current result table; source results are not modified.",
                          [{"id":"transformed-preview","label":"Transformed result preview","rows":out.head(200).to_dict(orient="records")}])
        if len(usable) < 2:
            raise ValueError("Sensitivity analysis needs at least two varying numeric result fields.")
        parameter, output = usable[0], usable[1]
        if tool == "local-sensitivity":
            out = local_sensitivity(frame, parameter, output)
            rows = out.to_dict(orient="records")
            return result(experiment_id, "physical_lab_visual_analytics.local_sensitivity", p,
                          {"segments": len(rows), "parameter": parameter, "output": output},
                          [xy_series("local-sensitivity","local sensitivity",out["parameter_center"],out["sensitivity"],x_label=parameter,y_label=f"d({output})/d({parameter})")],
                          "Finite-difference local sensitivity is descriptive for the selected result fields and depends on the sampled parameter spacing.",
                          [{"id":"local-sensitivity","label":"Local sensitivity","rows":rows}])
        if tool == "elasticity-sensitivity":
            out = elasticity_sensitivity(frame, parameter, output)
            rows = out.to_dict(orient="records")
            finite = pd.to_numeric(out["elasticity"], errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
            return result(experiment_id, "physical_lab_visual_analytics.elasticity_sensitivity", p,
                          {"segments": len(rows), "parameter": parameter, "output": output, "maxAbsElasticity": float(finite.abs().max()) if len(finite) else None},
                          [xy_series("elasticity","elasticity sensitivity",out["parameter_center"],out["elasticity"],x_label=parameter,y_label="elasticity")],
                          "Elasticity is a local normalized sensitivity and is undefined where the output center is zero.",
                          [{"id":"elasticity","label":"Elasticity sensitivity","rows":rows}])
        varying = []
        for col in usable:
            values = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(values) >= 3 and int(values.nunique()) >= 2:
                varying.append(col)
        if len(varying) < 2:
            raise ValueError("Standardized sensitivity needs at least two varying numeric result fields.")
        parameter_candidates = varying[:-1]
        output = varying[-1]
        out = standardized_sensitivity(frame, parameter_candidates, output)
        rows = out.to_dict(orient="records")
        if not rows:
            raise ValueError("Standardized sensitivity found no fields with enough finite variation.")
        return result(experiment_id, "physical_lab_visual_analytics.standardized_sensitivity", p,
                      {"parameterCount": len(rows), "output": output, "largestAbsSlope": float(out["abs_standardized_slope"].max())},
                      [xy_series("standardized-sensitivity","standardized sensitivity",range(len(rows)),out["standardized_slope"],x_label="parameter rank",y_label="standardized slope")],
                      "Standardized slopes and Spearman coefficients summarize association in the current finite result table; they do not imply causation.",
                      [{"id":"standardized-sensitivity","label":"Standardized sensitivity","rows":rows}])

    if tool in {"polynomial-regression","monte-carlo-propagation","doe-design","parameter-estimation","polynomial-cv","pca-svd","conditioning-diagnostics","tikhonov","tsvd","correlation-matrix","pareto-frontier","robust-sensitivity","run-comparison","morris-design"}:
        import pandas as pd
        frame, columns = _result_frame_and_numeric_columns(context)
        varying = _varying_numeric_columns(frame, [c for c in columns if c != "index"])
        if tool == "monte-carlo-propagation":
            from physical_lab_applied_analysis import monte_carlo_propagation
            means=[0.0,1.0,2.0]; stds=[0.1,0.2,0.15]; coeff=[1.0,-0.5,0.25]
            out=monte_carlo_propagation(means=means,standard_uncertainties=stds,coefficients=coeff,samples=i(p,"monteCarloSamples",2000,100,20000),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis.monte_carlo_propagation",p,{"mean":out["mean"],"standardDeviation":out["standard_deviation"],"median":out["median"],"samples":out["samples"]},[xy_series("mc-distribution","Monte Carlo distribution",range(len(out["distribution"])),out["distribution"],x_label="sample",y_label="output")],out["boundary"])
        if tool == "doe-design":
            from physical_lab_applied_analysis import design_experiment
            factors=[{"name":"factor_a","low":-1.0,"high":1.0},{"name":"factor_b","low":0.0,"high":2.0}]
            out=design_experiment(factors,method=str(p.get("doeMethod","latin-hypercube")),samples=i(p,"doeSamples",24,2,256),seed=i(p,"analysisSeed",0,0,2147483647))
            design=out["design"]
            return result(experiment_id,"physical_lab_applied_analysis.design_experiment",p,{"rowCount":out["row_count"],"method":out["method"],"factorCount":len(out["factors"])},[],out["boundary"],[{"id":"doe-design","label":"DOE design","rows":design.to_dict(orient="records")}])
        if tool == "morris-design":
            from physical_lab_applied_analysis_advanced import morris_design
            factors=[{"name":"factor_a","low":-1.0,"high":1.0},{"name":"factor_b","low":0.0,"high":2.0}]
            out=morris_design(factors,trajectories=i(p,"morrisTrajectories",6,2,100),levels=i(p,"morrisLevels",6,4,20),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis_advanced.morris_design",p,{"rows":len(out["rows"]),"trajectories":out["trajectories"],"levels":out["levels"]},[],out["boundary"],[{"id":"morris-design","label":"Morris screening design","rows":out["rows"]}])
        if len(varying) < 2:
            raise ValueError(f"{tool} needs at least two varying numeric result fields.")
        xcol, ycol = varying[0], varying[-1]
        if tool == "polynomial-regression":
            from physical_lab_applied_analysis import polynomial_regression
            out=polynomial_regression(frame,xcol,ycol,degree=i(p,"polynomialDegree",2,1,6))
            diag=out["diagnostics"]
            return result(experiment_id,"physical_lab_applied_analysis.polynomial_regression",p,{"degree":out["degree"],"rSquared":out["r2"],"rmse":out["rmse"],"rank":out["rank"]},[xy_series("poly-observed","observed",diag[xcol],diag["observed"],x_label=xcol,y_label=ycol,chart="scatter"),xy_series("poly-fit","polynomial fit",diag[xcol],diag["predicted"],x_label=xcol,y_label=ycol)],out["boundary"],[{"id":"coefficients","label":"Polynomial coefficients","rows":out["coefficients"]}])
        if tool == "parameter-estimation":
            from physical_lab_applied_analysis import estimate_parameters
            out=estimate_parameters(frame,xcol,ycol,model=str(p.get("parameterModel","linear")))
            diag=out["diagnostics"]
            return result(experiment_id,"physical_lab_applied_analysis.estimate_parameters",p,{"model":out["model"],"rmse":out["rmse"],"mae":out["mae"],"n":out["n"]},[xy_series("parameter-observed","observed",diag[xcol],diag["observed"],x_label=xcol,y_label=ycol,chart="scatter"),xy_series("parameter-fit","estimated model",diag[xcol],diag["predicted"],x_label=xcol,y_label=ycol)],out["boundary"],[{"id":"parameters","label":"Estimated parameters","rows":out["parameters"]}])
        if tool == "polynomial-cv":
            from physical_lab_applied_analysis_advanced import cross_validate_polynomials
            out=cross_validate_polynomials(frame,xcol,ycol,degrees=(1,2,3),folds=min(5,max(2,len(frame)//4)),seed=i(p,"analysisSeed",0,0,2147483647))
            return result(experiment_id,"physical_lab_applied_analysis_advanced.cross_validate_polynomials",p,{"modelsCompared":len(out),"bestDegree":int(out.iloc[0]["degree"]) if len(out) else None,"bestCvRmse":float(out.iloc[0]["cv_rmse_mean"]) if len(out) else None},[], "Cross-validation compares predictive error among the specified polynomial families; it does not establish physical model truth.",[{"id":"polynomial-cv","label":"Polynomial cross-validation","rows":out.to_dict(orient="records")}])
        if tool == "pca-svd":
            from physical_lab_applied_math_deep import pca_svd
            chosen=varying[:min(4,len(varying))]
            out=pca_svd(frame,chosen,standardize=True,max_components=min(3,len(chosen)))
            return result(experiment_id,"physical_lab_applied_math_deep.pca_svd",p,{"rows":out["rows"],"effectiveRank":out["effective_rank"],"componentCount":len(out["explained_variance_ratio"])},[xy_series("pca-variance","explained variance",range(1,len(out["explained_variance_ratio"])+1),out["explained_variance_ratio"],x_label="component",y_label="explained variance ratio")],out["boundary"],[{"id":"pca-loadings","label":"PCA loadings","rows":out["loadings"].to_dict(orient="records")}])
        if tool == "conditioning-diagnostics":
            from physical_lab_applied_math_deep import conditioning_diagnostics
            chosen=varying[:min(4,len(varying))]
            out=conditioning_diagnostics(frame,chosen,center=True,standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.conditioning_diagnostics",p,{"rank":out["rank"],"columnCount":out["column_count"],"fullColumnRank":out["full_column_rank"],"conditionNumber":out["condition_number"]},[xy_series("singular-values","singular values",range(1,len(out["singular_values"])+1),out["singular_values"],x_label="index",y_label="singular value")],out["boundary"])
        predictors=varying[:-1][:min(3,len(varying)-1)]
        response=varying[-1]
        if tool == "tikhonov":
            from physical_lab_applied_math_deep import tikhonov_regression
            out=tikhonov_regression(frame,predictors,response,regularization=f(p,"regularization",1e-3,0.0,1e6),standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.tikhonov_regression",p,{"rmse":out["rmse"],"mae":out["mae"],"dataResidualNorm":out["data_residual_norm"],"regularizationNorm":out["regularization_norm"]},[],out["boundary"],[{"id":"tikhonov-coefficients","label":"Tikhonov coefficients","rows":out["coefficients"]},{"id":"tikhonov-diagnostics","label":"Tikhonov diagnostics","rows":out["diagnostics"].to_dict(orient="records")}])
        if tool == "tsvd":
            from physical_lab_applied_math_deep import truncated_svd_regression
            rank=max(1,min(len(predictors),i(p,"tsvdRank",1,1,10)))
            out=truncated_svd_regression(frame,predictors,response,rank=rank,standardize=True)
            return result(experiment_id,"physical_lab_applied_math_deep.truncated_svd_regression",p,{"rank":out["rank"],"maxRank":out["max_rank"],"rmse":out["rmse"],"dataResidualNorm":out["data_residual_norm"],"solutionNorm":out["solution_norm"]},[],out["boundary"],[{"id":"tsvd-coefficients","label":"TSVD coefficients","rows":out["coefficients"]},{"id":"tsvd-diagnostics","label":"TSVD diagnostics","rows":out["diagnostics"].to_dict(orient="records")}])
        if tool == "correlation-matrix":
            from physical_lab_tradeoff_analysis import correlation_matrix
            chosen=varying[:min(6,len(varying))]
            out=correlation_matrix(frame,chosen,method=str(p.get("correlationMethod","pearson")))
            rows=[{"field":idx,**{str(c):float(v) if pd.notna(v) else None for c,v in row.items()}} for idx,row in out.to_dict(orient="index").items()]
            return result(experiment_id,"physical_lab_tradeoff_analysis.correlation_matrix",p,{"fieldCount":len(chosen),"method":str(p.get("correlationMethod","pearson"))},[],"Correlation summarizes pairwise association in the current finite result table and does not imply causation.",[{"id":"correlation","label":"Correlation matrix","rows":rows}])
        if tool == "pareto-frontier":
            from physical_lab_tradeoff_analysis import pareto_frontier
            out=pareto_frontier(frame,x=xcol,x_goal="min",y=ycol,y_goal="max")
            return result(experiment_id,"physical_lab_tradeoff_analysis.pareto_frontier",p,{"points":len(out),"paretoPoints":int(out["pareto"].sum()) if "pareto" in out else 0,"xObjective":xcol,"yObjective":ycol},[xy_series("pareto-points","Pareto objective points",out[xcol],out[ycol],x_label=xcol,y_label=ycol,chart="scatter")],"Pareto membership depends on the selected objectives and directions; it is not a universal ranking.",[{"id":"pareto","label":"Pareto frontier","rows":out.to_dict(orient="records")}])
        if tool == "robust-sensitivity":
            from physical_lab_tradeoff_analysis import robust_sensitivity_summary
            out=robust_sensitivity_summary(frame,predictors,response)
            return result(experiment_id,"physical_lab_tradeoff_analysis.robust_sensitivity_summary",p,{"parameters":len(out),"response":response},[],"Robust sensitivity combines several descriptive diagnostics without creating a synthetic master score.",[{"id":"robust-sensitivity","label":"Robust sensitivity summary","rows":out.to_dict(orient="records")}])
        if tool == "run-comparison":
            from physical_lab_research_orchestrator import compare_numeric_runs
            rows=frame[varying[:min(5,len(varying))]].dropna().head(8).to_dict(orient="records")
            out=compare_numeric_runs(rows,baseline_index=0)
            return result(experiment_id,"physical_lab_research_orchestrator.compare_numeric_runs",p,{"runs":len(out["rows"]),"sharedMetrics":len(out["shared_metrics"]),"baselineIndex":out["baseline_index"]},[],out["boundary"],[{"id":"run-comparison","label":"Run comparison","rows":out["rows"]}])

    if tool == "result-inspector":
        from physical_lab_result_inspector import inspect_result, numerical_sanity_report
        inspection = inspect_result(context)
        sanity = numerical_sanity_report(context)
        inventory = inspection.get("inventory") or []
        checks = sanity.get("checks") or []
        metrics = {
            "fieldCount": len(inventory),
            "numericFieldCount": sum(1 for row in inventory if row.get("classification") in {"scalar", "vector", "matrix"}),
            "sanityCheckCount": len(checks),
            "warningCount": sum(1 for row in checks if str(row.get("severity")).lower() in {"warning", "error"}),
        }
        tables = [
            {"id": "schema-inventory", "label": "Result schema inventory", "rows": inventory[:250]},
            {"id": "sanity-checks", "label": "Numerical sanity checks", "rows": checks[:250]},
        ]
        return result(experiment_id, "physical_lab_result_inspector", p, metrics, [],
                      "Structural inspection and numerical sanity checks summarize the current result contract; they do not independently validate the underlying physical model.", tables)

    if tool == "bootstrap":
        from physical_lab_applied_analysis import bootstrap_statistic
        x, y, series = _first_numeric_series(context)
        out = bootstrap_statistic(
            y,
            statistic=str(p.get("bootstrapStatistic", "mean")),
            resamples=i(p, "bootstrapResamples", 1500, 100, 20000),
            confidence=f(p, "bootstrapConfidence", 0.95, 0.5, 0.999),
            seed=i(p, "analysisSeed", 0, 0, 2147483647),
        )
        interval = out.get("interval") or [None, None]
        metrics = {
            "estimate": out.get("estimate"),
            "confidenceLow": interval[0] if len(interval) > 0 else None,
            "confidenceHigh": interval[1] if len(interval) > 1 else None,
            "standardError": out.get("bootstrap_standard_error"),
            "sampleCount": out.get("n", len(y)),
            "resamples": out.get("resamples"),
        }
        return result(experiment_id, "physical_lab_applied_analysis.bootstrap_statistic", p, metrics, [],
                      "Bootstrap uncertainty here is conditional on the selected finite result series and resampling protocol; it does not include omitted model-form or measurement uncertainty.")

    if tool in {"regression", "robust-regression"}:
        import pandas as pd
        x, y, series = _first_numeric_series(context)
        frame = pd.DataFrame({"x": x, "y": y})
        if tool == "regression":
            from physical_lab_applied_analysis import regression_diagnostics
            out = regression_diagnostics(frame, ["x"], "y", include_intercept=True)
            coeff_rows = out.get("coefficients") or []
            coeff = {str(row.get("term")): row.get("estimate") for row in coeff_rows if isinstance(row, dict)}
            metrics = {
                "rSquared": out.get("r2"),
                "adjustedRSquared": out.get("adjusted_r2"),
                "rmse": out.get("rmse"),
                "mae": out.get("mae"),
                "conditionNumber": out.get("condition_number"),
                "intercept": coeff.get("intercept"),
                "slope": coeff.get("x"),
            }
            series_out = [xy_series("fit-data", str(series.get("label") or "data"), x, y, x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y"), chart="scatter")]
            diagnostics = out.get("diagnostics")
            if diagnostics is not None and hasattr(diagnostics, "columns") and "predicted" in diagnostics.columns:
                series_out.append(xy_series("linear-fit", "linear fit", x, diagnostics["predicted"].to_numpy(dtype=float), x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y")))
            tables = [{"id":"coefficients","label":"Regression coefficients","rows":coeff_rows}]
            if diagnostics is not None and hasattr(diagnostics, "to_dict"):
                tables.append({"id":"diagnostics","label":"Regression diagnostics","rows":diagnostics.to_dict(orient="records")})
            return result(experiment_id, "physical_lab_applied_analysis.regression_diagnostics", p, metrics, series_out,
                          out.get("boundary") or "Ordinary least-squares diagnostics summarize the selected current result series; residual structure and model assumptions still require interpretation.", tables)
        from physical_lab_applied_analysis_advanced import robust_regression_huber
        out = robust_regression_huber(frame, ["x"], "y", delta=f(p, "huberDelta", 1.345, 0.1, 20.0))
        coeff_rows = out.get("coefficients") or []
        coeff = {str(row.get("term")): row.get("estimate") for row in coeff_rows if isinstance(row, dict)}
        metrics = {
            "intercept": coeff.get("intercept"),
            "slope": coeff.get("x"),
            "rmse": out.get("rmse"),
            "mae": out.get("mae"),
            "downweightedFraction": out.get("downweighted_fraction"),
            "iterations": out.get("iterations"),
            "converged": out.get("converged"),
        }
        diagnostics = out.get("diagnostics")
        series_out = [xy_series("robust-data", str(series.get("label") or "data"), x, y, x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y"), chart="scatter")]
        if diagnostics is not None and hasattr(diagnostics, "columns") and "predicted" in diagnostics.columns:
            series_out.append(xy_series("robust-fit", "Huber fit", x, diagnostics["predicted"].to_numpy(dtype=float), x_label=str(series.get("xLabel") or "x"), y_label=str(series.get("yLabel") or "y")))
        tables = [{"id":"coefficients","label":"Huber coefficients","rows":coeff_rows}]
        if diagnostics is not None and hasattr(diagnostics, "to_dict"):
            tables.append({"id":"diagnostics","label":"Huber diagnostics","rows":diagnostics.to_dict(orient="records")})
        return result(experiment_id, "physical_lab_applied_analysis_advanced.robust_regression_huber", p, metrics,
                      series_out, out.get("boundary") or "Huber regression is a robust descriptive fit for the selected result series; it does not establish the correct physical functional form.", tables)

    if tool == "convergence-diagnostics":
        from physical_lab_research_orchestrator import convergence_diagnostics
        x, y, series = _first_numeric_series(context)
        if len(y) < 4:
            raise ValueError("Convergence diagnostics need at least four finite points.")
        reference = float(y[-1])
        error = np.abs(y - reference)
        resolution = np.arange(1, len(y) + 1, dtype=float)
        usable = error > max(1e-15, np.finfo(float).eps)
        if int(np.count_nonzero(usable)) < 3:
            usable = np.ones_like(error, dtype=bool)
            error = np.maximum(error, 1e-15)
        out = convergence_diagnostics(resolution[usable], error[usable])
        metrics = {
            "observedOrder": out.get("observed_order"),
            "loglogRSquared": out.get("loglog_r2"),
            "errorModelPrefactor": out.get("error_model_prefactor"),
            "finestResolution": out.get("finest_resolution"),
            "finestError": out.get("finest_error"),
            "referenceValue": reference,
        }
        return result(experiment_id, "physical_lab_research_orchestrator.convergence_diagnostics", p, metrics,
                      [xy_series("convergence-error", "distance from final sample", resolution, error, x_label="sample index", y_label="absolute difference")],
                      "This convenience diagnostic treats the final series value as a reference and sample index as a resolution proxy. Use an explicit refinement study when the x-axis is not a true numerical resolution parameter.")

    raise ValueError(f"Unsupported global analysis tool: {tool}")


def run_experiment_tool(experiment_id: str, tool: str, p: dict[str, Any], mode: str) -> dict[str, Any]:
    if tool in {"result-inspector", "bootstrap", "regression", "robust-regression", "convergence-diagnostics", "visualization-summary", "visualization-transform", "local-sensitivity", "elasticity-sensitivity", "standardized-sensitivity", "polynomial-regression", "monte-carlo-propagation", "doe-design", "parameter-estimation", "polynomial-cv", "pca-svd", "conditioning-diagnostics", "tikhonov", "tsvd", "correlation-matrix", "pareto-frontier", "robust-sensitivity", "run-comparison", "morris-design"}:
        return run_global_analysis_tool(experiment_id, tool, p)
    if experiment_id == "kerr-geodesics" and tool == "refinement":
        from physical_lab_kerr_geodesics import run_refinement_pair
        out = run_refinement_pair(_kerr_config_from_params(p))
        tight = out["tight"]
        keys = list(out["absolute_deltas"].keys())
        return result(experiment_id, "physical_lab_kerr_geodesics.run_refinement_pair", p, {
            "tightResidual": out["tight_residual"],
            **{f"delta_{k}": v for k, v in out["absolute_deltas"].items()},
        }, [xy_series("refinement-deltas","absolute refinement deltas",range(len(keys)),[out["absolute_deltas"][k] for k in keys],x_label="diagnostic index",y_label="absolute delta")],
        "Loose-versus-tight numerical refinement check for the same Kerr configuration.", [{"id":"tight","label":"Tight result","rows":[tight]}])

    if experiment_id == "solar-system-dynamics" and tool in {"refinement","ftle"}:
        cfg = _solar_config_from_params(p)
        if tool == "refinement":
            from physical_lab_solar_system_dynamics import run_refinement_pair
            out = run_refinement_pair(cfg)
            keys=list(out["relative_changes"].keys())
            return result(experiment_id,"physical_lab_solar_system_dynamics.run_refinement_pair",p,{
                "maxRelativeChange":out["max_relative_change"], **{f"relative_{k}":v for k,v in out["relative_changes"].items()}
            },[xy_series("refinement","relative refinement changes",range(len(keys)),[out["relative_changes"][k] for k in keys],x_label="diagnostic index",y_label="relative change")],
            "Loose-versus-tight integration refinement for the bounded Solar-System model.")
        from physical_lab_solar_system_dynamics import finite_time_lyapunov_indicator
        out=finite_time_lyapunov_indicator(cfg,d0=f(p,"ftleD0",1e-8,1e-12,1e-3),segment_years=f(p,"ftleSegmentYears",2.0,0.05,20.0),max_years=f(p,"ftleMaxYears",30.0,0.1,200.0))
        return result(experiment_id,"physical_lab_solar_system_dynamics.finite_time_lyapunov_indicator",p,{
            "finiteTimeRatePerYear":out["finite_time_rate_per_year"],"elapsedYears":out["elapsed_years"],"renormalizations":out["renormalizations"]
        },[xy_series("ftle-separation","pre-renormalization separation",out["times_years"],out["pre_renormalization_separation"],x_label="time (yr)",y_label="phase-space separation")],out["boundary"])

    if experiment_id == "honeycomb-lattice" and tool in {"normal-modes","phonon-dispersion","phonon-dos"}:
        cfg=_lattice_config_from_params(p)
        if tool=="normal-modes":
            from physical_lab_lattice_dynamics import build_lattice, normal_modes
            out=normal_modes(build_lattice(cfg)); freq=out["frequencies_cycles_per_time"]
            return result(experiment_id,"physical_lab_lattice_dynamics.normal_modes",p,{
                "zeroModeCount":out["zero_mode_count"],"negativeEigenvalueCount":out["negative_eigenvalue_count"],"mostNegativeEigenvalue":out["most_negative_eigenvalue"]
            },[xy_series("modes","normal-mode frequencies",range(len(freq)),freq,x_label="mode index",y_label="frequency")],out["boundary"])
        from physical_lab_lattice_phonons import phonon_dispersion, phonon_dos
        if tool=="phonon-dos":
            out=phonon_dos(cfg,q_grid=i(p,"phononQGrid",12,4,80),bins=i(p,"phononBins",80,16,240))
            return result(experiment_id,"physical_lab_lattice_phonons.phonon_dos",p,{
                "sampleCount":out["sample_count"],"branchCount":out["branch_count"],"normalizationError":out["normalization_error"],"frequencyMin":out["frequency_min"],"frequencyMax":out["frequency_max"]
            },[xy_series("dos","phonon DOS",out["frequency_centers"],out["density"],x_label="frequency",y_label="density")],out["boundary"])
        out=phonon_dispersion(cfg,points_per_segment=i(p,"phononPointsPerSegment",24,8,100))
        coord=np.asarray(out["path_coordinate"]); freqs=np.asarray(out["frequencies_cycles_per_time"])
        series=[xy_series(f"branch-{j}",f"branch {j}",coord,freqs[:,j],x_label="high-symmetry path",y_label="frequency") for j in range(freqs.shape[1])]
        return result(experiment_id,"physical_lab_lattice_phonons.phonon_dispersion",p,{
            "branchCount":out["branch_count"],"gammaZeroModeCount":out["gamma_zero_mode_count"],"hermiticityResidualMax":out["hermiticity_residual_max"],"negativeEigenvalueMagnitudeMax":out["negative_eigenvalue_magnitude_max"]
        },series,out["boundary"])

    if experiment_id == "undulator-spectrum" and tool in {"angular-map","beam-broadening"}:
        from physical_lab_undulator_spectrum import angular_harmonic_map, beam_broadened_resonance
        period=f(p,"periodMm",50.0,1.0,1000.0)/1000.0; gamma=f(p,"gamma",6000.0,2.0,1e7); K=f(p,"K",0.7,0.0,20.0); harmonic=i(p,"harmonic",1,1,15)
        if tool=="angular-map":
            out=angular_harmonic_map(period_m=period,gamma=gamma,K=K,harmonic=harmonic,theta_max_mrad=f(p,"thetaMaxMrad",1.0,.05,10.0),points=i(p,"angularPoints",61,21,181))
            axis=np.asarray(out["theta_axis_mrad"]); grid=np.asarray(out["resonance_energy_eV"]); cut=grid[len(axis)//2]
            return result(experiment_id,"physical_lab_undulator_spectrum.angular_harmonic_map",p,{
                "onAxisEnergyEV":out["on_axis_energy_eV"],"edgeEnergyEV":out["edge_energy_eV"],"minimumEnergyEV":out["minimum_energy_eV"],"maximumEnergyEV":out["maximum_energy_eV"]
            },[xy_series("angular-cut","central angular cut",axis,cut,x_label="theta_x (mrad)",y_label="resonance energy (eV)")],out["boundary"])
        out=beam_broadened_resonance(period_m=period,gamma=gamma,K=K,harmonic=harmonic,relative_energy_spread_rms=f(p,"relativeEnergySpreadRms",1e-3,0.0,.2),angular_divergence_rms_mrad=f(p,"angularDivergenceRmsMrad",.05,0.0,10.0),samples=i(p,"beamSamples",12000,2000,200000),seed=i(p,"beamSeed",20260911,0,2147483647),bins=i(p,"beamBins",120,40,500))
        return result(experiment_id,"physical_lab_undulator_spectrum.beam_broadened_resonance",p,{
            "nominalEnergyEV":out["nominal_energy_eV"],"meanEnergyEV":out["mean_energy_eV"],"medianEnergyEV":out["median_energy_eV"],"rmsEnergySpreadEV":out["rms_energy_spread_eV"],"relativeRmsLinewidth":out["relative_rms_linewidth"],"p05EV":out["p05_eV"],"p95EV":out["p95_eV"]
        },[xy_series("beam-broadening","beam-broadened resonance",out["bin_center_eV"],out["density"],x_label="photon energy (eV)",y_label="density")],out["boundary"])

    if experiment_id == "frequency-response" and tool == "duffing":
        from physical_lab_frequency_response import duffing_frequency_sweep
        out=duffing_frequency_sweep(omega_0=f(p,"omega0",1.0,.1,20.0),zeta=f(p,"zeta",.05,0.0,1.0),cubic_stiffness=f(p,"cubicStiffness",1.0,0.0,50.0),force_amplitude=f(p,"force",.3,0.0,20.0),frequency_start=f(p,"frequencyStart",.7,.05,20.0),frequency_stop=f(p,"frequencyStop",1.6,.1,30.0),frequency_points=i(p,"frequencyPoints",17,7,41),settle_cycles=i(p,"settleCycles",16,4,120),observe_cycles=i(p,"observeCycles",5,3,40),points_per_cycle=i(p,"pointsPerCycle",48,32,240))
        rows=out["rows"]; omega=[r["omega_rad_s"] for r in rows]
        return result(experiment_id,"physical_lab_frequency_response.duffing_frequency_sweep",p,{
            "forwardPeakFrequencyRadS":out["forward_peak_frequency_rad_s"],"forwardPeakAmplitude":out["forward_peak_amplitude"],"reversePeakFrequencyRadS":out["reverse_peak_frequency_rad_s"],"reversePeakAmplitude":out["reverse_peak_amplitude"],"maxBranchAmplitudeGap":out["max_branch_amplitude_gap"]
        },[
            xy_series("duffing-forward","forward amplitude",omega,[r["forward_amplitude"] for r in rows],x_label="omega (rad/s)",y_label="amplitude"),
            xy_series("duffing-reverse","reverse amplitude",omega,[r["reverse_amplitude"] for r in rows],x_label="omega (rad/s)",y_label="amplitude")
        ],out["boundary"],[{"id":"duffing","label":"Duffing sweep","rows":rows}])

    if experiment_id == "utube-studio" and tool in {"operating-state","elasticity","scan-plan","uncertainty","dimensionless-groups","inverse-geometry","design-space","robust-design","adaptive-plan","verification-requirements","research-questions","uncertainty-budget","hysteresis-analysis","rate-sweep","digital-twin-calibration","digital-twin-field","beam-phase-space"}:
        volume=f(p,"volumeMl",3.0,.05,30.0); rpm=f(p,"rpm",260.0,1.0,1000.0); rin=f(p,"rinMm",15.12,1.0,100.0)/1000.0; radius=f(p,"radiusMm",7.48,.1,50.0)/1000.0; nq=i(p,"nq",48,12,128)
        if tool=="dimensionless-groups":
            from physical_lab_utube_advanced import dimensionless_groups
            out=dimensionless_groups(rpm,rin_m=rin,a_m=radius,rho_kg_m3=f(p,"rhoKgM3",997.8,100.0,5000.0),gamma_mN_m=f(p,"gammaMnM",72.0,1.0,500.0))
            return result(experiment_id,"physical_lab_utube_advanced.dimensionless_groups",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[],str(out.get("boundary") or "Dimensionless groups summarize the nominated operating point."),[{"id":"dimensionless","label":"Dimensionless groups","rows":[out]}])
        if tool=="inverse-geometry":
            from physical_lab_utube_advanced import inverse_geometry_design
            out=inverse_geometry_design(f(p,"targetThresholdRpm",250.0,1.0,1000.0),volume,solve_for=str(p.get("solveFor","rin_m")))
            return result(experiment_id,"physical_lab_utube_advanced.inverse_geometry_design",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[],str(out.get("boundary") or "Inverse geometry design is model-based."),[{"id":"inverse-geometry","label":"Inverse geometry design","rows":[out]}])
        if tool=="design-space":
            from physical_lab_utube_advanced import design_space
            vols=np.linspace(max(.05,volume-.5),volume+.5,3); rins=np.linspace(max(.001,rin-.001),rin+.001,3); radii=np.linspace(max(.0005,radius-.0005),radius+.0005,3)
            frame=design_space(volumes_ml=vols,rin_values_m=rins,a_values_m=radii,target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0),nq=nq,max_points=100)
            return result(experiment_id,"physical_lab_utube_advanced.design_space",p,{"designPoints":len(frame)},[],"Design-space screening is a bounded model study, not manufacturing qualification.",[{"id":"design-space","label":"Design space","rows":frame.to_dict(orient="records")}])
        if tool=="robust-design":
            from physical_lab_utube_advanced import robust_design_space, pareto_robust_design
            vols=np.linspace(max(.05,volume-.3),volume+.3,3); rins=np.linspace(max(.001,rin-.0005),rin+.0005,3); radii=np.linspace(max(.0005,radius-.00025),radius+.00025,3)
            frame=robust_design_space(volumes_ml=vols,rin_values_m=rins,a_values_m=radii,target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0),nq=max(12,min(nq,32)),max_points=80)
            pareto=pareto_robust_design(frame)
            return result(experiment_id,"physical_lab_utube_advanced.robust_design_space",p,{"designPoints":len(frame),"paretoPoints":len(pareto)},[],"Robust/Pareto screening compares modeled tolerance sensitivity and does not certify a design.",[{"id":"robust-design","label":"Robust design space","rows":frame.to_dict(orient="records")},{"id":"pareto","label":"Pareto robust designs","rows":pareto.to_dict(orient="records")}])
        if tool=="adaptive-plan":
            from physical_lab_utube_advanced import adaptive_threshold_plan
            target=f(p,"targetThresholdRpm",250.0,1.0,1000.0)
            out=adaptive_threshold_plan([{"n_rpm":target-5,"state":"below"},{"n_rpm":target+5,"state":"above"}],target)
            rows=out if isinstance(out,list) else [out]
            return result(experiment_id,"physical_lab_utube_advanced.adaptive_threshold_plan",p,{"planItems":len(rows)},[],"Adaptive planning proposes bounded next measurements; it does not execute hardware.",[{"id":"adaptive-plan","label":"Adaptive threshold plan","rows":rows}])
        if tool=="verification-requirements":
            from physical_lab_utube_advanced import verification_requirements
            rows=verification_requirements(target_threshold_rpm=f(p,"targetThresholdRpm",250.0,1.0,1000.0))
            if isinstance(rows,dict): rows=[rows]
            return result(experiment_id,"physical_lab_utube_advanced.verification_requirements",p,{"requirements":len(rows)},[],"Verification requirements are explicit planning criteria, not certification.",[{"id":"verification-requirements","label":"Verification requirements","rows":rows}])
        if tool=="research-questions":
            from physical_lab_utube_advanced import research_questions
            rows=research_questions()
            if rows and isinstance(rows[0],str): rows=[{"question":x} for x in rows]
            return result(experiment_id,"physical_lab_utube_advanced.research_questions",p,{"questions":len(rows)},[],"Research questions organize investigation and are not conclusions.",[{"id":"research-questions","label":"Research questions","rows":rows}])
        if tool=="uncertainty-budget":
            from physical_lab_utube_uncertainty import local_uncertainty_budget
            means={"volume_ml":volume,"n_rpm":rpm,"rin_m":rin,"a_m":radius,"rho_kg_m3":f(p,"rhoKgM3",997.8,100.0,5000.0),"gamma_mN_m":f(p,"gammaMnM",72.0,1.0,500.0),"theta_deg":f(p,"thetaDeg",0.0,-180.0,180.0)}
            std={"volume_ml":f(p,"uVolumeMl",.05,0.0,10.0),"n_rpm":f(p,"uRpm",1.0,0.0,100.0),"rin_m":f(p,"uRinMm",.2,0.0,10.0)/1000.0,"a_m":f(p,"uRadiusMm",.1,0.0,10.0)/1000.0}
            out=local_uncertainty_budget(means,std,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_uncertainty.local_uncertainty_budget",p,{"budgetTerms":len(rows)},[],"Local uncertainty budgets linearize the model around the nominated operating point.",[{"id":"uncertainty-budget","label":"Local uncertainty budget","rows":rows}])
        if tool=="hysteresis-analysis":
            from physical_lab_utube_hysteresis import analyze_hysteresis_sweeps
            target=f(p,"targetThresholdRpm",250.0,1.0,1000.0)
            out=analyze_hysteresis_sweeps([volume]*3,[1.0,2.0,4.0],[target+1,target+2,target+4],[target-1,target-2,target-4],rin_m=rin,a_m=radius,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_hysteresis.analyze_hysteresis_sweeps",p,{"rows":len(rows)},[],"Hysteresis analysis is reduced-order and does not replace CFD or additional measurements.",[{"id":"hysteresis-analysis","label":"Hysteresis sweep analysis","rows":rows}])
        if tool=="rate-sweep":
            from physical_lab_utube_hysteresis import rate_sweep_prediction
            out=rate_sweep_prediction(volume,[0.5,1.0,2.0,4.0],response_tau_s=f(p,"responseTau",.2,0.0,1000.0),quasi_static_halfwidth_rpm=f(p,"quasiStaticHalfwidth",1.0,0.0,1000.0),rin_m=rin,a_m=radius,nq=nq)
            rows=out.to_dict(orient="records") if hasattr(out,"to_dict") else (out if isinstance(out,list) else [out])
            return result(experiment_id,"physical_lab_utube_hysteresis.rate_sweep_prediction",p,{"rows":len(rows)},[],"Rate-sweep predictions are reduced-order dynamic estimates.",[{"id":"rate-sweep","label":"Rate sweep prediction","rows":rows}])
        if tool=="digital-twin-calibration":
            from physical_lab_digital_twin import fit_linear_calibration, apply_linear_calibration
            raw=[0.0,1.0,2.0,3.0]; ref=[0.1,1.05,2.05,3.1]; fit=fit_linear_calibration(raw,ref); out=fit.to_dict(); calibrated=apply_linear_calibration(raw,float(fit.slope),float(fit.offset))
            return result(experiment_id,"physical_lab_digital_twin.fit_linear_calibration",p,{k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))},[xy_series("calibration","calibrated",raw,calibrated,x_label="raw",y_label="calibrated")],"Calibration diagnostics quantify only the supplied reference relationship.",[{"id":"calibration","label":"Calibration fit","rows":[out]}])
        if tool=="digital-twin-field":
            from physical_lab_digital_twin import compare_field_series, fit_model_affine, suggest_residual_measurement_points
            x=[0,1,2,3,4]; measured=[0.0,1.1,1.9,3.05,3.9]; model=[0.0,1.0,2.0,3.0,4.0]
            comp_obj=compare_field_series(x,measured,model); fit_obj=fit_model_affine(measured,model); suggestions=suggest_residual_measurement_points(x,measured,model)
            comp=comp_obj.to_dict(); fit=fit_obj.to_dict()
            metrics={**{k:v for k,v in comp.items() if isinstance(v,(int,float,str,bool))},**{f"fit_{k}":v for k,v in fit.items() if isinstance(v,(int,float,str,bool))}}
            rows=suggestions if isinstance(suggestions,list) else [suggestions]
            return result(experiment_id,"physical_lab_digital_twin.compare_field_series",p,metrics,[xy_series("measured-field","measured",x,measured,x_label="position",y_label="field"),xy_series("model-field","model",x,model,x_label="position",y_label="field")],"Digital-twin field comparison is diagnostic and does not prove model validity.",[{"id":"residual-points","label":"Suggested residual measurement points","rows":rows}])
        if tool=="beam-phase-space":
            from physical_lab_digital_twin import analyze_beam_phase_space
            x=[-2e-3,-1e-3,0.0,1e-3,2e-3]; px=[-1e-4,-4e-5,0,5e-5,1.1e-4]; y=[-1e-3,-.5e-3,0,.5e-3,1e-3]; py=[-6e-5,-3e-5,0,3e-5,6e-5]
            out_obj=analyze_beam_phase_space(x,px,y,py,beta_gamma=f(p,"betaGamma",1.0,1e-12,1e6)); out=out_obj.to_dict()
            metrics={k:v for k,v in out.items() if isinstance(v,(int,float,str,bool))}
            metrics.update({f"x_{k}":v for k,v in out.get("x_plane",{}).items() if isinstance(v,(int,float,str,bool))})
            metrics.update({f"y_{k}":v for k,v in out.get("y_plane",{}).items() if isinstance(v,(int,float,str,bool))})
            return result(experiment_id,"physical_lab_digital_twin.analyze_beam_phase_space",p,metrics,[],"Phase-space statistics summarize supplied samples and do not establish beamline validity.",[{"id":"beam-phase-space","label":"Beam phase-space statistics","rows":[out]}])
        if tool=="operating-state":
            from physical_lab_utube_advanced import operating_state
            out=operating_state(volume,rpm,rin_m=rin,a_m=radius,nq=nq,near_threshold_band_rpm=f(p,"nearThresholdBandRpm",3.0,.1,50.0))
            return result(experiment_id,"physical_lab_utube_advanced.operating_state",p,out,[] ,out["boundary"])
        if tool=="elasticity":
            from physical_lab_utube_advanced import threshold_elasticity
            frame=threshold_elasticity(volume,rin_m=rin,a_m=radius,relative_step=f(p,"elasticityStep",1e-3,1e-5,.1),nq=nq); rows=frame.to_dict(orient="records")
            return result(experiment_id,"physical_lab_utube_advanced.threshold_elasticity",p,{"maxAbsElasticity":max(abs(float(r["elasticity"])) for r in rows)},[xy_series("elasticity","threshold elasticity",range(len(rows)),[r["elasticity"] for r in rows],x_label="parameter index",y_label="elasticity")],"Local central-difference sensitivity of threshold to volume and geometry.",[{"id":"elasticity","label":"Elasticity","rows":rows}])
        if tool=="scan-plan":
            from physical_lab_utube_experiment import threshold
            from physical_lab_utube_advanced import experiment_scan_plan
            ng=threshold(volume,rin=rin,a=radius,nq=nq); frame=experiment_scan_plan(ng,coarse_span_rpm=f(p,"coarseSpanRpm",40.0,1.0,200.0),coarse_step_rpm=f(p,"coarseStepRpm",10.0,.1,100.0),fine_span_rpm=f(p,"fineSpanRpm",8.0,.5,100.0),fine_step_rpm=f(p,"fineStepRpm",2.0,.1,50.0)); rows=frame.to_dict(orient="records")
            return result(experiment_id,"physical_lab_utube_advanced.experiment_scan_plan",p,{"predictedThresholdRpm":ng,"plannedPoints":len(rows)},[xy_series("scan-plan","planned rpm points",range(len(rows)),[r["n_rpm"] for r in rows],x_label="step",y_label="rpm")],"Deterministic two-resolution experimental scan plan around the model threshold.",[{"id":"scan-plan","label":"Scan plan","rows":rows}])
        from physical_lab_utube_uncertainty import propagate_uncertainty
        means={"volume_ml":volume,"n_rpm":rpm,"rin_m":rin,"a_m":radius,"rho_kg_m3":f(p,"rhoKgM3",997.8,100.0,5000.0),"gamma_mN_m":f(p,"gammaMnM",72.0,1.0,500.0),"theta_deg":f(p,"thetaDeg",0.0,-180.0,180.0)}
        std={"volume_ml":f(p,"uVolumeMl",.05,0.0,10.0),"n_rpm":f(p,"uRpm",1.0,0.0,100.0),"rin_m":f(p,"uRinMm",.2,0.0,10.0)/1000.0,"a_m":f(p,"uRadiusMm",.1,0.0,10.0)/1000.0,"rho_kg_m3":f(p,"uRho",1.0,0.0,100.0),"gamma_mN_m":f(p,"uGamma",1.0,0.0,100.0),"theta_deg":f(p,"uThetaDeg",1.0,0.0,90.0)}
        out=propagate_uncertainty(means,std,samples=i(p,"uncertaintySamples",300,50,5000),seed=i(p,"uncertaintySeed",0,0,2147483647),nq=nq); ng=out["outputs"]["n_g_rpm"]; rec=out["records"]
        vals=[r.get("n_g_rpm") for r in rec if r.get("n_g_rpm") is not None]
        return result(experiment_id,"physical_lab_utube_uncertainty.propagate_uncertainty",p,{"samplesSucceeded":out["samples_succeeded"],"samplesFailed":out["samples_failed"],"thresholdMeanRpm":ng.get("mean"),"thresholdStdRpm":ng.get("std"),"thresholdP05Rpm":ng.get("p05"),"thresholdP95Rpm":ng.get("p95")},[xy_series("uncertainty","threshold samples",range(len(vals)),vals,x_label="sample",y_label="n_g (rpm)")],out["boundary"])

    raise ValueError(f"Unsupported tool '{tool}' for experiment '{experiment_id}'")


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
        tool = str(parameters.pop("__tool", "") or "").strip()
        payload = run_experiment_tool(args.experiment, tool, parameters, args.mode) if tool else HANDLERS[args.experiment](parameters, args.mode)
        sys.stdout.write(json.dumps(clean(payload), separators=(",", ":"), allow_nan=False))
        return 0
    except Exception as exc:
        error = {"schema": SCHEMA, "experimentId": args.experiment, "error": str(exc), "errorType": exc.__class__.__name__}
        sys.stdout.write(json.dumps(error, separators=(",", ":"), allow_nan=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
