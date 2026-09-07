# BetterBoard Magnet Bench → Engineering Lab bridge

Engineering Lab can independently validate the numerical field-comparison evidence produced by BetterBoard Magnet Bench 03.

```text
real magnet
  ↓
BetterBoard Magnet Bench 01 — vector acquisition
  ↓
Magnet Bench 02 — baseline / repeatability / B(position)
  ↓
Magnet Bench 03 — RADIA/model comparison
  ↓
magnet03_residuals.csv + physical_lab_field_bridge.json
  ↓
Engineering Lab independent recomputation
```

Run from the Engineering Lab repository:

```bash
python3 scripts/betterboard_magnet_bridge_validation.py \
  /path/to/magnet03_residuals.csv \
  --bridge /path/to/physical_lab_field_bridge.json
```

The validator uses the canonical `physical_lab_digital_twin.py` definitions for:

- `compare_field_series`
- `fit_model_affine`
- `suggest_residual_measurement_points`

It recomputes MAE, RMSE, bias, maximum residual, relative RMSE, R², peaks, field integrals, residual spread and affine discrepancy fit from the residual CSV rather than trusting BetterBoard's summary.

`PASS` means the two applications reproduced the same numerical comparison for the supplied rows. It does not establish sensor calibration, traceable position, magnet geometry/material correctness, or RADIA model validity.
