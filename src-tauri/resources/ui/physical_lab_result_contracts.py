"""Explicit result contracts and uncertainty objects for Physical Lab.

Contracts attach machine-readable quantity/unit/shape/role metadata to known result
schemas. Unknown schemas remain inspectable but unregistered; no scientific meaning
is guessed. Uncertainty is represented explicitly rather than inferred from field
names.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from physical_lab_experiment_kernel import plain

CONTRACT_SCHEMA = "physical-lab-result-contract-v1"
UNCERTAINTY_SCHEMA = "physical-lab-uncertainty-v1"


def _sha(value: Any) -> str:
    raw = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def field(quantity: str, *, unit: str = "", shape: str = "scalar", role: str = "observable", description: str = "") -> dict[str, Any]:
    return {"quantity": quantity, "unit": unit, "shape": shape, "role": role, "description": description}


RESULT_CONTRACTS: dict[str, dict[str, Any]] = {
    "physical-lab-pid-step-v1": {
        "domain": "control-systems",
        "fields": {
            "time_s": field("time", unit="s", shape="series", role="coordinate"),
            "position": field("position", shape="series"),
            "velocity": field("velocity", shape="series"),
            "control": field("control effort", shape="series"),
            "overshoot_pct": field("overshoot", unit="%", role="performance-metric"),
            "settling_time_s": field("settling time", unit="s", role="performance-metric"),
            "iae": field("integral absolute error", role="performance-metric"),
            "control_rms": field("control RMS", role="performance-metric"),
        },
    },
    "physical-lab-lqr-kalman-v1": {
        "domain": "control-estimation",
        "fields": {
            "time_s": field("time", unit="s", shape="series", role="coordinate"),
            "state": field("state vector", shape="matrix"),
            "state_estimate": field("estimated state vector", shape="matrix"),
            "measurement": field("measurement", shape="series"),
            "control": field("control effort", shape="series"),
            "position_estimation_rmse": field("position estimation RMSE", role="numerical-quality"),
            "velocity_estimation_rmse": field("velocity estimation RMSE", role="numerical-quality"),
            "control_rms": field("control RMS", role="performance-metric"),
            "closed_loop_eigenvalues_real": field("closed-loop eigenvalue real part", shape="series", role="stability-diagnostic"),
        },
    },
    "physical-lab-heat-cn-v1": {
        "domain": "heat-equation",
        "fields": {
            "x": field("position", unit="m", shape="series", role="coordinate"),
            "numerical": field("temperature-like field", shape="series"),
            "analytic": field("analytic reference field", shape="series", role="reference"),
            "dx": field("grid spacing", unit="m", role="discretization"),
            "dt": field("time step", unit="s", role="discretization"),
            "fourier_number": field("Fourier number", unit="1", role="stability-diagnostic"),
            "l2_error": field("L2 error", role="numerical-quality"),
            "max_error": field("maximum error", role="numerical-quality"),
        },
    },
    "physical-lab-wave-fd-v1": {
        "domain": "wave-equation",
        "fields": {
            "x": field("position", unit="m", shape="series", role="coordinate"),
            "numerical": field("wave field", shape="series"),
            "analytic": field("analytic reference field", shape="series", role="reference"),
            "dx": field("grid spacing", unit="m", role="discretization"),
            "dt": field("time step", unit="s", role="discretization"),
            "cfl": field("Courant number", unit="1", role="stability-diagnostic"),
            "l2_error": field("L2 error", role="numerical-quality"),
            "max_relative_energy_drift": field("relative energy drift", unit="1", role="numerical-quality"),
        },
    },
    "physical-lab-poisson-fd-v1": {
        "domain": "poisson-equation",
        "fields": {
            "x": field("x coordinate", shape="series", role="coordinate"),
            "y": field("y coordinate", shape="series", role="coordinate"),
            "solution": field("numerical field", shape="matrix"),
            "analytic": field("analytic reference field", shape="matrix", role="reference"),
            "grid_spacing": field("grid spacing", role="discretization"),
            "l2_error": field("L2 error", role="numerical-quality"),
            "max_error": field("maximum error", role="numerical-quality"),
            "relative_residual": field("relative linear-system residual", unit="1", role="numerical-quality"),
        },
    },
    "physical-lab-empirical-frf-v1": {
        "domain": "signal-processing",
        "fields": {
            "frequency_hz": field("frequency", unit="Hz", shape="series", role="coordinate"),
            "Puu": field("input power spectral density", shape="series"),
            "Pyy": field("output power spectral density", shape="series"),
            "coherence": field("magnitude-squared coherence", unit="1", shape="series", role="quality-diagnostic"),
            "H1": field("H1 transfer-function estimate", shape="complex-series"),
            "H2": field("H2 transfer-function estimate", shape="complex-series"),
        },
    },
    "physical-lab-chirp-frf-identification-v1": {
        "domain": "system-identification",
        "fields": {
            "time_s": field("time", unit="s", shape="series", role="coordinate"),
            "frequency_hz": field("frequency", unit="Hz", shape="series", role="coordinate"),
            "input_observed": field("observed input", shape="series"),
            "output_observed": field("observed output", shape="series"),
            "coherence": field("magnitude-squared coherence", unit="1", shape="series", role="quality-diagnostic"),
            "H1": field("H1 transfer-function estimate", shape="complex-series"),
            "H2": field("H2 transfer-function estimate", shape="complex-series"),
            "reference_H": field("reference transfer function", shape="complex-series", role="reference"),
        },
    },
}


def get_contract(schema: str | None) -> dict[str, Any] | None:
    raw = RESULT_CONTRACTS.get(str(schema or ""))
    if raw is None:
        return None
    stable = {"schema": CONTRACT_SCHEMA, "result_schema": str(schema), **plain(raw)}
    return {**stable, "contract_sha256": _sha(stable)}


def annotate_inventory(result_schema: str | None, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    contract = get_contract(result_schema)
    fields = dict((contract or {}).get("fields") or {})
    annotated = []
    matched = 0
    for row in inventory:
        out = dict(row)
        meta = fields.get(str(row.get("path") or ""))
        if meta:
            matched += 1
            out.update({
                "contract_registered": True,
                "quantity": meta.get("quantity"),
                "unit": meta.get("unit"),
                "expected_shape": meta.get("shape"),
                "role": meta.get("role") or out.get("role"),
                "description": meta.get("description") or "",
            })
        else:
            out["contract_registered"] = False
        annotated.append(out)
    return {
        "registered": contract is not None,
        "contract": contract,
        "matched_fields": matched,
        "inventory": annotated,
        "boundary": "Registered metadata is explicit schema metadata. Unregistered fields remain visible but their scientific quantity/unit is not inferred.",
    }


def make_uncertainty(
    *,
    estimate: float,
    unit: str = "",
    standard_uncertainty: float | None = None,
    coverage_factor: float | None = None,
    interval: tuple[float, float] | None = None,
    coverage_probability: float | None = None,
    method: str,
    components: list[Mapping[str, Any]] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    est = float(estimate)
    if not math.isfinite(est):
        raise ValueError("estimate must be finite")
    su = None if standard_uncertainty is None else float(standard_uncertainty)
    if su is not None and (not math.isfinite(su) or su < 0):
        raise ValueError("standard_uncertainty must be finite and non-negative")
    k = None if coverage_factor is None else float(coverage_factor)
    if k is not None and (not math.isfinite(k) or k <= 0):
        raise ValueError("coverage_factor must be finite and positive")
    iv = None
    if interval is not None:
        lo, hi = float(interval[0]), float(interval[1])
        if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
            raise ValueError("interval must be finite and ordered")
        iv = [lo, hi]
    cp = None if coverage_probability is None else float(coverage_probability)
    if cp is not None and not (0 < cp <= 1):
        raise ValueError("coverage_probability must lie in (0,1]")
    if not str(method).strip():
        raise ValueError("uncertainty method is required")
    stable = {
        "schema": UNCERTAINTY_SCHEMA,
        "estimate": est,
        "unit": str(unit),
        "standard_uncertainty": su,
        "coverage_factor": k,
        "interval": iv,
        "coverage_probability": cp,
        "method": str(method).strip(),
        "components": plain(list(components or [])),
        "notes": str(notes),
    }
    return {**stable, "uncertainty_sha256": _sha(stable)}


def validate_uncertainty(value: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if value.get("schema") != UNCERTAINTY_SCHEMA:
        errors.append("unexpected uncertainty schema")
    try:
        rebuilt = make_uncertainty(
            estimate=value.get("estimate"), unit=str(value.get("unit") or ""),
            standard_uncertainty=value.get("standard_uncertainty"),
            coverage_factor=value.get("coverage_factor"),
            interval=tuple(value.get("interval")) if value.get("interval") is not None else None,
            coverage_probability=value.get("coverage_probability"),
            method=str(value.get("method") or ""), components=list(value.get("components") or []), notes=str(value.get("notes") or ""),
        )
        supplied = str(value.get("uncertainty_sha256") or "")
        if supplied and supplied != rebuilt["uncertainty_sha256"]:
            errors.append("uncertainty_sha256 does not match content")
    except Exception as exc:
        errors.append(str(exc))
    return {"valid": not errors, "errors": errors, "boundary": "Structural uncertainty-object validation only; it does not establish completeness or correctness of the uncertainty model."}
