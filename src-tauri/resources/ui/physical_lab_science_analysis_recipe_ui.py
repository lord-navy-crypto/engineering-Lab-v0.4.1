"""Small reusable controls for saving reproducible Science Analysis recipes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from physical_lab_visual_analytics import save_science_analysis_recipe


def render_save_recipe(
    st: Any,
    project_path: Path,
    *,
    profile: str,
    source: Mapping[str, Any],
    analysis: Mapping[str, Any],
    key_suffix: str,
) -> None:
    source_identity = dict(source.get("identity") or {})
    source_identity.setdefault("source_id", str(source.get("id") or ""))
    source_identity.setdefault("source_kind", str(source.get("kind") or ""))
    if st.button("Save Science Analysis Recipe", key=f"pl_science_recipe_{profile}_{key_suffix}"):
        try:
            saved = save_science_analysis_recipe(project_path, source_identity=source_identity, analysis=dict(analysis))
            st.success(f"Saved {saved['recipe_id']} · sha256 {saved['sha256'][:16]}…")
        except Exception as exc:
            st.error(f"Could not save Science Analysis Recipe: {exc}")
