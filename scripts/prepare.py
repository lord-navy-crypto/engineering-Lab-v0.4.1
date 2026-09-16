#!/usr/bin/env python3
from pathlib import Path
from shutil import copy2
import json

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DIST = ROOT / "dist"
ICONS = ROOT / "src-tauri" / "icons"
SURFACES = ROOT / "src-tauri" / "resources" / "surfaces.json"
HOME_LAYOUT = ROOT / "src-tauri" / "resources" / "home_layout.json"
DIST.mkdir(parents=True, exist_ok=True)
ICONS.mkdir(parents=True, exist_ok=True)

for name in ("index.html", "styles.css", "app.js"):
    copy2(WEB / name, DIST / name)

# Keep native navigation sources isolated for review, then concatenate them into
# the existing classic app.js bundle. Canonical JSON manifests are embedded as
# inert data so Home, Workbench and search share one source of truth without a
# parallel Rust registry or a second frontend build system.
workbench = WEB / "surface_catalog.js"
launcher = WEB / "capability_launcher.js"
home_progressive = WEB / "home_progressive.js"
if workbench.is_file() and SURFACES.is_file():
    rows = json.loads(SURFACES.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise SystemExit("src-tauri/resources/surfaces.json must be a non-empty JSON array")
    home_layout = {}
    if HOME_LAYOUT.is_file():
        home_layout = json.loads(HOME_LAYOUT.read_text(encoding="utf-8"))
        if not isinstance(home_layout, dict):
            raise SystemExit("src-tauri/resources/home_layout.json must be a JSON object")
    app_bundle = DIST / "app.js"
    base = app_bundle.read_text(encoding="utf-8")
    launcher_source = launcher.read_text(encoding="utf-8") if launcher.is_file() else ""
    home_source = home_progressive.read_text(encoding="utf-8") if home_progressive.is_file() else ""
    workbench_source = workbench.read_text(encoding="utf-8")
    catalog_js = "window.__PHYSICAL_LAB_SURFACES__ = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n"
    home_js = "window.__PHYSICAL_LAB_HOME_LAYOUT__ = " + json.dumps(home_layout, ensure_ascii=False, separators=(",", ":")) + ";\n"
    app_bundle.write_text(
        base.rstrip()
        + "\n\n/* Native Engineering navigation metadata */\n"
        + catalog_js
        + home_js
        + ("\n/* Shared native capability launcher */\n" + launcher_source if launcher_source else "")
        + ("\n/* First-principles progressive Home + unified discovery */\n" + home_source if home_source else "")
        + "\n/* Native Engineering Workbench */\n"
        + workbench_source
        + "\n",
        encoding="utf-8",
    )

# Icons are committed with the source package. Regenerate only when missing.
if not (ICONS / "icon.icns").exists():
    try:
        from PIL import Image, ImageDraw
        size = 1024
        img = Image.new("RGBA", (size, size), (14, 18, 28, 255))
        d = ImageDraw.Draw(img)
        pad = 100
        d.rounded_rectangle((pad, pad, size-pad, size-pad), radius=210, fill=(27, 34, 49, 255))
        center = (size//2, size//2)
        for w, h, angle in [(620, 250, 0), (620, 250, 60), (620, 250, 120)]:
            layer = Image.new("RGBA", (size, size), (0,0,0,0))
            ld = ImageDraw.Draw(layer)
            box=(center[0]-w//2, center[1]-h//2, center[0]+w//2, center[1]+h//2)
            ld.ellipse(box, outline=(210,220,235,235), width=22)
            layer=layer.rotate(angle, center=center, resample=Image.Resampling.BICUBIC)
            img.alpha_composite(layer)
        d=ImageDraw.Draw(img)
        d.ellipse((center[0]-66, center[1]-66, center[0]+66, center[1]+66), fill=(245,247,250,255))
        d.ellipse((center[0]+225, center[1]-34, center[0]+287, center[1]+28), fill=(245,247,250,255))
        img.save(ICONS / "icon.png")
        for name, px in [("32x32.png",32),("128x128.png",128),("128x128@2x.png",256)]:
            img.resize((px, px), Image.Resampling.LANCZOS).save(ICONS / name)
        img.save(ICONS / "icon.icns", format="ICNS")
    except ImportError:
        raise SystemExit("Physical Lab icons are missing and Pillow is unavailable. Restore src-tauri/icons from the source package.")

print("Prepared Physical Lab frontend, first-principles Home, unified search, Workbench, and icons.")
