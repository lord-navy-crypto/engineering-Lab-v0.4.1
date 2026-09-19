#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    import physical_lab_visual_analytics as va

    require(va.unit_comparability("m", "mm")["status"] == "CONVERTIBLE", "convertible units not recognized")
    require(va.unit_comparability("m", "s")["status"] == "INCOMPATIBLE", "incompatible units not rejected")
    require(va.unit_comparability("", "m")["status"] == "UNSPECIFIED", "missing unit status failed")

    frame = pd.DataFrame({"p": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0]})
    elastic = va.elasticity_sensitivity(frame, "p", "y")
    require(len(elastic) == 3, "elasticity row count failed")
    require(all(abs(float(x) - 1.0) < 1e-12 for x in elastic["elasticity"]), "elasticity calculation failed")

    grid = pd.DataFrame({"a": [0, 0, 1, 1], "b": [0, 1, 0, 1], "z": [1.0, 2.0, 3.0, 4.0]})
    surface = va.response_surface(grid, "a", "b", "z")
    xs = va.response_surface_slice(surface, axis="x", index=0)
    ys = va.response_surface_slice(surface, axis="y", index=1)
    require(len(xs) == 2 and len(ys) == 2, "response-surface slice failed")

    source = {"dataset_id": "fixture", "sha256": "abc"}
    analysis = {"kind": "sensitivity", "parameter": "p", "output": "y"}
    id1, sha1 = va.science_analysis_identity(source, analysis)
    id2, sha2 = va.science_analysis_identity(source, analysis)
    require(id1 == id2 and sha1 == sha2, "science recipe identity is not deterministic")

    with tempfile.TemporaryDirectory() as tmp:
        saved = va.save_science_analysis_recipe(Path(tmp), source_identity=source, analysis=analysis)
        path = Path(saved["path"])
        require(path.exists(), "science recipe was not written")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        require(loaded["recipe_id"] == id1 and loaded["sha256"] == sha1, "science recipe content mismatch")

    print("PASS: unit comparability, elasticity, surface slices and science analysis recipes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
