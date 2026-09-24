from __future__ import annotations

import unittest

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig
from planing_seakeeping.kernels.nonlinear_2dt.planing_forced_motion import (
    _extend_station_load_to_transom,
    _integrate_station_interval,
    _remove_aft_station_interval,
    fixed_ground_plane_activation_time_s,
    GroundPlaneForcedMotionLaw,
    identify_planing_incident_wave_excitation,
    instantaneous_handoff_creation_time_s,
    incident_wave_elevation_at_body_station_m,
    incident_wave_phase_at_body_station_rad,
    PlaningForcedMotionCase,
    identify_planing_forced_motion_column,
    planing_forced_motion_kinematics,
    run_planing_forced_motion_2dt,
    sun_front_sectional_force_density,
    sun_transom_sectional_force_density,
)


class Nonlinear2DtPlaningForcedMotionTests(unittest.TestCase):
    def _case(self) -> PlaningForcedMotionCase:
        return PlaningForcedMotionCase(
            speed_mps=2.0,
            mean_trim_rad=np.radians(4.0),
            wetted_length_m=0.45,
            lcg_from_transom_m=0.22,
            motion_dof="heave",
            motion_amplitude=0.0005,
            omega_rad_s=8.0,
            duration_s=2.0 * (2.0 * np.pi / 8.0),
            time_step_s=(2.0 * np.pi / 8.0) / 16.0,
            initial_draft_m=0.012,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=9.81,
        )

    def test_ground_plane_motion_law_closes_draft_velocity_acceleration(self) -> None:
        case = self._case()
        law = GroundPlaneForcedMotionLaw(case, reference_draft_m=0.06, creation_time_s=-0.05)
        time = 0.12
        epsilon = 1e-6
        velocity_fd = (
            law.displacement_m(time + epsilon) - law.displacement_m(time - epsilon)
        ) / (2.0 * epsilon)
        acceleration_fd = (
            law.velocity_mps(time + epsilon) - law.velocity_mps(time - epsilon)
        ) / (2.0 * epsilon)
        self.assertAlmostEqual(law.velocity_mps(time), velocity_fd, delta=1e-8)
        self.assertAlmostEqual(law.acceleration_mps2(time), acceleration_fd, delta=1e-7)

    def _incident_wave_case(self) -> PlaningForcedMotionCase:
        gravity = 9.81
        wavenumber = 1.0
        omega0 = np.sqrt(gravity * wavenumber)
        speed = 2.0
        encounter = omega0 + wavenumber * speed
        period = 2.0 * np.pi / encounter
        return PlaningForcedMotionCase(
            speed_mps=speed,
            mean_trim_rad=np.radians(4.0),
            wetted_length_m=0.45,
            lcg_from_transom_m=0.22,
            motion_dof="fixed",
            motion_amplitude=0.0,
            omega_rad_s=encounter,
            duration_s=2.0 * period,
            time_step_s=period / 32.0,
            initial_draft_m=0.012,
            rho_water_kg_m3=1000.0,
            gravity_m_s2=gravity,
            incident_wave_amplitude_m=0.0005,
            incident_wave_omega0_rad_s=omega0,
            incident_wave_wavenumber_rad_m=wavenumber,
        )

    def test_fixed_plane_intrinsic_phase_matches_body_encounter_phase(self) -> None:
        case = self._incident_wave_case()
        law = GroundPlaneForcedMotionLaw(
            case,
            reference_draft_m=0.06,
            creation_time_s=0.17,
            incident_wave_active=True,
        )
        time_s = 0.41
        wave = law.incident_wave()
        self.assertIsNotNone(wave)
        assert wave is not None
        _, x_from_transom, _ = law.longitudinal_coordinates(time_s)
        body_phase = incident_wave_phase_at_body_station_rad(
            case,
            time_s,
            x_from_transom,
        )
        self.assertAlmostEqual(wave.phase_rad(time_s), body_phase, places=12)
        self.assertAlmostEqual(
            law.submergence_m(time_s) - law.draft_m(time_s),
            incident_wave_elevation_at_body_station_m(
                case,
                time_s,
                x_from_transom,
            ),
            places=12,
        )

    def test_incident_wave_wetted_length_satisfies_zero_submergence(self) -> None:
        case = self._incident_wave_case()
        time_s = 0.23
        motion = planing_forced_motion_kinematics(case, time_s)
        x = motion.instantaneous_wetted_length_m
        residual = (
            (case.wetted_length_m - x) * case.mean_trim_rad
            + incident_wave_elevation_at_body_station_m(case, time_s, x)
        )
        self.assertAlmostEqual(residual, 0.0, delta=1e-12)
        self.assertTrue(np.isfinite(motion.wetted_length_rate_mps))

    def test_direct_incident_wave_queue_produces_uncalibrated_excitation(self) -> None:
        case = self._incident_wave_case()
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )
        result = run_planing_forced_motion_2dt(config, case)
        identified = identify_planing_incident_wave_excitation(
            result,
            case,
            discard_cycles=0.25,
            retained_cycles=1.5,
        )
        self.assertTrue(result.metadata["incident_wave_included"])
        self.assertGreater(float(np.linalg.norm(identified.excitation_per_wave_amplitude)), 0.0)
        self.assertTrue(np.isfinite(identified.harmonic_fit.residual_nrmse).all())
        self.assertFalse(identified.metadata["response_calibration_used"])

    def test_ground_plane_interval_must_be_an_integer_number_of_bem_steps(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer multiple"):
            PlaningForcedMotionCase(
                **{
                    **self._case().__dict__,
                    "ground_plane_interval_s": 1.5 * self._case().time_step_s,
                }
            )

    def test_parallel_ground_plane_execution_matches_serial_result(self) -> None:
        case = self._case()
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=0.8,
            water_depth_m=0.6,
            body_panels_per_side=3,
            free_surface_panels_per_side=4,
            side_wall_panels=2,
            bottom_panels=4,
            gauss_order=4,
            damping_beach_length_m=0.2,
        )

        serial = run_planing_forced_motion_2dt(config, case)
        parallel = run_planing_forced_motion_2dt(
            config,
            case,
            parallel_workers=2,
        )

        np.testing.assert_allclose(
            parallel.generalized_load,
            serial.generalized_load,
            rtol=0.0,
            atol=0.0,
        )
        np.testing.assert_allclose(
            parallel.station_force_density_n_m,
            serial.station_force_density_n_m,
            rtol=0.0,
            atol=0.0,
            equal_nan=True,
        )
        self.assertEqual(parallel.metadata["parallel_workers"], 2)

    def test_parallel_worker_count_must_be_positive_integer(self) -> None:
        case = self._case()
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=0.8,
            water_depth_m=0.6,
            body_panels_per_side=3,
            free_surface_panels_per_side=4,
            side_wall_panels=2,
            bottom_panels=4,
            gauss_order=4,
        )
        for invalid in (0, -1, 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run_planing_forced_motion_2dt(
                    config,
                    case,
                    parallel_workers=invalid,
                )

    def test_ground_plane_queue_runs_and_reports_pending_physical_components(self) -> None:
        case = self._case()
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )
        progress: list[tuple[int, int, float]] = []
        result = run_planing_forced_motion_2dt(
            config,
            case,
            progress_callback=lambda index, count, time_s: progress.append(
                (index, count, time_s)
            ),
        )
        self.assertEqual(result.generalized_load.shape, (len(result.time_s), 2))
        self.assertTrue(np.isfinite(result.generalized_load).all())
        np.testing.assert_allclose(
            result.generalized_load,
            result.bem_generalized_load
            + result.transom_generalized_load
            + result.front_generalized_load,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            result.raw_bem_generalized_load,
            result.pre_chine_bem_generalized_load
            + result.post_chine_bem_generalized_load,
            rtol=0.0,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            result.raw_bem_generalized_load,
            result.resolved_station_generalized_load
            + result.transom_extrapolation_generalized_load,
            rtol=0.0,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            result.raw_bem_generalized_load,
            np.sum(result.longitudinal_bem_bin_generalized_load, axis=1),
            rtol=0.0,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            result.aftmost_resolved_station_x_m,
            result.transom_coverage_gap_m,
            rtol=0.0,
            atol=1e-14,
        )
        self.assertTrue(
            np.all(
                result.foremost_resolved_station_x_m
                > result.aftmost_resolved_station_x_m
            )
        )
        maximum_station_count = int(result.metadata["maximum_matrix_station_count"])
        station_arrays = (
            result.station_x_from_transom_m,
            result.station_force_density_n_m,
            result.station_creation_parameter_s,
            result.station_age_parameter_s,
            result.station_contact_half_beam_m,
            result.station_jet_cut_count,
        )
        for values in station_arrays:
            self.assertEqual(values.shape, (len(result.time_s), maximum_station_count))
        leading_offset = case.initial_draft_m / np.tan(case.mean_trim_rad)
        for time_index, time_s in enumerate(result.time_s):
            count = int(result.active_plane_count[time_index])
            x = result.station_x_from_transom_m[time_index, :count]
            creation = result.station_creation_parameter_s[time_index, :count]
            age = result.station_age_parameter_s[time_index, :count]
            self.assertTrue(np.isfinite(x).all())
            self.assertTrue(np.all(np.diff(x) > 0.0))
            np.testing.assert_allclose(age, float(time_s) - creation, rtol=0.0, atol=1e-14)
            np.testing.assert_allclose(
                x,
                case.wetted_length_m - leading_offset - case.speed_mps * age,
                rtol=0.0,
                atol=1e-12,
            )
            self.assertTrue(
                np.isfinite(result.station_force_density_n_m[time_index, :count]).all()
            )
            self.assertTrue(
                np.isfinite(result.station_contact_half_beam_m[time_index, :count]).all()
            )
            self.assertTrue(np.all(result.station_jet_cut_count[time_index, :count] >= 0))
            self.assertTrue(
                np.isnan(result.station_x_from_transom_m[time_index, count:]).all()
            )
            self.assertTrue(np.all(result.station_jet_cut_count[time_index, count:] == -1))
        self.assertEqual(
            tuple(result.metadata["longitudinal_bem_bin_labels"]),
            (
                "aft_post_chine",
                "middle_post_chine",
                "forward_post_chine",
                "pre_chine",
            ),
        )
        self.assertGreater(float(np.max(result.front_approximation_length_m)), 0.0)
        self.assertGreater(float(np.max(np.abs(result.front_generalized_load))), 0.0)
        self.assertGreaterEqual(result.minimum_matrix_station_count, 2)
        self.assertLess(float(np.max(result.max_potential_bvp_relative_residual)), 1e-9)
        self.assertTrue(np.isfinite(result.max_potential_bvp_condition_number).all())
        self.assertGreater(float(np.max(result.max_potential_bvp_condition_number)), 0.0)
        self.assertLess(float(np.max(result.max_pressure_bvp_relative_residual)), 1e-9)
        self.assertTrue(np.isfinite(result.max_pressure_bvp_condition_number).all())
        self.assertGreater(float(np.max(result.max_pressure_bvp_condition_number)), 0.0)
        self.assertLess(float(np.max(result.max_contact_constraint_abs_m)), 1e-10)
        self.assertTrue(result.metadata["front_approximation_included"])
        self.assertFalse(result.metadata["transom_3d_correction_included"])
        self.assertFalse(result.metadata["response_calibration_used"])
        self.assertEqual(
            int(result.metadata["wet_plane_removal_count"]),
            int(result.metadata["contact_exit_removal_count"])
            + int(result.metadata["transom_exit_removal_count"])
            + int(result.metadata["forward_interval_exit_removal_count"])
            + int(result.metadata["below_handoff_draft_removal_count"]),
        )
        self.assertEqual(progress[0], (0, len(result.time_s), 0.0))
        self.assertEqual(progress[-1][0], len(result.time_s))
        self.assertEqual(progress[-1][1], len(result.time_s))
        self.assertAlmostEqual(progress[-1][2], float(result.time_s[-1]))
        identified = identify_planing_forced_motion_column(
            result,
            case,
            restoring_column=np.zeros(2),
            discard_cycles=0.25,
            retained_cycles=1.5,
        )
        self.assertTrue(np.isfinite(identified.column.added_mass_column).all())
        self.assertTrue(np.isfinite(identified.column.damping_column).all())
        self.assertFalse(identified.column.metadata["response_calibration_used"])

    def test_ground_plane_creation_interval_is_decoupled_from_bem_time_step(self) -> None:
        base = self._case()
        case = PlaningForcedMotionCase(
            **{
                **base.__dict__,
                "time_step_s": base.time_step_s / 2.0,
                "ground_plane_interval_s": base.time_step_s,
            }
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )

        result = run_planing_forced_motion_2dt(config, case)

        self.assertEqual(result.metadata["bem_substeps_per_ground_plane_interval"], 2)
        self.assertEqual(result.metadata["ground_plane_handoff_mode"], "fixed_earth_grid")
        self.assertLessEqual(
            float(result.metadata["maximum_ground_plane_spacing_error_m"]),
            1e-12,
        )
        self.assertEqual(
            result.metadata["creation_draft_interpretation"],
            "actual_section_submergence_at_fixed_grid_introduction; "
            "deviation_from_steady_handoff_is_physical_in_forced_motion",
        )
        self.assertAlmostEqual(result.metadata["bem_internal_time_step_s"], case.time_step_s)
        self.assertAlmostEqual(
            result.metadata["ground_plane_interval_s"],
            case.ground_plane_interval_s,
        )
        self.assertLessEqual(int(np.max(result.active_plane_count)), 8)
        self.assertGreaterEqual(result.minimum_matrix_station_count, 2)

        expected_spacing = case.speed_mps * float(case.ground_plane_interval_s)
        for time_index in range(len(result.time_s)):
            count = int(result.active_plane_count[time_index])
            x = result.station_x_from_transom_m[time_index, :count]
            if len(x) > 1:
                np.testing.assert_allclose(
                    np.diff(x),
                    expected_spacing,
                    rtol=0.0,
                    atol=1e-12,
                )

    def test_scheduled_wagner_starts_fixed_planes_without_handoff_delay(self) -> None:
        base = self._case()
        case = PlaningForcedMotionCase(
            **{
                **base.__dict__,
                "ground_plane_handoff_mode": "fixed_earth_grid_scheduled_wagner",
            }
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )

        result = run_planing_forced_motion_2dt(config, case)

        self.assertEqual(
            result.metadata["ground_plane_handoff_mode"],
            "fixed_earth_grid_scheduled_wagner",
        )
        self.assertEqual(result.metadata["fixed_plane_deferred_creation_count"], 0)
        self.assertEqual(result.metadata["fixed_plane_localized_activation_count"], 0)
        self.assertEqual(result.metadata["fixed_plane_pending_count_at_end"], 0)
        self.assertGreater(result.metadata["minimum_creation_draft_m"], 0.0)
        self.assertLess(
            result.metadata["minimum_creation_draft_m"],
            case.initial_draft_m,
        )
        self.assertEqual(
            result.metadata["fixed_plane_activation_rule"],
            "Earth-fixed equal-spacing plane initialized by Wagner at its scheduled "
            "introduction time using the actual positive section draft",
        )

    def test_sun_front_sectional_force_matches_eq_7_45_heave_special_case(self) -> None:
        case = self._case()
        x_from_transom = case.wetted_length_m - 0.05
        motion = planing_forced_motion_kinematics(case, 0.0)
        self.assertAlmostEqual(motion.instantaneous_wetted_length_m, case.wetted_length_m)
        heave_entry_speed = case.speed_mps * case.mean_trim_rad + (
            case.motion_amplitude * case.omega_rad_s
        )
        local_draft = 0.05 * case.mean_trim_rad
        added_mass_k = (
            case.front_added_mass_cm
            * case.rho_water_kg_m3
            * np.pi
            * case.front_pileup_factor**2
            / (2.0 * np.tan(np.radians(20.0)) ** 2)
        )
        expected = 2.0 * added_mass_k * local_draft * heave_entry_speed**2
        actual = sun_front_sectional_force_density(
            case,
            deadrise_rad=np.radians(20.0),
            time_s=0.0,
            x_from_transom_m=x_from_transom,
        )
        self.assertAlmostEqual(actual, expected, delta=1e-10 * max(abs(expected), 1.0))

    def test_sun_front_sectional_force_matches_eq_7_45_pitch_special_case(self) -> None:
        heave_case = self._case()
        case = PlaningForcedMotionCase(
            **{**heave_case.__dict__, "motion_dof": "pitch", "motion_amplitude": np.radians(0.1)}
        )
        x_from_transom = case.wetted_length_m - 0.05
        pitch_rate = -case.motion_amplitude * case.omega_rad_s
        x_aft_from_cg = case.lcg_from_transom_m - x_from_transom
        local_draft = 0.05 * case.mean_trim_rad
        entry_speed = (
            case.speed_mps * case.mean_trim_rad + x_aft_from_cg * pitch_rate
        )
        entry_acceleration = 2.0 * case.speed_mps * pitch_rate
        added_mass_k = (
            case.front_added_mass_cm
            * case.rho_water_kg_m3
            * np.pi
            * case.front_pileup_factor**2
            / (2.0 * np.tan(np.radians(20.0)) ** 2)
        )
        expected = (
            2.0 * added_mass_k * local_draft * entry_speed**2
            + added_mass_k * local_draft**2 * entry_acceleration
        )
        actual = sun_front_sectional_force_density(
            case,
            deadrise_rad=np.radians(20.0),
            time_s=0.0,
            x_from_transom_m=x_from_transom,
        )
        self.assertAlmostEqual(actual, expected, delta=1e-10 * max(abs(expected), 1.0))

    def test_event_handoff_keeps_creation_draft_constant_during_cycle(self) -> None:
        case = PlaningForcedMotionCase(
            **{
                **self._case().__dict__,
                "initial_draft_m": 0.00025,
                "motion_amplitude": 0.0005,
            }
        )
        for time_s in np.linspace(0.0, 2.0 * np.pi / case.omega_rad_s, 17):
            creation_time = instantaneous_handoff_creation_time_s(case, float(time_s))
            law = GroundPlaneForcedMotionLaw(
                case,
                reference_draft_m=0.05,
                creation_time_s=creation_time,
            )
            self.assertAlmostEqual(law.draft_m(float(time_s)), case.initial_draft_m, places=13)

    def test_fixed_ground_plane_activation_is_localized_without_moving_plane(self) -> None:
        case = PlaningForcedMotionCase(
            **{
                **self._case().__dict__,
                "motion_amplitude": 0.01,
                "initial_draft_m": 0.006,
            }
        )
        creation_time = 0.75 * (2.0 * np.pi / case.omega_rad_s)
        motion = GroundPlaneForcedMotionLaw(
            case,
            reference_draft_m=0.05,
            creation_time_s=creation_time,
        )
        times = np.linspace(creation_time, creation_time + 0.2, 401)
        supported = np.asarray(
            [motion.draft_m(time) >= case.initial_draft_m for time in times]
        )
        crossings = np.flatnonzero(supported[1:] & ~supported[:-1])
        self.assertGreater(len(crossings), 0)
        index = int(crossings[0])
        event = fixed_ground_plane_activation_time_s(
            case,
            motion,
            interval_start_s=float(times[index]),
            interval_end_s=float(times[index + 1]),
            minimum_draft_m=case.initial_draft_m,
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertGreater(event, float(times[index]))
        self.assertLessEqual(event, float(times[index + 1]))
        self.assertAlmostEqual(motion.draft_m(event), case.initial_draft_m, delta=1e-10)
        _, x_before, _ = motion.longitudinal_coordinates(float(times[index]))
        _, x_event, _ = motion.longitudinal_coordinates(event)
        self.assertAlmostEqual(
            x_event - x_before,
            -case.speed_mps * (event - float(times[index])),
            delta=1e-12,
        )

    def test_uncorrected_station_integral_is_closed_at_the_transom(self) -> None:
        x = np.asarray([0.1, 0.2, 0.3])
        force = 4.0 + 3.0 * x
        closed_x, closed_force, gap = _extend_station_load_to_transom(x, force)

        np.testing.assert_allclose(closed_x, [0.0, 0.1, 0.2, 0.3])
        np.testing.assert_allclose(closed_force, 4.0 + 3.0 * closed_x)
        self.assertAlmostEqual(gap, 0.1)

    def test_piecewise_linear_station_force_has_exact_additive_pitch_moment(self) -> None:
        x = np.asarray([0.0, 0.4, 1.0])
        force = 1.0 + 2.0 * x
        lcg = 0.3
        total = _integrate_station_interval(
            x,
            force,
            lower_m=0.0,
            upper_m=1.0,
            lcg_from_transom_m=lcg,
        )
        aft = _integrate_station_interval(
            x,
            force,
            lower_m=0.0,
            upper_m=0.55,
            lcg_from_transom_m=lcg,
        )
        forward = _integrate_station_interval(
            x,
            force,
            lower_m=0.55,
            upper_m=1.0,
            lcg_from_transom_m=lcg,
        )

        np.testing.assert_allclose(total, [2.0, 17.0 / 30.0], atol=1e-14)
        np.testing.assert_allclose(total, aft + forward, atol=1e-14)

    def test_source_keel_reduction_removes_aft_interval_at_exact_boundary(self) -> None:
        x = np.asarray([0.0, 0.1, 0.3, 0.6])
        force = 4.0 + 3.0 * x
        corrected_x, corrected_force = _remove_aft_station_interval(
            x,
            force,
            removed_length_m=0.2,
        )

        np.testing.assert_allclose(corrected_x, [0.2, 0.3, 0.6])
        np.testing.assert_allclose(corrected_force, 4.0 + 3.0 * corrected_x)

    def test_transom_source_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct source corrections"):
            PlaningForcedMotionCase(
                **{
                    **self._case().__dict__,
                    "transom_correction_enabled": True,
                    "transom_keel_reduction_beams": 0.5,
                }
            )

    def test_sun_transom_patch_reproduces_eq_7_22_troesch_coefficient(self) -> None:
        beam = 0.318
        gravity = 9.80665
        fn_b = 2.5
        case = PlaningForcedMotionCase(
            speed_mps=fn_b * np.sqrt(gravity * beam),
            mean_trim_rad=np.radians(4.0),
            wetted_length_m=3.0 * beam,
            lcg_from_transom_m=1.47 * beam,
            motion_dof="heave",
            motion_amplitude=0.036 * beam,
            omega_rad_s=1.4 * np.sqrt(gravity / beam),
            duration_s=2.0,
            time_step_s=0.02,
            initial_draft_m=0.8 * beam * np.tan(np.radians(4.0)),
            rho_water_kg_m3=1000.0,
            gravity_m_s2=gravity,
            transom_correction_enabled=True,
        )
        x = 0.1 * beam
        force = sun_transom_sectional_force_density(
            case,
            beam_m=beam,
            mean_transom_draft_m=0.266 * beam,
            time_s=0.0,
            x_from_transom_m=x,
        )
        normalized = force / (0.5 * case.rho_water_kg_m3 * case.speed_mps**2 * beam)
        expected = 1.61 / fn_b**2 * np.sqrt(0.1)
        self.assertAlmostEqual(normalized, expected, delta=0.015 * expected)

    def test_transom_corrected_queue_has_disjoint_load_decomposition(self) -> None:
        case = PlaningForcedMotionCase(
            **{
                **self._case().__dict__,
                "transom_correction_enabled": True,
            }
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )
        result = run_planing_forced_motion_2dt(config, case)
        np.testing.assert_allclose(
            result.generalized_load,
            result.bem_generalized_load
            + result.transom_generalized_load
            + result.front_generalized_load,
            rtol=0.0,
            atol=1e-12,
        )
        self.assertGreater(float(np.max(np.abs(result.transom_generalized_load))), 0.0)
        self.assertTrue(result.metadata["transom_3d_correction_included"])
        self.assertTrue(
            np.all(result.transom_correction_length_m > 0.0)
        )

    def test_source_keel_reduction_queue_removes_fixed_half_beam_without_patch_load(self) -> None:
        case = PlaningForcedMotionCase(
            **{
                **self._case().__dict__,
                "transom_keel_reduction_beams": 0.5,
            }
        )
        config = MovingWedgeConfig(
            deadrise_rad=np.radians(20.0),
            mean_draft_m=0.05,
            chine_half_beam_m=0.16,
            free_surface_extent_m=1.0,
            water_depth_m=0.8,
            body_panels_per_side=4,
            free_surface_panels_per_side=5,
            side_wall_panels=2,
            bottom_panels=6,
            gauss_order=4,
            damping_beach_length_m=0.3,
        )
        result = run_planing_forced_motion_2dt(config, case)

        np.testing.assert_allclose(
            result.generalized_load,
            result.bem_generalized_load + result.front_generalized_load,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(result.transom_generalized_load, 0.0, atol=0.0)
        self.assertGreater(
            float(np.max(np.abs(result.raw_bem_generalized_load - result.bem_generalized_load))),
            0.0,
        )
        self.assertEqual(
            result.metadata["transom_3d_correction_mode"],
            "source_keel_wetted_length_reduction",
        )
        np.testing.assert_allclose(
            result.transom_correction_length_m,
            0.5 * 2.0 * config.chine_half_beam_m,
            atol=1e-14,
        )


if __name__ == "__main__":
    unittest.main()
