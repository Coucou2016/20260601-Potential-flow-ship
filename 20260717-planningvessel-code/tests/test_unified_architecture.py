import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from planing_seakeeping.geometry import (
    geometry_source_audit,
    load_unified_offsets_csv,
    make_delft372_catamaran_from_offsets,
    make_delft372_demihull_from_offsets,
    make_delft372_demihull_surrogate,
    make_trimaran2019_surrogate,
    multibody_sections,
)
from planing_seakeeping.kernels.hydrofoil import (
    HydrofoilGeometry,
    HydrofoilState,
    finite_wing_lift_slope,
    hydrofoil_force,
    routh_hurwitz_quartic,
)
from planing_seakeeping.kernels.linear_2p5d import (
    A1_CONVENTION_CANDIDATE_STATUS,
    A1_CONTROL_HISTORY_INHERITANCE_STATUS,
    A1_CONTROL_SURFACE_CANDIDATE_STATUS,
    A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS,
    A1_CLOSED_CYLINDER_ADDED_MASS_STATUS,
    A1_FREE_SURFACE_OSCILLATOR_STATUS,
    A1_HISTORY_RHS_CONVERGENCE_STATUS,
    A1_HISTORY_KERNEL_DERIVATIVE_STATUS,
    A1_INNER_FREE_SURFACE_STATE_STATUS,
    A1_INNER_KERNEL_CANDIDATE_STATUS,
    A1_INNER_KERNEL_GREEN_IDENTITY_STATUS,
    A1_INNER_MIXED_BOUNDARY_STATUS,
    LINEAR_2P5D_CLOSED_CYLINDER_ADDED_MASS_STATUS,
    A1_OUTER_CONTROL_BALANCE_STATUS,
    A1_POTENTIAL_UNIT_CLOSURE_STATUS,
    A1_RHS_SOURCE_DECOMPOSITION_STATUS,
    A1_LOW_FN_STATION_MIN,
    DEFAULT_A1_HEAVE_PITCH_CONVENTION,
    FreeSurfaceMarchingState,
    MATCHED_WIGLEY_SENSITIVITY_STATUS,
    Matched2p5DSectionSolver,
    MatchedSectionBoundaryData,
    MatchedSectionForceResult,
    MatchedSectionSolution,
    MatchedWigleySensitivityCase,
    a1_convention_candidate_cases,
    a1_convention_candidate_mapping_rows,
    a1_closed_cylinder_added_mass_rows,
    a1_control_surface_candidate_cases,
    a1_control_surface_green_identity_rows,
    a1_control_history_inheritance_rows,
    a1_free_surface_oscillator_rows,
    a1_history_rhs_convergence_rows,
    a1_history_kernel_derivative_rows,
    a1_inner_free_surface_state_rows,
    a1_inner_kernel_green_identity_rows,
    a1_inner_mixed_boundary_identity_rows,
    a1_inner_kernel_candidate_cases,
    a1_grid_recommendation,
    a1_outer_control_balance_rows,
    a1_rhs_source_decomposition_rows,
    advance_free_surface_state,
    assemble_frequency_domain_from_station_hull,
    audit_matched_system_blocks,
    audit_closed_cylinder_heave_added_mass,
    audit_control_history_inheritance,
    audit_outer_control_balance,
    audit_rhs_source_decomposition,
    audit_free_surface_oscillator_marching,
    audit_history_rhs_quadrature_convergence,
    audit_heave_pitch_a1_convention,
    audit_inner_free_surface_state_scale,
    audit_inner_kernel_green_identity,
    audit_inner_mixed_boundary_green_identity,
    audit_body_boundary_inner_fluid_normal,
    audit_outer_control_surface_green_identity,
    audit_transient_history_kernel_normal_derivative,
    build_closed_ellipse_inner_boundary,
    build_control_surface_geometry,
    build_flat_free_surface_geometry,
    build_inner_domain_panel_geometry,
    build_section_marching_grid,
    build_transient_free_surface_history,
    build_two_zone_waterline_free_surface_geometry,
    build_waterline_clipped_free_surface_geometry,
    compute_heave_pitch_control_surface_end_term_force_matrix,
    compute_heave_pitch_stokes_body_forward_speed_force_matrix,
    deep_water_encounter,
    deep_water_head_sea_wave_from_encounter,
    estimate_local_time_phase_body_potential_x_gradient,
    heave_radiation_normal_velocity,
    initialize_free_surface_state,
    integrate_section_heave_pitch_force,
    inner_domain_source_normal_matrix,
    inner_domain_source_potential_matrix,
    local_time_from_station,
    matched_wigley_best_case_summary,
    matched_wigley_a1_convention_candidate_rows,
    matched_wigley_a1_control_surface_candidate_rows,
    matched_wigley_a1_inner_kernel_candidate_rows,
    matched_wigley_sensitivity_rows,
    pitch_radiation_normal_velocity,
    pitch_radiation_normal_velocity_components,
    pressure_force_to_added_mass_damping,
    resample_free_surface_state,
    write_matched_wigley_sensitivity,
    write_a1_convention_candidate_benchmark,
    write_a1_closed_cylinder_added_mass_audit,
    write_a1_control_surface_candidate_benchmark,
    write_a1_control_surface_green_identity_audit,
    write_a1_control_history_inheritance_audit,
    write_a1_free_surface_oscillator_audit,
    write_a1_history_rhs_convergence_audit,
    write_a1_history_kernel_derivative_audit,
    write_a1_inner_free_surface_state_audit,
    write_a1_inner_kernel_green_identity_audit,
    write_a1_inner_mixed_boundary_identity_audit,
    write_a1_inner_kernel_candidate_benchmark,
    write_a1_outer_control_balance_audit,
    write_a1_rhs_source_decomposition_audit,
    write_matched_wigley_station_diagnostics,
    closed_boundary_three_part_panel_counts,
    split_inner_boundary_geometry_by_panel_counts,
)
from planing_seakeeping.kernels.multihull import ComponentLoad, assemble_component_loads
from planing_seakeeping.kernels.nonlinear_2dt import SectionPlaneManager
from planing_seakeeping.providers.planing_2dt import (
    NonlinearBEM2DtProvider,
    ReducedOrderPlaning2DtProvider,
    ReducedOrderPlaningLoadProvider,
)
from planing_seakeeping.providers.linear_hydrodynamics import LinearFrequencyProvider, build_legacy_2p5d_provider
from planing_seakeeping.regimes import LoadArbiter, RegimeObservables
from planing_seakeeping.schema import (
    HullComponentConfig,
    HydrofoilProviderConfig,
    Linear2p5DProviderConfig,
    MultihullInteractionProviderConfig,
    VesselConfig,
)
from planing_seakeeping.section_bem import hard_chine_v_offsets, wigley_section_offsets
from planing_seakeeping.station_2p5d import HardChineStation, RigidBody6DOF, StationHull, make_wigley_iii_hull
from planing_seakeeping.types import ValidityReport


ROOT = Path(__file__).resolve().parents[1]


