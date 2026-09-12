# BetterBoard Research Bridge v1

`betterboard.research-bridge/1.0` is the interchange contract between BetterBoard Studio, Engineering Lab, and OpenPenguin.

The bridge is intentionally provenance-first. Raw BetterBoard measurement evidence is not replaced by Engineering Lab analysis or OpenPenguin suggestions.

## Layer model

1. **Evidence** — raw measurement files, metadata, hardware target provenance, firmware identity.
2. **Research context** — Experiment Notebook entries, annotations, hypotheses, decisions, and Lab Journey events.
3. **Engineering analysis** — Engineering Lab imports and derived results such as models, fits, residuals, simulations, and validation warnings.
4. **AI advisory** — OpenPenguin explanations, anomaly candidates, questions, and proposed next experiments.

## Required top-level fields

- `schema` = `betterboard.research-bridge/1.0`
- `session_id`
- `created_at_utc`
- `producer`
- `experiment`
- `hardware`
- `evidence`
- `research_context`
- `engineering_lab`
- `ai`
- `provenance`

Every contextual event should preserve an `origin` such as `human`, `betterboard`, `engineering-lab`, or `openguin`, and a `kind` such as `measurement`, `observation`, `analysis`, `annotation`, `hypothesis`, `suggestion`, `warning`, or `decision`.

## Engineering Lab import rule

Engineering Lab may read BetterBoard evidence and append derived records to `engineering_lab.results`. It must not rewrite the raw evidence references or represent a derived value as a direct sensor measurement.

A successful import means the package is structurally valid and traceable. It does **not** establish calibration, physical correctness, or model validity.

## OpenPenguin rule

OpenPenguin may inspect selected Research Bridge context and append advisory records to `ai.suggestions`. AI output must remain visibly distinguishable from measurements and validated Engineering Lab results.

Use `scripts/betterboard_research_bridge_v1.py` to validate a bridge package before import.
