from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

import physical_lab_project_kernel as projects
from physical_lab_project_interop import build_reproducibility_pack, dataset_csv_bytes, list_canonical_datasets, save_canonical_dataset


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        project_dir, project = projects.create_project("Interop Validation", research_question="Can project datasets and packs remain reproducible?")

        columns = {"time_s": [0.0, 0.5, 1.0], "signal": [1.0, None, 3.0]}
        a = save_canonical_dataset(project_dir, name="shared-table", profile="numerical-methods", columns=columns, units={"time_s": "s", "signal": "V"}, source="synthetic.csv")
        b = save_canonical_dataset(project_dir, name="shared-table", profile="numerical-methods", columns=columns, units={"time_s": "s", "signal": "V"}, source="synthetic.csv")
        assert a["dataset_id"] == b["dataset_id"]
        assert a["sha256"] == b["sha256"]

        rows = list_canonical_datasets(project_dir)
        assert rows and rows[0]["dataset_id"] == a["dataset_id"]
        data = dataset_csv_bytes(rows[0])
        parsed = list(csv.reader(io.StringIO(data.decode("utf-8"))))
        header = parsed[0]
        assert set(header) == {"time_s", "signal"}
        by_name = {name: idx for idx, name in enumerate(header)}
        assert parsed[1][by_name["time_s"]] == "0.0"
        assert parsed[1][by_name["signal"]] == "1.0"
        assert parsed[2][by_name["time_s"]] == "0.5"
        assert parsed[2][by_name["signal"]] == ""
        assert parsed[3][by_name["time_s"]] == "1.0"
        assert parsed[3][by_name["signal"]] == "3.0"

        p1 = build_reproducibility_pack(project_dir)
        p2 = build_reproducibility_pack(project_dir)
        assert p1["zip_sha256"] == p2["zip_sha256"]
        assert p1["bytes"] == p2["bytes"]

        with zipfile.ZipFile(io.BytesIO(p1["bytes"]), "r") as zf:
            names = set(zf.namelist())
            assert "project.json" in names
            assert "PROJECT_REPORT.md" in names
            assert "REPRODUCIBILITY_MANIFEST.json" in names
            manifest = json.loads(zf.read("REPRODUCIBILITY_MANIFEST.json"))
            for entry in manifest["files"]:
                payload = zf.read(entry["path"])
                assert hashlib.sha256(payload).hexdigest() == entry["sha256"]
                assert len(payload) == entry["size_bytes"]

    print("Project interop validation: PASS")


if __name__ == "__main__":
    main()
