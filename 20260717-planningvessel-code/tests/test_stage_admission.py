import json
from pathlib import Path

import numpy as np
import pytest

from planing_seakeeping.providers.linear_hydrodynamics import LinearFrequencyProvider
from scripts.aggregate_gate2_frequency_candidate import _frozen_configuration, _validated_provider_evidence
from scripts.freeze_longitudinal_stage import freeze
from planing_seakeeping.linear_case import load_linear_case, steady_series


@pytest.mark.parametrize("source", ["capytaine", "pdstrip", "database", "typo"])
@pytest.mark.parametrize("production", [True, False])
def test_unimplemented_backends_cannot_claim_capability(source, production):
    with pytest.raises(NotImplementedError):
        LinearFrequencyProvider(source=source, production=production)


def test_missing_or_self_asserted_certificate_never_passes():
    assert not _frozen_configuration([{}, {}, {}])[0]
    assert not _frozen_configuration([])[0]
    assert not _validated_provider_evidence([{"correction_metadata": {"validity_status": "PASS"}}] * 3)


def test_response_blind_freeze_and_required_inputs(tmp_path):
    freeze(tmp_path / "frozen")
    path = tmp_path / "frozen/run.json"
    raw, boat = load_linear_case(path)
    assert len(raw["cases"]) == 3
    assert all(len(c["wave_amplitude_m"]) == 8 for c in raw["cases"])
    del raw["boat"]["mass_kg"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="boat requires"):
        load_linear_case(path)


def test_direct_excitation_is_explicit_and_unknown_route_rejected(tmp_path):
    freeze(tmp_path / "frozen", "matched_domain_incident_diffraction")
    path = tmp_path / "frozen/run.json"
    raw, _ = load_linear_case(path)
    assert raw["hydrodynamics"]["head_sea_excitation_formulation"] == "matched_domain_incident_diffraction"
    raw["hydrodynamics"]["head_sea_excitation_formulation"] = "unimplemented"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported head-sea"):
        load_linear_case(path)


def test_steady_series_derivatives_are_same_phasor():
    from types import SimpleNamespace
    model = SimpleNamespace(hydrodynamics=SimpleNamespace(solver_omega_rad_s=np.array([2.])),
        wave_amplitude_m=np.array([.1]), dynamic_stiffness=np.array([np.eye(2)]),
        excitation_per_wave_amplitude=np.array([[1+2j, .1+.2j]]), point_x_forward_m=2.)
    data = steady_series(model, 0)
    np.testing.assert_allclose(data.cg_accel_mps2, -4 * data.heave_m)
    np.testing.assert_allclose(data.bow_accel_mps2, -4 * (data.heave_m + 2 * data.pitch_rad))
    assert data.surge_m.eq(0).all()


def test_explicit_reconstructed_route_and_invalid_grading(tmp_path):
    freeze(tmp_path/'frozen', 'matched_domain_incident_diffraction', True, 'reconstructed_symmetric', 1.5)
    path = tmp_path/'frozen/run.json'
    raw,_ = load_linear_case(path)
    assert raw['hydrodynamics']['panel_integration_route'] == 'reconstructed_symmetric'
    assert raw['hydrodynamics']['waterline_grading_exponent'] == 1.5
    for value in (True, '1.5', 0., 3., float('nan')):
        raw['hydrodynamics']['waterline_grading_exponent'] = value
        path.write_text(json.dumps(raw),encoding='utf-8')
        with pytest.raises(ValueError,match='waterline_grading'):
            load_linear_case(path)
    raw['hydrodynamics']['waterline_grading_exponent'] = 1.5
    raw['hydrodynamics']['panel_integration_route'] = 'unimplemented'
    path.write_text(json.dumps(raw),encoding='utf-8')
    with pytest.raises(ValueError,match='Unsupported panel'):
        load_linear_case(path)


