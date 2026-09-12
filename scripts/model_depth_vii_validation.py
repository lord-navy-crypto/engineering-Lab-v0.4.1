from __future__ import annotations
import math, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src-tauri'/'resources'/'ui'))
from physical_lab_model_depth_vii import damped_oscillator_inverse, frequency_response_identification, regularized_inverse_demo

def main():
    decay=damped_oscillator_inverse(noise_std=0.003,samples=700,seed=11)
    assert decay['success']
    assert abs(decay['estimate']['omega_n']-decay['truth']['omega_n'])/decay['truth']['omega_n'] < 0.02
    assert abs(decay['estimate']['zeta']-decay['truth']['zeta']) < 0.015
    assert math.isfinite(decay['jacobian_condition_number'])

    frf=frequency_response_identification(noise_fraction=0.003,points=120,seed=12)
    assert abs(frf['estimate']['stiffness']-frf['truth']['stiffness'])/frf['truth']['stiffness'] < 0.02
    assert abs(frf['estimate']['damping']-frf['truth']['damping'])/max(frf['truth']['damping'],1e-12) < 0.05
    assert math.isfinite(frf['jacobian_condition_number'])

    ridge=regularized_inverse_demo(noise_std=0.05,seed=13)
    assert ridge['design_condition_number'] > 1e3
    rows=ridge['rows']; unreg=next(r for r in rows if r['lambda']==0.0)
    assert any(r['parameter_error_norm'] < unreg['parameter_error_norm'] for r in rows if r['lambda']>0)
    assert all(math.isfinite(r['prediction_rmse_vs_truth']) for r in rows)
    print('Model Depth VII validation PASS')
    print({'decay':decay['estimate'],'frf':frf['estimate'],'condition':ridge['design_condition_number']})

if __name__=='__main__': main()
