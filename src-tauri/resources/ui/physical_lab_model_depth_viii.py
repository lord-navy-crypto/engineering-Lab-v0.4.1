"""Eighth-wave model-depth studies: signal processing and empirical system identification.

Adds bounded frequency-domain diagnostics for measured-like input/output time series:
- Welch auto/cross spectra and magnitude-squared coherence.
- H1/H2 empirical transfer-function estimators with explicit cross-spectrum convention.
- Chirp-driven SDOF benchmark against the known continuous-time compliance FRF.
- Window/leakage comparison for off-bin tones.

These are finite-record signal-processing diagnostics, not hardware calibration or experimental validation.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
from scipy import signal


def _plain(v: Any) -> Any:
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, complex):
        return {"real": float(v.real), "imag": float(v.imag)}
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        if np.iscomplexobj(v):
            return {"real": v.real.tolist(), "imag": v.imag.tolist()}
        return [_plain(x) for x in v.tolist()]
    if hasattr(v, "item"):
        try:
            return _plain(v.item())
        except Exception:
            pass
    return v


def empirical_transfer_function(
    input_signal: Sequence[float],
    output_signal: Sequence[float],
    *,
    sample_rate_hz: float,
    nperseg: int = 1024,
    overlap_fraction: float = 0.5,
    window: str = "hann",
) -> dict[str, Any]:
    """Estimate Welch spectra, coherence, H1 and H2 FRFs.

    scipy.signal.csd(x, y) uses Pxy = conj(X) Y. With input u and output y:
      H1 = Puy / Puu
      H2 = Pyy / Pyu
    where Pyu = conj(Y) U. For y = H u and ideal noiseless data, both recover H.
    """
    u = np.asarray(input_signal, dtype=float)
    y = np.asarray(output_signal, dtype=float)
    fs = float(sample_rate_hz)
    if u.ndim != 1 or y.ndim != 1 or len(u) != len(y) or len(u) < 128:
        raise ValueError("input/output must be paired 1-D series with at least 128 samples")
    if not (np.all(np.isfinite(u)) and np.all(np.isfinite(y))) or fs <= 0:
        raise ValueError("input/output and sample rate must be finite; sample rate must be positive")
    seg = max(64, min(int(nperseg), len(u)))
    overlap = max(0, min(int(round(seg * float(overlap_fraction))), seg - 1))
    common = dict(fs=fs, window=window, nperseg=seg, noverlap=overlap, detrend="constant", scaling="density")
    f, Puu = signal.welch(u, **common)
    _, Pyy = signal.welch(y, **common)
    _, Puy = signal.csd(u, y, **common)
    _, Pyu = signal.csd(y, u, **common)
    floor = max(float(np.max(Puu)) * 1e-14, 1e-30)
    H1 = Puy / np.maximum(Puu, floor)
    denom_h2 = Pyu.copy()
    small = np.abs(denom_h2) < max(float(np.max(np.abs(Pyu))) * 1e-14, 1e-30)
    denom_h2[small] = np.nan + 1j * np.nan
    H2 = Pyy / denom_h2
    coherence = np.abs(Puy) ** 2 / np.maximum(Puu * Pyy, floor * floor)
    coherence = np.clip(np.real(coherence), 0.0, 1.0)
    segment_count_approx = 1 if len(u) <= seg else 1 + max(0, (len(u) - seg) // max(seg - overlap, 1))
    return _plain({
        "schema": "physical-lab-empirical-frf-v1",
        "frequency_hz": f,
        "Puu": Puu,
        "Pyy": Pyy,
        "Puy": Puy,
        "H1": H1,
        "H2": H2,
        "coherence": coherence,
        "nperseg": seg,
        "noverlap": overlap,
        "window": window,
        "approx_segment_count": int(segment_count_approx),
        "boundary": (
            "Welch finite-record spectral estimates. Cross-spectrum convention is Pxy=conj(X)Y; H1=Puy/Puu and H2=Pyy/Pyu. "
            "Estimator bias depends on input/output noise, leakage, stationarity, record length, window and segment averaging."
        ),
    })


def chirp_frf_experiment(
    *,
    mass: float = 1.0,
    stiffness: float = 18.0,
    damping: float = 0.7,
    sample_rate_hz: float = 100.0,
    duration_s: float = 80.0,
    f_start_hz: float = 0.15,
    f_stop_hz: float = 2.5,
    input_noise_std: float = 0.01,
    output_noise_std: float = 0.002,
    nperseg: int = 1024,
    window: str = "hann",
    seed: int = 20260911,
) -> dict[str, Any]:
    """Drive a linear SDOF oscillator with a chirp and estimate its empirical FRF."""
    m, k, c = float(mass), float(stiffness), float(damping)
    fs, duration = float(sample_rate_hz), float(duration_s)
    f0, f1 = float(f_start_hz), float(f_stop_hz)
    if min(m, k, fs, duration, f0, f1) <= 0 or c < 0 or f1 <= f0 or f1 >= 0.45 * fs:
        raise ValueError("invalid oscillator, timing, or chirp parameters")
    n = int(round(fs * duration))
    n = max(1000, min(n, 300000))
    t = np.arange(n, dtype=float) / fs
    u_true = signal.chirp(t, f0=f0, f1=f1, t1=t[-1], method="linear", phi=0.0)
    A = np.asarray([[0.0, 1.0], [-k / m, -c / m]], dtype=float)
    B = np.asarray([[0.0], [1.0 / m]], dtype=float)
    C = np.asarray([[1.0, 0.0]], dtype=float)
    D = np.asarray([[0.0]], dtype=float)
    Ad, Bd, Cd, Dd, dt = signal.cont2discrete((A, B, C, D), 1.0 / fs, method="zoh")
    _, y_true, _ = signal.dlsim((Ad, Bd, Cd, Dd, dt), u_true, t=t)
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    rng = np.random.default_rng(int(seed))
    u_obs = u_true + rng.normal(scale=float(input_noise_std), size=n)
    y_obs = y_true + rng.normal(scale=float(output_noise_std), size=n)
    frf = empirical_transfer_function(
        u_obs, y_obs, sample_rate_hz=fs, nperseg=int(nperseg), overlap_fraction=0.5, window=str(window)
    )
    f = np.asarray(frf["frequency_hz"], dtype=float)
    H1 = np.asarray(frf["H1"]["real"], dtype=float) + 1j * np.asarray(frf["H1"]["imag"], dtype=float)
    H2 = np.asarray(frf["H2"]["real"], dtype=float) + 1j * np.asarray(frf["H2"]["imag"], dtype=float)
    coh = np.asarray(frf["coherence"], dtype=float)
    omega = 2.0 * math.pi * f
    href = 1.0 / (k - m * omega * omega + 1j * c * omega)
    band = (f >= f0) & (f <= f1) & (coh >= 0.5) & np.isfinite(H1) & np.isfinite(H2)
    def metrics(hhat: np.ndarray) -> dict[str, Any]:
        if np.count_nonzero(band) < 3:
            return {"valid_bins": int(np.count_nonzero(band)), "median_magnitude_error_db": None, "median_phase_error_deg": None}
        ratio = np.abs(hhat[band]) / np.maximum(np.abs(href[band]), 1e-30)
        mag_err = 20.0 * np.log10(np.maximum(ratio, 1e-30))
        phase_err = np.angle(hhat[band] / href[band], deg=True)
        return {
            "valid_bins": int(np.count_nonzero(band)),
            "median_magnitude_error_db": float(np.median(np.abs(mag_err))),
            "median_phase_error_deg": float(np.median(np.abs(phase_err))),
        }
    natural_hz = math.sqrt(k / m) / (2.0 * math.pi)
    return _plain({
        "schema": "physical-lab-chirp-frf-identification-v1",
        "time_s": t,
        "input_observed": u_obs,
        "output_observed": y_obs,
        "truth": {"mass": m, "stiffness": k, "damping": c, "natural_frequency_hz": natural_hz},
        "chirp_band_hz": [f0, f1],
        "frequency_hz": f,
        "H1": H1,
        "H2": H2,
        "reference_H": href,
        "coherence": coh,
        "H1_error": metrics(H1),
        "H2_error": metrics(H2),
        "spectral_settings": {"nperseg": frf["nperseg"], "noverlap": frf["noverlap"], "window": frf["window"], "approx_segment_count": frf["approx_segment_count"]},
        "boundary": (
            "Synthetic chirp-driven linear SDOF benchmark. H1/H2 are empirical finite-record estimates compared with the known continuous compliance FRF. "
            "Agreement is evaluated only inside the excited band at coherence >= 0.5; this is not a measured hardware identification result."
        ),
    })


def spectral_leakage_study(
    *, sample_rate_hz: float = 128.0, samples: int = 1024, tone_hz: float = 10.37
) -> dict[str, Any]:
    """Compare leakage for rectangular and Hann windows on an off-bin sinusoid."""
    fs = float(sample_rate_hz); n = max(128, min(int(samples), 32768)); f0 = float(tone_hz)
    if fs <= 0 or not (0 < f0 < 0.5 * fs):
        raise ValueError("invalid sample rate or tone")
    t = np.arange(n) / fs; x = np.sin(2.0 * math.pi * f0 * t)
    rows = []
    for name, win in [("boxcar", np.ones(n)), ("hann", np.hanning(n))]:
        spec = np.abs(np.fft.rfft(x * win)) ** 2
        freq = np.fft.rfftfreq(n, 1.0 / fs)
        peak = int(np.argmax(spec)); lo = max(0, peak - 1); hi = min(len(spec), peak + 2)
        total = float(np.sum(spec)); main = float(np.sum(spec[lo:hi])); leakage = max(total - main, 0.0) / max(total, 1e-30)
        rows.append({"window": name, "peak_frequency_hz": float(freq[peak]), "leakage_fraction_outside_peak_pm1_bin": leakage})
    return _plain({
        "schema": "physical-lab-window-leakage-v1",
        "sample_rate_hz": fs, "samples": n, "tone_hz": f0, "rows": rows,
        "boundary": "Single finite off-bin tone benchmark. Leakage fraction depends on the chosen main-lobe bin definition; window choice trades sidelobe leakage against main-lobe width and amplitude scaling."
    })
