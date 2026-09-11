"""Fifth-wave non-accelerator model-depth studies.

Adds:
- random-walk diffusion / first-return scaling,
- Monte Carlo vs scrambled-Sobol dimension sensitivity,
- finite-supercell lattice normal-mode localization and defect overlap.

The studies are bounded numerical diagnostics, not asymptotic proofs or calibrated
material predictions.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Iterable


def _np():
    import numpy as np
    return np


def _plain(value: Any) -> Any:
    np = _np()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_plain(v) for v in value.tolist()]
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except Exception:
            pass
    return value


def random_walk_diffusion_return_study(
    *, walkers: int = 12000, steps: int = 1200, seed: int = 20260911,
    checkpoints: Iterable[int] = (5, 10, 20, 50, 100, 200, 500, 1000),
) -> dict[str, Any]:
    """2-D nearest-neighbor diffusion scaling plus first-return statistics."""
    np = _np()
    n = max(1000, min(int(walkers), 100000))
    total = max(50, min(int(steps), 10000))
    cps = sorted({int(v) for v in checkpoints if 1 <= int(v) <= total})
    if total not in cps:
        cps.append(total)
    rng = np.random.default_rng(int(seed))
    x = np.zeros(n, dtype=np.int32); y = np.zeros(n, dtype=np.int32)
    first_return = np.full(n, -1, dtype=np.int32)
    ever_left = np.zeros(n, dtype=bool)
    rows = []
    for step in range(1, total + 1):
        direction = rng.integers(0, 4, size=n)
        x += (direction == 0).astype(np.int32) - (direction == 1).astype(np.int32)
        y += (direction == 2).astype(np.int32) - (direction == 3).astype(np.int32)
        at_origin = (x == 0) & (y == 0)
        newly = ever_left & at_origin & (first_return < 0)
        first_return[newly] = step
        ever_left |= ~at_origin
        if step in cps:
            r2 = x.astype(float)**2 + y.astype(float)**2
            rows.append({
                "step": step,
                "mean_square_displacement": float(np.mean(r2)),
                "msd_over_step": float(np.mean(r2) / step),
                "origin_probability": float(np.mean(at_origin)),
                "ever_returned_fraction": float(np.mean(first_return >= 0)),
            })
    positive = [(r["step"], r["mean_square_displacement"]) for r in rows if r["step"] >= 10 and r["mean_square_displacement"] > 0]
    lx = np.log([p[0] for p in positive]); ly = np.log([p[1] for p in positive])
    xc = lx - np.mean(lx)
    slope = float(np.dot(xc, ly - np.mean(ly)) / max(np.dot(xc, xc), 1e-30))
    observed = first_return[first_return >= 0]
    return _plain({
        "schema": "physical-lab-random-walk-diffusion-return-v1",
        "walkers": n, "steps": total, "rows": rows,
        "msd_loglog_slope": slope,
        "effective_diffusion_coefficient_2d": float(rows[-1]["mean_square_displacement"] / (4.0 * rows[-1]["step"])),
        "returned_fraction_by_horizon": float(np.mean(first_return >= 0)),
        "median_first_return_step_conditional": None if observed.size == 0 else float(np.median(observed)),
        "boundary": "Finite 2-D nearest-neighbor walk ensemble. MSD slope and return fractions are finite-horizon diagnostics; they do not prove asymptotic recurrence or limiting exponents.",
    })


def qmc_dimension_sensitivity(
    *, dimensions: Iterable[int] = (2, 4, 8, 16), power: int = 10,
    replicates: int = 8, seed: int = 20260911,
) -> dict[str, Any]:
    """Compare MC and scrambled Sobol as dimension increases for one separable integral."""
    np = _np()
    from scipy.stats import qmc
    dims = sorted({int(d) for d in dimensions})
    if not dims or min(dims) < 1 or max(dims) > 32:
        raise ValueError("dimensions must lie in [1,32]")
    p = max(6, min(int(power), 15)); reps = max(4, min(int(replicates), 24)); n = 1 << p
    one_d = 0.5 * math.sqrt(math.pi) * math.erf(1.0)
    rows = []
    for d in dims:
        reference = one_d ** d
        mc_err = []; qmc_err = []
        for rep in range(reps):
            rng = np.random.default_rng(int(seed) + 101*d + rep)
            x = rng.random((n, d))
            mc = float(np.mean(np.exp(-np.sum(x*x, axis=1))))
            mc_err.append(abs(mc - reference))
            sobol = qmc.Sobol(d=d, scramble=True, seed=int(seed) + 10007*d + rep)
            sx = sobol.random_base2(m=p)
            sq = float(np.mean(np.exp(-np.sum(sx*sx, axis=1))))
            qmc_err.append(abs(sq - reference))
        probe = qmc.Sobol(d=d, scramble=True, seed=int(seed) + 17*d).random_base2(m=min(p, 9))
        discrepancy = float(qmc.discrepancy(probe))
        rows.append({
            "dimension": d, "samples": n, "reference": reference,
            "mc_median_abs_error": float(np.median(mc_err)),
            "qmc_median_abs_error": float(np.median(qmc_err)),
            "median_improvement_factor": float(np.median(mc_err) / max(float(np.median(qmc_err)), 1e-18)),
            "scrambled_sobol_discrepancy_probe": discrepancy,
        })
    return _plain({
        "schema": "physical-lab-qmc-dimension-sensitivity-v1", "rows": rows,
        "boundary": "Dimension sensitivity for one smooth separable benchmark at fixed sample count. The discrepancy probe and error ratios do not establish universal QMC behavior for arbitrary integrands.",
    })


def _finite_lattice_modes(config, *, fd_step: float = 2e-5) -> dict[str, Any]:
    np = _np()
    import physical_lab_lattice_dynamics as lattice
    model = lattice.build_lattice(config)
    n = len(model.positions); ndof = 2*n
    h = float(fd_step)
    if not (1e-7 <= h <= 1e-2):
        raise ValueError("fd_step outside supported range")
    zero = np.zeros((n,2), dtype=float)
    vel = np.zeros_like(zero)
    K = np.zeros((ndof, ndof), dtype=float)
    for col in range(ndof):
        up = zero.copy(); um = zero.copy()
        up.reshape(-1)[col] = h; um.reshape(-1)[col] = -h
        fp = lattice.force_components(model, up, vel, 0.0, include_dissipation=False, include_external=False)["total"].reshape(-1)
        fm = lattice.force_components(model, um, vel, 0.0, include_dissipation=False, include_external=False)["total"].reshape(-1)
        K[:, col] = -(fp - fm) / (2.0*h)
    K = 0.5*(K + K.T)
    masses = np.repeat(model.masses, 2)
    invsqrt = 1.0 / np.sqrt(np.maximum(masses, 1e-30))
    D = invsqrt[:,None] * K * invsqrt[None,:]
    D = 0.5*(D + D.T)
    eigvals, eigvecs = np.linalg.eigh(D)
    order = np.argsort(eigvals); eigvals = eigvals[order]; eigvecs = eigvecs[:,order]
    freqs = np.sqrt(np.maximum(eigvals,0.0))/(2.0*math.pi)
    rows = []
    defect = np.asarray(model.defect_mask, dtype=bool)
    for branch in range(ndof):
        vec = eigvecs[:,branch].reshape(n,2)
        atom_weight = np.sum(np.abs(vec)**2,axis=1)
        atom_weight /= max(float(np.sum(atom_weight)),1e-30)
        ipr = float(np.sum(atom_weight**2))
        pr = float(1.0 / max(n*ipr,1e-30))
        overlap = float(np.sum(atom_weight[defect])) if np.any(defect) else 0.0
        rows.append({
            "branch": branch, "frequency_cycles_per_time": float(freqs[branch]),
            "participation_ratio_fraction": pr, "inverse_participation_ratio": ipr,
            "defect_overlap_fraction": overlap,
        })
    return {"model": model, "rows": rows, "negative_eigenvalue_magnitude_max": max(0.0,-float(np.min(eigvals)))}


def lattice_defect_localization_study(
    *, nx: int = 3, ny: int = 3, layers: int = 1,
    defect_mode: str = "mass", defect_mass_multiplier: float = 4.0,
    defect_bond_scale: float = 0.25,
) -> dict[str, Any]:
    """Compare pristine and defective finite-supercell normal-mode localization."""
    import physical_lab_lattice_dynamics as lattice
    if defect_mode not in {"mass", "weak-bond", "line-weak-bond"}:
        raise ValueError("defect_mode must be mass, weak-bond, or line-weak-bond")
    base = lattice.LatticeConfig(
        nx=int(nx), ny=int(ny), layers=int(layers), stacking="AA",
        damping=0.0, interlayer_damping=0.0, drive_mode="none", drive_amplitude=0.0,
        stochastic_mode=False, temperature_reduced=0.0, initial_displacement=0.0,
        defect_mode="none",
    )
    defective = replace(base, defect_mode=defect_mode, defect_mass_multiplier=float(defect_mass_multiplier), defect_bond_scale=float(defect_bond_scale))
    pristine_modes = _finite_lattice_modes(base)
    defect_modes = _finite_lattice_modes(defective)
    prow = pristine_modes["rows"]; drow = defect_modes["rows"]
    nonzero_p = [r for r in prow if r["frequency_cycles_per_time"] > 1e-7]
    nonzero_d = [r for r in drow if r["frequency_cycles_per_time"] > 1e-7]
    most_local = min(nonzero_d, key=lambda r: r["participation_ratio_fraction"])
    most_defect = max(nonzero_d, key=lambda r: r["defect_overlap_fraction"])
    return _plain({
        "schema": "physical-lab-lattice-defect-localization-v1",
        "config": {"nx":int(nx),"ny":int(ny),"layers":int(layers),"defect_mode":defect_mode,"defect_mass_multiplier":float(defect_mass_multiplier),"defect_bond_scale":float(defect_bond_scale)},
        "pristine_modes": prow, "defect_modes": drow,
        "pristine_median_participation_fraction": float(__import__('numpy').median([r["participation_ratio_fraction"] for r in nonzero_p])),
        "defect_median_participation_fraction": float(__import__('numpy').median([r["participation_ratio_fraction"] for r in nonzero_d])),
        "most_localized_defect_mode": most_local,
        "largest_defect_overlap_mode": most_defect,
        "negative_eigenvalue_magnitude_max": max(pristine_modes["negative_eigenvalue_magnitude_max"], defect_modes["negative_eigenvalue_magnitude_max"]),
        "boundary": "Finite-supercell harmonic modes obtained from a numerical Hessian of the reduced-unit spring model. Participation ratio and defect overlap diagnose localization in this model only; they are not ab-initio defect phonons or experimentally calibrated localization lengths.",
    })
