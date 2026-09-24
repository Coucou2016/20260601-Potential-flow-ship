from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml


def test_begovic_forced_motion_targets_are_source_derived_and_frequency_complete() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs" / "begovic_nonlinear_2dt_forced_motion_targets.yml").read_text(
            encoding="utf-8"
        )
    )
    hull = pd.read_csv(root / config["shared"]["source"]["hull"]).iloc[0]
    states = pd.read_csv(root / config["shared"]["source"]["running_state"])
    response = pd.read_csv(root / config["shared"]["source"]["response"])
    shared = config["shared"]

    assert shared["beam_m"] == float(hull["beam_m"])
    assert shared["deadrise_deg"] == float(hull["deadrise_deg"])
    assert shared["lcg_over_beam"] == pytest.approx(
        float(hull["lcg_from_transom_m"]) / float(hull["beam_m"])
    )
    assert shared["vcg_over_beam"] == pytest.approx(
        float(hull["vcg_m"]) / float(hull["beam_m"])
    )

    beam = float(shared["beam_m"])
    beta = math.radians(float(shared["deadrise_deg"]))
    frequency_scale = math.sqrt(beam / float(shared["gravity_m_s2"]))
    for target in config["targets"]:
        fn_b = float(target["fn_b"])
        source_state = states[np.isclose(states["fn_b"], fn_b)].iloc[0]
        assert target["speed_m_s"] == float(source_state["speed_m_s"])
        assert target["trim_deg"] == float(source_state["running_trim_deg"])
        assert target["reported_mean_wetted_length_m"] == float(
            source_state["mean_wetted_length_m"]
        )

        trim = math.radians(float(target["trim_deg"]))
        chine_offset = math.tan(beta) / (math.pi * math.tan(trim))
        mean_wetted = float(target["reported_mean_wetted_length_m"]) / beam
        keel_over_beam = mean_wetted + 0.5 * chine_offset
        draft = keel_over_beam * math.sin(trim)
        assert target["keel_wetted_length_over_beam"] == pytest.approx(
            keel_over_beam, rel=0.0, abs=5.0e-12
        )
        assert target["chine_wetting_offset_over_beam"] == pytest.approx(
            chine_offset, rel=0.0, abs=5.0e-12
        )
        assert target["mean_wetted_length_over_beam"] == pytest.approx(
            mean_wetted, rel=0.0, abs=5.0e-12
        )
        assert target["mean_draft_over_beam"] == pytest.approx(
            draft, rel=0.0, abs=5.0e-12
        )
        assert target["keel_wetted_length_over_beam"] == pytest.approx(
            target["mean_wetted_length_over_beam"]
            + 0.5 * target["chine_wetting_offset_over_beam"],
            rel=0.0,
            abs=5.0e-12,
        )

        source_frequency = np.sort(
            response[np.isclose(response["fn_b"], fn_b)]["encounter_omega_rad_s"].to_numpy(
                dtype=float
            )
            * frequency_scale
        )
        np.testing.assert_allclose(target["sigma_samples"], source_frequency, rtol=0.0, atol=5.0e-10)

    assert "requires_sensitivity" in config["targets"][0]["wetted_geometry_status"]
    assert all(
        "within_stated_cv_range" in target["wetted_geometry_status"]
        for target in config["targets"][1:]
    )
