#!/usr/bin/env python3
from pathlib import Path

path = Path("src-tauri/resources/ui/physical_lab_visual_analytics_ui.py")
text = path.read_text(encoding="utf-8")
old = '            "rows": len(source.get("frame") or []),\n'
new = '            "rows": len(source["frame"]) if source.get("frame") is not None else 0,\n'
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected one Visual Analytics frame metadata expression, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Visual Analytics DataFrame metadata handling fixed.")
