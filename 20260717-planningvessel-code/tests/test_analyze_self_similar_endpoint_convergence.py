from __future__ import annotations

import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_endpoint_convergence import (
    _expected_panel_fractions,
    analyze_endpoint_convergence,
)


def test_expected_panel_fractions_accepts_frozen_monitor_contract() -> None:
    fractions = np.asarray([0.0, 0.1, 0.35, 0.7, 1.0])
    spacing = _expected_panel_fractions(
        {
            "free_surface_panels": 4,
            "coupled_outer_grid_mode": "frozen_monitor",
            "coupled_outer_monitor_fractions": fractions.tolist(),
        }
    )

    np.testing.assert_allclose(spacing, np.diff(fractions))


def _write_run(
    root: Path,
    name: str,
    *,
    panels: int,
    radius: float,
    cfl: float,
    root_ratio: float,
    kinematic_integral: float,
) -> Path:
    run = root / name
    run.mkdir()
    config = {
        "free_surface_panels": panels,
        "far_radius": radius,
        "pseudo_cfl": cfl,
        "coupled_outer_grid_mode": "double_ended",
        "coupled_outer_root_spacing_ratio": root_ratio,
        "coupled_outer_far_spacing_ratio": 0.25,
        "coupled_outer_endpoint_decay": 4.0,
        "coupled_linear_gradient_recovery": "element",
    }
    (run / "coupled_checkpoint.json").write_text(
        json.dumps(
            {
                "config": config,
                "completed_iterations": 12,
                "cumulative_pseudo_time": 0.1,
            }
        ),
        encoding="utf-8",
    )
    coordinate = np.linspace(0.0, 1.0, panels)
    raw_spacing = np.exp(
        np.log(root_ratio) * np.power(1.0 - coordinate, 4.0)
        + np.log(0.25) * np.power(coordinate, 4.0)
    )
    node_xi = np.concatenate(([0.0], np.cumsum(raw_spacing / raw_spacing.sum())))
    pd.DataFrame({"xi": node_xi, "eta": np.zeros_like(node_xi)}).to_csv(
        run / "coupled_checkpoint_outer_nodes.csv",
        index=False,
    )
    pd.DataFrame(
        {
            "pseudo_time": [0.0, 0.05, 0.1],
            "kinematic_integral": [
                1.2 * kinematic_integral,
                1.1 * kinematic_integral,
                kinematic_integral,
            ],
        }
    ).to_csv(run / "coupled_pseudo_time_history.csv", index=False)
    (run / "resume_summary.json").write_text(
        json.dumps(
            {
                "reference_used_during_solve": False,
                "final_state": {
                    "kinematic_integral": kinematic_integral,
                    "kinematic_rms": 0.01,
                    "bem_condition_number": 100.0,
                },
                "post_solve_reference_metrics": {
                    "free_surface_nrmse": 0.04,
                    "pressure_nrmse": 0.05,
                },
                "post_solve_scalar_reference_metrics": {
                    "pressure_peak_relative_error": 0.02,
                    "pressure_peak_location_relative_error": 0.02,
                },
            }
        ),
        encoding="utf-8",
    )
    return run


def test_endpoint_convergence_audit_refuses_incomplete_matrix() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        runs = [
            _write_run(
                root,
                "coarse",
                panels=80,
                radius=20.0,
                cfl=0.25,
                root_ratio=0.08,
                kinematic_integral=0.0011,
            ),
            _write_run(
                root,
                "fine",
                panels=120,
                radius=20.0,
                cfl=0.25,
                root_ratio=0.08,
                kinematic_integral=0.0009,
            ),
        ]
        levels, pairs, report = analyze_endpoint_convergence(runs)

    assert len(levels) == 2
    assert len(pairs) == 1
    assert report["classification"] == "DIAGNOSTIC_MATRIX_INCOMPLETE"
    assert report["validated"] is False


def test_endpoint_convergence_audit_identifies_best_run() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        runs = [
            _write_run(
                root,
                "a",
                panels=80,
                radius=20.0,
                cfl=0.25,
                root_ratio=0.08,
                kinematic_integral=0.004,
            ),
            _write_run(
                root,
                "b",
                panels=120,
                radius=20.0,
                cfl=0.25,
                root_ratio=0.08,
                kinematic_integral=0.003,
            ),
        ]
        _, _, report = analyze_endpoint_convergence(runs)

    assert report["best_run"]["run"] == "b"
    assert report["metric_pass"] is False


def test_endpoint_convergence_audit_rejects_grid_that_disagrees_with_config() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        valid = _write_run(
            root,
            "valid",
            panels=80,
            radius=20.0,
            cfl=0.25,
            root_ratio=0.08,
            kinematic_integral=0.004,
        )
        invalid = _write_run(
            root,
            "invalid",
            panels=80,
            radius=20.0,
            cfl=0.25,
            root_ratio=0.08,
            kinematic_integral=0.0001,
        )
        nodes = pd.read_csv(invalid / "coupled_checkpoint_outer_nodes.csv")
        nodes["xi"] = np.linspace(0.0, 1.0, len(nodes))
        nodes.to_csv(invalid / "coupled_checkpoint_outer_nodes.csv", index=False)
        _, _, report = analyze_endpoint_convergence([valid, invalid])

    assert report["best_run"]["run"] == "valid"
    assert report["grid_contract_pass"] is False
    assert report["grid_contract_failed_runs"] == ["invalid"]


def test_time_step_pair_is_compared_at_common_pseudo_time() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        coarse = _write_run(
            root,
            "coarse_cfl",
            panels=80,
            radius=20.0,
            cfl=0.25,
            root_ratio=0.08,
            kinematic_integral=0.004,
        )
        fine = _write_run(
            root,
            "fine_cfl",
            panels=80,
            radius=20.0,
            cfl=0.125,
            root_ratio=0.08,
            kinematic_integral=0.003,
        )
        pd.DataFrame(
            {
                "pseudo_time": [0.0, 0.1],
                "kinematic_integral": [0.006, 0.004],
            }
        ).to_csv(coarse / "coupled_pseudo_time_history.csv", index=False)
        pd.DataFrame(
            {
                "pseudo_time": [0.0, 0.1, 0.2],
                "kinematic_integral": [0.006, 0.004, 0.003],
            }
        ).to_csv(fine / "coupled_pseudo_time_history.csv", index=False)
        _, pairs, _ = analyze_endpoint_convergence([coarse, fine])

    pair = pairs.loc[pairs["sweep"] == "pseudo_cfl"].iloc[0]
    assert pair["coarse_level"] == 0.25
    assert pair["fine_level"] == 0.125
    assert pair["comparison_pseudo_time"] == 0.1
    assert pair["kinematic_integral_relative_change"] == 0.0
