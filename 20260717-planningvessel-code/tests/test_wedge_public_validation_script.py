from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _load_script_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_wedge_entry_public_reference.py"
    spec = importlib.util.spec_from_file_location("validate_wedge_entry_public_reference", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_curve_metrics_are_zero_for_identical_curves() -> None:
    module = _load_script_module()
    values = np.asarray([0.0, 1.0, 2.0])
    metrics = module._curve_metrics(values, values)
    assert metrics["rmse"] == 0.0
    assert metrics["nrmse_by_reference_range"] == 0.0


def test_comparison_interpolates_only_on_overlap() -> None:
    module = _load_script_module()
    rows, metrics = module._comparison_rows(
        np.asarray([0.0, 2.0]),
        np.asarray([0.0, 2.0]),
        np.asarray([-1.0, 0.0, 1.0, 2.0, 3.0]),
        np.asarray([-1.0, 0.0, 1.0, 2.0, 3.0]),
    )
    assert len(rows) == 3
    assert metrics["rmse"] == 0.0
