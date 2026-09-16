#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all_expected(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"Expected {expected} matches in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


self_check = ROOT / "scripts" / "self_check.py"
replace_once(self_check, "assert len(mods) == 13, f'Expected 13 modules, found {len(mods)}'", "assert len(mods) == 14, f'Expected 14 modules, found {len(mods)}'")
replace_once(self_check, "assert sum(m['kind']=='lab' for m in mods) == 10", "assert sum(m['kind']=='lab' for m in mods) == 11")
replace_once(self_check, "bundled_ids={'kerr-geodesics','solar-system-dynamics','honeycomb-lattice'}", "bundled_ids={'kerr-geodesics','solar-system-dynamics','honeycomb-lattice','rotating-utube'}")
replace_once(
    self_check,
    "for profile in ['kerr-geodesics','solar-system-dynamics','honeycomb-lattice']:\n    assert profile in ui_base, profile",
    "for profile in ['kerr-geodesics','solar-system-dynamics','honeycomb-lattice','rotating-utube']:\n    assert profile in ui_base, profile",
)
# Rust uses one generic bundled-Lab path. Do not require a per-profile rotating-utube literal there.
replace_all_expected(self_check, "print('Modules: 13 (10 labs + 3 runtime/builders)')", "print('Modules: 14 (11 labs + 3 runtime/builders)')", 1)
replace_all_expected(self_check, "print('Top-level Labs: 10')", "print('Top-level Labs: 11')", 2)

ui_base = ROOT / "src-tauri" / "resources" / "ui" / "physical_lab_sitecustomize_base.py"
replace_once(
    ui_base,
    '    "honeycomb-lattice",\n    "radiation-platform",',
    '    "honeycomb-lattice",\n    "rotating-utube",\n    "radiation-platform",',
)

print("Applied U-Tube catalog/self-check contract patch.")
