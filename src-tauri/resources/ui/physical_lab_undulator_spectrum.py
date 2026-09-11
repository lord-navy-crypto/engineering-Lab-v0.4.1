"""Analytic/sampled undulator spectrum studies for Physical Lab.

This module deliberately complements, rather than replaces, the pinned
single-electron field-map Radiation Platform solver. It provides fast studies of
planar-undulator resonance structure, off-axis harmonic motion, and finite beam
energy-spread/divergence broadening using explicit textbook resonance relations.

It is not a full Lienard-Wiechert field solver, FEL gain model, coherent bunch
simulation, beamline optics model, or detector simulation.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

HC_EV_M = 1.2398419843320026e-6  # h*c in eV*m


def _np():
    import numpy as np
    return np


def _finite(x: Any, name: str) -> float:
    value = float(x)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def resonance_wavelength_m(
    *,
    period_m: float,
    gamma: float,
    K: float,
    harmonic: int = 1,
    theta_rad: float = 0.0,
) -> float:
    """Planar-undulator resonance wavelength for harmonic n."""
    lam_u = _finite(period_m, "period_m")
    g = _finite(gamma, "gamma")
    k = _finite(K, "K")
    theta = _finite(theta_rad, "theta_rad")
    n = int(harmonic)
    if lam_u <= 0 or g <= 1 or k < 0 or n < 1:
        raise ValueError("require period>0, gamma>1, K>=0, harmonic>=1")
    return lam_u * (1.0 + 0.5 * k * k + g * g * theta * theta) / (2.0 * n * g * g)


def resonance_energy_eV(**kwargs: Any) -> float:
    return HC_EV_M / resonance_wavelength_m(**kwargs)


def _planar_harmonic_coupling(K: float, harmonic: int) -> float:
    """On-axis odd-harmonic planar-undulator JJ coupling squared."""
    from scipy.special import jv

    n = int(harmonic)
    if n % 2 == 0:
        return 0.0
    k2 = float(K) ** 2
    q = n * k2 / (4.0 + 2.0 * k2)
    order_lo = 0.5 * (n - 1)
    order_hi = 0.5 * (n + 1)
    jj = float(jv(order_lo, q) - jv(order_hi, q))
    return jj * jj


def harmonic_spectrum(
    *,
    period_m: float = 0.05,
    gamma: float = 100.0,
    K: float = 0.7,
    n_periods: int = 20,
    theta_mrad: float = 0.0,
    harmonics: Sequence[int] = (1, 3, 5, 7),
    points: int = 2200,
    span_fraction: float = 0.12,
) -> dict[str, Any]:
    """Return a finite-N incoherent single-electron line-shape study.

    Each odd harmonic is represented by the standard finite-N interference
    factor sinc^2[N*pi*(E/E_n-1)] scaled by the planar JJ coupling. The line
    shape is a resonance/interference model, not a replacement for the pinned
    full trajectory radiation solver.
    """
    np = _np()
    N = int(n_periods)
    if N < 2 or N > 1000:
        raise ValueError("n_periods must be in [2,1000]")
    theta = 1e-3 * _finite(theta_mrad, "theta_mrad")
    hs = sorted({int(n) for n in harmonics if int(n) >= 1})
    if not hs:
        raise ValueError("at least one harmonic is required")
    centers = {
        n: resonance_energy_eV(period_m=period_m, gamma=gamma, K=K, harmonic=n, theta_rad=theta)
        for n in hs
    }
    e_min = min(centers.values()) * (1.0 - float(span_fraction))
    e_max = max(centers.values()) * (1.0 + float(span_fraction))
    energy = np.linspace(e_min, e_max, max(600, min(int(points), 12000)))
    total = np.zeros_like(energy)
    rows = []
    for n in hs:
        center = centers[n]
        coupling = _planar_harmonic_coupling(K, n)
        detuning = N * (energy / center - 1.0)
        line = coupling * np.sinc(detuning) ** 2
        total += line
        # For sinc^2(N*x), the first-zero relative width is exactly 1/N.
        rows.append({
            "harmonic": n,
            "resonance_energy_eV": float(center),
            "coupling_JJ2": float(coupling),
            "first_zero_relative_half_width": 1.0 / N,
        })
    peak = float(np.max(total))
    if peak > 0:
        total = total / peak
    return {
        "schema": "physical-lab-undulator-harmonic-spectrum-v1",
        "energy_eV": energy.tolist(),
        "relative_intensity": total.tolist(),
        "harmonics": rows,
        "inputs": {
            "period_m": float(period_m), "gamma": float(gamma), "K": float(K),
            "n_periods": N, "theta_mrad": float(theta_mrad),
        },
        "boundary": (
            "Finite-N planar-undulator resonance/interference model with textbook JJ harmonic coupling. "
            "It does not include measured field errors, full Lienard-Wiechert amplitudes, electron-bunch coherence, FEL gain, optics, or detector response."
        ),
    }


def angular_harmonic_map(
    *,
    period_m: float = 0.05,
    gamma: float = 100.0,
    K: float = 0.7,
    harmonic: int = 1,
    theta_max_mrad: float = 5.0,
    points: int = 81,
) -> dict[str, Any]:
    """Map resonance energy versus observation angle on an x/y image plane."""
    np = _np()
    count = max(21, min(int(points), 181))
    axis = np.linspace(-float(theta_max_mrad), float(theta_max_mrad), count)
    tx, ty = np.meshgrid(axis, axis, indexing="xy")
    theta = 1e-3 * np.sqrt(tx * tx + ty * ty)
    denom = 1.0 + 0.5 * float(K) ** 2 + float(gamma) ** 2 * theta * theta
    lam = float(period_m) * denom / (2.0 * int(harmonic) * float(gamma) ** 2)
    energy = HC_EV_M / lam
    on_axis = resonance_energy_eV(period_m=period_m, gamma=gamma, K=K, harmonic=harmonic, theta_rad=0.0)
    return {
        "schema": "physical-lab-undulator-angular-map-v1",
        "theta_axis_mrad": axis.tolist(),
        "resonance_energy_eV": energy.tolist(),
        "on_axis_energy_eV": float(on_axis),
        "edge_energy_eV": float(energy[0, count // 2]),
        "minimum_energy_eV": float(np.min(energy)),
        "maximum_energy_eV": float(np.max(energy)),
        "boundary": (
            "This map applies only the planar-undulator resonance-angle relation. It shows spectral red-shift with angle, not angular intensity or polarization from a full radiation field calculation."
        ),
    }


def beam_broadened_resonance(
    *,
    period_m: float = 0.05,
    gamma: float = 100.0,
    K: float = 0.7,
    harmonic: int = 1,
    relative_energy_spread_rms: float = 1e-3,
    angular_divergence_rms_mrad: float = 0.05,
    samples: int = 30000,
    seed: int = 20260911,
    bins: int = 180,
) -> dict[str, Any]:
    """Monte-Carlo map of resonance-energy broadening from beam spread.

    gamma samples use a Gaussian relative energy spread. x/y angles use
    independent Gaussian divergences. The result propagates these beam
    distributions only through the resonance relation; it is not a bunch
    radiation intensity calculation.
    """
    np = _np()
    count = max(2000, min(int(samples), 200000))
    spread = _finite(relative_energy_spread_rms, "relative_energy_spread_rms")
    div = 1e-3 * _finite(angular_divergence_rms_mrad, "angular_divergence_rms_mrad")
    if spread < 0 or div < 0:
        raise ValueError("beam spreads must be non-negative")
    rng = np.random.default_rng(int(seed))
    g = float(gamma) * (1.0 + spread * rng.standard_normal(count))
    if np.any(g <= 1.0):
        raise ValueError("sampled gamma <= 1; reduce relative energy spread")
    tx = div * rng.standard_normal(count)
    ty = div * rng.standard_normal(count)
    theta2 = tx * tx + ty * ty
    denom = 1.0 + 0.5 * float(K) ** 2 + g * g * theta2
    lam = float(period_m) * denom / (2.0 * int(harmonic) * g * g)
    energy = HC_EV_M / lam
    nominal = resonance_energy_eV(period_m=period_m, gamma=gamma, K=K, harmonic=harmonic, theta_rad=0.0)
    hist, edges = np.histogram(energy, bins=max(40, min(int(bins), 500)), density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    q05, q50, q95 = np.quantile(energy, [0.05, 0.5, 0.95])
    sigma = float(np.std(energy, ddof=1))
    return {
        "schema": "physical-lab-undulator-beam-broadening-v1",
        "bin_center_eV": centers.tolist(),
        "density": hist.tolist(),
        "nominal_energy_eV": float(nominal),
        "mean_energy_eV": float(np.mean(energy)),
        "median_energy_eV": float(q50),
        "rms_energy_spread_eV": sigma,
        "relative_rms_linewidth": sigma / max(float(np.mean(energy)), 1e-30),
        "p05_eV": float(q05), "p95_eV": float(q95),
        "inputs": {
            "relative_energy_spread_rms": spread,
            "angular_divergence_rms_mrad": float(angular_divergence_rms_mrad),
            "samples": count, "seed": int(seed),
        },
        "boundary": (
            "Finite Monte-Carlo propagation of beam energy spread and angular divergence through the resonance equation only. "
            "It is not a full bunch radiation, emittance phase-space, coherent, FEL, optics, or detector calculation."
        ),
    }
