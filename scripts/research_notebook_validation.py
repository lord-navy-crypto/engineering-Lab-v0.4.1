#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PHYSICAL_LAB_DATA_DIR"] = tmp
        import physical_lab_project_kernel as projects
        from physical_lab_lab_journey import list_events, verify_journey
        from physical_lab_project_interop import build_reproducibility_pack
        from physical_lab_research_notebook import (
            add_annotation,
            add_notebook_entry,
            list_annotations,
            list_notebook_entries,
            verify_record,
        )

        project_dir, _ = projects.create_project("Notebook Validation")
        note = add_notebook_entry(
            project_dir,
            kind="hypothesis",
            title="Sampling-rate hypothesis",
            text="If the apparent variation is sampling-limited, increasing the rate should change the observed spectrum.",
            evidence_refs=["dataset-test"],
            tags=["sampling", "hypothesis"],
        )
        record = note["entry"]
        require(verify_record(record)["valid"], "notebook SHA/ID verification failed")
        require(record["evidence_refs"] == ["dataset-test"], "notebook evidence ref changed")
        require(note["journey_event"]["event_type"] == "hypothesis", "notebook did not create hypothesis journey event")

        annotation = add_annotation(
            project_dir,
            target_type="dataset",
            target_id="dataset-test",
            label="Possible transient",
            note="Review the first 0.2 s separately.",
            locator={"time_s": [0.0, 0.2]},
            tags=["transient"],
        )
        ann = annotation["annotation"]
        require(verify_record(ann)["valid"], "annotation SHA/ID verification failed")
        require(ann["target"]["id"] == "dataset-test", "annotation target changed")
        require(ann["locator"]["time_s"] == [0.0, 0.2], "annotation locator changed")
        require(annotation["journey_event"]["event_type"] == "annotation", "annotation did not create journey event")

        require(len(list_notebook_entries(project_dir)) == 1, "wrong notebook entry count")
        require(len(list_annotations(project_dir)) == 1, "wrong annotation count")
        journey = list_events(project_dir)
        require(len(journey) == 2, "notebook/annotation did not mirror into Lab Journey")
        require(verify_journey(project_dir)["valid"], "journey chain invalid after notebook operations")

        pack = build_reproducibility_pack(project_dir)
        paths = {row["path"] for row in pack["manifest"]["files"]}
        require(any(p.startswith("notebook/") for p in paths), "notebook record missing from reproducibility pack")
        require(any(p.startswith("annotations/") for p in paths), "annotation record missing from reproducibility pack")
        require(any(p.startswith("journey/events/") for p in paths), "journey events missing from reproducibility pack")

    print("PASS: Experiment Notebook, annotations, Journey linkage and reproducibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
