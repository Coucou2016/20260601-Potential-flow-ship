from __future__ import annotations

import csv
from dataclasses import replace
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.longitudinal_response import LongitudinalFrequencyModel
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.planing_frequency_correction import (
    PlaningFrequencyCorrection,
    _interpolate_matrix,
    apply_transom_sectional_force_cutoff,
    apply_frequency_correction,
    assemble_matched_domain_head_sea_excitation,
    assemble_phase_resolved_head_sea_excitation,
    assemble_section_bem_head_sea_excitation,
    build_planing_wetted_station_hull,
    assemble_planing_wetted_hydrostatic_restoring,
    compute_matched_bie_frequency_correction,
    compute_section_bem_frequency_correction,
    head_sea_wavenumber_from_encounter_frequency,
    load_nonlinear_2dt_forced_motion_correction,
    matched_bie_matrix_to_bow_up,
    matched_bie_excitation_to_bow_up,
)
from planing_seakeeping.types import LongitudinalHydrodynamicMatrices


class PlaningFrequencyCorrectionTests(unittest.TestCase):
    @staticmethod
    def _prescribed_state() -> tuple[BoatConfig, object]:
        boat = BoatConfig(
            length_m=1.9,
            beam_m=0.424,
            deadrise_deg=16.7,
            mass_kg=32.6,
            lcg_m=0.697,
            vcg_m=0.143,
            pitch_radius_gyration_m=0.583,
        )
        trim_deg = 4.0
        trim_rad = math.radians(trim_deg)
        keel_wetted_length_m = 1.49
        z_wl = math.sin(trim_rad) * (
            boat.lcg_m + boat.vcg_m / math.tan(trim_rad) - keel_wetted_length_m
        )
        equilibrium = make_prescribed_equilibrium(
            boat,
            3.4,
            PrescribedRunningStateConfig(enabled=True, trim_deg=trim_deg, z_wl_m=z_wl),
        )
        return boat, equilibrium

    def test_matched_bie_pitch_coordinate_transform_flips_only_couplings(self) -> None:
        source = np.asarray([[4.0, 2.0], [3.0, 5.0]])
        transformed = matched_bie_matrix_to_bow_up(source)
        np.testing.assert_allclose(transformed, [[4.0, -2.0], [-3.0, 5.0]])

    def test_transom_sectional_force_cutoff_zeroes_aft_density_and_end_term(self) -> None:
        station_x = np.repeat(np.asarray([[0.05, 0.15, 0.25, 0.35]]), 2, axis=0)
        density = np.ones((2, 4, 2, 2), dtype=complex)
        end_force = 3.0 * np.ones((2, 2, 2), dtype=complex)
        corrected_density, corrected_end, corrected_total, diagnostics = (
            apply_transom_sectional_force_cutoff(
                station_x_m=station_x,
                force_density_by_station=density,
                end_force_matrices=end_force,
                end_station_x_m=np.asarray([0.05, 0.30]),
                cutoff_length_m=0.20,
            )
        )
        np.testing.assert_allclose(corrected_density[:, :2], 0.0)
        np.testing.assert_allclose(corrected_density[:, 2:], 1.0)
        np.testing.assert_allclose(corrected_end[0], 0.0)
        np.testing.assert_allclose(corrected_end[1], 3.0)
        expected_integral = np.sum(
            0.5
            * (corrected_density[:, 1:] + corrected_density[:, :-1])
            * np.diff(station_x, axis=1)[:, :, None, None],
            axis=1,
        )
        np.testing.assert_allclose(
            corrected_total,
            expected_integral + corrected_end,
        )
        self.assertEqual(diagnostics["minimum_retained_station_count"], 2.0)
        self.assertEqual(diagnostics["end_force_zeroed_fraction"], 0.5)

    def test_transom_linear_recovery_is_zero_at_stern_and_continuous_to_full_force(self) -> None:
        station_x = np.asarray([[0.0, 0.1, 0.2, 0.3]])
        density = np.ones((1, 4, 2, 2), dtype=complex)
        corrected_density, corrected_end, _, diagnostics = (
            apply_transom_sectional_force_cutoff(
                station_x_m=station_x,
                force_density_by_station=density,
                end_force_matrices=np.ones((1, 2, 2), dtype=complex),
                end_station_x_m=np.asarray([0.1]),
                cutoff_length_m=0.2,
                recovery_profile="linear_ramp",
            )
        )
        np.testing.assert_allclose(
            corrected_density[0, :, 0, 0],
            [0.0, 0.5, 1.0, 1.0],
        )
        np.testing.assert_allclose(corrected_end[0], 0.5)
        self.assertEqual(diagnostics["minimum_recovery_weight"], 0.0)
        self.assertEqual(diagnostics["end_force_zeroed_fraction"], 0.0)

    def test_transom_square_root_recovery_satisfies_local_pressure_asymptotic(self) -> None:
        station_x = np.asarray([[0.0, 0.05, 0.2, 0.3]])
        density = np.ones((1, 4, 2, 2), dtype=complex)
        corrected_density, corrected_end, _, diagnostics = (
            apply_transom_sectional_force_cutoff(
                station_x_m=station_x,
                force_density_by_station=density,
                end_force_matrices=np.ones((1, 2, 2), dtype=complex),
                end_station_x_m=np.asarray([0.05]),
                cutoff_length_m=0.2,
                recovery_profile="square_root_ramp",
            )
        )
        np.testing.assert_allclose(
            corrected_density[0, :, 0, 0],
            [0.0, 0.5, 1.0, 1.0],
        )
        np.testing.assert_allclose(corrected_end[0], 0.5)
        self.assertEqual(diagnostics["minimum_recovery_weight"], 0.0)

    def test_matched_bie_defaults_to_equilibrium_mean_wetted_contour(self) -> None:
        boat, equilibrium = self._prescribed_state()
        geometric = build_planing_wetted_station_hull(
            boat, equilibrium, station_count=15, wagner_pileup_factor=1.0
        )
        default_geometry = build_planing_wetted_station_hull(boat, equilibrium, station_count=15)
        piled_up = build_planing_wetted_station_hull(
            boat,
            equilibrium,
            station_count=15,
            wagner_pileup_factor=math.pi / 2.0,
        )
        geometric_beams = np.asarray([station.waterplane_beam_m() for station in geometric.stations])
        default_beams = np.asarray(
            [station.waterplane_beam_m() for station in default_geometry.stations]
        )
        piled_up_beams = np.asarray([station.waterplane_beam_m() for station in piled_up.stations])
        np.testing.assert_allclose(default_beams, geometric_beams)
        chine_wet_x = (
            equilibrium.geometry.keel_wetted_length_m - equilibrium.geometry.x_s_m
        )
        nearest = int(
            np.argmin(
                np.abs(
                    np.asarray([station.x_m for station in default_geometry.stations])
                    - chine_wet_x
                )
            )
        )
        expected_beam = boat.beam_m * min(
            max(
                (
                    equilibrium.geometry.keel_wetted_length_m
                    - default_geometry.stations[nearest].x_m
                )
                / equilibrium.geometry.x_s_m,
                0.0,
            ),
            1.0,
        )
        self.assertAlmostEqual(default_beams[nearest], expected_beam, places=12)
        self.assertTrue(np.all(piled_up_beams >= geometric_beams))
        self.assertTrue(np.any(piled_up_beams > 1.25 * geometric_beams))
        self.assertLessEqual(float(piled_up_beams.max()), boat.beam_m)

    def test_mean_wetted_hydrostatic_restoring_is_finite_positive_and_station_converged(self) -> None:
        boat, equilibrium = self._prescribed_state()
        medium = assemble_planing_wetted_hydrostatic_restoring(
            boat,
            equilibrium,
            station_count=201,
        )
        fine = assemble_planing_wetted_hydrostatic_restoring(
            boat,
            equilibrium,
            station_count=401,
        )
        self.assertEqual(fine.shape, (2, 2))
        self.assertTrue(np.isfinite(fine).all())
        self.assertGreater(fine[0, 0], 0.0)
        self.assertGreater(fine[1, 1], 0.0)
        self.assertGreater(float(np.linalg.det(fine)), 0.0)
        relative_change = np.abs(medium - fine) / np.maximum(np.abs(fine), 1.0e-12)
        self.assertLess(float(relative_change.max()), 0.01)

    def test_matched_and_section_corrections_are_independent_callable_routes(self) -> None:
        boat, equilibrium = self._prescribed_state()
        omega = np.asarray([2.0, 3.0])
        solve_omega = np.asarray([2.0, 3.0, 4.0])
        force = np.empty((3, 2, 2), dtype=complex)
        for index, value in enumerate(solve_omega):
            force[index] = value**2 * np.asarray([[2.0, 0.5], [0.25, 1.0]])
        full = SimpleNamespace(
            metadata={"provider_route": "mock_matched_bie"},
            validity=SimpleNamespace(status="diagnostic"),
            contribution_breakdown={
                "heave_pitch_complex_force_matrices": force,
                "heave_pitch_time_derivative_force_matrices": force,
                "heave_pitch_stokes_body_forward_speed_force_matrices": np.zeros_like(force),
                "heave_pitch_end_term_force_matrices": np.zeros_like(force),
            },
        )
        provider = Mock()
        provider.solve_station_hull.return_value = full
        with patch(
            "planing_seakeeping.planing_frequency_correction.LinearFrequencyProvider",
            return_value=provider,
        ) as provider_factory:
            matched = compute_matched_bie_frequency_correction(
                boat,
                equilibrium,
                omega,
                high_frequency_reference_rad_s=4.0,
                station_count=9,
                history_steps=64,
                history_quadrature_count=48,
                history_k_max=30.0,
                free_surface_substeps_per_station=2,
            )
        self.assertEqual(provider_factory.call_args.kwargs["matched_options"]["history_steps"], 64)
        self.assertEqual(provider_factory.call_args.kwargs["matched_options"]["history_quadrature_count"], 48)
        self.assertEqual(provider_factory.call_args.kwargs["matched_options"]["history_k_max"], 30.0)
        self.assertEqual(provider_factory.call_args.kwargs["matched_options"]["free_surface_substeps_per_station"], 2)
        self.assertEqual(matched.raw_added_mass.shape, (3, 2, 2))
        self.assertEqual(matched.metadata["provider_route"], "mock_matched_bie")

        six_by_six = np.eye(6)
        section_result = SimpleNamespace(added_mass=six_by_six, damping=2.0 * six_by_six)
        with patch(
            "planing_seakeeping.planing_frequency_correction.assemble_experimental_bem_6dof_matrices",
            return_value=section_result,
        ) as section_solver:
            section = compute_section_bem_frequency_correction(
                boat,
                equilibrium,
                omega,
                high_frequency_reference_rad_s=4.0,
                station_count=9,
            )
        self.assertEqual(section.raw_added_mass.shape, (3, 2, 2))
        self.assertEqual(section_solver.call_count, 3)

    def test_matrix_interpolation_preserves_endpoints_and_shape(self) -> None:
        omega = np.asarray([2.0, 4.0, 8.0])
        values = np.zeros((3, 2, 2))
        values[:, 0, 0] = [3.0, 2.0, 0.0]
        values[:, 1, 1] = [1.0, 0.5, 0.0]
        interpolated = _interpolate_matrix(np.asarray([2.0, 3.0, 8.0]), omega, values)
        self.assertEqual(interpolated.shape, (3, 2, 2))
        np.testing.assert_allclose(interpolated[0], values[0])
        np.testing.assert_allclose(interpolated[-1], values[-1])
        self.assertAlmostEqual(float(interpolated[1, 0, 0]), 2.5)

    def test_head_sea_encounter_inversion_and_phase_excitation_close_long_wave_limit(
        self,
    ) -> None:
        encounter = np.asarray([1.0e-3, 2.0e-3, 3.0e-3])
        speed = 3.4
        gravity = 9.80665
        wavenumber, wave_omega = head_sea_wavenumber_from_encounter_frequency(
            encounter,
            speed,
            gravity,
        )
        np.testing.assert_allclose(
            wave_omega + speed * wavenumber,
            encounter,
            rtol=1.0e-12,
            atol=1.0e-12,
        )

        station_x = np.repeat(np.asarray([[0.0, 0.5, 1.0]]), 3, axis=0)
        x_forward = station_x[0] - 0.5
        local_heave_column = np.asarray([[4.0, -1.0], [4.0, -1.0], [4.0, -1.0]])
        density = np.zeros((3, 3, 2, 2), dtype=complex)
        density[:, :, :, 0] = local_heave_column[None, :, :]
        integrated_column = np.trapezoid(local_heave_column, station_x[0], axis=0)
        total_force = np.zeros((3, 2, 2), dtype=complex)
        total_force[:, :, 0] = integrated_column
        restoring = np.asarray([[10.0, 2.0], [3.0, 5.0]])
        excitation, components, diagnostics = assemble_phase_resolved_head_sea_excitation(
            station_x_m=station_x,
            total_force_density_by_station=density,
            total_force_matrices=total_force,
            end_force_matrices=np.zeros((3, 2, 2), dtype=complex),
            end_station_x_m=np.full(3, np.nan),
            station_waterplane_beam_m=np.ones((3, 3)),
            restoring_matrix=restoring,
            encounter_omega_rad_s=encounter,
            speed_mps=speed,
            gravity_m_s2=gravity,
            lcg_from_transom_m=0.5,
        )
        expected_long_wave = -1j * restoring[:, 0] + 1j * (
            wave_omega / encounter
        )[:, None] * integrated_column[None, :]
        np.testing.assert_allclose(excitation, expected_long_wave, rtol=2.0e-3, atol=2.0e-3)
        np.testing.assert_allclose(
            excitation,
            components["froude_krylov"] + components["diffraction_total"],
        )
        self.assertLess(diagnostics["maximum_restoring_moment_residual"], 1.0e-12)
        self.assertLess(
            diagnostics["maximum_uniform_radiation_reconstruction_residual"],
            1.0e-12,
        )

    def test_phase_resolved_excitation_requires_explicit_application(self) -> None:
        omega = np.asarray([2.0, 3.0, 4.0])
        values = np.repeat(np.eye(2)[None, :, :], 3, axis=0)
        phase_excitation = np.asarray(
            [[1.0 + 2.0j, 3.0 + 4.0j], [2.0 + 3.0j, 4.0 + 5.0j], [3.0 + 4.0j, 5.0 + 6.0j]]
        )
        correction = PlaningFrequencyCorrection(
            sample_omega_rad_s=omega,
            high_frequency_reference_rad_s=4.0,
            delta_added_mass=np.zeros_like(values),
            delta_radiation_damping=np.zeros_like(values),
            raw_added_mass=2.0 * values,
            raw_radiation_damping=3.0 * values,
            metadata={"source": "phase_excitation_test"},
            excitation_per_wave_amplitude=phase_excitation,
            excitation_components={"froude_krylov": 0.25 * phase_excitation},
        )
        hydro = LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=omega,
            encounter_omega_rad_s=omega,
            added_mass=values,
            radiation_damping=values,
            metadata={"provider_route": "test"},
        )
        base_excitation = np.ones((3, 2), dtype=complex)
        base = LongitudinalFrequencyModel(
            hydrodynamics=hydro,
            rigid_mass=np.eye(2),
            restoring=values,
            excitation_per_wave_amplitude=base_excitation,
            omega0_rad_s=omega,
            wavenumber_rad_m=np.ones(3),
            wavelength_m=np.ones(3),
            wave_amplitude_m=0.01,
            point_x_forward_m=1.0,
            heave_finite_length_factor=np.ones(3),
            pitch_finite_length_factor=np.ones(3),
            metadata={"excitation_formulation": "base"},
        )
        unchanged = apply_frequency_correction(
            base,
            correction,
            application_mode="replace_with_matched_bie",
        )
        np.testing.assert_allclose(unchanged.excitation_per_wave_amplitude, base_excitation)
        phased = apply_frequency_correction(
            base,
            correction,
            application_mode="replace_with_matched_bie",
            use_phase_resolved_excitation=True,
        )
        np.testing.assert_allclose(phased.excitation_per_wave_amplitude, phase_excitation)
        self.assertTrue(phased.metadata["phase_resolved_excitation_enabled"])

    def test_section_bem_excitation_integrates_station_phase_and_pitch_moment(self) -> None:
        boat, equilibrium = self._prescribed_state()
        hull = build_planing_wetted_station_hull(boat, equilibrium, station_count=9)
        result = SimpleNamespace(
            complex_vertical_force_per_m=2.0 + 1.0j,
            condition_number=12.0,
            residual_norm=1.0e-10,
        )
        with patch(
            "planing_seakeeping.planing_frequency_correction.solve_wave_excitation",
            return_value=result,
        ) as solver:
            excitation, components, diagnostics = assemble_section_bem_head_sea_excitation(
                hull=hull,
                encounter_omega_rad_s=np.asarray([6.0, 7.0, 8.0]),
                speed_mps=equilibrium.speed_through_water_mps,
                gravity_m_s2=boat.gravity_m_s2,
                rho_water_kg_m3=boat.rho_water_kg_m3,
                body_panel_count=16,
                free_surface_panel_count_per_side=10,
            )
        self.assertEqual(solver.call_count, 3 * len(hull.stations))
        self.assertEqual(excitation.shape, (3, 2))
        self.assertTrue(np.isfinite(excitation).all())
        np.testing.assert_allclose(
            components["section_bem_incident_plus_diffraction"],
            excitation,
        )
        self.assertEqual(diagnostics["section_bem_excitation_maximum_condition_number"], 12.0)
        self.assertGreater(float(np.linalg.norm(excitation[:, 1])), 0.0)

    def test_matched_domain_excitation_applies_stern_recovery_and_pitch_transform(self) -> None:
        station_x = np.array([0.0, 1.0, 2.0])
        fk_density = np.tile(np.array([1.0 + 0.0j, 2.0 + 0.0j]), (3, 1))
        diffraction_density = np.tile(np.array([0.5 + 0.0j, 0.25 + 0.0j]), (3, 1))
        mocked_result = SimpleNamespace(
            x_m=station_x,
            froude_krylov_force_density_by_station=fk_density,
            diffraction_force_density_by_station=diffraction_density,
            maximum_condition_number=12.0,
            maximum_linear_system_relative_residual=1.0e-13,
            body_condition_relative_residual=2.0e-14,
            equation30_incident_pressure_relative_residual=3.0e-14,
            force_density_integration_relative_residual=4.0e-14,
        )
        with patch(
            "planing_seakeeping.planing_frequency_correction."
            "solve_station_hull_head_sea_excitation_matched_sweep",
            return_value=mocked_result,
        ) as solve:
            excitation, components, diagnostics = assemble_matched_domain_head_sea_excitation(
                hull=Mock(),
                encounter_omega_rad_s=np.array([2.0, 3.0]),
                speed_mps=4.0,
                gravity_m_s2=9.80665,
                rho_water_kg_m3=1025.0,
                config=Linear2p5DProviderConfig(
                    hull_stations=5,
                    body_panels_per_section=8,
                    free_surface_inner_panels=4,
                    free_surface_outer_panels=4,
                ),
                transom_recovery_length_m=0.5,
                transom_recovery_profile="hard_zero",
                matched_sweep_options={"history_steps": 64, "history_quadrature_count": 48, "history_k_max": 30.0},
            )
        self.assertEqual(solve.call_count, 2)
        self.assertEqual(solve.call_args.kwargs["matched_sweep_options"]["history_steps"], 64)
        expected_kernel = np.array([2.25, 3.375], dtype=complex)
        np.testing.assert_allclose(
            excitation,
            1j * np.tile(matched_bie_excitation_to_bow_up(expected_kernel), (2, 1)),
        )
        np.testing.assert_allclose(
            components["matched_domain_froude_krylov"],
            1j * np.tile(np.array([1.5, -3.0], dtype=complex), (2, 1)),
        )
        np.testing.assert_allclose(
            components["matched_domain_diffraction"],
            1j * np.tile(np.array([0.75, -0.375], dtype=complex), (2, 1)),
        )
        self.assertEqual(diagnostics["matched_domain_excitation_maximum_condition_number"], 12.0)
        self.assertAlmostEqual(diagnostics["matched_domain_excitation_mean_recovery_weight"], 2.0 / 3.0)

    def test_correction_contract_requires_strict_frequency_order(self) -> None:
        zeros = np.zeros((3, 2, 2))
        with self.assertRaises(ValueError):
            PlaningFrequencyCorrection(
                sample_omega_rad_s=np.asarray([2.0, 2.0, 8.0]),
                high_frequency_reference_rad_s=8.0,
                delta_added_mass=zeros,
                delta_radiation_damping=zeros,
                raw_added_mass=zeros,
                raw_radiation_damping=zeros,
                metadata={},
            )

    def test_nonlinear_2dt_csv_loader_preserves_nonreciprocal_matrix_and_rejects_zero_restoring(
        self,
    ) -> None:
        coefficient_base = {
            "A33": 10.0,
            "A35": 20.0,
            "A53": 30.0,
            "A55": 40.0,
            "B33": 50.0,
            "B35": 60.0,
            "B53": 70.0,
            "B55": 80.0,
        }

        def write_case(
            path: Path,
            restoring: str,
            coefficient_names=None,
            *,
            include_target_context: bool = False,
        ) -> None:
            selected = coefficient_base if coefficient_names is None else {
                name: coefficient_base[name] for name in coefficient_names
            }
            with path.open("w", encoding="utf-8", newline="") as stream:
                fieldnames = [
                    "component",
                    "omega_rad_s",
                    "coefficient",
                    "value_dimensional",
                    "harmonic_fit_residual_nrmse",
                    "restoring_subtraction",
                    "response_calibration_used",
                ]
                if include_target_context:
                    fieldnames.extend(
                        [
                            "target_identifier",
                            "beam_m",
                            "deadrise_deg",
                            "trim_deg",
                            "fn_b",
                            "mean_wetted_length_over_b",
                            "lcg_from_transom_m",
                            "rho_water_kg_m3",
                            "gravity_m_s2",
                            "matrix_coordinate_contract",
                        ]
                    )
                writer = csv.DictWriter(
                    stream,
                    fieldnames=fieldnames,
                )
                writer.writeheader()
                for omega in (1.0, 2.0, 3.0):
                    for coefficient, base in selected.items():
                        row = {
                                "component": "total",
                                "omega_rad_s": omega,
                                "coefficient": coefficient,
                                "value_dimensional": base + omega,
                                "harmonic_fit_residual_nrmse": 0.01,
                                "restoring_subtraction": restoring,
                                "response_calibration_used": False,
                            }
                        if include_target_context:
                            row.update(
                                {
                                    "target_identifier": "test_hull",
                                    "beam_m": 0.318,
                                    "deadrise_deg": 20.0,
                                    "trim_deg": 4.0,
                                    "fn_b": 2.5,
                                    "mean_wetted_length_over_b": 3.0,
                                    "lcg_from_transom_m": 0.46746,
                                    "rho_water_kg_m3": 1000.0,
                                    "gravity_m_s2": 9.80665,
                                    "matrix_coordinate_contract": (
                                        "heave_up_pitch_bow_up_force_and_moment_about_cg"
                                    ),
                                }
                            )
                        writer.writerow(row)

        with tempfile.TemporaryDirectory() as directory:
            accepted_path = Path(directory) / "accepted.csv"
            write_case(accepted_path, "sun2007_fig7_4_digitized")
            correction = load_nonlinear_2dt_forced_motion_correction(accepted_path)
            np.testing.assert_allclose(correction.raw_added_mass[0], [[11.0, 21.0], [31.0, 41.0]])
            np.testing.assert_allclose(
                correction.raw_radiation_damping[0], [[51.0, 61.0], [71.0, 81.0]]
            )
            self.assertNotEqual(
                correction.raw_added_mass[0, 0, 1], correction.raw_added_mass[0, 1, 0]
            )
            self.assertEqual(len(correction.metadata["source_csv_sha256"]), 64)
            self.assertFalse(correction.metadata["response_calibration_used"])

            restoring_path = Path(directory) / "restoring.csv"
            with restoring_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=("component", "row", "column", "value", "units"),
                )
                writer.writeheader()
                for row, column, value in (
                    ("heave_force", "heave", 101.0),
                    ("heave_force", "pitch", 102.0),
                    ("pitch_moment", "heave", 103.0),
                    ("pitch_moment", "pitch", 104.0),
                ):
                    writer.writerow(
                        {
                            "component": "total",
                            "row": row,
                            "column": column,
                            "value": value,
                            "units": "test",
                        }
                    )
            correction_with_restoring = load_nonlinear_2dt_forced_motion_correction(
                accepted_path,
                restoring_matrices_path=restoring_path,
            )
            np.testing.assert_allclose(
                correction_with_restoring.raw_restoring,
                np.repeat(
                    np.array([[101.0, 102.0], [103.0, 104.0]])[None, :, :],
                    3,
                    axis=0,
                ),
            )
            self.assertEqual(
                correction_with_restoring.metadata["complete_matrix_contract"],
                "replace_A_B_C_together",
            )
            self.assertEqual(
                len(correction_with_restoring.metadata["restoring_matrices_csv_sha256"]),
                64,
            )

            heave_path = Path(directory) / "heave.csv"
            pitch_path = Path(directory) / "pitch.csv"
            write_case(heave_path, "sun2007_fig7_4_digitized", ("A33", "A53", "B33", "B53"))
            write_case(pitch_path, "sun2007_fig7_4_digitized", ("A35", "A55", "B35", "B55"))
            merged = load_nonlinear_2dt_forced_motion_correction([heave_path, pitch_path])
            np.testing.assert_allclose(merged.raw_added_mass, correction.raw_added_mass)
            self.assertEqual(len(merged.metadata["source_csv_sha256"]), 2)

            diagnostic_path = Path(directory) / "zero_restoring.csv"
            write_case(diagnostic_path, "zero_diagnostic_only")
            with self.assertRaisesRegex(ValueError, "zero-restoring"):
                load_nonlinear_2dt_forced_motion_correction(diagnostic_path)

            context_path = Path(directory) / "with_context.csv"
            write_case(
                context_path,
                "sun2007_fig7_4_digitized",
                include_target_context=True,
            )
            contextual = load_nonlinear_2dt_forced_motion_correction(
                context_path,
                require_target_context=True,
            )
            self.assertEqual(contextual.metadata["target_context"]["target_identifier"], "test_hull")
            self.assertAlmostEqual(contextual.metadata["target_context"]["fn_b"], 2.5)
            with self.assertRaisesRegex(ValueError, "missing target context"):
                load_nonlinear_2dt_forced_motion_correction(
                    accepted_path,
                    require_target_context=True,
                )

    def test_matched_replacement_and_excitation_recomputation_use_final_matrices(self) -> None:
        omega = np.asarray([2.0, 3.0, 4.0])
        base_added = np.repeat(np.eye(2)[None, :, :], 3, axis=0)
        base_damping = 2.0 * base_added
        matched_added = np.asarray([3.0, 4.0, 5.0])[:, None, None] * np.eye(2)[None, :, :]
        matched_damping = np.asarray([6.0, 7.0, 8.0])[:, None, None] * np.eye(2)[None, :, :]
        correction = PlaningFrequencyCorrection(
            sample_omega_rad_s=omega,
            high_frequency_reference_rad_s=4.0,
            delta_added_mass=matched_added - matched_added[-1],
            delta_radiation_damping=matched_damping - matched_damping[-1],
            raw_added_mass=matched_added,
            raw_radiation_damping=matched_damping,
            metadata={"source": "synthetic_contract_test"},
        )
        hydro = LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=omega,
            encounter_omega_rad_s=omega,
            added_mass=base_added,
            radiation_damping=base_damping,
            metadata={"provider_route": "synthetic_base"},
        )
        base = LongitudinalFrequencyModel(
            hydrodynamics=hydro,
            rigid_mass=np.eye(2),
            restoring=np.repeat((3.0 * np.eye(2))[None, :, :], 3, axis=0),
            excitation_per_wave_amplitude=np.ones((3, 2), dtype=complex),
            omega0_rad_s=omega - 1.0,
            wavenumber_rad_m=np.ones(3),
            wavelength_m=np.ones(3),
            wave_amplitude_m=0.01,
            point_x_forward_m=1.0,
            heave_finite_length_factor=np.ones(3),
            pitch_finite_length_factor=np.ones(3),
            metadata={},
        )
        replaced = apply_frequency_correction(
            base,
            correction,
            application_mode="replace_with_matched_bie",
            recompute_faltinsen_excitation=True,
        )
        np.testing.assert_allclose(replaced.hydrodynamics.added_mass, matched_added)
        np.testing.assert_allclose(replaced.hydrodynamics.radiation_damping, matched_damping)
        self.assertGreater(float(np.linalg.norm(replaced.excitation_per_wave_amplitude)), 0.0)
        self.assertTrue(replaced.metadata["excitation_recomputed_from_final_matrices"])

        target_restoring = np.repeat(
            np.asarray([[[9.0, 1.0], [2.0, 8.0]]]), 3, axis=0
        )
        complete_correction = replace(
            correction,
            raw_restoring=target_restoring,
            metadata={
                **correction.metadata,
                "application_contract": "replace_with_matched_bie",
                "complete_matrix_contract": "replace_A_B_C_together",
            },
        )
        complete = apply_frequency_correction(
            base,
            complete_correction,
            application_mode="replace_with_matched_bie",
            recompute_faltinsen_excitation=True,
        )
        np.testing.assert_allclose(complete.restoring, target_restoring)
        self.assertTrue(complete.metadata["frequency_correction_restoring_replaced"])
        with self.assertRaisesRegex(ValueError, "complete A/B/C replacement"):
            apply_frequency_correction(
                base,
                complete_correction,
                include_added_mass=True,
                include_radiation_damping=False,
                application_mode="replace_with_matched_bie",
            )

        hybrid = apply_frequency_correction(
            base,
            correction,
            application_mode="planing_base_plus_matched_radiation",
            recompute_faltinsen_excitation=True,
        )
        np.testing.assert_allclose(
            hybrid.hydrodynamics.added_mass,
            base_added + matched_added - matched_added[-1],
        )
        np.testing.assert_allclose(
            hybrid.hydrodynamics.radiation_damping,
            base_damping + matched_damping,
        )

        asymptotic = apply_frequency_correction(
            base,
            correction,
            application_mode="planing_high_frequency_added_plus_matched_damping",
            recompute_faltinsen_excitation=True,
        )
        np.testing.assert_allclose(
            asymptotic.hydrodynamics.added_mass,
            base_added + matched_added - matched_added[-1],
        )
        np.testing.assert_allclose(
            asymptotic.hydrodynamics.radiation_damping,
            matched_damping,
        )

    def test_target_bound_matrix_rejects_cross_condition_application(self) -> None:
        omega = np.asarray([2.0, 3.0, 4.0])
        values = np.repeat(np.eye(2)[None, :, :], 3, axis=0)
        correction = PlaningFrequencyCorrection(
            sample_omega_rad_s=omega,
            high_frequency_reference_rad_s=4.0,
            delta_added_mass=np.zeros_like(values),
            delta_radiation_damping=np.zeros_like(values),
            raw_added_mass=values,
            raw_radiation_damping=values,
            metadata={
                "source": "target_bound_test",
                "target_context": {
                    "target_identifier": "source_label_only",
                    "beam_m": 0.318,
                    "deadrise_deg": 20.0,
                    "trim_deg": 4.0,
                    "fn_b": 2.5,
                    "mean_wetted_length_over_b": 3.0,
                    "lcg_from_transom_m": 0.46746,
                    "rho_water_kg_m3": 1000.0,
                    "gravity_m_s2": 9.80665,
                    "matrix_coordinate_contract": (
                        "heave_up_pitch_bow_up_force_and_moment_about_cg"
                    ),
                },
            },
        )
        hydro = LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=omega,
            encounter_omega_rad_s=omega,
            added_mass=values,
            radiation_damping=values,
            metadata={"provider_route": "test"},
        )
        base = LongitudinalFrequencyModel(
            hydrodynamics=hydro,
            rigid_mass=np.eye(2),
            restoring=values,
            excitation_per_wave_amplitude=np.ones((3, 2), dtype=complex),
            omega0_rad_s=omega,
            wavenumber_rad_m=np.ones(3),
            wavelength_m=np.ones(3),
            wave_amplitude_m=0.01,
            point_x_forward_m=1.0,
            heave_finite_length_factor=np.ones(3),
            pitch_finite_length_factor=np.ones(3),
            metadata={
                "target_context": {
                    "beam_m": 0.318,
                    "deadrise_deg": 16.7,
                    "trim_deg": 4.0,
                    "fn_b": 2.5,
                    "mean_wetted_length_over_b": 3.0,
                    "lcg_from_transom_m": 0.46746,
                    "rho_water_kg_m3": 1000.0,
                    "gravity_m_s2": 9.80665,
                    "matrix_coordinate_contract": (
                        "heave_up_pitch_bow_up_force_and_moment_about_cg"
                    ),
                }
            },
        )
        with self.assertRaisesRegex(ValueError, "target mismatch for deadrise_deg"):
            apply_frequency_correction(
                base,
                correction,
                application_mode="replace_with_matched_bie",
            )

    def test_target_context_accepts_published_two_decimal_fn_rounding(self) -> None:
        omega = np.asarray([2.0, 3.0, 4.0])
        values = np.repeat(np.eye(2)[None, :, :], 3, axis=0)
        correction = PlaningFrequencyCorrection(
            sample_omega_rad_s=omega,
            high_frequency_reference_rad_s=4.0,
            delta_added_mass=np.zeros_like(values),
            delta_radiation_damping=np.zeros_like(values),
            raw_added_mass=values,
            raw_radiation_damping=values,
            metadata={
                "source": "rounded_fn_test",
                "target_context": {"fn_b": 2.82},
            },
        )
        hydro = LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=omega,
            encounter_omega_rad_s=omega,
            added_mass=values,
            radiation_damping=values,
            metadata={"provider_route": "test"},
        )
        base = LongitudinalFrequencyModel(
            hydrodynamics=hydro,
            rigid_mass=np.eye(2),
            restoring=values,
            excitation_per_wave_amplitude=np.ones((3, 2), dtype=complex),
            omega0_rad_s=omega,
            wavenumber_rad_m=np.ones(3),
            wavelength_m=np.ones(3),
            wave_amplitude_m=0.01,
            point_x_forward_m=1.0,
            heave_finite_length_factor=np.ones(3),
            pitch_finite_length_factor=np.ones(3),
            metadata={"target_context": {"fn_b": 2.8198407259476403}},
        )

        corrected = apply_frequency_correction(
            base,
            correction,
            application_mode="replace_with_matched_bie",
        )

        self.assertEqual(corrected.metadata["frequency_correction_application_mode"], "replace_with_matched_bie")

    def test_target_bound_matrix_rejects_frequency_extrapolation(self) -> None:
        sample_omega = np.asarray([2.0, 3.0, 4.0])
        response_omega = np.asarray([1.9, 3.0, 4.0])
        values = np.repeat(np.eye(2)[None, :, :], 3, axis=0)
        correction = PlaningFrequencyCorrection(
            sample_omega_rad_s=sample_omega,
            high_frequency_reference_rad_s=4.0,
            delta_added_mass=np.zeros_like(values),
            delta_radiation_damping=np.zeros_like(values),
            raw_added_mass=values,
            raw_radiation_damping=values,
            metadata={
                "source": "target_bound_test",
                "application_contract": "replace_with_matched_bie",
            },
        )
        hydro = LongitudinalHydrodynamicMatrices(
            solver_omega_rad_s=response_omega,
            encounter_omega_rad_s=response_omega,
            added_mass=values,
            radiation_damping=values,
            metadata={"provider_route": "test"},
        )
        base = LongitudinalFrequencyModel(
            hydrodynamics=hydro,
            rigid_mass=np.eye(2),
            restoring=values,
            excitation_per_wave_amplitude=np.ones((3, 2), dtype=complex),
            omega0_rad_s=response_omega,
            wavenumber_rad_m=np.ones(3),
            wavelength_m=np.ones(3),
            wave_amplitude_m=0.01,
            point_x_forward_m=1.0,
            heave_finite_length_factor=np.ones(3),
            pitch_finite_length_factor=np.ones(3),
            metadata={},
        )
        with self.assertRaisesRegex(ValueError, "only be interpolated inside"):
            apply_frequency_correction(
                base,
                correction,
                application_mode="replace_with_matched_bie",
            )


if __name__ == "__main__":
    unittest.main()
