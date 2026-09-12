from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'src-tauri'/'resources'/'ui'
sys.path.insert(0,str(UI))
from physical_lab_model_depth_ix import pid_step_response,lqr_kalman_demo,heat_equation_1d,wave_equation_1d,poisson_equation_2d

def main()->None:
    pid=pid_step_response(kp=8,ki=2,kd=2,duration=12)
    assert abs(float(pid['position'][-1])-1.0) < 0.05
    assert float(pid['overshoot_pct']) < 60.0
    assert float(pid['control_rms']) > 0.0

    lqg=lqr_kalman_demo(process_noise=0.005,measurement_noise=0.02,seed=20260911)
    eig=np.asarray(lqg['closed_loop_eigenvalues_real'],dtype=float)
    assert np.all(eig < 0.0)
    assert float(lqg['position_estimation_rmse']) < 0.2

    h1=heat_equation_1d(points=41,time_steps=200)
    h2=heat_equation_1d(points=161,time_steps=800)
    assert float(h2['l2_error']) < float(h1['l2_error'])
    assert float(h2['max_error']) < 5e-4

    w=wave_equation_1d(points=321,cfl=0.8)
    assert float(w['cfl']) <= 1.0 + 1e-12
    assert float(w['l2_error']) < 5e-3
    assert float(w['max_relative_energy_drift']) < 0.1

    p1=poisson_equation_2d(points=21)
    p2=poisson_equation_2d(points=61)
    assert float(p2['l2_error']) < float(p1['l2_error'])
    assert float(p2['relative_residual']) < 1e-10
    print('Model Depth IX validation: PASS')

if __name__=='__main__': main()
