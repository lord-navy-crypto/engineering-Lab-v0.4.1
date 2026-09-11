"""Frequency-response simulation core for Physical Lab dynamics models.

This module strengthens the simulation content of the two physics-first dynamics
Labs without changing their external source repositories:

- Oscillation / Integration: forced linear oscillator frequency response with an
  analytic steady-state reference for amplitude and phase.
- Nonlinear Dynamics / Chaos: hardening Duffing continuation sweeps that expose
  nonlinear resonance and forward/backward branch sensitivity.

The routines are deterministic and bounded.  Branch sensitivity is reported as
finite-sweep evidence; it is not automatically labeled physical hysteresis or a
complete bifurcation diagram.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable


def _np():
    import numpy as np
    return np


def _finite(value: Any, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _rk4_step(rhs: Callable[[float, Any], Any], t: float, state: Any, dt: float):
    np = _np()
    y = np.asarray(state, dtype=float)
    k1 = np.asarray(rhs(t, y), dtype=float)
    k2 = np.asarray(rhs(t + 0.5 * dt, y + 0.5 * dt * k1), dtype=float)
    k3 = np.asarray(rhs(t + 0.5 * dt, y + 0.5 * dt * k2), dtype=float)
    k4 = np.asarray(rhs(t + dt, y + dt * k3), dtype=float)
    return y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def _frequency_grid(start: float, stop: float, points: int) -> list[float]:
    np = _np()
    lo = _finite(start, "frequency_start")
    hi = _finite(stop, "frequency_stop")
    if not (0.0 < lo < hi):
        raise ValueError("frequency bounds must satisfy 0 < start < stop")
    count = max(5, min(int(points), 121))
    return [float(v) for v in np.linspace(lo, hi, count)]


def _harmonic_fit(times: Any, values: Any, omega: float) -> tuple[float, float, float]:
    """Return fundamental amplitude, lag phase, and residual RMS.

    The fitted model is x(t) = a cos(wt) + b sin(wt) + c.  For a response
    convention x=A cos(wt-phi), phase lag phi=atan2(b,a).
    """
    np = _np()
    t = np.asarray(times, dtype=float)
    x = np.asarray(values, dtype=float)
    if t.size != x.size or t.size < 8:
        raise ValueError("harmonic fit requires at least eight paired samples")
    design = np.column_stack((np.cos(omega * t), np.sin(omega * t), np.ones_like(t)))
    coeff, *_ = np.linalg.lstsq(design, x, rcond=None)
    fitted = design @ coeff
    amplitude = float(math.hypot(float(coeff[0]), float(coeff[1])))
    phase = float(math.atan2(float(coeff[1]), float(coeff[0])))
    residual_rms = float(math.sqrt(float(np.mean((x - fitted) ** 2))))
    return amplitude, phase, residual_rms


def _integrate_periodic_response(
    rhs_factory: Callable[[float], Callable[[float, Any], Any]],
    omega: float,
    *,
    initial_state: Iterable[float] = (0.0, 0.0),
    settle_cycles: int = 24,
    observe_cycles: int = 8,
    points_per_cycle: int = 72,
) -> dict[str, Any]:
    np = _np()
    w = _finite(omega, "drive frequency")
    if w <= 0:
        raise ValueError("drive frequency must be positive")
    settle = max(4, min(int(settle_cycles), 120))
    observe = max(3, min(int(observe_cycles), 40))
    ppc = max(32, min(int(points_per_cycle), 240))
    period = 2.0 * math.pi / w
    dt = period / ppc
    total_steps = (settle + observe) * ppc
    observation_start = settle * ppc
    state = np.asarray(list(initial_state), dtype=float)
    if state.shape != (2,) or not np.all(np.isfinite(state)):
        raise ValueError("initial_state must contain two finite values")
    rhs = rhs_factory(w)
    times: list[float] = []
    positions: list[float] = []
    velocities: list[float] = []
    t = 0.0
    for index in range(total_steps):
        state = _rk4_step(rhs, t, state, dt)
        t += dt
        if not np.all(np.isfinite(state)):
            raise ValueError("non-finite state reached during frequency-response integration")
        if index >= observation_start:
            times.append(t)
            positions.append(float(state[0]))
            velocities.append(float(state[1]))
    amplitude, phase, harmonic_residual_rms = _harmonic_fit(times, positions, w)
    x = np.asarray(positions, dtype=float)
    rms = float(math.sqrt(float(np.mean(x * x))))
    half_peak_to_peak = 0.5 * float(np.max(x) - np.min(x))
    poincare = x[ppc - 1 :: ppc]
    poincare_spread = float(np.std(poincare, ddof=1)) if poincare.size > 1 else 0.0
    return {
        "omega_rad_s": w,
        "dt_s": dt,
        "steady_rms": rms,
        "fundamental_amplitude": amplitude,
        "half_peak_to_peak": half_peak_to_peak,
        "phase_lag_rad": phase,
        "harmonic_residual_rms": harmonic_residual_rms,
        "poincare_spread": poincare_spread,
        "final_state": [float(state[0]), float(state[1])],
        "observed_cycles": observe,
    }


def linear_forced_response_sweep(
    *,
    omega_n: float = 2.0,
    zeta: float = 0.05,
    force_amplitude: float = 1.0,
    frequency_start: float = 0.6,
    frequency_stop: float = 3.2,
    frequency_points: int = 25,
    settle_cycles: int = 24,
    observe_cycles: int = 8,
    points_per_cycle: int = 72,
) -> dict[str, Any]:
    """Numerical forced-oscillator sweep with an analytic steady-state reference."""
    np = _np()
    wn = _finite(omega_n, "omega_n")
    damping = _finite(zeta, "zeta")
    force = _finite(force_amplitude, "force_amplitude")
    if wn <= 0 or damping < 0 or force < 0:
        raise ValueError("omega_n must be positive; zeta and force_amplitude must be non-negative")
    frequencies = _frequency_grid(frequency_start, frequency_stop, frequency_points)

    def rhs_factory(omega: float):
        def rhs(t: float, state: Any):
            x, velocity = state
            return (
                velocity,
                force * math.cos(omega * t) - 2.0 * damping * wn * velocity - wn * wn * x,
            )
        return rhs

    rows: list[dict[str, Any]] = []
    for omega in frequencies:
        numerical = _integrate_periodic_response(
            rhs_factory,
            omega,
            settle_cycles=settle_cycles,
            observe_cycles=observe_cycles,
            points_per_cycle=points_per_cycle,
        )
        denominator = math.hypot(wn * wn - omega * omega, 2.0 * damping * wn * omega)
        analytic_amplitude = force / denominator if denominator > 0 else float("inf")
        analytic_phase = math.atan2(2.0 * damping * wn * omega, wn * wn - omega * omega)
        amplitude_error = abs(numerical["fundamental_amplitude"] - analytic_amplitude) / max(
            abs(analytic_amplitude), 1e-15
        )
        phase_error = abs((numerical["phase_lag_rad"] - analytic_phase + math.pi) % (2.0 * math.pi) - math.pi)
        rows.append({
            **numerical,
            "frequency_ratio": omega / wn,
            "analytic_amplitude": analytic_amplitude,
            "analytic_phase_lag_rad": analytic_phase,
            "amplitude_relative_error": amplitude_error,
            "phase_absolute_error_rad": phase_error,
        })

    numerical_peak = max(rows, key=lambda row: float(row["fundamental_amplitude"]))
    analytic_peak = max(rows, key=lambda row: float(row["analytic_amplitude"]))
    max_amplitude_error = max(float(row["amplitude_relative_error"]) for row in rows)
    rms_amplitude_error = math.sqrt(
        sum(float(row["amplitude_relative_error"]) ** 2 for row in rows) / len(rows)
    )
    max_phase_error = max(float(row["phase_absolute_error_rad"]) for row in rows)
    theoretical_resonance = (
        wn * math.sqrt(max(0.0, 1.0 - 2.0 * damping * damping))
        if damping < 1.0 / math.sqrt(2.0)
        else None
    )
    return {
        "schema": "physical-lab-frequency-response-v1",
        "profile": "oscillation-integration",
        "scenario": "linear-forced-frequency-response",
        "inputs": {
            "omega_n_rad_s": wn,
            "zeta": damping,
            "force_amplitude": force,
            "frequency_range_rad_s": [frequencies[0], frequencies[-1]],
            "frequency_points": len(frequencies),
            "settle_cycles": max(4, min(int(settle_cycles), 120)),
            "observe_cycles": max(3, min(int(observe_cycles), 40)),
            "points_per_cycle": max(32, min(int(points_per_cycle), 240)),
        },
        "rows": rows,
        "numerical_peak_frequency_rad_s": float(numerical_peak["omega_rad_s"]),
        "numerical_peak_amplitude": float(numerical_peak["fundamental_amplitude"]),
        "analytic_grid_peak_frequency_rad_s": float(analytic_peak["omega_rad_s"]),
        "theoretical_resonance_frequency_rad_s": theoretical_resonance,
        "max_amplitude_relative_error": max_amplitude_error,
        "rms_amplitude_relative_error": rms_amplitude_error,
        "max_phase_absolute_error_rad": max_phase_error,
        "boundary": (
            "Single-degree-of-freedom linear oscillator with viscous damping and harmonic force. "
            "The analytic comparison is a steady-state verification reference; finite settling, discretization, "
            "real structural modes, nonlinear stiffness and experimental uncertainty are outside this result."
        ),
    }


def duffing_frequency_sweep(
    *,
    omega_0: float = 1.0,
    zeta: float = 0.05,
    cubic_stiffness: float = 1.0,
    force_amplitude: float = 0.30,
    frequency_start: float = 0.70,
    frequency_stop: float = 1.60,
    frequency_points: int = 25,
    settle_cycles: int = 35,
    observe_cycles: int = 8,
    points_per_cycle: int = 60,
) -> dict[str, Any]:
    """Forward/reverse continuation sweep for a hardening Duffing oscillator.

    Equation: x'' + 2*zeta*omega0*x' + omega0^2*x + beta*x^3 = F*cos(omega*t).
    Successive frequencies inherit the previous final state to expose branch
    sensitivity that independent zero-state runs can hide.
    """
    np = _np()
    w0 = _finite(omega_0, "omega_0")
    damping = _finite(zeta, "zeta")
    beta = _finite(cubic_stiffness, "cubic_stiffness")
    force = _finite(force_amplitude, "force_amplitude")
    if w0 <= 0 or damping < 0 or force < 0:
        raise ValueError("omega_0 must be positive; zeta and force_amplitude must be non-negative")
    frequencies = _frequency_grid(frequency_start, frequency_stop, frequency_points)

    def rhs_factory(omega: float):
        def rhs(t: float, state: Any):
            x, velocity = state
            return (
                velocity,
                force * math.cos(omega * t)
                - 2.0 * damping * w0 * velocity
                - w0 * w0 * x
                - beta * x**3,
            )
        return rhs

    def continuation(sequence: list[float]) -> list[dict[str, Any]]:
        state = np.asarray([0.0, 0.0], dtype=float)
        rows: list[dict[str, Any]] = []
        for omega in sequence:
            result = _integrate_periodic_response(
                rhs_factory,
                omega,
                initial_state=state,
                settle_cycles=settle_cycles,
                observe_cycles=observe_cycles,
                points_per_cycle=points_per_cycle,
            )
            state = np.asarray(result["final_state"], dtype=float)
            rows.append(result)
        return rows

    forward = continuation(frequencies)
    reverse_desc = continuation(list(reversed(frequencies)))
    reverse = list(reversed(reverse_desc))
    rows: list[dict[str, Any]] = []
    for omega, fwd, rev in zip(frequencies, forward, reverse):
        gap = abs(float(fwd["fundamental_amplitude"]) - float(rev["fundamental_amplitude"]))
        rows.append({
            "omega_rad_s": omega,
            "frequency_ratio": omega / w0,
            "forward_amplitude": float(fwd["fundamental_amplitude"]),
            "reverse_amplitude": float(rev["fundamental_amplitude"]),
            "branch_amplitude_gap": gap,
            "forward_phase_lag_rad": float(fwd["phase_lag_rad"]),
            "reverse_phase_lag_rad": float(rev["phase_lag_rad"]),
            "forward_harmonic_residual_rms": float(fwd["harmonic_residual_rms"]),
            "reverse_harmonic_residual_rms": float(rev["harmonic_residual_rms"]),
            "forward_poincare_spread": float(fwd["poincare_spread"]),
            "reverse_poincare_spread": float(rev["poincare_spread"]),
        })
    maximum_gap = max(rows, key=lambda row: float(row["branch_amplitude_gap"]))
    forward_peak = max(rows, key=lambda row: float(row["forward_amplitude"]))
    reverse_peak = max(rows, key=lambda row: float(row["reverse_amplitude"]))
    response_span = max(float(r["forward_amplitude"]) for r in rows) - min(
        float(r["forward_amplitude"]) for r in rows
    )
    return {
        "schema": "physical-lab-frequency-response-v1",
        "profile": "nonlinear-chaos",
        "scenario": "duffing-nonlinear-frequency-response",
        "equation": "x'' + 2*zeta*omega0*x' + omega0^2*x + beta*x^3 = F*cos(omega*t)",
        "inputs": {
            "omega_0_rad_s": w0,
            "zeta": damping,
            "cubic_stiffness": beta,
            "force_amplitude": force,
            "frequency_range_rad_s": [frequencies[0], frequencies[-1]],
            "frequency_points": len(frequencies),
            "settle_cycles": max(4, min(int(settle_cycles), 120)),
            "observe_cycles": max(3, min(int(observe_cycles), 40)),
            "points_per_cycle": max(32, min(int(points_per_cycle), 240)),
        },
        "rows": rows,
        "forward_peak_frequency_rad_s": float(forward_peak["omega_rad_s"]),
        "forward_peak_amplitude": float(forward_peak["forward_amplitude"]),
        "reverse_peak_frequency_rad_s": float(reverse_peak["omega_rad_s"]),
        "reverse_peak_amplitude": float(reverse_peak["reverse_amplitude"]),
        "max_branch_amplitude_gap": float(maximum_gap["branch_amplitude_gap"]),
        "max_branch_gap_frequency_rad_s": float(maximum_gap["omega_rad_s"]),
        "forward_response_amplitude_span": response_span,
        "boundary": (
            "Finite-time deterministic continuation of a normalized hardening Duffing oscillator. "
            "A forward/reverse branch gap is a numerical branch-sensitivity indicator under the stated sweep protocol; "
            "it is not by itself proof of a complete bifurcation structure, physical hysteresis in hardware, or chaos."
        ),
    }