class UnifiedArchitectureTests(unittest.TestCase):
    def test_smooth_regime_weights_sum_to_one(self):
        report = LoadArbiter().weights(
            RegimeObservables(
                fn_l=0.8,
                fn_b=2.0,
                buoyancy_fraction=0.25,
                planing_lift_fraction=0.8,
                wetted_length_over_beam=3.0,
                transom_dry=True,
            )
        )
        self.assertAlmostEqual(sum(report.as_array()), 1.0)
        self.assertGreater(report.planing, report.displacement)

    def test_schema_rejects_placeholder_production(self):
        with self.assertRaisesRegex(ValueError, "placeholder"):
            HydrofoilProviderConfig(enabled=True, production=True, model="placeholder").validate()
        with self.assertRaisesRegex(ValueError, "Catamaran"):
            VesselConfig(
                name="bad_cat",
                platform_type="catamaran",
                hull_components=(HullComponentConfig(name="main"),),
            ).validate()
        with self.assertRaisesRegex(ValueError, "independent_hulls"):
            MultihullInteractionProviderConfig(enabled=True, production=True, model="independent_hulls").validate()

    def test_linear_frequency_provider_routes_matched_and_legacy_2p5d(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(78.0, 0.2, 0.75, 0.8)
        config = Linear2p5DProviderConfig(
            formulation="matched_bie",
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        provider = LinearFrequencyProvider(
            source="linear_2p5d",
            rho_water_kg_m3=1000.0,
            config=config,
            matched_options={
                "history_steps": 2,
                "history_quadrature_count": 16,
                "history_k_max": 15.0,
            },
        )
        hydro = provider.solve_station_hull(hull, body, np.array([3.0]), speed_mps=1.2)
        self.assertEqual(hydro.metadata["provider_route"], "matched_bie_station_sweep")
        self.assertEqual(hydro.metadata["provider_formulation"], "matched_bie")
        self.assertIn("heave_pitch_complex_force_matrices", hydro.contribution_breakdown)
        self.assertTrue(np.isfinite(hydro.added_mass[0, 2, 2]))
        self.assertFalse(hydro.validity.is_validated)

        legacy = build_legacy_2p5d_provider().solve_station_hull(hull, body, np.array([3.0]), speed_mps=1.2)
        self.assertEqual(legacy.metadata["provider_route"], "legacy_station_forward_speed_assembly")
        self.assertEqual(legacy.metadata["provider_formulation"], "legacy_station_prototype")
        with self.assertRaisesRegex(ValueError, "production-ready"):
            LinearFrequencyProvider(source="linear_2p5d", production=True)
        with self.assertRaisesRegex(ValueError, "production-ready"):
            LinearFrequencyProvider(
                source="linear_2p5d",
                config=Linear2p5DProviderConfig(production=True, formulation="matched_bie"),
            )

    def test_unified_offsets_csv_loads_component_hull(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "offsets.csv"
            path.write_text(
                "\n".join(
                    [
                        "component,station_id,x_from_ap_m,point_order,y_m,z_m,feature",
                        "main,S0,0.0,0,0.1,0.0,chine",
                        "main,S0,0.0,1,0.0,0.1,keel",
                        "main,S0,0.0,2,-0.1,0.0,chine",
                        "main,S1,1.0,0,0.1,0.0,chine",
                        "main,S1,1.0,1,0.0,0.1,keel",
                        "main,S1,1.0,2,-0.1,0.0,chine",
                    ]
                ),
                encoding="utf-8",
            )
            hulls = load_unified_offsets_csv(path)
        self.assertIn("main", hulls)
        self.assertGreater(hulls["main"].hydrostatics().displacement_volume_m3, 0.0)

    def test_surrogate_geometry_is_audited_as_not_validation_ready(self):
        components = (make_delft372_demihull_surrogate(),) + make_trimaran2019_surrogate()
        audit = geometry_source_audit(components)
        self.assertTrue(all(not row["usable_for_validation"] for row in audit))
        sections = multibody_sections(components, np.linspace(0.0, 3.0, 5))
        self.assertGreater(max(section.active_component_count for section in sections), 1)

    def test_delft372_extracted_offsets_match_reported_hydrostatics(self):
        component = make_delft372_demihull_from_offsets(ROOT / "benchmarks/delft372/delft372_demihull_offsets.csv")
        hydro = component.hull.hydrostatics()
        total_displacement_kg = 2.0 * 1000.0 * hydro.displacement_volume_m3
        audit = geometry_source_audit((component,))
        self.assertEqual(len(component.hull.stations), 23)
        self.assertTrue(audit[0]["usable_for_validation"])
        self.assertAlmostEqual(total_displacement_kg, 87.07, delta=1.75)
        self.assertAlmostEqual(hydro.center_of_buoyancy_x_m, 1.41, delta=0.05)

    def test_delft372_catamaran_offsets_assemble_port_starboard_components(self):
        components = make_delft372_catamaran_from_offsets(
            ROOT / "benchmarks/delft372/delft372_demihull_offsets.csv"
        )
        self.assertEqual(tuple(component.role for component in components), ("port_demihull", "starboard_demihull"))
        self.assertAlmostEqual(components[1].origin_from_vessel_ap_m[1] - components[0].origin_from_vessel_ap_m[1], 0.70)
        self.assertTrue(all(row["usable_for_validation"] for row in geometry_source_audit(components)))
        sections = multibody_sections(components, np.linspace(0.0, 3.0, 7))
        self.assertGreaterEqual(max(section.active_component_count for section in sections), 2)

    def test_validation_target_matrix_keeps_known_gates_visible(self):
        path = ROOT / "benchmarks/validation_targets.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = {row["gate_id"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rows["G3"]["status"], "PASS")
        self.assertEqual(rows["G2"]["status"], "BLOCKED")
        self.assertEqual(rows["G5"]["status"], "BLOCKED")
        self.assertIn("delft372_demihull_offsets.csv", rows["G3"]["current_artifact"])

    def test_a1_marching_grid_maps_station_to_local_time(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        grid = build_section_marching_grid(hull, speed_mps=6.0)
        self.assertEqual(grid.x_from_ap_m.shape, (5,))
        self.assertAlmostEqual(grid.local_time_s[0], 0.5)
        self.assertAlmostEqual(grid.local_time_s[-1], 0.0)
        self.assertTrue(np.all(np.diff(grid.x_from_ap_m) > 0.0))
        self.assertTrue(np.all(np.diff(grid.local_time_s) < 0.0))

    def test_a1_inner_domain_simple_green_block_solves(self):
        offsets = hard_chine_v_offsets(beam_m=0.4, draft_m=0.12, point_count_per_side=5)
        geometry = build_inner_domain_panel_geometry(offsets, body_panel_count=12)
        normal_matrix = inner_domain_source_normal_matrix(geometry)
        potential_matrix = inner_domain_source_potential_matrix(geometry)
        rhs = heave_radiation_normal_velocity(geometry, omega_rad_s=4.0)
        system = Matched2p5DSectionSolver().assemble_inner_domain_system(
            offsets,
            rhs,
            body_panel_count=12,
        )
        solution = system.solve()
        self.assertEqual(normal_matrix.shape, (12, 12))
        self.assertEqual(potential_matrix.shape, (12, 12))
        self.assertTrue(np.all(np.isfinite(solution)))
        self.assertLess(system.relative_residual(solution), 1e-10)
        self.assertGreater(system.condition_number, 1.0)

    def test_a1_pitch_radiation_velocity_sign_diagnostics_are_explicit(self):
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.3, draft_m=0.1), 6)
        base = pitch_radiation_normal_velocity(body, 2.0, 0.4, forward_speed_mps=1.1)
        oscillatory, forward = pitch_radiation_normal_velocity_components(body, 2.0, 0.4, forward_speed_mps=1.1)
        self.assertTrue(np.allclose(base, oscillatory + forward))
        self.assertGreater(np.linalg.norm(oscillatory), 0.0)
        self.assertGreater(np.linalg.norm(forward), 0.0)
        flipped_mode = pitch_radiation_normal_velocity(
            body,
            2.0,
            0.4,
            forward_speed_mps=1.1,
            radiation_sign=-1.0,
        )
        flipped_speed = pitch_radiation_normal_velocity(
            body,
            2.0,
            0.4,
            forward_speed_mps=1.1,
            forward_speed_sign=-1.0,
        )
        self.assertTrue(np.allclose(flipped_mode, -base))
        self.assertFalse(np.allclose(flipped_speed, base))

    def test_a1_free_surface_staggered_marching_matches_equations(self):
        y = np.linspace(-0.5, 0.5, 5)
        vertical_velocity = np.full_like(y, 0.2)
        state = initialize_free_surface_state(y, vertical_velocity, dt_s=0.1, gravity_m_s2=10.0)
        self.assertTrue(np.allclose(state.elevation_m, 0.01))
        self.assertTrue(np.allclose(state.potential_m2_s, -0.01))
        advanced = advance_free_surface_state(state, vertical_velocity, dt_s=0.1, gravity_m_s2=10.0)
        self.assertTrue(np.allclose(advanced.elevation_m, 0.03))
        self.assertTrue(np.allclose(advanced.potential_m2_s, -0.04))
        previous_level = advance_free_surface_state(
            state,
            vertical_velocity,
            dt_s=0.1,
            gravity_m_s2=10.0,
            potential_elevation_level="previous",
        )
        self.assertTrue(np.allclose(previous_level.elevation_m, 0.03))
        self.assertTrue(np.allclose(previous_level.potential_m2_s, -0.02))
        average_level = advance_free_surface_state(
            state,
            vertical_velocity,
            dt_s=0.1,
            gravity_m_s2=10.0,
            potential_elevation_level="average",
        )
        self.assertTrue(np.allclose(average_level.potential_m2_s, -0.03))
        gravity_flipped = initialize_free_surface_state(
            y,
            vertical_velocity,
            dt_s=0.1,
            gravity_m_s2=10.0,
            dynamic_gravity_sign=1.0,
        )
        self.assertTrue(np.allclose(gravity_flipped.potential_m2_s, 0.01))
        reverse_time = initialize_free_surface_state(
            y,
            vertical_velocity,
            dt_s=0.1,
            gravity_m_s2=10.0,
            time_direction_sign=-1.0,
        )
        self.assertTrue(np.allclose(reverse_time.elevation_m, -0.01))
        self.assertTrue(np.allclose(reverse_time.potential_m2_s, -0.01))

    def test_a1_free_surface_oscillator_audit_converges_with_step_refinement(self):
        coarse = audit_free_surface_oscillator_marching(dt_s=0.08, step_count=25)
        fine = audit_free_surface_oscillator_marching(dt_s=0.04, step_count=50)
        self.assertEqual(
            coarse.validity.status,
            "a1_free_surface_eq19_22_oscillator_diagnostic_not_hard_gate",
        )
        self.assertLess(fine.rms_elevation_normalized_error, coarse.rms_elevation_normalized_error)
        self.assertLess(fine.rms_potential_normalized_error, coarse.rms_potential_normalized_error)
        self.assertLess(fine.max_potential_normalized_error, 0.02)

    def test_a1_free_surface_oscillator_rows_and_writer_emit_csv(self):
        rows = a1_free_surface_oscillator_rows(dt_values=(0.08, 0.04), normalized_error_tolerance=0.08)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_FREE_SURFACE_OSCILLATOR_STATUS for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_free_surface_oscillator_audit(
                tmp,
                dt_values=(0.08, 0.04),
                normalized_error_tolerance=0.08,
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(summary.iloc[0]["diagnostic_conclusion"], "free_surface_marching_converges_with_step_refinement")
            self.assertTrue((Path(tmp) / "a1_free_surface_oscillator.csv").exists())
            self.assertTrue((Path(tmp) / "a1_free_surface_oscillator_summary.csv").exists())

    def test_a1_free_surface_resampling_does_not_cross_hull_gap(self):
        state = FreeSurfaceMarchingState(
            y_m=np.array([-1.0, -0.5, 0.5, 1.0]),
            elevation_m=np.array([-10.0, -5.0, 5.0, 10.0], dtype=complex),
            potential_m2_s=np.array([-20.0, -10.0, 10.0, 20.0], dtype=complex),
            time_s=1.0,
            half_step_time_s=0.5,
            validity=ValidityReport.unvalidated("synthetic disjoint free-surface state"),
        )
        resampled = resample_free_surface_state(state, np.array([-0.75, -0.25, 0.25, 0.75]))
        self.assertTrue(np.allclose(resampled.elevation_m, [-7.5, -5.0, 5.0, 7.5]))
        self.assertTrue(np.allclose(resampled.potential_m2_s, [-15.0, -10.0, 10.0, 15.0]))

    def test_a1_waterline_clipped_free_surface_excludes_hull_gap(self):
        free = build_waterline_clipped_free_surface_geometry(-1.0, 1.0, 0.25, panel_count=8)
        self.assertEqual(free.panel_count, 8)
        self.assertTrue(np.all((free.mid_y_m <= -0.25) | (free.mid_y_m >= 0.25)))
        self.assertTrue(np.all(free.length_m > 0.0))
        self.assertAlmostEqual(float(np.min(free.mid_y_m)), -0.90625)
        self.assertAlmostEqual(float(np.max(free.mid_y_m)), 0.90625)

    def test_a1_two_zone_waterline_free_surface_refines_near_waterline(self):
        free = build_two_zone_waterline_free_surface_geometry(
            -1.0,
            1.0,
            waterline_half_beam_m=0.2,
            transition_half_beam_m=0.5,
            inner_panel_count_per_side=3,
            outer_panel_count_per_side=2,
        )
        self.assertEqual(free.panel_count, 10)
        self.assertTrue(np.all((free.mid_y_m <= -0.2) | (free.mid_y_m >= 0.2)))
        self.assertTrue(np.all(free.length_m > 0.0))
        right_lengths = free.length_m[free.panel_count // 2 :]
        self.assertLessEqual(float(np.max(right_lengths[:3])), float(np.min(right_lengths[3:])))
        self.assertAlmostEqual(float(np.min(free.mid_y_m)), -0.875)
        self.assertAlmostEqual(float(np.max(free.mid_y_m)), 0.875)

    def test_a1_outer_history_and_control_surface_block_are_finite(self):
        control = build_control_surface_geometry(radius_m=1.0, panel_count=8)
        history = build_transient_free_surface_history(
            control,
            dt_s=0.1,
            history_steps=3,
            quadrature_count=32,
            k_max=30.0,
        )
        past_phi = np.zeros((3, control.panel_count), dtype=complex)
        past_phi_n = np.ones((3, control.panel_count), dtype=complex) * (1.0 + 0.1j)
        rhs = history.convolution_rhs(past_phi, past_phi_n)
        rectangle_rhs = history.convolution_rhs(past_phi, past_phi_n, quadrature_rule="rectangle")
        no_potential_kernel_rhs = history.convolution_rhs(
            past_phi,
            past_phi_n,
            potential_kernel_scale=0.0,
        )
        scaled_rhs = history.convolution_rhs(past_phi, past_phi_n, rhs_scale=0.25)
        system = Matched2p5DSectionSolver().assemble_outer_control_surface_system(
            control,
            history,
            past_phi,
            past_phi_n,
        )
        no_image_system = Matched2p5DSectionSolver().assemble_outer_control_surface_system(
            control,
            history,
            past_phi,
            past_phi_n,
            control_image_scale=0.0,
        )
        solution = system.solve()
        self.assertEqual(history.green_potential.shape, (3, 8, 8))
        self.assertEqual(history.green_normal_derivative.shape, (3, 8, 8))
        self.assertEqual(system.matrix.shape, (8, 16))
        self.assertEqual(solution.shape, (16,))
        self.assertFalse(np.allclose(no_image_system.matrix, system.matrix))
        self.assertTrue(np.all(np.isfinite(rhs)))
        self.assertFalse(np.allclose(rectangle_rhs, rhs))
        self.assertFalse(np.allclose(no_potential_kernel_rhs, rhs))
        self.assertTrue(np.allclose(scaled_rhs, 0.25 * rhs))
        self.assertTrue(np.all(np.isfinite(solution)))
        self.assertGreater(np.linalg.norm(history.green_potential), 0.0)

    def test_a1_transient_history_kernel_normal_derivative_matches_finite_difference(self):
        control = build_control_surface_geometry(radius_m=1.0, panel_count=16)
        audit = audit_transient_history_kernel_normal_derivative(
            control,
            lag_s=0.05,
            finite_difference_epsilon_m=1.0e-4,
            quadrature_count=192,
            k_max=50.0,
        )
        self.assertEqual(
            audit.validity.status,
            "a1_eq28_history_kernel_normal_derivative_diagnostic_not_hard_gate",
        )
        self.assertLess(audit.relative_residual, 1.0e-5)
        self.assertGreater(audit.green_normal_derivative_norm, 0.0)

    def test_a1_transient_history_kernel_derivative_rows_and_writer_emit_csv(self):
        rows = a1_history_kernel_derivative_rows(
            panel_counts=(8, 16),
            lag_values_s=(0.02, 0.05),
            quadrature_count=192,
            k_max=50.0,
            relative_tolerance=1.0e-3,
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_HISTORY_KERNEL_DERIVATIVE_STATUS for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_history_kernel_derivative_audit(
                tmp,
                panel_counts=(8, 16),
                lag_values_s=(0.02, 0.05),
                quadrature_count=192,
                k_max=50.0,
                relative_tolerance=1.0e-3,
            )
            self.assertEqual(len(detail), 4)
            self.assertTrue(all(summary["diagnostic_conclusion"] == "eq28_normal_derivative_matches_finite_difference"))
            self.assertTrue((Path(tmp) / "a1_history_kernel_derivative.csv").exists())
            self.assertTrue((Path(tmp) / "a1_history_kernel_derivative_summary.csv").exists())

    def test_a1_history_rhs_convergence_audit_improves_with_refined_kernel(self):
        control = build_control_surface_geometry(radius_m=1.0, panel_count=8)
        coarse = audit_history_rhs_quadrature_convergence(
            control,
            quadrature_count=48,
            k_max=40.0,
            reference_quadrature_count=384,
            reference_k_max=100.0,
        )
        fine = audit_history_rhs_quadrature_convergence(
            control,
            quadrature_count=96,
            k_max=60.0,
            reference_quadrature_count=384,
            reference_k_max=100.0,
        )
        self.assertEqual(
            coarse.validity.status,
            "a1_eq24_history_rhs_quadrature_convergence_diagnostic_not_hard_gate",
        )
        self.assertLess(fine.max_channel_relative_residual, coarse.max_channel_relative_residual)
        self.assertLess(fine.max_channel_relative_residual, 0.001)

    def test_a1_history_rhs_convergence_rows_and_writer_emit_csv(self):
        rows = a1_history_rhs_convergence_rows(
            panel_count=8,
            quadrature_cases=((48, 40.0), (96, 60.0)),
            reference_quadrature_count=384,
            reference_k_max=100.0,
            relative_tolerance=0.002,
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_HISTORY_RHS_CONVERGENCE_STATUS for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_history_rhs_convergence_audit(
                tmp,
                panel_count=8,
                quadrature_cases=((48, 40.0), (96, 60.0)),
                reference_quadrature_count=384,
                reference_k_max=100.0,
                relative_tolerance=0.002,
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(
                summary.iloc[0]["diagnostic_conclusion"],
                "eq24_history_rhs_converges_to_refined_kernel_reference",
            )
            self.assertTrue((Path(tmp) / "a1_history_rhs_convergence.csv").exists())
            self.assertTrue((Path(tmp) / "a1_history_rhs_convergence_summary.csv").exists())

    def test_a1_station_control_history_inheritance_reconstructs_rhs(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        sweep = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        self.assertEqual(sweep.history_steps, 2)
        self.assertGreater(sweep.history_dt_s, 0.0)
        heave = audit_control_history_inheritance(sweep, mode_name="heave")
        pitch = audit_control_history_inheritance(sweep, mode_name="pitch")
        self.assertEqual(len(heave), len(sweep.x_m))
        self.assertEqual(len(pitch), len(sweep.x_m))
        self.assertEqual(
            heave[0].validity.status,
            "a1_eq24_station_control_history_inheritance_diagnostic_not_hard_gate",
        )
        self.assertEqual(heave[0].expected_previous_station_local_index, -1)
        self.assertEqual(heave[1].expected_previous_station_local_index, sweep.solve_order[0])
        self.assertLess(max(row.rhs_relative_residual for row in heave), 1.0e-12)
        self.assertLess(max(row.rhs_relative_residual for row in pitch), 1.0e-12)
        self.assertLess(max(row.lag0_potential_relative_residual for row in heave), 1.0e-12)
        self.assertLess(max(row.lag0_normal_derivative_relative_residual for row in pitch), 1.0e-12)

    def test_matched_head_sea_excitation_closes_a1_equation_chain(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        omega_e = 3.0
        speed = 1.2
        wavenumber, omega_0 = deep_water_head_sea_wave_from_encounter(omega_e, speed)
        self.assertAlmostEqual(omega_0 + speed * wavenumber, omega_e, places=12)
        result = Matched2p5DSectionSolver(config).solve_station_hull_head_sea_excitation_matched_sweep(
            hull,
            omega_e,
            speed,
            rho_water_kg_m3=1000.0,
            matched_sweep_options={
                "history_steps": 2,
                "history_quadrature_count": 16,
                "history_k_max": 15.0,
            },
        )
        self.assertAlmostEqual(result.wavenumber_rad_m, wavenumber, places=12)
        self.assertAlmostEqual(result.absolute_wave_omega_rad_s, omega_0, places=12)
        self.assertEqual(result.total_excitation.shape, (2,))
        self.assertGreater(float(np.linalg.norm(result.total_excitation)), 0.0)
        np.testing.assert_allclose(
            result.total_excitation,
            result.froude_krylov_force + result.diffraction_force,
            rtol=1.0e-12,
            atol=1.0e-12,
        )
        expected_boundary = np.asarray(
            [
                -wavenumber
                * result.incident_potential_by_station[index]
                * body.normal_z
                for index, body in enumerate(result.diffraction_sweep.bodies)
            ],
            dtype=complex,
        )
        np.testing.assert_allclose(
            result.diffraction_body_normal_velocity_by_station,
            expected_boundary,
            rtol=1.0e-12,
            atol=1.0e-12,
        )
        self.assertLess(result.body_condition_relative_residual, 1.0e-12)
        self.assertLess(result.equation30_incident_pressure_relative_residual, 1.0e-12)
        self.assertLess(result.force_density_integration_relative_residual, 1.0e-12)
        self.assertLess(result.maximum_linear_system_relative_residual, 1.0e-8)
        self.assertTrue(np.isfinite(result.maximum_condition_number))
        self.assertEqual(
            result.diffraction_sweep.pressure_force_sweep.assembly.force_assembly_route,
            "eq31_pressure_gradient_only",
        )
        self.assertIsNone(result.diffraction_sweep.end_term)
        self.assertIn("eq3_eq4_eq30", result.validity.status)

    def test_a1_station_control_history_inheritance_rows_and_writer_emit_csv(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        case = MatchedWigleySensitivityCase(
            name="history_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        rows = a1_control_history_inheritance_rows(
            reference,
            cases=(case,),
            coefficients=("A33",),
            modes=("heave",),
            row_limit_per_coefficient=1,
            relative_tolerance=1.0e-10,
        )
        self.assertGreaterEqual(len(rows), 2)
        self.assertLessEqual(len(rows), case.station_count)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_CONTROL_HISTORY_INHERITANCE_STATUS for row in rows))
        self.assertEqual(rows[0]["expected_previous_station_local_index"], -1)
        self.assertEqual(rows[1]["expected_previous_station_local_index"], rows[0]["station_local_index"])
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_control_history_inheritance_audit(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A33",),
                modes=("heave",),
                row_limit_per_coefficient=1,
                relative_tolerance=1.0e-10,
            )
            self.assertEqual(len(detail), len(rows))
            self.assertEqual(summary.iloc[0]["diagnostic_conclusion"], "station_control_history_rhs_reconstructs_from_solve_order")
            self.assertTrue((Path(tmp) / "a1_control_history_inheritance.csv").exists())
            self.assertTrue((Path(tmp) / "a1_control_history_inheritance_summary.csv").exists())

    def test_a1_outer_control_balance_splits_real_eq24_terms(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        sweep = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        audits = audit_outer_control_balance(sweep, mode_name="heave")
        self.assertEqual(len(audits), len(sweep.x_m))
        self.assertEqual(
            audits[0].validity.status,
            "a1_eq24_outer_control_balance_scale_phase_diagnostic_not_hard_gate",
        )
        self.assertLess(max(row.relative_residual for row in audits), 1.0e-5)
        self.assertTrue(any(row.history_rhs_norm > 0.0 for row in audits[1:]))
        nonzero = [row for row in audits if row.history_rhs_norm > 1.0e-14]
        self.assertTrue(all(np.isfinite(row.lhs_rhs_real_alignment) for row in nonzero))
        self.assertTrue(all(np.isfinite(row.lhs_rhs_phase_deg) for row in nonzero))

    def test_a1_outer_control_balance_rows_and_writer_emit_csv(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        case = MatchedWigleySensitivityCase(
            name="balance_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        rows = a1_outer_control_balance_rows(
            reference,
            cases=(case,),
            coefficients=("A33",),
            modes=("heave",),
            row_limit_per_coefficient=1,
            relative_tolerance=1.0e-5,
        )
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_OUTER_CONTROL_BALANCE_STATUS for row in rows))
        self.assertTrue(any(bool(row["history_rhs_nonzero"]) for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_outer_control_balance_audit(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A33",),
                modes=("heave",),
                row_limit_per_coefficient=1,
                relative_tolerance=1.0e-5,
            )
            self.assertEqual(len(detail), len(rows))
            self.assertEqual(
                summary.iloc[0]["diagnostic_conclusion"],
                "outer_control_lhs_reconstructs_history_rhs_scale_phase_recorded",
            )
            self.assertTrue((Path(tmp) / "a1_outer_control_balance.csv").exists())
            self.assertTrue((Path(tmp) / "a1_outer_control_balance_summary.csv").exists())

    def test_a1_rhs_source_decomposition_reconstructs_real_matched_solution(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        sweep = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        audits = audit_rhs_source_decomposition(sweep, mode_name="heave")
        self.assertEqual(len(audits), 3 * len(sweep.x_m))
        self.assertEqual(
            audits[0].validity.status,
            "a1_eq23_eq24_rhs_source_decomposition_diagnostic_not_hard_gate",
        )
        self.assertEqual(
            {row.source_name for row in audits},
            {"body_normal_velocity", "inner_free_surface_potential", "outer_control_history"},
        )
        self.assertLess(max(row.source_sum_relative_residual for row in audits), 1.0e-5)
        self.assertTrue(any(row.control_potential_norm > 0.0 for row in audits))
        self.assertTrue(any(row.control_normal_derivative_norm > 0.0 for row in audits))

    def test_a1_rhs_source_decomposition_rows_and_writer_emit_csv(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        case = MatchedWigleySensitivityCase(
            name="rhs_source_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        rows = a1_rhs_source_decomposition_rows(
            reference,
            cases=(case,),
            coefficients=("A33",),
            modes=("heave",),
            row_limit_per_coefficient=1,
            relative_tolerance=1.0e-5,
        )
        self.assertGreaterEqual(len(rows), 6)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_RHS_SOURCE_DECOMPOSITION_STATUS for row in rows))
        self.assertEqual(
            {row["source_name"] for row in rows},
            {"body_normal_velocity", "inner_free_surface_potential", "outer_control_history"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_rhs_source_decomposition_audit(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A33",),
                modes=("heave",),
                row_limit_per_coefficient=1,
                relative_tolerance=1.0e-5,
            )
            self.assertEqual(len(detail), len(rows))
            self.assertEqual(
                set(summary["source_name"]),
                {"body_normal_velocity", "inner_free_surface_potential", "outer_control_history"},
            )
            self.assertTrue((Path(tmp) / "a1_rhs_source_decomposition.csv").exists())
            self.assertTrue((Path(tmp) / "a1_rhs_source_decomposition_summary.csv").exists())

    def test_a1_inner_free_surface_state_reconstructs_marching_and_transfer(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        sweep = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        audits = audit_inner_free_surface_state_scale(sweep, mode_name="heave")
        self.assertEqual(len(audits), len(sweep.x_m))
        self.assertEqual(
            audits[0].validity.status,
            "a1_inner_free_surface_state_scale_marching_diagnostic_not_hard_gate",
        )
        self.assertEqual(audits[0].previous_station_local_index, -1)
        self.assertEqual(audits[1].previous_station_local_index, sweep.solve_order[0])
        self.assertTrue(all(row.update_kind == "advance_eq19_20" for row in audits))
        self.assertLess(max(row.update_relative_residual for row in audits), 1.0e-12)
        self.assertLess(max(row.transfer_relative_residual for row in audits), 1.0e-12)
        self.assertLess(max(row.time_before_abs_residual_s for row in audits), 1.0e-12)
        self.assertLess(max(row.time_after_abs_residual_s for row in audits), 1.0e-12)
        self.assertTrue(any(row.vertical_velocity_norm > 0.0 for row in audits))

    def test_a1_inner_free_surface_state_rows_and_writer_emit_csv(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        case = MatchedWigleySensitivityCase(
            name="inner_free_state_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=32,
            history_k_max=20.0,
        )
        rows = a1_inner_free_surface_state_rows(
            reference,
            cases=(case,),
            coefficients=("A33",),
            modes=("heave",),
            row_limit_per_coefficient=1,
            relative_tolerance=1.0e-10,
        )
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["gate_role"] == A1_INNER_FREE_SURFACE_STATE_STATUS for row in rows))
        self.assertTrue(all(row["free_surface_update_kind"] == "advance_eq19_20" for row in rows))
        self.assertLess(max(row["time_before_abs_residual_s"] for row in rows), 1.0e-12)
        self.assertLess(max(row["time_after_abs_residual_s"] for row in rows), 1.0e-12)
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_inner_free_surface_state_audit(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A33",),
                modes=("heave",),
                row_limit_per_coefficient=1,
                relative_tolerance=1.0e-10,
            )
            self.assertEqual(len(detail), len(rows))
            self.assertEqual(
                summary.iloc[0]["diagnostic_conclusion"],
                "inner_free_surface_state_updates_and_transfers_reconstruct_eq19_22",
            )
            self.assertTrue((Path(tmp) / "a1_inner_free_surface_state.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_free_surface_state_summary.csv").exists())

    def test_a1_outer_control_surface_green_identity_checks_image_and_diagonal_terms(self):
        control = build_control_surface_geometry(radius_m=1.0, panel_count=64)
        default = audit_outer_control_surface_green_identity(control)
        reverse_image = audit_outer_control_surface_green_identity(control, control_image_scale=-1.0)
        reverse_diagonal = audit_outer_control_surface_green_identity(control, control_diagonal_sign=-1.0)
        self.assertEqual(default.validity.status, "a1_eq24_outer_control_green_identity_diagnostic_not_hard_gate")
        self.assertLess(default.relative_residual, 0.004)
        self.assertGreater(reverse_image.relative_residual, 0.5)
        self.assertGreater(reverse_diagonal.relative_residual, 0.5)

    def test_a1_outer_control_surface_green_identity_rows_and_writer_emit_csv(self):
        rows = a1_control_surface_green_identity_rows(
            panel_counts=(16, 32),
            source_points=((0.2, 0.3),),
            relative_tolerance=0.02,
        )
        by_name = {str(row["a1_control_candidate_name"]): row for row in rows if int(row["panel_count"]) == 32}
        self.assertEqual(by_name["default_control_terms"]["diagnostic_status"], "PASS")
        self.assertEqual(by_name["reverse_image_terms"]["diagnostic_status"], "FAIL")
        self.assertEqual(by_name["reverse_diagonal"]["diagnostic_status"], "FAIL")
        self.assertEqual(by_name["default_control_terms"]["gate_role"], A1_CONTROL_SURFACE_GREEN_IDENTITY_STATUS)
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_control_surface_green_identity_audit(
                tmp,
                panel_counts=(16, 32),
                source_points=((0.2, 0.3),),
                relative_tolerance=0.02,
            )
            self.assertGreaterEqual(len(detail), 14)
            default_summary = summary[summary["a1_control_candidate_name"] == "default_control_terms"].iloc[0]
            reverse_summary = summary[summary["a1_control_candidate_name"] == "reverse_image_terms"].iloc[0]
            self.assertEqual(default_summary["diagnostic_conclusion"], "eq24_instantaneous_identity_within_tolerance")
            self.assertEqual(reverse_summary["diagnostic_conclusion"], "eq24_instantaneous_identity_outside_tolerance")
            self.assertTrue((Path(tmp) / "a1_control_surface_green_identity.csv").exists())
            self.assertTrue((Path(tmp) / "a1_control_surface_green_identity_summary.csv").exists())

    def test_a1_matched_eq23_eq24_square_system_solves(self):
        body_offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.1, point_count_per_side=4)
        body = build_inner_domain_panel_geometry(body_offsets, body_panel_count=8)
        free = build_flat_free_surface_geometry(-0.8, 0.8, panel_count=6)
        control = build_control_surface_geometry(radius_m=1.0, panel_count=6)
        history = build_transient_free_surface_history(
            control,
            dt_s=0.08,
            history_steps=2,
            quadrature_count=32,
            k_max=25.0,
        )
        data = MatchedSectionBoundaryData(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=heave_radiation_normal_velocity(body, omega_rad_s=3.0),
            free_surface_potential=np.zeros(free.panel_count, dtype=complex),
            history=history,
            past_control_potential=np.zeros((2, control.panel_count), dtype=complex),
            past_control_normal_derivative=np.zeros((2, control.panel_count), dtype=complex),
        )
        system = Matched2p5DSectionSolver().assemble_matched_section_system(data)
        solution = system.solve()
        audit = audit_matched_system_blocks(data, system, solution)
        expected_unknown_count = body.panel_count + free.panel_count + 2 * control.panel_count
        self.assertEqual(system.matrix.shape, (expected_unknown_count, expected_unknown_count))
        self.assertEqual(len(system.unknown_labels), expected_unknown_count)
        self.assertTrue(system.unknown_labels[0].startswith("psi_body_"))
        self.assertTrue(system.unknown_labels[-1].startswith("psi_n_control_"))
        self.assertTrue(np.all(np.isfinite(solution)))
        self.assertLess(system.relative_residual(solution), 1e-8)
        self.assertEqual(audit.row_block_names, ("eq23_body", "eq23_free_surface", "eq23_inner_control", "eq24_outer_control"))
        self.assertEqual(audit.unknown_block_names, ("psi_body", "psi_n_free_surface", "psi_control", "psi_n_control"))
        self.assertLess(audit.row_relative_residual("eq23_body"), 1e-8)
        self.assertLess(audit.row_residual_norms[audit.row_index("eq24_outer_control")], 1e-12)
        self.assertGreaterEqual(audit.unknown_solution_norm("psi_body"), 0.0)
        label, norm = audit.max_matrix_block()
        self.assertIn("<-", label)
        self.assertGreater(norm, 0.0)
        self.assertIn("block_audit", audit.validity.status)

    def test_a1_matched_control_row_can_use_separate_free_surface_potential(self):
        body_offsets = hard_chine_v_offsets(beam_m=0.3, draft_m=0.1, point_count_per_side=4)
        body = build_inner_domain_panel_geometry(body_offsets, body_panel_count=8)
        free = build_flat_free_surface_geometry(-0.8, 0.8, panel_count=6)
        control = build_control_surface_geometry(radius_m=1.0, panel_count=6)
        history = build_transient_free_surface_history(
            control,
            dt_s=0.08,
            history_steps=2,
            quadrature_count=32,
            k_max=25.0,
        )
        base_free_potential = np.linspace(0.1, 0.6, free.panel_count).astype(complex)
        control_free_potential = 2.0 * base_free_potential
        common = dict(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=heave_radiation_normal_velocity(body, omega_rad_s=3.0),
            free_surface_potential=base_free_potential,
            history=history,
            past_control_potential=np.zeros((2, control.panel_count), dtype=complex),
            past_control_normal_derivative=np.zeros((2, control.panel_count), dtype=complex),
        )
        shared = Matched2p5DSectionSolver().assemble_matched_section_system(MatchedSectionBoundaryData(**common))
        override = Matched2p5DSectionSolver().assemble_matched_section_system(
            MatchedSectionBoundaryData(
                **common,
                free_surface_potential_control_row=control_free_potential,
            )
        )
        rhs_delta = override.rhs - shared.rhs
        body_slice = slice(0, body.panel_count)
        free_slice = slice(body.panel_count, body.panel_count + free.panel_count)
        control_slice = slice(body.panel_count + free.panel_count, body.panel_count + free.panel_count + control.panel_count)
        outer_slice = slice(body.panel_count + free.panel_count + control.panel_count, None)
        self.assertLess(np.linalg.norm(rhs_delta[body_slice]), 1e-12)
        self.assertLess(np.linalg.norm(rhs_delta[free_slice]), 1e-12)
        self.assertGreater(np.linalg.norm(rhs_delta[control_slice]), 0.0)
        self.assertLess(np.linalg.norm(rhs_delta[outer_slice]), 1e-12)

    def test_a1_matched_solution_pressure_and_section_force_are_finite(self):
        body_offsets = hard_chine_v_offsets(beam_m=0.32, draft_m=0.11, point_count_per_side=4)
        body = build_inner_domain_panel_geometry(body_offsets, body_panel_count=8)
        free = build_flat_free_surface_geometry(-0.9, 0.9, panel_count=6)
        control = build_control_surface_geometry(radius_m=1.1, panel_count=6)
        history = build_transient_free_surface_history(
            control,
            dt_s=0.08,
            history_steps=2,
            quadrature_count=32,
            k_max=25.0,
        )
        data = MatchedSectionBoundaryData(
            body=body,
            inner_free_surface=free,
            control=control,
            body_normal_velocity=heave_radiation_normal_velocity(body, omega_rad_s=3.5),
            free_surface_potential=np.zeros(free.panel_count, dtype=complex),
            history=history,
            past_control_potential=np.zeros((2, control.panel_count), dtype=complex),
            past_control_normal_derivative=np.zeros((2, control.panel_count), dtype=complex),
        )
        solver = Matched2p5DSectionSolver()
        system = solver.assemble_matched_section_system(data)
        split = solver.split_solution(data, system.solve())
        pressure = solver.recover_body_pressure(
            body,
            split,
            omega_rad_s=3.5,
            rho_water_kg_m3=1000.0,
            forward_speed_mps=2.0,
            body_potential_x_gradient=np.zeros(body.panel_count, dtype=complex),
        )
        pressure_no_gradient = solver.recover_body_pressure(
            body,
            split,
            omega_rad_s=3.5,
            rho_water_kg_m3=1000.0,
            forward_speed_mps=2.0,
            body_potential_x_gradient=np.ones(body.panel_count, dtype=complex),
            pressure_gradient_scale=0.0,
        )
        pressure_with_gradient = solver.recover_body_pressure(
            body,
            split,
            omega_rad_s=3.5,
            rho_water_kg_m3=1000.0,
            forward_speed_mps=2.0,
            body_potential_x_gradient=np.ones(body.panel_count, dtype=complex),
            pressure_gradient_scale=1.0,
        )
        force = integrate_section_heave_pitch_force(pressure, lever_arm_m=0.4)
        added, damping = pressure_force_to_added_mass_damping(force.heave_force_per_m, 3.5)
        self.assertEqual(split.body_potential.shape, (body.panel_count,))
        self.assertEqual(pressure.pressure_pa.shape, (body.panel_count,))
        self.assertTrue(np.all(np.isfinite(pressure.pressure_pa)))
        self.assertTrue(
            np.allclose(
                pressure.pressure_pa,
                pressure.pressure_time_derivative_pa + pressure.pressure_forward_speed_pa,
            )
        )
        self.assertFalse(np.allclose(pressure_no_gradient.pressure_pa, pressure_with_gradient.pressure_pa))
        self.assertTrue(np.isfinite(force.heave_force_per_m))
        self.assertAlmostEqual(
            abs(force.heave_force_per_m - force.heave_force_time_derivative_per_m - force.heave_force_forward_speed_per_m),
            0.0,
        )
        self.assertAlmostEqual(force.pitch_moment_per_m, force.heave_force_per_m * 0.4)
        self.assertAlmostEqual(
            abs(
                force.pitch_moment_per_m
                - force.pitch_moment_time_derivative_per_m
                - force.pitch_moment_forward_speed_per_m
            ),
            0.0,
        )
        self.assertAlmostEqual(force.added_mass_per_m, added)
        self.assertAlmostEqual(force.damping_per_m, damping)

    def test_a1_station_potential_gradient_recovers_linear_field(self):
        x = np.array([0.0, 0.5, 1.0, 1.5])
        panel_offsets = np.array([0.0, 0.2, -0.1])
        slope = 2.0 - 0.5j
        phi = x[:, None] * slope + panel_offsets[None, :]
        gradient = Matched2p5DSectionSolver().estimate_body_potential_x_gradient(x, phi)
        self.assertEqual(gradient.body_potential_x_gradient.shape, phi.shape)
        self.assertTrue(np.allclose(gradient.body_potential_x_gradient, slope))
        self.assertEqual(gradient.scheme, "central")
        for scheme in ("forward", "backward"):
            one_sided = Matched2p5DSectionSolver().estimate_body_potential_x_gradient(x, phi, scheme=scheme)
            self.assertEqual(one_sided.scheme, scheme)
            self.assertTrue(np.allclose(one_sided.body_potential_x_gradient, slope))

        curved = (x[:, None] ** 2) * slope + panel_offsets[None, :]
        forward = Matched2p5DSectionSolver().estimate_body_potential_x_gradient(x, curved, scheme="forward")
        backward = Matched2p5DSectionSolver().estimate_body_potential_x_gradient(x, curved, scheme="backward")
        self.assertFalse(np.allclose(forward.body_potential_x_gradient, backward.body_potential_x_gradient))

    def test_a1_local_time_phase_gradient_uses_chain_rule(self):
        x = np.array([0.0, 0.5, 1.0, 1.5])
        panel_offsets = np.array([0.1 - 0.2j, -0.3 + 0.05j])
        psi_slope = 0.7 + 0.4j
        psi = x[:, None] * psi_slope + panel_offsets[None, :]
        omega = 1.6
        speed = 2.0
        phase = np.exp(1j * omega * (1.5 - x) / speed)
        result = estimate_local_time_phase_body_potential_x_gradient(
            x,
            psi,
            omega_rad_s=omega,
            speed_mps=speed,
            phase_factor=phase,
        )
        expected = np.conjugate(phase)[:, None] * (psi_slope + 1j * omega * psi / speed)
        self.assertEqual(result.body_potential_x_gradient.shape, psi.shape)
        self.assertEqual(result.scheme, "central_local_time_phase_chain_rule")
        self.assertTrue(np.allclose(result.body_potential_x_gradient, expected))

    def test_a1_whole_ship_heave_pitch_coefficients_assemble_from_sections(self):
        omega = 2.0
        x = np.array([0.0, 1.0, 2.0])

        def force(heave: complex, pitch: complex) -> MatchedSectionForceResult:
            added, damping = pressure_force_to_added_mass_damping(heave, omega)
            pitch_added, pitch_damping = pressure_force_to_added_mass_damping(pitch, omega)
            return MatchedSectionForceResult(
                heave_force_per_m=heave,
                pitch_moment_per_m=pitch,
                added_mass_per_m=added,
                damping_per_m=damping,
                pitch_added_mass_per_m2=pitch_added,
                pitch_damping_per_m2=pitch_damping,
                omega_rad_s=omega,
                lever_arm_m=0.0,
                validity=ValidityReport.unvalidated("synthetic section force for assembly test"),
                heave_force_time_derivative_per_m=heave,
                pitch_moment_time_derivative_per_m=pitch,
            )

        heave_mode = (
            force(4.0 - 2.0j, 1.0 - 0.5j),
            force(6.0 - 3.0j, 1.5 - 0.75j),
            force(8.0 - 4.0j, 2.0 - 1.0j),
        )
        pitch_mode = (
            force(2.0 - 1.0j, 3.0 - 1.5j),
            force(2.5 - 1.25j, 4.0 - 2.0j),
            force(3.0 - 1.5j, 5.0 - 2.5j),
        )
        end_terms = np.array([[1.0 - 0.2j, 0.5 - 0.1j], [0.25 - 0.05j, 0.75 - 0.15j]])
        assembly = Matched2p5DSectionSolver().assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
        )
        expected_force = np.array(
            [
                [np.trapezoid([4.0 - 2.0j, 6.0 - 3.0j, 8.0 - 4.0j], x), np.trapezoid([2.0 - 1.0j, 2.5 - 1.25j, 3.0 - 1.5j], x)],
                [np.trapezoid([1.0 - 0.5j, 1.5 - 0.75j, 2.0 - 1.0j], x), np.trapezoid([3.0 - 1.5j, 4.0 - 2.0j, 5.0 - 2.5j], x)],
            ],
            dtype=complex,
        ) + end_terms
        self.assertTrue(np.allclose(assembly.complex_force_matrix, expected_force))
        self.assertAlmostEqual(assembly.coefficient_dict()["A33"], np.real(expected_force[0, 0]) / omega**2)
        self.assertAlmostEqual(assembly.coefficient_dict()["B55"], -np.imag(expected_force[1, 1]) / omega)
        self.assertEqual(assembly.force_assembly_route, "eq32_stokes_body_plus_end")

    def test_a1_whole_ship_force_assembly_routes_are_explicit(self):
        omega = 2.0
        x = np.array([0.0, 1.0, 2.0])

        def force(
            time_heave: complex,
            forward_heave: complex,
            time_pitch: complex,
            forward_pitch: complex,
        ) -> MatchedSectionForceResult:
            heave = time_heave + forward_heave
            pitch = time_pitch + forward_pitch
            added, damping = pressure_force_to_added_mass_damping(heave, omega)
            pitch_added, pitch_damping = pressure_force_to_added_mass_damping(pitch, omega)
            return MatchedSectionForceResult(
                heave_force_per_m=heave,
                pitch_moment_per_m=pitch,
                added_mass_per_m=added,
                damping_per_m=damping,
                pitch_added_mass_per_m2=pitch_added,
                pitch_damping_per_m2=pitch_damping,
                omega_rad_s=omega,
                lever_arm_m=0.0,
                validity=ValidityReport.unvalidated("synthetic decomposed force for route test"),
                heave_force_time_derivative_per_m=time_heave,
                heave_force_forward_speed_per_m=forward_heave,
                pitch_moment_time_derivative_per_m=time_pitch,
                pitch_moment_forward_speed_per_m=forward_pitch,
            )

        heave_mode = (
            force(1.0 + 0.1j, 10.0 + 1.0j, 2.0 + 0.2j, 20.0 + 2.0j),
            force(2.0 + 0.2j, 11.0 + 1.1j, 3.0 + 0.3j, 21.0 + 2.1j),
            force(3.0 + 0.3j, 12.0 + 1.2j, 4.0 + 0.4j, 22.0 + 2.2j),
        )
        pitch_mode = (
            force(5.0 + 0.5j, 30.0 + 3.0j, 6.0 + 0.6j, 40.0 + 4.0j),
            force(6.0 + 0.6j, 31.0 + 3.1j, 7.0 + 0.7j, 41.0 + 4.1j),
            force(7.0 + 0.7j, 32.0 + 3.2j, 8.0 + 0.8j, 42.0 + 4.2j),
        )
        time_matrix = np.array(
            [
                [np.trapezoid([1.0 + 0.1j, 2.0 + 0.2j, 3.0 + 0.3j], x), np.trapezoid([5.0 + 0.5j, 6.0 + 0.6j, 7.0 + 0.7j], x)],
                [np.trapezoid([2.0 + 0.2j, 3.0 + 0.3j, 4.0 + 0.4j], x), np.trapezoid([6.0 + 0.6j, 7.0 + 0.7j, 8.0 + 0.8j], x)],
            ],
            dtype=complex,
        )
        pressure_gradient_matrix = np.array(
            [
                [np.trapezoid([10.0 + 1.0j, 11.0 + 1.1j, 12.0 + 1.2j], x), np.trapezoid([30.0 + 3.0j, 31.0 + 3.1j, 32.0 + 3.2j], x)],
                [np.trapezoid([20.0 + 2.0j, 21.0 + 2.1j, 22.0 + 2.2j], x), np.trapezoid([40.0 + 4.0j, 41.0 + 4.1j, 42.0 + 4.2j], x)],
            ],
            dtype=complex,
        )
        stokes_body = np.array([[100.0 + 10.0j, 200.0 + 20.0j], [300.0 + 30.0j, 400.0 + 40.0j]])
        row_measure_transport = np.array(
            [[9.0 + 0.9j, 8.0 + 0.8j], [7.0 + 0.7j, 6.0 + 0.6j]],
            dtype=complex,
        )
        end_terms = np.array([[1.0 - 0.2j, 2.0 - 0.3j], [3.0 - 0.4j, 4.0 - 0.5j]])
        solver = Matched2p5DSectionSolver()

        current = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
        )
        eq31 = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq31",
        )
        eq32 = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq32_stokes_body_plus_end",
        )
        eq32_body = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq32_stokes_body_only",
        )
        eq31_plus_row_measure = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq31_pressure_gradient_plus_row_measure_transport",
        )
        eq31_minus_row_measure = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq31_pressure_gradient_minus_row_measure_transport",
        )
        eq31_plus_row_measure_end = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq31_pressure_gradient_plus_row_measure_transport_plus_end",
        )
        eq31_minus_row_measure_end = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="eq31_pressure_gradient_minus_row_measure_transport_plus_end",
        )
        all_terms = solver.assemble_whole_ship_heave_pitch_coefficients(
            x,
            heave_mode,
            pitch_mode,
            omega_rad_s=omega,
            end_term_force_matrix=end_terms,
            stokes_body_forward_speed_force_matrix=stokes_body,
            row_measure_transport_force_matrix=row_measure_transport,
            force_assembly_route="all_terms",
        )

        self.assertTrue(np.allclose(current.complex_force_matrix, time_matrix + stokes_body + end_terms))
        self.assertTrue(np.allclose(eq31.complex_force_matrix, time_matrix + pressure_gradient_matrix))
        self.assertTrue(np.allclose(eq32.complex_force_matrix, time_matrix + stokes_body + end_terms))
        self.assertTrue(np.allclose(eq32_body.complex_force_matrix, time_matrix + stokes_body))
        self.assertTrue(
            np.allclose(eq31_plus_row_measure.complex_force_matrix, time_matrix + pressure_gradient_matrix + row_measure_transport)
        )
        self.assertTrue(
            np.allclose(eq31_minus_row_measure.complex_force_matrix, time_matrix + pressure_gradient_matrix - row_measure_transport)
        )
        self.assertTrue(
            np.allclose(
                eq31_plus_row_measure_end.complex_force_matrix,
                time_matrix + pressure_gradient_matrix + row_measure_transport + end_terms,
            )
        )
        self.assertTrue(
            np.allclose(
                eq31_minus_row_measure_end.complex_force_matrix,
                time_matrix + pressure_gradient_matrix - row_measure_transport + end_terms,
            )
        )
        self.assertTrue(
            np.allclose(all_terms.complex_force_matrix, time_matrix + pressure_gradient_matrix + stokes_body + end_terms)
        )
        self.assertEqual(eq31.force_assembly_route, "eq31_pressure_gradient_only")
        self.assertEqual(eq32.force_assembly_route, "eq32_stokes_body_plus_end")
        self.assertEqual(
            eq31_plus_row_measure.force_assembly_route,
            "eq31_pressure_gradient_plus_row_measure_transport",
        )
        self.assertEqual(
            eq31_minus_row_measure.force_assembly_route,
            "eq31_pressure_gradient_minus_row_measure_transport",
        )
        self.assertEqual(
            eq31_plus_row_measure_end.force_assembly_route,
            "eq31_pressure_gradient_plus_row_measure_transport_plus_end",
        )
        self.assertEqual(
            eq31_minus_row_measure_end.force_assembly_route,
            "eq31_pressure_gradient_minus_row_measure_transport_plus_end",
        )

    def test_a1_station_sweep_pipeline_recovers_pressures_and_coefficients(self):
        omega = 2.4
        speed = 1.25
        rho = 998.0
        x = np.array([0.0, 0.8, 1.6, 2.4])
        lever_arms = x - 1.2
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.34, draft_m=0.12), 6)
        bodies = tuple(body for _ in x)
        panel_offsets = np.linspace(-0.2, 0.15, body.panel_count)
        heave_slope = 0.35 - 0.08j
        pitch_slope = -0.12 + 0.05j
        heave_phi = x[:, None] * heave_slope + panel_offsets[None, :]
        pitch_phi = x[:, None] * pitch_slope + 0.25j * panel_offsets[None, :]

        def solution(phi: np.ndarray) -> MatchedSectionSolution:
            return MatchedSectionSolution(
                body_potential=np.asarray(phi, dtype=complex),
                inner_free_surface_normal_derivative=np.zeros(0, dtype=complex),
                control_potential=np.zeros(0, dtype=complex),
                control_normal_derivative=np.zeros(0, dtype=complex),
                validity=ValidityReport.unvalidated("synthetic matched station solution for pipeline test"),
            )

        heave_solutions = tuple(solution(row) for row in heave_phi)
        pitch_solutions = tuple(solution(row) for row in pitch_phi)
        end_terms = np.array([[0.2 - 0.03j, -0.1 + 0.04j], [0.05 - 0.02j, 0.12 - 0.01j]])
        sweep = Matched2p5DSectionSolver().assemble_heave_pitch_from_matched_station_solutions(
            x,
            bodies,
            heave_solutions,
            pitch_solutions,
            omega_rad_s=omega,
            rho_water_kg_m3=rho,
            forward_speed_mps=speed,
            lever_arms_m=lever_arms,
            end_term_force_matrix=end_terms,
        )

        self.assertTrue(np.allclose(sweep.heave_potential_gradient.body_potential_x_gradient, heave_slope))
        self.assertTrue(np.allclose(sweep.pitch_potential_gradient.body_potential_x_gradient, pitch_slope))
        expected_pressure = -rho * (1j * omega * heave_phi[2] - speed * heave_slope)
        self.assertTrue(np.allclose(sweep.heave_mode_pressures[2].pressure_pa, expected_pressure))

        def heave_force_density(phi: np.ndarray, slope: complex) -> np.ndarray:
            pressure = -rho * (1j * omega * phi - speed * slope)
            return np.sum(pressure * (-body.normal_z) * body.length_m, axis=1)

        heave_mode_forces = heave_force_density(heave_phi, heave_slope)
        pitch_mode_forces = heave_force_density(pitch_phi, pitch_slope)
        expected_pressure_force = np.array(
            [
                [np.trapezoid(heave_mode_forces, x), np.trapezoid(pitch_mode_forces, x)],
                [np.trapezoid(heave_mode_forces * lever_arms, x), np.trapezoid(pitch_mode_forces * lever_arms, x)],
            ],
            dtype=complex,
        )
        expected_stokes_density = np.zeros((len(x), 2, 2), dtype=complex)
        for index in range(len(x)):
            pitch_m5_measure = -body.normal_z * body.length_m
            expected_stokes_density[index, 1, 0] = rho * speed * np.sum(heave_phi[index] * pitch_m5_measure)
            expected_stokes_density[index, 1, 1] = rho * speed * np.sum(pitch_phi[index] * pitch_m5_measure)
        expected_stokes = np.trapezoid(expected_stokes_density, x, axis=0)
        expected_time_force = expected_pressure_force - sweep.assembly.forward_speed_force_matrix
        expected_force = expected_time_force + expected_stokes + end_terms
        self.assertTrue(np.allclose(sweep.stokes_body_forward_speed.force_density_by_station, expected_stokes_density))
        self.assertTrue(np.allclose(sweep.assembly.stokes_body_forward_speed_force_matrix, expected_stokes))
        self.assertTrue(np.allclose(sweep.assembly.complex_force_matrix, expected_force))
        self.assertAlmostEqual(sweep.coefficient_dict()["A55"], np.real(expected_force[1, 1]) / omega**2)
        self.assertEqual(sweep.assembly.force_assembly_route, "eq32_stokes_body_plus_end")
        self.assertIn("station_sweep", sweep.validity.status)

    def test_a1_stokes_end_term_helper_matches_contour_integral(self):
        rho = 1000.0
        speed = 3.0
        lever = 0.7
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.28, draft_m=0.1), 6)
        heave_phi = np.linspace(0.1, 0.4, body.panel_count) + 0.05j
        pitch_phi = -0.2j * np.linspace(0.0, 1.0, body.panel_count) + 0.12

        def solution(phi: np.ndarray) -> MatchedSectionSolution:
            return MatchedSectionSolution(
                body_potential=np.asarray(phi, dtype=complex),
                inner_free_surface_normal_derivative=np.zeros(0, dtype=complex),
                control_potential=np.zeros(0, dtype=complex),
                control_normal_derivative=np.zeros(0, dtype=complex),
                validity=ValidityReport.unvalidated("synthetic end-term potential"),
            )

        end_term = Matched2p5DSectionSolver().compute_heave_pitch_stokes_end_term_force_matrix(
            body,
            solution(heave_phi),
            solution(pitch_phi),
            rho_water_kg_m3=rho,
            forward_speed_mps=speed,
            lever_arm_m=lever,
        )
        generalized_heave = -body.normal_z * body.length_m
        generalized_pitch = generalized_heave * lever
        expected = -rho * speed * np.array(
            [
                [np.sum(heave_phi * generalized_heave), np.sum(pitch_phi * generalized_heave)],
                [np.sum(heave_phi * generalized_pitch), np.sum(pitch_phi * generalized_pitch)],
            ],
            dtype=complex,
        )
        self.assertTrue(np.allclose(end_term.complex_force_matrix, expected))
        self.assertEqual(end_term.row_labels, ("heave_force", "pitch_moment"))
        self.assertIn("eq32", end_term.validity.status)

    def test_a1_control_surface_end_term_helper_uses_control_potential(self):
        rho = 1000.0
        speed = 2.75
        lever = -0.25
        control = build_control_surface_geometry(radius_m=1.2, panel_count=8)
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.28, draft_m=0.1), 6)
        heave_control_phi = np.linspace(0.2, 0.5, control.panel_count) + 0.03j
        pitch_control_phi = -0.1 + 0.04j * np.linspace(0.0, 1.0, control.panel_count)

        def solution(control_phi: np.ndarray) -> MatchedSectionSolution:
            return MatchedSectionSolution(
                body_potential=np.full(body.panel_count, 99.0 + 12.0j, dtype=complex),
                inner_free_surface_normal_derivative=np.zeros(0, dtype=complex),
                control_potential=np.asarray(control_phi, dtype=complex),
                control_normal_derivative=np.zeros(control.panel_count, dtype=complex),
                validity=ValidityReport.unvalidated("synthetic control-surface end-term potential"),
            )

        end_term = compute_heave_pitch_control_surface_end_term_force_matrix(
            control,
            solution(heave_control_phi),
            solution(pitch_control_phi),
            rho_water_kg_m3=rho,
            forward_speed_mps=speed,
            lever_arm_m=lever,
        )
        generalized_heave = -control.normal_z * control.length_m
        generalized_pitch = generalized_heave * lever
        expected = -rho * speed * np.array(
            [
                [np.sum(heave_control_phi * generalized_heave), np.sum(pitch_control_phi * generalized_heave)],
                [np.sum(heave_control_phi * generalized_pitch), np.sum(pitch_control_phi * generalized_pitch)],
            ],
            dtype=complex,
        )
        self.assertTrue(np.allclose(end_term.complex_force_matrix, expected))
        self.assertEqual(end_term.row_labels, ("heave_force", "pitch_moment"))
        self.assertIn("control_surface_end_term", end_term.validity.status)

    def test_a1_stokes_body_forward_speed_helper_matches_section_integral(self):
        rho = 998.0
        speed = 2.5
        x = np.array([0.0, 0.5, 1.5])
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.28, draft_m=0.1), 6)
        bodies = tuple(body for _ in x)
        base = np.linspace(0.1, 0.4, body.panel_count) + 0.05j
        heave_phi = np.vstack([base, 1.5 * base, 2.0 * base])
        pitch_phi = np.vstack([0.2j * base, -0.3 * base, 0.7 * base])

        def solution(phi: np.ndarray) -> MatchedSectionSolution:
            return MatchedSectionSolution(
                body_potential=np.asarray(phi, dtype=complex),
                inner_free_surface_normal_derivative=np.zeros(0, dtype=complex),
                control_potential=np.zeros(0, dtype=complex),
                control_normal_derivative=np.zeros(0, dtype=complex),
                validity=ValidityReport.unvalidated("synthetic stokes body potential"),
            )

        heave_solutions = tuple(solution(row) for row in heave_phi)
        pitch_solutions = tuple(solution(row) for row in pitch_phi)
        stokes = compute_heave_pitch_stokes_body_forward_speed_force_matrix(
            x,
            bodies,
            heave_solutions,
            pitch_solutions,
            rho_water_kg_m3=rho,
            forward_speed_mps=speed,
        )
        pitch_m5_measure = -body.normal_z * body.length_m
        expected_density = np.zeros((len(x), 2, 2), dtype=complex)
        expected_density[:, 1, 0] = [rho * speed * np.sum(row * pitch_m5_measure) for row in heave_phi]
        expected_density[:, 1, 1] = [rho * speed * np.sum(row * pitch_m5_measure) for row in pitch_phi]
        self.assertTrue(np.allclose(stokes.force_density_by_station, expected_density))
        self.assertTrue(np.allclose(stokes.complex_force_matrix, np.trapezoid(expected_density, x, axis=0)))
        self.assertTrue(np.allclose(stokes.force_density_by_station[:, 0, :], 0.0))
        self.assertIn("eq32", stokes.validity.status)

    def test_a1_heave_pitch_coordinate_convention_centralizes_rows(self):
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.28, draft_m=0.1), 6)
        convention = DEFAULT_A1_HEAVE_PITCH_CONVENTION
        lever = 0.35
        omega = 2.3
        speed = 1.4

        heave_row = -body.normal_z
        self.assertTrue(np.allclose(convention.heave_n3(body), heave_row))
        self.assertTrue(np.allclose(convention.pitch_n5(body, lever), lever * heave_row))
        self.assertTrue(np.allclose(convention.pitch_m5(body), heave_row))
        self.assertTrue(np.allclose(convention.heave_body_normal_velocity(body, omega), 1j * omega * heave_row))

        pitch_oscillation, pitch_forward = convention.pitch_body_normal_velocity_components(
            body,
            omega,
            lever,
            forward_speed_mps=speed,
        )
        self.assertTrue(np.allclose(pitch_oscillation, 1j * omega * lever * heave_row))
        self.assertTrue(np.allclose(pitch_forward, speed * heave_row))

        pressure_heave, pressure_pitch = convention.pressure_generalized_rows(
            body.normal_z,
            body.length_m,
            lever_arm_m=lever,
        )
        end_heave, end_pitch = convention.end_contour_n_rows(body, lever_arm_m=lever)
        stokes_m3, stokes_m5 = convention.stokes_body_m_rows(body)
        self.assertTrue(np.allclose(pressure_heave, heave_row * body.length_m))
        self.assertTrue(np.allclose(pressure_pitch, lever * pressure_heave))
        self.assertTrue(np.allclose(end_heave, pressure_heave))
        self.assertTrue(np.allclose(end_pitch, pressure_pitch))
        self.assertTrue(np.allclose(stokes_m3, 0.0))
        self.assertTrue(np.allclose(stokes_m5, pressure_heave))
        rows = convention.paper_to_package_mapping_rows()
        symbols = {row.a1_symbol for row in rows}
        self.assertIn("N3", symbols)
        self.assertIn("N5", symbols)
        self.assertIn("m5", symbols)
        self.assertIn("Eq.32 end contour term", symbols)
        self.assertTrue(all(row.status == "PENDING_GATE1_BENCHMARK_VALIDATION" for row in rows))
        table = convention.paper_to_package_mapping_table()
        self.assertEqual(len(table), len(rows))
        self.assertEqual(table[0]["convention_name"], convention.name)
        self.assertEqual(table[0]["validity_status"], convention.validity.status)
        self.assertIn("convention_layer", convention.validity.status)

    def test_a1_convention_candidate_cases_are_controlled_diagnostics(self):
        base = MatchedWigleySensitivityCase(
            name="candidate_base",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = a1_convention_candidate_cases(base)
        names = {candidate.name for candidate in candidates}
        self.assertIn("default_mapping", names)
        self.assertIn("reverse_n5_and_pitch_row", names)
        self.assertIn("reverse_m5_forward_speed", names)
        self.assertTrue(all(candidate.status == A1_CONVENTION_CANDIDATE_STATUS for candidate in candidates))
        reverse_n5 = next(candidate for candidate in candidates if candidate.name == "reverse_n5_and_pitch_row")
        self.assertAlmostEqual(reverse_n5.case.pitch_radiation_lever_sign, -1.0)
        self.assertAlmostEqual(reverse_n5.case.pitch_moment_sign, -1.0)
        self.assertIn("N5", reverse_n5.changed_mapping_rows)
        mapping = a1_convention_candidate_mapping_rows(candidates[:2])
        self.assertGreater(len(mapping), len(DEFAULT_A1_HEAVE_PITCH_CONVENTION.paper_to_package_mapping_rows()))
        self.assertTrue(any(row["candidate_changes_this_row"] for row in mapping))
        self.assertTrue(all(row["a1_convention_candidate_status"] == A1_CONVENTION_CANDIDATE_STATUS for row in mapping))

    def test_a1_convention_candidate_benchmark_writes_annotated_rows(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        base = MatchedWigleySensitivityCase(
            name="candidate_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = a1_convention_candidate_cases(base)[:2]
        rows = matched_wigley_a1_convention_candidate_rows(
            reference,
            candidates=candidates,
            coefficients=("A55",),
            row_limit=1,
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["a1_convention_candidate_status"] == A1_CONVENTION_CANDIDATE_STATUS for row in rows))
        self.assertTrue(all(row["default_convention_name"] == DEFAULT_A1_HEAVE_PITCH_CONVENTION.name for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary, best = write_a1_convention_candidate_benchmark(
                reference,
                tmp,
                candidates=candidates,
                coefficients=("A55",),
                row_limit=1,
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 2)
            self.assertEqual(len(best), 1)
            self.assertTrue((Path(tmp) / "a1_convention_candidate_benchmark.csv").exists())
            self.assertTrue((Path(tmp) / "a1_convention_candidate_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_convention_candidate_best_cases.csv").exists())
            self.assertTrue((Path(tmp) / "a1_convention_candidate_mapping.csv").exists())
            self.assertTrue((Path(tmp) / "a1_convention_candidate_metadata.csv").exists())

    def test_a1_control_surface_candidate_benchmark_writes_annotated_rows(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        base = MatchedWigleySensitivityCase(
            name="control_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = a1_control_surface_candidate_cases(base)
        names = {candidate.name for candidate in candidates}
        self.assertIn("default_control_terms", names)
        self.assertIn("reverse_image_terms", names)
        self.assertIn("reverse_both_columns", names)
        self.assertTrue(all(candidate.status == A1_CONTROL_SURFACE_CANDIDATE_STATUS for candidate in candidates))
        reverse_image = next(candidate for candidate in candidates if candidate.name == "reverse_image_terms")
        self.assertAlmostEqual(reverse_image.case.control_image_scale, -1.0)
        self.assertIn("A-Abar image term", reverse_image.changed_eq24_terms)
        rows = matched_wigley_a1_control_surface_candidate_rows(
            reference,
            candidates=candidates[:2],
            coefficients=("A33",),
            row_limit=1,
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["a1_control_candidate_status"] == A1_CONTROL_SURFACE_CANDIDATE_STATUS for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary, best = write_a1_control_surface_candidate_benchmark(
                reference,
                tmp,
                candidates=candidates[:2],
                coefficients=("A33",),
                row_limit=1,
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 2)
            self.assertEqual(len(best), 1)
            self.assertTrue((Path(tmp) / "a1_control_surface_candidate_benchmark.csv").exists())
            self.assertTrue((Path(tmp) / "a1_control_surface_candidate_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_control_surface_candidate_best_cases.csv").exists())
            self.assertTrue((Path(tmp) / "a1_control_surface_candidate_metadata.csv").exists())

    def test_a1_inner_kernel_candidate_benchmark_writes_annotated_rows(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        base = MatchedWigleySensitivityCase(
            name="inner_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = a1_inner_kernel_candidate_cases(base)
        names = {candidate.name for candidate in candidates}
        self.assertIn("raw_eq25_default", names)
        self.assertIn("normalize_a_and_b_by_2pi", names)
        self.assertIn("positive_eq23_self_term", names)
        self.assertTrue(all(candidate.status == A1_INNER_KERNEL_CANDIDATE_STATUS for candidate in candidates))
        normalized = next(candidate for candidate in candidates if candidate.name == "normalize_a_and_b_by_2pi")
        self.assertAlmostEqual(normalized.case.inner_a_scale, 1.0 / (2.0 * np.pi))
        self.assertAlmostEqual(normalized.case.inner_b_scale, 1.0 / (2.0 * np.pi))
        positive_diagonal = next(candidate for candidate in candidates if candidate.name == "positive_eq23_self_term")
        self.assertAlmostEqual(positive_diagonal.case.inner_diagonal_sign, 1.0)
        rows = matched_wigley_a1_inner_kernel_candidate_rows(
            reference,
            candidates=candidates[:2],
            coefficients=("A33",),
            row_limit=1,
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["a1_inner_candidate_status"] == A1_INNER_KERNEL_CANDIDATE_STATUS for row in rows))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary, best = write_a1_inner_kernel_candidate_benchmark(
                reference,
                tmp,
                candidates=candidates[:2],
                coefficients=("A33",),
                row_limit=1,
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 2)
            self.assertEqual(len(best), 1)
            self.assertTrue((Path(tmp) / "a1_inner_kernel_candidate_benchmark.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_kernel_candidate_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_kernel_candidate_best_cases.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_kernel_candidate_metadata.csv").exists())

    def test_a1_inner_kernel_green_identity_audit_distinguishes_self_term(self):
        geometry = build_closed_ellipse_inner_boundary(
            semiaxis_y_m=1.0,
            semiaxis_z_m=0.45,
            panel_count=128,
        )
        raw = audit_inner_kernel_green_identity(geometry, potential_name="linear_y")
        wrong_self = audit_inner_kernel_green_identity(
            geometry,
            potential_name="linear_y",
            inner_diagonal_sign=1.0,
        )
        self.assertEqual(raw.validity.status, "a1_eq23_inner_kernel_green_identity_diagnostic_not_hard_gate")
        self.assertLess(raw.relative_residual, 0.02)
        self.assertGreater(wrong_self.relative_residual, 0.5)
        self.assertLess(raw.relative_residual, wrong_self.relative_residual)

    def test_a1_composite_boundary_uses_inner_fluid_body_normal(self):
        audits = []
        for body_panels, free_panels, control_panels in ((16, 12, 24), (30, 20, 40)):
            body = build_inner_domain_panel_geometry(
                wigley_section_offsets(0.3, 0.1875, point_count_per_side=body_panels // 2),
                body_panel_count=body_panels,
            )
            free = build_two_zone_waterline_free_surface_geometry(
                -0.9,
                0.9,
                0.15,
                0.15,
                inner_panel_count_per_side=free_panels // 4,
                outer_panel_count_per_side=free_panels // 4,
            )
            control = build_control_surface_geometry(0.9, control_panels)
            audits.append(audit_body_boundary_inner_fluid_normal(body, free, control))

        coarse, fine = audits
        self.assertEqual(
            fine.validity.status,
            "a1_eq23_body_boundary_inner_fluid_normal_identity_diagnostic_not_hard_gate",
        )
        self.assertLess(fine.corrected_to_stored_residual_ratio, 0.4)
        self.assertLess(
            fine.inner_fluid_body_normal_relative_residual,
            coarse.inner_fluid_body_normal_relative_residual,
        )
        self.assertGreater(fine.stored_body_normal_relative_residual, 0.2)

    def test_a1_closed_cylinder_added_mass_audit_exposes_pressure_sign(self):
        audit = audit_closed_cylinder_heave_added_mass(
            radius_m=1.0,
            panel_count=256,
            omega_rad_s=2.0,
            rho_water_kg_m3=1000.0,
        )
        self.assertEqual(audit.validity.status, LINEAR_2P5D_CLOSED_CYLINDER_ADDED_MASS_STATUS)
        self.assertLess(audit.source_system_relative_residual, 1e-10)
        self.assertAlmostEqual(audit.computed_added_mass_ratio, -1.0, delta=0.01)
        self.assertLess(audit.pressure_sign_corrected_relative_error, 0.01)
        self.assertAlmostEqual(audit.potential_alignment_scale_to_analytic, -1.0, delta=0.01)
        self.assertLess(audit.potential_alignment_relative_residual, 1e-10)

    def test_a1_closed_cylinder_added_mass_writer_records_pressure_chain_diagnostic(self):
        rows = a1_closed_cylinder_added_mass_rows(
            panel_counts=(64, 128),
            corrected_relative_tolerance=0.02,
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["a1_closed_cylinder_added_mass_status"] == A1_CLOSED_CYLINDER_ADDED_MASS_STATUS for row in rows))
        self.assertTrue(all(row["diagnostic_status"] == "PASS" for row in rows))
        self.assertTrue(all(row["raw_added_mass_sign"] == "negative" for row in rows))
        self.assertLess(float(rows[-1]["pressure_sign_corrected_relative_error"]), 0.02)
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_closed_cylinder_added_mass_audit(
                tmp,
                panel_counts=(64, 128),
                corrected_relative_tolerance=0.02,
            )
            self.assertTrue((Path(tmp) / "a1_closed_cylinder_added_mass.csv").exists())
            self.assertTrue((Path(tmp) / "a1_closed_cylinder_added_mass_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_closed_cylinder_added_mass_metadata.csv").exists())
            self.assertEqual(len(detail), 2)
            self.assertEqual(summary["diagnostic_conclusion"].iloc[0], "closed_cylinder_exposes_inner_pressure_sign_reversal")
            self.assertLess(float(summary["pressure_sign_corrected_relative_error_finest"].iloc[0]), 0.02)

    def test_a1_inner_kernel_green_identity_writer_records_candidates(self):
        base = MatchedWigleySensitivityCase(
            name="green_identity_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = tuple(
            candidate
            for candidate in a1_inner_kernel_candidate_cases(base)
            if candidate.name in {"raw_eq25_default", "positive_eq23_self_term"}
        )
        rows = a1_inner_kernel_green_identity_rows(
            candidates=candidates,
            panel_counts=(64,),
            potential_names=("linear_y",),
            relative_tolerance=0.08,
        )
        self.assertEqual(len(rows), 2)
        raw = next(row for row in rows if row["a1_inner_candidate_name"] == "raw_eq25_default")
        wrong = next(row for row in rows if row["a1_inner_candidate_name"] == "positive_eq23_self_term")
        self.assertEqual(raw["a1_inner_green_identity_status"], A1_INNER_KERNEL_GREEN_IDENTITY_STATUS)
        self.assertEqual(raw["diagnostic_status"], "PASS")
        self.assertEqual(wrong["diagnostic_status"], "FAIL")
        self.assertLess(float(raw["relative_residual"]), float(wrong["relative_residual"]))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_inner_kernel_green_identity_audit(
                tmp,
                candidates=candidates,
                panel_counts=(32, 64),
                potential_names=("linear_y",),
                relative_tolerance=0.08,
            )
            self.assertTrue((Path(tmp) / "a1_inner_kernel_green_identity.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_kernel_green_identity_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_kernel_green_identity_metadata.csv").exists())
            self.assertEqual(len(detail), 4)
            self.assertEqual(len(summary), 2)
            self.assertIn(A1_INNER_KERNEL_GREEN_IDENTITY_STATUS, set(summary["gate_role"]))

    def test_a1_inner_mixed_boundary_identity_audit_distinguishes_known_unknown_placement(self):
        panel_count = 96
        closed = build_closed_ellipse_inner_boundary(
            semiaxis_y_m=1.0,
            semiaxis_z_m=0.45,
            panel_count=panel_count,
        )
        body, free, control = split_inner_boundary_geometry_by_panel_counts(
            closed,
            closed_boundary_three_part_panel_counts(panel_count),
        )
        raw = audit_inner_mixed_boundary_green_identity(body, free, control, potential_name="linear_y")
        wrong_self = audit_inner_mixed_boundary_green_identity(
            body,
            free,
            control,
            potential_name="linear_y",
            inner_diagonal_sign=1.0,
        )
        self.assertEqual(raw.validity.status, "a1_eq23_inner_kernel_green_identity_diagnostic_not_hard_gate")
        self.assertLess(raw.total_relative_residual, 0.05)
        self.assertGreater(wrong_self.total_relative_residual, 0.5)
        self.assertLess(raw.total_relative_residual, wrong_self.total_relative_residual)
        self.assertLess(raw.body_relative_residual, 0.2)
        self.assertLess(raw.free_relative_residual, 0.2)
        self.assertLess(raw.control_relative_residual, 0.2)

    def test_a1_inner_mixed_boundary_identity_writer_records_candidates(self):
        base = MatchedWigleySensitivityCase(
            name="mixed_identity_tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        candidates = tuple(
            candidate
            for candidate in a1_inner_kernel_candidate_cases(base)
            if candidate.name in {"raw_eq25_default", "normalize_b_only_by_2pi"}
        )
        rows = a1_inner_mixed_boundary_identity_rows(
            candidates=candidates,
            panel_counts=(66,),
            potential_names=("linear_y",),
            relative_tolerance=0.08,
        )
        self.assertEqual(len(rows), 2)
        raw = next(row for row in rows if row["a1_inner_candidate_name"] == "raw_eq25_default")
        b_only = next(row for row in rows if row["a1_inner_candidate_name"] == "normalize_b_only_by_2pi")
        self.assertEqual(raw["a1_inner_mixed_boundary_status"], A1_INNER_MIXED_BOUNDARY_STATUS)
        self.assertEqual(raw["diagnostic_status"], "PASS")
        self.assertEqual(b_only["diagnostic_status"], "FAIL")
        self.assertLess(float(raw["total_relative_residual"]), float(b_only["total_relative_residual"]))
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_a1_inner_mixed_boundary_identity_audit(
                tmp,
                candidates=candidates,
                panel_counts=(33, 66),
                potential_names=("linear_y",),
                relative_tolerance=0.08,
            )
            self.assertTrue((Path(tmp) / "a1_inner_mixed_boundary_identity.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_mixed_boundary_identity_summary.csv").exists())
            self.assertTrue((Path(tmp) / "a1_inner_mixed_boundary_identity_metadata.csv").exists())
            self.assertEqual(len(detail), 4)
            self.assertEqual(len(summary), 2)
            self.assertIn(A1_INNER_MIXED_BOUNDARY_STATUS, set(summary["gate_role"]))

    def test_a1_heave_pitch_convention_audit_flags_sign_mismatch(self):
        body = build_inner_domain_panel_geometry(hard_chine_v_offsets(beam_m=0.28, draft_m=0.1), 6)
        audit = audit_heave_pitch_a1_convention(
            body,
            2.5,
            radiation_lever_arm_m=0.4,
            moment_lever_arm_m=0.4,
            forward_speed_mps=1.2,
        )
        self.assertLess(audit.heave_n3_to_force_row_relative_residual, 1e-12)
        self.assertLess(audit.pitch_n5_to_moment_row_relative_residual, 1e-12)
        self.assertLess(audit.pitch_m5_forward_to_stokes_relative_residual, 1e-12)
        self.assertGreater(audit.pitch_m5_to_n5_norm_ratio, 1.0)
        self.assertIn("convention_audit", audit.validity.status)

        lever_mismatch = audit_heave_pitch_a1_convention(
            body,
            2.5,
            radiation_lever_arm_m=-0.4,
            moment_lever_arm_m=0.4,
            forward_speed_mps=1.2,
        )
        self.assertGreater(lever_mismatch.pitch_n5_to_moment_row_relative_residual, 1.0)
        m5_mismatch = audit_heave_pitch_a1_convention(
            body,
            2.5,
            radiation_lever_arm_m=0.4,
            moment_lever_arm_m=0.4,
            forward_speed_mps=1.2,
            pitch_forward_speed_sign=-1.0,
        )
        self.assertGreater(m5_mismatch.pitch_m5_forward_to_stokes_relative_residual, 1.0)

    def test_a1_station_hull_matched_sweep_runs_wigley_pipeline(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        sweep = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        self.assertGreaterEqual(len(sweep.x_m), 2)
        self.assertEqual(sweep.pressure_force_sweep.assembly.complex_force_matrix.shape, (2, 2))
        self.assertTrue(np.all(np.isfinite(sweep.heave_condition_numbers)))
        self.assertTrue(np.all(np.isfinite(sweep.pitch_condition_numbers)))
        self.assertLess(float(np.max(sweep.heave_residuals)), 1e-7)
        self.assertLess(float(np.max(sweep.pitch_residuals)), 1e-7)
        self.assertEqual(len(sweep.heave_block_audits), len(sweep.x_m))
        self.assertEqual(len(sweep.pitch_block_audits), len(sweep.x_m))
        self.assertIn("block_audit", sweep.heave_block_audits[0].validity.status)
        self.assertGreaterEqual(sweep.heave_block_audits[0].unknown_solution_norm("psi_body"), 0.0)
        self.assertTrue(all(np.isfinite(value) for value in sweep.coefficient_dict().values()))
        self.assertIsNotNone(sweep.end_term)
        self.assertIsNotNone(sweep.control_surface_end_term)
        self.assertEqual(sweep.control_surface_end_term.complex_force_matrix.shape, (2, 2))
        self.assertIn("control_surface_end_term", sweep.control_surface_end_term.validity.status)
        self.assertTrue(np.allclose(sweep.end_term.complex_force_matrix, 0.0))
        self.assertTrue(np.allclose(sweep.control_surface_end_term.complex_force_matrix, 0.0))
        self.assertEqual(sweep.end_hull_station_index, 0)
        self.assertEqual(sweep.end_active_station_local_index, -1)
        self.assertAlmostEqual(sweep.end_station_x_m, 0.0)
        self.assertTrue(sweep.end_station_is_degenerate)
        self.assertEqual(sweep.end_term_geometry_source, "actual_degenerate_hull_endpoint")
        self.assertEqual(sweep.solve_order, tuple(range(len(sweep.x_m) - 1, -1, -1)))
        self.assertEqual(sweep.pitch_body_condition_oscillation_by_station.shape[0], len(sweep.x_m))
        self.assertEqual(sweep.pitch_body_condition_forward_speed_by_station.shape[0], len(sweep.x_m))
        self.assertGreater(np.linalg.norm(sweep.pitch_body_condition_oscillation_by_station), 0.0)
        self.assertGreater(np.linalg.norm(sweep.pitch_body_condition_forward_speed_by_station), 0.0)
        self.assertTrue(sweep.use_free_surface_marching)
        self.assertAlmostEqual(sweep.end_term_scale, 1.0)
        self.assertEqual(sweep.end_station, "aft")
        self.assertAlmostEqual(sweep.pitch_radiation_sign, 1.0)
        self.assertAlmostEqual(sweep.pitch_radiation_lever_sign, 1.0)
        self.assertAlmostEqual(sweep.pitch_forward_speed_sign, 1.0)
        self.assertAlmostEqual(sweep.pitch_oscillation_scale, 1.0)
        self.assertAlmostEqual(sweep.pitch_forward_speed_scale, 1.0)
        self.assertAlmostEqual(sweep.pitch_moment_sign, 1.0)
        self.assertAlmostEqual(sweep.time_step_scale, 1.0)
        self.assertAlmostEqual(sweep.free_surface_velocity_scale, 1.0)
        self.assertEqual(sweep.free_surface_normal_derivative_source, "raw")
        self.assertAlmostEqual(sweep.free_surface_time_direction_sign, 1.0)
        self.assertAlmostEqual(sweep.free_surface_dynamic_gravity_sign, -1.0)
        self.assertEqual(sweep.free_surface_potential_elevation_level, "updated")
        self.assertAlmostEqual(sweep.history_rhs_scale, 1.0)
        self.assertEqual(sweep.history_convolution_rule, "trapezoid")
        self.assertAlmostEqual(sweep.history_potential_kernel_scale, 1.0)
        self.assertAlmostEqual(sweep.history_normal_derivative_kernel_scale, 1.0)
        self.assertAlmostEqual(sweep.control_image_scale, 1.0)
        self.assertAlmostEqual(sweep.control_potential_kernel_scale, 1.0)
        self.assertAlmostEqual(sweep.control_normal_derivative_kernel_scale, 1.0)
        self.assertAlmostEqual(sweep.control_diagonal_sign, 1.0)
        self.assertAlmostEqual(sweep.inner_a_scale, 1.0)
        self.assertAlmostEqual(sweep.inner_b_scale, 1.0)
        self.assertAlmostEqual(sweep.inner_diagonal_sign, -1.0)
        self.assertAlmostEqual(sweep.inner_free_surface_known_potential_rhs_scale, 1.0)
        self.assertAlmostEqual(sweep.inner_free_surface_unknown_normal_column_scale, 1.0)
        self.assertEqual(sweep.pressure_gradient_scheme, "central")
        self.assertAlmostEqual(sweep.pressure_gradient_scale, 1.0)
        self.assertTrue(sweep.apply_local_time_phase)
        self.assertTrue(sweep.local_time_phase_gradient_correction)
        self.assertTrue(sweep.clip_inner_free_surface_to_waterline)
        self.assertFalse(sweep.two_zone_inner_free_surface)
        self.assertGreater(float(np.max(np.abs(sweep.heave_free_surface_potential_by_station))), 0.0)
        self.assertGreater(float(np.max(np.abs(sweep.pitch_free_surface_potential_by_station))), 0.0)
        self.assertEqual(sweep.heave_free_surface_potential_after_station.shape, sweep.heave_free_surface_potential_by_station.shape)
        self.assertEqual(sweep.heave_outer_history_rhs_by_station.shape[0], len(sweep.x_m))
        self.assertEqual(len(sweep.heave_free_surface_update_kind_by_station), len(sweep.x_m))
        first_index = sweep.solve_order[0]
        second_index = sweep.solve_order[1]
        dt = float(np.median(np.diff(sweep.x_m)) / 1.2)
        expected_first_advanced_potential = (
            -9.80665
            * sweep.heave_mode_solutions[first_index].inner_free_surface_normal_derivative
            * dt**2
        )
        first_advanced_state = FreeSurfaceMarchingState(
            y_m=sweep.inner_free_surface_geometries[first_index].mid_y_m,
            elevation_m=sweep.heave_free_surface_elevation_after_station[first_index],
            potential_m2_s=expected_first_advanced_potential,
            time_s=sweep.heave_free_surface_time_after_by_station[first_index],
            half_step_time_s=sweep.heave_free_surface_time_after_by_station[first_index] - 0.5 * dt,
            validity=ValidityReport.unvalidated("expected first-station free-surface state"),
        )
        expected_second_station_state = resample_free_surface_state(
            first_advanced_state,
            sweep.inner_free_surface_geometries[second_index].mid_y_m,
        )
        self.assertTrue(
            np.allclose(
                sweep.heave_free_surface_potential_by_station[second_index],
                expected_second_station_state.potential_m2_s,
            )
        )
        self.assertTrue(
            np.allclose(
                sweep.heave_free_surface_potential_after_station[first_index],
                expected_first_advanced_potential,
            )
        )
        self.assertEqual(sweep.heave_free_surface_update_kind_by_station[first_index], "advance_eq19_20")
        self.assertEqual(sweep.heave_free_surface_update_kind_by_station[second_index], "advance_eq19_20")
        self.assertAlmostEqual(
            sweep.heave_free_surface_time_before_by_station[first_index],
            sweep.local_time_s_by_station[first_index],
        )
        self.assertAlmostEqual(
            sweep.heave_free_surface_time_after_by_station[first_index],
            sweep.local_time_s_by_station[first_index] + dt,
        )
        self.assertTrue(np.all(np.isfinite(sweep.heave_outer_history_rhs_by_station)))
        body = RigidBody6DOF.from_radii(78.0, 0.2, 0.75, 0.8)
        hydro = Matched2p5DSectionSolver(config).assemble_frequency_domain_from_matched_station_hull(
            hull,
            body,
            np.array([3.0]),
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
        )
        self.assertEqual(hydro.added_mass.shape, (1, 6, 6))
        self.assertTrue(np.all(np.isfinite(hydro.added_mass[:, 2:5:2, 2:5:2])))
        self.assertGreater(hydro.restoring[0, 2, 2], 0.0)
        self.assertTrue(np.allclose(hydro.excitation, 0.0))
        self.assertFalse(hydro.validity.is_validated)
        self.assertAlmostEqual(hydro.metadata["end_term_scale"], 1.0)
        self.assertEqual(hydro.metadata["end_station"], "aft")
        self.assertAlmostEqual(hydro.metadata["pitch_radiation_sign"], 1.0)
        self.assertAlmostEqual(hydro.metadata["pitch_oscillation_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["pitch_forward_speed_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["pitch_moment_sign"], 1.0)
        self.assertAlmostEqual(hydro.metadata["time_step_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["free_surface_velocity_scale"], 1.0)
        self.assertEqual(hydro.metadata["free_surface_normal_derivative_source"], "raw")
        self.assertAlmostEqual(hydro.metadata["free_surface_time_direction_sign"], 1.0)
        self.assertAlmostEqual(hydro.metadata["free_surface_dynamic_gravity_sign"], -1.0)
        self.assertEqual(hydro.metadata["free_surface_potential_elevation_level"], "updated")
        self.assertAlmostEqual(hydro.metadata["history_rhs_scale"], 1.0)
        self.assertEqual(hydro.metadata["history_convolution_rule"], "trapezoid")
        self.assertAlmostEqual(hydro.metadata["history_potential_kernel_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["history_normal_derivative_kernel_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["control_image_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["control_potential_kernel_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["control_normal_derivative_kernel_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["control_diagonal_sign"], 1.0)
        self.assertAlmostEqual(hydro.metadata["inner_a_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["inner_b_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["inner_diagonal_sign"], -1.0)
        self.assertAlmostEqual(hydro.metadata["inner_free_surface_known_potential_rhs_scale"], 1.0)
        self.assertAlmostEqual(hydro.metadata["inner_free_surface_unknown_normal_column_scale"], 1.0)
        self.assertEqual(hydro.metadata["pressure_gradient_scheme"], "central")
        self.assertAlmostEqual(hydro.metadata["pressure_gradient_scale"], 1.0)
        self.assertTrue(hydro.metadata["apply_local_time_phase"])
        self.assertTrue(hydro.metadata["local_time_phase_gradient_correction"])
        self.assertEqual(hydro.metadata["a1_coordinate_convention_name"], DEFAULT_A1_HEAVE_PITCH_CONVENTION.name)
        self.assertEqual(
            hydro.metadata["a1_coordinate_convention_status"],
            DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status,
        )
        self.assertTrue(hydro.metadata["clip_inner_free_surface_to_waterline"])
        self.assertFalse(hydro.metadata["two_zone_inner_free_surface"])
        self.assertEqual(hydro.metadata["provider_route"], "matched_bie_station_sweep")
        self.assertEqual(hydro.metadata["provider_formulation"], "matched_bie")
        self.assertEqual(hydro.metadata["matrix_contract"], "heave_pitch_2x2_v1")
        self.assertEqual(hydro.metadata["matrix_row_dofs"], ("heave", "pitch"))
        self.assertEqual(hydro.metadata["matrix_source_dof_indices"], (2, 4))
        self.assertEqual(hydro.metadata["force_harmonic_convention"], "F=omega^2*A-i*omega*B")
        self.assertEqual(hydro.metadata["input_omega_role"], "radiation_encounter_frequency_a1_eq4")
        self.assertEqual(hydro.metadata["encounter_omega_definition"], "same_as_input_omega_for_radiation_problem")
        self.assertFalse(hydro.metadata["wave_encounter_transformation_applied"])
        self.assertTrue(np.allclose(hydro.encounter_omega, hydro.omega))
        self.assertFalse(hydro.metadata["empirical_output_scaling_used"])
        block = hydro.longitudinal_heave_pitch_matrices()
        self.assertEqual(block.added_mass.shape, (1, 2, 2))
        self.assertEqual(block.radiation_damping.shape, (1, 2, 2))
        self.assertAlmostEqual(
            block.reconstruction_relative_residual(
                hydro.contribution_breakdown["heave_pitch_complex_force_matrices"]
            ),
            0.0,
            places=12,
        )
        self.assertIn(
            "heave_pitch_control_surface_end_term_force_matrices_diagnostic",
            hydro.contribution_breakdown,
        )
        self.assertEqual(
            hydro.contribution_breakdown[
                "heave_pitch_control_surface_end_term_force_matrices_diagnostic"
            ].shape,
            (1, 2, 2),
        )
        for key in [
            "heave_inner_free_surface_normal_derivative_norms",
            "pitch_inner_free_surface_normal_derivative_norms",
            "heave_free_surface_potential_increment_norms",
            "pitch_free_surface_potential_increment_norms",
            "heave_free_surface_potential_increment_to_normal_derivative_gains",
            "pitch_free_surface_potential_increment_to_normal_derivative_gains",
            "heave_free_surface_potential_increment_normal_derivative_phase_degs",
            "pitch_free_surface_potential_increment_normal_derivative_phase_degs",
            "heave_body_pressure_to_body_potential_gains",
            "pitch_body_pressure_to_body_potential_gains",
            "heave_body_pressure_forward_to_time_norm_ratios",
            "pitch_body_pressure_forward_to_time_norm_ratios",
            "station_x_m",
            "station_x_over_l",
            "station_waterplane_beams",
            "station_effective_drafts",
            "station_submerged_areas",
            "station_waterplane_beam_adjacent_relative_jumps",
            "station_effective_draft_adjacent_relative_jumps",
            "station_submerged_area_adjacent_relative_jumps",
            "station_waterplane_beam_gradient_to_beam_gains",
            "station_effective_draft_gradient_to_draft_gains",
            "station_submerged_area_gradient_to_area_gains",
            "station_waterplane_beam_gradient_peak_x_over_l",
            "station_submerged_area_gradient_peak_x_over_l",
            "heave_body_potential_norm_to_beam_squared_ratios",
            "pitch_body_potential_norm_to_beam_squared_ratios",
            "heave_body_potential_norm_to_submerged_area_ratios",
            "pitch_body_potential_norm_to_submerged_area_ratios",
            "heave_body_potential_norm_to_beam_squared_peak_x_over_l",
            "pitch_body_potential_norm_to_beam_squared_peak_x_over_l",
            "heave_body_potential_norm_to_submerged_area_peak_x_over_l",
            "pitch_body_potential_norm_to_submerged_area_peak_x_over_l",
            "aft_active_station_x_over_l",
            "aft_active_station_waterplane_beams",
            "aft_active_station_effective_drafts",
            "aft_active_station_submerged_areas",
            "aft_active_station_body_panel_length_sums",
            "aft_active_station_body_panel_length_maxes",
            "aft_active_station_body_panel_normal_z_norms",
            "aft_active_station_heave_generalized_row_norms",
            "aft_active_station_pitch_generalized_row_norms",
            "heave_pressure_time_formula_ratios",
            "pitch_pressure_time_formula_ratios",
            "heave_pressure_forward_formula_ratios",
            "pitch_pressure_forward_formula_ratios",
            "heave_body_potential_x_gradient_norms",
            "pitch_body_potential_x_gradient_norms",
            "heave_body_potential_x_gradient_to_potential_gains",
            "pitch_body_potential_x_gradient_to_potential_gains",
            "heave_body_potential_x_gradient_characteristic_lengths",
            "pitch_body_potential_x_gradient_characteristic_lengths",
            "heave_body_potential_x_gradient_gain_times_hull_length",
            "pitch_body_potential_x_gradient_gain_times_hull_length",
            "heave_central_body_potential_x_gradient_to_potential_gains",
            "pitch_central_body_potential_x_gradient_to_potential_gains",
            "heave_forward_body_potential_x_gradient_to_potential_gains",
            "pitch_forward_body_potential_x_gradient_to_potential_gains",
            "heave_backward_body_potential_x_gradient_to_potential_gains",
            "pitch_backward_body_potential_x_gradient_to_potential_gains",
            "heave_central_body_potential_x_gradient_gain_times_hull_length",
            "pitch_central_body_potential_x_gradient_gain_times_hull_length",
            "heave_forward_body_potential_x_gradient_gain_times_hull_length",
            "pitch_forward_body_potential_x_gradient_gain_times_hull_length",
            "heave_backward_body_potential_x_gradient_gain_times_hull_length",
            "pitch_backward_body_potential_x_gradient_gain_times_hull_length",
            "heave_phase_aligned_body_potential_x_gradient_to_potential_gains",
            "pitch_phase_aligned_body_potential_x_gradient_to_potential_gains",
            "heave_phase_aligned_body_potential_x_gradient_characteristic_lengths",
            "pitch_phase_aligned_body_potential_x_gradient_characteristic_lengths",
            "heave_phase_aligned_body_potential_x_gradient_gain_times_hull_length",
            "pitch_phase_aligned_body_potential_x_gradient_gain_times_hull_length",
            "heave_phase_aligned_gradient_gain_to_raw_gain_ratios",
            "pitch_phase_aligned_gradient_gain_to_raw_gain_ratios",
            "heave_phase_aligned_central_body_potential_x_gradient_to_potential_gains",
            "pitch_phase_aligned_central_body_potential_x_gradient_to_potential_gains",
            "heave_phase_aligned_forward_body_potential_x_gradient_to_potential_gains",
            "pitch_phase_aligned_forward_body_potential_x_gradient_to_potential_gains",
            "heave_phase_aligned_backward_body_potential_x_gradient_to_potential_gains",
            "pitch_phase_aligned_backward_body_potential_x_gradient_to_potential_gains",
            "heave_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length",
            "pitch_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length",
            "heave_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length",
            "pitch_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length",
            "heave_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length",
            "pitch_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length",
            "heave_adjacent_body_potential_relative_jumps",
            "pitch_adjacent_body_potential_relative_jumps",
            "heave_adjacent_body_potential_symmetric_norm_ratios",
            "pitch_adjacent_body_potential_symmetric_norm_ratios",
            "heave_adjacent_body_potential_real_alignments",
            "pitch_adjacent_body_potential_real_alignments",
            "heave_adjacent_body_potential_phase_degs",
            "pitch_adjacent_body_potential_phase_degs",
            "heave_phase_aligned_adjacent_body_potential_relative_jumps",
            "pitch_phase_aligned_adjacent_body_potential_relative_jumps",
            "heave_phase_aligned_adjacent_body_potential_real_alignments",
            "pitch_phase_aligned_adjacent_body_potential_real_alignments",
            "heave_phase_aligned_adjacent_body_potential_phase_degs",
            "pitch_phase_aligned_adjacent_body_potential_phase_degs",
            "body_panel_mid_y_adjacent_relative_jumps",
            "body_panel_mid_z_adjacent_relative_jumps",
            "body_panel_normal_adjacent_relative_jumps",
            "body_panel_length_adjacent_relative_jumps",
            "heave_mode_heave_force_to_pressure_norm_gains",
            "heave_mode_pitch_moment_to_pressure_norm_gains",
            "pitch_mode_heave_force_to_pressure_norm_gains",
            "pitch_mode_pitch_moment_to_pressure_norm_gains",
            "heave_pitch_total_force_density_peak_x_over_l",
            "heave_pitch_time_derivative_force_density_peak_x_over_l",
            "heave_pitch_forward_speed_force_density_peak_x_over_l",
            "heave_pitch_total_force_density_peak_abs",
            "heave_pitch_time_derivative_force_density_peak_abs",
            "heave_pitch_forward_speed_force_density_peak_abs",
            "heave_pitch_total_force_density_peak_to_integral_abs_ratios",
            "heave_pitch_time_derivative_force_density_peak_to_integral_abs_ratios",
            "heave_pitch_forward_speed_force_density_peak_to_integral_abs_ratios",
            "heave_pitch_total_force_density_abs_centroid_x_over_l",
            "heave_pitch_time_derivative_force_density_abs_centroid_x_over_l",
            "heave_pitch_forward_speed_force_density_abs_centroid_x_over_l",
            "heave_pitch_total_force_density_aft_abs",
            "heave_pitch_time_derivative_force_density_aft_abs",
            "heave_pitch_forward_speed_force_density_aft_abs",
        ]:
            self.assertIn(key, hydro.contribution_breakdown)
            values = np.asarray(hydro.contribution_breakdown[key], dtype=float)
            self.assertEqual(values.shape[0], 1)
            self.assertTrue(np.any(np.isfinite(values)))
        for key in [
            "heave_pitch_pressure_force_matrices_excluding_aft_active_station",
            "heave_pitch_pressure_force_matrices_excluding_bow_active_station",
            "heave_pitch_pressure_force_matrices_excluding_end_active_stations",
            "heave_pitch_time_derivative_force_matrices_excluding_aft_active_station",
            "heave_pitch_forward_speed_force_matrices_excluding_aft_active_station",
        ]:
            self.assertIn(key, hydro.contribution_breakdown)
            values = np.asarray(hydro.contribution_breakdown[key], dtype=complex)
            self.assertEqual(values.shape, (1, 2, 2))
            self.assertTrue(np.all(np.isfinite(values)))
        stokes_density = np.asarray(
            hydro.contribution_breakdown["heave_pitch_stokes_body_forward_speed_force_density_by_station"],
            dtype=complex,
        )
        self.assertEqual(stokes_density.shape[0], 1)
        self.assertEqual(stokes_density.shape[2:], (2, 2))
        self.assertTrue(np.all(np.isfinite(stokes_density)))
        self.assertAlmostEqual(
            float(np.nanmedian(hydro.contribution_breakdown["heave_pressure_time_formula_ratios"])),
            1.0,
        )
        self.assertAlmostEqual(
            float(np.nanmedian(hydro.contribution_breakdown["pitch_pressure_time_formula_ratios"])),
            1.0,
        )
        phased = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
            apply_local_time_phase=True,
            local_time_phase_gradient_correction=True,
        )
        self.assertTrue(phased.apply_local_time_phase)
        self.assertTrue(phased.local_time_phase_gradient_correction)
        self.assertEqual(
            phased.pressure_force_sweep.heave_potential_gradient.scheme,
            "central_local_time_phase_chain_rule",
        )
        self.assertTrue(np.all(np.isfinite(phased.pressure_force_sweep.assembly.complex_force_matrix)))
        clipped = Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
            clip_inner_free_surface_to_waterline=True,
        )
        self.assertTrue(clipped.clip_inner_free_surface_to_waterline)
        self.assertEqual(clipped.inner_free_surface_y_by_station.shape, sweep.heave_free_surface_potential_by_station.shape)
        self.assertTrue(
            any(
                not np.allclose(clipped.inner_free_surface_y_by_station[0], row)
                for row in clipped.inner_free_surface_y_by_station[1:]
            )
        )
        two_zone_config = Linear2p5DProviderConfig(
            hull_stations=5,
            body_panels_per_section=8,
            free_surface_inner_panels=8,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        two_zone = Matched2p5DSectionSolver(two_zone_config).solve_station_hull_heave_pitch_matched_sweep(
            hull,
            omega_rad_s=3.0,
            speed_mps=1.2,
            rho_water_kg_m3=1000.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
            clip_inner_free_surface_to_waterline=True,
            two_zone_inner_free_surface=True,
        )
        self.assertTrue(two_zone.two_zone_inner_free_surface)
        self.assertEqual(two_zone.inner_free_surface_y_by_station.shape[1], 8)
        self.assertTrue(np.all(two_zone.inner_free_surface_panel_length_by_station > 0.0))

    def test_a1_end_term_rejects_substitution_for_excluded_non_degenerate_endpoint(self):
        stations = tuple(
            HardChineStation(
                x_m=float(x_m),
                beam_m=float(beam_m),
                draft_m=0.1,
                deadrise_deg=45.0,
                waterplane_beam_override_m=float(beam_m),
                submerged_area_override_m2=float(area_m2),
            )
            for x_m, beam_m, area_m2 in (
                (0.0, 0.05, 0.005),
                (1.0, 0.30, 0.020),
                (2.0, 0.30, 0.020),
                (3.0, 0.30, 0.020),
            )
        )
        hull = StationHull(length_m=3.0, stations=stations, lcg_from_transom_m=1.5)
        config = Linear2p5DProviderConfig(
            hull_stations=4,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
        )
        with self.assertRaisesRegex(ValueError, "non-degenerate"):
            Matched2p5DSectionSolver(config).solve_station_hull_heave_pitch_matched_sweep(
                hull,
                omega_rad_s=3.0,
                speed_mps=1.2,
                rho_water_kg_m3=1000.0,
                history_steps=2,
                history_quadrature_count=16,
                history_k_max=15.0,
                active_min_beam_m=0.1,
            )

    def test_matched_wigley_sensitivity_writes_diagnostic_rows(self):
        reference = ROOT / "benchmarks" / "ma2005" / "wigley_iii_coefficients_digitized.csv"
        case = MatchedWigleySensitivityCase(
            name="tiny",
            station_count=5,
            body_panels_per_section=8,
            free_surface_inner_panels=4,
            free_surface_outer_panels=4,
            control_surface_radius_beams=2.0,
            history_steps=2,
            history_quadrature_count=16,
            history_k_max=15.0,
            end_station="bow",
            end_term_scale=-1.0,
            pitch_radiation_sign=-1.0,
            pitch_radiation_lever_sign=-1.0,
            pitch_forward_speed_sign=-1.0,
            pitch_moment_sign=-1.0,
            time_step_scale=0.5,
            free_surface_velocity_scale=0.25,
            history_rhs_scale=0.75,
            history_convolution_rule="rectangle",
            history_potential_kernel_scale=0.5,
            history_normal_derivative_kernel_scale=-0.5,
            control_image_scale=0.0,
            control_potential_kernel_scale=-1.0,
            control_normal_derivative_kernel_scale=0.5,
            control_diagonal_sign=-1.0,
            inner_a_scale=0.5,
            inner_b_scale=0.25,
            inner_diagonal_sign=1.0,
            pressure_gradient_scheme="forward",
            pressure_gradient_scale=0.5,
            clip_inner_free_surface_to_waterline=True,
            two_zone_inner_free_surface=True,
        )
        rows = matched_wigley_sensitivity_rows(reference, cases=(case,), coefficients=("A33",), row_limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gate_role"], MATCHED_WIGLEY_SENSITIVITY_STATUS)
        self.assertEqual(rows[0]["case_name"], "tiny")
        self.assertAlmostEqual(float(rows[0]["end_term_scale"]), -1.0)
        self.assertEqual(rows[0]["end_station"], "bow")
        self.assertAlmostEqual(float(rows[0]["pitch_radiation_sign"]), -1.0)
        self.assertAlmostEqual(float(rows[0]["pitch_moment_sign"]), -1.0)
        self.assertAlmostEqual(float(rows[0]["time_step_scale"]), 0.5)
        self.assertAlmostEqual(float(rows[0]["free_surface_velocity_scale"]), 0.25)
        self.assertAlmostEqual(float(rows[0]["history_rhs_scale"]), 0.75)
        self.assertEqual(rows[0]["history_convolution_rule"], "rectangle")
        self.assertAlmostEqual(float(rows[0]["history_potential_kernel_scale"]), 0.5)
        self.assertAlmostEqual(float(rows[0]["history_normal_derivative_kernel_scale"]), -0.5)
        self.assertAlmostEqual(float(rows[0]["control_image_scale"]), 0.0)
        self.assertAlmostEqual(float(rows[0]["control_potential_kernel_scale"]), -1.0)
        self.assertAlmostEqual(float(rows[0]["control_normal_derivative_kernel_scale"]), 0.5)
        self.assertAlmostEqual(float(rows[0]["control_diagonal_sign"]), -1.0)
        self.assertAlmostEqual(float(rows[0]["inner_a_scale"]), 0.5)
        self.assertAlmostEqual(float(rows[0]["inner_b_scale"]), 0.25)
        self.assertAlmostEqual(float(rows[0]["inner_diagonal_sign"]), 1.0)
        self.assertEqual(rows[0]["pressure_gradient_scheme"], "forward")
        self.assertAlmostEqual(float(rows[0]["pressure_gradient_scale"]), 0.5)
        self.assertTrue(bool(rows[0]["clip_inner_free_surface_to_waterline"]))
        self.assertTrue(bool(rows[0]["two_zone_inner_free_surface"]))
        self.assertEqual(rows[0]["a1_grid_recommendation_status"], "A1_GRID_COARSE_DIAGNOSTIC")
        self.assertTrue(np.isfinite(float(rows[0]["computed_value"])))
        self.assertIn("rho*displacement_volume", rows[0]["ma2005_normalization_formula"])
        self.assertTrue(np.isfinite(float(rows[0]["required_normalization_scale"])))
        self.assertTrue(np.isfinite(float(rows[0]["required_normalization_scale_over_current"])))
        self.assertEqual(rows[0]["normalization_audit_status"], "INFO_NOT_GATE")
        self.assertAlmostEqual(
            float(rows[0]["computed_value"]),
            float(rows[0]["computed_body_integral_value"]) + float(rows[0]["computed_end_term_value"]),
        )
        self.assertAlmostEqual(
            float(rows[0]["computed_body_integral_value"]),
            float(rows[0]["computed_time_derivative_value"]) + float(rows[0]["computed_forward_speed_value"]),
        )
        self.assertTrue(np.isfinite(float(rows[0]["computed_stokes_body_forward_speed_value"])))
        self.assertAlmostEqual(
            float(rows[0]["computed_stokes_total_with_end_term_value"]),
            float(rows[0]["computed_time_derivative_value"])
            + float(rows[0]["computed_stokes_forward_speed_with_end_term_value"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = write_matched_wigley_sensitivity(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A33",),
                row_limit=1,
            )
            self.assertTrue((Path(tmp) / "matched_wigley_sensitivity.csv").exists())
            self.assertTrue((Path(tmp) / "matched_wigley_sensitivity_summary.csv").exists())
            self.assertTrue((Path(tmp) / "matched_wigley_sensitivity_best_cases.csv").exists())
            self.assertEqual(len(detail), 1)
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary.iloc[0]["gate_role"], MATCHED_WIGLEY_SENSITIVITY_STATUS)
            best = matched_wigley_best_case_summary(summary)
            self.assertEqual(len(best), 1)
            self.assertEqual(best.iloc[0]["best_case_name"], "tiny")
            self.assertEqual(best.iloc[0]["a1_grid_recommendation_status"], "A1_GRID_COARSE_DIAGNOSTIC")
        with tempfile.TemporaryDirectory() as tmp:
            station = write_matched_wigley_station_diagnostics(
                reference,
                tmp,
                cases=(case,),
                coefficients=("A53",),
                row_limit=1,
            )
            self.assertTrue((Path(tmp) / "matched_wigley_station_diagnostics.csv").exists())
            self.assertGreaterEqual(len(station), 2)
            self.assertLessEqual(len(station), case.station_count)
            self.assertEqual(station.iloc[0]["selected_mode"], "heave")
            self.assertEqual(station.iloc[0]["selected_generalized_row"], "pitch_moment")
            self.assertTrue(np.isfinite(float(station.iloc[-1]["cumulative_body_integral_value"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["free_surface_potential_norm_before_solve"])))
            self.assertIn(station.iloc[0]["free_surface_update_kind"], {"initialize_eq21_22", "advance_eq19_20"})
            self.assertTrue(np.isfinite(float(station.iloc[-1]["free_surface_potential_norm_after_update"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["outer_history_rhs_norm_before_solve"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["control_potential_norm"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["body_condition_norm"])))
            self.assertEqual(station.iloc[-1]["a1_coordinate_convention_name"], DEFAULT_A1_HEAVE_PITCH_CONVENTION.name)
            self.assertEqual(
                station.iloc[-1]["a1_coordinate_convention_status"],
                DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity.status,
            )
            self.assertIn("convention_audit", station.iloc[-1]["a1_convention_audit_status"])
            self.assertTrue(
                np.isfinite(float(station.iloc[-1]["a1_pitch_n5_to_moment_row_relative_residual"]))
            )
            self.assertTrue(
                np.isfinite(float(station.iloc[-1]["a1_pitch_m5_forward_to_stokes_relative_residual"]))
            )
            self.assertTrue(np.isfinite(float(station.iloc[-1]["a1_pitch_m5_to_n5_norm_ratio"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["pitch_body_condition_oscillation_norm"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["pitch_body_condition_forward_speed_norm"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["pressure_time_derivative_norm"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["pressure_forward_speed_norm"])))
            self.assertIn("block_audit", station.iloc[-1]["a1_matched_block_audit_status"])
            self.assertTrue(np.isfinite(float(station.iloc[-1]["a1_eq23_body_relative_residual"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["a1_eq24_outer_control_relative_residual"])))
            self.assertTrue(np.isfinite(float(station.iloc[-1]["a1_unknown_psi_body_norm"])))
            self.assertIn("<-", station.iloc[-1]["a1_max_matrix_block_label"])
            self.assertIn("<-", station.iloc[-1]["a1_max_contribution_block_label"])
            self.assertEqual(station.iloc[-1]["a1_unit_closure_status"], A1_POTENTIAL_UNIT_CLOSURE_STATUS)
            self.assertTrue(np.isfinite(float(station.iloc[-1]["a1_unit_body_characteristic_span_m"])))
            self.assertTrue(
                np.isfinite(
                    float(station.iloc[-1]["a1_unit_body_potential_per_normal_velocity_length_m"])
                )
            )
            self.assertTrue(
                np.isfinite(
                    float(station.iloc[-1]["a1_unit_body_potential_per_normal_velocity_over_span"])
                )
            )
            self.assertTrue(
                np.isfinite(
                    float(station.iloc[-1]["a1_unit_inner_fs_normal_derivative_to_body_condition_norm_ratio"])
                )
            )
            self.assertTrue(
                np.isfinite(
                    float(station.iloc[-1]["a1_unit_control_normal_derivative_to_body_condition_norm_ratio"])
                )
            )
            self.assertAlmostEqual(
                float(station.iloc[-1]["a1_unit_pressure_time_over_rho_omega_phi_norm_ratio"]),
                1.0,
            )
            self.assertTrue(
                np.isfinite(float(station.iloc[-1]["a1_unit_pressure_forward_to_time_norm_ratio"]))
            )
            self.assertTrue(
                np.isfinite(
                    float(station.iloc[-1]["cumulative_stokes_body_forward_speed_value"])
                )
            )
            self.assertAlmostEqual(
                float(station.iloc[-1]["cumulative_stokes_with_end_term_value"]),
                float(station.iloc[-1]["cumulative_time_derivative_value"])
                + float(station.iloc[-1]["cumulative_stokes_body_forward_speed_value"])
                + float(station.iloc[-1]["end_term_value"]),
            )
            self.assertAlmostEqual(
                float(station.iloc[-1]["cumulative_body_integral_value"]),
                float(station.iloc[-1]["cumulative_time_derivative_value"])
                + float(station.iloc[-1]["cumulative_forward_speed_value"]),
            )
            self.assertAlmostEqual(float(station.iloc[0]["pressure_gradient_scale"]), 0.5)
            self.assertEqual(station.iloc[0]["history_convolution_rule"], "rectangle")
            self.assertAlmostEqual(float(station.iloc[0]["history_potential_kernel_scale"]), 0.5)
            self.assertAlmostEqual(float(station.iloc[0]["history_normal_derivative_kernel_scale"]), -0.5)
            self.assertAlmostEqual(float(station.iloc[0]["control_image_scale"]), 0.0)
            self.assertAlmostEqual(float(station.iloc[0]["control_potential_kernel_scale"]), -1.0)
            self.assertAlmostEqual(float(station.iloc[0]["control_normal_derivative_kernel_scale"]), 0.5)
            self.assertAlmostEqual(float(station.iloc[0]["control_diagonal_sign"]), -1.0)
            self.assertAlmostEqual(float(station.iloc[0]["inner_a_scale"]), 0.5)
            self.assertAlmostEqual(float(station.iloc[0]["inner_b_scale"]), 0.25)
            self.assertAlmostEqual(float(station.iloc[0]["inner_diagonal_sign"]), 1.0)
            self.assertEqual(station.iloc[0]["pressure_gradient_scheme"], "forward")
            self.assertTrue(bool(station.iloc[0]["clip_inner_free_surface_to_waterline"]))
            self.assertTrue(bool(station.iloc[0]["two_zone_inner_free_surface"]))
            self.assertLess(float(station.iloc[0]["inner_free_surface_y_min_m"]), 0.0)
            self.assertGreater(float(station.iloc[0]["inner_free_surface_y_max_m"]), 0.0)
            self.assertEqual(station.iloc[0]["a1_grid_recommendation_status"], "A1_GRID_COARSE_DIAGNOSTIC")

    def test_a1_grid_recommendation_flags_coarse_and_recommended_cases(self):
        coarse = a1_grid_recommendation(MatchedWigleySensitivityCase(name="coarse"), fn_l=0.4)
        recommended = a1_grid_recommendation(
            MatchedWigleySensitivityCase(
                name="recommended",
                station_count=41,
                free_surface_inner_panels=12,
                free_surface_outer_panels=10,
                control_surface_radius_beams=3.0,
            ),
            fn_l=0.3,
        )
        self.assertEqual(coarse["a1_grid_recommendation_status"], "A1_GRID_COARSE_DIAGNOSTIC")
        self.assertEqual(recommended["a1_grid_recommendation_status"], "A1_GRID_RECOMMENDED")
        self.assertTrue(recommended["a1_control_radius_ok"])
        self.assertTrue(recommended["a1_station_count_ok"])
        low_fn = a1_grid_recommendation(
            MatchedWigleySensitivityCase(
                name="low_fn",
                station_count=A1_LOW_FN_STATION_MIN - 1,
                free_surface_inner_panels=12,
                free_surface_outer_panels=10,
                control_surface_radius_beams=3.0,
            ),
            fn_l=0.2,
        )
        self.assertEqual(low_fn["a1_min_station_count_for_fn"], A1_LOW_FN_STATION_MIN)
        self.assertFalse(low_fn["a1_station_count_ok"])

    def test_matched_wigley_sensitivity_summarizes_error_rows(self):
        case = MatchedWigleySensitivityCase(name="error_case")
        with tempfile.TemporaryDirectory() as tmp:
            reference = Path(tmp) / "bad_reference.csv"
            reference.write_text(
                "\n".join(
                    [
                        "coefficient,reference_value,omega_e_sqrt_l_over_g,speed_case,normalization,length_m,beam_m,draft_m,displacement_volume_m3",
                        "A33,1.0,1.0,unknown_speed,ma2005,3.0,0.3,0.1875,0.075",
                        "A55,0.1,1.0,unknown_speed,ma2005,3.0,0.3,0.1875,0.075",
                    ]
                ),
                encoding="utf-8",
            )
            limited_rows = matched_wigley_sensitivity_rows(
                reference,
                cases=(case,),
                coefficients=("A33", "A55"),
                row_limit_per_coefficient=1,
            )
            self.assertEqual(len(limited_rows), 2)
            detail, summary = write_matched_wigley_sensitivity(
                reference,
                Path(tmp) / "out",
                cases=(case,),
                coefficients=("A33",),
            )
            self.assertEqual(len(detail), 1)
            self.assertEqual(detail.iloc[0]["diagnostic_status"], "ERROR")
            self.assertEqual(len(summary), 1)
            self.assertEqual(int(summary.iloc[0]["error_rows"]), 1)
            self.assertTrue((Path(tmp) / "out" / "matched_wigley_sensitivity_best_cases.csv").exists())

    def test_linear_2p5d_contract_routes_station_hull(self):
        hull = make_wigley_iii_hull(length_m=3.0, beam_m=0.3, draft_m=0.1875, station_count=5)
        body = RigidBody6DOF.from_radii(100.0, 0.2, 0.75, 0.8)
        hydro = assemble_frequency_domain_from_station_hull(hull, body, np.array([1.5, 2.0]), speed_mps=3.0)
        self.assertEqual(hydro.added_mass.shape, (2, 6, 6))
        self.assertFalse(hydro.validity.is_validated)
        self.assertGreater(hydro.encounter_omega[0], hydro.omega[0])
        k, encounter = deep_water_encounter(2.0, 3.0, 180.0, 9.80665)
        self.assertGreater(k, 0.0)
        self.assertGreater(encounter, 2.0)
        self.assertAlmostEqual(local_time_from_station(1.5, 3.0), 0.5)
        system = Matched2p5DSectionSolver().assemble_placeholder_system(3)
        self.assertEqual(system.solve().shape, (3,))

    def test_nonlinear_2dt_provider_is_named_and_guarded(self):
        self.assertIsInstance(ReducedOrderPlaning2DtProvider(), ReducedOrderPlaningLoadProvider)
        provider = NonlinearBEM2DtProvider()
        self.assertTrue(provider.capabilities.nonlinear_free_surface)
        with self.assertRaises(NotImplementedError):
            provider.simulate()

    def test_section_plane_manager_advances_and_inherits(self):
        manager = SectionPlaneManager.initialize(bow_x_m=0.0, length_m=2.0, section_count=5)
        advanced = manager.advance(bow_x_m=0.75, dt_s=0.1)
        self.assertTrue(all(plane.age_s >= 0.1 or plane.inherited_from_x_m is not None for plane in advanced.planes))
        self.assertLessEqual(max(plane.x_ground_m for plane in advanced.planes), 0.75)

    def test_multihull_load_assembly_uses_moment_arms(self):
        load = ComponentLoad(
            name="port",
            force_n=np.array([0.0, 0.0, 10.0]),
            moment_nm=np.zeros(3),
            origin_from_vessel_ap_m=(0.0, -0.5, 0.0),
        )
        tau = assemble_component_loads((load,), cog_from_ap_m=(0.0, 0.0, 0.0))
        self.assertAlmostEqual(tau[2], 10.0)
        self.assertAlmostEqual(tau[3], -5.0)

    def test_hydrofoil_linear_model_and_routh_hurwitz(self):
        self.assertGreater(finite_wing_lift_slope(5.0), 0.0)
        force, moment = hydrofoil_force(
            HydrofoilGeometry(
                area_m2=0.12,
                aspect_ratio=5.0,
                reference_point_body_m=(2.0, 0.0, -0.2),
                flap_lift_effectiveness=0.4,
            ),
            HydrofoilState(speed_mps=8.0, alpha_rad=0.04, flap_rad=0.02),
        )
        self.assertGreater(force[2], 0.0)
        self.assertEqual(moment.shape, (3,))
        self.assertTrue(routh_hurwitz_quartic((1.0, 4.0, 6.0, 4.0, 1.0))["stable"])
        self.assertFalse(routh_hurwitz_quartic((1.0, -1.0, 1.0, 1.0, 1.0))["stable"])


if __name__ == "__main__":
    unittest.main()
