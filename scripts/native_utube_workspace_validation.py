#!/usr/bin/env python3
from pathlib import Path

app = Path("web/app.js").read_text(encoding="utf-8")
html = Path("web/index.html").read_text(encoding="utf-8")
native = Path("web/utube-native.js").read_text(encoding="utf-8")
css = Path("web/styles.css").read_text(encoding="utf-8")

required_app = [
    "utube:['utubeView'",
    "nativeUtubeCard()+labs.slice(-2)",
    "(activeCategory==='All'?nativeUtubeCard():'')",
    "bindNativeUtube();",
]
required_native = [
    "function nativeUtubeCard()",
    "function openNativeUtube(){showView('utube');renderNativeUtube()}",
    "function utubeCapacity(",
    "function utubeThreshold(",
    "function utubePotential(",
    "function renderNativeUtubeHysteresis(",
]
for marker in required_app:
    assert marker in app, f"missing app-shell marker: {marker}"
for marker in required_native:
    assert marker in native, f"missing native U-Tube marker: {marker}"

assert 'id="utubeView"' in html
assert '<script src="utube-native.js"></script>' in html
assert "Native experiment workspace — U-Tube migration" in css

start = html.index('id="utubeView"')
end = html.index('id="labView"', start)
utube_html = html[start:end]
assert "<iframe" not in utube_html
assert "localhost" not in utube_html
assert "127.0.0.1" not in utube_html

open_start = native.index("function openNativeUtube")
open_end = native.index("function readUtubeInputs", open_start)
native_open = native[open_start:open_end]
for forbidden in ("launch_module", "labFrame", "iframe", "localhost", "127.0.0.1"):
    assert forbidden not in native_open, f"native U-Tube open path contains forbidden legacy marker: {forbidden}"

print("Native U-Tube workspace validation: PASS")
