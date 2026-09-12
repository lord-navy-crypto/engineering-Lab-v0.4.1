"""UI for project-level data bridge and reproducibility packaging."""
from __future__ import annotations
from pathlib import Path
from typing import Any

import physical_lab_project_kernel as projects
from physical_lab_project_interop import (
    build_reproducibility_pack,
    dataset_csv_bytes,
    list_canonical_datasets,
    save_canonical_dataset,
)


def render_project_interop(st: Any, profile: str) -> None:
    active = str(st.session_state.get(projects.ACTIVE_PROJECT_SESSION_KEY) or "")
    if not active:
        return
    project_path = Path(active)
    if not (project_path / "project.json").exists():
        return

    st.markdown("---")
    with st.expander("Physical Lab · Project Data Bridge & Reproducibility", expanded=False):
        st.caption("Promote numeric tables into reusable project datasets and export a portable provenance pack. These are transport/reproducibility tools, not scientific validation.")
        tab_data, tab_pack = st.tabs(["Data Bridge", "Reproducibility Pack"])

        with tab_data:
            parsed = st.session_state.get(f"pl_orch_table_{profile}")
            if parsed:
                st.markdown("#### Promote current numeric table")
                numeric = list(parsed.get("numeric_columns") or [])
                selected = st.multiselect("Columns", numeric, default=numeric, key=f"pl_bridge_cols_{profile}")
                c1,c2 = st.columns(2)
                name = c1.text_input("Dataset name", value=f"{profile}-dataset", key=f"pl_bridge_name_{profile}")
                notes = c2.text_input("Notes", value="", key=f"pl_bridge_notes_{profile}")
                unit_text = st.text_input("Units (optional, comma-separated column=unit)", value="", key=f"pl_bridge_units_{profile}")
                units = {}
                for part in unit_text.split(","):
                    if "=" in part:
                        k,v = part.split("=",1); units[k.strip()] = v.strip()
                if st.button("Promote table to project dataset", type="primary", disabled=not selected, key=f"pl_bridge_save_{profile}"):
                    cols = {k: parsed["column_data"][k] for k in selected}
                    rec = save_canonical_dataset(project_path, name=name, profile=profile, columns=cols, units=units, source=str(parsed.get("filename") or ""), notes=notes)
                    st.success(f"Saved {rec['dataset_id']} · sha256 {rec['sha256'][:12]}…")
                    st.rerun()
            else:
                st.info("Parse a CSV/TSV in Research Orchestrator first to promote it into a reusable project dataset.")

            datasets = list_canonical_datasets(project_path)
            if datasets:
                st.markdown("#### Project datasets")
                st.dataframe([
                    {"id":d.get("dataset_id"),"name":d.get("name"),"source_profile":d.get("profile"),"rows":d.get("row_count"),"columns":len(d.get("columns") or {}),"sha256":str(d.get("sha256") or "")[:16]}
                    for d in datasets
                ], hide_index=True, width="stretch")
                ids=[d["dataset_id"] for d in datasets]
                chosen=st.selectbox("Inspect / export dataset",ids,key=f"pl_bridge_pick_{profile}")
                dataset=next(d for d in datasets if d["dataset_id"]==chosen)
                st.json({k:v for k,v in dataset.items() if k not in {"columns","file_path"}})
                st.dataframe([
                    {k:(dataset["columns"][k][i] if i < len(dataset["columns"][k]) else None) for k in dataset["columns"]}
                    for i in range(min(int(dataset.get("row_count") or 0),100))
                ], hide_index=True, width="stretch")
                st.download_button("Download canonical dataset CSV", data=dataset_csv_bytes(dataset), file_name=f"{dataset.get('name','dataset')}.csv", mime="text/csv", key=f"pl_bridge_download_{profile}_{chosen}")
            else:
                st.caption("No canonical project datasets yet.")

        with tab_pack:
            st.markdown("#### Portable reproducibility package")
            include_assets = st.checkbox("Include raw measurement assets up to 8 MB each", value=False, key=f"pl_repro_assets_{profile}")
            st.caption("Default pack includes measurement/calibration metadata, experiments, result references, evidence/provenance, reports, project datasets, and a generated project report. Large external solver artifacts are not embedded.")
            if st.button("Build reproducibility ZIP", type="primary", key=f"pl_repro_build_{profile}"):
                st.session_state[f"pl_repro_pack_{profile}"] = build_reproducibility_pack(project_path, include_measurement_assets=include_assets)
            pack = st.session_state.get(f"pl_repro_pack_{profile}")
            if pack:
                a,b,c=st.columns(3)
                a.metric("Pack files", pack["file_count"])
                b.metric("ZIP size", f"{pack['size_bytes']/1024:.1f} KiB")
                c.metric("ZIP sha256", pack["zip_sha256"][:16]+"…")
                if pack["manifest"].get("omitted"):
                    st.warning(f"Omitted {len(pack['manifest']['omitted'])} oversized file(s); inspect manifest for details.")
                st.download_button("Download reproducibility pack", data=pack["bytes"], file_name=pack["filename"], mime="application/zip", key=f"pl_repro_download_{profile}")
                st.json({k:v for k,v in pack["manifest"].items() if k != "files"})
                st.caption(pack["boundary"])
