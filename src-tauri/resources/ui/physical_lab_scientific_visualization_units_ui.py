"""Unit-aware and native-UQ views for Engineering Lab Scientific Visualization."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from physical_lab_scientific_visualization import (
    axis_label,
    contract_field_metadata,
    convert_series,
    convertible_units,
    field_metadata,
    uncertainty_plot_record,
    uncertainty_records,
)
from physical_lab_visualization_studio import numeric_columns


def render_units_uq(st: Any, source: dict[str, Any], result: dict[str, Any] | None, profile: str) -> None:
    tab_units, tab_uq = st.tabs(["Unit-aware fields", "Explicit uncertainty"])
    with tab_units:
        frame: pd.DataFrame = source["frame"]
        numeric = numeric_columns(frame)
        if result is None:
            st.info("This source has no registered result contract in this view. Units are not inferred from field names.")
            st.dataframe(pd.DataFrame({"field": numeric, "unit": ["unspecified"] * len(numeric)}), hide_index=True, width="stretch")
        else:
            metadata = contract_field_metadata(result)
            rows = []
            for field in numeric:
                clean = field[2:] if field.startswith("$.") else field
                meta = field_metadata(result, clean)
                rows.append({"frame_field": field, **meta})
            st.dataframe(rows, hide_index=True, width="stretch")
            if not metadata:
                st.warning("The result schema is unregistered; scientific quantity/unit metadata was not guessed.")
            registered = [r for r in rows if r.get("registered") and r.get("unit") and r.get("frame_field") in frame.columns]
            if registered:
                selected = st.selectbox("Field for converted display", [r["frame_field"] for r in registered], key=f"pl_sv_unit_field_{profile}")
                row = next(r for r in registered if r["frame_field"] == selected)
                original = str(row.get("unit") or "")
                targets = convertible_units(original) or [original]
                target = st.selectbox("Display unit", targets, key=f"pl_sv_unit_target_{profile}")
                values = convert_series(frame[selected].tolist(), original, target)
                preview = pd.DataFrame({"row": list(range(len(values))), axis_label(selected, target): values})
                st.line_chart(preview.set_index("row"), height=320)
                st.caption(f"Display conversion only: {original} → {target}. Stored evidence is unchanged.")
            else:
                st.caption("No current numeric field has an explicit convertible unit in the registered contract.")

    with tab_uq:
        if result is None:
            st.info("Select a Project result to inspect physical-lab-uncertainty-v1 objects.")
            return
        records = uncertainty_records(result)
        if not records:
            st.info("No explicit uncertainty object is present. Error/residual fields are not reinterpreted as uncertainty.")
            return
        st.dataframe(records, hide_index=True, width="stretch")
        valid = [r for r in records if r.get("valid")]
        if not valid:
            st.warning("Uncertainty objects were found, but none passed structural validation.")
            return
        path = st.selectbox("Uncertainty object", [str(r["path"]) for r in valid], key=f"pl_sv_uq_path_{profile}")
        record = next(r for r in valid if str(r["path"]) == path)
        plotted = uncertainty_plot_record(record)
        error_y = None
        if plotted.get("error_plus") is not None:
            error_y = {"type": "data", "array": [plotted["error_plus"]], "arrayminus": [plotted["error_minus"]], "visible": True}
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[path], y=[plotted["estimate"]], mode="markers", marker={"size": 12}, error_y=error_y, name=str(record.get("method") or "UQ")))
        fig.update_layout(height=430, yaxis_title=axis_label("estimate", plotted.get("unit")), title=f"Explicit UQ · {plotted['kind']}")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        st.json({"method": record.get("method"), "coverage_factor": record.get("coverage_factor"), "coverage_probability": record.get("coverage_probability"), "sha256": record.get("sha256")})
        st.caption("Structural validity does not establish completeness or correctness of the uncertainty model.")
