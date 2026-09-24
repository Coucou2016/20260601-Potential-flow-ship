from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from planing_seakeeping.coefficients import _restoring_matrix
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.linear_case import load_linear_case
from scripts.audit_prescribed_restoring import analytic_restoring


@pytest.mark.parametrize("index", [0, 1, 2])
def test_chain_derivatives_reproduce_production(index):
    root = Path(__file__).resolve().parents[1]
    raw, boat = load_linear_case(root / "benchmarks/longitudinal_refined_20260921/run.json")
    case = raw["cases"][index]
    eq = make_prescribed_equilibrium(boat, case["speed_mps"], PrescribedRunningStateConfig(
        enabled=True, trim_deg=case["trim_deg"], lambda_w=case["lambda_w"]))
    np.testing.assert_allclose(analytic_restoring(boat, eq), _restoring_matrix(boat, eq), rtol=1e-6)
    with pytest.raises(ValueError, match="wetted_lengths_type"):
        analytic_restoring(replace(boat, wetted_lengths_type=2), eq)
    with pytest.raises(ValueError, match="Trim clamp"):
        analytic_restoring(boat, replace(eq, trim_rad=0.0))
