import tempfile
import unittest
from pathlib import Path

import numpy as np

from planing_seakeeping.cli import main as cli_main
from planing_seakeeping.section_bem import (
    hard_chine_v_offsets,
    section_bem_body_panel_convergence_study,
    section_bem_convergence_study,
    section_bem_multimode_radiation_diagnostics,
    section_bem_pressure_transfer_diagnostics,
    solve_heave_radiation,
    solve_heave_radiation_pdstrip_style,
    solve_pressure_transfer,
    solve_radiation_modes,
    solve_wave_excitation,
)
from planing_seakeeping.station_2p5d import (
    DOF_LABELS,
    STATION_2P5D_VALIDATED,
    RigidBody6DOF,
    StationHull,
    assemble_experimental_bem_6dof_matrices,
    assemble_forward_speed_2p5d_matrices,
    assemble_hybrid_forward_coupling_matrices,
    assemble_hybrid_pressure_damping_coupling_matrices,
    assemble_pressure_transfer_forward_speed_matrices,
    assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices,
    assemble_prototype_6dof_matrices,
    forward_speed_coupling_variant_diagnostics,
    forward_speed_coupling_station_contribution_diagnostics,
    forward_speed_2p5d_component_diagnostics,
    forward_speed_pressure_gradient_diagnostics,
    forward_speed_pressure_transfer_diagnostics,
    assemble_prototype_strip_matrices,
    experimental_bem_wave_excitation_6dof,
    load_station_hull,
    load_station_offsets_csv,
    make_sl7_surrogate_hull,
    make_wigley_iii_hull,
    prototype_wave_excitation_6dof,
    station_geometry_audit,
    section_bem_excitation_diagnostics,
    section_bem_multimode_station_diagnostics,
    section_bem_pressure_transfer_station_diagnostics,
    section_bem_station_diagnostics,
    solve_station_rao_6dof,
    station_frequency_matrices_long,
    station_rao_frequency_sweep,
)


ROOT = Path(__file__).resolve().parents[1]


