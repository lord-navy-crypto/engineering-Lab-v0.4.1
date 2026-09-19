#!/usr/bin/env python3
from pathlib import Path

app = Path("web/app.js").read_text(encoding="utf-8")
html = Path("web/index.html").read_text(encoding="utf-8")
utube = Path("web/utube-native.js").read_text(encoding="utf-8")
native = Path("web/native-experiments.js").read_text(encoding="utf-8")
css = Path("web/styles.css").read_text(encoding="utf-8")

experiment_ids = [
    "numerical-methods",
    "ising-monte-carlo",
    "random-walk-monte-carlo",
    "nonlinear-chaos",
    "oscillation-integration",
    "radia-magnet-studio",
    "radiation-platform",
    "kerr-geodesics",
    "solar-system-dynamics",
    "honeycomb-lattice",
    "utube-studio",
    "kerr-shadow",
    "undulator-spectrum",
    "frequency-response",
]
assert len(experiment_ids) == 14

for experiment_id in experiment_ids:
    assert f"id:'{experiment_id}'" in native, f"missing native experiment registry entry: {experiment_id}"

for marker in (
    "function nativeExperimentCardFor(",
    "function nativeModuleCard(",
    "function openNativeExperiment(",
    "function renderNativeExperimentShell(",
    "function nativePreviewSeries(",
    "function renderNativeExperimentPreview(",
):
    assert marker in native, f"missing native experiment implementation marker: {marker}"

for marker in (
    "utube:['utubeView'",
    "experiment:['nativeExperimentView'",
    "nativeModuleCard(m)",
    "nativeExtraExperimentCards()",
    "bindNativeExperimentShell();",
):
    assert marker in app, f"missing app-shell marker: {marker}"

assert 'id="nativeExperimentView"' in html
assert 'id="utubeView"' in html
assert '<script src="utube-native.js"></script>' in html
assert '<script src="native-experiments.js"></script>' in html
assert 'id="nativeExperimentPreview"' in html
assert "Native experiment workspace — U-Tube migration" in css

for view_id in ("nativeExperimentView", "utubeView"):
    start = html.index(f'id="{view_id}"')
    end = html.find('<section id=', start + 10)
    segment = html[start:] if end < 0 else html[start:end]
    assert "<iframe" not in segment, f"{view_id} still embeds iframe"
    for forbidden_src in (
        'src="http://localhost',
        "src='http://localhost",
        'src="http://127.0.0.1',
        "src='http://127.0.0.1",
    ):
        assert forbidden_src not in segment, f"{view_id} embeds local web source: {forbidden_src}"

utube_open = utube[utube.index("function openNativeUtube"):utube.index("function readUtubeInputs")]
native_open = native[native.index("function openNativeExperiment"):native.index("function renderNativeExperimentShell")]
for block_name, block in (("U-Tube", utube_open), ("shared native experiments", native_open)):
    for forbidden in ("launch_module", "labFrame", "iframe", "http://localhost", "http://127.0.0.1"):
        assert forbidden not in block, f"{block_name} open path contains forbidden legacy marker: {forbidden}"

guard = "if(typeof nativeExperimentSpec==='function'&&nativeExperimentSpec(id)){openNativeExperiment(id);return}"
assert guard in app, "openModule does not guard native experiments before legacy server launch"

print("Native experiment workspace validation: PASS (14/14 registered)")
