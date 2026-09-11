#!/usr/bin/env python3
"""Deterministic validation for Model Depth IV."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'src-tauri'/'resources'/'ui'/'physical_lab_model_depth_iv.py'
spec=importlib.util.spec_from_file_location('physical_lab_model_depth_iv',MOD)
if spec is None or spec.loader is None: raise RuntimeError(f'Unable to load {MOD}')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

# Conditioning: Hilbert condition number must rise strongly with size; residual can stay tiny.
cond=mod.conditioning_study(sizes=(5,8,12),perturbation=1e-10)
rows=cond['rows']
assert rows[0]['condition_2'] < rows[1]['condition_2'] < rows[2]['condition_2']
assert rows[-1]['condition_2'] > 1e10
assert rows[-1]['relative_residual'] < 1e-5
assert rows[-1]['amplification'] > 1.0

# Stiff analytic relaxation: all methods must succeed and remain accurate; implicit methods should avoid RK45-scale work.
stiff=mod.stiff_ode_comparison(stiffness=1000.0,duration=5.0)
by={r['method']:r for r in stiff['rows']}
assert all(r['success'] for r in stiff['rows'])
assert max(r['max_abs_error'] for r in stiff['rows']) < 2e-5
assert by['Radau']['nfev'] < by['RK45']['nfev']
assert by['BDF']['nfev'] < by['RK45']['nfev']

# Long-time oscillator: Verlet should retain bounded energy error; RK4 remains finite and typically drifts monotonically downward.
integ=mod.long_time_oscillator_integrators(periods=180,dt=0.08)
assert integ['verlet_max_abs_relative_energy_error'] < 0.01
assert abs(integ['rk4_final_relative_energy_error']) < 0.02
assert math.isfinite(integ['rk4_final_relative_energy_error'])

# Compact solar secular run: arrays finite and the underlying Newtonian integration remains conservative.
solar=mod.solar_secular_dynamics(duration_years=40.0,samples=900,inclination_jupiter_deg=2.0)
assert len(solar['time_years']) == 900
assert all(math.isfinite(float(x)) for x in solar['jupiter_eccentricity'])
assert all(math.isfinite(float(x)) for x in solar['saturn_eccentricity'])
assert solar['relative_energy_drift'] < 1e-6
assert solar['five_two_deviation_slow_spectrum']['dominant_period_years'] is not None

print('Model Depth IV validation: PASS')
print(f"- Hilbert kappa2(n=12): {rows[-1]['condition_2']:.3e}")
print(f"- stiff nfev RK45/Radau/BDF: {by['RK45']['nfev']}/{by['Radau']['nfev']}/{by['BDF']['nfev']}")
print(f"- Verlet max |dE/E|: {integ['verlet_max_abs_relative_energy_error']:.3e}")
print(f"- solar relative energy drift: {solar['relative_energy_drift']:.3e}")
print('Boundary: bounded numerical/model diagnostics; no ephemeris, global solver-ranking, or experimental-validation claim.')
