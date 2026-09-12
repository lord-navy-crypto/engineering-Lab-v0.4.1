#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'src-tauri'/'resources'/'ui'/'physical_lab_model_depth_vi.py'
spec=importlib.util.spec_from_file_location('physical_lab_model_depth_vi',MOD)
if spec is None or spec.loader is None: raise RuntimeError(MOD)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

modal=mod.coupled_modal_energy_transfer(duration=80.0,dt=0.02,coupling_k=0.12)
phi=np.asarray(modal['mode_shapes_mass_normalized'],dtype=float)
assert np.max(np.abs(phi.T@phi-np.eye(2))) < 1e-10
assert modal['relative_total_energy_change'] < 2e-4
assert 0.0 <= modal['max_oscillator2_energy_fraction'] <= 1.000001
assert modal['max_oscillator2_energy_fraction'] > 0.8

det=mod.coupled_detuning_scan(detunings=(-0.5,-0.25,0.0,0.25,0.5),duration=100.0,dt=0.03)
rows={round(float(r['relative_detuning']),2):r for r in det['rows']}
assert rows[0.0]['max_energy_transfer_to_oscillator2'] >= rows[0.5]['max_energy_transfer_to_oscillator2']
assert rows[0.0]['max_energy_transfer_to_oscillator2'] >= rows[-0.5]['max_energy_transfer_to_oscillator2']

boot=mod.bootstrap_mean_uncertainty(sample_size=400,bootstrap_replicates=1000,seed=1234)
lo,hi=boot['percentile_95_interval']
assert 0.0 < boot['bootstrap_standard_error'] < 0.1
assert lo < hi
assert abs(boot['estimate']-boot['analytic_reference']) < 0.08

tail=mod.gaussian_tail_importance_sampling(threshold=4.0,samples=30000,replicates=16,seed=4321)
assert tail['analytic_reference_probability'] > 0
assert tail['importance_sampling']['replicate_std'] < tail['crude_mc']['replicate_std']
assert tail['std_reduction_factor'] > 3.0
assert abs(tail['importance_sampling']['mean']-tail['analytic_reference_probability']) < 5e-6

print('Model Depth VI validation: PASS')
print(f"- modal max transfer = {modal['max_oscillator2_energy_fraction']:.4f}")
print(f"- modal energy change = {modal['relative_total_energy_change']:.3e}")
print(f"- bootstrap SE = {boot['bootstrap_standard_error']:.3e}")
print(f"- 4-sigma IS std reduction = {tail['std_reduction_factor']:.2f}x")
