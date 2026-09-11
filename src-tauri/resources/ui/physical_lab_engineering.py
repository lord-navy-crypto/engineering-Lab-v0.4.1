"""Compatibility facade for Physical Lab engineering tools.

The original Engineering V&V/UQ implementation is retained verbatim in
``physical_lab_engineering_legacy``. This facade inserts project, measurement,
model-specific, diagnostics and application workspaces before delegating to the
established engineering workflow.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    import physical_lab_engineering_legacy as _legacy
except ModuleNotFoundError:
    _legacy_path=Path(__file__).with_name("physical_lab_engineering_legacy.py"); _spec=importlib.util.spec_from_file_location("physical_lab_engineering_legacy",_legacy_path)
    if _spec is None or _spec.loader is None: raise ImportError(f"Unable to load Physical Lab engineering implementation: {_legacy_path}")
    _legacy=importlib.util.module_from_spec(_spec); sys.modules.setdefault("physical_lab_engineering_legacy",_legacy); _spec.loader.exec_module(_legacy)
for _name,_value in vars(_legacy).items():
    if not _name.startswith("_") and _name!="render_engineering_vvuq": globals()[_name]=_value
_render_engineering_vvuq_legacy=_legacy.render_engineering_vvuq


def _load_module_by_path(module_name:str,filename:str):
    ui_dir=Path(__file__).resolve().parent; spec=importlib.util.spec_from_file_location(module_name,ui_dir/filename)
    if spec is None or spec.loader is None: raise ImportError(f"Unable to load Physical Lab module: {filename}")
    module=importlib.util.module_from_spec(spec); sys.modules[module_name]=module
    try: spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(module_name) is module: sys.modules.pop(module_name,None)
        raise
    return module


def _load(name:str,file:str):
    try: return __import__(name)
    except ModuleNotFoundError: return _load_module_by_path(name,file)


def _load_project_kernel_module(): return _load("physical_lab_project_kernel","physical_lab_project_kernel.py")
def _load_measurement_registry_module(): return _load("physical_lab_measurement_registry","physical_lab_measurement_registry.py")
def _load_diagnostics_module(): return _load("physical_lab_diagnostics","physical_lab_diagnostics.py")
def _load_compute_engine_module(): return _load("physical_lab_compute_engine","physical_lab_compute_engine.py")


def _load_kerr_ui_module():
    _load("physical_lab_kerr_geodesics","physical_lab_kerr_geodesics.py"); return _load("physical_lab_kerr_ui","physical_lab_kerr_ui.py")


def _load_kerr_platform_ui_module():
    _load("physical_lab_kerr_geodesics","physical_lab_kerr_geodesics.py"); _load("physical_lab_experiment_kernel","physical_lab_experiment_kernel.py"); _load("physical_lab_kerr_workflow","physical_lab_kerr_workflow.py"); return _load("physical_lab_kerr_platform_ui","physical_lab_kerr_platform_ui.py")


def _load_solar_system_ui_module():
    _load("physical_lab_solar_system_dynamics","physical_lab_solar_system_dynamics.py"); _load("physical_lab_experiment_kernel","physical_lab_experiment_kernel.py"); _load("physical_lab_solar_system_workflow","physical_lab_solar_system_workflow.py"); return _load("physical_lab_solar_system_ui","physical_lab_solar_system_ui.py")


def _load_lattice_ui_module():
    _load("physical_lab_lattice_dynamics","physical_lab_lattice_dynamics.py"); _load("physical_lab_lattice_phonons","physical_lab_lattice_phonons.py"); _load("physical_lab_experiment_kernel","physical_lab_experiment_kernel.py"); _load("physical_lab_lattice_workflow","physical_lab_lattice_workflow.py"); return _load("physical_lab_lattice_ui","physical_lab_lattice_ui.py")


def _load_new_model_refinement_ui_module():
    _load("physical_lab_new_model_refinements","physical_lab_new_model_refinements.py"); return _load("physical_lab_new_model_refinement_ui","physical_lab_new_model_refinement_ui.py")


def _load_frequency_response_ui_module():
    _load("physical_lab_frequency_response","physical_lab_frequency_response.py"); return _load("physical_lab_frequency_response_ui","physical_lab_frequency_response_ui.py")


def _load_deep_science_ui_module():
    _load("physical_lab_deep_science","physical_lab_deep_science.py"); return _load("physical_lab_deep_science_ui","physical_lab_deep_science_ui.py")


def _load_kerr_shadow_sweep_ui_module():
    _load("physical_lab_deep_science","physical_lab_deep_science.py")
    _load("physical_lab_kerr_shadow_sweep","physical_lab_kerr_shadow_sweep.py")
    return _load("physical_lab_kerr_shadow_sweep_ui","physical_lab_kerr_shadow_sweep_ui.py")


def _load_remaining_science_ui_module():
    _load("physical_lab_remaining_science","physical_lab_remaining_science.py")
    return _load("physical_lab_remaining_science_ui","physical_lab_remaining_science_ui.py")


def _load_undulator_spectrum_ui_module():
    _load("physical_lab_undulator_spectrum","physical_lab_undulator_spectrum.py")
    return _load("physical_lab_undulator_spectrum_ui","physical_lab_undulator_spectrum_ui.py")


def _load_radiation_stokes_ui_module():
    _load("physical_lab_radia_radiation_propagation","physical_lab_radia_radiation_propagation.py")
    return _load("physical_lab_radiation_stokes_ui","physical_lab_radiation_stokes_ui.py")


def _record_module_exception(source:str,exc:Exception,profile:str)->None:
    try: _load_diagnostics_module().record_exception(source,exc,profile=profile,code="PLATFORM_MODULE_ERROR")
    except Exception: pass


def _load_application_modules():
    application_modes=_load("physical_lab_application_modes","physical_lab_application_modes.py"); range_module=_load("physical_lab_display_ranges","physical_lab_display_ranges.py"); return application_modes,range_module.padded_range


def _load_engineering_scenario_module(): return _load("physical_lab_engineering_scenarios","physical_lab_engineering_scenarios.py")


def render_engineering_vvuq(st, profile:str, namespace:dict|None=None)->None:
    if profile=="nonlinear-chaos":
        for source,loader,method,label in (
            ("kerr-geodesic-model",_load_kerr_ui_module,"render_kerr_geodesic_workspace","Kerr Geodesic Dynamics"),
            ("kerr-platform-workflow",_load_kerr_platform_ui_module,"render_kerr_platform_workspace","Kerr Experiment/Compute workflow"),
            ("solar-system-dynamics",_load_solar_system_ui_module,"render_solar_system_workspace","Sun–Jupiter–Saturn Dynamics"),
        ):
            try: getattr(loader(),method)(st,profile)
            except Exception as exc: _record_module_exception(source,exc,profile); st.warning(f"Physical Lab {label} could not load: {exc}")
    if profile=="oscillation-integration":
        try: _load_lattice_ui_module().render_lattice_workspace(st,profile)
        except Exception as exc: _record_module_exception("multilayer-honeycomb-lattice",exc,profile); st.warning(f"Physical Lab Multilayer Honeycomb Lattice Dynamics could not load: {exc}")

    if profile in {"ising-monte-carlo","random-walk-monte-carlo","nonlinear-chaos","oscillation-integration"}:
        try: _load_remaining_science_ui_module().render_remaining_science_workspace(st,profile)
        except Exception as exc: _record_module_exception("advanced-model-science",exc,profile); st.warning(f"Physical Lab Advanced Model Science could not load: {exc}")

    if profile in {"radia-magnet-studio","radiation-platform"}:
        try: _load_undulator_spectrum_ui_module().render_undulator_spectrum_workspace(st,namespace)
        except Exception as exc: _record_module_exception("undulator-spectrum-studio",exc,profile); st.warning(f"Physical Lab Undulator Spectrum & Beam Broadening Studio could not load: {exc}")

    if profile=="radia-magnet-studio":
        try: _load_radiation_stokes_ui_module().render_radiation_stokes_workspace(st,profile,namespace)
        except Exception as exc: _record_module_exception("trajectory-radiation-stokes-map",exc,profile); st.warning(f"Physical Lab Trajectory Radiation & Stokes Map could not load: {exc}")

    if profile in {"nonlinear-chaos","oscillation-integration","numerical-methods"}:
        try: _load_deep_science_ui_module().render_deep_science_workspace(st,profile)
        except Exception as exc: _record_module_exception("deep-science-studio",exc,profile); st.warning(f"Physical Lab Deep Science Studio could not load: {exc}")

    if profile=="nonlinear-chaos":
        try: _load_kerr_shadow_sweep_ui_module().render_kerr_shadow_morphology_workspace(st,profile)
        except Exception as exc: _record_module_exception("kerr-shadow-morphology",exc,profile); st.warning(f"Physical Lab Kerr Shadow Morphology Lab could not load: {exc}")

    if profile in {"nonlinear-chaos","oscillation-integration"}:
        try: _load_frequency_response_ui_module().render_frequency_response_workspace(st,profile)
        except Exception as exc: _record_module_exception("frequency-response-studio",exc,profile); st.warning(f"Physical Lab Frequency Response Studio could not load: {exc}")
        try: _load_new_model_refinement_ui_module().render_new_model_refinement_workspace(st,profile)
        except Exception as exc: _record_module_exception("new-model-refinement-studio",exc,profile); st.warning(f"Physical Lab New Model Refinement Studio could not load: {exc}")
    try: _load_project_kernel_module().render_project_workspace(st,profile,namespace)
    except Exception as exc: _record_module_exception("project-kernel",exc,profile); st.warning(f"Physical Lab Project Kernel could not load: {exc}")
    try: _load_measurement_registry_module().render_measurement_workspace(st,profile)
    except Exception as exc: _record_module_exception("measurement-calibration",exc,profile); st.warning(f"Physical Lab Measurement/Calibration Evidence could not load: {exc}")
    try:
        application_modes,padded_range=_load_application_modules(); application_modes.padded_range=padded_range; application_modes.render_application_mode(st,profile,namespace)
    except Exception as exc: _record_module_exception("application-mode",exc,profile); st.warning(f"Physical Lab Application Mode could not load: {exc}")
    try: _load_engineering_scenario_module().render_engineering_scenario_review(st,profile)
    except Exception as exc: _record_module_exception("engineering-scenario",exc,profile); st.warning(f"Physical Lab Engineering Scenario Review could not load: {exc}")
    try: _load_diagnostics_module().render_diagnostics_workspace(st,profile,_load_compute_engine_module())
    except Exception as exc: _record_module_exception("diagnostics-workspace",exc,profile); st.warning(f"Physical Lab Run & Diagnostics Log could not load: {exc}")
    _render_engineering_vvuq_legacy(st,profile,namespace)
