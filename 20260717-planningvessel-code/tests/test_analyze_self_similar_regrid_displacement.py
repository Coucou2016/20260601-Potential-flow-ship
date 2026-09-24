from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.analyze_self_similar_regrid_displacement import (
    audit_regrid_displacement,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    SelfSimilarCoupledRK2Diagnostics,
    SelfSimilarGeometryMaintenanceAdjustment,
    SelfSimilarMatchingSurfaceAdjustment,
)


def _matching() -> SelfSimilarMatchingSurfaceAdjustment:
    return SelfSimilarMatchingSurfaceAdjustment(
        effective_panel_shift=0.25,
        full_panel_shifts=0,
        fractional_panel_shift=0.25,
        root_displacement_ratio=0.1,
        bisection_iterations=3,
        trigger_code=1,
    )


def _geometry(
    *,
    raw: float,
    maintenance: float,
    net: float,
    cancellation: float,
) -> SelfSimilarGeometryMaintenanceAdjustment:
    return SelfSimilarGeometryMaintenanceAdjustment(
        raw_normal_velocity_integral=raw,
        normal_velocity_integral=maintenance,
        tangential_velocity_integral=0.5,
        net_normal_velocity_integral=net,
        maximum_normal_displacement_ratio=0.02,
        normal_velocity_correlation=-0.5,
        normal_cancellation_fraction=cancellation,
    )


def test_multistep_regrid_audit_reports_raw_maintenance_and_net_motion() -> None:
    first = SimpleNamespace(
        kinematic_integral_linear_exact=4.0,
        dipole_coefficient=2.0,
        jet_interface=SimpleNamespace(
            root_state=SimpleNamespace(s_lambda=1.0),
        ),
    )
    second = SimpleNamespace(
        kinematic_integral_linear_exact=3.0,
        dipole_coefficient=2.1,
        jet_interface=SimpleNamespace(
            root_state=SimpleNamespace(s_lambda=1.0),
        ),
    )
    third = SimpleNamespace(
        kinematic_integral_linear_exact=3.5,
        dipole_coefficient=2.2,
        jet_interface=SimpleNamespace(
            root_state=SimpleNamespace(s_lambda=1.0),
        ),
    )
    diagnostics = SelfSimilarCoupledRK2Diagnostics(
        provisional=_matching(),
        final=_matching(),
        provisional_geometry_maintenance=_geometry(
            raw=8.0,
            maintenance=2.0,
            net=5.0,
            cancellation=0.3,
        ),
        final_geometry_maintenance=_geometry(
            raw=4.0,
            maintenance=1.0,
            net=2.0,
            cancellation=0.4,
        ),
        rejected_attempt_count=0,
    )
    checkpoint = SimpleNamespace(
        coupled=first,
        completed_iterations=7,
        cumulative_pseudo_time=0.12,
    )

    with (
        patch(
            "scripts.analyze_self_similar_regrid_displacement."
            "load_coupled_self_similar_checkpoint",
            return_value=checkpoint,
        ),
        patch(
            "scripts.analyze_self_similar_regrid_displacement."
            "_advance_coupled_self_similar_wedge_pseudo_time_rk2_with_diagnostics",
            side_effect=[
                (second, 0.01, 0.03, diagnostics),
                (third, 0.02, 0.04, diagnostics),
            ],
        ),
        patch(
            "scripts.analyze_self_similar_regrid_displacement."
            "derive_shallow_water_jet_root_state_from_coupled",
            side_effect=lambda coupled: SimpleNamespace(
                s_lambda={id(first): 1.2, id(second): 1.1, id(third): 1.05}[
                    id(coupled)
                ]
            ),
        ),
    ):
        summary, records = audit_regrid_displacement(
            Path("checkpoint"),
            steps=2,
            root_inner_iterations=0,
        )

    assert summary["steps_completed"] == 2
    assert summary["kinematic_integral_initial"] == 4.0
    assert summary["kinematic_integral_final"] == 3.5
    assert summary["kinematic_integral_minimum"] == 3.0
    assert summary["final_maintenance_to_raw_normal_ratio_median"] == 0.25
    assert summary["final_net_to_raw_normal_ratio_median"] == 0.5
    assert records[0]["final_raw_normal_velocity_integral"] == 4.0
    assert records[0]["final_maintenance_normal_velocity_integral"] == 1.0
    assert records[0]["final_net_normal_velocity_integral"] == 2.0
    assert records[1]["kinematic_integral_change"] == 0.5
