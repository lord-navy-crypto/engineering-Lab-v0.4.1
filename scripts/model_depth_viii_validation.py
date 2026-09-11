from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_model_depth_viii import empirical_transfer_function, chirp_frf_experiment, spectral_leakage_study


def main() -> None:
    # Cross-spectrum convention sanity check: exact broadband gain y = 2u.
    rng = np.random.default_rng(20260911)
    u = rng.normal(size=8192)
    y = 2.0 * u
    r = empirical_transfer_function(u, y, sample_rate_hz=200.0, nperseg=1024, window="hann")
    Puu = np.asarray(r["Puu"], dtype=float)
    coh = np.asarray(r["coherence"], dtype=float)
    h1 = np.asarray(r["H1"]["real"], dtype=float) + 1j*np.asarray(r["H1"]["imag"], dtype=float)
    h2 = np.asarray(r["H2"]["real"], dtype=float) + 1j*np.asarray(r["H2"]["imag"], dtype=float)
    mask = Puu > 1e-6 * float(np.max(Puu))
    assert np.count_nonzero(mask) > 20
    assert float(np.median(coh[mask])) > 0.999999
    assert float(np.median(np.abs(h1[mask] - 2.0))) < 1e-10
    assert float(np.median(np.abs(h2[mask] - 2.0))) < 1e-10

    # Low-noise chirp must recover the known SDOF FRF reasonably inside the excited/coherent band.
    c = chirp_frf_experiment(
        stiffness=18.0,
        damping=0.7,
        input_noise_std=0.001,
        output_noise_std=0.0002,
        duration_s=100.0,
        nperseg=1024,
        seed=20260911,
    )
    assert c["H1_error"]["valid_bins"] >= 8
    assert c["H1_error"]["median_magnitude_error_db"] is not None
    assert c["H1_error"]["median_phase_error_deg"] is not None
    assert float(c["H1_error"]["median_magnitude_error_db"]) < 3.0
    assert float(c["H1_error"]["median_phase_error_deg"]) < 35.0
    coherence = np.asarray(c["coherence"], dtype=float)
    assert np.all((coherence >= -1e-12) & (coherence <= 1.0 + 1e-12))

    # Leakage diagnostic must remain finite and localize the tone near its true frequency.
    leak = spectral_leakage_study(sample_rate_hz=128.0, samples=1024, tone_hz=10.31)
    for row in leak["rows"]:
        frac = float(row["leakage_fraction_outside_peak_pm1_bin"])
        assert 0.0 <= frac <= 1.0
        assert abs(float(row["peak_frequency_hz"]) - 10.31) <= 0.13

    print("Model Depth VIII validation: PASS")


if __name__ == "__main__":
    main()