def test_cutoff_quadrature_requires_explicit_compatible_route(tmp_path):
    freeze(tmp_path / "frozen", "matched_domain_incident_diffraction")
    path = tmp_path / "frozen/run.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["hydrodynamics"]["cutoff_quadrature"] = "clipped_linear"
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded, _ = load_linear_case(path)
    assert loaded["hydrodynamics"]["cutoff_quadrature"] == "clipped_linear"
    raw["hydrodynamics"]["head_sea_excitation_formulation"] = "equivalent_radiation"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="requires direct"):
        load_linear_case(path)
    raw["hydrodynamics"]["cutoff_quadrature"] = "unknown"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported cutoff"):
        load_linear_case(path)


def test_wrong_provenance_hash_is_rejected(tmp_path):
    freeze(tmp_path / "frozen")
    path = tmp_path / "frozen/run.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    key = next(iter(raw["provenance"]["source_hashes"]))
    raw["provenance"]["source_hashes"][key] = "0" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_linear_case(path)


@pytest.mark.parametrize("key,value", [("frequency_sampling", "unknown"),
    ("history_steps", True), ("history_quadrature_count", 15),
    ("history_k_max", float("nan")), ("history_k_max", -1), ("unrecognized", 10)])
def test_refined_mesh_rejects_invalid_parameters(tmp_path, key, value):
    freeze(tmp_path / "frozen", "matched_domain_incident_diffraction", refined=True)
    path = tmp_path / "frozen/run.json"
    raw, _ = load_linear_case(path)
    raw["mesh"][key] = value
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_linear_case(path)


def test_refined_case_passes_exact_frequencies_and_history_to_kernel(tmp_path, monkeypatch):
    from planing_seakeeping import linear_case
    freeze(tmp_path / "frozen", "matched_domain_incident_diffraction", refined=True)
    raw, boat = load_linear_case(tmp_path / "frozen/run.json")
    captured = {}
    class ReachedKernel(Exception):
        pass
    def capture(boat, eq, frequencies, **kwargs):
        captured.update(kwargs)
        captured["frequencies"] = frequencies
        raise ReachedKernel
    monkeypatch.setattr(linear_case, "compute_matched_bie_frequency_correction", capture)
    with pytest.raises(ReachedKernel):
        linear_case.build_case_model(boat, raw["cases"][0], raw["mesh"], **raw["hydrodynamics"])
    np.testing.assert_allclose(captured["frequencies"], sorted(raw["cases"][0]["encounter_omega_rad_s"]), rtol=1e-12)
    for key in ("station_count", "history_steps", "history_quadrature_count", "history_k_max",
                "body_panels_per_section", "free_surface_inner_panels", "free_surface_outer_panels"):
        assert captured[key] == raw["mesh"][key]
    assert captured["cutoff_quadrature"] == "clipped_linear"


@pytest.mark.parametrize("allow", [False, True])
def test_irregular_fallback_requires_explicit_opt_in(allow):
    from unittest.mock import patch
    import pandas as pd
    from planing_seakeeping.config import load_config
    from planing_seakeeping.solver import analyze_speed
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "configs/report_quick_planing.yml")
    config.simulation.allow_linear_fallback = allow
    with patch("planing_seakeeping.solver.simulate_time_domain", side_effect=[pd.DataFrame(), RuntimeError("test failure")]), \
         patch("planing_seakeeping.solver.simulate_linear_response", return_value=pd.DataFrame()) as fallback, \
         patch("planing_seakeeping.solver.rms_after", return_value={}), \
         patch("planing_seakeeping.solver._response_diagnostics", return_value={}):
        if allow:
            result = analyze_speed(config, config.speeds()[0])
            assert result.summary["fallback_reason"] == "test failure"
            fallback.assert_called_once()
        else:
            with pytest.raises(RuntimeError, match="test failure"):
                analyze_speed(config, config.speeds()[0])
            fallback.assert_not_called()
