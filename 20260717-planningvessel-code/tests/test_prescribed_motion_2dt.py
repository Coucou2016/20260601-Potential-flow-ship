from __future__ import annotations

import unittest

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt import (
    PrescribedMotion2DtCase,
    SectionalLoadHistory,
    prescribed_motion_kinematics,
)
from planing_seakeeping.providers.planing_2dt import NonlinearBEM2DtProvider
from planing_seakeeping.station_2p5d import HardChineStation, StationHull


def _test_hull() -> StationHull:
    return StationHull(
        length_m=4.0,
        lcg_from_transom_m=1.7,
        stations=tuple(
            HardChineStation(x_m=x, beam_m=0.8, draft_m=0.16 + 0.01 * x, deadrise_deg=20.0)
            for x in (0.0, 0.6, 1.7, 2.8, 4.0)
        ),
    )


class _AnalyticSectionSolver:
    def __init__(self, target_generalized_load: np.ndarray) -> None:
        self.target = np.asarray(target_generalized_load, dtype=float)

    def solve(self, case: PrescribedMotion2DtCase, kinematics) -> SectionalLoadHistory:
        x = kinematics.station_x_from_transom_m
        lever = x - case.hull.lcg_m
        basis = np.column_stack((np.ones_like(x), lever))
        gram = np.asarray(
            [
                [np.trapezoid(basis[:, 0], x), np.trapezoid(basis[:, 1], x)],
                [np.trapezoid(basis[:, 0] * lever, x), np.trapezoid(basis[:, 1] * lever, x)],
            ]
        )
        coefficients = np.linalg.solve(gram, self.target.T).T
        sectional = coefficients @ basis.T
        shape = sectional.shape
        return SectionalLoadHistory(
            time_s=kinematics.time_s,
            station_x_from_transom_m=x,
            vertical_force_per_length_n_m=sectional,
            potential_bvp_relative_residual=np.full(shape, 1e-12),
            pressure_bvp_relative_residual=np.full(shape, 2e-12),
            condition_number=np.full(shape, 12.0),
            metadata={"solver": "analytic_sectional_distribution_test_double"},
        )


class PrescribedMotion2DtTests(unittest.TestCase):
    def test_kinematics_follow_forced_heave_and_local_rigid_body_relation(self) -> None:
        case = PrescribedMotion2DtCase(
            hull=_test_hull(),
            speed_mps=4.5,
            mean_trim_rad=np.radians(4.0),
            motion_dof="heave",
            motion_amplitude=0.02,
            omega_rad_s=3.0,
            duration_s=5.0,
            time_step_s=0.01,
        )
        result = prescribed_motion_kinematics(case)
        expected = -case.motion_amplitude * np.sin(case.omega_rad_s * result.time_s)
        np.testing.assert_allclose(result.heave_m, expected, rtol=0.0, atol=1e-14)
        np.testing.assert_allclose(
            result.local_vertical_displacement_m,
            np.broadcast_to(expected[:, None], result.local_vertical_displacement_m.shape),
            rtol=0.0,
            atol=1e-14,
        )
        np.testing.assert_allclose(
            result.local_draft_m + result.local_vertical_displacement_m,
            np.broadcast_to(
                np.asarray([station.effective_draft_m() for station in case.hull.stations])[None, :],
                result.local_draft_m.shape,
            ),
            rtol=0.0,
            atol=1e-14,
        )

    def test_provider_orchestration_recovers_known_hydrodynamic_column(self) -> None:
        case = PrescribedMotion2DtCase(
            hull=_test_hull(),
            speed_mps=4.5,
            mean_trim_rad=np.radians(4.0),
            motion_dof="pitch",
            motion_amplitude=np.radians(0.43),
            omega_rad_s=3.2,
            duration_s=8.0,
            time_step_s=0.01,
        )
        time = case.time_s
        added_truth = np.asarray([320.0, -74.0])
        damping_truth = np.asarray([-110.0, 540.0])
        restoring = np.asarray([45.0, 810.0])
        sine = restoring * case.motion_amplitude - case.omega_rad_s**2 * case.motion_amplitude * added_truth
        cosine = case.omega_rad_s * case.motion_amplitude * damping_truth
        loads = (
            np.asarray([120.0, -35.0])[None, :]
            + np.sin(case.omega_rad_s * time)[:, None] * sine[None, :]
            + np.cos(case.omega_rad_s * time)[:, None] * cosine[None, :]
            + 0.03 * np.sin(2.0 * case.omega_rad_s * time)[:, None] * np.abs(sine)[None, :]
        )
        result = NonlinearBEM2DtProvider().simulate_prescribed_motion(
            case,
            _AnalyticSectionSolver(loads),
            restoring_column=restoring,
            discard_cycles=1.0,
            retained_cycles=2.0,
        )
        np.testing.assert_allclose(result.forced_motion_column.added_mass_column, added_truth, rtol=1e-11)
        np.testing.assert_allclose(result.forced_motion_column.damping_column, damping_truth, rtol=1e-11)
        np.testing.assert_allclose(result.generalized_load, loads, rtol=1e-12, atol=1e-10)
        self.assertFalse(result.metadata["response_calibration_used"])
        self.assertIn("section_bem_pending", result.metadata["status"])


if __name__ == "__main__":
    unittest.main()
