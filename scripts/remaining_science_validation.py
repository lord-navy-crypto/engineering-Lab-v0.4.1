#!/usr/bin/env python3
"""Deterministic validation for Advanced Model Science."""
from __future__ import annotations
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'src-tauri'/'resources'/'ui'
sys.path.insert(0,str(UI))

from physical_lab_remaining_science import (
    ising_finite_size_scan, random_walk_first_passage, qmc_convergence_study,
    duffing_bifurcation_sweep, coupled_mode_study,
)


def require(condition: bool, message: str) -> None:
    if not condition: raise AssertionError(message)


def main() -> None:
    ising=ising_finite_size_scan(sizes=(6,8),temperatures=(1.7,2.1,2.3,2.8),burn_sweeps=100,sample_sweeps=260,thin=1)
    require(len(ising['rows'])==8,'unexpected Ising row count')
    for L in (6,8):
        rows=[r for r in ising['rows'] if r['L']==L]
        low=min(rows,key=lambda r:r['temperature']); high=max(rows,key=lambda r:r['temperature'])
        require(low['mean_abs_magnetization'] > high['mean_abs_magnetization'],'Ising ordered/disordered magnetization trend missing')
        require(all(r['heat_capacity_per_spin'] >= -1e-12 for r in rows),'negative Ising heat capacity estimate')
    require(abs(ising['onsager_critical_temperature_reduced']-2.269185314)<1e-6,'Onsager Tc reference changed')

    rw=random_walk_first_passage(walkers=3000,boundary_radius=8,max_steps=700)
    require(0.5 < rw['hit_fraction'] <= 1.0,'first-passage hit fraction outside expected bounded case')
    require(rw['median_first_passage_step'] is not None and rw['median_first_passage_step']>0,'missing first-passage median')
    surv=[r['survival_fraction'] for r in rw['survival_curve']]
    require(all(b <= a+1e-15 for a,b in zip(surv,surv[1:])),'survival curve must be monotone nonincreasing')

    qmc=qmc_convergence_study(powers=(5,6,7,8,9),replicates=8)
    require(qmc['rows'][-1]['qmc_median_abs_error'] < qmc['rows'][-1]['mc_median_abs_error'],'Sobol should beat MC on the terminal smooth-integral benchmark')
    require(qmc['qmc_loglog_error_slope'] < qmc['mc_loglog_error_slope'],'Sobol convergence slope should be steeper on this benchmark')

    duf=duffing_bifurcation_sweep(amplitudes=(0.20,0.24,0.28,0.32,0.36,0.40),steps_per_period=48,settle_periods=45,sample_periods=24)
    require(duf['max_resolved_branch_count'] >= 1,'Duffing branch resolver returned no branches')
    require(duf['max_nearby_state_separation_gain'] > 0,'Duffing nearby-state diagnostic invalid')
    require(all(len(r['stroboscopic_x'])==24 for r in duf['rows']),'Duffing stroboscopic sample count mismatch')

    modes=coupled_mode_study(coupling_k=0.12,duration=80,dt=0.02)
    omega=modes['normal_mode_omega_rad_s']
    require(abs(omega[0]-1.0)<1e-10,'symmetric mode frequency mismatch')
    require(abs(omega[1]-math.sqrt(1.24))<1e-10,'antisymmetric mode frequency mismatch')
    require(modes['relative_energy_drift_max'] < 2e-4,'coupled-mode Verlet energy drift too large')
    require(modes['beat_period_s'] is not None and modes['beat_period_s']>0,'missing beat period')

    print('Advanced remaining-science validation: PASS')
    print(f"- Ising finite-size rows: {len(ising['rows'])}; exact Tc={ising['onsager_critical_temperature_reduced']:.6f}")
    print(f"- Random-walk hit fraction: {rw['hit_fraction']:.4f}; median first passage={rw['median_first_passage_step']:.1f}")
    print(f"- QMC terminal improvement: {qmc['rows'][-1]['median_improvement_factor']:.3g}x")
    print(f"- Duffing max resolved branches: {duf['max_resolved_branch_count']}")
    print(f"- Coupled-mode energy drift: {modes['relative_energy_drift_max']:.3e}")
    print('Boundary: bounded computational studies only; no infinite-size phase proof, universal QMC claim, complete bifurcation proof, or calibrated modal test.')


if __name__=='__main__': main()
