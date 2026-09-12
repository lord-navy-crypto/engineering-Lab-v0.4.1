#!/usr/bin/env python3
"""Deterministic validation for non-accelerator model-depth studies."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'src-tauri'/'resources'/'ui'
sys.path.insert(0,str(UI))
MOD=UI/'physical_lab_model_depth.py'
spec=importlib.util.spec_from_file_location('physical_lab_model_depth',MOD)
if spec is None or spec.loader is None: raise RuntimeError(MOD)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

# Autocorrelation estimator: correlated AR(1) must have lower ESS than white noise.
rng=np.random.default_rng(12345)
white=rng.normal(size=4096)
ar=np.zeros(4096)
noise=rng.normal(size=4096)
for i in range(1,len(ar)): ar[i]=0.8*ar[i-1]+noise[i]
w=mod.integrated_autocorrelation_time(white)
a=mod.integrated_autocorrelation_time(ar)
assert a['tau_int']>w['tau_int']
assert a['ess']<w['ess']
assert 0<a['ess']<=len(ar)

# Unforced damped Duffing should settle into a stable well with negative finite-time exponent.
d=mod.duffing_lyapunov_scan(amplitudes=(0.0,0.04,0.08,0.12),steps_per_period=64,settle_periods=40,analysis_periods=40)
assert len(d['rows'])==4
assert d['rows'][0]['largest_finite_time_lyapunov_per_time']<0.0
assert all(np.isfinite(r['largest_finite_time_lyapunov_per_time']) for r in d['rows'])
assert 'asymptotic proof' in d['boundary'].lower()

# Finite-cell q-resolved spectrum: only nonzero allowed q modes, bounded normalized spectra.
s=mod.lattice_dynamic_structure_factor(nx=2,ny=2,layers=1,steps=512,dt=0.004,velocity_scale=0.02,q_modes=((1,0),(0,1)),seed=99)
assert len(s['modes'])==2
assert s['max_relative_energy_drift']<5e-3
for row in s['modes']:
    spec=np.asarray(row['S_q_omega_normalized'],dtype=float)
    assert row['q_magnitude']>0
    assert np.all(spec>=-1e-12)
    assert np.max(spec)<=1.0+1e-12
    assert row['dominant_frequency_cycles_per_reduced_time']>=0
assert 'finite-supercell' in s['boundary'].lower()

print('Model Depth III validation: PASS')
print(f"- AR(1) tau_int={a['tau_int']:.3f} > white tau_int={w['tau_int']:.3f}")
print(f"- unforced Duffing FTLE={d['rows'][0]['largest_finite_time_lyapunov_per_time']:.5g}")
print(f"- lattice max relative energy drift={s['max_relative_energy_drift']:.3e}")
print('Boundary: finite-chain, finite-time and finite-supercell diagnostics only.')