class Station2P5DTests(unittest.TestCase):
    def test_example_station_hull_loads_and_integrates(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        hydro = hull.hydrostatics()
        self.assertGreater(hydro.displacement_volume_m3, 0.0)
        self.assertGreater(hydro.waterplane_area_m2, 0.0)
        self.assertGreaterEqual(hydro.center_of_buoyancy_x_m, 0.0)
        self.assertLessEqual(hydro.center_of_buoyancy_x_m, hull.length_m)

    def test_prototype_strip_matrices_are_symmetric_positive(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        matrices = assemble_prototype_strip_matrices(hull, omega_rad_s=2.0)
        self.assertFalse(STATION_2P5D_VALIDATED)
        self.assertEqual(matrices.status, "frequency_forward_speed_prototype_not_validated")
        self.assertTrue(np.allclose(matrices.added_mass, matrices.added_mass.T))
        self.assertTrue(np.allclose(matrices.damping, matrices.damping.T))
        self.assertTrue(np.allclose(matrices.restoring, matrices.restoring.T))
        self.assertGreater(float(np.linalg.det(matrices.added_mass)), 0.0)
        self.assertGreater(float(np.linalg.det(matrices.restoring)), 0.0)

    def test_prototype_6dof_matrices_have_expected_layout(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        matrices = assemble_prototype_6dof_matrices(hull, omega_rad_s=2.0)
        self.assertEqual(matrices.dof_labels, DOF_LABELS)
        self.assertEqual(matrices.added_mass.shape, (6, 6))
        self.assertEqual(matrices.damping.shape, (6, 6))
        self.assertEqual(matrices.restoring.shape, (6, 6))
        self.assertTrue(np.allclose(matrices.added_mass, matrices.added_mass.T))
        self.assertTrue(np.allclose(matrices.damping, matrices.damping.T))
        self.assertTrue(np.allclose(matrices.restoring, matrices.restoring.T))
        self.assertGreater(matrices.added_mass[2, 2], 0.0)
        self.assertGreater(matrices.restoring[2, 2], 0.0)
        self.assertGreater(matrices.restoring[3, 3], 0.0)
        self.assertGreater(matrices.restoring[4, 4], 0.0)

    def test_wave_excitation_respects_heading_symmetry(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        head = prototype_wave_excitation_6dof(hull, 1.0, 0.5, heading_deg=180.0)
        oblique = prototype_wave_excitation_6dof(hull, 1.0, 0.5, heading_deg=135.0)
        self.assertAlmostEqual(abs(head[1]), 0.0, places=12)
        self.assertAlmostEqual(abs(head[3]), 0.0, places=12)
        self.assertAlmostEqual(abs(head[5]), 0.0, places=12)
        self.assertGreater(abs(head[2]), 0.0)
        self.assertGreater(abs(oblique[1]), 0.0)
        self.assertGreater(abs(oblique[5]), 0.0)

    def test_6dof_rao_solve_returns_finite_response(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        matrices = assemble_prototype_6dof_matrices(hull, omega_rad_s=1.5)
        body = RigidBody6DOF.from_radii(
            mass_kg=3500.0,
            roll_radius_gyration_m=0.8,
            pitch_radius_gyration_m=2.5,
            yaw_radius_gyration_m=2.8,
        )
        excitation = prototype_wave_excitation_6dof(hull, 0.5, 0.4, heading_deg=180.0)
        response = solve_station_rao_6dof(matrices, body, excitation, encounter_omega_rad_s=1.5)
        self.assertEqual(response.shape, (6,))
        self.assertTrue(np.isfinite(response).all())

    def test_station_rao_frequency_sweep_columns(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        body = RigidBody6DOF.from_radii(3500.0, 0.8, 2.5, 2.8)
        rows = station_rao_frequency_sweep(hull, body, np.array([2.0, 3.0]), speed_mps=5.0)
        self.assertEqual(len(rows), 2)
        for label in DOF_LABELS:
            self.assertIn(f"{label}_rao_abs_per_m", rows[0])
            self.assertIn(f"{label}_phase_rad", rows[0])
            self.assertIn(f"{label}_excitation_abs_per_m", rows[0])
            self.assertIn(f"{label}_excitation_phase_rad", rows[0])
        self.assertGreater(rows[0]["heave_excitation_abs_per_m"], 0.0)

    def test_station_frequency_matrix_sweep_exports_all_6dof_terms(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_hull.yml")
        rows = station_frequency_matrices_long(hull, np.array([2.0, 3.0]), speed_mps=5.0)
        self.assertEqual(len(rows), 2 * 3 * len(DOF_LABELS) * len(DOF_LABELS))
        first = rows[0]
        for column in [
            "wave_period_s",
            "omega0_rad_s",
            "omega_e_rad_s",
            "matrix_type",
            "row_dof",
            "col_dof",
            "value",
        ]:
            self.assertIn(column, first)
        matrix_types = {row["matrix_type"] for row in rows}
        self.assertEqual(matrix_types, {"added_mass", "damping", "restoring"})

    def test_station_prototype_cli_writes_excitation_and_frequency_matrices(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "station"
            code = cli_main(
                [
                    "station-prototype",
                    str(ROOT / "configs" / "example_station_hull.yml"),
                    "--out",
                    str(out_dir),
                    "--period-count",
                    "2",
                ]
            )
            self.assertEqual(code, 0)
            excitation_path = out_dir / "station_excitation.csv"
            matrices_path = out_dir / "station_frequency_matrices_long.csv"
            self.assertTrue(excitation_path.exists())
            self.assertTrue(matrices_path.exists())
            excitation_header = excitation_path.read_text(encoding="utf-8").splitlines()[0]
            matrices_header = matrices_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertIn("heave_excitation_abs_per_m", excitation_header)
            self.assertIn("matrix_type", matrices_header)

    def test_loader_reports_missing_station_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yml"
            path.write_text("length_m: 1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stations"):
                load_station_hull(path)

    def test_station_offsets_load_and_define_hydrostatics(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_offsets.yml")
        station = hull.stations[1]
        self.assertIsNotNone(station.section_offsets())
        self.assertAlmostEqual(station.waterplane_beam_m(), 0.36)
        self.assertAlmostEqual(station.effective_draft_m(), 0.20)
        self.assertAlmostEqual(station.submerged_area_m2(), 0.036)
        self.assertAlmostEqual(station.centroid_z_below_waterline_m(), 0.20 / 3.0)
        hydro = hull.hydrostatics()
        self.assertGreater(hydro.displacement_volume_m3, 0.0)
        self.assertGreater(hydro.waterplane_area_m2, 0.0)

    def test_station_geometry_audit_reports_offset_quality(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_offsets_csv.yml")
        rows = station_geometry_audit(hull)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["geometry_source"] == "offsets" for row in rows))
        self.assertTrue(all(row["status"] == "PASS" for row in rows))
        self.assertEqual(rows[1]["offset_point_count"], 3)
        self.assertAlmostEqual(float(rows[1]["offset_signed_area_m2"]), 0.036)

    def test_station_geometry_audit_warns_on_non_waterline_endpoints(self):
        station_cls = type(make_wigley_iii_hull(length_m=2.0, station_count=3).stations[1])
        good = station_cls(
            x_m=0.0,
            beam_m=0.2,
            draft_m=0.1,
            deadrise_deg=90.0,
            offset_points_m=((0.1, 0.0), (0.0, 0.1), (-0.1, 0.0)),
        )
        bad = station_cls(
            x_m=1.0,
            beam_m=0.2,
            draft_m=0.1,
            deadrise_deg=90.0,
            offset_points_m=((0.1, 0.01), (0.0, 0.1), (-0.1, 0.0)),
        )
        rows = station_geometry_audit(StationHull(length_m=2.0, stations=(good, bad)))
        self.assertEqual(rows[1]["status"], "WARN")
        self.assertIn("endpoints", rows[1]["note"])

    def test_station_offsets_feed_section_bem_path(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_offsets.yml")
        rows = section_bem_station_diagnostics(
            hull,
            omega_rad_s=np.array([3.0]),
            free_surface_panel_count_per_side=3,
        )
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertEqual(len(active), len(hull.stations))
        self.assertEqual(active[0]["body_panel_count"], 2)
        self.assertGreater(max(float(row["added_mass_per_m"]) for row in active), 0.0)

    def test_station_offsets_csv_loads_and_matches_inline_example(self):
        csv_stations = load_station_offsets_csv(ROOT / "configs" / "example_station_offsets.csv")
        csv_hull = load_station_hull(ROOT / "configs" / "example_station_offsets_csv.yml")
        inline_hull = load_station_hull(ROOT / "configs" / "example_station_offsets.yml")
        self.assertEqual(len(csv_stations), 4)
        self.assertEqual(len(csv_hull.stations), len(inline_hull.stations))
        self.assertAlmostEqual(csv_hull.hydrostatics().displacement_volume_m3, inline_hull.hydrostatics().displacement_volume_m3)
        self.assertAlmostEqual(csv_hull.stations[1].submerged_area_m2(), 0.036)

    def test_station_offsets_csv_reports_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_offsets.csv"
            path.write_text("x_m,y_m\n0.0,0.1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_station_offsets_csv(path)

    def test_benchmark_hull_generators_are_positive(self):
        for hull in [make_wigley_iii_hull(), make_sl7_surrogate_hull()]:
            hydro = hull.hydrostatics()
            matrices = assemble_prototype_6dof_matrices(hull)
            self.assertGreater(hydro.displacement_volume_m3, 0.0)
            self.assertGreater(hydro.waterplane_area_m2, 0.0)
            self.assertGreater(matrices.added_mass[2, 2], 0.0)

    def test_wigley_iii_longitudinal_factor_matches_ma2005_table_1(self):
        hull = make_wigley_iii_hull(
            length_m=3.0,
            beam_m=0.3,
            draft_m=0.1875,
            station_count=41,
        )

        quarter_station = hull.stations[10]
        expected_quarter_beam = 0.3 * (1.0 - 0.5**2) * (1.0 + 0.2 * 0.5**2)

        self.assertAlmostEqual(quarter_station.x_m, 0.75)
        self.assertAlmostEqual(quarter_station.waterplane_beam_m(), expected_quarter_beam)
        self.assertAlmostEqual(hull.hydrostatics().displacement_volume_m3, 0.078, delta=1e-4)

    def test_forward_speed_adds_longitudinal_coupling(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875)
        still = assemble_prototype_6dof_matrices(hull, omega_rad_s=4.0, speed_mps=0.0)
        forward = assemble_prototype_6dof_matrices(hull, omega_rad_s=4.0, speed_mps=0.4 * np.sqrt(9.80665 * 3.0))
        self.assertAlmostEqual(still.added_mass[2, 4], still.added_mass[4, 2])
        self.assertNotAlmostEqual(forward.added_mass[2, 4], forward.added_mass[4, 2])
        self.assertNotAlmostEqual(forward.damping[2, 4], forward.damping[4, 2])

    def test_section_bem_heave_solver_returns_finite_positive_terms(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=6)
        result = solve_heave_radiation(offsets, omega_rad_s=4.0, free_surface_panel_count_per_side=4)
        self.assertEqual(result.status, "experimental_2d_free_surface_source_panel_not_validated")
        self.assertGreater(result.added_mass_per_m, 0.0)
        self.assertGreaterEqual(result.damping_per_m, 0.0)
        self.assertLess(result.residual_norm, 1e-8)
        self.assertTrue(np.isfinite(result.condition_number))

    def test_section_bem_multimode_radiation_matches_scalar_heave(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=8)
        scalar = solve_heave_radiation(offsets, omega_rad_s=4.0, free_surface_panel_count_per_side=12)
        multimode = solve_radiation_modes(offsets, omega_rad_s=4.0, free_surface_panel_count_per_side=12)
        heave_index = multimode.modes.index("heave")
        sway_index = multimode.modes.index("sway")
        self.assertEqual(multimode.status, "experimental_multimode_2d_free_surface_source_panel_not_validated")
        self.assertEqual(multimode.added_mass_matrix_per_m.shape, (3, 3))
        self.assertAlmostEqual(multimode.added_mass_matrix_per_m[heave_index, heave_index], scalar.added_mass_per_m)
        self.assertAlmostEqual(multimode.damping_matrix_per_m[heave_index, heave_index], scalar.damping_per_m)
        self.assertAlmostEqual(multimode.added_mass_matrix_per_m[sway_index, heave_index], 0.0, places=10)
        self.assertAlmostEqual(multimode.added_mass_matrix_per_m[heave_index, sway_index], 0.0, places=10)
        self.assertTrue(np.isfinite(multimode.added_mass_matrix_per_m).all())
        self.assertTrue(np.isfinite(multimode.damping_matrix_per_m).all())
        self.assertLess(max(multimode.residual_norm_by_mode.values()), 1e-8)

    def test_section_bem_multimode_diagnostics_flatten_matrix(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=8)
        rows = section_bem_multimode_radiation_diagnostics(
            offsets,
            omega_rad_s=4.0,
            free_surface_panel_count_per_side=12,
        )
        self.assertEqual(len(rows), 9)
        self.assertIn("response_mode", rows[0])
        self.assertIn("excitation_mode", rows[0])
        self.assertIn("reciprocal_added_gap_per_m", rows[0])
        self.assertEqual(rows[0]["status"], "experimental_multimode_2d_free_surface_source_panel_not_validated")

    def test_section_bem_pressure_transfer_integrates_to_known_forces(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=8)
        pressure = solve_pressure_transfer(
            offsets,
            omega_rad_s=4.0,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=4.0**2 / 9.80665,
            free_surface_panel_count_per_side=12,
        )
        multimode = solve_radiation_modes(offsets, omega_rad_s=4.0, free_surface_panel_count_per_side=12)
        excitation = solve_wave_excitation(
            offsets,
            omega_rad_s=4.0,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=4.0**2 / 9.80665,
            free_surface_panel_count_per_side=12,
        )
        self.assertEqual(pressure.status, "experimental_section_pressure_transfer_not_validated")
        self.assertEqual(pressure.radiation_potential_m2_s.shape, (pressure.panel_count, 3))
        self.assertTrue(np.isfinite(pressure.radiation_potential_m2_s).all())
        self.assertEqual(pressure.radiation_pressure_pa.shape, (pressure.panel_count, 3))
        self.assertTrue(np.isfinite(pressure.radiation_pressure_pa).all())
        self.assertTrue(np.isfinite(pressure.total_wave_pressure_pa).all())
        np.testing.assert_allclose(pressure.radiation_force_matrix_per_m, multimode.complex_force_matrix_per_m)
        np.testing.assert_allclose(
            pressure.total_wave_force_vector_per_m,
            np.array(
                [
                    excitation.complex_lateral_force_per_m,
                    excitation.complex_vertical_force_per_m,
                    excitation.complex_roll_moment_per_m,
                ]
            ),
            atol=1e-10,
        )
        np.testing.assert_allclose(
            pressure.total_wave_pressure_pa,
            pressure.incident_pressure_pa + pressure.diffracted_pressure_pa,
        )

    def test_section_bem_pressure_transfer_diagnostics_flatten_panels(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=8)
        rows = section_bem_pressure_transfer_diagnostics(
            offsets,
            omega_rad_s=4.0,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=4.0**2 / 9.80665,
            free_surface_panel_count_per_side=12,
        )
        self.assertEqual(len(rows), 16 * (3 + 3))
        kinds = {row["pressure_kind"] for row in rows}
        self.assertEqual(kinds, {"radiation", "wave_incident", "wave_diffracted", "wave_total"})
        self.assertIn("pressure_real_pa", rows[0])
        self.assertEqual(rows[0]["status"], "experimental_section_pressure_transfer_not_validated")

    def test_pdstrip_style_heave_solver_returns_finite_terms(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=6)
        result = solve_heave_radiation_pdstrip_style(
            offsets,
            omega_rad_s=4.0,
            free_surface_panel_count_per_side=12,
            body_panel_count=20,
        )
        self.assertEqual(result.status, "experimental_pdstrip_style_section_solver_not_validated")
        self.assertGreater(result.added_mass_per_m, 0.0)
        self.assertGreaterEqual(result.damping_per_m, 0.0)
        self.assertLess(result.residual_norm, 1e-8)
        self.assertTrue(np.isfinite(result.condition_number))

    def test_section_offsets_resample_by_arclength_controls_body_panels(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=2)
        refined = offsets.resample_by_arclength(12)
        self.assertEqual(len(refined.y_m), 13)
        self.assertAlmostEqual(refined.y_m[0], offsets.y_m[0])
        self.assertAlmostEqual(refined.z_down_m[0], offsets.z_down_m[0])
        self.assertAlmostEqual(refined.y_m[-1], offsets.y_m[-1])
        self.assertAlmostEqual(refined.z_down_m[-1], offsets.z_down_m[-1])
        result = solve_heave_radiation(offsets, omega_rad_s=4.0, free_surface_panel_count_per_side=4, body_panel_count=12)
        self.assertEqual(result.panel_count, 12)

    def test_section_bem_wave_excitation_returns_finite_forces(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=6)
        result = solve_wave_excitation(
            offsets,
            omega_rad_s=4.0,
            wave_amplitude_m=1.0,
            wavenumber_rad_m=4.0**2 / 9.80665,
            transverse_wavenumber_rad_m=0.0,
            free_surface_panel_count_per_side=4,
        )
        self.assertEqual(result.status, "experimental_2d_free_surface_source_panel_not_validated")
        self.assertGreater(abs(result.complex_vertical_force_per_m), 0.0)
        self.assertAlmostEqual(abs(result.complex_lateral_force_per_m), 0.0, places=6)
        self.assertLess(result.residual_norm, 1e-8)
        self.assertTrue(np.isfinite(result.condition_number))

    def test_section_bem_convergence_study_reports_refinement_changes(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=8)
        rows = section_bem_convergence_study(offsets, omega_rad_s=4.0, panel_counts_per_side=(6, 8, 10, 12))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["added_mass_rel_change_from_previous"], "")
        self.assertNotEqual(rows[-1]["added_mass_rel_change_from_previous"], "")
        self.assertLess(float(rows[-1]["added_mass_rel_change_from_previous"]), 0.05)
        self.assertLess(float(rows[-1]["damping_rel_change_from_previous"]), 0.05)

    def test_section_bem_body_panel_convergence_study_reports_refinement_changes(self):
        offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.18, point_count_per_side=2)
        rows = section_bem_body_panel_convergence_study(
            offsets,
            omega_rad_s=4.0,
            body_panel_counts=(8, 12, 16, 20),
            free_surface_panel_count_per_side=12,
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["added_mass_rel_change_from_previous"], "")
        self.assertEqual(rows[-1]["body_panel_count"], 20)
        self.assertLess(float(rows[-1]["added_mass_rel_change_from_previous"]), 0.05)
        self.assertLess(float(rows[-1]["damping_rel_change_from_previous"]), 0.05)

    def test_experimental_bem_matrix_path_is_available_but_unvalidated(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        matrices = assemble_experimental_bem_6dof_matrices(
            hull,
            omega_rad_s=4.0,
            free_surface_panel_count_per_side=4,
        )
        self.assertEqual(matrices.status, "experimental_2d_free_surface_source_panel_not_validated")
        self.assertEqual(matrices.added_mass.shape, (6, 6))
        self.assertGreater(matrices.added_mass[2, 2], 0.0)
        self.assertGreaterEqual(matrices.damping[2, 2], 0.0)

    def test_section_bem_station_diagnostics_cover_stations_and_frequencies(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = section_bem_station_diagnostics(
            hull,
            omega_rad_s=np.array([2.0, 4.0]),
            free_surface_panel_count_per_side=3,
        )
        self.assertEqual(len(rows), 10)
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertGreater(len(active), 0)
        self.assertIn("condition_number", active[0])
        self.assertIn("residual_norm", active[0])
        self.assertLess(max(float(row["residual_norm"]) for row in active), 1e-7)

    def test_section_bem_station_diagnostics_can_resample_body_panels(self):
        hull = load_station_hull(ROOT / "configs" / "example_station_offsets_csv.yml")
        rows = section_bem_station_diagnostics(
            hull,
            omega_rad_s=np.array([3.0]),
            free_surface_panel_count_per_side=3,
            body_panel_count=12,
        )
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertTrue(active)
        self.assertEqual(active[0]["body_panel_count"], 12)

    def test_section_bem_multimode_station_diagnostics_cover_mode_pairs(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=3)
        rows = section_bem_multimode_station_diagnostics(
            hull,
            omega_rad_s=np.array([4.0]),
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
        )
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertTrue(active)
        self.assertIn("response_mode", active[0])
        self.assertIn("excitation_mode", active[0])
        self.assertIn("reciprocal_added_gap_per_m", active[0])
        self.assertEqual(len(active) % 9, 0)

    def test_section_bem_pressure_transfer_station_diagnostics_cover_panels(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=3)
        rows = section_bem_pressure_transfer_station_diagnostics(
            hull,
            omega_rad_s=np.array([4.0]),
            wave_amplitude_m=1.0,
            wavenumber_rad_m=np.array([4.0**2 / 9.80665]),
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
        )
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertTrue(active)
        self.assertIn("panel_index", active[0])
        self.assertIn("pressure_kind", active[0])
        self.assertIn("pressure_abs_pa", active[0])
        self.assertEqual({row["pressure_kind"] for row in active}, {"radiation", "wave_incident", "wave_diffracted", "wave_total"})

    def test_section_bem_station_diagnostics_can_use_pdstrip_style_solver(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = section_bem_station_diagnostics(
            hull,
            omega_rad_s=np.array([4.0]),
            free_surface_panel_count_per_side=10,
            body_panel_count=16,
            section_solver="pdstrip_style",
        )
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertTrue(active)
        self.assertEqual(active[0]["section_solver"], "pdstrip_style")
        self.assertEqual(active[0]["status"], "experimental_pdstrip_style_section_solver_not_validated")
        self.assertGreater(max(float(row["added_mass_per_m"]) for row in active), 0.0)

    def test_section_bem_excitation_diagnostics_cover_stations(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = section_bem_excitation_diagnostics(
            hull,
            omega_rad_s=np.array([2.0, 4.0]),
            wave_amplitude_m=1.0,
            wavenumber_rad_m=np.array([(2.0**2) / 9.80665, (4.0**2) / 9.80665]),
            free_surface_panel_count_per_side=3,
        )
        self.assertEqual(len(rows), 10)
        active = [row for row in rows if row["status"] != "skipped_tiny_section"]
        self.assertGreater(len(active), 0)
        self.assertIn("vertical_force_abs_per_m", active[0])
        self.assertIn("lateral_force_abs_per_m", active[0])
        self.assertLess(max(float(row["residual_norm"]) for row in active), 1e-7)

    def test_experimental_bem_wave_excitation_vector_is_finite(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        excitation = experimental_bem_wave_excitation_6dof(
            hull,
            wave_amplitude_m=1.0,
            omega_rad_s=4.0,
            wavenumber_rad_m=4.0**2 / 9.80665,
            heading_deg=180.0,
            free_surface_panel_count_per_side=3,
        )
        self.assertEqual(excitation.shape, (6,))
        self.assertTrue(np.isfinite(excitation).all())
        self.assertGreater(abs(excitation[2]), 0.0)
        self.assertAlmostEqual(abs(excitation[1]), 0.0, places=6)

    def test_station_rao_can_use_experimental_bem_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            radiation_model="section_bem",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=12,
        )
        self.assertEqual(rows[0]["radiation_model"], "section_bem")
        self.assertEqual(rows[0]["excitation_model"], "section_bem_incident_diffraction_experimental")
        self.assertEqual(rows[0]["matrix_status"], "experimental_2d_free_surface_source_panel_not_validated")
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_station_rao_can_use_pdstrip_style_radiation_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            radiation_model="pdstrip_style",
            bem_free_surface_panel_count_per_side=10,
            bem_body_panel_count=16,
        )
        self.assertEqual(rows[0]["radiation_model"], "pdstrip_style")
        self.assertEqual(rows[0]["matrix_status"], "experimental_pdstrip_style_section_solver_not_validated")
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_forward_speed_2p5d_matrix_path_is_available_but_unvalidated(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        matrices = assemble_forward_speed_2p5d_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
        )
        self.assertEqual(matrices.status, "experimental_pdstrip_like_forward_speed_assembly_not_validated")
        self.assertTrue(np.isfinite(matrices.added_mass).all())
        self.assertTrue(np.isfinite(matrices.damping).all())
        self.assertGreater(matrices.added_mass[2, 2], 0.0)
        self.assertNotAlmostEqual(matrices.damping[2, 4], matrices.damping[4, 2])

    def test_forward_speed_2p5d_component_diagnostics_sum_to_total(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        rows = forward_speed_2p5d_component_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
        )
        self.assertEqual(len(rows), 12)
        by_component = {}
        for row in rows:
            key = (row["added_mass_coefficient"], row["damping_coefficient"])
            by_component.setdefault(key, {})[row["component"]] = row
        for component_rows in by_component.values():
            self.assertEqual(set(component_rows), {"main_radiation", "forward_gradient", "total"})
            added_parts = (
                float(component_rows["main_radiation"]["added_mass_value"])
                + float(component_rows["forward_gradient"]["added_mass_value"])
            )
            damping_parts = (
                float(component_rows["main_radiation"]["damping_value"])
                + float(component_rows["forward_gradient"]["damping_value"])
            )
            self.assertAlmostEqual(added_parts, float(component_rows["total"]["added_mass_value"]))
            self.assertAlmostEqual(damping_parts, float(component_rows["total"]["damping_value"]))

    def test_pdstrip_step_forward_speed_matrix_path_is_available_but_unvalidated(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        matrices = assemble_forward_speed_2p5d_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
            assembly_method="pdstrip_step",
        )
        self.assertEqual(matrices.status, "experimental_pdstrip_step_forward_speed_assembly_not_validated")
        self.assertTrue(np.isfinite(matrices.added_mass).all())
        self.assertTrue(np.isfinite(matrices.damping).all())
        self.assertGreater(matrices.added_mass[2, 2], 0.0)
        rows = forward_speed_2p5d_component_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
            assembly_method="pdstrip_step",
        )
        self.assertEqual({row["assembly_method"] for row in rows}, {"pdstrip_step"})
        self.assertEqual(rows[0]["status"], "experimental_pdstrip_step_forward_speed_assembly_not_validated")

    def test_forward_speed_pressure_transfer_diagnostics_close_main_operator(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = forward_speed_pressure_transfer_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=6,
            body_panel_count=10,
        )
        components = {row["component"] for row in rows}
        self.assertEqual(
            components,
            {
                "pressure_main_radiation_raw",
                "pressure_main_radiation_clipped_like_force",
                "force_main_radiation",
                "pressure_raw_minus_force_main_radiation",
                "pressure_clipped_minus_force_main_radiation",
            },
        )
        by_component = {}
        for row in rows:
            key = (row["added_mass_coefficient"], row["damping_coefficient"])
            by_component.setdefault(key, {})[row["component"]] = row
        for component_rows in by_component.values():
            diff_real = float(component_rows["pressure_clipped_minus_force_main_radiation"]["dynamic_operator_real"])
            diff_imag = float(component_rows["pressure_clipped_minus_force_main_radiation"]["dynamic_operator_imag"])
            self.assertAlmostEqual(diff_real, 0.0, places=8)
            self.assertAlmostEqual(diff_imag, 0.0, places=8)
        self.assertEqual(rows[0]["status"], "experimental_pressure_transfer_forward_speed_diagnostic_not_validated")

    def test_forward_speed_pressure_gradient_diagnostics_close_pdstrip_step_operator(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = forward_speed_pressure_gradient_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=6,
            body_panel_count=10,
        )
        sources = {row["source"] for row in rows}
        self.assertEqual(
            sources,
            {
                "pressure_raw_pdstrip_step",
                "pressure_clipped_pdstrip_step",
                "force_pdstrip_step",
                "pressure_raw_minus_force_pdstrip_step",
                "pressure_clipped_minus_force_pdstrip_step",
            },
        )
        parts = {row["operator_part"] for row in rows}
        self.assertEqual(parts, {"main_radiation", "forward_gradient", "total"})
        clipped_diff = [row for row in rows if row["source"] == "pressure_clipped_minus_force_pdstrip_step"]
        self.assertTrue(clipped_diff)
        for row in clipped_diff:
            self.assertAlmostEqual(float(row["dynamic_operator_real"]), 0.0, places=8)
            self.assertAlmostEqual(float(row["dynamic_operator_imag"]), 0.0, places=8)
        self.assertEqual(rows[0]["status"], "experimental_pressure_transfer_gradient_end_term_diagnostic_not_validated")

    def test_forward_speed_coupling_variant_diagnostics_include_sign_and_transpose_choices(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        rows = forward_speed_coupling_variant_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
        )
        variants = {row["variant"] for row in rows}
        self.assertIn("current", variants)
        self.assertIn("current_transpose", variants)
        self.assertIn("reverse_gradient", variants)
        self.assertIn("negative_speed_term", variants)
        self.assertIn("pdstrip_step", variants)
        self.assertIn("pdstrip_step_transpose", variants)
        current_a35 = [
            row
            for row in rows
            if row["variant"] == "current" and row["added_mass_coefficient"] == "A35"
        ][0]
        transposed_a35 = [
            row
            for row in rows
            if row["variant"] == "current_transpose" and row["added_mass_coefficient"] == "A35"
        ][0]
        self.assertNotAlmostEqual(
            float(current_a35["added_mass_value"]),
            float(transposed_a35["added_mass_value"]),
        )

    def test_forward_speed_coupling_station_contribution_diagnostics_include_pressure_sources(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = forward_speed_coupling_station_contribution_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
            coefficients=("B35", "B53"),
        )
        self.assertTrue(rows)
        sources = {row["source"] for row in rows}
        self.assertIn("pressure_clipped", sources)
        self.assertIn("force_collocation", sources)
        self.assertIn("force_pdstrip_style", sources)
        self.assertEqual({"B35", "B53"}, {row["coefficient"] for row in rows})
        self.assertIn("pdstrip_step", {row["assembly_method"] for row in rows})
        self.assertIn("total", {row["operator_part"] for row in rows})
        self.assertTrue(all(np.isfinite(float(row["station_contribution_value"])) for row in rows))

    def test_forward_speed_station_contribution_diagnostics_include_added_and_pitch_terms(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        rows = forward_speed_coupling_station_contribution_diagnostics(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
            coefficients=("A35", "B55"),
        )
        self.assertTrue(rows)
        self.assertEqual({"A35", "B55"}, {row["coefficient"] for row in rows})
        self.assertIn("added_mass", {row["coefficient_kind"] for row in rows})
        self.assertIn("damping", {row["coefficient_kind"] for row in rows})
        self.assertIn("pressure_clipped", {row["source"] for row in rows})
        self.assertTrue(all(np.isfinite(float(row["station_contribution_value"])) for row in rows))

    def test_station_rao_can_use_forward_speed_2p5d_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            speed_mps=2.0,
            radiation_model="strip_2p5d_forward",
            bem_free_surface_panel_count_per_side=8,
            bem_body_panel_count=12,
        )
        self.assertEqual(rows[0]["radiation_model"], "strip_2p5d_forward")
        self.assertEqual(rows[0]["matrix_status"], "experimental_pdstrip_like_forward_speed_assembly_not_validated")
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_station_rao_can_use_pdstrip_step_forward_speed_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            speed_mps=2.0,
            radiation_model="strip_2p5d_pdstrip_step",
            bem_free_surface_panel_count_per_side=8,
            bem_body_panel_count=12,
        )
        self.assertEqual(rows[0]["radiation_model"], "strip_2p5d_pdstrip_step")
        self.assertEqual(rows[0]["matrix_status"], "experimental_pdstrip_step_forward_speed_assembly_not_validated")
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_pressure_transfer_forward_speed_matrix_path_is_available_but_unvalidated(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        continuous = assemble_pressure_transfer_forward_speed_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
        )
        step = assemble_pressure_transfer_forward_speed_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
            assembly_method="pdstrip_step",
        )
        self.assertEqual(continuous.status, "experimental_pressure_transfer_forward_speed_assembly_not_validated")
        self.assertEqual(step.status, "experimental_pressure_transfer_pdstrip_step_forward_speed_assembly_not_validated")
        self.assertTrue(np.isfinite(continuous.added_mass[2, 2]))
        self.assertTrue(np.isfinite(step.damping[4, 4]))

    def test_pressure_transfer_pdstrip_damping_forward_speed_matrix_path_is_available_but_unvalidated(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        continuous = assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
        )
        step = assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=4,
            body_panel_count=8,
            assembly_method="pdstrip_step",
        )
        self.assertEqual(
            continuous.status,
            "diagnostic_pressure_transfer_added_pdstrip_style_damping_forward_speed_assembly_not_validated",
        )
        self.assertEqual(
            step.status,
            "diagnostic_pressure_transfer_added_pdstrip_style_damping_pdstrip_step_forward_speed_assembly_not_validated",
        )
        self.assertTrue(np.isfinite(continuous.added_mass[2, 2]))
        self.assertTrue(np.isfinite(continuous.damping[2, 4]))
        self.assertTrue(np.isfinite(step.damping[4, 4]))

    def test_station_rao_can_use_pressure_transfer_forward_speed_models(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        for model, status in (
            ("pressure_transfer_forward", "experimental_pressure_transfer_forward_speed_assembly_not_validated"),
            (
                "pressure_transfer_pdstrip_step",
                "experimental_pressure_transfer_pdstrip_step_forward_speed_assembly_not_validated",
            ),
            (
                "pressure_transfer_pdstrip_damping_forward",
                "diagnostic_pressure_transfer_added_pdstrip_style_damping_forward_speed_assembly_not_validated",
            ),
            (
                "pressure_transfer_pdstrip_damping_pdstrip_step",
                "diagnostic_pressure_transfer_added_pdstrip_style_damping_pdstrip_step_forward_speed_assembly_not_validated",
            ),
        ):
            rows = station_rao_frequency_sweep(
                hull,
                body,
                np.array([2.5]),
                speed_mps=2.0,
                radiation_model=model,
                bem_free_surface_panel_count_per_side=4,
                bem_body_panel_count=8,
            )
            self.assertEqual(rows[0]["radiation_model"], model)
            self.assertEqual(rows[0]["matrix_status"], status)
            self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_hybrid_forward_coupling_keeps_prototype_diagonals_and_forward_couplings(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=7)
        prototype = assemble_prototype_6dof_matrices(hull, omega_rad_s=4.0, speed_mps=2.0)
        forward = assemble_forward_speed_2p5d_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
        )
        hybrid = assemble_hybrid_forward_coupling_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=8,
            body_panel_count=12,
        )
        self.assertEqual(hybrid.status, "diagnostic_prototype_diagonal_forward_coupling_not_validated")
        for idx in (2, 4):
            self.assertAlmostEqual(hybrid.added_mass[idx, idx], prototype.added_mass[idx, idx])
            self.assertAlmostEqual(hybrid.damping[idx, idx], prototype.damping[idx, idx])
        for row_idx, col_idx in ((2, 4), (4, 2)):
            self.assertAlmostEqual(hybrid.added_mass[row_idx, col_idx], forward.added_mass[row_idx, col_idx])
            self.assertAlmostEqual(hybrid.damping[row_idx, col_idx], forward.damping[row_idx, col_idx])

    def test_station_rao_can_use_hybrid_forward_coupling_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            speed_mps=2.0,
            radiation_model="hybrid_forward_coupling",
            bem_free_surface_panel_count_per_side=8,
            bem_body_panel_count=12,
        )
        self.assertEqual(rows[0]["radiation_model"], "hybrid_forward_coupling")
        self.assertEqual(rows[0]["matrix_status"], "diagnostic_prototype_diagonal_forward_coupling_not_validated")
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))

    def test_hybrid_pressure_damping_coupling_uses_pressure_damping_only_for_couplings(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        prototype = assemble_prototype_6dof_matrices(hull, omega_rad_s=4.0, speed_mps=2.0)
        forward = assemble_forward_speed_2p5d_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=3,
            body_panel_count=8,
        )
        pressure = assemble_pressure_transfer_forward_speed_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=3,
            body_panel_count=8,
            assembly_method="pdstrip_step",
        )
        hybrid = assemble_hybrid_pressure_damping_coupling_matrices(
            hull,
            omega_rad_s=4.0,
            speed_mps=2.0,
            free_surface_panel_count_per_side=3,
            body_panel_count=8,
        )
        self.assertEqual(
            hybrid.status,
            "diagnostic_prototype_diagonal_forward_added_pressure_damping_coupling_not_validated",
        )
        for idx in (2, 4):
            self.assertAlmostEqual(hybrid.added_mass[idx, idx], prototype.added_mass[idx, idx])
            self.assertAlmostEqual(hybrid.damping[idx, idx], prototype.damping[idx, idx])
        for row_idx, col_idx in ((2, 4), (4, 2)):
            self.assertAlmostEqual(hybrid.added_mass[row_idx, col_idx], forward.added_mass[row_idx, col_idx])
            self.assertAlmostEqual(hybrid.damping[row_idx, col_idx], pressure.damping[row_idx, col_idx])

    def test_station_rao_can_use_hybrid_pressure_damping_coupling_model(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(80.0, 0.1, 0.75, 0.75)
        rows = station_rao_frequency_sweep(
            hull,
            body,
            np.array([2.5]),
            speed_mps=2.0,
            radiation_model="hybrid_pressure_damping_coupling",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=8,
        )
        self.assertEqual(rows[0]["radiation_model"], "hybrid_pressure_damping_coupling")
        self.assertEqual(
            rows[0]["matrix_status"],
            "diagnostic_prototype_diagonal_forward_added_pressure_damping_coupling_not_validated",
        )
        self.assertTrue(np.isfinite(rows[0]["heave_rao_abs_per_m"]))


if __name__ == "__main__":
    unittest.main()
