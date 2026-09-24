import tempfile
import unittest
from pathlib import Path
import math
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

from planing_seakeeping.benchmark_data import compare_reference_curve, load_reference_curve
from planing_seakeeping.config import load_config
from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.solver import analyze_speed
from planing_seakeeping.solver import solve_rao
from planing_seakeeping.validation import (
    _amplitude_prediction,
    _ma2005_hydro_gap_report_lines,
    _ma2005_panel_convergence_report_lines,
    _ma2005_computed_coefficient,
    _ma2005_error_metrics,
    _ma2005_external_pdstrip_cache_work_dir,
    _ma2005_geometry_metadata,
    _ma2005_hull_from_row,
    _ma2005_matrix_cache_key,
    _write_ma2005_aft_terminal_end_closure_audit,
    _write_ma2005_complex_forward_identity_audit,
    _write_ma2005_eq30_component_contribution_audit,
    _write_ma2005_geometry_transport_balance_audit,
    _write_ma2005_interior_mi_transport_consistency_audit,
    _write_ma2005_projection_derivative_balance_audit,
    _write_ma2005_projection_transport_audit,
    _ma2005_row_measure_transport_summary,
    _ma2005_row_measure_mapping_candidate_overview,
    _ma2005_row_measure_mapping_candidate_summary,
    _ma2005_endpoint_force_route_candidate_rows,
    _write_ma2005_endpoint_force_route_candidate_audit,
    _write_ma2005_distributed_geometry_component_route_audit,
    _write_ma2005_pressure_gradient_replacement_scale_audit,
    _ma2005_row_measure_zero_mi_boundary_audit_rows,
    _ma2005_row_measure_zero_mi_boundary_summary,
    _ma2005_heave_projection_measure_identity_rows,
    _write_ma2005_heave_projection_measure_identity_audit,
    _ma2005_formula_transport_identity_rows,
    _write_ma2005_formula_transport_identity_audit,
    _write_ma2005_eq31_product_rule_endpoint_requirement_audit,
    _write_ma2005_conservative_product_derivative_audit,
    _write_ma2005_mapping_conservative_product_derivative_audit,
    _write_ma2005_fixed_control_surface_transport_gap_audit,
    _write_ma2005_zero_m3_geometry_transport_blocker_trace,
    _write_ma2005_heave_row_ab_pairing_audit,
    _write_ma2005_time_pressure_source_audit,
    _write_ma2005_heave_pressure_radiation_check,
    _write_ma2005_open_section_pressure_reference_audit,
    _write_ma2005_pitch_row_moment_chain_audit,
    _write_ma2005_pitch_complex_station_closure_audit,
    _write_ma2005_pitch_complex_startup_window_audit,
    _write_ma2005_pitch_fixed_measure_consistency_audit,
    _write_ma2005_pitch_mapping_complex_closure_audit,
    _write_ma2005_pitch_end_contour_complex_requirement_audit,
    _write_ma2005_pitch_damping_normalization_blocker_trace,
    _write_ma2005_pitch_m5_forward_speed_scale_probe,
    _ma2005_force_for_assembly_route,
    _write_ma2005_pitch_complex_component_phase_budget_audit,
    _write_ma2005_pitch_endpoint_spike_dominance_audit,
    _write_ma2005_pitch_eq31_eq32_moment_balance_audit,
    _write_ma2005_remaining_failure_chain_budget_audit,
    _write_ma2005_b55_damping_pressure_source_audit,
    _ma2005_pitch_fixed_measure_panel_audit_rows,
    _ma2005_pitch_fixed_measure_panel_audit_summary,
    _write_ma2005_pitch_moment_complex_scale_requirement_audit,
    _write_ma2005_ab_force_reconstruction_candidate_audit,
    _write_ma2005_force_assembly_route_candidate_audit,
    _write_ma2005_force_assembly_theory_consistency_audit,
    _write_ma2005_row_measure_end_contour_interaction_audit,
    _write_ma2005_b33_endpoint_half_station_closure_audit,
    _write_ma2005_endpoint_forward_route_candidate_audit,
    _write_ma2005_heave_row_pitch_column_split_audit,
    _write_ma2005_literature_traceability_gap_audit,
    _write_ma2005_journee_table_reference_audit,
    _write_ma2005_gate1_reference_trace,
    _write_ma2005_a1_frequency_ladder_audit,
    _write_ma2005_reference_root_consistency_audit,
    _write_ma2005_reference_pairing_policy_audit,
    _write_ma2005_journee_frequency_gate_probe,
    _write_ma2005_journee_paired_table_gate_probe,
    _write_ma2005_journee_coefficient_frequency_trend_audit,
    _write_ma2005_journee_component_frequency_trend_audit,
    _write_ma2005_body_potential_frequency_entry_audit,
    _write_ma2005_journee_complex_scale_phase_audit,
    _write_ma2005_journee_cell35_pitch_column_complex_audit,
    _write_ma2005_journee_cell35_component_complex_audit,
    _write_ma2005_journee_cell35_time_pressure_phase_candidate_audit,
    _write_ma2005_time_pressure_harmonic_convention_trace_audit,
    _write_ma2005_fixed_control_surface_boundary_gap_audit,
    _write_ma2005_control_surface_end_contour_audit,
    _write_ma2005_local_time_phase_component_audit,
    _write_ma2005_local_time_phase_frequency_sensitivity_audit,
    _write_ma2005_coefficient_conversion_chain_audit,
    _write_ma2005_body_condition_unit_chain_audit,
    _write_ma2005_time_pressure_scale_origin_audit,
    _write_ma2005_time_pressure_pi_kernel_trace_audit,
    _write_ma2005_time_pressure_formula_unit_chain_audit,
    _write_ma2005_body_potential_normalization_trace_audit,
    _ma2005_body_potential_constant_mode_rows,
    _write_ma2005_body_potential_constant_mode_audit,
    _write_ma2005_body_potential_time_pressure_chain_audit,
    _write_ma2005_phi_phi_n_kernel_normalization_trace_audit,
    _write_ma2005_inner_free_surface_geometry_candidate_audit,
    _write_ma2005_free_surface_geometry_rhs_marching_cross_audit,
    _write_ma2005_inner_free_surface_rhs_row_block_candidate_audit,
    _write_ma2005_inner_free_surface_control_row_scale_requirement_audit,
    _write_ma2005_inner_free_surface_control_row_projection_candidate_audit,
    _write_ma2005_eq23_sign_mapping_audit,
    _write_ma2005_eq23_normal_definition_audit,
    _write_ma2005_phi_n_orientation_audit,
    _write_ma2005_a1_semantic_normal_audit,
    _write_ma2005_sc_shared_unknown_convention_audit,
    _write_ma2005_control_row_free_surface_rhs_source_candidate_audit,
    _write_ma2005_control_row_rhs_source_projection_coupled_candidate_audit,
    _write_ma2005_control_row_free_surface_rhs_source_audit,
    _write_ma2005_a1_free_surface_grid_implementation_audit,
    _write_ma2005_shared_body_potential_scale_audit,
    _write_ma2005_time_pressure_scale_candidate_audit,
    _write_ma2005_free_surface_longitudinal_staggering_audit,
    _write_ma2005_gate1_remaining_blocker_audit,
    _write_ma2005_candidate_impact_summary,
    _write_ma2005_zero_mi_normal_transport_candidate_audit,
    _write_ma2005_zero_m3_transport_scale_requirement_audit,
    _write_ma2005_row_measure_transport_direction_candidate_audit,
    _write_ma2005_section_force_derivative_audit,
    _write_ma2005_station_geometry_transport_closure_audit,
    _write_ma2005_station_marching_direction_audit,
    _write_ma2005_station_mapping_gradient_audit,
    make_faltinsen_ch9_case,
    validate_faltinsen_ch9,
    validate_goal_gap_audit,
    validate_katayama_classification,
    validate_katayama_qualitative_trends,
    validate_reasonableness,
    validate_section_bem_numerics,
)
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    InnerDomainPanelGeometry,
    MatchedSectionSolution,
    compute_heave_pitch_row_measure_transport_force_matrix,
)
from planing_seakeeping.pdstrip_external import parse_sectionresults
from planing_seakeeping.types import ValidityReport


ROOT = Path(__file__).resolve().parents[1]


class ValidationTests(unittest.TestCase):
    def _synthetic_pdstrip_sectionresults(self, path: Path, station_count: int, omega: float = 2.0):
        lines = ["Synthetic external PDSTRIP", "1"]
        for _station in range(station_count):
            radiation = [
                omega**2 * complex(2.0 if row == col else 0.0, -0.05)
                for row in range(3)
                for col in range(3)
            ]
            diffraction = [complex(1.0 + idx, 0.0) for idx in range(3)]
            froude_krylov = [complex(2.0 + idx, 0.0) for idx in range(3)]
            lines.append(f"{omega:.6f} 1 0.0")
            lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in radiation))
            lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in diffraction))
            lines.append(" ".join(f"({value.real:.6f},{value.imag:.6f})" for value in froude_krylov))
        lines.append("123.456")
        path.write_text("\n".join(lines), encoding="ascii")
        return parse_sectionresults(path)

    def test_ma2005_error_metrics_use_near_zero_absolute_tolerance(self):
        metrics = _ma2005_error_metrics(
            expected=0.0,
            actual=0.006,
            relative_tolerance=0.30,
            row_idx=2,
            col_idx=4,
            normalization="ma2005",
        )
        self.assertEqual(metrics["status"], "PASS")
        self.assertEqual(metrics["error_metric"], "absolute_near_zero")
        self.assertAlmostEqual(float(metrics["effective_abs_tolerance"]), 0.01)

    def test_ma2005_error_metrics_keep_relative_tolerance_away_from_zero(self):
        metrics = _ma2005_error_metrics(
            expected=0.2,
            actual=0.27,
            relative_tolerance=0.30,
            row_idx=2,
            col_idx=4,
            normalization="ma2005",
        )
        self.assertEqual(metrics["status"], "FAIL")
        self.assertEqual(metrics["error_metric"], "relative")

    def test_ma2005_section_force_derivative_audit_reconstructs_ab_complex_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            omega_bar = 1.0
            length_m = 9.80665
            omega = 1.0
            speed = 2.0
            x = [0.0, 1.0, 2.0]
            time_complex = [1.0 + 0.0j, 2.0 + 0.0j, 4.0 + 0.0j]
            time_gradient = [1.0 + 0.0j, 1.5 + 0.0j, 2.0 + 0.0j]
            forward_complex = [speed / (-1j * omega) * value for value in time_gradient]

            comparison = pd.DataFrame(
                [
                    {
                        "row": 0,
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_pressure_gradient_component_value": 0.0,
                    },
                    {
                        "row": 1,
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_pressure_gradient_component_value": -6.0,
                    },
                ]
            )
            rows = []
            for coefficient in ("A33", "B33"):
                prefix = coefficient[0]
                for station_index, x_m in enumerate(x):
                    time_value = (
                        time_complex[station_index].real / omega**2
                        if prefix == "A"
                        else -time_complex[station_index].imag / omega
                    )
                    forward_value = (
                        forward_complex[station_index].real / omega**2
                        if prefix == "A"
                        else -forward_complex[station_index].imag / omega
                    )
                    rows.append(
                        {
                            "coefficient": coefficient,
                            "station_index": station_index,
                            "x_m": x_m,
                            "x_over_l": x_m / length_m,
                            "time_derivative_density_value_per_m": time_value,
                            "pressure_gradient_density_value_per_m": forward_value,
                            "stokes_body_forward_density_value_per_m": 0.0,
                        }
                    )
            detail, summary = _write_ma2005_section_force_derivative_audit(
                comparison,
                pd.DataFrame(rows),
                tmp_path,
                "synthetic",
            )
            self.assertEqual(set(summary["coefficient"]), {"A33", "B33"})
            self.assertGreater(len(detail), 0)
            self.assertLess(
                float(
                    pd.to_numeric(
                        summary["pressure_gradient_minus_force_derivative_proxy_integral_value"],
                        errors="coerce",
                    )
                    .abs()
                    .max()
                ),
                1e-12,
            )
            self.assertLess(
                float(pd.to_numeric(summary["station_integral_closure_residual"], errors="coerce").abs().max()),
                1e-12,
            )

    def test_ma2005_complex_forward_identity_audit_reconstructs_ab_force_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            omega = 2.0
            length_m = 9.80665

            def raw_pair(force: complex) -> tuple[float, float]:
                return force.real / omega**2, -force.imag / omega

            time_force = 5.0 + 2.0j
            gradient_force = 3.0 - 4.0j
            stokes_force = 1.0 - 1.0j
            end_force = 2.0 - 3.0j
            current_force = time_force + gradient_force + end_force
            a_current, b_current = raw_pair(current_force)
            a_time, b_time = raw_pair(time_force)
            a_gradient, b_gradient = raw_pair(gradient_force)
            a_stokes, b_stokes = raw_pair(stokes_force)
            a_end, b_end = raw_pair(end_force)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega,
                        "hull_length_m": length_m,
                        "normalization_scale": 1.0,
                        "reference_value": a_current,
                        "raw_computed_value": a_current,
                        "status": "PASS",
                        "matched_time_derivative_component_raw": a_time,
                        "matched_pressure_gradient_component_raw": a_gradient,
                        "matched_stokes_body_forward_component_raw": a_stokes,
                        "matched_end_term_component_raw": a_end,
                    },
                    {
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega,
                        "hull_length_m": length_m,
                        "normalization_scale": 1.0,
                        "reference_value": b_current,
                        "raw_computed_value": b_current,
                        "status": "PASS",
                        "matched_time_derivative_component_raw": b_time,
                        "matched_pressure_gradient_component_raw": b_gradient,
                        "matched_stokes_body_forward_component_raw": b_stokes,
                        "matched_end_term_component_raw": b_end,
                    },
                    {
                        "coefficient": "A35",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "hull_length_m": length_m,
                        "normalization_scale": 1.0,
                        "reference_value": 1.0,
                        "raw_computed_value": 1.0,
                        "status": "FAIL",
                    },
                    {
                        "coefficient": "B35",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": 2.0,
                        "hull_length_m": length_m,
                        "normalization_scale": 1.0,
                        "reference_value": 1.0,
                        "raw_computed_value": 1.0,
                        "status": "FAIL",
                    },
                ]
            )
            detail, summary = _write_ma2005_complex_forward_identity_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertEqual(len(summary), 1)
            paired = detail[detail["pair_status"].eq("paired_same_frequency_ab_complex_reconstruction")]
            unpaired = detail[detail["pair_status"].eq("frequency_mismatch_unpaired")]
            self.assertEqual(set(paired["matrix_cell"]), {"33"})
            self.assertEqual(set(unpaired["matrix_cell"]), {"35"})
            self.assertEqual(paired["identity_status"].iloc[0], "PASS")
            self.assertLess(float(paired["complex_identity_residual_norm"].iloc[0]), 1e-12)
            self.assertLess(float(paired["current_force_closure_residual_norm"].iloc[0]), 1e-12)
            self.assertEqual(int(summary["pairable_ab_complex_count"].iloc[0]), 1)
            self.assertEqual(int(summary["unpairable_frequency_or_missing_count"].iloc[0]), 1)
            self.assertIn("frequency_pair_gap", summary["diagnostic_conclusion"].iloc[0])

    def test_ma2005_projection_derivative_balance_audit_compares_three_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "reference_value": 0.1,
                        "computed_value": 2.0,
                        "gate_error_ratio": 10.0,
                        "status": "FAIL",
                    },
                    {
                        "coefficient": "B55",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "reference_value": 0.2,
                        "computed_value": 3.0,
                        "gate_error_ratio": 12.0,
                        "status": "FAIL",
                    },
                ]
            )
            section = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "matrix_cell": "55",
                        "force_derivative_proxy_integral_value": 1.0,
                    },
                    {
                        "coefficient": "B55",
                        "matrix_cell": "55",
                        "force_derivative_proxy_integral_value": 1.5,
                    },
                ]
            )
            identity = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "pressure_gradient_integral_value": 4.0,
                        "stokes_body_forward_integral_value": 2.0,
                        "end_contour_integral_value": 0.5,
                    },
                    {
                        "coefficient": "B55",
                        "pressure_gradient_integral_value": 5.0,
                        "stokes_body_forward_integral_value": 1.0,
                        "end_contour_integral_value": 0.5,
                    },
                ]
            )
            detail, summary = _write_ma2005_projection_derivative_balance_audit(
                comparison,
                section,
                identity,
                tmp_path,
                "synthetic",
            )
            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 1)
            self.assertTrue(detail["ab_frequency_pair_status"].eq("same_frequency_ab_pair").all())
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
            self.assertEqual(int(summary["same_frequency_pair_count"].iloc[0]), 2)
            self.assertEqual(int(summary["gradient_stokes_end_pass_count"].iloc[0]), 0)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "same_frequency_projection_balance_does_not_close",
            )

    def test_ma2005_projection_transport_audit_tracks_endpoint_jump_and_direct_gradient_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            omega_bar = 1.0
            length_m = 9.80665
            omega = 1.0
            speed = 2.0
            x = [0.0, 1.0, 2.0]
            time_complex = [1.0 + 0.0j, 2.0 + 0.0j, 3.0 + 0.0j]
            transport_complex = [0.0 + 2.0j, 0.0 + 2.0j, 0.0 + 2.0j]
            direct_complex = [value + 1.0j for value in transport_complex]

            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_end_term_component_value": 0.0,
                        "matched_end_term_component_raw": 0.0,
                    },
                    {
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_end_term_component_value": 0.0,
                        "matched_end_term_component_raw": 0.0,
                    },
                ]
            )
            rows = []
            for coefficient in ("A33", "B33"):
                prefix = coefficient[0]
                for station_index, x_m in enumerate(x):
                    time_value = (
                        time_complex[station_index].real / omega**2
                        if prefix == "A"
                        else -time_complex[station_index].imag / omega
                    )
                    direct_value = (
                        direct_complex[station_index].real / omega**2
                        if prefix == "A"
                        else -direct_complex[station_index].imag / omega
                    )
                    rows.append(
                        {
                            "coefficient": coefficient,
                            "station_index": station_index,
                            "x_m": x_m,
                            "x_over_l": x_m / length_m,
                            "time_derivative_density_value_per_m": time_value,
                            "pressure_gradient_density_value_per_m": direct_value,
                            "stokes_body_forward_density_value_per_m": 0.0,
                        }
                    )

            detail, summary = _write_ma2005_projection_transport_audit(
                comparison,
                pd.DataFrame(rows),
                tmp_path,
                "synthetic",
            )

            self.assertEqual(set(summary["coefficient"]), {"A33", "B33"})
            self.assertGreater(len(detail), 0)
            paired = summary[summary["coefficient"].eq("B33")].iloc[0]
            self.assertEqual(paired["ab_frequency_pair_status"], "same_frequency_ab_pair")
            self.assertLess(abs(float(paired["transport_minus_endpoint_jump_value"])), 1e-12)
            self.assertGreater(float(paired["direct_transport_residual_norm"]), 0.0)
            self.assertEqual(
                paired["diagnostic_conclusion"],
                "projection_transport_closes_to_endpoint_but_not_direct_gradient",
            )
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_pitch_complex_station_closure_audit_reports_complex_residuals(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            omega_bar = 1.0
            length_m = 9.80665
            speed = 2.0
            x = [0.0, 1.0, 2.0]
            projection_density = [0.0 + 0.0j, 1.0 + 0.0j, 2.0 + 0.0j]
            time_complex = [-1j * value for value in projection_density]
            direct_complex = [3.0 + 0.0j for _ in x]
            stokes_complex = [1.5 + 0.0j for _ in x]

            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_end_term_component_value": 0.5,
                    },
                    {
                        "coefficient": "B55",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": speed,
                        "normalization_scale": 1.0,
                        "matched_end_term_component_value": 0.0,
                    },
                ]
            )
            rows = []
            for coefficient in ("A55", "B55"):
                prefix = coefficient[0]
                for station_index, x_m in enumerate(x):
                    def projected(value: complex) -> float:
                        return value.real if prefix == "A" else -value.imag

                    rows.append(
                        {
                            "coefficient": coefficient,
                            "station_index": station_index,
                            "x_m": x_m,
                            "x_over_l": x_m / length_m,
                            "time_derivative_density_value_per_m": projected(time_complex[station_index]),
                            "pressure_gradient_density_value_per_m": projected(direct_complex[station_index]),
                            "stokes_body_forward_density_value_per_m": projected(stokes_complex[station_index]),
                        }
                    )

            detail, summary = _write_ma2005_pitch_complex_station_closure_audit(
                comparison,
                pd.DataFrame(rows),
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(summary), 1)
            row = summary.iloc[0]
            self.assertEqual(row["pair_status"], "same_frequency_ab_pair")
            self.assertAlmostEqual(float(row["direct_pressure_gradient_force_real"]), 6.0)
            self.assertAlmostEqual(float(row["projection_transport_force_real"]), 4.0)
            self.assertAlmostEqual(float(row["stokes_plus_end_force_real"]), 3.5)
            self.assertGreater(float(row["direct_minus_transport_residual_norm"]), 0.0)
            self.assertEqual(row["diagnostic_conclusion"], "pitch_complex_station_closure_not_closed")
            self.assertTrue((tmp_path / "synthetic_pitch_complex_station_closure_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_complex_station_closure_summary.csv").exists())
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_pitch_complex_startup_window_audit_reports_front_window_sensitivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "station_index": 0,
                        "x_m": 0.0,
                        "x_over_l": 0.0,
                        "trapz_weight_m": 1.0,
                        "direct_pressure_gradient_force_density_real": 10.0,
                        "direct_pressure_gradient_force_density_imag": 0.0,
                        "projection_transport_force_density_real": 0.0,
                        "projection_transport_force_density_imag": 0.0,
                        "stokes_body_forward_force_density_real": 0.0,
                        "stokes_body_forward_force_density_imag": 0.0,
                        "direct_minus_transport_station_force_real": 10.0,
                        "direct_minus_transport_station_force_imag": 0.0,
                        "station_abs_direct_transport_residual_share": 1.0,
                        "diagnostic_flags": "first_active_station",
                    },
                    {
                        "matrix_cell": "55",
                        "station_index": 1,
                        "x_m": 1.0,
                        "x_over_l": 0.1,
                        "trapz_weight_m": 1.0,
                        "direct_pressure_gradient_force_density_real": 1.0,
                        "direct_pressure_gradient_force_density_imag": 0.0,
                        "projection_transport_force_density_real": 1.0,
                        "projection_transport_force_density_imag": 0.0,
                        "stokes_body_forward_force_density_real": 1.0,
                        "stokes_body_forward_force_density_imag": 0.0,
                        "direct_minus_transport_station_force_real": 0.0,
                        "direct_minus_transport_station_force_imag": 0.0,
                        "station_abs_direct_transport_residual_share": 0.0,
                        "diagnostic_flags": "none",
                    },
                    {
                        "matrix_cell": "55",
                        "station_index": 2,
                        "x_m": 2.0,
                        "x_over_l": 0.2,
                        "trapz_weight_m": 1.0,
                        "direct_pressure_gradient_force_density_real": 1.0,
                        "direct_pressure_gradient_force_density_imag": 0.0,
                        "projection_transport_force_density_real": 1.0,
                        "projection_transport_force_density_imag": 0.0,
                        "stokes_body_forward_force_density_real": 1.0,
                        "stokes_body_forward_force_density_imag": 0.0,
                        "direct_minus_transport_station_force_real": 0.0,
                        "direct_minus_transport_station_force_imag": 0.0,
                        "station_abs_direct_transport_residual_share": 0.0,
                        "diagnostic_flags": "none",
                    },
                ]
            )
            summary = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "end_contour_force_real": 0.0,
                        "end_contour_force_imag": 0.0,
                    }
                ]
            )

            station_detail, window_summary = _write_ma2005_pitch_complex_startup_window_audit(
                detail,
                summary,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_pitch_complex_startup_window_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_complex_startup_window_summary.csv").exists())
            self.assertTrue(station_detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
            baseline = window_summary[window_summary["window_name"].eq("full_station_set")].iloc[0]
            first = window_summary[window_summary["window_name"].eq("exclude_first_1_stations")].iloc[0]
            self.assertGreater(float(baseline["direct_minus_transport_residual_norm"]), 0.0)
            self.assertAlmostEqual(float(first["direct_minus_transport_residual_norm"]), 0.0)
            self.assertAlmostEqual(float(first["excluded_direct_transport_residual_share"]), 1.0)
            self.assertEqual(
                first["diagnostic_conclusion"],
                "front_window_strongly_reduces_direct_transport_residual",
            )

    def test_ma2005_pitch_fixed_measure_consistency_audit_merges_pitch_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pitch_complex_summary = pd.DataFrame(
                [
                    {
                        "direct_minus_transport_residual_norm": 0.75,
                        "direct_stokes_end_residual_norm": 0.8,
                        "transport_stokes_end_residual_norm": 1.1,
                    }
                ]
            )
            startup_summary = pd.DataFrame(
                [
                    {
                        "window_name": "full_station_set",
                        "direct_minus_transport_norm_ratio_vs_full": 1.0,
                        "direct_minus_transport_improvement_fraction": 0.0,
                        "diagnostic_conclusion": "baseline_full_station_set",
                    },
                    {
                        "window_name": "exclude_first_1_stations",
                        "direct_minus_transport_norm_ratio_vs_full": 1.2,
                        "direct_minus_transport_improvement_fraction": -0.2,
                        "diagnostic_conclusion": "front_window_does_not_reduce_direct_transport_residual",
                    },
                ]
            )
            row_measure = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "row_family": "pitch_row_N5_m5",
                        "column_family": "pitch_radiation",
                        "row_measure_transport_integral_value": -0.4,
                        "stokes_body_forward_integral_value": 1.6,
                        "transport_stokes_residual_norm": 1.6,
                        "transport_negative_stokes_residual_norm": 1.0,
                        "least_squares_transport_over_negative_stokes_scale": 0.4,
                        "least_squares_scaled_residual_norm": 0.8,
                        "median_row_gradient_to_stokes_m_norm_ratio": 0.87,
                        "median_row_gradient_stokes_m_alignment": -0.95,
                        "peak_abs_residual_x_over_l": 0.3,
                        "diagnostic_conclusion": "row_measure_transport_expected_opposite_sign_but_scale_mismatch",
                    },
                    {
                        "coefficient": "B55",
                        "row_family": "pitch_row_N5_m5",
                        "column_family": "pitch_radiation",
                        "row_measure_transport_integral_value": -0.6,
                        "stokes_body_forward_integral_value": 0.4,
                        "transport_stokes_residual_norm": 2.2,
                        "transport_negative_stokes_residual_norm": 2.1,
                        "least_squares_transport_over_negative_stokes_scale": 0.08,
                        "least_squares_scaled_residual_norm": 2.0,
                        "median_row_gradient_to_stokes_m_norm_ratio": 0.87,
                        "median_row_gradient_stokes_m_alignment": -0.95,
                        "peak_abs_residual_x_over_l": 0.02,
                        "diagnostic_conclusion": "row_measure_transport_expected_opposite_sign_but_scale_mismatch",
                    },
                ]
            )

            detail, summary = _write_ma2005_pitch_fixed_measure_consistency_audit(
                pitch_complex_summary,
                startup_summary,
                row_measure,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 1)
            row = summary.iloc[0]
            self.assertEqual(row["row_measure_scale_mismatch_count"], 2)
            self.assertEqual(
                row["diagnostic_conclusion"],
                "pitch_fixed_measure_scale_mismatch_not_startup_window",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_fixed_measure_consistency_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_fixed_measure_consistency_summary.csv").exists())
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_pitch_mapping_complex_closure_audit_compares_mapping_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            omega_bar = 1.0
            length_m = 9.80665
            x = [0.0, 1.0, 2.0]
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": 1.0,
                        "normalization_scale": 1.0,
                    },
                    {
                        "coefficient": "B55",
                        "hull": "synthetic",
                        "speed_case": "Fn0.4",
                        "omega_e_sqrt_l_over_g": omega_bar,
                        "hull_length_m": length_m,
                        "speed_mps": 1.0,
                        "normalization_scale": 1.0,
                    },
                ]
            )
            pitch_detail = pd.DataFrame(
                [
                    {
                        "benchmark": "synthetic",
                        "matrix_cell": "55",
                        "station_index": i,
                        "x_m": value,
                        "x_over_l": value / length_m,
                        "direct_pressure_gradient_force_density_real": 3.0,
                        "direct_pressure_gradient_force_density_imag": 0.0,
                        "projection_transport_force_density_real": 2.0,
                        "projection_transport_force_density_imag": 0.0,
                        "stokes_body_forward_force_density_real": 3.0,
                        "stokes_body_forward_force_density_imag": 0.0,
                    }
                    for i, value in enumerate(x)
                ]
            )
            pitch_summary = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "omega_rad_s": 1.0,
                        "speed_mps": 1.0,
                        "direct_pressure_gradient_force_real": 6.0,
                        "direct_pressure_gradient_force_imag": 0.0,
                        "projection_transport_force_real": 4.0,
                        "projection_transport_force_imag": 0.0,
                        "stokes_plus_end_force_real": 6.0,
                        "stokes_plus_end_force_imag": 0.0,
                        "end_contour_force_real": 0.0,
                        "end_contour_force_imag": 0.0,
                    }
                ]
            )
            mapping_rows = []
            for candidate_name, a_density in [
                ("current_equal_panel_x_derivative", 2.0),
                ("mapped_normalized_y_central", 3.0),
            ]:
                for coefficient, density in [("A55", a_density), ("B55", 0.0)]:
                    for station_index, x_m in enumerate(x):
                        mapping_rows.append(
                            {
                                "benchmark": "synthetic",
                                "candidate_name": candidate_name,
                                "source_row": 0,
                                "coefficient": coefficient,
                                "station_index": station_index,
                                "x_m": x_m,
                                "x_over_l": x_m / length_m,
                                "candidate_transport_density_value_per_m": density,
                            }
                        )
            detail, summary = _write_ma2005_pitch_mapping_complex_closure_audit(
                comparison,
                pitch_detail,
                pitch_summary,
                pd.DataFrame(mapping_rows),
                tmp_path,
                "synthetic",
            )

            self.assertEqual(set(summary["candidate_name"]), {"current_equal_panel_x_derivative", "mapped_normalized_y_central"})
            closed = summary[summary["candidate_name"].eq("mapped_normalized_y_central")].iloc[0]
            current = summary[summary["candidate_name"].eq("current_equal_panel_x_derivative")].iloc[0]
            self.assertEqual(closed["pair_status"], "same_frequency_ab_pair")
            self.assertAlmostEqual(float(closed["direct_candidate_residual_norm"]), 0.0)
            self.assertAlmostEqual(float(closed["candidate_stokes_end_residual_norm"]), 0.0)
            self.assertEqual(
                closed["diagnostic_conclusion"],
                "mapping_candidate_complex_closes_direct_and_stokes_end",
            )
            self.assertGreater(float(current["direct_candidate_residual_norm"]), 0.0)
            self.assertTrue((tmp_path / "synthetic_pitch_mapping_complex_closure_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_mapping_complex_closure_summary.csv").exists())
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
            self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_pitch_end_contour_complex_requirement_audit_reports_required_end_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "hull_length_m": 9.80665,
                        "speed_mps": 1.0,
                        "normalization_scale": 1.0,
                    },
                    {
                        "coefficient": "B55",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "hull_length_m": 9.80665,
                        "speed_mps": 1.0,
                        "normalization_scale": 1.0,
                    },
                ]
            )
            pitch_summary = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "direct_pressure_gradient_force_real": 6.0,
                        "direct_pressure_gradient_force_imag": 0.0,
                        "projection_transport_force_real": 4.0,
                        "projection_transport_force_imag": 0.0,
                        "stokes_body_forward_force_real": 3.0,
                        "stokes_body_forward_force_imag": 0.0,
                        "end_contour_force_real": 1.0,
                        "end_contour_force_imag": 0.0,
                    }
                ]
            )
            end_summary = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "endpoint_forward_gradient_integral_value": 1.0,
                        "endpoint_total_pressure_integral_value": 1.0,
                    },
                    {
                        "coefficient": "B55",
                        "endpoint_forward_gradient_integral_value": 0.0,
                        "endpoint_total_pressure_integral_value": 0.0,
                    },
                ]
            )

            detail, summary = _write_ma2005_pitch_end_contour_complex_requirement_audit(
                comparison,
                pitch_summary,
                end_summary,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(set(detail["closure_target"]), {"direct_pressure_gradient_closure", "projection_transport_closure"})
            direct = detail[detail["closure_target"].eq("direct_pressure_gradient_closure")].iloc[0]
            transport = detail[detail["closure_target"].eq("projection_transport_closure")].iloc[0]
            self.assertAlmostEqual(float(direct["required_end_contour_force_real"]), 3.0)
            self.assertAlmostEqual(float(direct["required_over_current_end_scale_real"]), 3.0)
            self.assertGreater(float(direct["required_current_end_residual_norm"]), 0.0)
            self.assertAlmostEqual(float(transport["required_end_contour_force_real"]), 1.0)
            self.assertAlmostEqual(float(transport["required_current_end_residual_norm"]), 0.0)
            self.assertEqual(
                summary.iloc[0]["diagnostic_conclusion"],
                "end_contour_requirement_differs_by_closure_target",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_end_contour_complex_requirement_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_end_contour_complex_requirement_summary.csv").exists())
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
            self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_pitch_fixed_measure_panel_audit_separates_measure_and_identity(self):
        x = np.asarray([[0.0, 1.0, 2.0]], dtype=float)
        x_over_l = np.asarray([[0.0, 0.5, 1.0]], dtype=float)
        station_count = 3
        panel_count = 2
        normal_z = -np.ones((1, station_count, panel_count), dtype=float)
        panel_length = np.ones((1, station_count, panel_count), dtype=float)
        lever = np.asarray([[3.0, 1.0, 0.0]], dtype=float)
        heave_measure = -normal_z[0] * panel_length[0]
        n5 = lever[0, :, None] * heave_measure
        gradient = np.gradient(n5, x[0], axis=0, edge_order=2)
        row_measure = np.zeros((1, station_count, 2, panel_count), dtype=float)
        row_gradient = np.zeros_like(row_measure)
        stokes_m = np.zeros_like(row_measure)
        row_measure[0, :, 1, :] = n5
        row_gradient[0, :, 1, :] = gradient
        stokes_m[0, :, 1, :] = heave_measure
        pitch_phi = np.ones((1, station_count, panel_count), dtype=complex)
        hydro = SimpleNamespace(
            contribution_breakdown={
                "station_x_m": x,
                "station_x_over_l": x_over_l,
                "heave_pitch_pressure_row_measure_by_station": row_measure,
                "heave_pitch_pressure_row_measure_x_gradient_by_station": row_gradient,
                "heave_pitch_stokes_m_measure_by_station": stokes_m,
                "body_panel_normal_z_by_station": normal_z,
                "body_panel_length_by_station": panel_length,
                "pitch_body_potential_by_station": pitch_phi,
                "pitch_moment_lever_arms_m": lever,
                "pitch_radiation_lever_arms_m": lever,
                "pitch_base_lever_arms_m": lever,
            }
        )

        rows = _ma2005_pitch_fixed_measure_panel_audit_rows(
            hydro,
            benchmark="synthetic",
            source_row=0,
            hull="synthetic",
            speed_case="Fn",
            omega_e_sqrt_l_over_g=1.0,
            coefficient="A55",
            prefix="A",
            row_idx=4,
            col_idx=4,
            normalization_scale=1.0,
            omega_rad_s=1.0,
            rho_water_kg_m3=1.0,
            forward_speed_mps=1.0,
            reference_value=1.0,
        )
        detail = pd.DataFrame(rows)
        summary = _ma2005_pitch_fixed_measure_panel_audit_summary(detail, "synthetic")

        self.assertEqual(len(detail), station_count * panel_count)
        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertLess(float(row["pressure_measure_residual_norm"]), 1e-12)
        self.assertLess(float(row["stokes_measure_residual_norm"]), 1e-12)
        self.assertLess(float(row["gradient_measure_residual_norm"]), 1e-12)
        self.assertLess(float(row["product_rule_residual_norm"]), 1e-12)
        self.assertGreater(float(row["row_gradient_negative_stokes_residual_norm"]), 0.25)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "pitch_measures_match_local_convention_but_not_negative_stokes_identity",
        )
        self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_geometry_transport_balance_audit_flags_opposite_required_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            projection_transport = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "coefficient": "A55",
                        "pair_status": "same_frequency_ab_pair",
                        "ab_frequency_pair_status": "same_frequency_ab_pair",
                        "direct_pressure_gradient_integral_value": 2.0,
                        "projection_transport_integral_value": 1.0,
                        "stokes_plus_end_integral_value": 4.0,
                        "direct_transport_residual_norm": 0.5,
                        "transport_stokes_end_residual_norm": 0.75,
                    },
                    {
                        "matrix_cell": "55",
                        "coefficient": "B55",
                        "pair_status": "same_frequency_ab_pair",
                        "ab_frequency_pair_status": "same_frequency_ab_pair",
                        "direct_pressure_gradient_integral_value": 2.0,
                        "projection_transport_integral_value": 4.0,
                        "stokes_plus_end_integral_value": 4.0,
                        "direct_transport_residual_norm": 0.5,
                        "transport_stokes_end_residual_norm": 0.0,
                    },
                ]
            )
            detail, summary = _write_ma2005_geometry_transport_balance_audit(
                projection_transport,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 1)
            a55 = detail[detail["coefficient"].eq("A55")].iloc[0]
            b55 = detail[detail["coefficient"].eq("B55")].iloc[0]
            self.assertEqual(
                a55["diagnostic_conclusion"],
                "inferred_geometry_transport_opposes_required_stokes_end_balance",
            )
            self.assertEqual(
                b55["diagnostic_conclusion"],
                "inferred_geometry_transport_matches_required_stokes_end_balance",
            )
            self.assertEqual(int(summary["same_frequency_pair_count"].iloc[0]), 2)
            self.assertEqual(int(summary["opposite_sign_count"].iloc[0]), 1)
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_station_geometry_transport_closure_audit_localizes_endpoint_residual(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            projection_transport = pd.DataFrame(
                [
                    {
                        "matrix_cell": "55",
                        "coefficient": "A55",
                        "pair_status": "same_frequency_ab_pair",
                        "station_index": 0,
                        "x_m": 0.0,
                        "x_over_l": 0.0,
                        "trapz_weight_m": 0.5,
                        "direct_pressure_gradient_density_value_per_m": 0.0,
                        "projection_transport_derivative_density_value_per_m": 0.0,
                        "stokes_body_forward_density_value_per_m": 0.0,
                    },
                    {
                        "matrix_cell": "55",
                        "coefficient": "A55",
                        "pair_status": "same_frequency_ab_pair",
                        "station_index": 1,
                        "x_m": 1.0,
                        "x_over_l": 1.0,
                        "trapz_weight_m": 0.5,
                        "direct_pressure_gradient_density_value_per_m": 0.0,
                        "projection_transport_derivative_density_value_per_m": 0.0,
                        "stokes_body_forward_density_value_per_m": 0.0,
                    },
                ]
            )
            station_forward_identity = pd.DataFrame(
                [
                    {
                        "coefficient": "A55",
                        "station_index": 0,
                        "is_configured_end_station": True,
                        "end_contour_station_contribution_value": 2.0,
                    },
                    {
                        "coefficient": "A55",
                        "station_index": 1,
                        "is_configured_end_station": False,
                        "end_contour_station_contribution_value": 0.0,
                    },
                ]
            )

            detail, summary = _write_ma2005_station_geometry_transport_closure_audit(
                projection_transport,
                station_forward_identity,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 1)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "station_geometry_transport_residual_localized_at_configured_end",
            )
            self.assertAlmostEqual(float(summary["configured_end_abs_residual_share"].iloc[0]), 1.0)
            configured = detail[detail["is_configured_end_station"].astype(str).str.lower().eq("true")].iloc[0]
            self.assertAlmostEqual(float(configured["station_geometry_transport_residual_value"]), -2.0)
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_interior_mi_transport_consistency_audit_flags_opposite_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            station_geometry = pd.DataFrame(
                [
                    {
                        "coefficient": "B53",
                        "matrix_cell": "53",
                        "station_index": 0,
                        "x_m": 0.0,
                        "x_over_l": 0.0,
                        "is_configured_end_station": True,
                        "projection_transport_station_contribution_value": 0.0,
                        "stokes_body_forward_station_contribution_value": 0.0,
                    },
                    {
                        "coefficient": "B53",
                        "matrix_cell": "53",
                        "station_index": 1,
                        "x_m": 1.0,
                        "x_over_l": 0.5,
                        "is_configured_end_station": False,
                        "projection_transport_station_contribution_value": 1.0,
                        "stokes_body_forward_station_contribution_value": -2.0,
                    },
                    {
                        "coefficient": "B53",
                        "matrix_cell": "53",
                        "station_index": 2,
                        "x_m": 2.0,
                        "x_over_l": 1.0,
                        "is_configured_end_station": False,
                        "projection_transport_station_contribution_value": 2.0,
                        "stokes_body_forward_station_contribution_value": -4.0,
                    },
                ]
            )

            detail, summary = _write_ma2005_interior_mi_transport_consistency_audit(
                station_geometry,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 1)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "interior_transport_opposes_stokes_mi_row",
            )
            self.assertAlmostEqual(float(summary["least_squares_transport_over_stokes_scale"].iloc[0]), -0.5)
            self.assertAlmostEqual(float(summary["transport_stokes_opposite_sign_fraction"].iloc[0]), 1.0)
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_row_measure_transport_summary_flags_opposite_rows(self):
        data = pd.DataFrame(
            [
                {
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 0,
                    "x_m": 0.0,
                    "x_over_l": 0.0,
                    "row_measure_gradient_to_stokes_m_norm_ratio": 1.0,
                    "row_measure_gradient_stokes_m_alignment": -1.0,
                    "row_measure_transport_density_value_per_m": 1.0,
                    "stokes_body_forward_density_value_per_m": -2.0,
                },
                {
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 1,
                    "x_m": 1.0,
                    "x_over_l": 0.5,
                    "row_measure_gradient_to_stokes_m_norm_ratio": 1.0,
                    "row_measure_gradient_stokes_m_alignment": -1.0,
                    "row_measure_transport_density_value_per_m": 2.0,
                    "stokes_body_forward_density_value_per_m": -4.0,
                },
                {
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 2,
                    "x_m": 2.0,
                    "x_over_l": 1.0,
                    "row_measure_gradient_to_stokes_m_norm_ratio": 1.0,
                    "row_measure_gradient_stokes_m_alignment": -1.0,
                    "row_measure_transport_density_value_per_m": 3.0,
                    "stokes_body_forward_density_value_per_m": -6.0,
                },
            ]
        )

        summary = _ma2005_row_measure_transport_summary(data, "synthetic")

        self.assertEqual(len(summary), 1)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "row_measure_transport_expected_opposite_sign_but_scale_mismatch",
        )
        self.assertAlmostEqual(float(summary["least_squares_transport_over_stokes_scale"].iloc[0]), -0.5)
        self.assertAlmostEqual(float(summary["least_squares_transport_over_negative_stokes_scale"].iloc[0]), 0.5)
        self.assertAlmostEqual(float(summary["transport_stokes_opposite_sign_fraction"].iloc[0]), 1.0)
        self.assertAlmostEqual(float(summary["transport_negative_stokes_residual_norm"].iloc[0]), 0.5)
        self.assertEqual(str(summary["candidate_default_gate_eligible"].iloc[0]), "false")

    def test_ma2005_row_measure_direction_candidate_audit_compares_reversed_x(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data = pd.DataFrame(
                [
                    {
                        "source_row": 0,
                        "coefficient": "B53",
                        "row_family": "pitch_row_N5_m5",
                        "column_family": "heave_radiation",
                        "station_index": 0,
                        "x_m": 0.0,
                        "x_over_l": 0.0,
                        "row_measure_transport_density_value_per_m": 1.0,
                        "stokes_body_forward_density_value_per_m": -2.0,
                    },
                    {
                        "source_row": 0,
                        "coefficient": "B53",
                        "row_family": "pitch_row_N5_m5",
                        "column_family": "heave_radiation",
                        "station_index": 1,
                        "x_m": 1.0,
                        "x_over_l": 0.5,
                        "row_measure_transport_density_value_per_m": 2.0,
                        "stokes_body_forward_density_value_per_m": -4.0,
                    },
                    {
                        "source_row": 0,
                        "coefficient": "B53",
                        "row_family": "pitch_row_N5_m5",
                        "column_family": "heave_radiation",
                        "station_index": 2,
                        "x_m": 2.0,
                        "x_over_l": 1.0,
                        "row_measure_transport_density_value_per_m": 3.0,
                        "stokes_body_forward_density_value_per_m": -6.0,
                    },
                ]
            )

            detail, summary = _write_ma2005_row_measure_transport_direction_candidate_audit(
                data,
                tmp_path,
                "synthetic",
            )

            self.assertEqual(len(detail), 2)
            self.assertEqual(len(summary), 2)
            current = summary[summary["candidate_name"].eq("current_equal_panel_x_derivative")].iloc[0]
            reversed_x = summary[summary["candidate_name"].eq("reversed_x_derivative")].iloc[0]
            self.assertAlmostEqual(float(current["median_candidate_negative_stokes_residual_norm"]), 0.5)
            self.assertAlmostEqual(float(current["median_candidate_over_negative_stokes_scale"]), 0.5)
            self.assertEqual(
                current["diagnostic_conclusion"],
                "candidate_excluded_by_residual_scale_or_mapping_mismatch",
            )
            self.assertAlmostEqual(float(reversed_x["median_candidate_over_negative_stokes_scale"]), -0.5)
            self.assertEqual(
                reversed_x["diagnostic_conclusion"],
                "candidate_excluded_by_expected_sign_reversal",
            )
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
            self.assertTrue(
                (tmp_path / "synthetic_row_measure_transport_direction_candidate_detail.csv").exists()
            )
            self.assertTrue(
                (tmp_path / "synthetic_row_measure_transport_direction_candidate_summary.csv").exists()
            )

    def test_ma2005_row_measure_mapping_candidate_summary_ranks_control_surface_candidates(self):
        detail = pd.DataFrame(
            [
                {
                    "candidate_name": "mapped_normalized_arclength_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 0,
                    "x_m": 0.0,
                    "x_over_l": 0.0,
                    "candidate_transport_density_value_per_m": 2.0,
                    "stokes_body_forward_density_value_per_m": -2.0,
                },
                {
                    "candidate_name": "mapped_normalized_arclength_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 1,
                    "x_m": 1.0,
                    "x_over_l": 0.5,
                    "candidate_transport_density_value_per_m": 4.0,
                    "stokes_body_forward_density_value_per_m": -4.0,
                },
                {
                    "candidate_name": "mapped_normalized_arclength_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 2,
                    "x_m": 2.0,
                    "x_over_l": 1.0,
                    "candidate_transport_density_value_per_m": 6.0,
                    "stokes_body_forward_density_value_per_m": -6.0,
                },
                {
                    "candidate_name": "mapped_fixed_y_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 0,
                    "x_m": 0.0,
                    "x_over_l": 0.0,
                    "candidate_transport_density_value_per_m": -1.0,
                    "stokes_body_forward_density_value_per_m": -2.0,
                },
                {
                    "candidate_name": "mapped_fixed_y_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 1,
                    "x_m": 1.0,
                    "x_over_l": 0.5,
                    "candidate_transport_density_value_per_m": -2.0,
                    "stokes_body_forward_density_value_per_m": -4.0,
                },
                {
                    "candidate_name": "mapped_fixed_y_central",
                    "source_row": 0,
                    "coefficient": "B53",
                    "row_family": "pitch_row_N5_m5",
                    "column_family": "heave_radiation",
                    "station_index": 2,
                    "x_m": 2.0,
                    "x_over_l": 1.0,
                    "candidate_transport_density_value_per_m": -3.0,
                    "stokes_body_forward_density_value_per_m": -6.0,
                },
            ]
        )

        summary = _ma2005_row_measure_mapping_candidate_summary(detail, "synthetic")
        overview = _ma2005_row_measure_mapping_candidate_overview(summary, "synthetic")

        closed = summary[
            summary["candidate_name"].eq("mapped_normalized_arclength_central")
        ].iloc[0]
        reversed_sign = summary[summary["candidate_name"].eq("mapped_fixed_y_central")].iloc[0]
        self.assertEqual(closed["diagnostic_conclusion"], "mapping_candidate_closes_negative_stokes_target")
        self.assertAlmostEqual(float(closed["candidate_negative_stokes_residual_norm"]), 0.0)
        self.assertEqual(reversed_sign["diagnostic_conclusion"], "mapping_candidate_reverses_expected_sign")
        self.assertEqual(
            overview[overview["candidate_name"].eq("mapped_normalized_arclength_central")][
                "diagnostic_conclusion"
            ].iloc[0],
            "mapping_candidate_closes_all_rows",
        )
        self.assertEqual(
            overview[overview["candidate_name"].eq("mapped_fixed_y_central")][
                "diagnostic_conclusion"
            ].iloc[0],
            "mapping_candidate_excluded_by_expected_sign_reversal",
        )

    def test_row_measure_transport_exposes_heave_projection_leibniz_endpoint_candidate(self):
        x_m = np.asarray([0.0, 1.0, 2.0], dtype=float)
        station_nodes = [
            np.asarray([-1.0, 0.0, 1.0], dtype=float),
            np.asarray([-2.0, 0.0, 2.0], dtype=float),
            np.asarray([-4.0, 0.0, 4.0], dtype=float),
        ]
        bodies = tuple(
            InnerDomainPanelGeometry(
                mid_y_m=0.5 * (nodes[:-1] + nodes[1:]),
                mid_z_down_m=np.asarray([0.0, 0.0], dtype=float),
                normal_y=np.asarray([0.0, 0.0], dtype=float),
                normal_z=np.asarray([-1.0, -1.0], dtype=float),
                length_m=np.diff(nodes),
                node_y_m=nodes,
                node_z_down_m=np.asarray([0.0, 0.0, 0.0], dtype=float),
            )
            for nodes in station_nodes
        )
        validity = ValidityReport.unvalidated("synthetic section solution")

        def solution(phi0: complex, phi1: complex) -> MatchedSectionSolution:
            return MatchedSectionSolution(
                body_potential=np.asarray([phi0, phi1], dtype=complex),
                inner_free_surface_normal_derivative=np.zeros(0, dtype=complex),
                control_potential=np.zeros(0, dtype=complex),
                control_normal_derivative=np.zeros(0, dtype=complex),
                validity=validity,
            )

        heave_solutions = tuple(solution(1.0 + station, 2.0 + station) for station in range(3))
        pitch_solutions = tuple(solution(3.0 + station, 4.0 + station) for station in range(3))

        result = compute_heave_pitch_row_measure_transport_force_matrix(
            x_m,
            bodies,
            heave_solutions,
            pitch_solutions,
            forward_speed_mps=2.0,
            lever_arms_m=np.asarray([1.0, 1.0, 1.0], dtype=float),
        )

        names = list(result.candidate_names)
        self.assertIn("heave_projection_leibniz_endpoint_flux_pitch_current", names)
        endpoint_index = names.index("heave_projection_leibniz_endpoint_flux_pitch_current")
        current_index = names.index("current_equal_panel_x_derivative")
        endpoint_gradient = result.candidate_pressure_row_measure_x_gradient_by_station[endpoint_index]
        current_gradient = result.candidate_pressure_row_measure_x_gradient_by_station[current_index]

        expected_endpoint = np.asarray([[0.5, 0.5], [1.5, 1.5], [2.5, 2.5]], dtype=float)
        self.assertTrue(np.allclose(endpoint_gradient[:, 0, :], expected_endpoint))
        self.assertTrue(np.allclose(endpoint_gradient[:, 1, :], current_gradient[:, 1, :]))
        self.assertEqual(result.validity.status, "a1_eq31_row_measure_transport_diagnostic_not_hard_gate")

    def test_ma2005_endpoint_force_route_candidate_audit_keeps_candidate_diagnostic_only(self):
        matrices = {
            "heave_pitch_time_derivative_force_matrices": np.zeros((1, 2, 2), dtype=complex),
            "heave_pitch_forward_speed_force_matrices": np.zeros((1, 2, 2), dtype=complex),
            "heave_pitch_end_term_force_matrices": np.zeros((1, 2, 2), dtype=complex),
            "heave_pitch_stokes_body_forward_speed_force_matrices": np.zeros((1, 2, 2), dtype=complex),
            "heave_pitch_row_measure_transport_force_matrices": np.zeros((1, 2, 2), dtype=complex),
            "heave_pitch_row_measure_transport_force_matrices_mapping_candidate_"
            "heave_projection_leibniz_endpoint_flux_pitch_current": np.zeros((1, 2, 2), dtype=complex),
        }
        matrices[
            "heave_pitch_row_measure_transport_force_matrices_mapping_candidate_"
            "heave_projection_leibniz_endpoint_flux_pitch_current"
        ][0, 0, 0] = -2.0j
        hydro = SimpleNamespace(contribution_breakdown=matrices)

        rows = _ma2005_endpoint_force_route_candidate_rows(
            hydro,
            benchmark="synthetic",
            source_row=0,
            hull="wigley",
            speed_case="Fn0.4",
            omega_e_sqrt_l_over_g=1.0,
            coefficient="B33",
            prefix="B",
            row_idx=2,
            col_idx=2,
            normalization_scale=1.0,
            normalization="ma2005",
            omega_rad_s=1.0,
            reference_value=2.0,
            tolerance=0.15,
            current_default_value=0.0,
            current_default_gate_error_ratio=10.0,
        )

        self.assertGreater(len(rows), 0)
        endpoint_plus_end = [
            row
            for row in rows
            if row["force_assembly_route"] == "time_plus_pressure_gradient_plus_endpoint_flux_plus_end"
        ][0]
        self.assertEqual(endpoint_plus_end["candidate_status"], "PASS")
        self.assertEqual(endpoint_plus_end["candidate_default_gate_eligible"], "false")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_endpoint_force_route_candidate_audit(
                rows,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_endpoint_force_route_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_endpoint_force_route_candidate_summary.csv").exists())
            self.assertFalse(detail.empty)
            self.assertFalse(summary.empty)
            self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_distributed_geometry_component_route_audit_tests_formula_components(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "reference_value": 2.0,
                    "computed_value": 0.0,
                    "gate_error_ratio": 10.0,
                    "matched_time_derivative_component_value": 0.0,
                    "matched_pressure_gradient_component_value": 0.0,
                    "matched_end_term_component_value": 0.0,
                }
            ]
        )
        formula = pd.DataFrame(
            [
                {
                    "source_row": 0,
                    "coefficient": "B33",
                    "eq31_transport_integral_value": 2.0,
                    "normal_variation_integral_value": 1.0,
                    "panel_length_variation_integral_value": 0.25,
                    "product_rule_residual_integral_value": 0.0,
                    "section_interior_panel_integral_value": 1.5,
                    "eq32_boundary_proxy_integral_value": 0.5,
                    "eq31_minus_eq32_proxy_integral_value": 1.5,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_distributed_geometry_component_route_audit(
                comparison,
                formula,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_distributed_geometry_component_route_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_distributed_geometry_component_route_summary.csv").exists())
            full_route = detail[detail["force_assembly_route"].eq("plus_full_eq31_transport")].iloc[0]
            self.assertEqual(full_route["candidate_status"], "PASS")
            self.assertEqual(full_route["candidate_default_gate_eligible"], "false")
            self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_pressure_gradient_replacement_scale_audit_stays_diagnostic_only(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "reference_value": 2.0,
                    "computed_value": 0.0,
                    "matched_time_derivative_component_value": 0.0,
                    "matched_pressure_gradient_component_value": 1.0,
                    "matched_end_term_component_value": 0.0,
                },
                {
                    "coefficient": "A35",
                    "reference_value": 6.0,
                    "computed_value": 0.0,
                    "matched_time_derivative_component_value": 0.0,
                    "matched_pressure_gradient_component_value": 1.0,
                    "matched_end_term_component_value": 0.0,
                },
                {
                    "coefficient": "B35",
                    "reference_value": -4.0,
                    "computed_value": 0.0,
                    "matched_time_derivative_component_value": 0.0,
                    "matched_pressure_gradient_component_value": 1.0,
                    "matched_end_term_component_value": 0.0,
                },
            ]
        )
        formula = pd.DataFrame(
            [
                {"source_row": 0, "coefficient": "B33", "eq31_transport_integral_value": 2.0},
                {"source_row": 1, "coefficient": "A35", "eq31_transport_integral_value": 2.0},
                {"source_row": 2, "coefficient": "B35", "eq31_transport_integral_value": 2.0},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pressure_gradient_replacement_scale_audit(
                comparison,
                formula,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_pressure_gradient_replacement_scale_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pressure_gradient_replacement_scale_summary.csv").exists())
            self.assertEqual(len(detail), 3)
            self.assertEqual(int(summary.iloc[0]["row_count"]), 3)
            self.assertEqual(
                summary.iloc[0]["diagnostic_conclusion"],
                "pressure_gradient_replacement_requires_nonuniform_alpha",
            )
            self.assertEqual(summary.iloc[0]["candidate_default_gate_eligible"], "false")
            self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_row_measure_zero_mi_boundary_audit_covers_heave_row_coefficients(self):
        station_count = 3
        row_gradient = [
            [
                [[1.0, 2.0, 1.0], [0.0, 0.0, 0.0]],
                [[1.0, 2.0, 1.0], [0.0, 0.0, 0.0]],
                [[1.0, 2.0, 1.0], [0.0, 0.0, 0.0]],
            ]
        ]
        transport_density = [
            [
                [[4j, 8.0 + 4j], [0j, 0j]],
                [[4j, 8.0 + 4j], [0j, 0j]],
                [[4j, 8.0 + 4j], [0j, 0j]],
            ]
        ]
        zero_transport_density = [
            [
                [[0j, 0j], [0j, 0j]],
                [[0j, 0j], [0j, 0j]],
                [[0j, 0j], [0j, 0j]],
            ]
        ]
        hydro = SimpleNamespace(
            contribution_breakdown={
                "station_x_m": [[0.0, 1.0, 2.0]],
                "station_x_over_l": [[0.0, 0.5, 1.0]],
                "heave_pitch_row_measure_transport_force_density_by_station": transport_density,
                "heave_pitch_stokes_body_forward_speed_force_density_by_station": zero_transport_density,
                "heave_pitch_pressure_row_measure_x_gradient_by_station": row_gradient,
                "heave_pitch_stokes_m_measure_by_station": [
                    [
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                    ]
                ],
                "body_panel_normal_z_by_station": [
                    [[-1.0, -1.0, -1.0], [-1.0, -1.0, -1.0], [-1.0, -1.0, -1.0]]
                ],
                "body_panel_length_by_station": [
                    [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
                ],
                "heave_body_potential_by_station": [
                    [[1j, 1j, 1j], [1j, 1j, 1j], [1j, 1j, 1j]]
                ],
                "pitch_body_potential_by_station": [
                    [
                        [2.0 + 1j, 2.0 + 1j, 2.0 + 1j],
                        [2.0 + 1j, 2.0 + 1j, 2.0 + 1j],
                        [2.0 + 1j, 2.0 + 1j, 2.0 + 1j],
                    ]
                ],
                "heave_pitch_row_measure_transport_mapping_candidate_names": [
                    "mapped_normalized_y_central",
                    "mapped_normalized_arclength_central",
                ],
                "heave_pitch_row_measure_transport_force_density_mapping_candidate_mapped_normalized_y_central": zero_transport_density,
                "heave_pitch_row_measure_transport_force_density_mapping_candidate_mapped_normalized_arclength_central": zero_transport_density,
            }
        )

        all_rows = []
        for coefficient, prefix, col_idx in [
            ("B33", "B", 2),
            ("A35", "A", 4),
            ("B35", "B", 4),
        ]:
            rows = _ma2005_row_measure_zero_mi_boundary_audit_rows(
                hydro,
                benchmark="synthetic",
                source_row=0,
                hull="wigley_iii",
                speed_case="Fn0.4",
                omega_e_sqrt_l_over_g=1.0,
                coefficient=coefficient,
                prefix=prefix,
                row_idx=2,
                col_idx=col_idx,
                normalization_scale=1.0,
                omega_rad_s=1.0,
                rho_water_kg_m3=1.0,
                forward_speed_mps=1.0,
                reference_value=0.0,
            )
            self.assertEqual(len(rows), station_count)
            all_rows.extend(rows)

        detail = pd.DataFrame(all_rows)
        summary = _ma2005_row_measure_zero_mi_boundary_summary(detail, "synthetic")

        self.assertEqual(set(detail["coefficient"].astype(str)), {"B33", "A35", "B35"})
        self.assertEqual(set(summary["coefficient"].astype(str)), {"B33", "A35", "B35"})
        for column in [
            "zero_mi_target_value_per_m",
            "row_measure_transport_density_value_per_m",
            "stokes_body_forward_density_value_per_m",
            "normal_variation_density_value_per_m",
            "panel_length_variation_density_value_per_m",
            "lever_variation_density_value_per_m",
            "product_rule_residual_density_value_per_m",
            "waterline_contour_density_value_per_m",
            "boundary_density_value_per_m",
            "section_endpoint_panel_density_value_per_m",
            "section_interior_panel_density_value_per_m",
            "best_mapping_candidate_name",
            "mapping_residual_density_value_per_m",
            "dominant_gradient_component",
            "candidate_default_gate_eligible",
            "path_diagnostic_status",
            "eq31_row_measure_transport_density_value_per_m",
            "eq32_stokes_body_density_value_per_m",
            "eq32_boundary_proxy_density_value_per_m",
            "eq32_stokes_plus_boundary_proxy_density_value_per_m",
            "eq31_minus_eq32_boundary_proxy_density_value_per_m",
        ]:
            self.assertIn(column, detail.columns)
        for column in [
            "zero_mi_residual_integral_value",
            "normal_variation_integral_value",
            "panel_length_variation_integral_value",
            "lever_variation_integral_value",
            "product_rule_residual_integral_value",
            "waterline_contour_integral_value",
            "boundary_integral_value",
            "section_endpoint_panel_abs_share",
            "waterline_contour_abs_share",
            "boundary_abs_share",
            "residual_abs_centroid_x_over_l",
            "decomposition_closure_residual",
            "residual_source_class",
            "diagnostic_conclusion",
            "candidate_default_gate_eligible",
            "path_diagnostic_status",
            "eq31_row_measure_transport_integral_value",
            "eq32_stokes_body_integral_value",
            "eq32_boundary_proxy_integral_value",
            "eq32_stokes_plus_boundary_proxy_integral_value",
            "eq31_minus_eq32_boundary_proxy_integral_value",
            "eq31_eq32_boundary_proxy_residual_norm",
            "eq31_eq32_boundary_proxy_residual_abs_centroid_x_over_l",
        ]:
            self.assertIn(column, summary.columns)
        self.assertTrue(
            detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all()
        )
        self.assertTrue(detail["path_diagnostic_status"].astype(str).eq("INFO").all())
        self.assertTrue(
            summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all()
        )
        self.assertTrue(summary["path_diagnostic_status"].astype(str).eq("INFO").all())
        self.assertTrue(summary["diagnostic_conclusion"].astype(str).str.contains("localized").all())
        self.assertTrue(
            pd.to_numeric(summary["eq31_eq32_boundary_proxy_residual_norm"], errors="coerce").notna().all()
        )
        self.assertAlmostEqual(
            float(pd.to_numeric(detail["lever_variation_density_value_per_m"], errors="coerce").abs().max()),
            0.0,
        )
        self.assertLess(
            float(pd.to_numeric(summary["decomposition_closure_residual"], errors="coerce").abs().max()),
            1e-12,
        )

    def test_ma2005_formula_transport_identity_audit_is_station_panel_level(self):
        x_values = [0.0, 1.0, 2.0]
        heave_row = [
            [1.0, 2.0, 4.0],
            [2.0, 4.0, 8.0],
            [3.0, 6.0, 12.0],
        ]
        row_gradient = [
            [
                [[1.0, 2.0, 4.0], [0.0, 0.0, 0.0]],
                [[1.0, 2.0, 4.0], [0.0, 0.0, 0.0]],
                [[1.0, 2.0, 4.0], [0.0, 0.0, 0.0]],
            ]
        ]
        hydro = SimpleNamespace(
            contribution_breakdown={
                "station_x_m": [x_values],
                "station_x_over_l": [[0.0, 0.5, 1.0]],
                "heave_pitch_pressure_row_measure_by_station": [
                    [
                        [heave_row[0], [0.0, 0.0, 0.0]],
                        [heave_row[1], [0.0, 0.0, 0.0]],
                        [heave_row[2], [0.0, 0.0, 0.0]],
                    ]
                ],
                "heave_pitch_pressure_row_measure_x_gradient_by_station": row_gradient,
                "heave_pitch_stokes_m_measure_by_station": [
                    [
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                    ]
                ],
                "body_panel_normal_z_by_station": [
                    [
                        [-1.0, -2.0, -4.0],
                        [-2.0, -4.0, -8.0],
                        [-3.0, -6.0, -12.0],
                    ]
                ],
                "body_panel_length_by_station": [
                    [
                        [1.0, 1.0, 1.0],
                        [1.0, 1.0, 1.0],
                        [1.0, 1.0, 1.0],
                    ]
                ],
                "heave_body_potential_by_station": [
                    [
                        [-1j, -1j, -1j],
                        [-1j, -1j, -1j],
                        [-1j, -1j, -1j],
                    ]
                ],
                "pitch_body_potential_by_station": [
                    [
                        [1.0, 1.0, 1.0],
                        [1.0, 1.0, 1.0],
                        [1.0, 1.0, 1.0],
                    ]
                ],
            }
        )
        rows = _ma2005_formula_transport_identity_rows(
            hydro,
            benchmark="synthetic",
            source_row=0,
            hull="wigley_iii",
            speed_case="Fn0.4",
            omega_e_sqrt_l_over_g=1.0,
            coefficient="B33",
            prefix="B",
            row_idx=2,
            col_idx=2,
            normalization_scale=1.0,
            omega_rad_s=1.0,
            rho_water_kg_m3=1.0,
            forward_speed_mps=1.0,
            reference_value=1.0,
        )
        self.assertEqual(len(rows), 9)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 1.0,
                        "computed_value": 9.0,
                        "status": "FAIL",
                        "gate_error_ratio": 10.0,
                    }
                ]
            )
            detail, summary = _write_ma2005_formula_transport_identity_audit(
                rows,
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_formula_transport_identity_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_formula_transport_identity_summary.csv").exists())
        self.assertEqual(int(summary["station_count"].iloc[0]), 3)
        self.assertEqual(int(summary["panel_count"].iloc[0]), 3)
        self.assertIn("panel_index", detail.columns)
        self.assertIn("symbol_convention", detail.columns)
        self.assertIn("longitudinal_end_station_proxy_density_value_per_m", detail.columns)
        self.assertIn("longitudinal_endpoint_state_panel_value", detail.columns)
        self.assertIn("longitudinal_end_station_abs_share", summary.columns)
        self.assertIn("longitudinal_endpoint_state_integral_value", summary.columns)
        self.assertGreater(float(summary["interior_distributed_abs_share"].iloc[0]), 0.0)
        self.assertGreater(float(summary["longitudinal_end_station_abs_share"].iloc[0]), 0.0)
        self.assertNotEqual(float(summary["longitudinal_endpoint_state_integral_value"].iloc[0]), 0.0)
        self.assertLess(float(summary["formula_decomposition_closure_residual_norm"].iloc[0]), 1e-12)
        self.assertEqual(summary["dominant_formula_component"].iloc[0], "normal_variation")
        self.assertEqual(
            summary["candidate_default_gate_eligible"].astype(str).str.lower().iloc[0],
            "false",
        )

    def test_ma2005_eq31_product_rule_endpoint_requirement_audit_keeps_gap_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 2.1,
                        "computed_value": 9.18,
                        "status": "FAIL",
                        "gate_error_ratio": 22.0,
                        "matched_pressure_gradient_component_value": 8.0,
                        "matched_stokes_body_forward_component_value": 0.0,
                        "matched_end_term_component_value": 0.5,
                    }
                ]
            )
            formula_summary = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "eq31_transport_integral_value": -7.0,
                        "eq32_boundary_proxy_integral_value": -0.25,
                        "longitudinal_end_station_proxy_integral_value": 0.2,
                    }
                ]
            )

            detail, summary = _write_ma2005_eq31_product_rule_endpoint_requirement_audit(
                comparison,
                formula_summary,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_eq31_product_rule_endpoint_requirement_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_eq31_product_rule_endpoint_requirement_summary.csv").exists())
            self.assertEqual(len(detail), 1)
            row = detail.iloc[0]
            self.assertAlmostEqual(float(row["product_rule_required_endpoint_value"]), 1.0)
            self.assertAlmostEqual(float(row["direct_minus_eq32_reported_value"]), 7.5)
            self.assertAlmostEqual(float(row["required_reported_end_scale_for_product_rule"]), 2.0)
            self.assertEqual(
                row["endpoint_requirement_class"],
                "required_endpoint_not_explained_by_current_end_or_boundary_proxy",
            )
            self.assertEqual(row["diagnostic_conclusion"], "eq31_product_rule_endpoint_requirement_open")
            self.assertEqual(str(row["candidate_default_gate_eligible"]).lower(), "false")
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "eq31_product_rule_endpoint_requirement_open_for_all_zero_m3_rows",
            )

    def test_ma2005_eq31_product_rule_endpoint_requirement_audit_detects_longitudinal_endpoint_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 2.1,
                        "computed_value": 9.18,
                        "status": "FAIL",
                        "gate_error_ratio": 22.0,
                        "matched_pressure_gradient_component_value": 8.0,
                        "matched_stokes_body_forward_component_value": 0.0,
                        "matched_end_term_component_value": 0.5,
                    }
                ]
            )
            formula_summary = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "eq31_transport_integral_value": -7.0,
                        "eq32_boundary_proxy_integral_value": -0.25,
                        "longitudinal_end_station_proxy_integral_value": 0.2,
                        "aft_endpoint_state_integral_value": -0.5,
                        "bow_endpoint_state_integral_value": 1.5,
                        "longitudinal_endpoint_state_integral_value": 1.0,
                    }
                ]
            )

            detail, summary = _write_ma2005_eq31_product_rule_endpoint_requirement_audit(
                comparison,
                formula_summary,
                tmp_path,
                "synthetic",
            )

            row = detail.iloc[0]
            self.assertAlmostEqual(float(row["product_rule_required_endpoint_value"]), 1.0)
            self.assertAlmostEqual(float(row["formula_longitudinal_endpoint_state_value"]), 1.0)
            self.assertAlmostEqual(float(row["product_rule_minus_longitudinal_endpoint_state_value"]), 0.0)
            self.assertEqual(
                row["endpoint_requirement_class"],
                "longitudinal_endpoint_state_same_scale_as_required_endpoint",
            )
            self.assertEqual(
                row["diagnostic_conclusion"],
                "eq31_product_rule_endpoint_requirement_nearly_closed_by_longitudinal_state",
            )
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "eq31_product_rule_endpoint_requirement_closed_by_longitudinal_state_for_all_zero_m3_rows",
            )

    def test_ma2005_conservative_product_derivative_audit_keeps_gate_separate_from_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 2.1,
                        "computed_value": 9.18,
                        "status": "FAIL",
                        "gate_error_ratio": 22.0,
                        "matched_time_derivative_component_value": 0.0,
                    }
                ]
            )
            endpoint_detail = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "direct_pressure_gradient_component_value": 8.0,
                        "row_measure_transport_integral_value": -7.0,
                        "formula_longitudinal_endpoint_state_value": 1.0,
                        "reported_end_contour_component_value": 0.5,
                    }
                ]
            )

            detail, summary = _write_ma2005_conservative_product_derivative_audit(
                comparison,
                endpoint_detail,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_conservative_product_derivative_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_conservative_product_derivative_summary.csv").exists())
            row = detail.iloc[0]
            self.assertAlmostEqual(float(row["conservative_required_direct_pressure_gradient_value"]), 8.0)
            self.assertAlmostEqual(float(row["split_product_rule_residual_value"]), 0.0)
            self.assertEqual(
                row["diagnostic_conclusion"],
                "conservative_product_derivative_closes_but_gate_remains_open",
            )
            self.assertEqual(str(row["candidate_default_gate_eligible"]).lower(), "false")
            self.assertEqual(int(summary["conservative_eq31_pass_count"].iloc[0]), 0)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "conservative_product_derivative_improves_all_zero_m3_rows_but_gate_remains_open",
            )

    def test_ma2005_mapping_conservative_product_derivative_audit_ranks_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 2.1,
                        "computed_value": 9.18,
                        "status": "FAIL",
                        "gate_error_ratio": 22.0,
                        "matched_time_derivative_component_value": 0.0,
                    }
                ]
            )
            endpoint_detail = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "direct_pressure_gradient_component_value": 8.0,
                        "formula_longitudinal_endpoint_state_value": 1.0,
                        "reported_end_contour_component_value": 0.5,
                    }
                ]
            )
            mapping_summary = pd.DataFrame(
                [
                    {
                        "candidate_name": "mapped_fixed_y_central",
                        "source_row": 1,
                        "coefficient": "B33",
                        "candidate_transport_integral_value": -1.1,
                    },
                    {
                        "candidate_name": "mapped_normalized_y_central",
                        "source_row": 1,
                        "coefficient": "B33",
                        "candidate_transport_integral_value": -7.0,
                    },
                ]
            )

            detail, summary = _write_ma2005_mapping_conservative_product_derivative_audit(
                comparison,
                endpoint_detail,
                mapping_summary,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_mapping_conservative_product_derivative_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_mapping_conservative_product_derivative_summary.csv").exists())
            self.assertEqual(set(detail["candidate_name"]), {"mapped_fixed_y_central", "mapped_normalized_y_central"})
            fixed = summary[summary["candidate_name"].eq("mapped_fixed_y_central")].iloc[0]
            normalized = summary[summary["candidate_name"].eq("mapped_normalized_y_central")].iloc[0]
            self.assertEqual(int(fixed["candidate_conservative_eq31_pass_count"]), 1)
            self.assertLess(
                float(fixed["best_route_max_gate_error_ratio"]),
                float(normalized["best_route_max_gate_error_ratio"]),
            )
            self.assertEqual(
                str(fixed["candidate_default_gate_eligible"]).lower(),
                "false",
            )
            self.assertEqual(
                fixed["diagnostic_conclusion"],
                "mapping_conservative_product_derivative_candidate_closes_subset",
            )

    def test_ma2005_heave_row_ab_pairing_audit_marks_frequency_mismatch_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "A33",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "speed_case": "Fn0.4",
                        "gate_error_ratio": 1.0,
                        "status": "FAIL",
                    },
                    {
                        "coefficient": "B33",
                        "omega_e_sqrt_l_over_g": 2.0,
                        "speed_case": "Fn0.4",
                        "gate_error_ratio": 22.0,
                        "status": "FAIL",
                    },
                    {
                        "coefficient": "A35",
                        "omega_e_sqrt_l_over_g": 1.5,
                        "speed_case": "Fn0.4",
                        "gate_error_ratio": 41.0,
                        "status": "FAIL",
                    },
                    {
                        "coefficient": "B35",
                        "omega_e_sqrt_l_over_g": 2.5,
                        "speed_case": "Fn0.4",
                        "gate_error_ratio": 164.0,
                        "status": "FAIL",
                    },
                ]
            )
            formula = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "eq31_eq32_proxy_residual_norm": 0.88,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                    {
                        "coefficient": "A35",
                        "eq31_eq32_proxy_residual_norm": 0.88,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                    {
                        "coefficient": "B35",
                        "eq31_eq32_proxy_residual_norm": 0.90,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                ]
            )

            detail, summary = _write_ma2005_heave_row_ab_pairing_audit(
                comparison,
                formula,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_heave_row_ab_pairing_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_heave_row_ab_pairing_summary.csv").exists())
            targets = detail[detail["zero_m3_transport_target_row"].astype(str).eq("true")]
            self.assertEqual(set(targets["coefficient"].astype(str)), {"B33", "A35", "B35"})
            self.assertTrue(targets["pair_status"].astype(str).eq("frequency_mismatch_ab_pair").all())
            self.assertTrue(targets["complex_force_closure_evaluable"].astype(str).eq("false").all())
            row = summary.iloc[0]
            self.assertEqual(int(row["target_row_count"]), 3)
            self.assertEqual(int(row["frequency_mismatch_pair_count"]), 3)
            self.assertEqual(int(row["complex_evaluable_target_count"]), 0)
            self.assertEqual(
                row["diagnostic_conclusion"],
                "heave_row_zero_m3_targets_lack_same_frequency_ab_pairs",
            )
            self.assertEqual(row["candidate_default_gate_eligible"], "false")

    def test_ma2005_fixed_control_surface_transport_gap_audit_flags_moving_panel_derivative(self):
        formula_summary = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "row_family": "heave_row_N3_m3",
                    "column_family": "heave_radiation",
                    "current_gate_error_ratio": 20.0,
                    "formula_decomposition_closure_residual_norm": 1.0e-12,
                    "eq31_eq32_proxy_residual_norm": 0.88,
                    "interior_distributed_abs_share": 0.88,
                    "normal_variation_abs_share": 0.79,
                    "panel_length_variation_abs_share": 0.21,
                    "boundary_proxy_abs_share": 0.12,
                    "longitudinal_end_station_abs_share": 0.03,
                    "dominant_formula_component": "interior_distributed_transport",
                }
            ]
        )
        zero_summary = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "waterline_contour_abs_share": 0.12,
                    "configured_end_station_abs_share": 0.02,
                    "residual_abs_centroid_x_over_l": 0.26,
                    "peak_abs_residual_x_over_l": 0.075,
                    "dominant_decomposition_component": "normal_variation",
                    "residual_source_class": "panel_normal_variation_dominant",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_fixed_control_surface_transport_gap_audit(
                formula_summary,
                zero_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_fixed_control_surface_transport_gap_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_fixed_control_surface_transport_gap_summary.csv").exists())

        self.assertEqual(detail["blocker_status"].iloc[0], "OPEN")
        self.assertEqual(
            detail["diagnostic_conclusion"].iloc[0],
            "moving_hull_panel_derivative_dominates_not_fixed_control_surface_closure",
        )
        self.assertEqual(int(summary["open_blocker_count"].iloc[0]), 1)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "fixed_control_surface_transport_gap_confirmed",
        )
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_zero_m3_geometry_transport_blocker_trace_collects_route_exclusions(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "status": "FAIL",
                    "gate_error_ratio": 22.0,
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A35",
                    "status": "FAIL",
                    "gate_error_ratio": 41.0,
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B35",
                    "status": "FAIL",
                    "gate_error_ratio": 164.0,
                    "provider_route": "matched_bie_station_sweep",
                },
            ]
        )
        formula_summary = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "formula_decomposition_closure_residual_norm": 1.0e-12,
                    "eq31_eq32_proxy_residual_norm": proxy,
                    "interior_distributed_abs_share": 0.88,
                    "normal_variation_abs_share": 0.79,
                    "boundary_proxy_abs_share": 0.12,
                }
                for coefficient, proxy in [("B33", 0.88), ("A35", 0.88), ("B35", 0.90)]
            ]
        )
        fixed_summary = pd.DataFrame(
            [
                {
                    "open_blocker_count": 3,
                    "diagnostic_conclusion": "fixed_control_surface_transport_gap_confirmed",
                }
            ]
        )
        zero_summary = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "peak_abs_residual_x_over_l": 0.075,
                    "residual_abs_centroid_x_over_l": centroid,
                    "residual_source_class": "panel_normal_variation_dominant",
                }
                for coefficient, centroid in [("B33", 0.26), ("A35", 0.26), ("B35", 0.28)]
            ]
        )
        scale_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "add_panel_normal_variation",
                    "required_scale_max_over_min_abs": 6.4,
                    "unit_pass_count": 0,
                    "median_scale_pass_count": 1,
                    "max_gate_error_ratio": 113.0,
                }
            ]
        )
        direction_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "current_equal_panel_x_derivative",
                    "closed_row_count": 2,
                    "median_candidate_negative_stokes_residual_norm": 1.6,
                    "diagnostic_conclusion": "candidate_excluded_by_zero_mi_rows_and_scale_mismatch",
                },
                {
                    "candidate_name": "reversed_x_derivative",
                    "closed_row_count": 2,
                    "median_candidate_negative_stokes_residual_norm": 1.9,
                    "diagnostic_conclusion": "candidate_excluded_by_expected_sign_reversal",
                },
            ]
        )
        force_route = pd.DataFrame(
            [
                {
                    "force_assembly_route": "eq31_pressure_gradient_plus_row_measure_transport",
                    "pass_count": 0,
                    "max_gate_error_ratio": 126.0,
                },
                {
                    "force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    "pass_count": 0,
                    "max_gate_error_ratio": 164.0,
                },
            ]
        )
        end_summary = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "end_contour_effect_is_mixed_after_row_measure",
                    "required_end_scale_spread": 13.9,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_zero_m3_geometry_transport_blocker_trace(
                comparison,
                formula_summary,
                fixed_summary,
                zero_summary,
                scale_summary,
                direction_summary,
                force_route,
                end_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_zero_m3_geometry_transport_blocker_trace.csv").exists())
            self.assertTrue((tmp_path / "synthetic_zero_m3_geometry_transport_blocker_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 5)
        self.assertFalse(detail["supports_default_geometry_transport_change"].astype(bool).any())
        self.assertTrue(detail["blocks_default_geometry_transport_change"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_fail_count"]), 3)
        self.assertEqual(int(row["supporting_default_geometry_transport_change_count"]), 0)
        self.assertEqual(str(row["best_force_route"]), "eq31_pressure_gradient_plus_row_measure_transport")
        self.assertEqual(int(row["best_force_route_pass_count"]), 0)
        self.assertEqual(str(row["best_direction_candidate"]), "current_equal_panel_x_derivative")
        self.assertEqual(int(row["end_contour_mixed_interaction_count"]), 1)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "zero_m3_geometry_transport_gap_localized_to_moving_normal_variation_no_default_route",
        )
        self.assertIn("fixed-control-surface", row["next_required_evidence"])
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_heave_projection_measure_identity_separates_moving_mesh_and_leibniz_flux(self):
        x = np.asarray([[0.0, 1.0, 2.0]], dtype=float)
        x_over_l = np.asarray([[0.0, 0.5, 1.0]], dtype=float)
        station_count = 3
        panel_count = 2
        node_y = np.asarray(
            [
                [
                    [0.0, 1.0, 2.0],
                    [0.0, 1.2, 2.6],
                    [0.0, 1.4, 3.2],
                ]
            ],
            dtype=float,
        )
        delta_y = np.diff(node_y, axis=2)
        normal_z = -np.ones((1, station_count, panel_count), dtype=float)
        panel_length = delta_y.copy()
        row_measure = np.zeros((1, station_count, 2, panel_count), dtype=float)
        row_gradient = np.zeros_like(row_measure)
        row_measure[0, :, 0, :] = delta_y[0]
        row_gradient[0, :, 0, :] = np.gradient(delta_y[0], x[0], axis=0, edge_order=2)
        pitch_phi = np.asarray([[[10.0 + 0j, 1.0 + 0j]] * station_count], dtype=complex)
        heave_phi = np.ones_like(pitch_phi)
        hydro = SimpleNamespace(
            contribution_breakdown={
                "station_x_m": x,
                "station_x_over_l": x_over_l,
                "heave_pitch_pressure_row_measure_by_station": row_measure,
                "heave_pitch_pressure_row_measure_x_gradient_by_station": row_gradient,
                "body_panel_node_y_by_station": node_y,
                "body_panel_delta_y_by_station": delta_y,
                "body_panel_normal_z_by_station": normal_z,
                "body_panel_length_by_station": panel_length,
                "heave_body_potential_by_station": heave_phi,
                "pitch_body_potential_by_station": pitch_phi,
            }
        )
        rows = _ma2005_heave_projection_measure_identity_rows(
            hydro,
            benchmark="synthetic",
            source_row=2,
            hull="synthetic",
            speed_case="Fn",
            omega_e_sqrt_l_over_g=1.0,
            coefficient="A35",
            prefix="A",
            row_idx=2,
            col_idx=4,
            normalization_scale=1.0,
            omega_rad_s=1.0,
            rho_water_kg_m3=1.0,
            forward_speed_mps=1.0,
            reference_value=-0.2,
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_heave_projection_measure_identity_audit(
                rows,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_heave_projection_measure_identity_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_heave_projection_measure_identity_summary.csv").exists())

        self.assertEqual(len(detail), station_count)
        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertEqual(row["projection_orientation"], "N3_ds_equals_delta_y")
        self.assertLess(float(row["max_projection_identity_residual_norm"]), 1e-12)
        self.assertLess(float(row["max_normal_length_identity_residual_norm"]), 1e-12)
        self.assertLess(float(row["max_row_gradient_projection_residual_norm"]), 1e-12)
        self.assertGreater(abs(float(row["moving_minus_leibniz_boundary_integral_value"])), 1.0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "heave_row_measure_is_projection_but_current_derivative_is_moving_mesh_not_fixed_control_surface",
        )
        self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).eq("false").all())
        self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).eq("false").all())

    def test_ma2005_source_ranking_audits_write_compact_acceptance_tables(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "status": "FAIL",
                    "gate_error_ratio": 20.0,
                    "provider_route": "matched_bie_station_sweep",
                    "matched_time_derivative_component_value": 9.0,
                    "matched_pressure_gradient_component_value": 1.0,
                    "matched_stokes_body_forward_component_value": 0.5,
                    "matched_end_term_component_value": 0.1,
                },
                {
                    "coefficient": "A53",
                    "reference_value": 1.0,
                    "computed_value": 8.0,
                    "status": "FAIL",
                    "gate_error_ratio": 18.0,
                    "provider_route": "matched_bie_station_sweep",
                    "matched_time_derivative_component_value": 7.0,
                    "matched_pressure_gradient_component_value": 0.5,
                    "matched_stokes_body_forward_component_value": 0.2,
                    "matched_end_term_component_value": 0.1,
                },
                {
                    "coefficient": "A55",
                    "reference_value": 1.0,
                    "computed_value": 5.0,
                    "status": "FAIL",
                    "gate_error_ratio": 12.0,
                    "provider_route": "matched_bie_station_sweep",
                    "matched_time_derivative_component_value": 0.5,
                    "matched_pressure_gradient_component_value": 3.0,
                    "matched_stokes_body_forward_component_value": 2.0,
                    "matched_end_term_component_value": 1.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 1.0,
                    "computed_value": 6.0,
                    "status": "FAIL",
                    "gate_error_ratio": 13.0,
                    "provider_route": "matched_bie_station_sweep",
                    "matched_time_derivative_component_value": 0.5,
                    "matched_pressure_gradient_component_value": 4.0,
                    "matched_stokes_body_forward_component_value": 1.0,
                    "matched_end_term_component_value": 0.5,
                },
            ]
        )
        comparison["hull_length_m"] = 3.0
        comparison["hull_beam_m"] = 0.3
        comparison["hull_draft_m"] = 0.1875
        comparison["omega_e_sqrt_l_over_g"] = 1.0
        comparison["normalization_scale"] = comparison["coefficient"].map(
            {"A33": 79.95, "A53": 239.85, "A55": 719.55, "B55": 1300.95}
        )
        body_summary = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "max_body_potential_to_body_normal_velocity_gain": 12.0,
                    "max_body_potential_x_gradient_gain_times_l": 3.0,
                },
                {
                    "coefficient": "A53",
                    "max_body_potential_to_body_normal_velocity_gain": 11.0,
                    "max_body_potential_x_gradient_gain_times_l": 2.0,
                },
            ]
        )
        body_detail = pd.DataFrame(
            [
                {
                    "benchmark": "synthetic",
                    "source_row": 0,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "station_index": 0,
                    "x_m": 1.2,
                    "x_over_l": 0.4,
                    "waterplane_beam_m": 0.25,
                    "effective_draft_m": 0.1875,
                    "submerged_area_m2": 0.03,
                    "time_derivative_density_value_per_m": 1.0,
                },
                {
                    "benchmark": "synthetic",
                    "source_row": 0,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "station_index": 1,
                    "x_m": 1.5,
                    "x_over_l": 0.5,
                    "waterplane_beam_m": 0.3,
                    "effective_draft_m": 0.1875,
                    "submerged_area_m2": 0.0375,
                    "time_derivative_density_value_per_m": 1.1,
                },
                {
                    "benchmark": "synthetic",
                    "source_row": 4,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "station_index": 0,
                    "x_m": 1.2,
                    "x_over_l": 0.4,
                    "waterplane_beam_m": 0.25,
                    "effective_draft_m": 0.1875,
                    "submerged_area_m2": 0.03,
                    "time_derivative_density_value_per_m": 0.3,
                },
                {
                    "benchmark": "synthetic",
                    "source_row": 4,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "station_index": 1,
                    "x_m": 1.5,
                    "x_over_l": 0.5,
                    "waterplane_beam_m": 0.3,
                    "effective_draft_m": 0.1875,
                    "submerged_area_m2": 0.0375,
                    "time_derivative_density_value_per_m": 0.0,
                },
            ]
        )
        heave_summary = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "peak_abs_station_index": 1,
                    "peak_abs_station_x_over_l": 0.5,
                    "peak_abs_station_contribution_share": 0.8,
                    "station_integral_time_component_value": 9.0,
                    "station_integral_closure_residual": 0.0,
                    "time_contribution_cancellation_index": 1.2,
                    "required_global_scale_to_reference_from_time_integral": 0.1,
                    "max_free_surface_potential_to_body_potential_ratio": 4.0,
                    "max_control_potential_to_body_potential_ratio": 2.0,
                    "max_inner_free_surface_normal_derivative_to_body_normal_velocity_ratio": 1.5,
                    "time_contribution_abs_centroid_x_over_l": 0.45,
                },
                {
                    "coefficient": "A53",
                    "peak_abs_station_index": 2,
                    "peak_abs_station_x_over_l": 0.7,
                    "peak_abs_station_contribution_share": 0.6,
                    "station_integral_time_component_value": 7.0,
                    "station_integral_closure_residual": 0.0,
                    "time_contribution_cancellation_index": 1.1,
                    "required_global_scale_to_reference_from_time_integral": 0.2,
                    "max_free_surface_potential_to_body_potential_ratio": 3.0,
                    "max_control_potential_to_body_potential_ratio": 1.5,
                    "max_inner_free_surface_normal_derivative_to_body_normal_velocity_ratio": 1.3,
                    "time_contribution_abs_centroid_x_over_l": 0.55,
                },
            ]
        )
        pitch_summary = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "max_forward_to_oscillation_norm_ratio": 4.0,
                    "median_forward_to_oscillation_norm_ratio": 2.0,
                    "dominant_pressure_gradient_station_index": 1,
                    "dominant_pressure_gradient_x_over_l": 0.5,
                    "dominant_pressure_gradient_density_abs": 3.0,
                    "moment_radiation_lever_ratio_min": 0.9,
                    "moment_radiation_lever_ratio_max": 1.1,
                },
                {
                    "coefficient": "B55",
                    "max_forward_to_oscillation_norm_ratio": 5.0,
                    "median_forward_to_oscillation_norm_ratio": 3.0,
                    "dominant_pressure_gradient_station_index": 2,
                    "dominant_pressure_gradient_x_over_l": 0.7,
                    "dominant_pressure_gradient_density_abs": 4.0,
                    "moment_radiation_lever_ratio_min": 0.8,
                    "moment_radiation_lever_ratio_max": 1.2,
                },
            ]
        )
        end_summary = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "end_to_endpoint_forward_ratio_abs": 0.5,
                    "end_lever_minus_station_moment_lever_m": 0.1,
                },
                {
                    "coefficient": "B55",
                    "end_to_endpoint_forward_ratio_abs": 0.6,
                    "end_lever_minus_station_moment_lever_m": 0.2,
                },
            ]
        )
        lever_summary = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "max_forward_identity_residual_over_effective_tolerance": 2.0,
                    "max_abs_end_lever_delta_m": 0.1,
                },
                {
                    "coefficient": "B55",
                    "max_forward_identity_residual_over_effective_tolerance": 3.0,
                    "max_abs_end_lever_delta_m": 0.2,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            time_detail, time_summary = _write_ma2005_time_pressure_source_audit(
                comparison,
                body_summary,
                heave_summary,
                tmp_path,
                "synthetic",
            )
            pressure_radiation_detail, pressure_radiation_summary = (
                _write_ma2005_heave_pressure_radiation_check(
                    comparison,
                    body_summary,
                    heave_summary,
                    tmp_path,
                    "synthetic",
                )
            )
            open_section_detail, open_section_summary = _write_ma2005_open_section_pressure_reference_audit(
                comparison,
                body_detail,
                tmp_path,
                "synthetic",
                bem_free_surface_panel_count_per_side=3,
                bem_body_panel_count=4,
            )
            pitch_detail, pitch_out_summary = _write_ma2005_pitch_row_moment_chain_audit(
                comparison,
                pitch_summary,
                end_summary,
                lever_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_source_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_heave_pressure_radiation_check.csv").exists())
            self.assertTrue((tmp_path / "synthetic_heave_pressure_radiation_check_summary.csv").exists())
            self.assertTrue((tmp_path / "synthetic_open_section_pressure_reference_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_open_section_pressure_reference_summary.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_row_moment_chain_audit.csv").exists())
        self.assertEqual(set(time_detail["coefficient"]), {"A33", "A53"})
        self.assertEqual(set(pressure_radiation_detail["coefficient"]), {"A33", "A53"})
        self.assertEqual(set(open_section_detail["coefficient"]), {"A33", "A53"})
        self.assertEqual(set(open_section_summary["coefficient"]), {"A33", "A53"})
        self.assertIn("independent_section_body_potential_norm", open_section_detail.columns)
        self.assertIn("independent_to_matched_body_potential_norm_ratio", open_section_detail.columns)
        self.assertIn("median_independent_to_matched_body_potential_norm_ratio", open_section_summary.columns)
        self.assertIn("potential_scale_conclusion", open_section_summary.columns)
        self.assertEqual(set(pitch_detail["coefficient"]), {"A55", "B55"})
        self.assertEqual(time_detail[time_detail["coefficient"].eq("A33")]["source_rank_1"].iloc[0], "Eq.30_time_derivative_pressure")
        self.assertEqual(
            pressure_radiation_detail[pressure_radiation_detail["coefficient"].eq("A33")][
                "station_integral_closure_status"
            ].iloc[0],
            "PASS",
        )
        self.assertEqual(
            pressure_radiation_detail[pressure_radiation_detail["coefficient"].eq("A33")][
                "open_section_independent_reference_status"
            ].iloc[0],
            "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE",
        )
        self.assertEqual(pitch_detail[pitch_detail["coefficient"].eq("B55")]["source_rank_1"].iloc[0], "Eq.31_pressure_gradient_moment")
        self.assertEqual(int(time_summary["fail_count"].iloc[0]), 2)
        self.assertEqual(int(pressure_radiation_summary["pending_reference_count"].iloc[0]), 2)
        self.assertEqual(
            open_section_summary["candidate_default_gate_eligible"].astype(str).str.lower().iloc[0],
            "false",
        )
        self.assertEqual(int(pitch_out_summary["fail_count"].iloc[0]), 2)

    def test_ma2005_pitch_moment_complex_scale_requirement_flags_phase_rotation(self):
        component_audit = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "reference_value": 1.0,
                    "computed_value": 1.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "time_derivative_pressure_contribution_value": 0.0,
                    "forward_speed_pressure_gradient_contribution_value": 1.0,
                    "stokes_body_forward_speed_contribution_value": 0.0,
                    "end_contour_contribution_value": 0.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 0.1,
                    "computed_value": 1.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "time_derivative_pressure_contribution_value": 0.0,
                    "forward_speed_pressure_gradient_contribution_value": 1.0,
                    "stokes_body_forward_speed_contribution_value": 0.0,
                    "end_contour_contribution_value": 0.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_moment_complex_scale_requirement_audit(
                component_audit,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_moment_complex_scale_requirement_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_moment_complex_scale_requirement_summary.csv").exists())

            gradient = summary[
                summary["candidate_name"].eq("scale_pressure_gradient_moment_keep_time_end")
            ].iloc[0]
            self.assertAlmostEqual(float(gradient["required_complex_scale_real"]), 0.55)
            self.assertAlmostEqual(float(gradient["required_complex_scale_imag"]), -0.45)
            self.assertGreater(float(gradient["imag_to_real_abs_ratio"]), 0.25)
            self.assertEqual(
                gradient["diagnostic_conclusion"],
                "pitch_pair_requires_complex_phase_rotation_not_real_scale",
            )
            self.assertEqual(int(gradient["pass_count"]), 0)
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())

            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                pitch_moment_complex_scale_requirement_summary=summary,
            )
            self.assertIn(
                "pitch_moment_complex_scale_requirement",
                set(impact["candidate_family"].astype(str)),
            )
            self.assertIn(
                "scale_pressure_gradient_moment_keep_time_end",
                set(detail["candidate_name"].astype(str)),
            )

    def test_ma2005_pitch_damping_normalization_blocker_trace_excludes_simple_conversion(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 0.063,
                    "computed_value": 0.16,
                    "gate_error_ratio": 10.0,
                    "matched_candidate_time_only_value": 0.063,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                },
                {
                    "coefficient": "B55",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 0.09,
                    "computed_value": 1.86,
                    "gate_error_ratio": 131.0,
                    "matched_candidate_time_only_value": 0.57,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                },
            ]
        )
        conversion = pd.DataFrame(
            [
                {
                    "coefficient": "B55",
                    "variant_name": "damping_divide_omega",
                    "computed_value": 1.03,
                    "gate_error_ratio": 69.0,
                    "gate_ratio_delta_vs_current": -62.0,
                    "status": "FAIL",
                }
            ]
        )
        ab_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "current_ab_split",
                    "pass_count": 0,
                    "row_count": 2,
                    "max_gate_error_ratio": 131.0,
                }
            ]
        )
        pitch_scale_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "scale_forward_gradient_plus_end_moment_keep_time",
                    "pass_count": 1,
                    "row_count": 2,
                    "max_gate_error_ratio": 4.3,
                    "imag_to_real_abs_ratio": 0.08,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_damping_normalization_blocker_trace(
                comparison,
                conversion,
                ab_summary,
                pitch_scale_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_damping_normalization_blocker_trace.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_damping_normalization_blocker_summary.csv").exists())
            self.assertEqual(set(detail["coefficient"]), {"A55", "B55"})
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "pitch_damping_blocker_not_conversion_or_simple_moment_scale",
            )
            self.assertEqual(summary["candidate_default_gate_eligible"].iloc[0], "false")

    def test_ma2005_pitch_m5_forward_speed_scale_probe_stays_diagnostic_only(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "row": 6,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 0.063,
                    "computed_value": 0.16,
                    "gate_error_ratio": 10.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                },
                {
                    "coefficient": "B55",
                    "row": 7,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 0.09,
                    "computed_value": 1.86,
                    "gate_error_ratio": 131.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                },
            ]
        )

        def fake_compute(row, **_kwargs):
            coeff = str(row["coefficient"]).upper()
            scale = float(row["matched_pitch_forward_speed_scale"])
            values = {
                ("A55", 1.0): 0.16,
                ("B55", 1.0): 1.86,
                ("A55", 0.0): 0.063,
                ("B55", 0.0): 0.57,
                ("A55", -1.0): -0.20,
                ("B55", -1.0): -1.20,
                ("A55", 0.5): 0.09,
                ("B55", 0.5): 1.10,
                ("A55", 2.0): 0.30,
                ("B55", 2.0): 2.60,
            }
            computed = values[(coeff, scale)]
            return {
                "computed_value": computed,
                "raw_value": computed,
                "normalization": "ma2005",
                "normalization_scale": 1.0,
                "provider_route": "matched_bie_station_sweep",
                "provider_formulation": "matched_bie",
                "matched_pitch_oscillation_scale": 1.0,
                "matched_pitch_forward_speed_scale": scale,
                "matched_candidate_time_only_value": 0.063 if coeff == "A55" else 0.57,
                "matched_time_derivative_component_value": 0.063 if coeff == "A55" else 0.57,
                "matched_pressure_gradient_component_value": computed - 0.063,
                "matched_stokes_body_forward_component_value": 0.0,
                "matched_end_term_component_value": 0.0,
                "matched_selected_body_pressure_forward_to_time_norm_ratio_max": abs(scale),
                "matched_selected_forward_speed_density_cancellation_index": 0.5,
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_m5_forward_speed_scale_probe(
                comparison,
                tmp_path,
                "synthetic",
                compute_fn=fake_compute,
            )
            self.assertTrue((tmp_path / "synthetic_pitch_m5_forward_speed_scale_probe.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_m5_forward_speed_scale_summary.csv").exists())
            self.assertEqual(set(detail["coefficient"]), {"A55", "B55"})
            self.assertFalse(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())

            remove = summary[summary["candidate_name"].eq("remove_m5_forward_scale_0")].iloc[0]
            self.assertEqual(int(remove["pass_count"]), 1)
            self.assertEqual(
                remove["diagnostic_conclusion"],
                "m5_forward_scale_closes_only_one_pitch_row",
            )
            self.assertGreater(float(remove["b55_gate_error_ratio"]), 1.0)

    def test_ma2005_pitch_complex_component_phase_budget_identifies_phase_aligned_term(self):
        component_audit = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "reference_value": 1.0,
                    "computed_value": 1.0,
                    "gate_error_ratio": 0.0,
                    "tolerance": 0.15,
                    "time_derivative_pressure_contribution_value": 1.0,
                    "forward_speed_pressure_gradient_contribution_value": 0.0,
                    "stokes_body_forward_speed_contribution_value": 2.0,
                    "end_contour_contribution_value": 0.0,
                    "current_default_reconstructed_value": 1.0,
                    "all_four_component_sum_value": 3.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 0.1,
                    "computed_value": 1.1,
                    "gate_error_ratio": 66.0,
                    "tolerance": 0.15,
                    "time_derivative_pressure_contribution_value": 0.1,
                    "forward_speed_pressure_gradient_contribution_value": 1.0,
                    "stokes_body_forward_speed_contribution_value": 0.0,
                    "end_contour_contribution_value": 0.0,
                    "current_default_reconstructed_value": 1.1,
                    "all_four_component_sum_value": 1.1,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_complex_component_phase_budget_audit(
                component_audit,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_complex_component_phase_budget_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_complex_component_phase_budget_summary.csv").exists())
            self.assertIn("current_default_selected_route", set(detail["component_name"].astype(str)))
            self.assertEqual(
                summary["most_phase_aligned_component"].iloc[0],
                "time_derivative_pressure_T",
            )
            self.assertGreaterEqual(int(summary["component_candidate_pair_pass_count"].iloc[0]), 1)
            self.assertFalse(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())

            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                pitch_complex_component_phase_budget_summary=summary,
            )
            self.assertIn(
                "pitch_complex_component_phase_budget",
                set(impact["candidate_family"].astype(str)),
            )

    def test_ma2005_pitch_endpoint_spike_dominance_audit_flags_first_station_spike(self):
        rows = []
        for coefficient in ("A55", "B55"):
            for station_index, (x_m, pressure_gradient) in enumerate(
                [(0.0, 100.0), (1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]
            ):
                rows.append(
                    {
                        "benchmark": "synthetic",
                        "source_row": 0,
                        "coefficient": coefficient,
                        "station_index": station_index,
                        "x_m": x_m,
                        "x_over_l": x_m / 3.0,
                        "total_density_value_per_m": pressure_gradient,
                        "time_derivative_density_value_per_m": 0.0,
                        "pressure_gradient_density_value_per_m": pressure_gradient,
                        "stokes_body_forward_density_value_per_m": 0.0,
                    }
                )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_endpoint_spike_dominance_audit(
                pd.DataFrame(rows),
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_endpoint_spike_dominance_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_endpoint_spike_dominance_summary.csv").exists())
            self.assertFalse(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            pressure = detail[detail["component_name"].eq("pressure_gradient")]
            self.assertTrue(pressure["endpoint_spike_flag"].astype(str).str.lower().eq("true").all())
            self.assertGreater(float(summary["max_pressure_gradient_first_station_abs_share"].iloc[0]), 0.5)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "pitch_endpoint_pressure_gradient_or_moment_spike_detected",
            )

    def test_ma2005_pitch_eq31_eq32_moment_balance_audit_stays_diagnostic_only(self):
        component_audit = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "reference_value": 1.0,
                    "current_default_reconstructed_value": 3.0,
                    "gate_error_ratio": 13.3,
                    "tolerance": 0.15,
                    "time_derivative_pressure_contribution_value": 0.2,
                    "forward_speed_pressure_gradient_contribution_value": 2.8,
                    "stokes_body_forward_speed_contribution_value": 0.8,
                    "end_contour_contribution_value": 0.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 0.5,
                    "current_default_reconstructed_value": 2.5,
                    "gate_error_ratio": 26.7,
                    "tolerance": 0.15,
                    "time_derivative_pressure_contribution_value": 0.1,
                    "forward_speed_pressure_gradient_contribution_value": 2.4,
                    "stokes_body_forward_speed_contribution_value": 0.4,
                    "end_contour_contribution_value": 0.0,
                },
            ]
        )
        pitch_measure = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "density_row_gradient_integral_value": -0.8,
                    "density_negative_stokes_integral_value": -0.8,
                },
                {
                    "coefficient": "B55",
                    "density_row_gradient_integral_value": -0.4,
                    "density_negative_stokes_integral_value": -0.4,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_pitch_eq31_eq32_moment_balance_audit(
                component_audit,
                pitch_measure,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_pitch_eq31_eq32_moment_balance_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_pitch_eq31_eq32_moment_balance_summary.csv").exists())
            self.assertFalse(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertIn("eq32_T_plus_S_plus_E", set(detail["candidate_name"].astype(str)))
            self.assertEqual(summary["eq32_stokes_candidate_pass_count"].iloc[0], 2)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "pitch_eq31_eq32_route_closes_pair_but_requires_full_gate1_trace",
            )
            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                pitch_eq31_eq32_moment_balance_summary=summary,
            )
            self.assertIn("pitch_eq31_eq32_moment_balance", set(impact["candidate_family"].astype(str)))

    def test_ma2005_remaining_failure_chain_budget_audit_groups_three_blockers(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                    "matched_dominant_force_component": "time_derivative",
                },
                {
                    "coefficient": "A53",
                    "reference_value": 0.15,
                    "computed_value": 1.4,
                    "gate_error_ratio": 20.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B33",
                    "reference_value": 2.1,
                    "computed_value": 9.0,
                    "gate_error_ratio": 22.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A35",
                    "reference_value": -0.2,
                    "computed_value": -2.7,
                    "gate_error_ratio": 41.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B35",
                    "reference_value": 0.13,
                    "computed_value": 6.5,
                    "gate_error_ratio": 164.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A55",
                    "reference_value": 0.063,
                    "computed_value": 0.16,
                    "gate_error_ratio": 10.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B55",
                    "reference_value": 0.09,
                    "computed_value": 1.86,
                    "gate_error_ratio": 131.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
            ]
        )
        impact = pd.DataFrame(
            [
                {
                    "candidate_family": "inner_free_surface_control_row_projection_candidate",
                    "candidate_name": "only_control_rhs",
                    "affected_coefficients": "A33,A53",
                    "pass_count": 0,
                    "row_count": 2,
                    "max_gate_error_ratio": 2.4,
                    "candidate_default_gate_eligible": "false",
                },
                {
                    "candidate_family": "mapping_conservative_product_derivative",
                    "candidate_name": "heave_projection_leibniz_endpoint_flux_pitch_current",
                    "affected_coefficients": "B33,A35,B35",
                    "pass_count": 0,
                    "row_count": 3,
                    "max_gate_error_ratio": 132.0,
                    "candidate_default_gate_eligible": "false",
                },
                {
                    "candidate_family": "pitch_eq31_eq32_moment_balance",
                    "candidate_name": "eq31_T_plus_G_plus_row_measure_plus_E",
                    "affected_coefficients": "A55,B55",
                    "pass_count": 0,
                    "row_count": 2,
                    "max_gate_error_ratio": 86.0,
                    "candidate_default_gate_eligible": "false",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_remaining_failure_chain_budget_audit(
                comparison,
                impact,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_remaining_failure_chain_budget_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_remaining_failure_chain_budget_summary.csv").exists())
            self.assertEqual(len(summary), 3)
            self.assertEqual(set(summary["chain_acceptance_status"].astype(str)), {"FAIL"})
            self.assertEqual(
                int(
                    summary.loc[
                        summary["chain_id"].eq("A33_A53_time_pressure_body_potential"),
                        "current_fail_count",
                    ].iloc[0]
                ),
                2,
            )
            self.assertIn("A33", set(detail["coefficient"].astype(str)))
            self.assertEqual(
                summary.loc[
                    summary["chain_id"].eq("A55_B55_pitch_row_moment"),
                    "best_diagnostic_candidate_name",
                ].iloc[0],
                "eq31_T_plus_G_plus_row_measure_plus_E",
            )
            self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_remaining_failure_chain_budget_accepts_multifrequency_rows(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "reference_value": 1.0,
                    "computed_value": 1.0,
                    "gate_error_ratio": gate,
                    "status": "PASS",
                    "provider_route": "matched_bie_station_sweep",
                }
                for coefficient, gate in (("A33", 0.3), ("A33", 0.4), ("A53", 0.5), ("A53", 0.6))
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, summary = _write_ma2005_remaining_failure_chain_budget_audit(
                comparison,
                pd.DataFrame(),
                Path(tmp),
                "synthetic_multifrequency",
            )

        chain = summary[summary["chain_id"].eq("A33_A53_time_pressure_body_potential")].iloc[0]
        self.assertEqual(chain["chain_acceptance_status"], "PASS")
        self.assertEqual(int(chain["current_pass_count"]), 4)
        self.assertEqual(int(chain["current_fail_count"]), 0)
        self.assertEqual(chain["chain_blocker"], "none_for_current_reference_rows")

    def test_ma2005_force_route_audit_reconstructs_eq32_selected_force(self):
        selected = _ma2005_force_for_assembly_route(
            "eq32_stokes_body_plus_end",
            time_force=1.0 + 2.0j,
            gradient_force=10.0 + 20.0j,
            stokes_force=3.0 + 4.0j,
            row_measure_force=30.0 + 40.0j,
            end_force=5.0 + 6.0j,
        )
        self.assertEqual(selected, 9.0 + 12.0j)

    def test_ma2005_b55_damping_pressure_source_audit_flags_b55_only_closure(self):
        component_audit = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "reference_value": 0.063,
                    "computed_value": 0.16,
                    "gate_error_ratio": 10.0,
                    "tolerance": 0.15,
                    "effective_abs_tolerance": 0.00945,
                    "time_derivative_pressure_contribution_value": 0.059,
                    "forward_speed_pressure_gradient_contribution_value": 0.196,
                    "stokes_body_forward_speed_contribution_value": 1.63,
                    "end_contour_contribution_value": -0.095,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 0.09,
                    "computed_value": 1.858,
                    "gate_error_ratio": 131.0,
                    "tolerance": 0.15,
                    "effective_abs_tolerance": 0.0135,
                    "time_derivative_pressure_contribution_value": 0.567,
                    "forward_speed_pressure_gradient_contribution_value": 1.011,
                    "stokes_body_forward_speed_contribution_value": 0.427,
                    "end_contour_contribution_value": 0.280,
                },
            ]
        )
        pitch_scale_detail = pd.DataFrame(
            [
                {
                    "candidate_name": "scale_forward_gradient_plus_end_moment_keep_time",
                    "coefficient": "A55",
                    "candidate_computed_value": 0.104,
                    "gate_error_ratio": 4.3,
                    "candidate_status": "FAIL",
                    "required_complex_scale_real": -0.37,
                    "required_complex_scale_imag": -0.03,
                    "required_complex_scale_abs": 0.37,
                    "imag_to_real_abs_ratio": 0.08,
                },
                {
                    "candidate_name": "scale_forward_gradient_plus_end_moment_keep_time",
                    "coefficient": "B55",
                    "candidate_computed_value": 0.093,
                    "gate_error_ratio": 0.24,
                    "candidate_status": "PASS",
                    "required_complex_scale_real": -0.37,
                    "required_complex_scale_imag": -0.03,
                    "required_complex_scale_abs": 0.37,
                    "imag_to_real_abs_ratio": 0.08,
                },
            ]
        )
        m5_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "remove_m5_forward_scale_0",
                    "a55_gate_error_ratio": 0.4,
                    "b55_gate_error_ratio": 89.0,
                    "pass_count": 1,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_b55_damping_pressure_source_audit(
                component_audit,
                pitch_scale_detail,
                m5_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_b55_damping_pressure_source_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_b55_damping_pressure_source_summary.csv").exists())
            self.assertFalse(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "b55_can_be_matched_by_untraced_component_scale_but_pitch_pair_fails",
            )
            self.assertGreater(float(summary["b55_candidate_pass_count"].iloc[0]), 0)
            self.assertEqual(int(summary["pitch_pair_pass_candidate_count"].iloc[0]), 0)

            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                b55_damping_pressure_source_summary=summary,
            )
            self.assertIn("b55_damping_pressure_source", set(impact["candidate_family"].astype(str)))

    def test_ma2005_ab_force_reconstruction_candidate_detects_phase_split(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "reference_value": 2.0,
                    "computed_value": 1.0,
                    "raw_computed_value": 1.0,
                    "abs_error": 1.0,
                    "gate_error_ratio": 10.0,
                    "status": "FAIL",
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "normalization_scale": 1.0,
                    "provider_route": "matched_bie_station_sweep",
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "omega_e_rad_s": 1.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": -1.0,
                    "computed_value": 2.0,
                    "raw_computed_value": 2.0,
                    "abs_error": 3.0,
                    "gate_error_ratio": 20.0,
                    "status": "FAIL",
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "normalization_scale": 1.0,
                    "provider_route": "matched_bie_station_sweep",
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "omega_e_rad_s": 1.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_ab_force_reconstruction_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_ab_force_reconstruction_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_ab_force_reconstruction_candidate_summary.csv").exists())
            best = summary[
                summary["candidate_name"].eq("force_phase_plus_90_then_current_split")
            ].iloc[0]
            self.assertEqual(int(best["pass_count"]), 2)
            self.assertLessEqual(float(best["max_gate_error_ratio"]), 1.0)
            self.assertEqual(best["paired_cells"], "55")
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("true").any())
            self.assertEqual(
                set(
                    detail[
                        detail["candidate_name"].eq("force_phase_plus_90_then_current_split")
                    ]["candidate_status"].astype(str)
                ),
                {"PASS"},
            )

            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                ab_force_reconstruction_candidate_summary=summary,
            )
            self.assertIn(
                "ab_force_reconstruction_candidate",
                set(impact["candidate_family"].astype(str)),
            )

    def test_ma2005_gate1_remaining_blocker_audit_compresses_traceable_gaps(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "status": "FAIL",
                    "gate_error_ratio": 20.0,
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B33",
                    "reference_value": 2.0,
                    "computed_value": 8.0,
                    "status": "FAIL",
                    "gate_error_ratio": 15.0,
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A55",
                    "reference_value": 0.1,
                    "computed_value": 1.0,
                    "status": "FAIL",
                    "gate_error_ratio": 12.0,
                    "provider_route": "matched_bie_station_sweep",
                },
            ]
        )
        gate1_failure = pd.DataFrame(
            [
                {"coefficient": "A33", "failure_source": "heave_time_derivative_body_potential_scale"},
                {"coefficient": "B33", "failure_source": "forward_speed_pressure_gradient_station_mapping"},
                {"coefficient": "A55", "failure_source": "pitch_row_moment_chain"},
            ]
        )
        candidate_impact = pd.DataFrame(
            [
                {
                    "candidate_name": "least_squares_time_gradient_stokes_end",
                    "candidate_family": "scale_fit",
                    "pass_count": 1,
                    "row_count": 3,
                    "max_gate_error_ratio": 8.0,
                    "candidate_default_gate_eligible": False,
                }
            ]
        )
        heave_pressure = pd.DataFrame(
            [
                {
                    "station_integral_closure_pass_count": 1,
                    "pending_reference_count": 1,
                    "required_scale_min": 0.1,
                    "required_scale_max": 0.11,
                    "open_section_independent_reference_status": (
                        "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE"
                    ),
                }
            ]
        )
        open_section = pd.DataFrame(
            [
                {
                    "independent_reference_status": "EXPERIMENTAL_OPEN_SECTION_BEM_REFERENCE_NOT_HARD_GATE",
                    "median_independent_to_matched_abs_ratio": 0.04,
                }
            ]
        )
        formula = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "eq31_eq32_proxy_residual_norm": 0.9,
                    "dominant_formula_component": "interior_distributed_transport",
                    "interior_distributed_abs_share": 0.88,
                    "boundary_proxy_abs_share": 0.12,
                }
            ]
        )
        row_mapping = pd.DataFrame(
            [
                {
                    "candidate_name": "mapped_normalized_y_central",
                    "diagnostic_conclusion": "mapping_candidate_excluded_by_zero_mi_rows",
                }
            ]
        )
        fixed_control = pd.DataFrame(
            [
                {
                    "open_blocker_count": 1,
                    "median_interior_distributed_abs_share": 0.88,
                    "diagnostic_conclusion": "fixed_control_surface_transport_gap_confirmed",
                }
            ]
        )
        pitch_chain = pd.DataFrame(
            [
                {
                    "fail_count": 1,
                    "row_count": 1,
                    "max_gate_error_ratio": 12.0,
                    "dominant_rank_1_counts": "Eq.31_pressure_gradient_moment:1",
                }
            ]
        )
        stokes_end = pd.DataFrame(
            [
                {
                    "row_count": 3,
                    "identity_pass_count": 1,
                    "end_lever_consistency_pass_count": 3,
                    "max_forward_identity_residual_over_effective_tolerance": 42.0,
                    "min_end_to_endpoint_forward_ratio_abs": 0.44,
                    "max_end_to_endpoint_forward_ratio_abs": 0.80,
                    "diagnostic_conclusion": "eq31_eq32_stokes_end_identity_not_closed",
                }
            ]
        )
        matched_end = pd.DataFrame([{"endpoint_label": "configured_end_station"}])
        rhs_source = pd.DataFrame(
            [
                {
                    "max_source_sum_relative_residual": 1.0e-12,
                    "diagnostic_conclusion": "rhs_sources_reconstruct_solution",
                }
            ]
        )
        inner_state = pd.DataFrame(
            [
                {
                    "max_update_relative_residual": 0.0,
                    "max_transfer_relative_residual": 0.0,
                    "diagnostic_conclusion": "inner_state_updates_and_transfers_reconstruct_eq19_22",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_gate1_remaining_blocker_audit(
                comparison,
                gate1_failure,
                candidate_impact,
                heave_pressure,
                open_section,
                formula,
                row_mapping,
                fixed_control,
                pitch_chain,
                rhs_source,
                inner_state,
                tmp_path,
                "synthetic",
                stokes_end_lever_consistency_summary=stokes_end,
                matched_end_pressure_closure_summary=matched_end,
            )
            self.assertTrue((tmp_path / "synthetic_gate1_remaining_blocker_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_gate1_remaining_blocker_summary.csv").exists())

        self.assertIn("time_pressure_body_potential_scale", set(detail["blocker_id"]))
        self.assertIn("zero_m3_distributed_geometry_transport", set(detail["blocker_id"]))
        self.assertIn("pitch_row_moment_chain", set(detail["blocker_id"]))
        pitch_blocker = detail[detail["blocker_id"].eq("pitch_row_moment_chain")].iloc[0]
        self.assertIn("stokes_end_identity=eq31_eq32_stokes_end_identity_not_closed", pitch_blocker["evidence"])
        self.assertIn("end_to_endpoint_forward_ratio_range=[0.44,0.8]", pitch_blocker["evidence"])
        self.assertEqual(summary["compression_status"].iloc[0], "PENDING_COMPRESSED_TO_TRACEABLE_GAPS")
        self.assertFalse(bool(summary["default_fix_allowed_by_current_evidence"].iloc[0]))
        self.assertGreaterEqual(int(summary["current_materials_or_theory_gap_count"].iloc[0]), 3)

    def test_ma2005_literature_traceability_gap_audit_confirms_material_gaps(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": "A33", "status": "FAIL"},
                {"coefficient": "A53", "status": "FAIL"},
                {"coefficient": "B33", "status": "FAIL"},
                {"coefficient": "A35", "status": "FAIL"},
                {"coefficient": "B35", "status": "FAIL"},
                {"coefficient": "B53", "status": "FAIL"},
                {"coefficient": "A55", "status": "FAIL"},
                {"coefficient": "B55", "status": "FAIL"},
            ]
        )
        heave_pressure = pd.DataFrame(
            [
                {
                    "open_section_independent_reference_status": (
                        "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE"
                    ),
                    "required_scale_min": 0.098,
                    "required_scale_max": 0.106,
                }
            ]
        )
        formula = pd.DataFrame(
            [
                {
                    "dominant_formula_component": "interior_distributed_transport",
                    "eq31_eq32_proxy_residual_norm": 0.9,
                }
            ]
        )
        pitch = pd.DataFrame(
            [
                {
                    "fail_count": 2,
                    "max_gate_error_ratio": 131.0,
                    "dominant_rank_1_counts": "Eq.31_pressure_gradient_moment:1",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_literature_traceability_gap_audit(
                comparison,
                heave_pressure,
                formula,
                pitch,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_literature_traceability_gap_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_literature_traceability_gap_summary.csv").exists())

        self.assertEqual(int(summary["gate1_relevant_gap_count"].iloc[0]), 3)
        self.assertEqual(int(summary["confirmed_gate1_relevant_gap_count"].iloc[0]), 3)
        self.assertTrue(bool(summary["all_gate1_relevant_gaps_confirmed"].iloc[0]))
        self.assertEqual(
            summary["traceability_status"].iloc[0],
            "GATE1_FAILURES_COMPRESSED_TO_TRACEABLE_THEORY_OR_DATA_GAPS",
        )
        self.assertIn("sl7_digital_offsets_for_secondary_gate", set(detail["gap_id"]))
        self.assertIn("c1_trimaran_digital_offsets_for_future_multihull_gate", set(detail["gap_id"]))
        self.assertFalse(detail["default_promotion_allowed"].astype(bool).any())

    def test_ma2005_journee_table_reference_audit_flags_frequency_pairing(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                },
                {
                    "coefficient": "B33",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "reference_value": 2.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        "coefficient,omega_e_sqrt_l_over_g,reference_value,source_table,source_url,source_lines,source_note",
                        "A33,1.68,1.035,Table 2-III,https://example.test,1788,integrated coefficient",
                        "B33,2.23,2.008,Table 2-III,https://example.test,1789,integrated coefficient",
                    ]
                ),
                encoding="utf-8",
            )
            detail, summary = _write_ma2005_journee_table_reference_audit(
                comparison,
                tmp_path,
                "synthetic",
                reference_path=reference_path,
            )
            self.assertTrue((tmp_path / "synthetic_journee_table_reference_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_table_reference_summary.csv").exists())

        a33 = detail[detail["coefficient"].eq("A33")].iloc[0]
        b33 = detail[detail["coefficient"].eq("B33")].iloc[0]
        self.assertEqual(a33["audit_status"], "REFERENCE_VALUE_CLOSE_BUT_FREQUENCY_MISMATCH")
        self.assertEqual(b33["audit_status"], "REFERENCE_ROW_MATCHES_JOURNEE_TABLE")
        self.assertEqual(int(summary["matched_row_count"].iloc[0]), 2)
        self.assertEqual(int(summary["frequency_mismatch_count"].iloc[0]), 1)
        self.assertEqual(
            summary["external_integrated_reference_status"].iloc[0],
            "FOUND_JOURNEE_INTEGRATED_COEFFICIENT_TABLES_NOT_SECTION_PRESSURE",
        )
        self.assertFalse(bool(summary["default_promotion_allowed_by_journee_table"].iloc[0]))

    def test_ma2005_a1_frequency_ladder_audit_flags_sparse_gate_frequency_policy(self):
        length = 3.0
        gravity = 9.80665
        a1_omega_bar_4 = 4.0 * math.sqrt(length / gravity)
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "length_m": length,
                    "gravity_m_s2": gravity,
                },
                {
                    "coefficient": "B33",
                    "omega_e_sqrt_l_over_g": a1_omega_bar_4,
                    "reference_value": 2.0,
                    "length_m": length,
                    "gravity_m_s2": gravity,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        "coefficient,omega_e_sqrt_l_over_g,reference_value,source_table,source_url,source_lines,source_note",
                        f"A33,{3.0 * math.sqrt(length / gravity):.12g},1.035,Table 2-III,https://example.test,1788,integrated coefficient",
                        f"B33,{a1_omega_bar_4:.12g},2.008,Table 2-III,https://example.test,1789,integrated coefficient",
                    ]
                ),
                encoding="utf-8",
            )
            detail, summary = _write_ma2005_a1_frequency_ladder_audit(
                comparison,
                tmp_path,
                "synthetic",
                reference_path=reference_path,
            )
            self.assertTrue((tmp_path / "synthetic_a1_frequency_ladder_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_a1_frequency_ladder_summary.csv").exists())

        gate = detail[detail["source"].astype(str).eq("gate1_sparse_ma_figure_row")]
        journee = detail[detail["source"].astype(str).eq("journee_table_row")]
        a33 = gate[gate["coefficient"].astype(str).eq("A33")].iloc[0]
        b33 = gate[gate["coefficient"].astype(str).eq("B33")].iloc[0]
        self.assertFalse(bool(a33["a1_ladder_match"]))
        self.assertTrue(bool(b33["a1_ladder_match"]))
        self.assertTrue(journee["a1_ladder_match"].astype(bool).all())
        self.assertEqual(int(summary["gate1_ladder_match_count"].iloc[0]), 1)
        self.assertEqual(int(summary["gate1_ladder_mismatch_count"].iloc[0]), 1)
        self.assertEqual(int(summary["journee_ladder_match_count"].iloc[0]), 2)
        self.assertEqual(
            summary["frequency_trace_status"].iloc[0],
            "gate1_sparse_figure_frequencies_partly_mismatch_a1_ladder",
        )
        self.assertFalse(bool(summary["candidate_default_gate_eligible"].iloc[0]))

    def test_ma2005_journee_paired_table_gate_probe_pairs_same_frequency_ab_rows(self):
        comparison = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": coefficient,
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                    "normalization_scale": 10.0,
                    "hull_length_m": 3.0,
                    "provider_route": "matched_bie_station_sweep",
                }
                for coefficient in ("A33", "B33", "A35", "B35")
            ]
        )
        computed = {"A33": 1.0, "B33": 2.0, "A35": -1.0, "B35": 2.0}

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"]).upper()
            value = computed[coefficient]
            return {
                "computed_value": value,
                "raw_value": value * float(row["normalization_scale"]),
                "provider_route": "matched_bie_station_sweep",
                "provider_formulation": "matched_bie",
                "solver_status": "synthetic",
                "matched_time_derivative_component_value": value + 0.1,
                "matched_pressure_gradient_component_value": value + 0.2,
                "matched_stokes_body_forward_component_value": value + 0.3,
                "matched_end_term_component_value": value + 0.4,
                "matched_force_closure_residual_value": 0.0,
                "matched_dominant_force_component": "time_derivative",
                "matched_dominant_force_component_value": value + 0.1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        (
                            "hull,speed_case,motion_test,amplitude,omega_e_sqrt_l_over_g,coefficient,"
                            "reference_value,normalization,source_table,source_url,source_lines,source_note"
                        ),
                        "wigley_iii,Fn0.4,forced_heave,z_a=0.050m,1.68,A33,1.0,ma2005,Table 2-III,https://example.test,1788,heave",
                        "wigley_iii,Fn0.4,forced_heave,z_a=0.050m,1.68,B33,2.0,ma2005,Table 2-III,https://example.test,1788,heave",
                        "wigley_iii,Fn0.4,forced_pitch,theta_a=3deg,1.67,A35,-0.2,ma2005,Table 3-III,https://example.test,1922,pitch",
                        "wigley_iii,Fn0.4,forced_pitch,theta_a=3deg,1.67,B35,0.1,ma2005,Table 3-III,https://example.test,1922,pitch",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary, pair_detail, pair_summary = _write_ma2005_journee_paired_table_gate_probe(
                    comparison,
                    tmp_path,
                    "synthetic",
                    reference_path=reference_path,
                )

            self.assertTrue((tmp_path / "synthetic_journee_paired_table_gate_probe.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_paired_table_gate_probe_summary.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_paired_complex_force_probe.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_paired_complex_force_probe_summary.csv").exists())

        self.assertEqual(len(detail), 4)
        self.assertEqual(int(summary["pass_count"].iloc[0]), 2)
        self.assertEqual(int(summary["fail_count"].iloc[0]), 2)
        self.assertEqual(len(pair_detail), 2)
        self.assertEqual(int(pair_summary["pair_count"].iloc[0]), 2)
        self.assertEqual(int(pair_summary["pass_pair_count"].iloc[0]), 1)
        self.assertEqual(int(pair_summary["fail_pair_count"].iloc[0]), 1)
        self.assertEqual(pair_summary["paired_cells"].iloc[0], "33;35")
        for column in [
            "matched_time_derivative_component_value",
            "matched_pressure_gradient_component_value",
            "matched_stokes_body_forward_component_value",
            "matched_end_term_component_value",
            "matched_dominant_force_component",
            "matched_heave_body_normal_velocity_norm_max",
            "matched_pitch_body_normal_velocity_norm_max",
            "matched_heave_body_potential_norm_max",
            "matched_pitch_body_potential_norm_max",
            "matched_heave_body_pressure_time_derivative_norm_max",
            "matched_pitch_body_pressure_time_derivative_norm_max",
            "matched_heave_body_pressure_forward_speed_norm_max",
            "matched_pitch_body_pressure_forward_speed_norm_max",
            "matched_heave_body_pressure_forward_to_time_norm_ratio_max",
            "matched_pitch_body_pressure_forward_to_time_norm_ratio_max",
        ]:
            self.assertIn(column, detail.columns)
        passed = pair_detail[pair_detail["matrix_cell"].astype(str).eq("33")].iloc[0]
        failed = pair_detail[pair_detail["matrix_cell"].astype(str).eq("35")].iloc[0]
        self.assertEqual(passed["pair_status"], "PASS")
        self.assertEqual(failed["pair_status"], "FAIL")
        self.assertLess(float(passed["pair_force_residual_norm"]), 1e-12)
        self.assertEqual(
            pair_summary["diagnostic_conclusion"].iloc[0],
            "journee_paired_complex_force_probe_still_fails_default_provider",
        )

    def test_ma2005_journee_complex_scale_phase_audit_keeps_pair_scales_diagnostic(self):
        pair_detail = pd.DataFrame(
            [
                {
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 1.68,
                    "paired_coefficients": "A33,B33",
                    "computed_force_real": 10.0,
                    "computed_force_imag": -20.0,
                    "reference_force_real": 10.0,
                    "reference_force_imag": -20.0,
                    "a_reference_value": 1.0,
                    "a_computed_value": 1.0,
                    "b_reference_value": 2.0,
                    "b_computed_value": 2.0,
                },
                {
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "paired_coefficients": "A35,B35",
                    "computed_force_real": 100.0,
                    "computed_force_imag": 0.0,
                    "reference_force_real": 0.0,
                    "reference_force_imag": 100.0,
                    "a_reference_value": 0.01,
                    "a_computed_value": 100.0,
                    "b_reference_value": 10.0,
                    "b_computed_value": 1.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_complex_scale_phase_audit(
                pair_detail,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_complex_scale_phase_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_complex_scale_phase_summary.csv").exists())

        self.assertEqual(len(detail), 2)
        self.assertEqual(int(summary["pair_count"].iloc[0]), 2)
        self.assertEqual(int(summary["real_scale_plausible_count"].iloc[0]), 1)
        self.assertEqual(int(summary["ab_scale_consistent_count"].iloc[0]), 1)
        self.assertGreater(float(summary["complex_scale_phase_span_deg"].iloc[0]), 45.0)
        self.assertGreater(float(summary["max_ab_required_scale_log10_abs_delta"].iloc[0]), 1.0)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "journee_complex_scale_phase_varies_across_pairs",
        )
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_coefficient_frequency_trend_audit_flags_invariant_computation(self):
        paired_table = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 1.68,
                    "reference_value": 2.0,
                    "computed_value": 10.0,
                    "gate_error_ratio": 20.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "gate_error_ratio": 30.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 1.67,
                    "reference_value": -0.2,
                    "computed_value": -0.2,
                    "gate_error_ratio": 0.0,
                    "status": "PASS",
                },
                {
                    "coefficient": "A35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "reference_value": -0.1,
                    "computed_value": -0.1,
                    "gate_error_ratio": 0.0,
                    "status": "PASS",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_coefficient_frequency_trend_audit(
                paired_table,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_coefficient_frequency_trend_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_coefficient_frequency_trend_summary.csv").exists())

        b33 = detail[detail["coefficient"].eq("B33")].iloc[0]
        self.assertEqual(
            b33["diagnostic_conclusion"],
            "computed_frequency_invariant_despite_reference_variation",
        )
        self.assertTrue(bool(b33["computed_values_invariant"]))
        self.assertEqual(int(summary["frequency_invariant_computed_count"].iloc[0]), 1)
        self.assertIn("B33", str(summary["affected_coefficients"].iloc[0]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_component_frequency_trend_audit_localizes_invariant_component(self):
        paired_table = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 1.68,
                    "reference_value": 2.0,
                    "computed_value": 10.0,
                    "matched_time_derivative_component_value": 4.0,
                    "matched_pressure_gradient_component_value": 1.0,
                    "matched_stokes_body_forward_component_value": 0.5,
                    "matched_end_term_component_value": 0.0,
                },
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "matched_time_derivative_component_value": 4.0,
                    "matched_pressure_gradient_component_value": 2.0,
                    "matched_stokes_body_forward_component_value": 0.25,
                    "matched_end_term_component_value": 0.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_component_frequency_trend_audit(
                paired_table,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_component_frequency_trend_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_component_frequency_trend_summary.csv").exists())

        time_row = detail[
            detail["component_name"].astype(str).eq("time_derivative")
            & detail["coefficient"].astype(str).eq("B33")
        ].iloc[0]
        gradient_row = detail[
            detail["component_name"].astype(str).eq("pressure_gradient")
            & detail["coefficient"].astype(str).eq("B33")
        ].iloc[0]
        self.assertEqual(
            time_row["diagnostic_conclusion"],
            "component_frequency_invariant_despite_reference_variation",
        )
        self.assertTrue(bool(time_row["component_values_invariant"]))
        self.assertTrue(bool(gradient_row["component_values_variant"]))
        self.assertEqual(int(summary["frequency_invariant_component_count"].iloc[0]), 2)
        self.assertIn("B33:time_derivative", str(summary["affected_components"].iloc[0]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_cell35_pitch_column_complex_audit_isolates_blocker(self):
        pair_detail = pd.DataFrame(
            [
                {
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 1.67,
                    "paired_coefficients": "A35,B35",
                    "a_gate_error_ratio": 7.0,
                    "b_gate_error_ratio": 658.0,
                    "member_max_gate_error_ratio": 658.0,
                    "pair_force_residual_norm": 1.6,
                    "pair_status": "FAIL",
                },
                {
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "paired_coefficients": "A35,B35",
                    "a_gate_error_ratio": 78.0,
                    "b_gate_error_ratio": 839.0,
                    "member_max_gate_error_ratio": 839.0,
                    "pair_force_residual_norm": 2.25,
                    "pair_status": "FAIL",
                },
            ]
        )
        scale_phase = pd.DataFrame(
            [
                {
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 1.67,
                    "computed_force_phase_deg": -91.0,
                    "reference_force_phase_deg": -154.0,
                    "reference_minus_computed_phase_deg": -63.0,
                    "required_complex_scale_abs": 0.56,
                    "required_complex_scale_phase_deg": -63.0,
                    "a_required_scale": 0.32,
                    "b_required_scale": 0.005,
                    "a_b_required_scale_ratio": 64.0,
                    "a_b_required_scale_log10_abs_delta": 1.8,
                    "a_b_required_scale_same_sign": True,
                },
                {
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "computed_force_phase_deg": -84.0,
                    "reference_force_phase_deg": -152.0,
                    "reference_minus_computed_phase_deg": -68.0,
                    "required_complex_scale_abs": 0.41,
                    "required_complex_scale_phase_deg": -68.0,
                    "a_required_scale": -0.045,
                    "b_required_scale": 0.004,
                    "a_b_required_scale_ratio": -11.25,
                    "a_b_required_scale_log10_abs_delta": 1.05,
                    "a_b_required_scale_same_sign": False,
                },
            ]
        )
        component_trend = pd.DataFrame(
            [
                {
                    "coefficient": "B35",
                    "component_name": "time_derivative",
                    "component_values_invariant": True,
                    "component_values_variant": False,
                },
                {
                    "coefficient": "B35",
                    "component_name": "pressure_gradient",
                    "component_values_invariant": True,
                    "component_values_variant": False,
                },
                {
                    "coefficient": "B35",
                    "component_name": "end_term",
                    "component_values_invariant": True,
                    "component_values_variant": False,
                },
                {
                    "coefficient": "A35",
                    "component_name": "pressure_gradient",
                    "component_values_invariant": False,
                    "component_values_variant": True,
                },
                {
                    "coefficient": "A35",
                    "component_name": "end_term",
                    "component_values_invariant": False,
                    "component_values_variant": True,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_cell35_pitch_column_complex_audit(
                pair_detail,
                scale_phase,
                component_trend,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_cell35_pitch_column_complex_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_cell35_pitch_column_complex_summary.csv").exists())

        self.assertEqual(len(detail), 2)
        self.assertEqual(int(summary["pair_count"].iloc[0]), 2)
        self.assertEqual(int(summary["fail_pair_count"].iloc[0]), 2)
        self.assertEqual(int(summary["b35_invariant_component_count"].iloc[0]), 3)
        self.assertEqual(int(summary["a35_sensitive_component_count"].iloc[0]), 2)
        self.assertGreater(float(summary["phase_error_abs_max_deg"].iloc[0]), 60.0)
        self.assertIn("pressure_gradient", str(summary["b35_invariant_components"].iloc[0]))
        self.assertIn("pressure_gradient", str(summary["a35_sensitive_components"].iloc[0]))
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "cell35_pitch_column_complex_blocker_is_phase_and_b35_damping_invariance",
        )
        self.assertTrue(
            detail["diagnostic_conclusion"]
            .astype(str)
            .str.contains("phase_and_b35_invariance", regex=False)
            .all()
        )
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_cell35_component_complex_audit_finds_dominant_term(self):
        paired_table = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "motion_test": "forced_pitch",
                    "coefficient": "A35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "hull_length_m": 9.80665,
                    "gravity_m_s2": 9.80665,
                    "reference_value": -10.0,
                    "normalization_scale": 1.0,
                    "matched_time_derivative_component_raw": 20.0,
                    "matched_pressure_gradient_component_raw": -50.0,
                    "matched_stokes_body_forward_component_raw": 0.0,
                    "matched_row_measure_transport_component_raw": 0.0,
                    "matched_end_term_component_raw": -5.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "motion_test": "forced_pitch",
                    "coefficient": "B35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "hull_length_m": 9.80665,
                    "gravity_m_s2": 9.80665,
                    "reference_value": 4.0,
                    "normalization_scale": 1.0,
                    "matched_time_derivative_component_raw": 1.0,
                    "matched_pressure_gradient_component_raw": 10.0,
                    "matched_stokes_body_forward_component_raw": 0.0,
                    "matched_row_measure_transport_component_raw": 0.0,
                    "matched_end_term_component_raw": 2.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "motion_test": "forced_pitch",
                    "coefficient": "A35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.0,
                    "hull_length_m": 9.80665,
                    "gravity_m_s2": 9.80665,
                    "reference_value": -2.5,
                    "normalization_scale": 1.0,
                    "matched_time_derivative_component_raw": 5.0,
                    "matched_pressure_gradient_component_raw": -12.5,
                    "matched_stokes_body_forward_component_raw": 0.0,
                    "matched_row_measure_transport_component_raw": 0.0,
                    "matched_end_term_component_raw": -1.25,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "motion_test": "forced_pitch",
                    "coefficient": "B35",
                    "matrix_cell": "35",
                    "omega_e_sqrt_l_over_g": 2.0,
                    "hull_length_m": 9.80665,
                    "gravity_m_s2": 9.80665,
                    "reference_value": 2.0,
                    "normalization_scale": 1.0,
                    "matched_time_derivative_component_raw": 0.5,
                    "matched_pressure_gradient_component_raw": 5.0,
                    "matched_stokes_body_forward_component_raw": 0.0,
                    "matched_row_measure_transport_component_raw": 0.0,
                    "matched_end_term_component_raw": 1.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_cell35_component_complex_audit(
                paired_table,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_cell35_component_complex_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_cell35_component_complex_summary.csv").exists())

        self.assertEqual(int(summary["frequency_count"].iloc[0]), 2)
        self.assertEqual(
            summary["dominant_single_component_by_median_abs_ratio"].iloc[0],
            "pressure_gradient",
        )
        self.assertGreater(float(summary["time_derivative_median_phase_abs_deg"].iloc[0]), 60.0)
        self.assertLess(
            float(summary["pressure_gradient_median_phase_abs_deg"].iloc[0]),
            float(summary["time_derivative_median_phase_abs_deg"].iloc[0]),
        )
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "cell35_component_complex_time_pressure_misaligned_gradient_end_over_amplified",
        )
        gradient = detail[detail["candidate_name"].astype(str).eq("pressure_gradient")]
        self.assertEqual(len(gradient), 2)
        self.assertTrue((pd.to_numeric(gradient["component_abs_over_reference_abs"]) > 1.0).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_cell35_time_pressure_phase_candidate_keeps_best_excluded(self):
        component_detail = pd.DataFrame(
            [
                {
                    "omega_e_sqrt_l_over_g": 1.0,
                    "omega_rad_s": 1.0,
                    "candidate_name": "time_derivative",
                    "component_force_real": 6.0,
                    "component_force_imag": -1.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
                {
                    "omega_e_sqrt_l_over_g": 1.0,
                    "omega_rad_s": 1.0,
                    "candidate_name": "pressure_gradient",
                    "component_force_real": -6.0,
                    "component_force_imag": -4.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
                {
                    "omega_e_sqrt_l_over_g": 1.0,
                    "omega_rad_s": 1.0,
                    "candidate_name": "end_term",
                    "component_force_real": -1.0,
                    "component_force_imag": -1.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
                {
                    "omega_e_sqrt_l_over_g": 2.0,
                    "omega_rad_s": 2.0,
                    "candidate_name": "time_derivative",
                    "component_force_real": 6.0,
                    "component_force_imag": -1.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
                {
                    "omega_e_sqrt_l_over_g": 2.0,
                    "omega_rad_s": 2.0,
                    "candidate_name": "pressure_gradient",
                    "component_force_real": -6.0,
                    "component_force_imag": -4.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
                {
                    "omega_e_sqrt_l_over_g": 2.0,
                    "omega_rad_s": 2.0,
                    "candidate_name": "end_term",
                    "component_force_real": -1.0,
                    "component_force_imag": -1.0,
                    "reference_force_real": -2.0,
                    "reference_force_imag": 50.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_journee_cell35_time_pressure_phase_candidate_audit(
                component_detail,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_journee_cell35_time_pressure_phase_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_cell35_time_pressure_phase_candidate_summary.csv").exists())

        self.assertEqual(len(detail), 10)
        best = summary.iloc[0]
        self.assertNotEqual(best["candidate_name"], "current_time_plus_gradient_plus_end")
        self.assertIn(
            best["diagnostic_conclusion"],
            {
                "time_pressure_phase_candidate_best_but_still_unclosed",
                "time_pressure_phase_candidate_closes_cell35_but_needs_full_gate_trace",
            },
        )
        self.assertEqual(int(best["improved_frequency_count"]), 2)
        self.assertLess(
            float(best["median_residual_norm"]),
            float(
                summary[
                    summary["candidate_name"].astype(str).eq("current_time_plus_gradient_plus_end")
                ]["median_residual_norm"].iloc[0]
            ),
        )
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_time_pressure_harmonic_convention_trace_rejects_local_sign_flip(self):
        coefficients = ["A33", "B33", "A35", "B35", "A53", "B53", "A55", "B55"]
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "gate_error_ratio": 10.0 + index,
                    "matched_selected_pressure_time_formula_ratio_median": 1.0,
                }
                for index, coefficient in enumerate(coefficients)
            ]
        )
        pressure_detail = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "candidate_name": "time_derivative_flipped_keep_gradient_end",
                    "gate_error_ratio": 8.0 + index if index < 4 else 20.0 + index,
                    "status": "FAIL",
                }
                for index, coefficient in enumerate(coefficients)
            ]
        )
        pressure_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "time_derivative_flipped_keep_gradient_end",
                    "pass_count": 0,
                    "fail_count": 8,
                    "median_gate_error_ratio": 14.0,
                    "max_gate_error_ratio": 27.0,
                }
            ]
        )
        cell35_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "time_pressure_sign_flipped_plus_gradient_end",
                    "pass_count": 1,
                    "row_count": 2,
                    "median_residual_norm": 1.006,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_time_pressure_harmonic_convention_trace_audit(
                comparison,
                pressure_detail,
                pressure_summary,
                cell35_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_harmonic_convention_trace_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_time_pressure_harmonic_convention_trace_summary.csv").exists())

        self.assertEqual(len(detail), 8)
        self.assertTrue(bool(summary["formula_ratio_all_current"].iloc[0]))
        self.assertEqual(int(summary["sign_flip_pass_count"].iloc[0]), 0)
        self.assertEqual(int(summary["sign_flip_improved_count"].iloc[0]), 4)
        self.assertEqual(int(summary["sign_flip_worsened_count"].iloc[0]), 4)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "time_pressure_sign_flip_is_cell35_clue_but_not_global_convention",
        )
        self.assertEqual(
            summary["current_pressure_formula"].iloc[0],
            "p_time = -rho*i*omega*phi",
        )
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_fixed_control_surface_boundary_gap_audit_merges_open_blockers(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                }
                for coefficient in ["B33", "A35", "B35", "A55", "B55"]
            ]
        )
        force_routes = pd.DataFrame(
            [
                {
                    "force_assembly_route": "eq31_pressure_gradient_plus_row_measure_transport",
                    "row_count": 8,
                    "pass_count": 0,
                    "fail_count": 8,
                    "max_gate_error_ratio": 126.0,
                }
            ]
        )
        row_end = pd.DataFrame(
            [
                {
                    "interaction_name": "plus_row_measure",
                    "end_contour_helped_count": 1,
                    "end_contour_hurt_count": 5,
                    "required_end_scale_min": -11.0,
                    "required_end_scale_max": 2.0,
                    "required_end_scale_spread": 13.0,
                }
            ]
        )
        b33_endpoint = pd.DataFrame(
            [
                {
                    "b33_current_default_gate_error_ratio": 22.0,
                    "b33_row_measure_without_end_gate_error_ratio": 3.2,
                    "b33_row_measure_plus_full_endpoint_forward_gate_error_ratio": 0.35,
                    "required_current_end_scale_after_row_measure": 2.05,
                    "current_end_to_endpoint_forward_ratio": 0.44,
                }
            ]
        )
        endpoint_routes = pd.DataFrame(
            [
                {
                    "candidate_name": "row_measure_plus_configured_endpoint_forward",
                    "row_count": 8,
                    "pass_count": 1,
                    "fail_count": 7,
                    "max_gate_error_ratio": 145.0,
                    "passing_coefficients": "B33",
                    "failing_coefficients": "A35,B35,A55,B55",
                    "diagnostic_conclusion": "endpoint_forward_candidate_is_local_not_global",
                }
            ]
        )
        pitch_panel = pd.DataFrame(
            [
                {
                    "coefficient": "A55",
                    "pressure_measure_residual_norm": 0.0,
                    "stokes_measure_residual_norm": 0.0,
                    "product_rule_residual_norm": 0.004,
                    "row_gradient_negative_stokes_residual_norm": 1.17,
                    "row_gradient_over_negative_stokes_lsq_scale": 0.49,
                }
            ]
        )
        pitch_consistency = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "pitch_fixed_measure_scale_mismatch_not_startup_window",
                }
            ]
        )
        pitch_scale = pd.DataFrame(
            [
                {
                    "candidate_name": "scale_forward_gradient_plus_end_moment_keep_time",
                    "row_count": 2,
                    "pass_count": 1,
                    "fail_count": 1,
                    "max_gate_error_ratio": 4.33,
                    "required_complex_scale_abs": 0.8,
                    "required_complex_scale_phase_deg": -30.0,
                    "imag_to_real_abs_ratio": 0.2,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_fixed_control_surface_boundary_gap_audit(
                comparison,
                force_routes,
                row_end,
                b33_endpoint,
                endpoint_routes,
                pitch_panel,
                pitch_consistency,
                pitch_scale,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_fixed_control_surface_boundary_gap_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_fixed_control_surface_boundary_gap_summary.csv").exists())

        self.assertEqual(len(detail), 5)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "fixed_control_surface_boundary_gap_confirmed",
        )
        self.assertGreaterEqual(int(summary["open_gap_count"].iloc[0]), 4)
        self.assertTrue(bool(summary["row_measure_helps_b33"].iloc[0]))
        self.assertTrue(bool(summary["current_end_contour_mixed_help_hurt"].iloc[0]))
        self.assertTrue(bool(summary["endpoint_forward_proxy_local_only"].iloc[0]))
        self.assertTrue(bool(summary["pitch_measure_mismatch"].iloc[0]))
        self.assertTrue(bool(summary["pitch_complex_unclosed"].iloc[0]))
        self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())
        self.assertTrue(summary["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_control_surface_end_contour_audit_compares_body_and_control_end_terms(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 1.0,
                    "computed_value": 2.0,
                    "gate_error_ratio": 10.0,
                    "effective_abs_tolerance": 0.1,
                    "matched_end_term_component_value": 0.8,
                    "matched_control_surface_end_term_component_value": -0.2,
                },
                {
                    "coefficient": "A35",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 0.5,
                    "computed_value": 0.4,
                    "gate_error_ratio": 1.0,
                    "effective_abs_tolerance": 0.1,
                    "matched_end_term_component_value": 0.1,
                    "matched_control_surface_end_term_component_value": 0.3,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_control_surface_end_contour_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_control_surface_end_contour_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_control_surface_end_contour_summary.csv").exists())

        self.assertEqual(len(detail), 2)
        b33 = detail[detail["coefficient"].eq("B33")].iloc[0]
        self.assertAlmostEqual(
            float(b33["candidate_replace_body_end_with_control_surface_end_value"]),
            1.0,
        )
        self.assertEqual(b33["candidate_status"], "PASS")
        self.assertEqual(int(summary["candidate_pass_count"].iloc[0]), 1)
        self.assertEqual(int(summary["candidate_fail_count"].iloc[0]), 1)
        self.assertEqual(int(summary["candidate_improves_count"].iloc[0]), 1)
        self.assertEqual(summary["candidate_default_gate_eligible"].iloc[0], "false")
        self.assertTrue(detail["candidate_default_gate_eligible"].astype(str).str.lower().eq("false").all())

    def test_ma2005_body_potential_frequency_entry_audit_localizes_kinematic_tracking(self):
        paired_table = pd.DataFrame(
            [
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 2.0,
                    "computed_value": 10.0,
                    "matched_heave_body_normal_velocity_norm_max": 1.0,
                    "matched_heave_body_potential_norm_max": 4.0,
                    "matched_heave_body_pressure_time_derivative_norm_max": 4.0,
                    "matched_heave_body_pressure_forward_speed_norm_max": 2.0,
                },
                {
                    "coefficient": "B33",
                    "matrix_cell": "33",
                    "omega_e_sqrt_l_over_g": 2.0,
                    "reference_value": 1.0,
                    "computed_value": 10.0,
                    "matched_heave_body_normal_velocity_norm_max": 2.0,
                    "matched_heave_body_potential_norm_max": 8.0,
                    "matched_heave_body_pressure_time_derivative_norm_max": 16.0,
                    "matched_heave_body_pressure_forward_speed_norm_max": 4.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_body_potential_frequency_entry_audit(
                paired_table,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_body_potential_frequency_entry_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_body_potential_frequency_entry_summary.csv").exists())

        b33 = detail[detail["coefficient"].astype(str).eq("B33")].iloc[0]
        self.assertEqual(
            b33["diagnostic_conclusion"],
            "body_potential_tracks_kinematic_boundary_condition_only",
        )
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "body_potential_frequency_entry_tracks_kinematic_condition_only",
        )
        self.assertTrue(bool(b33["body_potential_tracks_body_condition"]))
        self.assertTrue(bool(b33["body_potential_frequency_filter_missing"]))
        self.assertAlmostEqual(float(b33["body_condition_frequency_sensitivity_ratio"]), 0.5)
        self.assertAlmostEqual(float(b33["body_potential_frequency_sensitivity_ratio"]), 0.5)
        self.assertAlmostEqual(float(b33["body_potential_to_condition_sensitivity_ratio"]), 1.0)
        self.assertAlmostEqual(float(b33["time_pressure_to_potential_frequency_gain_median"]), 1.0)
        self.assertAlmostEqual(float(b33["forward_pressure_to_potential_gradient_proxy_median"]), 0.5)
        self.assertEqual(int(summary["tracked_body_condition_count"].iloc[0]), 1)
        self.assertEqual(int(summary["body_potential_filter_missing_count"].iloc[0]), 1)
        self.assertEqual(int(summary["computed_frequency_invariant_count"].iloc[0]), 1)
        self.assertIn("B33", str(summary["affected_coefficients"].iloc[0]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_local_time_phase_frequency_sensitivity_audit_keeps_candidates_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                    "normalization_scale": 1.0,
                    "hull_length_m": 3.0,
                    "provider_route": "matched_bie_station_sweep",
                }
            ]
        )

        def fake_computed(row, **_kwargs):
            omega = float(row["omega_e_sqrt_l_over_g"])
            apply_phase = bool(row.get("matched_apply_local_time_phase", False))
            gradient = bool(row.get("matched_local_time_phase_gradient_correction", False))
            if not apply_phase:
                value = 2.0
            elif gradient:
                value = 0.5 + 0.1 * omega
            else:
                value = 3.0 + 0.5 * omega
            return {
                "computed_value": value,
                "raw_value": value,
                "normalization": "ma2005",
                "provider_route": "matched_bie_station_sweep",
                "provider_formulation": "matched_bie",
                "solver_status": "synthetic",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        (
                            "hull,speed_case,motion_test,amplitude,omega_e_sqrt_l_over_g,coefficient,"
                            "reference_value,normalization,source_table,source_url,source_lines,source_note"
                        ),
                        "wigley_iii,Fn0.4,forced_heave,z_a=0.050m,1.68,A33,1.0,ma2005,Table 2-III,https://example.test,1788,heave",
                        "wigley_iii,Fn0.4,forced_heave,z_a=0.050m,2.23,A33,1.4,ma2005,Table 2-III,https://example.test,1789,heave",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_local_time_phase_frequency_sensitivity_audit(
                    comparison,
                    tmp_path,
                    "synthetic",
                    reference_path=reference_path,
                )

            self.assertTrue((tmp_path / "synthetic_local_time_phase_frequency_sensitivity_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_local_time_phase_frequency_sensitivity_summary.csv").exists())

        self.assertEqual(len(detail), 6)
        self.assertEqual(len(summary), 3)
        default = summary[summary["variant"].eq("default_no_local_time_phase")].iloc[0]
        phase = summary[summary["variant"].eq("local_time_phase_only")].iloc[0]
        self.assertEqual(default["diagnostic_conclusion"], "default_frequency_invariant_despite_reference_variation")
        self.assertEqual(phase["diagnostic_conclusion"], "candidate_is_frequency_sensitive_but_gate_still_fails")
        self.assertFalse(bool(default["candidate_default_gate_eligible"]))
        self.assertFalse(bool(phase["candidate_default_gate_eligible"]))
        self.assertGreater(float(default["reference_frequency_sensitivity_ratio"]), 0.0)
        self.assertAlmostEqual(float(default["computed_frequency_sensitivity_ratio"]), 0.0)
        self.assertGreater(float(phase["computed_frequency_sensitivity_ratio"]), 0.0)

    def test_ma2005_local_time_phase_component_audit_tracks_component_changes(self):
        comparison = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                    "length_m": 3.0,
                    "beam_m": 0.3,
                    "draft_m": 0.1875,
                    "displacement_volume_m3": 0.078,
                    "station_count": 41,
                }
            ]
        )

        def fake_computed(row, **_kwargs):
            omega = float(row["omega_e_sqrt_l_over_g"])
            apply_phase = bool(row.get("matched_apply_local_time_phase", False))
            gradient_correction = bool(row.get("matched_local_time_phase_gradient_correction", False))
            time_value = 2.0 if not apply_phase else 2.0 + 0.4 * omega
            gradient_value = 0.1 if not gradient_correction else 0.1 + 0.2 * omega
            computed = time_value + gradient_value
            return {
                "computed_value": computed,
                "raw_value": computed,
                "normalization": "ma2005",
                "normalization_scale": 1.0,
                "provider_route": "matched_bie_station_sweep",
                "provider_formulation": "matched_bie",
                "solver_status": "synthetic",
                "matched_time_derivative_component_value": time_value,
                "matched_pressure_gradient_component_value": gradient_value,
                "matched_stokes_body_forward_component_value": 0.0,
                "matched_end_term_component_value": 0.0,
                "matched_time_derivative_component_raw": time_value,
                "matched_pressure_gradient_component_raw": gradient_value,
                "matched_stokes_body_forward_component_raw": 0.0,
                "matched_end_term_component_raw": 0.0,
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        "hull,speed_case,motion_test,omega_e_sqrt_l_over_g,coefficient,reference_value,normalization",
                        "wigley_iii,Fn0.4,forced_heave,1.0,A33,1.0,ma2005",
                        "wigley_iii,Fn0.4,forced_heave,2.0,A33,0.6,ma2005",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_local_time_phase_component_audit(
                    comparison,
                    tmp_path,
                    "synthetic",
                    reference_path=reference_path,
                )

            self.assertTrue((tmp_path / "synthetic_local_time_phase_component_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_local_time_phase_component_summary.csv").exists())

        self.assertEqual(len(detail), 6)
        self.assertEqual(len(summary), 3)
        default = summary[summary["variant"].eq("default_no_local_time_phase")].iloc[0]
        phase = summary[summary["variant"].eq("local_time_phase_only")].iloc[0]
        chain = summary[summary["variant"].eq("local_time_phase_with_gradient_correction")].iloc[0]
        self.assertEqual(
            default["diagnostic_conclusion"],
            "default_time_component_frequency_invariant_for_time_pressure_target",
        )
        self.assertEqual(
            phase["diagnostic_conclusion"],
            "local_time_phase_changes_time_component_but_gate_still_fails",
        )
        self.assertEqual(
            chain["diagnostic_conclusion"],
            "local_time_phase_changes_time_component_but_gate_still_fails",
        )
        self.assertAlmostEqual(float(default["time_derivative_component_sensitivity_ratio"]), 0.0)
        self.assertGreater(float(phase["time_derivative_component_sensitivity_ratio"]), 0.0)
        self.assertGreater(float(chain["median_abs_pressure_gradient_delta_vs_default"]), 0.0)
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_gate1_reference_trace_freezes_ma_rows_and_journee_nearest(self):
        comparison = pd.DataFrame(
            [
                {
                    "row": 0,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                },
                {
                    "row": 0,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "B33",
                    "omega_e_sqrt_l_over_g": 2.23,
                    "reference_value": 2.0,
                    "normalization": "ma2005",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ma_path = tmp_path / "ma.csv"
            ma_path.write_text(
                "\n".join(
                    [
                        "hull,speed_case,omega_e_sqrt_l_over_g,coefficient,reference_value,normalization,source_figure,source_note",
                        "wigley_iii,Fn0.4,1.0,A33,1.0,ma2005,Fig. 11,figure row",
                        "wigley_iii,Fn0.4,2.23,B33,2.0,ma2005,Fig. 12,figure row",
                    ]
                ),
                encoding="utf-8",
            )
            journee_path = tmp_path / "journee.csv"
            journee_path.write_text(
                "\n".join(
                    [
                        "coefficient,omega_e_sqrt_l_over_g,reference_value,source_table,source_note",
                        "A33,1.68,1.035,Table 2-III,integrated coefficient",
                        "B33,2.23,2.008,Table 2-III,integrated coefficient",
                    ]
                ),
                encoding="utf-8",
            )
            detail, summary = _write_ma2005_gate1_reference_trace(
                comparison,
                tmp_path,
                "synthetic",
                ma_reference_path=ma_path,
                journee_reference_path=journee_path,
            )
            self.assertTrue((tmp_path / "synthetic_gate1_reference_trace.csv").exists())
            self.assertTrue((tmp_path / "synthetic_gate1_reference_trace_summary.csv").exists())

        a33 = detail[detail["coefficient"].eq("A33")].iloc[0]
        b33 = detail[detail["coefficient"].eq("B33")].iloc[0]
        self.assertTrue(bool(a33["ma_source_row_matched"]))
        self.assertEqual(a33["source_figure"], "Fig. 11")
        self.assertEqual(
            a33["reference_trace_status"],
            "MA_SOURCE_ROW_WITH_JOURNEE_VALUE_CLOSE_BUT_FREQUENCY_MISMATCH",
        )
        self.assertEqual(
            b33["reference_trace_status"],
            "MA_SOURCE_ROW_WITH_JOURNEE_NEAREST_ROW_MATCH",
        )
        self.assertEqual(b33["source_figure"], "Fig. 12")
        self.assertEqual(int(summary["source_row_match_count"].iloc[0]), 2)
        self.assertEqual(int(summary["journee_frequency_mismatch_count"].iloc[0]), 1)
        self.assertEqual(
            summary["reference_trace_status"].iloc[0],
            "GATE1_REFERENCE_FIXED_TO_MA_FIGURE_ROWS_WITH_JOURNEE_FREQUENCY_MISMATCH",
        )
        self.assertFalse(bool(summary["default_promotion_allowed_by_reference_trace"].iloc[0]))

    def test_ma2005_reference_root_consistency_detects_sparse_active_subset(self):
        comparison = pd.DataFrame(
            [
                {
                    "row": 0,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                },
                {
                    "row": 1,
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "B33",
                    "omega_e_sqrt_l_over_g": 2.0,
                    "reference_value": 2.1,
                    "normalization": "ma2005",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            active_path = tmp_path / "active.csv"
            canonical_path = tmp_path / "canonical.csv"
            active_path.write_text(
                "\n".join(
                    [
                        "hull,speed_case,omega_e_sqrt_l_over_g,coefficient,reference_value,normalization",
                        "wigley_iii,Fn0.4,1.0,A33,1.0,ma2005",
                        "wigley_iii,Fn0.4,2.0,B33,2.1,ma2005",
                    ]
                ),
                encoding="utf-8",
            )
            canonical_path.write_text(
                "\n".join(
                    [
                        "hull,speed_case,omega_e_sqrt_l_over_g,coefficient,reference_value,normalization",
                        "wigley_iii,Fn0.4,1.0,A33,1.0,ma2005",
                        "wigley_iii,Fn0.4,2.0,A33,0.65,ma2005",
                        "wigley_iii,Fn0.4,2.0,B33,2.1,ma2005",
                    ]
                ),
                encoding="utf-8",
            )
            detail, summary = _write_ma2005_reference_root_consistency_audit(
                comparison,
                tmp_path,
                "synthetic",
                active_reference_path=active_path,
                canonical_reference_path=canonical_path,
            )
            self.assertTrue((tmp_path / "synthetic_reference_root_consistency_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_reference_root_consistency_summary.csv").exists())

        row = summary.iloc[0]
        self.assertEqual(int(row["active_reference_row_count"]), 2)
        self.assertEqual(int(row["canonical_reference_row_count"]), 3)
        self.assertEqual(int(row["comparison_row_count"]), 2)
        self.assertEqual(int(row["active_rows_found_in_canonical"]), 2)
        self.assertEqual(int(row["canonical_extra_row_count"]), 1)
        self.assertTrue(bool(row["active_is_sparse_canonical_subset"]))
        self.assertFalse(bool(row["active_is_canonical_complete"]))
        self.assertEqual(
            row["reference_root_consistency_status"],
            "ACTIVE_REFERENCE_IS_SPARSE_CANONICAL_SUBSET",
        )
        a33 = detail[detail["coefficient"].eq("A33")].iloc[0]
        self.assertEqual(int(a33["active_reference_row_count_for_coefficient"]), 1)
        self.assertEqual(int(a33["canonical_reference_row_count_for_coefficient"]), 2)
        self.assertTrue(bool(a33["active_is_sparse_subset_for_coefficient"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_journee_frequency_gate_probe_uses_nearest_tabulated_rows(self):
        comparison = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "coefficient": "A33",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "reference_value": 1.0,
                    "normalization": "ma2005",
                    "length_m": 3.0,
                    "beam_m": 0.3,
                    "draft_m": 0.1875,
                    "displacement_volume_m3": 0.078,
                    "station_count": 41,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "journee.csv"
            reference_path.write_text(
                "\n".join(
                    [
                        "coefficient,omega_e_sqrt_l_over_g,reference_value,source_table,source_url,source_lines,source_note",
                        "A33,1.68,1.035,Table 2-III,https://example.test,1788,integrated coefficient",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "planing_seakeeping.validation._ma2005_computed_coefficient",
                return_value={
                    "computed_value": 1.02,
                    "raw_value": 1.02,
                    "provider_route": "matched_bie_station_sweep",
                    "provider_formulation": "matched_bie",
                    "solver_status": "synthetic",
                },
            ) as computed:
                detail, summary = _write_ma2005_journee_frequency_gate_probe(
                    comparison,
                    tmp_path,
                    "synthetic",
                    reference_path=reference_path,
                )
            self.assertTrue((tmp_path / "synthetic_journee_frequency_gate_probe.csv").exists())
            self.assertTrue((tmp_path / "synthetic_journee_frequency_gate_probe_summary.csv").exists())

        self.assertAlmostEqual(float(computed.call_args.args[0]["omega_e_sqrt_l_over_g"]), 1.68)
        self.assertAlmostEqual(float(computed.call_args.args[0]["reference_value"]), 1.035)
        self.assertEqual(detail["provider_route"].iloc[0], "matched_bie_station_sweep")
        self.assertEqual(detail["status"].iloc[0], "PASS")
        self.assertEqual(int(summary["pass_count"].iloc[0]), 1)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "journee_frequency_probe_all_rows_pass",
        )
        self.assertFalse(bool(summary["candidate_default_gate_eligible"].iloc[0]))

    def test_ma2005_reference_pairing_policy_audit_freezes_active_ma_figure_scope(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": "A33", "omega_e_sqrt_l_over_g": 1.0, "reference_value": 1.0},
                {"coefficient": "B33", "omega_e_sqrt_l_over_g": 2.0, "reference_value": 2.1},
            ]
        )
        gate_trace = pd.DataFrame(
            [
                {
                    "row_count": 2,
                    "source_row_match_count": 2,
                    "journee_frequency_mismatch_count": 2,
                    "journee_value_close_count": 2,
                    "reference_trace_status": "GATE1_REFERENCE_FIXED_TO_MA_FIGURE_ROWS_WITH_JOURNEE_FREQUENCY_MISMATCH",
                }
            ]
        )
        ladder = pd.DataFrame(
            [
                {
                    "gate1_ladder_mismatch_count": 2,
                    "journee_ladder_match_count": 4,
                    "frequency_trace_status": "gate1_sparse_figure_frequencies_do_not_match_a1_ladder_but_journee_table_does",
                }
            ]
        )
        journee_table = pd.DataFrame(
            [
                {
                    "frequency_mismatch_count": 2,
                    "value_close_count": 2,
                    "external_integrated_reference_status": "FOUND_JOURNEE_INTEGRATED_COEFFICIENT_TABLES_NOT_SECTION_PRESSURE",
                }
            ]
        )
        journee_probe = pd.DataFrame(
            [
                {
                    "pass_count": 0,
                    "fail_count": 2,
                    "diagnostic_conclusion": "journee_frequency_probe_still_fails_default_provider",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_reference_pairing_policy_audit(
                comparison,
                gate_trace,
                ladder,
                journee_table,
                journee_probe,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_reference_pairing_policy_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_reference_pairing_policy_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 5)
        self.assertFalse(detail["allows_default_reference_switch"].astype(bool).any())
        self.assertFalse(detail["allows_equation_candidate_promotion"].astype(bool).any())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(row["active_hard_gate_reference_policy"], "active_ma_figure_digitized_sparse_gate_retained")
        self.assertIn("not_journee_a1_frequency_ladder", row["reference_pairing_conclusion"])
        self.assertIn("journee_frequency_switch_does_not_close", row["reference_pairing_conclusion"])
        self.assertFalse(bool(row["default_reference_switch_allowed"]))
        self.assertFalse(bool(row["candidate_default_gate_eligible"]))

    def test_ma2005_coefficient_conversion_chain_audit_writes_simple_variants(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": 2.0,
                    "raw_computed_value": 200.0,
                    "gate_error_ratio": 10.0,
                    "hull_length_m": 2.0,
                    "displacement_volume_m3": 0.1,
                    "rho_water_kg_m3": 1000.0,
                    "gravity_m_s2": 9.81,
                    "omega_e_rad_s": 2.0,
                },
                {
                    "coefficient": "B33",
                    "reference_value": 1.0,
                    "computed_value": 2.0,
                    "raw_computed_value": 200.0,
                    "gate_error_ratio": 10.0,
                    "hull_length_m": 2.0,
                    "displacement_volume_m3": 0.1,
                    "rho_water_kg_m3": 1000.0,
                    "gravity_m_s2": 9.81,
                    "omega_e_rad_s": 2.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_coefficient_conversion_chain_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_coefficient_conversion_chain_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_coefficient_conversion_chain_summary.csv").exists())

        self.assertIn("length_power_0", set(detail["variant_name"]))
        self.assertIn("damping_divide_omega", set(detail["variant_name"]))
        self.assertIn("damping_inverse_sqrt", set(detail["variant_name"]))
        self.assertIn("added_mass_sign_flipped_current", set(detail["variant_name"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        self.assertTrue(summary["row_count"].astype(int).gt(0).all())

    def test_ma2005_body_condition_unit_chain_audit_writes_unit_scale_proxies(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": 2.0,
                    "gate_error_ratio": 10.0,
                    "tolerance": 0.15,
                    "hull_length_m": 3.0,
                    "omega_e_sqrt_l_over_g": 2.0,
                },
                {
                    "coefficient": "B55",
                    "reference_value": 1.0,
                    "computed_value": 3.0,
                    "gate_error_ratio": 10.0,
                    "tolerance": 0.15,
                    "hull_length_m": 3.0,
                    "omega_e_sqrt_l_over_g": 2.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_body_condition_unit_chain_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_body_condition_unit_chain_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_body_condition_unit_chain_summary.csv").exists())

        self.assertIn("current_unit_displacement", set(detail["variant_name"]))
        self.assertIn("remove_dimensional_omega_unit_velocity_proxy", set(detail["variant_name"]))
        self.assertIn("remove_nondimensional_omega2_unit_acceleration_proxy", set(detail["variant_name"]))
        self.assertTrue(detail["phase_rotation_not_represented"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        self.assertTrue(summary["row_count"].astype(int).gt(0).all())

    def test_ma2005_time_pressure_scale_origin_audit_keeps_untraced_constants_diagnostic(self):
        one_over_pi_squared = 1.0 / (math.pi**2)
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 59.0,
                    "tolerance": 0.15,
                    "near_zero_abs_tolerance": 0.0,
                    "matched_selected_required_scale_to_reference": one_over_pi_squared,
                    "ma2005_candidate_length_power_2_value": 1.0,
                    "ma2005_candidate_length_power_2_gate_error_ratio": 0.0,
                    "ma2005_eq34_documented_length_power": 0,
                    "ma2005_best_length_power_candidate": "length_power_2",
                    "ma2005_best_length_power_candidate_status": "PASS",
                },
                {
                    "coefficient": "A53",
                    "reference_value": 0.15,
                    "computed_value": 0.15 * math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 30.0,
                    "tolerance": 0.30,
                    "near_zero_abs_tolerance": 0.0,
                    "matched_selected_required_scale_to_reference": one_over_pi_squared,
                    "ma2005_candidate_length_power_2_value": 0.47,
                    "ma2005_candidate_length_power_2_gate_error_ratio": 7.0,
                    "ma2005_eq34_documented_length_power": 1,
                    "ma2005_best_length_power_candidate": "length_power_2",
                    "ma2005_best_length_power_candidate_status": "FAIL",
                },
            ]
        )
        self_block = pd.DataFrame(
            [
                {
                    "candidate_name": "inner_a_normalized_by_2pi",
                    "pass_count": 0,
                    "max_gate_error_ratio": 671.0,
                }
            ]
        )
        coupling = pd.DataFrame(
            [
                {
                    "candidate_name": "known_phi_free_rhs_one_over_2pi",
                    "pass_count": 0,
                    "max_gate_error_ratio": 118.0,
                },
                {
                    "candidate_name": "known_phi_free_rhs_2pi",
                    "pass_count": 0,
                    "max_gate_error_ratio": 293.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_time_pressure_scale_origin_audit(
                comparison,
                self_block,
                coupling,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_scale_origin_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_time_pressure_scale_origin_summary.csv").exists())

        self.assertEqual(set(detail["coefficient"]), {"A33", "A53"})
        self.assertTrue(detail["nearest_simple_constant"].astype(str).eq("one_over_pi_squared").all())
        self.assertTrue(detail["one_over_pi_squared_passes_this_row"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertEqual(int(summary["one_over_pi_squared_pass_count"].iloc[0]), 2)
        self.assertEqual(int(summary["length_power2_pass_count"].iloc[0]), 1)
        self.assertEqual(int(summary["inner_a_normalized_by_2pi_pass_count"].iloc[0]), 0)
        self.assertEqual(int(summary["known_phi_free_rhs_one_over_2pi_pass_count"].iloc[0]), 0)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "one_over_pi_squared_matches_a33_a53_but_is_untraced_and_not_full_gate",
        )
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_time_pressure_pi_kernel_trace_excludes_untraced_pi_squared(self):
        one_over_pi_squared = 1.0 / (math.pi**2)
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": math.pi**2,
                    "matched_inner_a_scale": 1.0,
                    "matched_inner_b_scale": 1.0,
                    "matched_inner_diagonal_sign": -1.0,
                    "matched_time_step_scale": 1.0,
                    "ma2005_eq34_normalization_formula": "A33 = raw_a33 / (rho*displacement_volume)",
                },
                {
                    "coefficient": "A53",
                    "reference_value": 0.15,
                    "computed_value": 0.15 * math.pi**2,
                    "matched_inner_a_scale": 1.0,
                    "matched_inner_b_scale": 1.0,
                    "matched_inner_diagonal_sign": -1.0,
                    "matched_time_step_scale": 1.0,
                    "ma2005_eq34_normalization_formula": "A53 = raw_a53 / (rho*displacement_volume*L)",
                },
            ]
        )
        origin_summary = pd.DataFrame(
            [
                {
                    "row_count": 2,
                    "required_scale_min": one_over_pi_squared,
                    "required_scale_max": one_over_pi_squared,
                    "one_over_pi_squared_pass_count": 2,
                    "one_over_pi_squared_max_gate_error_ratio": 0.0,
                    "diagnostic_conclusion": "one_over_pi_squared_matches_a33_a53_but_is_untraced_and_not_full_gate",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_time_pressure_pi_kernel_trace_audit(
                comparison,
                origin_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_pi_kernel_trace_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_time_pressure_pi_kernel_trace_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 5)
        self.assertFalse(detail["supports_one_over_pi_squared_default"].astype(bool).any())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertEqual(int(summary["supporting_trace_count"].iloc[0]), 0)
        self.assertFalse(bool(summary["eq34_pi_factor_present"].iloc[0]))
        self.assertEqual(summary["current_inner_a_scale_unique"].iloc[0], "1")
        self.assertEqual(summary["current_inner_b_scale_unique"].iloc[0], "1")
        self.assertEqual(summary["current_inner_diagonal_sign_unique"].iloc[0], "-1")
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "one_over_pi_squared_is_observed_fit_not_traced_to_a1_raw_kernel_or_eq34",
        )
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_time_pressure_formula_unit_chain_excludes_untraced_constant(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": "A33", "gate_error_ratio": 61.0, "status": "FAIL"},
                {"coefficient": "A53", "gate_error_ratio": 28.0, "status": "FAIL"},
                {"coefficient": "B35", "gate_error_ratio": 164.0, "status": "FAIL"},
            ]
        )
        body_condition_unit_summary = pd.DataFrame(
            [
                {
                    "variant_name": "remove_dimensional_omega2_unit_acceleration_proxy",
                    "pass_count": 1,
                }
            ]
        )
        body_potential_frequency_summary = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "body_potential_frequency_entry_tracks_kinematic_condition_only",
                }
            ]
        )
        harmonic_summary = pd.DataFrame(
            [
                {
                    "coefficient_count": 8,
                    "sign_flip_pass_count": 0,
                    "current_pressure_formula": "p_time = -rho*i*omega*phi",
                    "diagnostic_conclusion": "time_pressure_sign_flip_is_cell35_clue_but_not_global_convention",
                }
            ]
        )
        scale_origin_summary = pd.DataFrame(
            [
                {
                    "row_count": 2,
                    "one_over_pi_squared_pass_count": 2,
                    "one_over_pi_squared_max_gate_error_ratio": 0.2,
                    "diagnostic_conclusion": "one_over_pi_squared_matches_a33_a53_but_is_untraced_and_not_full_gate",
                }
            ]
        )
        pi_trace_summary = pd.DataFrame(
            [
                {
                    "supporting_trace_count": 0,
                    "eq34_pi_factor_present": False,
                    "diagnostic_conclusion": "one_over_pi_squared_is_observed_fit_not_traced_to_a1_raw_kernel_or_eq34",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_time_pressure_formula_unit_chain_audit(
                comparison,
                body_condition_unit_summary,
                body_potential_frequency_summary,
                harmonic_summary,
                scale_origin_summary,
                pi_trace_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_formula_unit_chain_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_time_pressure_formula_unit_chain_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 6)
        self.assertFalse(detail["supports_default_time_pressure_change"].astype(bool).any())
        self.assertTrue(detail["blocks_default_time_pressure_change"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_fail_count"]), 2)
        self.assertEqual(int(row["blocking_trace_count"]), len(detail))
        self.assertEqual(int(row["supporting_default_change_count"]), 0)
        self.assertEqual(int(row["one_over_pi_squared_pass_count"]), 2)
        self.assertFalse(bool(row["one_over_pi_squared_formula_traced"]))
        self.assertFalse(bool(row["harmonic_sign_flip_global"]))
        self.assertEqual(
            row["diagnostic_conclusion"],
            "one_over_pi_squared_excluded_by_formula_unit_harmonic_kernel_chain",
        )
        self.assertIn("reference-frequency", row["next_required_evidence"])
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_body_potential_normalization_trace_keeps_open_section_scale_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": "A33", "gate_error_ratio": 61.0, "status": "FAIL"},
                {"coefficient": "A53", "gate_error_ratio": 28.0, "status": "FAIL"},
            ]
        )
        heave_pressure = pd.DataFrame(
            [
                {
                    "required_scale_min": 0.098,
                    "required_scale_max": 0.106,
                    "open_section_independent_reference_status": "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE",
                }
            ]
        )
        open_section = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "median_independent_to_matched_body_potential_norm_ratio": 0.041,
                    "independent_reference_status": "EXPERIMENTAL_OPEN_SECTION_BEM_REFERENCE_NOT_HARD_GATE",
                },
                {
                    "coefficient": "A53",
                    "median_independent_to_matched_body_potential_norm_ratio": 0.039,
                    "independent_reference_status": "EXPERIMENTAL_OPEN_SECTION_BEM_REFERENCE_NOT_HARD_GATE",
                },
            ]
        )
        body_unit = pd.DataFrame([{"pass_count": 1}])
        body_frequency = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "body_potential_frequency_entry_tracks_kinematic_condition_only",
                }
            ]
        )
        formula_unit = pd.DataFrame(
            [
                {
                    "one_over_pi_squared_formula_traced": False,
                }
            ]
        )
        reference_policy = pd.DataFrame(
            [
                {
                    "active_hard_gate_reference_policy": "active_ma_figure_digitized_sparse_gate_retained",
                    "reference_pairing_conclusion": "gate1_reference_is_ma_figure_digitization_not_journee_a1_frequency_ladder",
                }
            ]
        )
        closed = pd.DataFrame(
            [
                {
                    "pressure_sign_corrected_relative_error_finest": 0.0027,
                    "potential_alignment_scale_to_analytic_finest": -1.0028,
                    "diagnostic_conclusion": "closed_cylinder_exposes_inner_pressure_sign_reversal",
                }
            ]
        )
        chain = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "closed_section_inner_chain_magnitude_recovers_analytic_added_mass_after_explicit_sign_correction",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_body_potential_normalization_trace_audit(
                comparison,
                heave_pressure,
                open_section,
                body_unit,
                body_frequency,
                formula_unit,
                reference_policy,
                tmp_path,
                "synthetic",
                closed_cylinder_summary=closed,
                heave_time_pressure_chain_summary=chain,
            )
            self.assertTrue((tmp_path / "synthetic_body_potential_normalization_trace_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_body_potential_normalization_trace_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 5)
        self.assertFalse(detail["supports_default_body_potential_rescale"].astype(bool).any())
        self.assertTrue(detail["blocks_default_body_potential_rescale"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_fail_count"]), 2)
        self.assertEqual(int(row["supporting_default_rescale_count"]), 0)
        self.assertLess(float(row["open_section_median_potential_norm_ratio_max"]), 0.2)
        self.assertFalse(bool(row["time_pressure_scale_formula_traced"]))
        self.assertEqual(
            row["diagnostic_conclusion"],
            "closed_inner_chain_passes_but_open_wigley_body_potential_normalization_untraced",
        )
        self.assertIn("open-Wigley section", row["next_required_evidence"])
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_body_potential_time_pressure_chain_audit_aggregates_current_blocker(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "reference_value": 1.0,
                    "gate_error_ratio": 61.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 1.4,
                    "reference_value": 0.15,
                    "gate_error_ratio": 28.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "B33",
                    "computed_value": 9.0,
                    "reference_value": 2.1,
                    "gate_error_ratio": 22.0,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                },
            ]
        )
        state = pd.DataFrame(
            [
                {
                    "state_transfer_reconstruction_pass_count": 8,
                    "state_transfer_reconstruction_row_count": 8,
                    "state_transfer_max_update_relative_residual": 0.0,
                    "state_transfer_max_transfer_relative_residual": 0.0,
                    "diagnostic_conclusion": "a1_eq19_22_state_transfer_reconstructs_but_eq23_rhs_body_potential_scale_remains",
                }
            ]
        )
        rhs = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "source_reconstruction_status": "PASS",
                    "max_source_sum_relative_residual": 1.0e-15,
                    "dominant_source_by_median_body_potential_ratio": "inner_free_surface_potential",
                    "source_median_body_potential_ratios": "inner_free_surface_potential:0.9;body_normal_velocity:0.12",
                    "diagnostic_conclusion": "rhs_source_decomposition_identifies_inner_free_surface_potential_as_body_potential_dominant",
                },
                {
                    "coefficient": "A53",
                    "source_reconstruction_status": "PASS",
                    "max_source_sum_relative_residual": 1.0e-15,
                    "dominant_source_by_median_body_potential_ratio": "inner_free_surface_potential",
                    "source_median_body_potential_ratios": "inner_free_surface_potential:0.9;body_normal_velocity:0.12",
                    "diagnostic_conclusion": "rhs_source_decomposition_identifies_inner_free_surface_potential_as_body_potential_dominant",
                },
            ]
        )
        time_scale = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "station_integral_closure_residual": 1.0e-15,
                    "required_global_scale_to_reference_from_time_integral": 0.098,
                    "diagnostic_conclusion": "A33_A53_time_pressure_integral_is_closed_but_over_scaled_in_open_section_station_chain",
                },
                {
                    "coefficient": "A53",
                    "station_integral_closure_residual": -2.0e-16,
                    "required_global_scale_to_reference_from_time_integral": 0.106,
                    "diagnostic_conclusion": "A33_A53_time_pressure_integral_is_closed_but_over_scaled_in_open_section_station_chain",
                },
            ]
        )
        pi_trace = pd.DataFrame(
            [
                {
                    "one_over_pi_squared_value": 1.0 / (math.pi**2),
                    "one_over_pi_squared_pass_count": 2,
                    "supporting_trace_count": 0,
                    "diagnostic_conclusion": "one_over_pi_squared_is_observed_fit_not_traced_to_a1_raw_kernel_or_eq34",
                }
            ]
        )
        formula = pd.DataFrame(
            [
                {
                    "one_over_pi_squared_formula_traced": False,
                    "pressure_formula": "p_time = -rho*i*omega*phi",
                    "diagnostic_conclusion": "one_over_pi_squared_excluded_by_formula_unit_harmonic_kernel_chain",
                }
            ]
        )
        body_trace = pd.DataFrame(
            [
                {
                    "closed_section_corrected_relative_error": 0.0027,
                    "closed_section_potential_scale_to_analytic": -1.0028,
                    "open_section_median_potential_norm_ratio_min": 0.039,
                    "open_section_median_potential_norm_ratio_max": 0.041,
                    "open_section_reference_status": "EXPERIMENTAL_OPEN_SECTION_BEM_REFERENCE_NOT_HARD_GATE",
                    "diagnostic_conclusion": "closed_inner_chain_passes_but_open_wigley_body_potential_normalization_untraced",
                }
            ]
        )
        phi_trace = pd.DataFrame(
            [
                {
                    "supporting_default_normalization_change_count": 0,
                    "diagnostic_conclusion": "phi_phi_n_kernel_chain_traced_but_no_default_normalization_change_supported",
                }
            ]
        )
        fs_rhs_cross = pd.DataFrame(
            [
                {
                    "candidate_name": "known_phi_free_rhs_removed",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 3.33,
                    "median_gate_error_ratio": 1.87,
                    "a33_gate_error_ratio": 0.41,
                    "a53_gate_error_ratio": 3.33,
                    "a33_status": "PASS",
                    "a53_status": "FAIL",
                    "diagnostic_conclusion": "candidate_closes_a33_but_breaks_or_misses_a53",
                    "candidate_default_gate_eligible": False,
                    "candidate_exclusion_reason": "diagnostic-only split closure",
                },
                {
                    "candidate_name": "waterline_clipped_two_zone",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 21.56,
                    "median_gate_error_ratio": 10.79,
                    "a33_gate_error_ratio": 21.56,
                    "a53_gate_error_ratio": 0.018,
                    "a33_status": "FAIL",
                    "a53_status": "PASS",
                    "diagnostic_conclusion": "candidate_closes_a53_but_leaves_a33_blocked",
                    "candidate_default_gate_eligible": False,
                    "candidate_exclusion_reason": "diagnostic-only split closure",
                },
            ]
        )
        row_block = pd.DataFrame(
            [
                {
                    "candidate_name": "only_control_row_retained",
                    "row_count": 2,
                    "pass_count": 0,
                    "max_gate_error_ratio": 2.38,
                    "median_gate_error_ratio": 1.93,
                    "a33_gate_error_ratio": 1.47,
                    "a53_gate_error_ratio": 2.38,
                    "a33_status": "FAIL",
                    "a53_status": "FAIL",
                    "diagnostic_conclusion": "row_block_candidate_improves_subset_but_not_closed",
                    "candidate_default_gate_eligible": False,
                    "candidate_exclusion_reason": "diagnostic-only row-block candidate",
                },
                {
                    "candidate_name": "clip_two_zone_all_rows",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 21.56,
                    "median_gate_error_ratio": 10.79,
                    "a33_gate_error_ratio": 21.56,
                    "a53_gate_error_ratio": 0.018,
                    "a33_status": "FAIL",
                    "a53_status": "PASS",
                    "diagnostic_conclusion": "row_block_candidate_closes_a53_but_not_a33",
                    "candidate_default_gate_eligible": False,
                    "candidate_exclusion_reason": "diagnostic-only row-block candidate",
                },
            ]
        )
        local_time_cross = pd.DataFrame(
            [
                {
                    "candidate_name": "local_phase_chain_no_free_surface_marching",
                    "row_count": 8,
                    "pass_count": 1,
                    "max_gate_error_ratio": 21.1,
                    "median_gate_error_ratio": 5.71,
                    "a33_gate_error_ratio": 0.31,
                    "a33_gate_status": "PASS",
                    "candidate_gate_status": "FAIL",
                    "diagnostic_conclusion": "local_time_chain_closes_a33_only",
                    "candidate_default_gate_eligible": False,
                    "candidate_exclusion_reason": "diagnostic-only local-time/free-surface cross-probe",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_body_potential_time_pressure_chain_audit(
                comparison,
                tmp_path,
                "synthetic",
                a1_free_surface_grid_implementation_summary=state,
                rhs_source_decomposition_summary=rhs,
                heave_time_pressure_station_scale_summary=time_scale,
                time_pressure_pi_kernel_trace_summary=pi_trace,
                time_pressure_formula_unit_chain_summary=formula,
                body_potential_normalization_trace_summary=body_trace,
                phi_phi_n_kernel_normalization_trace_summary=phi_trace,
                free_surface_geometry_rhs_marching_cross_summary=fs_rhs_cross,
                inner_free_surface_rhs_row_block_candidate_summary=row_block,
                local_time_free_surface_cross_probe_summary=local_time_cross,
            )
            self.assertTrue((tmp_path / "synthetic_body_potential_time_pressure_chain_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_body_potential_time_pressure_chain_summary.csv").exists())

        self.assertIn("pi_squared_candidate_exclusion", set(detail["audit_item"]))
        self.assertIn("body_potential_open_wigley_normalization", set(detail["audit_item"]))
        self.assertIn("free_surface_geometry_rhs_marching_split_evidence", set(detail["audit_item"]))
        self.assertIn("eq23_known_free_potential_row_block_projection", set(detail["audit_item"]))
        self.assertIn("local_time_phase_free_surface_cross_probe", set(detail["audit_item"]))
        self.assertFalse(detail["supports_default_correction"].astype(bool).any())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        fs_row = detail[detail["audit_item"].eq("free_surface_geometry_rhs_marching_split_evidence")].iloc[0]
        self.assertEqual(fs_row["current_status"], "SPLIT_CLOSURE_ONLY")
        row_block_row = detail[detail["audit_item"].eq("eq23_known_free_potential_row_block_projection")].iloc[0]
        self.assertEqual(row_block_row["current_status"], "ROW_BLOCK_CANDIDATES_NOT_CLOSED")
        local_time_row = detail[detail["audit_item"].eq("local_time_phase_free_surface_cross_probe")].iloc[0]
        self.assertEqual(local_time_row["current_status"], "LOCAL_TIME_NOT_DEFAULTABLE")
        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_fail_count"]), 2)
        self.assertEqual(int(row["eq19_22_state_transfer_pass_count"]), 8)
        self.assertEqual(int(row["rhs_source_reconstruction_pass_count"]), 2)
        self.assertEqual(str(row["rhs_dominant_source"]), "inner_free_surface_potential")
        self.assertLess(float(row["time_integral_closure_max_abs_residual"]), 1.0e-10)
        self.assertEqual(int(row["one_over_pi_squared_pass_count"]), 2)
        self.assertFalse(bool(row["one_over_pi_squared_formula_traced"]))
        self.assertFalse(bool(row["default_correction_allowed_by_current_evidence"]))
        self.assertEqual(row["free_surface_geometry_rhs_best_candidate"], "known_phi_free_rhs_removed")
        self.assertTrue(bool(row["free_surface_geometry_rhs_split_closure_detected"]))
        self.assertEqual(row["rhs_row_block_best_candidate"], "only_control_row_retained")
        self.assertFalse(bool(row["rhs_row_block_full_closure_detected"]))
        self.assertEqual(row["local_time_best_candidate"], "local_phase_chain_no_free_surface_marching")
        self.assertEqual(int(row["local_time_best_pass_count"]), 1)
        self.assertFalse(bool(row["local_time_full_gate_detected"]))
        self.assertIn("open_body_potential_scale_untraced", row["diagnostic_conclusion"])
        self.assertIn("independent open-Wigley", row["next_required_evidence"])
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_a33_a53_passed_multifrequency_chain_is_recorded_as_closed(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "computed_value": value,
                    "reference_value": value,
                    "gate_error_ratio": 0.1,
                    "status": "PASS",
                    "provider_route": "matched_bie_station_sweep",
                    "matched_force_closure_residual_value": 1.0e-14,
                }
                for coefficient, value in (("A33", 1.07), ("A33", 0.941), ("A53", 0.19), ("A53", 0.145))
            ]
        )
        state = pd.DataFrame(
            [
                {
                    "state_transfer_reconstruction_pass_count": 8,
                    "state_transfer_reconstruction_row_count": 8,
                    "state_transfer_max_update_relative_residual": 0.0,
                    "state_transfer_max_transfer_relative_residual": 0.0,
                }
            ]
        )
        rhs = pd.DataFrame(
            [
                {
                    "coefficient": coefficient,
                    "source_reconstruction_status": "PASS",
                    "max_source_sum_relative_residual": 1.0e-15,
                }
                for coefficient in ("A33", "A53")
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            normalization_detail, normalization_summary = (
                _write_ma2005_body_potential_normalization_trace_audit(
                    comparison,
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    tmp_path,
                    "synthetic",
                )
            )
            chain_detail, chain_summary = _write_ma2005_body_potential_time_pressure_chain_audit(
                comparison,
                tmp_path,
                "synthetic",
                a1_free_surface_grid_implementation_summary=state,
                rhs_source_decomposition_summary=rhs,
                body_potential_normalization_trace_summary=normalization_summary,
            )

        normalization_row = normalization_summary.iloc[0]
        self.assertEqual(int(normalization_row["current_target_fail_count"]), 0)
        self.assertEqual(int(normalization_row["blocking_trace_count"]), 0)
        self.assertEqual(normalization_row["path_diagnostic_status"], "PASS")
        self.assertEqual(
            normalization_row["diagnostic_conclusion"],
            "current_a33_a53_gate_passes_no_body_potential_rescale_required",
        )
        self.assertFalse(normalization_detail["blocks_default_body_potential_rescale"].astype(bool).any())

        chain_row = chain_summary.iloc[0]
        self.assertEqual(int(chain_row["current_target_row_count"]), 4)
        self.assertEqual(int(chain_row["current_target_pass_count"]), 4)
        self.assertEqual(int(chain_row["current_target_fail_count"]), 0)
        self.assertLess(float(chain_row["selected_force_assembly_closure_max_abs_residual"]), 1.0e-9)
        self.assertEqual(int(chain_row["blocking_detail_count"]), 0)
        self.assertEqual(chain_row["path_diagnostic_status"], "PASS")
        self.assertEqual(
            chain_row["diagnostic_conclusion"],
            "a33_a53_eq23_body_potential_time_pressure_chain_closed_by_current_default_equations",
        )
        self.assertFalse(chain_detail["blocks_default_correction"].astype(bool).any())

    def test_ma2005_body_potential_constant_mode_audit_reconstructs_eq30_time_force(self):
        station_count = 3
        panel_count = 2
        x_m = np.asarray([0.0, 1.0, 2.0], dtype=float)
        body_constant = 1j * np.asarray([1.0, 1.5, 2.0], dtype=float)
        centered = 0.02j * np.asarray([[1.0, -1.0]] * station_count, dtype=complex)
        body_phi = body_constant[:, None] + centered
        panel_length = np.ones((station_count, panel_count), dtype=float)
        row_measure = np.zeros((station_count, 2, panel_count), dtype=float)
        row_measure[:, 0, :] = -0.5
        pressure_factor = -1j
        time_density = np.sum(pressure_factor * body_phi * row_measure[:, 0, :], axis=1)
        stored_density = np.zeros((station_count, 2, 2), dtype=complex)
        stored_density[:, 0, 0] = time_density
        breakdown = {
            "station_x_m": x_m[None, :],
            "station_x_over_l": (x_m / 2.0)[None, :],
            "heave_pressure_body_potential_by_station": body_phi[None, :, :],
            "heave_body_potential_by_station": body_phi[None, :, :],
            "body_panel_length_by_station": panel_length[None, :, :],
            "heave_pitch_pressure_row_measure_by_station": row_measure[None, :, :, :],
            "heave_pitch_time_derivative_force_density_by_station": stored_density[None, :, :, :],
            "heave_free_surface_potential_by_station": body_constant[None, :, None],
            "inner_free_surface_panel_length_by_station": np.ones((1, station_count, 1), dtype=float),
            "heave_control_potential_by_station": body_constant[None, :, None],
            "control_panel_length_by_station": np.ones((1, station_count, 1), dtype=float),
        }
        hydro = SimpleNamespace(contribution_breakdown=breakdown)
        rows = _ma2005_body_potential_constant_mode_rows(
            hydro,
            benchmark="synthetic",
            source_row=0,
            hull="wigley_iii",
            speed_case="Fn0.4",
            omega_e_sqrt_l_over_g=1.0,
            coefficient="A33",
            prefix="A",
            row_idx=2,
            col_idx=2,
            normalization_scale=1.0,
            omega_rad_s=1.0,
            rho_water_kg_m3=1.0,
            reference_value=-1.5,
        )
        self.assertEqual(len(rows), station_count)
        self.assertLess(max(float(row["density_decomposition_relative_residual"]) for row in rows), 1.0e-14)
        self.assertLess(max(float(row["stored_time_density_relative_residual"]) for row in rows), 1.0e-14)

        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = _write_ma2005_body_potential_constant_mode_audit(
                rows,
                Path(tmp),
                "synthetic",
            )
            self.assertTrue((Path(tmp) / "synthetic_body_potential_constant_mode_audit.csv").exists())
            self.assertTrue((Path(tmp) / "synthetic_body_potential_constant_mode_summary.csv").exists())

        self.assertEqual(len(detail), station_count)
        row = summary.iloc[0]
        self.assertGreater(float(row["constant_mode_force_abs_to_full_abs_ratio"]), 0.95)
        self.assertLess(float(row["force_decomposition_relative_residual"]), 1.0e-14)
        self.assertLess(float(row["stored_time_force_relative_residual"]), 1.0e-14)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "open_body_potential_station_constant_mode_dominates_eq30_time_pressure",
        )
        self.assertFalse(bool(row["candidate_default_gate_eligible"]))

    def test_ma2005_phi_phi_n_kernel_normalization_trace_blocks_untraced_changes(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "gate_error_ratio": 61.0,
                    "status": "FAIL",
                    "matched_inner_a_scale": 1.0,
                    "matched_inner_b_scale": 1.0,
                    "matched_inner_diagonal_sign": -1.0,
                    "matched_time_step_scale": 1.0,
                },
                {
                    "coefficient": "B33",
                    "gate_error_ratio": 22.0,
                    "status": "FAIL",
                    "matched_inner_a_scale": 1.0,
                    "matched_inner_b_scale": 1.0,
                    "matched_inner_diagonal_sign": -1.0,
                    "matched_time_step_scale": 1.0,
                },
                {
                    "coefficient": "A53",
                    "gate_error_ratio": 28.0,
                    "status": "FAIL",
                    "matched_inner_a_scale": 1.0,
                    "matched_inner_b_scale": 1.0,
                    "matched_inner_diagonal_sign": -1.0,
                    "matched_time_step_scale": 1.0,
                },
            ]
        )
        pi_kernel = pd.DataFrame(
            [
                {
                    "supporting_default_kernel_trace_count": 0,
                    "one_over_pi_squared_pass_count": 2,
                }
            ]
        )
        body_trace = pd.DataFrame(
            [
                {
                    "closed_section_corrected_relative_error": 0.0027,
                    "open_section_median_potential_norm_ratio_min": 0.039,
                    "open_section_median_potential_norm_ratio_max": 0.041,
                    "diagnostic_conclusion": "closed_inner_chain_passes_but_open_wigley_body_potential_normalization_untraced",
                }
            ]
        )
        phi_n = pd.DataFrame(
            [
                {
                    "diagnostic_conclusion": "inner_kernel_B_uses_stored_source_normals_A1_semantic_normal_still_requires_derivation",
                }
            ]
        )
        semantic = pd.DataFrame(
            [
                {
                    "stored_to_semantic_match_count": 1,
                    "stored_to_semantic_reversal_count": 2,
                    "diagnostic_conclusion": "a1_semantic_normal_prevents_blanket_default_flip",
                }
            ]
        )
        sc = pd.DataFrame(
            [
                {
                    "default_promotable_conversion_count": 0,
                    "diagnostic_conclusion": "sc_shared_unknown_convention_requires_rederivation_before_default_change",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_phi_phi_n_kernel_normalization_trace_audit(
                comparison,
                pi_kernel,
                body_trace,
                phi_n,
                semantic,
                sc,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_phi_phi_n_kernel_normalization_trace_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_phi_phi_n_kernel_normalization_trace_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 6)
        self.assertFalse(detail["supports_default_kernel_normalization_change"].astype(bool).any())
        self.assertTrue(detail["blocks_default_kernel_normalization_change"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_fail_count"]), 3)
        self.assertEqual(int(row["supporting_default_normalization_change_count"]), 0)
        self.assertEqual(int(row["one_over_pi_squared_pass_count"]), 2)
        self.assertEqual(str(row["current_inner_diagonal_sign_unique"]), "-1.0")
        self.assertEqual(int(row["default_promotable_conversion_count"]), 0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "phi_phi_n_kernel_chain_traced_but_no_default_normalization_change_supported",
        )
        self.assertIn("open Wigley", row["next_required_evidence"])
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_inner_free_surface_geometry_candidate_audit_stays_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 2.0,
                    "gate_error_ratio": 40.0,
                    "status": "FAIL",
                },
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.15,
                },
            ]
        )

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"])
            clipped = bool(row.get("matched_clip_inner_free_surface_to_waterline", False))
            two_zone = bool(row.get("matched_two_zone_inner_free_surface", False))
            values = {
                ("A33", False, False): 10.0,
                ("A53", False, False): 2.0,
                ("A33", True, False): 4.0,
                ("A53", True, False): 0.16,
                ("A33", True, True): 4.5,
                ("A53", True, True): 0.18,
            }
            return {
                "computed_value": values[(coefficient, clipped, two_zone)],
                "normalization": "ma2005",
                "solver_status": "ok",
                "provider_route": "matched_bie_station_sweep",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_inner_free_surface_geometry_candidate_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                )
            self.assertTrue((tmp_path / "synthetic_inner_free_surface_geometry_candidate_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_inner_free_surface_geometry_candidate_summary.csv").exists())

        self.assertEqual(set(detail["candidate_name"]), {
            "current_full_free_surface",
            "waterline_clipped_free_surface",
            "waterline_clipped_two_zone_free_surface",
        })
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        clipped = summary[summary["candidate_name"].eq("waterline_clipped_free_surface")].iloc[0]
        self.assertEqual(int(clipped["row_count"]), 2)
        self.assertGreaterEqual(int(clipped["improved_row_count"]), 1)
        self.assertLess(float(clipped["a53_gate_error_ratio"]), 1.0)
        self.assertEqual(
            clipped["diagnostic_conclusion"],
            "waterline_clipping_strongly_improves_time_pressure_subset_but_not_closed",
        )

    def test_ma2005_free_surface_geometry_rhs_marching_cross_audit_separates_a33_a53_closure(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 2.0,
                    "gate_error_ratio": 40.0,
                    "status": "FAIL",
                },
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.15,
                },
            ]
        )

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"])
            clipped = bool(row.get("matched_clip_inner_free_surface_to_waterline", False))
            two_zone = bool(row.get("matched_two_zone_inner_free_surface", False))
            rhs_scale = float(row.get("matched_inner_free_surface_known_potential_rhs_scale", 1.0))
            no_marching = not bool(row.get("matched_use_free_surface_marching", True))
            if abs(rhs_scale) < 1.0e-12 or no_marching:
                value = 1.02 if coefficient == "A33" else 0.0
            elif clipped and two_zone:
                value = 4.2 if coefficient == "A33" else 0.1505
            else:
                value = 10.0 if coefficient == "A33" else 2.0
            return {
                "computed_value": value,
                "normalization": "ma2005",
                "solver_status": "ok",
                "provider_route": "matched_bie_station_sweep",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_free_surface_geometry_rhs_marching_cross_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                )
            self.assertTrue((tmp_path / "synthetic_free_surface_geometry_rhs_marching_cross_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_free_surface_geometry_rhs_marching_cross_summary.csv").exists())

        self.assertIn("known_phi_free_rhs_removed", set(detail["candidate_name"]))
        self.assertIn("waterline_clipped_two_zone", set(detail["candidate_name"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        rhs_removed = summary[summary["candidate_name"].eq("known_phi_free_rhs_removed")].iloc[0]
        clipped = summary[summary["candidate_name"].eq("waterline_clipped_two_zone")].iloc[0]
        self.assertEqual(rhs_removed["diagnostic_conclusion"], "candidate_closes_a33_but_breaks_or_misses_a53")
        self.assertEqual(clipped["diagnostic_conclusion"], "candidate_closes_a53_but_leaves_a33_blocked")
        self.assertLess(float(rhs_removed["a33_gate_error_ratio"]), 1.0)
        self.assertLess(float(clipped["a53_gate_error_ratio"]), 1.0)

    def test_ma2005_inner_free_surface_rhs_row_block_candidate_audit_stays_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 2.0,
                    "gate_error_ratio": 40.0,
                    "status": "FAIL",
                },
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.15,
                },
            ]
        )

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"])
            clipped = bool(row.get("matched_clip_inner_free_surface_to_waterline", False))
            two_zone = bool(row.get("matched_two_zone_inner_free_surface", False))
            body_scale = float(row.get("matched_inner_free_surface_known_potential_body_row_scale", 1.0))
            free_scale = float(row.get("matched_inner_free_surface_known_potential_free_row_scale", 1.0))
            control_scale = float(row.get("matched_inner_free_surface_known_potential_control_row_scale", 1.0))
            if body_scale == 0.0 and free_scale == 1.0 and control_scale == 1.0 and not clipped:
                value = 1.02 if coefficient == "A33" else 0.0
            elif clipped and two_zone and body_scale == 0.0 and free_scale == 1.0 and control_scale == 0.0:
                value = 4.2 if coefficient == "A33" else 0.1505
            else:
                value = 10.0 if coefficient == "A33" else 2.0
            return {
                "computed_value": value,
                "normalization": "ma2005",
                "solver_status": "ok",
                "provider_route": "matched_bie_station_sweep",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_inner_free_surface_rhs_row_block_candidate_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                )
            self.assertTrue((tmp_path / "synthetic_inner_free_surface_rhs_row_block_candidate_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_inner_free_surface_rhs_row_block_candidate_summary.csv").exists())

        self.assertIn("body_row_removed", set(detail["candidate_name"]))
        self.assertIn("clip_two_zone_only_free_row_retained", set(detail["candidate_name"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        body_removed = summary[summary["candidate_name"].eq("body_row_removed")].iloc[0]
        clipped_free_only = summary[summary["candidate_name"].eq("clip_two_zone_only_free_row_retained")].iloc[0]
        self.assertEqual(body_removed["diagnostic_conclusion"], "row_block_candidate_closes_a33_but_not_a53")
        self.assertEqual(clipped_free_only["diagnostic_conclusion"], "row_block_candidate_closes_a53_but_not_a33")
        self.assertLess(float(body_removed["a33_gate_error_ratio"]), 1.0)
        self.assertLess(float(clipped_free_only["a53_gate_error_ratio"]), 1.0)

    def test_ma2005_inner_free_surface_control_row_scale_requirement_flags_nonuniform_scale(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 2.0,
                    "gate_error_ratio": 40.0,
                    "status": "FAIL",
                },
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.15,
                },
            ]
        )

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"])
            clipped = bool(row.get("matched_clip_inner_free_surface_to_waterline", False))
            body_scale = float(row.get("matched_inner_free_surface_known_potential_body_row_scale", 1.0))
            free_scale = float(row.get("matched_inner_free_surface_known_potential_free_row_scale", 1.0))
            control_scale = float(row.get("matched_inner_free_surface_known_potential_control_row_scale", 1.0))
            if not clipped and body_scale == 0.0 and free_scale == 0.0:
                value = control_scale if coefficient == "A33" else 0.03 * control_scale
            else:
                value = 4.0 + 0.2 * control_scale if coefficient == "A33" else 0.4 + 0.02 * control_scale
            return {
                "computed_value": value,
                "normalization": "ma2005",
                "solver_status": "ok",
                "provider_route": "matched_bie_station_sweep",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_inner_free_surface_control_row_scale_requirement_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                )
            self.assertTrue(
                (tmp_path / "synthetic_inner_free_surface_control_row_scale_requirement_audit.csv").exists()
            )
            self.assertTrue(
                (tmp_path / "synthetic_inner_free_surface_control_row_scale_requirement_summary.csv").exists()
            )

        self.assertIn("unclipped_only_control_row_scale", set(detail["candidate_name"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        control = summary[summary["candidate_name"].eq("unclipped_only_control_row_scale")].iloc[0]
        self.assertAlmostEqual(float(control["a33_required_control_row_scale"]), 1.0)
        self.assertAlmostEqual(float(control["a53_required_control_row_scale"]), 5.0)
        self.assertAlmostEqual(float(control["shared_median_control_row_scale"]), 3.0)
        self.assertEqual(
            control["diagnostic_conclusion"],
            "nonuniform_control_row_scale_requirement_keeps_subset_open",
        )
        self.assertGreater(float(control["max_gate_error_ratio"]), 1.0)

    def test_ma2005_inner_free_surface_control_row_projection_candidate_audit_stays_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "computed_value": 10.0,
                    "gate_error_ratio": 60.0,
                    "status": "FAIL",
                },
                {
                    "coefficient": "A53",
                    "computed_value": 2.0,
                    "gate_error_ratio": 40.0,
                    "status": "FAIL",
                },
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.15,
                },
            ]
        )

        def fake_computed(row, **_kwargs):
            coefficient = str(row["coefficient"])
            control_scale = float(row.get("matched_inner_free_surface_known_potential_control_row_scale", 1.0))
            unknown_scale = float(row.get("matched_inner_free_surface_unknown_normal_column_scale", 1.0))
            clipped = bool(row.get("matched_clip_inner_free_surface_to_waterline", False))
            if control_scale < 0.0 and unknown_scale == 1.0 and not clipped:
                value = 1.02 if coefficient == "A33" else 0.0
            elif unknown_scale < 0.0:
                value = 1.4 if coefficient == "A33" else 0.08
            else:
                value = 10.0 if coefficient == "A33" else 2.0
            return {
                "computed_value": value,
                "normalization": "ma2005",
                "solver_status": "ok",
                "provider_route": "matched_bie_station_sweep",
            }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_computed):
                detail, summary = _write_ma2005_inner_free_surface_control_row_projection_candidate_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                )
            self.assertTrue(
                (tmp_path / "synthetic_inner_free_surface_control_row_projection_candidate_audit.csv").exists()
            )
            self.assertTrue(
                (tmp_path / "synthetic_inner_free_surface_control_row_projection_candidate_summary.csv").exists()
            )

        self.assertIn("only_control_rhs_sign_flipped", set(detail["candidate_name"]))
        self.assertIn("only_control_rhs_unknown_normal_flipped", set(detail["candidate_name"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        sign_flipped = summary[summary["candidate_name"].eq("only_control_rhs_sign_flipped")].iloc[0]
        unknown_flipped = summary[summary["candidate_name"].eq("only_control_rhs_unknown_normal_flipped")].iloc[0]
        self.assertEqual(
            sign_flipped["diagnostic_conclusion"],
            "control_row_projection_candidate_closes_a33_but_not_a53",
        )
        self.assertEqual(
            unknown_flipped["diagnostic_conclusion"],
            "control_row_projection_candidate_improves_subset_but_not_closed",
        )
        self.assertLess(float(sign_flipped["a33_gate_error_ratio"]), 1.0)

    def test_ma2005_eq23_sign_mapping_audit_rejects_numerical_sign_flip_promotion(self):
        projection_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "only_control_rhs_sign_flipped",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 3.9667,
                    "a33_status": "PASS",
                    "a33_gate_error_ratio": 0.353,
                    "a53_status": "FAIL",
                    "a53_gate_error_ratio": 3.967,
                },
                {
                    "candidate_name": "only_control_rhs",
                    "row_count": 2,
                    "pass_count": 0,
                    "max_gate_error_ratio": 2.382,
                    "a33_status": "FAIL",
                    "a33_gate_error_ratio": 1.474,
                    "a53_status": "FAIL",
                    "a53_gate_error_ratio": 2.382,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_eq23_sign_mapping_audit(
                tmp_path,
                "synthetic",
                control_row_projection_candidate_summary=projection_summary,
            )
            self.assertTrue((tmp_path / "synthetic_eq23_sign_mapping_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_eq23_sign_mapping_summary.csv").exists())

        self.assertEqual(len(detail), 10)
        self.assertTrue(detail["matches_a1_eq23"].astype(bool).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["mapped_term_count"]), 10)
        self.assertEqual(int(row["mismatched_sign_count"]), 0)
        self.assertIn("only_control_rhs_sign_flipped", str(row["conflicting_candidates"]))
        self.assertEqual(
            row["diagnostic_conclusion"],
            "current_code_matches_A1_Eq23_sign_map_numeric_sign_flip_candidates_remain_unpromotable",
        )

    def test_ma2005_eq23_normal_definition_audit_keeps_definition_changes_diagnostic(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": name, "status": "FAIL"}
                for name in ("A33", "B33", "A35", "B35", "A53", "B53", "A55", "B55")
            ]
        )
        sign_summary = pd.DataFrame(
            [
                {
                    "mapped_term_count": 10,
                    "matched_sign_count": 10,
                    "mismatched_sign_count": 0,
                }
            ]
        )
        projection_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "only_control_rhs_sign_flipped",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 3.9667,
                    "a33_status": "PASS",
                    "a33_gate_error_ratio": 0.353,
                    "a53_status": "FAIL",
                    "a53_gate_error_ratio": 3.967,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_eq23_normal_definition_audit(
                comparison,
                tmp_path,
                "synthetic",
                eq23_sign_mapping_summary=sign_summary,
                control_row_projection_candidate_summary=projection_summary,
            )
            self.assertTrue((tmp_path / "synthetic_eq23_normal_definition_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_eq23_normal_definition_summary.csv").exists())

        self.assertGreaterEqual(len(detail), 8)
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["eq23_sign_mismatch_count"]), 0)
        self.assertGreater(int(row["high_risk_definition_count"]), 0)
        self.assertEqual(int(row["default_promotable_definition_change_count"]), 0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "eq23_signs_match_but_normal_definition_or_pitch_row_definition_requires_traced_derivation",
        )

    def test_ma2005_phi_n_orientation_audit_identifies_stored_source_normal(self):
        sign_summary = pd.DataFrame(
            [
                {
                    "mapped_term_count": 10,
                    "matched_sign_count": 10,
                    "mismatched_sign_count": 0,
                }
            ]
        )
        normal_definition_summary = pd.DataFrame(
            [
                {
                    "high_risk_definition_count": 4,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_phi_n_orientation_audit(
                tmp_path,
                "synthetic",
                eq23_sign_mapping_summary=sign_summary,
                eq23_normal_definition_summary=normal_definition_summary,
            )
            self.assertTrue((tmp_path / "synthetic_phi_n_orientation_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_phi_n_orientation_summary.csv").exists())

        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["boundary_count"]), 3)
        self.assertEqual(int(row["stored_orientation_pass_count"]), 3)
        self.assertEqual(int(row["reversed_orientation_pass_count"]), 0)
        self.assertEqual(int(row["default_promotable_orientation_change_count"]), 0)
        stored = detail[detail["orientation_candidate"].eq("stored_source_normal")]
        reversed_rows = detail[detail["orientation_candidate"].eq("reversed_source_normal")]
        self.assertTrue(stored["orientation_status"].eq("PASS").all())
        self.assertTrue(reversed_rows["orientation_status"].eq("FAIL").all())
        self.assertEqual(
            row["diagnostic_conclusion"],
            "inner_kernel_B_uses_stored_source_normals_A1_semantic_normal_still_requires_derivation",
        )

    def test_ma2005_a1_semantic_normal_audit_rejects_blanket_normal_flip(self):
        phi_detail = pd.DataFrame(
            [
                {
                    "boundary_role": boundary,
                    "orientation_candidate": "stored_source_normal",
                    "orientation_status": "PASS",
                }
                for boundary in ("body", "inner_free_surface", "inner_control")
            ]
        )
        phi_summary = pd.DataFrame(
            [
                {
                    "stored_orientation_pass_count": 3,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_a1_semantic_normal_audit(
                tmp_path,
                "synthetic",
                phi_n_orientation_audit=phi_detail,
                phi_n_orientation_summary=phi_summary,
            )
            self.assertTrue((tmp_path / "synthetic_a1_semantic_normal_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_a1_semantic_normal_summary.csv").exists())

        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["boundary_count"]), 3)
        self.assertEqual(int(row["direct_text_support_count"]), 1)
        self.assertEqual(int(row["inferred_support_count"]), 2)
        self.assertEqual(int(row["stored_to_semantic_match_count"]), 3)
        self.assertEqual(int(row["stored_to_semantic_reversal_count"]), 0)
        self.assertEqual(int(row["default_promotable_semantic_flip_count"]), 0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "current_A1_semantic_interpretation_matches_stored_normals_normal_flip_not_supported",
        )
        body = detail[detail["boundary_role"].eq("body")].iloc[0]
        self.assertEqual(body["evidence_level"], "direct_text_support")
        self.assertIn("inward unit normal", body["a1_semantic_normal"])

    def test_ma2005_sc_shared_unknown_convention_audit_keeps_conversion_diagnostic(self):
        semantic_summary = pd.DataFrame(
            [
                {
                    "stored_to_semantic_reversal_count": 0,
                }
            ]
        )
        projection_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "only_control_rhs_unknown_normal_flipped",
                    "row_count": 2,
                    "pass_count": 1,
                    "max_gate_error_ratio": 3.9667,
                    "a33_status": "PASS",
                    "a33_gate_error_ratio": 0.353,
                    "a53_status": "FAIL",
                    "a53_gate_error_ratio": 3.967,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_sc_shared_unknown_convention_audit(
                tmp_path,
                "synthetic",
                a1_semantic_normal_summary=semantic_summary,
                control_row_projection_candidate_summary=projection_summary,
            )
            self.assertTrue((tmp_path / "synthetic_sc_shared_unknown_convention_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_sc_shared_unknown_convention_summary.csv").exists())

        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["interface_count"]), 2)
        self.assertEqual(int(row["a1_continuity_text_support_count"]), 2)
        self.assertEqual(int(row["code_same_unknown_count"]), 2)
        self.assertEqual(int(row["explicit_sign_conversion_count"]), 0)
        self.assertEqual(int(row["default_promotable_conversion_count"]), 0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "sc_same_unknown_convention_matches_A1_text_no_default_sign_conversion_promotable",
        )
        normal_row = detail[detail["unknown"].eq("psi_n_control")].iloc[0]
        self.assertIn("-B_control", normal_row["eq23_code_column"])
        self.assertIn("-(B - Bbar)", normal_row["eq24_code_column"])

    def test_ma2005_control_row_free_surface_rhs_source_audit_requires_source_candidate(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": "A33", "gate_error_ratio": 61.0, "status": "FAIL"},
                {"coefficient": "A53", "gate_error_ratio": 28.0, "status": "FAIL"},
            ]
        )
        projection_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "only_control_rhs_sign_flipped",
                    "row_count": 2,
                    "pass_count": 1,
                    "fail_count": 1,
                    "max_gate_error_ratio": 3.9,
                    "median_gate_error_ratio": 2.1,
                    "a33_gate_error_ratio": 0.35,
                    "a53_gate_error_ratio": 3.9,
                    "a33_status": "PASS",
                    "a53_status": "FAIL",
                }
            ]
        )
        staggering_summary = pd.DataFrame(
            [
                {
                    "current_pass_count": 0,
                    "current_max_gate_error_ratio": 61.0,
                    "current_a33_gate_error_ratio": 61.0,
                    "current_a53_gate_error_ratio": 28.0,
                    "a1_half_step_pass_count": 0,
                    "a1_half_step_max_gate_error_ratio": 27.0,
                    "a1_half_step_a33_gate_error_ratio": 27.0,
                    "a1_half_step_a53_gate_error_ratio": 15.0,
                    "quarter_step_pass_count": 0,
                    "quarter_step_max_gate_error_ratio": 8.5,
                    "quarter_step_a33_gate_error_ratio": 8.5,
                    "quarter_step_a53_gate_error_ratio": 2.7,
                    "no_marching_pass_count": 1,
                    "no_marching_max_gate_error_ratio": 3.3,
                    "no_marching_a33_gate_error_ratio": 0.41,
                    "no_marching_a53_gate_error_ratio": 3.3,
                }
            ]
        )
        marching_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "free_surface_marching_disabled",
                    "row_count": 8,
                    "pass_count": 1,
                    "fail_count": 7,
                    "max_gate_error_ratio": 21.4,
                    "median_gate_error_ratio": 5.5,
                }
            ]
        )
        update_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "potential_uses_previous_elevation",
                    "row_count": 8,
                    "pass_count": 1,
                    "fail_count": 7,
                    "max_gate_error_ratio": 168.0,
                    "median_gate_error_ratio": 40.0,
                }
            ]
        )
        sc_summary = pd.DataFrame([{"default_promotable_conversion_count": 0}])
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_control_row_free_surface_rhs_source_audit(
                comparison,
                tmp_path,
                "synthetic",
                control_row_projection_candidate_summary=projection_summary,
                free_surface_marching_candidate_summary=marching_summary,
                free_surface_update_formula_candidate_summary=update_summary,
                free_surface_longitudinal_staggering_summary=staggering_summary,
                sc_shared_unknown_convention_summary=sc_summary,
            )
            self.assertTrue((tmp_path / "synthetic_control_row_free_surface_rhs_source_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_control_row_free_surface_rhs_source_summary.csv").exists())

        self.assertFalse(detail.empty)
        row = summary.iloc[0]
        self.assertFalse(bool(row["source_specific_candidate_available"]))
        self.assertEqual(int(row["default_promotable_source_change_count"]), 0)
        self.assertFalse(bool(row["candidate_default_gate_eligible"]))
        self.assertIn("candidate_missing", row["diagnostic_conclusion"])
        self.assertIn("control-row-only", row["next_required_evidence"])

    def test_ma2005_control_row_rhs_source_projection_coupled_candidate_audit_is_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference = pd.DataFrame(
                [
                    {
                        "coefficient": "A33",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "reference_value": 1.0,
                    },
                    {
                        "coefficient": "A53",
                        "omega_e_sqrt_l_over_g": 1.0,
                        "reference_value": 0.2,
                    },
                ]
            )
            reference_path = tmp_path / "reference.csv"
            reference.to_csv(reference_path, index=False)
            comparison = pd.DataFrame(
                [
                    {"coefficient": "A33", "gate_error_ratio": 10.0, "status": "FAIL"},
                    {"coefficient": "A53", "gate_error_ratio": 8.0, "status": "FAIL"},
                ]
            )

            def fake_calc(row, **_kwargs):
                coefficient = str(row["coefficient"])
                source = str(row.get("matched_control_row_free_surface_potential_source", ""))
                control_scale = float(row.get("matched_inner_free_surface_known_potential_control_row_scale", 1.0))
                reference_value = float(row["reference_value"])
                if coefficient == "A33" and source == "zero_no_marching" and control_scale < 0.0:
                    computed = 1.02
                elif coefficient == "A53" and source == "zero_no_marching" and control_scale < 0.0:
                    computed = 0.8
                else:
                    computed = reference_value * 2.0
                return {
                    "computed_value": computed,
                    "normalization": "ma2005",
                    "provider_route": "matched_bie_station_sweep",
                    "solver_status": "mocked",
                }

            with mock.patch("planing_seakeeping.validation._ma2005_computed_coefficient", side_effect=fake_calc):
                detail, summary = _write_ma2005_control_row_rhs_source_projection_coupled_candidate_audit(
                    comparison,
                    reference_path,
                    tmp_path,
                    "synthetic",
                    hydro_model="matched_bie_provider",
                )

            self.assertTrue((tmp_path / "synthetic_control_row_rhs_source_projection_coupled_candidate_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_control_row_rhs_source_projection_coupled_candidate_summary.csv").exists())
            self.assertFalse(detail.empty)
            best = summary.iloc[0]
            self.assertEqual(best["candidate_name"], "only_control_rhs_sign_flipped__source_zero_no_marching")
            self.assertEqual(int(best["pass_count"]), 1)
            self.assertFalse(bool(best["candidate_default_gate_eligible"]))
            self.assertIn("diagnostic_control_row_rhs_source_projection", best["gate_role"])

    def test_ma2005_shared_body_potential_scale_audit_excludes_single_scale_fix(self):
        one_over_pi_squared = 1.0 / (math.pi**2)
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "computed_value": math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 59.0,
                    "matched_time_derivative_component_value": math.pi**2,
                },
                {
                    "coefficient": "A53",
                    "reference_value": 0.15,
                    "computed_value": 0.15 * math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 30.0,
                    "matched_time_derivative_component_value": 0.15 * math.pi**2,
                },
            ]
        )
        time_summary = pd.DataFrame(
            [
                {
                    "one_over_pi_squared_value": one_over_pi_squared,
                }
            ]
        )
        mapping_detail = pd.DataFrame(
            [
                {
                    "candidate_name": "mapped_normalized_y_central",
                    "coefficient": "B33",
                    "reference_value": 2.1,
                    "candidate_conservative_eq31_value": 7.0,
                    "candidate_conservative_eq31_gate_error_ratio": 15.0,
                    "candidate_conservative_hybrid_value": 7.5,
                    "candidate_conservative_hybrid_gate_error_ratio": 17.0,
                },
                {
                    "candidate_name": "mapped_normalized_y_central",
                    "coefficient": "A35",
                    "reference_value": -0.2,
                    "candidate_conservative_eq31_value": -2.0,
                    "candidate_conservative_eq31_gate_error_ratio": 30.0,
                    "candidate_conservative_hybrid_value": -2.5,
                    "candidate_conservative_hybrid_gate_error_ratio": 38.0,
                },
                {
                    "candidate_name": "mapped_normalized_y_central",
                    "coefficient": "B35",
                    "reference_value": 0.13,
                    "candidate_conservative_eq31_value": 5.5,
                    "candidate_conservative_eq31_gate_error_ratio": 120.0,
                    "candidate_conservative_hybrid_value": 6.0,
                    "candidate_conservative_hybrid_gate_error_ratio": 130.0,
                },
            ]
        )
        mapping_summary = pd.DataFrame(
            [
                {
                    "candidate_name": "mapped_normalized_y_central",
                    "best_route_by_max_gate": "mapping_conservative_eq31",
                    "best_route_max_gate_error_ratio": 120.0,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_shared_body_potential_scale_audit(
                comparison,
                time_summary,
                mapping_detail,
                mapping_summary,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_shared_body_potential_scale_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_shared_body_potential_scale_summary.csv").exists())

        one_over_pi2 = summary[summary["scale_candidate"].eq("one_over_pi_squared")].iloc[0]
        self.assertEqual(int(one_over_pi2["time_pressure_pass_count"]), 2)
        self.assertLess(int(one_over_pi2["zero_m3_pass_count"]), 3)
        self.assertGreater(float(one_over_pi2["max_zero_m3_gate_error_ratio"]), 1.0)
        self.assertEqual(
            one_over_pi2["diagnostic_conclusion"],
            "shared_body_potential_scale_matches_time_pressure_but_excludes_zero_m3",
        )
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_time_pressure_scale_candidate_projects_to_full_gate(self):
        comparison = pd.DataFrame(
            [
                {
                    "row": 0,
                    "coefficient": "A33",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 1.0,
                    "computed_value": math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 59.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "matched_time_derivative_component_value": math.pi**2,
                    "matched_pressure_gradient_component_value": 0.0,
                    "matched_end_term_component_value": 0.0,
                    "matched_time_derivative_component_raw": math.pi**2,
                    "matched_pressure_gradient_component_raw": 0.0,
                    "matched_end_term_component_raw": 0.0,
                },
                {
                    "row": 1,
                    "coefficient": "A53",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 0.15,
                    "computed_value": 0.15 * math.pi**2,
                    "status": "FAIL",
                    "gate_error_ratio": 30.0,
                    "tolerance": 0.30,
                    "normalization": "ma2005",
                    "matched_time_derivative_component_value": 0.15 * math.pi**2,
                    "matched_pressure_gradient_component_value": 0.0,
                    "matched_end_term_component_value": 0.0,
                    "matched_time_derivative_component_raw": 0.15 * math.pi**2,
                    "matched_pressure_gradient_component_raw": 0.0,
                    "matched_end_term_component_raw": 0.0,
                },
                {
                    "row": 2,
                    "coefficient": "B35",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 0.13,
                    "computed_value": 10.13,
                    "status": "FAIL",
                    "gate_error_ratio": 160.0,
                    "tolerance": 0.30,
                    "normalization": "ma2005",
                    "matched_time_derivative_component_value": 10.0,
                    "matched_pressure_gradient_component_value": 0.13,
                    "matched_end_term_component_value": 0.0,
                    "matched_time_derivative_component_raw": 10.0,
                    "matched_pressure_gradient_component_raw": 0.13,
                    "matched_end_term_component_raw": 0.0,
                },
                {
                    "row": 3,
                    "coefficient": "A55",
                    "provider_route": "matched_bie_station_sweep",
                    "reference_value": 0.063,
                    "computed_value": 0.2,
                    "status": "FAIL",
                    "gate_error_ratio": 14.0,
                    "tolerance": 0.15,
                    "normalization": "ma2005",
                    "matched_time_derivative_component_value": 0.0,
                    "matched_pressure_gradient_component_value": 0.2,
                    "matched_end_term_component_value": 0.0,
                    "matched_time_derivative_component_raw": 0.0,
                    "matched_pressure_gradient_component_raw": 0.2,
                    "matched_end_term_component_raw": 0.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_time_pressure_scale_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_time_pressure_scale_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_time_pressure_scale_candidate_summary.csv").exists())

            one_over_pi2 = summary[
                summary["candidate_name"].eq("time_pressure_one_over_pi_squared_keep_gradient_end")
            ].iloc[0]
            self.assertEqual(int(one_over_pi2["target_pass_count"]), 2)
            self.assertLessEqual(float(one_over_pi2["target_max_gate_error_ratio"]), 1.0)
            self.assertLess(int(one_over_pi2["pass_count"]), int(one_over_pi2["row_count"]))
            self.assertEqual(one_over_pi2["diagnostic_conclusion"], "candidate_closes_a33_a53_only_not_full_gate")
            self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

            impact = _write_ma2005_candidate_impact_summary(
                comparison,
                tmp_path,
                "synthetic",
                time_pressure_scale_candidate_summary=summary,
            )
            self.assertIn(
                "time_pressure_one_over_pi_squared_keep_gradient_end",
                set(impact["candidate_name"].astype(str)),
            )
            detail_candidate = detail[
                detail["candidate_name"].eq("time_pressure_one_over_pi_squared_keep_gradient_end")
            ]
            self.assertEqual(int(detail_candidate["candidate_gate_status"].eq("PASS").sum()), 2)
            self.assertAlmostEqual(
                float(detail_candidate[detail_candidate["coefficient"].eq("A33")]["computed_value"].iloc[0]),
                1.0,
            )
            self.assertAlmostEqual(
                float(detail_candidate[detail_candidate["coefficient"].eq("A53")]["computed_value"].iloc[0]),
                0.15,
            )

    def test_ma2005_free_surface_longitudinal_staggering_audit_tracks_a1_half_step_proxy(self):
        rows = []
        candidate_rows = [
            ("current_marching", "A33", 61.0, "FAIL", 1.0),
            ("current_marching", "A53", 28.0, "FAIL", 1.0),
            ("free_surface_time_step_half", "A33", 28.0, "FAIL", 0.5),
            ("free_surface_time_step_half", "A53", 16.0, "FAIL", 0.5),
            ("free_surface_time_step_quarter", "A33", 8.5, "FAIL", 0.25),
            ("free_surface_time_step_quarter", "A53", 2.7, "FAIL", 0.25),
            ("free_surface_marching_disabled", "A33", 0.4, "PASS", 1.0),
            ("free_surface_marching_disabled", "A53", 3.3, "FAIL", 1.0),
        ]
        for candidate_name, coefficient, gate_error_ratio, status, time_step_scale in candidate_rows:
            rows.append(
                {
                    "candidate_name": candidate_name,
                    "coefficient": coefficient,
                    "gate_error_ratio": gate_error_ratio,
                    "candidate_gate_status": status,
                    "time_step_scale": time_step_scale,
                }
            )
        detail_source = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_free_surface_longitudinal_staggering_audit(
                detail_source,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_free_surface_longitudinal_staggering_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_free_surface_longitudinal_staggering_summary.csv").exists())

        self.assertEqual(len(detail), 8)
        self.assertEqual(set(detail["coefficient"]), {"A33", "A53"})
        self.assertIn("a1_half_body_station_step_proxy", set(detail["a1_staggering_role"]))
        self.assertTrue(detail["a1_required_time_step_scale_proxy"].astype(float).eq(0.5).all())
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        self.assertEqual(int(summary["row_count"].iloc[0]), 8)
        self.assertEqual(int(summary["current_pass_count"].iloc[0]), 0)
        self.assertEqual(int(summary["a1_half_step_pass_count"].iloc[0]), 0)
        self.assertEqual(int(summary["no_marching_pass_count"].iloc[0]), 1)
        self.assertAlmostEqual(float(summary["a1_half_step_a33_gate_error_ratio"].iloc[0]), 28.0)
        self.assertAlmostEqual(float(summary["a1_half_step_a53_gate_error_ratio"].iloc[0]), 16.0)
        self.assertEqual(
            summary["diagnostic_conclusion"].iloc[0],
            "a1_half_step_proxy_does_not_close_time_pressure_but_free_surface_marching_amplifies_a33",
        )
        self.assertFalse(summary["candidate_default_gate_eligible"].astype(bool).any())

    def test_ma2005_a1_free_surface_grid_implementation_audit_flags_half_station_gap(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": "A33",
                    "gate_error_ratio": 61.0,
                    "status": "FAIL",
                    "matched_time_step_scale": 1.0,
                    "matched_free_surface_substeps_per_station": 1,
                    "matched_control_row_free_surface_potential_source": "shared",
                    "provider_route": "matched_bie_station_sweep",
                },
                {
                    "coefficient": "A53",
                    "gate_error_ratio": 28.0,
                    "status": "FAIL",
                    "matched_time_step_scale": 1.0,
                    "matched_free_surface_substeps_per_station": 1,
                    "matched_control_row_free_surface_potential_source": "shared",
                    "provider_route": "matched_bie_station_sweep",
                },
            ]
        )
        staggering_summary = pd.DataFrame(
            [
                {
                    "a1_half_step_pass_count": 0,
                    "a1_two_substeps_pass_count": 0,
                    "no_marching_pass_count": 1,
                    "a1_half_step_a33_gate_error_ratio": 27.0,
                    "a1_half_step_a53_gate_error_ratio": 15.0,
                    "a1_two_substeps_a33_gate_error_ratio": 62.0,
                    "a1_two_substeps_a53_gate_error_ratio": 29.0,
                }
            ]
        )
        control_source_summary = pd.DataFrame(
            [
                {
                    "source_specific_candidate_available": True,
                    "subset_closing_evidence_count": 0,
                }
            ]
        )
        state_summary = pd.DataFrame(
            [
                {
                    "state_reconstruction_status": "PASS",
                    "max_update_relative_residual": 0.0,
                    "max_transfer_relative_residual": 0.0,
                },
                {
                    "state_reconstruction_status": "PASS",
                    "max_update_relative_residual": 0.0,
                    "max_transfer_relative_residual": 0.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_a1_free_surface_grid_implementation_audit(
                comparison,
                tmp_path,
                "synthetic",
                inner_free_surface_state_marching_summary=state_summary,
                free_surface_longitudinal_staggering_summary=staggering_summary,
                control_row_free_surface_rhs_source_summary=control_source_summary,
            )
            self.assertTrue((tmp_path / "synthetic_a1_free_surface_grid_implementation_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_a1_free_surface_grid_implementation_summary.csv").exists())

        self.assertEqual(len(detail), 6)
        self.assertIn("eq19_eq22_state_transfer_reconstruction", set(detail["audit_item"]))
        self.assertIn("section_3_3_twice_free_surface_stations", set(detail["audit_item"]))
        self.assertIn("section_3_5_solve_i_plus_1_after_eq20", set(detail["audit_item"]))
        self.assertFalse(detail["candidate_default_gate_eligible"].astype(bool).any())
        row = summary.iloc[0]
        self.assertEqual(int(row["state_vector_present_count"]), 2)
        self.assertEqual(int(row["state_transfer_reconstruction_pass_count"]), 2)
        self.assertEqual(int(row["state_transfer_reconstruction_row_count"]), 2)
        self.assertAlmostEqual(float(row["state_transfer_max_update_relative_residual"]), 0.0)
        self.assertAlmostEqual(float(row["state_transfer_max_transfer_relative_residual"]), 0.0)
        self.assertGreaterEqual(int(row["explicit_grid_or_transfer_gap_count"]), 2)
        self.assertEqual(int(row["current_target_pass_count"]), 0)
        self.assertEqual(int(row["a1_half_step_pass_count"]), 0)
        self.assertEqual(int(row["a1_two_substeps_pass_count"]), 0)
        self.assertTrue(bool(row["control_row_source_specific_candidate_available"]))
        self.assertIn("eq19_22_state_transfer_reconstructs", row["diagnostic_conclusion"])
        self.assertIn("zeta(i-1/2)", row["next_required_evidence"])

    def test_ma2005_a1_free_surface_grid_summary_handles_multiple_frequency_target_rows(self):
        comparison = pd.DataFrame(
            [
                {"coefficient": coefficient, "gate_error_ratio": gate, "status": "PASS"}
                for coefficient, gate in (("A33", 0.32), ("A33", 0.33), ("A53", 0.61), ("A53", 0.68))
            ]
        )
        state_summary = pd.DataFrame(
            [
                {
                    "state_reconstruction_status": "PASS",
                    "max_update_relative_residual": 0.0,
                    "max_transfer_relative_residual": 0.0,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, summary = _write_ma2005_a1_free_surface_grid_implementation_audit(
                comparison,
                Path(tmp),
                "synthetic_multifrequency",
                inner_free_surface_state_marching_summary=state_summary,
            )

        row = summary.iloc[0]
        self.assertEqual(int(row["current_target_row_count"]), 4)
        self.assertEqual(int(row["current_target_pass_count"]), 4)
        self.assertEqual(int(row["current_target_fail_count"]), 0)
        self.assertEqual(
            row["diagnostic_conclusion"],
            "a1_eq19_22_state_transfer_reconstructs_and_a33_a53_gate_passes_with_explicit_grid_gaps_remaining",
        )
        self.assertFalse(bool(row["candidate_default_gate_eligible"]))

    def test_ma2005_remaining_blocker_audit_uses_literature_trace_to_close_compression(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coeff,
                    "status": "FAIL",
                    "provider_route": "matched_bie_station_sweep",
                }
                for coeff in ["A33", "B33", "A35", "B35", "A53", "B53", "A55", "B55"]
            ]
        )
        gate1_failure = pd.DataFrame(
            [
                {"coefficient": "A33", "failure_source": "heave_time_derivative_body_potential_scale"},
                {"coefficient": "B33", "failure_source": "forward_speed_pressure_gradient_station_mapping"},
                {"coefficient": "A55", "failure_source": "pitch_row_moment_chain"},
            ]
        )
        candidate_impact = pd.DataFrame(
            [
                {
                    "candidate_name": "least_squares_time_only",
                    "candidate_family": "eq30_component_scale_fit",
                    "pass_count": 2,
                    "row_count": 8,
                    "max_gate_error_ratio": 6.0,
                    "candidate_default_gate_eligible": False,
                }
            ]
        )
        heave_pressure = pd.DataFrame(
            [
                {
                    "station_integral_closure_pass_count": 2,
                    "pending_reference_count": 2,
                    "required_scale_min": 0.098,
                    "required_scale_max": 0.106,
                    "open_section_independent_reference_status": (
                        "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE"
                    ),
                }
            ]
        )
        open_section = pd.DataFrame(
            [
                {
                    "independent_reference_status": "EXPERIMENTAL_OPEN_SECTION_BEM_REFERENCE_NOT_HARD_GATE",
                    "median_independent_to_matched_abs_ratio": 0.04,
                }
            ]
        )
        formula = pd.DataFrame(
            [
                {
                    "coefficient": "B35",
                    "eq31_eq32_proxy_residual_norm": 0.9,
                    "dominant_formula_component": "interior_distributed_transport",
                    "interior_distributed_abs_share": 0.9,
                    "boundary_proxy_abs_share": 0.1,
                }
            ]
        )
        row_mapping = pd.DataFrame(
            [
                {
                    "candidate_name": "current_equal_panel_x_derivative",
                    "diagnostic_conclusion": "mapping_candidate_excluded_by_zero_mi_rows",
                }
            ]
        )
        fixed_control = pd.DataFrame(
            [
                {
                    "open_blocker_count": 1,
                    "median_interior_distributed_abs_share": 0.88,
                    "diagnostic_conclusion": "fixed_control_surface_transport_gap_confirmed",
                }
            ]
        )
        pitch = pd.DataFrame(
            [
                {
                    "fail_count": 2,
                    "max_gate_error_ratio": 131.0,
                    "dominant_rank_1_counts": "Eq.31_pressure_gradient_moment:1",
                }
            ]
        )
        stokes_end = pd.DataFrame(
            [
                {
                    "row_count": 8,
                    "identity_pass_count": 2,
                    "end_lever_consistency_pass_count": 8,
                    "max_forward_identity_residual_over_effective_tolerance": 141.0,
                    "min_end_to_endpoint_forward_ratio_abs": 0.44,
                    "max_end_to_endpoint_forward_ratio_abs": 0.80,
                    "diagnostic_conclusion": "eq31_eq32_stokes_end_identity_not_closed",
                }
            ]
        )
        matched_end = pd.DataFrame([{"endpoint_label": "configured_end_station"}])
        rhs_source = pd.DataFrame(
            [
                {
                    "max_source_sum_relative_residual": 1.0e-12,
                    "diagnostic_conclusion": "rhs_sources_reconstruct_solution",
                }
            ]
        )
        inner_state = pd.DataFrame(
            [
                {
                    "max_update_relative_residual": 0.0,
                    "max_transfer_relative_residual": 0.0,
                    "diagnostic_conclusion": "inner_state_updates_and_transfers_reconstruct_eq19_22",
                }
            ]
        )
        literature_summary = pd.DataFrame(
            [
                {
                    "all_gate1_relevant_gaps_confirmed": True,
                    "confirmed_gate1_relevant_gap_count": 3,
                    "traceability_status": "GATE1_FAILURES_COMPRESSED_TO_TRACEABLE_THEORY_OR_DATA_GAPS",
                }
            ]
        )
        journee_summary = pd.DataFrame(
            [
                {
                    "matched_row_count": 8,
                    "frequency_mismatch_count": 8,
                    "value_close_count": 7,
                    "external_integrated_reference_status": (
                        "FOUND_JOURNEE_INTEGRATED_COEFFICIENT_TABLES_NOT_SECTION_PRESSURE"
                    ),
                }
            ]
        )
        journee_probe_summary = pd.DataFrame(
            [
                {
                    "row_count": 8,
                    "pass_count": 0,
                    "fail_count": 8,
                    "max_gate_error_ratio": 100.0,
                    "diagnostic_conclusion": "journee_frequency_probe_still_fails_default_provider",
                }
            ]
        )
        body_condition_unit_summary = pd.DataFrame(
            [
                {
                    "variant_name": "remove_dimensional_omega2_unit_acceleration_proxy",
                    "row_count": 8,
                    "pass_count": 1,
                    "fail_count": 7,
                    "max_gate_error_ratio": 35.0,
                    "diagnostic_conclusion": "simple_unit_scale_proxy_does_not_close_gate",
                }
            ]
        )
        gate1_reference_trace_summary = pd.DataFrame(
            [
                {
                    "row_count": 8,
                    "source_row_match_count": 8,
                    "journee_frequency_mismatch_count": 8,
                    "reference_trace_status": (
                        "GATE1_REFERENCE_FIXED_TO_MA_FIGURE_ROWS_WITH_JOURNEE_FREQUENCY_MISMATCH"
                    ),
                }
            ]
        )
        time_pressure_scale_origin_summary = pd.DataFrame(
            [
                {
                    "row_count": 2,
                    "one_over_pi_squared_pass_count": 2,
                    "one_over_pi_squared_max_gate_error_ratio": 0.1,
                    "length_power2_pass_count": 1,
                    "inner_a_normalized_by_2pi_pass_count": 0,
                    "known_phi_free_rhs_one_over_2pi_pass_count": 0,
                    "diagnostic_conclusion": (
                        "one_over_pi_squared_matches_a33_a53_but_is_untraced_and_not_full_gate"
                    ),
                }
            ]
        )
        free_surface_longitudinal_staggering_summary = pd.DataFrame(
            [
                {
                    "row_count": 8,
                    "a1_half_step_pass_count": 0,
                    "a1_half_step_a33_gate_error_ratio": 28.0,
                    "a1_half_step_a53_gate_error_ratio": 16.0,
                    "no_marching_pass_count": 1,
                    "diagnostic_conclusion": (
                        "a1_half_step_proxy_does_not_close_time_pressure_but_free_surface_marching_amplifies_a33"
                    ),
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            detail, summary = _write_ma2005_gate1_remaining_blocker_audit(
                comparison,
                gate1_failure,
                candidate_impact,
                heave_pressure,
                open_section,
                formula,
                row_mapping,
                fixed_control,
                pitch,
                rhs_source,
                inner_state,
                Path(tmp),
                "synthetic",
                literature_traceability_gap_summary=literature_summary,
                journee_table_reference_summary=journee_summary,
                journee_frequency_gate_probe_summary=journee_probe_summary,
                body_condition_unit_chain_summary=body_condition_unit_summary,
                stokes_end_lever_consistency_summary=stokes_end,
                matched_end_pressure_closure_summary=matched_end,
                gate1_reference_trace_summary=gate1_reference_trace_summary,
                time_pressure_scale_origin_summary=time_pressure_scale_origin_summary,
                free_surface_longitudinal_staggering_summary=free_surface_longitudinal_staggering_summary,
            )
        self.assertIn("reference_frequency_pairing_ambiguity", set(detail["blocker_id"]))
        reference_gap = detail[detail["blocker_id"].eq("reference_frequency_pairing_ambiguity")].iloc[0]
        self.assertIn("journee_frequency_probe_pass=0/8", reference_gap["evidence"])
        self.assertIn("gate1_reference_source_rows=8/8", reference_gap["evidence"])
        self.assertIn("gate1_reference_journee_mismatch=8", reference_gap["evidence"])
        time_gap = detail[detail["blocker_id"].eq("time_pressure_body_potential_scale")].iloc[0]
        self.assertIn(
            "scale_origin_conclusion=one_over_pi_squared_matches_a33_a53_but_is_untraced_and_not_full_gate",
            time_gap["evidence"],
        )
        self.assertIn("one_over_pi2_pass=2/2", time_gap["evidence"])
        self.assertIn("length_power2_pass=1/2", time_gap["evidence"])
        self.assertIn(
            "free_surface_stagger_conclusion=a1_half_step_proxy_does_not_close_time_pressure_but_free_surface_marching_amplifies_a33",
            time_gap["evidence"],
        )
        self.assertIn("a1_half_step_pass=0/2", time_gap["evidence"])
        self.assertIn("no_marching_pass=1/2", time_gap["evidence"])
        pitch_gap = detail[detail["blocker_id"].eq("pitch_row_moment_chain")].iloc[0]
        self.assertIn("stokes_end_identity_pass=2/8", pitch_gap["evidence"])
        self.assertIn("end_lever_pass=8/8", pitch_gap["evidence"])
        closed_paths = summary["closed_non_blocker_paths"].iloc[0]
        self.assertIn("body_condition_unit_scale_proxy", closed_paths)
        self.assertEqual(
            summary["compression_status"].iloc[0],
            "COMPRESSED_TO_TRACEABLE_THEORY_OR_DATA_GAPS",
        )
        self.assertEqual(
            summary["literature_traceability_status"].iloc[0],
            "GATE1_FAILURES_COMPRESSED_TO_TRACEABLE_THEORY_OR_DATA_GAPS",
        )
        self.assertEqual(int(summary["literature_confirmed_gate1_gap_count"].iloc[0]), 3)
        self.assertGreaterEqual(int(summary["current_materials_or_theory_gap_count"].iloc[0]), 4)

    def test_ma2005_candidate_impact_summary_projects_zero_m3_candidates_to_all_rows(self):
        comparison = pd.DataFrame(
            [
                {
                    "coefficient": coeff,
                    "reference_value": 1.0,
                    "computed_value": 2.0,
                    "abs_error": 1.0,
                    "status": "PASS" if coeff == "B53" else "FAIL",
                    "gate_error_ratio": 0.5 if coeff == "B53" else 10.0,
                }
                for coeff in ["A33", "B33", "A35", "B35", "A53", "B53", "A55", "B55"]
            ]
        )
        zero_detail = pd.DataFrame(
            [
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "B33",
                    "candidate_status": "PASS",
                    "candidate_gate_error_ratio": 0.8,
                    "candidate_abs_error": 0.1,
                },
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "A35",
                    "candidate_status": "FAIL",
                    "candidate_gate_error_ratio": 9.0,
                    "candidate_abs_error": 0.9,
                },
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "B35",
                    "candidate_status": "FAIL",
                    "candidate_gate_error_ratio": 11.0,
                    "candidate_abs_error": 1.1,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summary = _write_ma2005_candidate_impact_summary(
                comparison,
                tmp_path,
                "synthetic",
                zero_mi_normal_transport_candidate_detail=zero_detail,
                pressure_sign_summary=pd.DataFrame(
                    [
                        {
                            "candidate_name": "current_default",
                            "row_count": 8,
                            "pass_count": 1,
                            "max_gate_error_ratio": 10.0,
                            "median_gate_error_ratio": 10.0,
                        }
                    ]
                ),
            )
            self.assertTrue((tmp_path / "synthetic_candidate_impact_summary.csv").exists())
        projected = summary[
            summary["candidate_family"].eq("zero_m3_formula_transport_candidate")
            & summary["candidate_name"].eq("add_full_zero_m3_transport")
        ].iloc[0]
        self.assertEqual(int(projected["row_count"]), 8)
        self.assertEqual(int(projected["pass_count"]), 2)
        self.assertEqual(projected["affected_coefficients"], "A35,B33,B35")
        self.assertEqual(projected["candidate_default_gate_eligible"], "false")

    def test_ma2005_row_measure_zero_mi_boundary_summary_localizes_endpoint_panels(self):
        detail = pd.DataFrame(
            [
                {
                    "source_row": 0,
                    "coefficient": "B33",
                    "row_family": "heave_row_N3_m3",
                    "column_family": "heave_radiation",
                    "station_index": 0,
                    "x_m": 0.0,
                    "x_over_l": 0.0,
                    "is_configured_end_station": True,
                    "is_bow_station": False,
                    "row_measure_transport_density_value_per_m": 2.0,
                    "normal_variation_density_value_per_m": 1.0,
                    "panel_length_variation_density_value_per_m": 1.0,
                    "lever_variation_density_value_per_m": 0.0,
                    "product_rule_residual_density_value_per_m": 0.0,
                    "waterline_contour_density_value_per_m": 2.0,
                    "boundary_density_value_per_m": 2.0,
                    "section_endpoint_panel_density_value_per_m": 2.0,
                    "section_interior_panel_density_value_per_m": 0.0,
                    "mapping_residual_density_value_per_m": 0.0,
                },
                {
                    "source_row": 0,
                    "coefficient": "B33",
                    "row_family": "heave_row_N3_m3",
                    "column_family": "heave_radiation",
                    "station_index": 1,
                    "x_m": 1.0,
                    "x_over_l": 0.5,
                    "is_configured_end_station": False,
                    "is_bow_station": False,
                    "row_measure_transport_density_value_per_m": 4.0,
                    "normal_variation_density_value_per_m": 3.0,
                    "panel_length_variation_density_value_per_m": 1.0,
                    "lever_variation_density_value_per_m": 0.0,
                    "product_rule_residual_density_value_per_m": 0.0,
                    "waterline_contour_density_value_per_m": 4.0,
                    "boundary_density_value_per_m": 4.0,
                    "section_endpoint_panel_density_value_per_m": 4.0,
                    "section_interior_panel_density_value_per_m": 0.0,
                    "mapping_residual_density_value_per_m": 0.0,
                },
                {
                    "source_row": 0,
                    "coefficient": "B33",
                    "row_family": "heave_row_N3_m3",
                    "column_family": "heave_radiation",
                    "station_index": 2,
                    "x_m": 2.0,
                    "x_over_l": 1.0,
                    "is_configured_end_station": False,
                    "is_bow_station": True,
                    "row_measure_transport_density_value_per_m": 2.0,
                    "normal_variation_density_value_per_m": 1.0,
                    "panel_length_variation_density_value_per_m": 1.0,
                    "lever_variation_density_value_per_m": 0.0,
                    "product_rule_residual_density_value_per_m": 0.0,
                    "waterline_contour_density_value_per_m": 2.0,
                    "boundary_density_value_per_m": 2.0,
                    "section_endpoint_panel_density_value_per_m": 2.0,
                    "section_interior_panel_density_value_per_m": 0.0,
                    "mapping_residual_density_value_per_m": 0.0,
                },
            ]
        )

        summary = _ma2005_row_measure_zero_mi_boundary_summary(detail, "synthetic")

        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertEqual(row["residual_source_class"], "section_endpoint_or_waterline_panel_dominant")
        self.assertEqual(row["diagnostic_conclusion"], "zero_mi_nonzero_transport_source_localized")
        self.assertAlmostEqual(float(row["zero_mi_residual_integral_value"]), 6.0)
        self.assertAlmostEqual(float(row["normal_variation_integral_value"]), 4.0)
        self.assertAlmostEqual(float(row["panel_length_variation_integral_value"]), 2.0)
        self.assertAlmostEqual(float(row["decomposition_closure_residual"]), 0.0)
        self.assertAlmostEqual(float(row["section_endpoint_panel_abs_share"]), 1.0)
        self.assertAlmostEqual(float(row["boundary_abs_share"]), 1.0)
        self.assertAlmostEqual(float(row["lever_variation_abs_share"]), 0.0)
        self.assertEqual(str(row["candidate_default_gate_eligible"]).lower(), "false")
        self.assertEqual(row["path_diagnostic_status"], "INFO")

    def test_ma2005_zero_mi_normal_transport_candidate_audit_quantifies_candidate_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "reference_value": 2.0,
                        "computed_value": 5.0,
                        "tolerance": 0.15,
                        "gate_error_ratio": 10.0,
                        "normalization": "ma2005",
                        "row": 0,
                    }
                ]
            )
            zero_mi_summary = pd.DataFrame(
                [
                    {
                        "source_row": 0,
                        "coefficient": "B33",
                        "zero_mi_residual_integral_value": -3.0,
                        "normal_variation_integral_value": -2.0,
                        "eq31_minus_eq32_boundary_proxy_integral_value": -2.5,
                    }
                ]
            )

            detail, summary = _write_ma2005_zero_mi_normal_transport_candidate_audit(
                comparison,
                zero_mi_summary,
                tmp_path,
                "synthetic",
            )

            self.assertGreater(len(detail), 0)
            self.assertGreater(len(summary), 0)
            self.assertTrue((tmp_path / "synthetic_zero_mi_normal_transport_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_zero_mi_normal_transport_candidate_summary.csv").exists())
            self.assertIn("add_full_zero_m3_transport", set(detail["candidate_name"].astype(str)))
            closing = detail[detail["candidate_name"].eq("add_full_zero_m3_transport")].iloc[0]
            self.assertAlmostEqual(float(closing["candidate_computed_value"]), 2.0)
            self.assertEqual(closing["candidate_status"], "PASS")
            self.assertEqual(str(closing["candidate_default_gate_eligible"]).lower(), "false")
            best = summary.iloc[0]
            self.assertEqual(best["candidate_name"], "add_full_zero_m3_transport")
            self.assertEqual(int(best["pass_count"]), 1)
            self.assertEqual(str(best["candidate_default_gate_eligible"]).lower(), "false")
            self.assertEqual(best["path_diagnostic_status"], "INFO")

    def test_ma2005_zero_m3_transport_scale_requirement_audit_rejects_nonuniform_scales(self):
        candidate_detail = pd.DataFrame(
            [
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "B33",
                    "source_row": 1,
                    "reference_value": 2.0,
                    "current_computed_value": 5.0,
                    "candidate_delta_value": -3.0,
                    "candidate_computed_value": 2.0,
                    "candidate_gate_error_ratio": 0.0,
                    "candidate_status": "PASS",
                },
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "A35",
                    "source_row": 2,
                    "reference_value": -1.0,
                    "current_computed_value": -3.0,
                    "candidate_delta_value": 1.0,
                    "candidate_computed_value": -2.0,
                    "candidate_gate_error_ratio": 3.0,
                    "candidate_status": "FAIL",
                },
                {
                    "candidate_name": "add_full_zero_m3_transport",
                    "coefficient": "B35",
                    "source_row": 3,
                    "reference_value": 0.5,
                    "current_computed_value": 6.5,
                    "candidate_delta_value": -1.0,
                    "candidate_computed_value": 5.5,
                    "candidate_gate_error_ratio": 20.0,
                    "candidate_status": "FAIL",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            detail, summary = _write_ma2005_zero_m3_transport_scale_requirement_audit(
                candidate_detail,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_zero_m3_transport_scale_requirement_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_zero_m3_transport_scale_requirement_summary.csv").exists())

            self.assertEqual(len(detail), 3)
            self.assertEqual(len(summary), 1)
            row = summary.iloc[0]
            self.assertEqual(row["candidate_name"], "add_full_zero_m3_transport")
            self.assertAlmostEqual(float(row["required_scale_min"]), 1.0)
            self.assertAlmostEqual(float(row["required_scale_max"]), 6.0)
            self.assertGreater(float(row["required_scale_max_over_min_abs"]), 2.0)
            self.assertEqual(row["diagnostic_conclusion"], "zero_m3_transport_requires_nonuniform_row_scales")
            self.assertEqual(int(row["median_scale_pass_count"]), 1)
            self.assertEqual(str(row["candidate_default_gate_eligible"]).lower(), "false")

            impact = _write_ma2005_candidate_impact_summary(
                pd.DataFrame(),
                tmp_path,
                "synthetic",
                zero_m3_transport_scale_requirement_summary=summary,
            )
            self.assertIn("zero_m3_transport_scale_requirement", set(impact["candidate_family"].astype(str)))
            self.assertIn("add_full_zero_m3_transport", set(impact["candidate_name"].astype(str)))

    def test_ma2005_force_assembly_route_candidate_audit_reports_explicit_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 0,
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "reference_value": 1.0,
                        "computed_value": 3.0,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 10.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 1.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 3.0,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 2.0,
                        "matched_candidate_time_plus_stokes_body_value": 1.5,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 1.2,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 0.8,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 3.2,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 2.8,
                        "matched_candidate_all_terms_value": 4.0,
                        "matched_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    }
                ]
            )

            detail, summary = _write_ma2005_force_assembly_route_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_force_assembly_route_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_force_assembly_route_candidate_summary.csv").exists())
            self.assertEqual(len(detail), 9)
            self.assertEqual(
                set(summary["force_assembly_route"].astype(str)),
                {
                    "current_hybrid_pressure_gradient_plus_end",
                    "eq31_pressure_gradient_only",
                    "eq32_stokes_body_plus_end",
                    "eq32_stokes_body_only",
                    "eq31_pressure_gradient_plus_row_measure_transport",
                    "eq31_pressure_gradient_minus_row_measure_transport",
                    "eq31_pressure_gradient_plus_row_measure_transport_plus_end",
                    "eq31_pressure_gradient_minus_row_measure_transport_plus_end",
                    "all_terms_pressure_gradient_stokes_end",
                },
            )
            eq31 = summary[summary["force_assembly_route"].eq("eq31_pressure_gradient_only")].iloc[0]
            self.assertEqual(int(eq31["pass_count"]), 1)
            self.assertEqual(eq31["candidate_gate_status"], "PASS")
            self.assertEqual(str(eq31["candidate_default_gate_eligible"]).lower(), "false")
            current = summary[
                summary["force_assembly_route"].eq("current_hybrid_pressure_gradient_plus_end")
            ].iloc[0]
            self.assertTrue(bool(current["route_matches_current_default"]))
            self.assertEqual(current["path_diagnostic_status"], "INFO")
            interaction_detail, interaction_summary = _write_ma2005_row_measure_end_contour_interaction_audit(
                detail,
                tmp_path,
                "synthetic",
            )
            self.assertTrue((tmp_path / "synthetic_row_measure_end_contour_interaction_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_row_measure_end_contour_interaction_summary.csv").exists())
            self.assertEqual(len(interaction_detail), 2)
            self.assertEqual(
                set(interaction_summary["interaction_name"].astype(str)),
                {"plus_row_measure", "minus_row_measure"},
            )
            plus = interaction_summary[
                interaction_summary["interaction_name"].astype(str).eq("plus_row_measure")
            ].iloc[0]
            self.assertEqual(int(plus["end_contour_hurt_count"]), 1)
            self.assertEqual(str(plus["candidate_default_gate_eligible"]).lower(), "false")
            impact = _write_ma2005_candidate_impact_summary(
                comparison,
                tmp_path,
                "synthetic",
                force_assembly_route_candidate_summary=summary,
            )
            self.assertIn("eq31_pressure_gradient_only", set(impact["candidate_name"].astype(str)))

    def test_ma2005_b33_endpoint_half_station_closure_is_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 1,
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "reference_value": 2.1,
                        "computed_value": 9.1804284,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 22.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 8.678420568,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 9.180428404,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 0.502007836,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 1.066202336,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 16.2906388,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 1.568210172,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 16.792646636,
                        "matched_candidate_all_terms_value": 9.180428404,
                        "matched_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    }
                ]
            )
            route_detail, _ = _write_ma2005_force_assembly_route_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            interaction_detail, _ = _write_ma2005_row_measure_end_contour_interaction_audit(
                route_detail,
                tmp_path,
                "synthetic",
            )
            end_pressure = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "endpoint_label": "configured_end_station",
                        "station_index": 0,
                        "x_over_l": 0.025,
                        "trapz_weight_m": 0.0375,
                        "endpoint_forward_gradient_integral_value": 1.143909141,
                        "endpoint_total_pressure_integral_value": 1.143909141,
                        "end_term_component_value": 0.502007836,
                    }
                ]
            )
            station_forward = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "station_index": 0,
                        "x_m": 0.075,
                        "x_over_l": 0.025,
                        "station_forward_identity_residual_value": 0.6419,
                        "pressure_gradient_density_value_per_m": 30.5042,
                    },
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "station_index": 1,
                        "x_m": 0.150,
                        "x_over_l": 0.050,
                        "station_forward_identity_residual_value": -1.0013,
                        "pressure_gradient_density_value_per_m": -13.3513,
                    },
                ]
            )

            detail, summary = _write_ma2005_b33_endpoint_half_station_closure_audit(
                comparison,
                route_detail,
                interaction_detail,
                end_pressure,
                station_forward,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_b33_endpoint_half_station_closure_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_b33_endpoint_half_station_closure_summary.csv").exists())
            self.assertEqual(len(detail), 1)
            row = detail.iloc[0]
            self.assertEqual(row["row_measure_plus_full_endpoint_forward_status"], "PASS")
            self.assertEqual(row["row_measure_plus_half_endpoint_forward_status"], "FAIL")
            self.assertEqual(str(row["candidate_default_gate_eligible"]).lower(), "false")
            self.assertLess(float(row["row_measure_plus_full_endpoint_forward_gate_error_ratio"]), 1.0)
            self.assertIn("full_endpoint", str(summary["diagnostic_conclusion"].iloc[0]))
            self.assertEqual(str(summary["candidate_default_gate_eligible"].iloc[0]).lower(), "false")

    def test_ma2005_endpoint_forward_route_candidate_stays_local_when_only_b33_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 1,
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "reference_value": 2.1,
                        "computed_value": 9.1804284,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 22.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 8.678420568,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 9.180428404,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 0.502007836,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 1.066202336,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 16.2906388,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 1.568210172,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 16.792646636,
                        "matched_candidate_all_terms_value": 9.180428404,
                        "matched_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    },
                    {
                        "row": 2,
                        "coefficient": "A35",
                        "provider_route": "matched_bie_station_sweep",
                        "reference_value": -0.2,
                        "computed_value": -2.7,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 40.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": -1.5,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": -1.6,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": -0.1,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": -0.7,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": -2.3,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": -0.8,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": -2.4,
                        "matched_candidate_all_terms_value": -1.6,
                        "matched_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    },
                ]
            )
            route_detail, _ = _write_ma2005_force_assembly_route_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            end_pressure = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "endpoint_label": "configured_end_station",
                        "endpoint_forward_gradient_integral_value": 1.143909141,
                        "endpoint_total_pressure_integral_value": 1.143909141,
                        "end_term_component_value": 0.502007836,
                    },
                    {
                        "source_row": 2,
                        "coefficient": "A35",
                        "endpoint_label": "configured_end_station",
                        "endpoint_forward_gradient_integral_value": 0.05,
                        "endpoint_total_pressure_integral_value": 0.05,
                        "end_term_component_value": -0.1,
                    },
                ]
            )

            detail, summary = _write_ma2005_endpoint_forward_route_candidate_audit(
                comparison,
                route_detail,
                end_pressure,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_endpoint_forward_route_candidate_detail.csv").exists())
            self.assertTrue((tmp_path / "synthetic_endpoint_forward_route_candidate_summary.csv").exists())
            full = summary[
                summary["candidate_name"].astype(str).eq("row_measure_plus_configured_endpoint_forward")
            ].iloc[0]
            self.assertEqual(int(full["pass_count"]), 1)
            self.assertIn("B33", str(full["passing_coefficients"]))
            self.assertIn("A35", str(full["failing_coefficients"]))
            self.assertEqual(str(full["candidate_default_gate_eligible"]).lower(), "false")
            b33 = detail[
                detail["coefficient"].astype(str).eq("B33")
                & detail["candidate_name"].astype(str).eq("row_measure_plus_configured_endpoint_forward")
            ].iloc[0]
            self.assertEqual(b33["candidate_status"], "PASS")

    def test_ma2005_heave_row_pitch_column_split_separates_b33_from_a35_b35(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 1,
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": 2.0,
                        "reference_value": 2.1,
                        "computed_value": 9.18,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 22.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 8.6,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 9.1,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 0.5,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 1.066202336,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 16.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 1.568210172,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 16.5,
                        "matched_candidate_all_terms_value": 9.1,
                    },
                    {
                        "row": 2,
                        "coefficient": "A35",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": 1.5,
                        "reference_value": -0.2,
                        "computed_value": -2.7,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 41.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": -1.5,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": -1.6,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": -0.1,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": -1.25,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": -2.2,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": -1.35,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": -2.3,
                        "matched_candidate_all_terms_value": -1.6,
                    },
                    {
                        "row": 3,
                        "coefficient": "B35",
                        "provider_route": "matched_bie_station_sweep",
                        "omega_e_sqrt_l_over_g": 2.5,
                        "reference_value": 0.13,
                        "computed_value": 6.5,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 160.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 6.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 6.5,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 0.5,
                        "matched_candidate_time_plus_stokes_body_value": 0.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 5.0,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 7.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 5.5,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 7.5,
                        "matched_candidate_all_terms_value": 6.5,
                    },
                ]
            )
            route_detail, _ = _write_ma2005_force_assembly_route_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )
            end_pressure = pd.DataFrame(
                [
                    {
                        "source_row": 1,
                        "coefficient": "B33",
                        "endpoint_label": "configured_end_station",
                        "endpoint_forward_gradient_integral_value": 1.143909141,
                        "endpoint_total_pressure_integral_value": 1.143909141,
                        "end_term_component_value": 0.502007836,
                    },
                    {
                        "source_row": 2,
                        "coefficient": "A35",
                        "endpoint_label": "configured_end_station",
                        "endpoint_forward_gradient_integral_value": -0.20,
                        "endpoint_total_pressure_integral_value": -0.20,
                        "end_term_component_value": -0.10,
                    },
                    {
                        "source_row": 3,
                        "coefficient": "B35",
                        "endpoint_label": "configured_end_station",
                        "endpoint_forward_gradient_integral_value": 0.60,
                        "endpoint_total_pressure_integral_value": 0.60,
                        "end_term_component_value": 0.50,
                    },
                ]
            )
            endpoint_detail, _ = _write_ma2005_endpoint_forward_route_candidate_audit(
                comparison,
                route_detail,
                end_pressure,
                tmp_path,
                "synthetic",
            )
            formula = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "row_family": "heave_row_N3_m3",
                        "column_family": "heave_radiation",
                        "eq31_eq32_proxy_residual_norm": 0.8,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                    {
                        "coefficient": "A35",
                        "row_family": "heave_row_N3_m3",
                        "column_family": "pitch_radiation",
                        "eq31_eq32_proxy_residual_norm": 0.9,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                    {
                        "coefficient": "B35",
                        "row_family": "heave_row_N3_m3",
                        "column_family": "pitch_radiation",
                        "eq31_eq32_proxy_residual_norm": 0.95,
                        "dominant_formula_component": "interior_distributed_transport",
                    },
                ]
            )
            pairing = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "partner_coefficient": "A33",
                        "partner_omega_e_sqrt_l_over_g": 1.0,
                        "pair_status": "frequency_mismatch_ab_pair",
                        "complex_force_closure_evaluable": "false",
                    },
                    {
                        "coefficient": "A35",
                        "partner_coefficient": "B35",
                        "partner_omega_e_sqrt_l_over_g": 2.5,
                        "pair_status": "frequency_mismatch_ab_pair",
                        "complex_force_closure_evaluable": "false",
                    },
                    {
                        "coefficient": "B35",
                        "partner_coefficient": "A35",
                        "partner_omega_e_sqrt_l_over_g": 1.5,
                        "pair_status": "frequency_mismatch_ab_pair",
                        "complex_force_closure_evaluable": "false",
                    },
                ]
            )

            detail, summary = _write_ma2005_heave_row_pitch_column_split_audit(
                comparison,
                route_detail,
                endpoint_detail,
                formula,
                pairing,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_heave_row_pitch_column_split_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_heave_row_pitch_column_split_summary.csv").exists())
            self.assertEqual(set(detail["coefficient"].astype(str)), {"B33", "A35", "B35"})
            b33 = detail[detail["coefficient"].astype(str).eq("B33")].iloc[0]
            self.assertEqual(b33["endpoint_forward_status"], "PASS")
            self.assertEqual(int(summary["endpoint_forward_pass_count"].iloc[0]), 1)
            self.assertEqual(int(summary["pitch_column_endpoint_forward_pass_count"].iloc[0]), 0)
            self.assertIn("does_not_generalize", str(summary["diagnostic_conclusion"].iloc[0]))
            self.assertEqual(str(summary["candidate_default_gate_eligible"].iloc[0]).lower(), "false")

    def test_ma2005_force_assembly_theory_consistency_audit_flags_mixed_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 0,
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "reference_value": 1.0,
                        "computed_value": 3.0,
                        "tolerance": 0.15,
                        "normalization": "ma2005",
                        "gate_error_ratio": 10.0,
                        "status": "FAIL",
                        "matched_candidate_time_plus_pressure_gradient_value": 1.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 3.0,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 2.0,
                        "matched_candidate_time_plus_stokes_body_value": 1.5,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_value": 1.2,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_value": 0.8,
                        "matched_candidate_time_plus_pressure_gradient_plus_row_measure_transport_plus_end_value": 3.2,
                        "matched_candidate_time_plus_pressure_gradient_minus_row_measure_transport_plus_end_value": 2.8,
                        "matched_candidate_all_terms_value": 4.0,
                        "matched_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                    }
                ]
            )
            _, route_summary = _write_ma2005_force_assembly_route_candidate_audit(
                comparison,
                tmp_path,
                "synthetic",
            )

            detail, summary = _write_ma2005_force_assembly_theory_consistency_audit(
                comparison,
                route_summary,
                tmp_path,
                "synthetic",
            )

            self.assertTrue((tmp_path / "synthetic_force_assembly_theory_consistency_audit.csv").exists())
            self.assertTrue((tmp_path / "synthetic_force_assembly_theory_consistency_summary.csv").exists())
            current = detail[
                detail["force_assembly_route"].astype(str).eq("current_hybrid_pressure_gradient_plus_end")
            ].iloc[0]
            self.assertEqual(
                current["canonical_status"],
                "noncanonical_mixed_eq31_gradient_with_eq32_end_contour",
            )
            self.assertFalse(bool(current["theory_consistent_default_candidate"]))
            eq31 = detail[detail["force_assembly_route"].astype(str).eq("eq31_pressure_gradient_only")].iloc[0]
            self.assertEqual(eq31["canonical_status"], "canonical_eq31_direct_pressure_gradient")
            self.assertTrue(bool(eq31["theory_consistent_default_candidate"]))
            self.assertEqual(str(eq31["candidate_default_gate_eligible"]).lower(), "false")
            row = summary.iloc[0]
            self.assertEqual(row["diagnostic_conclusion"], "active_default_route_is_noncanonical_eq31_eq32_mixture")
            self.assertFalse(bool(row["active_default_is_canonical"]))
            self.assertEqual(int(row["canonical_route_count"]), 2)
            self.assertFalse(bool(row["default_migration_allowed_by_current_evidence"]))

    def test_ma2005_eq30_component_contribution_audit_reports_required_scales(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 0,
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "matched_actual_force_assembly_route": "current_hybrid_pressure_gradient_plus_end",
                        "reference_value": 1.0,
                        "computed_value": 11.0,
                        "abs_error": 10.0,
                        "rel_error": 10.0,
                        "effective_abs_tolerance": 0.15,
                        "gate_error_ratio": 10.0 / 0.15,
                        "status": "FAIL",
                        "matched_time_derivative_component_value": 10.0,
                        "matched_pressure_gradient_component_value": 2.0,
                        "matched_stokes_body_forward_component_value": 3.0,
                        "matched_end_term_component_value": -1.0,
                        "matched_force_closure_residual_value": 0.0,
                        "matched_candidate_time_only_value": 10.0,
                        "matched_candidate_time_plus_pressure_gradient_value": 12.0,
                        "matched_candidate_time_plus_pressure_gradient_plus_end_value": 11.0,
                        "matched_candidate_time_plus_stokes_body_plus_end_value": 12.0,
                        "matched_candidate_best_combination": "time_only",
                        "matched_candidate_best_value": 10.0,
                        "matched_candidate_best_abs_relative_error": 9.0,
                    }
                ]
            )
            detail, summary = _write_ma2005_eq30_component_contribution_audit(
                comparison,
                tmp_path,
                "ma2005_wigley_iii_coefficients",
            )
            self.assertEqual(len(detail), 1)
            self.assertEqual(len(summary), 1)
            row = detail.iloc[0]
            self.assertEqual(row["dominant_current_default_component"], "time_derivative_pressure")
            self.assertEqual(row["component_failure_source"], "time_derivative_body_potential_scale")
            self.assertAlmostEqual(float(row["required_time_derivative_scale_if_only_adjusted"]), 0.0)
            self.assertAlmostEqual(float(row["required_pressure_gradient_scale_if_only_adjusted"]), -4.0)
            self.assertEqual(summary["path_diagnostic_status"].iloc[0], "INFO")
            self.assertTrue(bool(summary["finite_numeric_outputs"].iloc[0]))

    def test_ma2005_eq30_component_contribution_audit_reconstructs_selected_eq32_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "row": 0,
                        "coefficient": "A33",
                        "provider_route": "matched_bie_station_sweep",
                        "matched_actual_force_assembly_route": "eq32_stokes_body_plus_end",
                        "reference_value": 12.0,
                        "computed_value": 12.0,
                        "abs_error": 0.0,
                        "rel_error": 0.0,
                        "effective_abs_tolerance": 0.15,
                        "gate_error_ratio": 0.0,
                        "status": "PASS",
                        "matched_time_derivative_component_value": 10.0,
                        "matched_pressure_gradient_component_value": 20.0,
                        "matched_stokes_body_forward_component_value": 3.0,
                        "matched_row_measure_transport_component_value": 4.0,
                        "matched_end_term_component_value": -1.0,
                        "matched_force_closure_residual_value": 0.0,
                    }
                ]
            )
            detail, summary = _write_ma2005_eq30_component_contribution_audit(
                comparison,
                tmp_path,
                "ma2005_wigley_iii_coefficients",
            )
            row = detail.iloc[0]
            self.assertEqual(row["force_assembly_route"], "eq32_stokes_body_plus_end")
            self.assertAlmostEqual(float(row["current_default_reconstructed_value"]), 12.0)
            self.assertEqual(row["dominant_current_default_component"], "time_derivative_pressure")
            self.assertTrue(bool(summary["finite_numeric_outputs"].iloc[0]))

    def test_ma2005_station_mapping_gradient_audit_flags_forward_gradient_mapping_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            station_transfer_path = pd.DataFrame(
                [
                    {
                        "benchmark": "synthetic",
                        "coefficient": "B33",
                        "pair_index": 0,
                        "x_mid_over_l": 0.0375,
                        "pressure_gradient_density_abs_pair_max": 25.0,
                        "body_potential_adjacent_relative_jump": 0.8,
                        "body_potential_adjacent_phase_deg": 180.0,
                        "phase_aligned_body_potential_adjacent_relative_jump": 0.75,
                        "body_panel_mid_y_adjacent_relative_jump": 0.35,
                        "body_panel_mid_z_adjacent_relative_jump": 0.02,
                        "body_panel_normal_adjacent_relative_jump": 0.1,
                        "body_panel_length_adjacent_relative_jump": 0.08,
                        "station_waterplane_beam_adjacent_relative_jump": 0.4,
                        "station_effective_draft_adjacent_relative_jump": 0.1,
                        "station_submerged_area_adjacent_relative_jump": 0.45,
                        "body_potential_x_gradient_gain_times_l_pair_max": 80.0,
                        "phase_aligned_gradient_gain_to_raw_gain_ratio_pair_max": 1.7,
                        "central_gradient_gain_times_l_pair_max": 80.0,
                        "forward_gradient_gain_times_l_pair_max": 120.0,
                        "backward_gradient_gain_times_l_pair_max": 60.0,
                        "pressure_gradient_density_pair_sign_change": "False",
                    }
                ]
            )
            component_audit = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "status": "FAIL",
                        "component_failure_source": "forward_speed_pressure_gradient_station_mapping",
                        "dominant_current_default_component": "forward_speed_pressure_gradient",
                        "reference_value": 2.1,
                        "computed_value": 9.6,
                        "gate_error_ratio": 24.0,
                        "required_pressure_gradient_scale_if_only_adjusted": 0.16,
                    }
                ]
            )
            detail, summary = _write_ma2005_station_mapping_gradient_audit(
                station_transfer_path,
                component_audit,
                tmp_path,
                "synthetic",
            )
            self.assertEqual(len(detail), 1)
            self.assertEqual(len(summary), 1)
            self.assertEqual(
                detail["diagnostic_conclusion"].iloc[0],
                "forward_gradient_failure_coincides_with_station_mapping_jump",
            )
            self.assertIn("large_body_potential_adjacent_jump", detail["mapping_risk_flags"].iloc[0])
            self.assertIn("large_station_geometry_jump", detail["mapping_risk_flags"].iloc[0])
            self.assertEqual(int(summary["forward_gradient_failure_count"].iloc[0]), 1)
            self.assertEqual(int(summary["high_mapping_risk_count"].iloc[0]), 1)
            self.assertEqual(summary["path_diagnostic_status"].iloc[0], "INFO")

    def test_ma2005_station_marching_direction_audit_separates_aft_peak_from_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "status": "FAIL",
                        "reference_value": 2.1,
                        "computed_value": 9.6,
                        "gate_error_ratio": 24.0,
                        "speed_mps": 4.0,
                        "hull_length_m": 3.0,
                        "station_count": 40,
                        "matched_station_solve_order_first_index": 39,
                        "matched_station_solve_order_last_index": 0,
                        "matched_station_solve_order_first_x_over_l": 0.975,
                        "matched_station_solve_order_last_x_over_l": 0.025,
                        "matched_station_solve_order_first_local_time_s": 0.01875,
                        "matched_station_solve_order_last_local_time_s": 0.73125,
                        "matched_station_solve_order_x_over_l_monotonic_decreasing": "True",
                        "matched_station_solve_order_local_time_monotonic_increasing": "True",
                        "matched_station_solve_order_matches_a1_local_time": "True",
                        "matched_end_term_station_x_over_l": 0.025,
                        "matched_aft_active_station_x_over_l": 0.025,
                        "matched_selected_forward_speed_force_density_peak_x_over_l": 0.0375,
                    }
                ]
            )
            station_transfer_path = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "pair_index": 0,
                        "x_mid_over_l": 0.0375,
                        "pressure_gradient_density_abs_pair_max": 10.0,
                    },
                    {
                        "coefficient": "B33",
                        "pair_index": 1,
                        "x_mid_over_l": 0.5,
                        "pressure_gradient_density_abs_pair_max": 2.0,
                    },
                ]
            )
            detail, summary = _write_ma2005_station_marching_direction_audit(
                comparison,
                station_transfer_path,
                tmp_path,
                "synthetic",
            )
            self.assertEqual(len(detail), 1)
            self.assertEqual(len(summary), 1)
            self.assertTrue(bool(detail["solve_order_matches_a1_local_time"].iloc[0]))
            self.assertTrue(bool(detail["pressure_gradient_peak_near_aft_end"].iloc[0]))
            self.assertFalse(bool(detail["pressure_gradient_peak_near_marching_start"].iloc[0]))
            self.assertEqual(
                detail["diagnostic_conclusion"].iloc[0],
                "a1_marching_direction_consistent_gradient_peak_is_aft_terminal",
            )
            self.assertEqual(int(summary["a1_marching_match_count"].iloc[0]), 1)
            self.assertEqual(int(summary["pressure_gradient_peak_near_aft_end_count"].iloc[0]), 1)
            self.assertEqual(int(summary["pressure_gradient_peak_near_marching_start_count"].iloc[0]), 0)
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains",
            )

    def test_ma2005_aft_terminal_end_closure_audit_flags_nonterminal_residual(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparison = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "provider_route": "matched_bie_station_sweep",
                        "status": "FAIL",
                        "reference_value": 2.1,
                        "computed_value": 9.6,
                        "gate_error_ratio": 24.0,
                    }
                ]
            )
            station_forward_identity = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "station_index": 0,
                        "x_over_l": 0.025,
                        "pressure_gradient_station_contribution_value": 2.5,
                        "stokes_body_forward_station_contribution_value": 0.0,
                        "end_contour_station_contribution_value": 2.0,
                        "station_forward_identity_residual_value": 0.5,
                    },
                    {
                        "coefficient": "B33",
                        "station_index": 1,
                        "x_over_l": 0.075,
                        "pressure_gradient_station_contribution_value": 0.5,
                        "stokes_body_forward_station_contribution_value": 0.0,
                        "end_contour_station_contribution_value": 0.0,
                        "station_forward_identity_residual_value": 0.5,
                    },
                    {
                        "coefficient": "B33",
                        "station_index": 2,
                        "x_over_l": 0.5,
                        "pressure_gradient_station_contribution_value": 7.0,
                        "stokes_body_forward_station_contribution_value": 0.0,
                        "end_contour_station_contribution_value": 0.0,
                        "station_forward_identity_residual_value": 7.0,
                    },
                ]
            )
            end_pressure_closure = pd.DataFrame(
                [
                    {
                        "coefficient": "B33",
                        "endpoint_label": "configured_end_station",
                        "x_over_l": 0.025,
                        "endpoint_forward_gradient_integral_value": 2.5,
                        "end_to_endpoint_forward_ratio_abs": 0.8,
                    }
                ]
            )
            detail, summary = _write_ma2005_aft_terminal_end_closure_audit(
                comparison,
                station_forward_identity,
                end_pressure_closure,
                tmp_path,
                "synthetic",
            )
            self.assertEqual(len(detail), 1)
            self.assertEqual(len(summary), 1)
            self.assertAlmostEqual(
                float(detail["required_end_contour_scale_to_close_identity"].iloc[0]),
                5.0,
            )
            self.assertLess(float(detail["terminal_x_0p10_abs_share"].iloc[0]), 0.75)
            self.assertFalse(bool(detail["terminal_band_explains_residual"].iloc[0]))
            self.assertEqual(
                detail["diagnostic_conclusion"].iloc[0],
                "residual_not_explained_by_simple_aft_terminal_band",
            )
            self.assertEqual(
                summary["diagnostic_conclusion"].iloc[0],
                "aft_terminal_band_and_end_scale_do_not_close_gate1",
            )

    def test_ma2005_sl7_table2_lcg_defaults_to_transom_coordinate(self):
        row = pd.Series(
            {
                "hull": "sl7",
                "length_m": 268.4,
                "beam_m": 32.16,
                "draft_m": 9.94,
                "station_count": 5,
            }
        )
        meta = _ma2005_geometry_metadata(row)
        hull = _ma2005_hull_from_row(row)
        self.assertAlmostEqual(float(meta["lcg_aft_of_amidship_m"]), 11.7)
        self.assertAlmostEqual(float(meta["lcg_from_transom_m"]), 122.5)
        self.assertAlmostEqual(hull.lcg_m, 122.5)
        self.assertEqual(meta["lcg_source"], "defaulted_from_ma2005_table2_lcg_aft_of_amidship")
        self.assertEqual(meta["geometry_status"], "SURROGATE_NEEDS_REAL_OFFSETS")
        self.assertEqual(meta["validation_status"], "NOT_EVALUATED")

    def test_ma2005_matched_bie_cache_key_tracks_diagnostic_settings(self):
        base = pd.Series(
            {
                "hull": "wigley_iii",
                "length_m": 3.0,
                "beam_m": 0.3,
                "draft_m": 0.1875,
                "station_count": 9,
            }
        )
        larger_history = base.copy()
        larger_history["matched_history_steps"] = 4
        wider_control = base.copy()
        wider_control["matched_control_surface_radius_beams"] = 4.0
        no_marching = base.copy()
        no_marching["matched_use_free_surface_marching"] = False
        half_velocity = base.copy()
        half_velocity["matched_free_surface_velocity_scale"] = 0.5
        two_substeps = base.copy()
        two_substeps["matched_free_surface_substeps_per_station"] = 2
        imaginary_source = base.copy()
        imaginary_source["matched_free_surface_normal_derivative_source"] = "imaginary_part_only"
        reverse_time = base.copy()
        reverse_time["matched_free_surface_time_direction_sign"] = -1.0
        previous_level = base.copy()
        previous_level["matched_free_surface_potential_elevation_level"] = "previous"
        control_row_source = base.copy()
        control_row_source["matched_control_row_free_surface_potential_source"] = "after_station"
        clipped_free_surface = base.copy()
        clipped_free_surface["matched_clip_inner_free_surface_to_waterline"] = False
        two_zone_free_surface = base.copy()
        two_zone_free_surface["matched_clip_inner_free_surface_to_waterline"] = True
        two_zone_free_surface["matched_two_zone_inner_free_surface"] = True
        free_rhs_removed = base.copy()
        free_rhs_removed["matched_inner_free_surface_known_potential_rhs_scale"] = 0.0
        free_rhs_body_row_removed = base.copy()
        free_rhs_body_row_removed["matched_inner_free_surface_known_potential_body_row_scale"] = 0.0
        free_rhs_free_row_removed = base.copy()
        free_rhs_free_row_removed["matched_inner_free_surface_known_potential_free_row_scale"] = 0.0
        free_rhs_control_row_removed = base.copy()
        free_rhs_control_row_removed["matched_inner_free_surface_known_potential_control_row_scale"] = 0.0
        free_unknown_flipped = base.copy()
        free_unknown_flipped["matched_inner_free_surface_unknown_normal_column_scale"] = -1.0
        eq32_route = base.copy()
        eq32_route["matched_force_assembly_route"] = "current_hybrid_pressure_gradient_plus_end"

        default_key = _ma2005_matrix_cache_key(base, 2.0, 1.0, "matched_bie", 4, 8)
        history_key = _ma2005_matrix_cache_key(larger_history, 2.0, 1.0, "matched_bie_provider", 4, 8)
        control_key = _ma2005_matrix_cache_key(wider_control, 2.0, 1.0, "matched_bie_provider", 4, 8)
        no_marching_key = _ma2005_matrix_cache_key(no_marching, 2.0, 1.0, "matched_bie_provider", 4, 8)
        half_velocity_key = _ma2005_matrix_cache_key(half_velocity, 2.0, 1.0, "matched_bie_provider", 4, 8)
        two_substeps_key = _ma2005_matrix_cache_key(two_substeps, 2.0, 1.0, "matched_bie_provider", 4, 8)
        imaginary_source_key = _ma2005_matrix_cache_key(imaginary_source, 2.0, 1.0, "matched_bie_provider", 4, 8)
        reverse_time_key = _ma2005_matrix_cache_key(reverse_time, 2.0, 1.0, "matched_bie_provider", 4, 8)
        previous_level_key = _ma2005_matrix_cache_key(previous_level, 2.0, 1.0, "matched_bie_provider", 4, 8)
        control_row_source_key = _ma2005_matrix_cache_key(
            control_row_source,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        clipped_free_surface_key = _ma2005_matrix_cache_key(
            clipped_free_surface,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        two_zone_free_surface_key = _ma2005_matrix_cache_key(
            two_zone_free_surface,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        free_rhs_removed_key = _ma2005_matrix_cache_key(free_rhs_removed, 2.0, 1.0, "matched_bie_provider", 4, 8)
        free_rhs_body_row_removed_key = _ma2005_matrix_cache_key(
            free_rhs_body_row_removed,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        free_rhs_free_row_removed_key = _ma2005_matrix_cache_key(
            free_rhs_free_row_removed,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        free_rhs_control_row_removed_key = _ma2005_matrix_cache_key(
            free_rhs_control_row_removed,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        free_unknown_flipped_key = _ma2005_matrix_cache_key(
            free_unknown_flipped,
            2.0,
            1.0,
            "matched_bie_provider",
            4,
            8,
        )
        eq32_route_key = _ma2005_matrix_cache_key(eq32_route, 2.0, 1.0, "matched_bie_provider", 4, 8)

        self.assertNotEqual(default_key, history_key)
        self.assertNotEqual(default_key, control_key)
        self.assertNotEqual(default_key, no_marching_key)
        self.assertNotEqual(default_key, half_velocity_key)
        self.assertNotEqual(default_key, two_substeps_key)
        self.assertNotEqual(default_key, imaginary_source_key)
        self.assertNotEqual(default_key, reverse_time_key)
        self.assertNotEqual(default_key, previous_level_key)
        self.assertNotEqual(default_key, control_row_source_key)
        self.assertNotEqual(default_key, clipped_free_surface_key)
        self.assertNotEqual(default_key, two_zone_free_surface_key)
        self.assertNotEqual(clipped_free_surface_key, two_zone_free_surface_key)
        self.assertNotEqual(default_key, free_rhs_removed_key)
        self.assertNotEqual(default_key, free_rhs_body_row_removed_key)
        self.assertNotEqual(default_key, free_rhs_free_row_removed_key)
        self.assertNotEqual(default_key, free_rhs_control_row_removed_key)
        self.assertNotEqual(free_rhs_body_row_removed_key, free_rhs_free_row_removed_key)
        self.assertNotEqual(free_rhs_body_row_removed_key, free_rhs_control_row_removed_key)
        self.assertNotEqual(free_rhs_free_row_removed_key, free_rhs_control_row_removed_key)
        self.assertNotEqual(default_key, free_unknown_flipped_key)
        self.assertNotEqual(default_key, eq32_route_key)
        self.assertEqual(default_key[0], "matched_bie_provider")

    def test_ma2005_sl7_geometry_audit_is_written_and_offsets_gap_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "sl7",
                    "speed_case": "synthetic",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 268.4,
                    "beam_m": 32.16,
                    "draft_m": 9.94,
                    "displacement_volume_m3": 47184.39024390244,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(base)["computed_value"]
            pd.DataFrame([{**base.to_dict(), "reference_value": expected}]).to_csv(
                data_dir / "sl7_coefficients_digitized.csv",
                index=False,
            )
            out_dir = tmp_path / "out"
            summary = validate_goal_gap_audit(out_dir, reference_root)
            metrics = set(summary["metric"])
            self.assertIn("ma2005_sl7_coefficients_geometry_audit", metrics)
            self.assertIn("ma2005_sl7_coefficients_sl7_real_offsets_available", metrics)
            offset_row = summary[summary["metric"].eq("ma2005_sl7_coefficients_sl7_real_offsets_available")].iloc[0]
            self.assertEqual(offset_row["status"], "NOT_EVALUATED")
            audit = pd.read_csv(out_dir / "ma2005_sl7_coefficients_geometry_audit.csv")
            self.assertEqual(audit["geometry_status"].iloc[0], "SURROGATE_NEEDS_REAL_OFFSETS")
            self.assertAlmostEqual(audit["lcg_from_transom_m"].iloc[0], 122.5)
            comparison = pd.read_csv(out_dir / "ma2005_sl7_coefficients_comparison.csv")
            self.assertIn("geometry_status", comparison.columns)
            self.assertIn("lcg_source", comparison.columns)
            self.assertEqual(comparison["geometry_status"].iloc[0], "SURROGATE_NEEDS_REAL_OFFSETS")

    def test_faltinsen_case_reconstructs_prescribed_state(self):
        case = make_faltinsen_ch9_case()
        self.assertAlmostEqual(case.equilibrium.fn_b, 3.0, places=12)
        self.assertAlmostEqual(case.equilibrium.trim_deg, 4.0, places=12)
        self.assertAlmostEqual(case.equilibrium.geometry.lambda_w, 4.0, places=6)

    def test_validation_writes_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_faltinsen_ch9(out_dir)
            self.assertTrue((out_dir / "validation_summary.csv").exists())
            self.assertTrue((out_dir / "validation_status_by_benchmark.csv").exists())
            self.assertTrue((out_dir / "validation_report.md").exists())
            self.assertTrue((out_dir / "faltinsen_ch9_eigenvalues.csv").exists())
            self.assertTrue((out_dir / "faltinsen_ch9_rao.csv").exists())
            self.assertTrue((out_dir / "figures" / "faltinsen_ch9_rao.png").exists())
            report = (out_dir / "validation_report.md").read_text(encoding="utf-8")
            self.assertIn("Status By Benchmark", report)
            self.assertIn("Faltinsen Table 9.2 Eigenvalues", report)
            eigenvalues = pd.read_csv(out_dir / "faltinsen_ch9_eigenvalues.csv")
            self.assertEqual(len(eigenvalues), 2)
            self.assertIn("actual_eigenvalue_nondim", eigenvalues.columns)
            self.assertIn("mode_status", eigenvalues.columns)
            self.assertTrue(eigenvalues["mode"].str.contains("mode_").all())
            self.assertIn("prescribed_lambda_w", set(summary["metric"]))
            self.assertIn("heave_rao_digitized_peak_amplitude", set(summary["metric"]))
            self.assertIn("pitch_rao_digitized_peak_amplitude", set(summary["metric"]))

    def test_ma2005_gap_summary_is_reportable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pd.DataFrame(
                [
                    {
                        "benchmark": "ma2005_wigley_iii_coefficients",
                        "summary_type": "overall_best",
                        "coefficient": "all",
                        "hydro_model": "hybrid_forward_coupling",
                        "pass_checks": 39,
                        "fail_checks": 16,
                        "total_checks": 55,
                        "pass_fraction": 39 / 55,
                        "median_gate_error_ratio": 0.66,
                        "max_gate_error_ratio": 3.2,
                        "blocker_coefficients": "B53(6/8), B35(3/3)",
                        "recommendation": "diagnostic only",
                        "filter": "all rows",
                    },
                    {
                        "benchmark": "ma2005_wigley_iii_coefficients",
                        "summary_type": "best_model_blocker",
                        "coefficient": "B53",
                        "hydro_model": "hybrid_forward_coupling",
                        "pass_checks": 2,
                        "fail_checks": 6,
                        "total_checks": 8,
                        "pass_fraction": 0.25,
                        "median_gate_error_ratio": 1.7,
                        "max_gate_error_ratio": "",
                        "blocker_coefficients": "B53",
                        "recommendation": "damping coupling: audit forward-speed pressure-gradient.",
                        "filter": "all rows",
                    },
                ]
            ).to_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_gap_summary.csv", index=False)
            pd.DataFrame(
                [
                    {
                        "benchmark": "ma2005_wigley_iii_coefficients",
                        "coefficient": "B53",
                        "priority_rank": 1,
                        "priority_class": "blocking_all_candidate_models",
                        "best_hydro_model": "hybrid_forward_coupling",
                        "best_model_family": "forward_speed_assembly",
                        "best_pass_checks": 2,
                        "best_fail_checks": 6,
                        "best_total_checks": 8,
                        "best_fail_fraction": 0.75,
                        "best_median_gate_error_ratio": 1.7,
                        "best_max_gate_error_ratio": 3.2,
                        "accepted_diagnostic_models": "none",
                        "recommendation": "damping coupling: audit forward-speed pressure-gradient.",
                        "next_evidence_needed": "inspect pressure-gradient phase",
                        "filter": "all rows",
                    }
                ]
            ).to_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_blocker_ranking.csv", index=False)
            pd.DataFrame(
                [
                    {
                        "benchmark": "ma2005_wigley_iii_coefficients",
                        "hydro_model": "hybrid_forward_coupling",
                        "model_family": "hybrid",
                        "coefficient": "B53",
                        "case_count": 8,
                        "pass_checks": 2,
                        "fail_checks": 6,
                        "reference_log_abs_slope_vs_log_omega": 0.8,
                        "computed_log_abs_slope_vs_log_omega": -0.1,
                        "scaled_computed_log_abs_slope_vs_log_omega": -0.1,
                        "computed_minus_reference_log_slope": -0.9,
                        "signed_shape_correlation": 0.42,
                        "scaled_signed_shape_correlation": 0.42,
                        "best_fit_signed_scale_to_reference": 1.8,
                        "best_fit_normalized_shape_rmse": 0.55,
                        "computed_over_reference_median": 0.5,
                        "computed_over_reference_spread": 2.0,
                        "median_gate_error_ratio": 1.7,
                        "max_gate_error_ratio": 3.2,
                        "shape_status": "frequency_shape_gap",
                        "filter": "all rows",
                    }
                ]
            ).to_csv(
                out_dir / "ma2005_wigley_iii_coefficients_coefficient_frequency_shape_summary.csv",
                index=False,
            )
            lines = _ma2005_hydro_gap_report_lines(out_dir)
            report_text = "\n".join(lines)
            self.assertIn("hybrid_forward_coupling", report_text)
            self.assertIn("B53(6/8)", report_text)
            self.assertIn("forward-speed pressure-gradient", report_text)
            self.assertIn("blocker ranking", report_text)
            self.assertIn("gate_ratio=1.7", report_text)
            self.assertIn("coefficient frequency-shape audit", report_text)
            self.assertIn("corr=0.42", report_text)
            self.assertIn("scaled_rmse=0.55", report_text)
            self.assertIn("slope_delta=-0.9", report_text)

    def test_prescribed_running_state_config_path(self):
        config = load_config(ROOT / "configs" / "faltinsen_ch9_prescribed.yml")
        config.simulation.duration_s = 2.0
        config.simulation.discard_initial_s = 0.5
        config.simulation.time_step_s = 0.08
        config.waves.period_count = 20
        speed = config.speeds()[0]
        result = analyze_speed(config, speed)
        self.assertEqual(result.summary["equilibrium_source"], "prescribed_running_state")
        self.assertAlmostEqual(result.equilibrium.fn_b, 3.0, places=12)
        self.assertAlmostEqual(result.equilibrium.geometry.lambda_w, 4.0, places=6)
        self.assertAlmostEqual(result.equilibrium.trim_deg, 4.0, places=12)
        self.assertGreater(result.equilibrium.geometry.keel_wetted_length_m, result.equilibrium.geometry.chine_wetted_length_m)

    def test_digitized_reference_curve_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "faltinsen_ch9"
            data_dir.mkdir()
            (data_dir / "fig_9_34_heave_rao_digitized.csv").write_text(
                "lambda_over_l,heave_rao_m_per_m\n1.0,1.0\n2.0,4.4\n3.0,2.0\n",
                encoding="utf-8",
            )
            reference = load_reference_curve(
                "faltinsen_ch9",
                "fig_9_34_heave_rao_digitized.csv",
                "lambda_over_l",
                "heave_rao_m_per_m",
                root,
            )
            computed = pd.DataFrame(
                {
                    "lambda_over_l": [1.0, 2.0, 3.0],
                    "heave_rao_m_per_m": [1.0, 4.0, 2.0],
                }
            )
            comparison = compare_reference_curve(computed, "lambda_over_l", "heave_rao_m_per_m", reference)
            self.assertAlmostEqual(comparison.reference_peak_x, 2.0)
            self.assertAlmostEqual(comparison.computed_peak_x, 2.0)
            self.assertLess(comparison.peak_y_rel_error, 0.10)

    def test_validation_consumes_digitized_reference_curves(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "faltinsen_ch9"
            data_dir.mkdir(parents=True)
            case = make_faltinsen_ch9_case()
            matrices = compute_hydro_matrices(case.boat, case.equilibrium)
            rao = solve_rao(case.boat, case.waves, case.equilibrium, matrices, case.bow_x_from_cg_m)
            average_wetted_length = case.equilibrium.geometry.lambda_w * case.boat.beam_m
            rao["lambda_over_l"] = (2.0 * math.pi / rao["wavenumber_rad_m"]) / average_wetted_length
            rao[["lambda_over_l", "heave_rao_m_per_m"]].to_csv(
                data_dir / "fig_9_34_heave_rao_digitized.csv",
                index=False,
            )
            rao[["lambda_over_l", "pitch_rao_rad_per_wave_slope"]].to_csv(
                data_dir / "fig_9_35_pitch_rao_digitized.csv",
                index=False,
            )
            summary = validate_faltinsen_ch9(tmp_path / "out", reference_root)
            metrics = set(summary["metric"])
            self.assertIn("heave_rao_digitized_peak_amplitude", metrics)
            self.assertIn("pitch_rao_digitized_peak_amplitude", metrics)
            self.assertNotIn("heave_rao_digitized_reference_curve", metrics)
            digitized = summary[summary["metric"].str.contains("digitized_peak_amplitude")]
            self.assertTrue(digitized["status"].eq("PASS").all())

    def test_reasonableness_checks_cover_convergence_and_trends(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_reasonableness(out_dir)
            metrics = set(summary["metric"])
            self.assertIn("regular_time_step_convergence_max_rms_change", metrics)
            self.assertIn("irregular_spectrum_component_convergence_max_rms_change", metrics)
            self.assertIn("small_wave_height_heave_m_rms_linearity", metrics)
            self.assertIn("small_wave_height_pitch_rad_rms_linearity", metrics)
            self.assertIn("small_wave_height_bow_vertical_accel_mps2_rms_linearity", metrics)
            self.assertIn("large_wave_response_gain_or_limit_reported", metrics)
            self.assertIn("speed_sweep_total_mass_min_eigenvalue_positive", metrics)
            self.assertIn("speed_sweep_restoring_min_eigenvalue_positive", metrics)
            self.assertIn("speed_sweep_equilibrium_heave_residual_fraction", metrics)
            self.assertIn("speed_sweep_equilibrium_pitch_residual_fraction", metrics)
            self.assertIn("speed_sweep_linear_stability_eigenvalues_finite", metrics)
            self.assertIn("speed_sweep_linear_stability_margin_reported", metrics)
            self.assertIn("speed_sweep_bow_accel_rao_increases_with_speed", metrics)
            self.assertTrue((out_dir / "sanity_spectrum_convergence.csv").exists())
            self.assertTrue((out_dir / "sanity_matrix_equilibrium.csv").exists())
            self.assertTrue((out_dir / "sanity_wave_height_response.csv").exists())
            spectrum = pd.read_csv(out_dir / "sanity_spectrum_convergence.csv")
            matrix = pd.read_csv(out_dir / "sanity_matrix_equilibrium.csv")
            wave_height = pd.read_csv(out_dir / "sanity_wave_height_response.csv")
            self.assertIn("relative_change", spectrum.columns)
            self.assertIn("coarse_component_count", spectrum.columns)
            self.assertIn("refined_component_count", spectrum.columns)
            self.assertEqual({64}, set(spectrum["coarse_component_count"]))
            self.assertEqual({128}, set(spectrum["refined_component_count"]))
            self.assertIn("bow_vertical_accel_mps2_rms", set(spectrum["metric"]))
            self.assertIn("total_mass_min_eigenvalue", matrix.columns)
            self.assertIn("restoring_min_eigenvalue", matrix.columns)
            self.assertIn("equilibrium_heave_residual_weight_fraction", matrix.columns)
            self.assertIn("max_stability_eigenvalue_real", matrix.columns)
            self.assertIn("wave_height_m", wave_height.columns)
            self.assertIn("model_limit_flag", wave_height.columns)
            self.assertIn("limit_reason", wave_height.columns)
            self.assertIn("heave_m_rms_gain_vs_linear_baseline", wave_height.columns)
            self.assertTrue((pd.to_numeric(wave_height["wave_height_m"], errors="coerce") >= 0.1).any())
            self.assertTrue(wave_height["model_limit_flag"].astype(str).str.lower().eq("true").any())
            self.assertTrue((pd.to_numeric(matrix["total_mass_min_eigenvalue"], errors="coerce") > 0.0).all())
            stability_report = summary[summary["metric"].eq("speed_sweep_linear_stability_margin_reported")]
            self.assertEqual(stability_report.iloc[0]["status"], "INFO")
            self.assertTrue(summary["status"].isin(["PASS", "INFO"]).all())

    def test_section_bem_numerical_sanity_writes_convergence_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_section_bem_numerics(out_dir)
            self.assertTrue((out_dir / "section_bem_convergence.csv").exists())
            self.assertTrue((out_dir / "section_bem_body_panel_convergence.csv").exists())
            self.assertTrue((out_dir / "section_bem_excitation_sanity.csv").exists())
            self.assertTrue((out_dir / "section_bem_multimode_radiation_sanity.csv").exists())
            self.assertTrue((out_dir / "section_bem_pressure_transfer_sanity.csv").exists())
            self.assertTrue((out_dir / "forward_speed_pressure_transfer_sanity.csv").exists())
            self.assertTrue((out_dir / "forward_speed_pressure_gradient_sanity.csv").exists())
            self.assertTrue((out_dir / "section_bem_numerical_sanity.csv").exists())
            metrics = set(summary["metric"])
            self.assertIn("section_bem_added_mass_panel_convergence", metrics)
            self.assertIn("section_bem_damping_panel_convergence", metrics)
            self.assertIn("section_bem_body_added_mass_panel_convergence", metrics)
            self.assertIn("section_bem_body_damping_panel_convergence", metrics)
            self.assertIn("section_bem_head_wave_vertical_excitation_nonzero", metrics)
            self.assertIn("section_bem_multimode_heave_matches_scalar_added_mass", metrics)
            self.assertIn("section_bem_multimode_symmetric_sway_heave_coupling", metrics)
            self.assertIn("section_bem_pressure_transfer_radiation_integral_closure", metrics)
            self.assertIn("section_bem_pressure_transfer_wave_integral_closure", metrics)
            self.assertIn("section_bem_pressure_forward_main_operator_closure", metrics)
            self.assertIn("section_bem_pressure_gradient_pdstrip_step_closure", metrics)
            self.assertIn("section_bem_pressure_gradient_raw_clip_difference_finite", metrics)
            self.assertTrue(summary["status"].eq("PASS").all())

    def test_katayama_classification_benchmark_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_katayama_classification(out_dir, ROOT / "benchmarks")
            metrics = set(summary["metric"])
            self.assertIn("katayama_classification_dataset_available", metrics)
            self.assertIn("katayama_classification_accuracy", metrics)
            self.assertTrue((out_dir / "katayama_classification.csv").exists())
            accuracy = summary[summary["metric"].eq("katayama_classification_accuracy")].iloc[0]
            self.assertEqual(accuracy["status"], "PASS")

    def test_katayama_qualitative_trend_gate_reports_model_limitations(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_katayama_qualitative_trends(out_dir)
            metrics = set(summary["metric"])
            self.assertIn("katayama_qualitative_source_statement_recorded", metrics)
            self.assertIn("fn1p21_heave_monotonic_lambda_trend", metrics)
            self.assertIn("fn3p63_heave_wave_height_peak_amplitude_decreases", metrics)
            self.assertIn("fn3p63_pitch_wave_height_peak_shifts_longer", metrics)
            self.assertIn("katayama_nonlinear_pilot_grid_computed", metrics)
            self.assertIn("fn3p63_heave_nonlinear_pilot_medium_wave_peak_shifts_longer", metrics)
            self.assertIn("fn3p63_nonlinear_pilot_large_wave_model_limit_reported", metrics)
            self.assertTrue(summary["status"].eq("FAIL").any())
            self.assertTrue((out_dir / "katayama_qualitative_trends.csv").exists())
            self.assertTrue((out_dir / "katayama_nonlinear_pilot_trends.csv").exists())
            self.assertTrue((out_dir / "figures" / "katayama_qualitative_trends.png").exists())
            self.assertTrue((out_dir / "figures" / "katayama_nonlinear_pilot_trends.png").exists())
            trends = pd.read_csv(out_dir / "katayama_qualitative_trends.csv")
            pilot = pd.read_csv(out_dir / "katayama_nonlinear_pilot_trends.csv")
            self.assertIn("source_statement", trends.columns)
            self.assertIn("response_model", trends.columns)
            self.assertIn("accepted_for_peak_trend", pilot.columns)
            self.assertEqual({"frequency_domain_linear_rao"}, set(trends["response_model"]))
            self.assertEqual({"nonlinear_time_domain_rk4_pilot"}, set(pilot["response_model"]))
            self.assertTrue(pilot["dryout_risk_flag"].astype(bool).any())

    def test_goal_gap_audit_reports_remaining_validation_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            summary = validate_goal_gap_audit(out_dir, ROOT / "benchmarks")
            metrics = set(summary["metric"])
            self.assertIn("fridsma_regular_wave_amplitudes_dataset_schema", metrics)
            self.assertIn("fridsma_config_a_lambda_1_heave_rao_m_per_m", metrics)
            self.assertIn("katayama_regular_wave_amplitudes_dataset_available", metrics)
            self.assertIn("ma2005_wigley_iii_coefficients_dataset_schema", metrics)
            self.assertIn("ma2005_sl7_coefficients_dataset_schema", metrics)
            self.assertIn("ma2005_wigley_iii_coefficients_geometry_audit", metrics)
            self.assertIn("ma2005_sl7_coefficients_geometry_audit", metrics)
            self.assertIn("ma2005_sl7_coefficients_sl7_real_offsets_available", metrics)
            self.assertIn("ma2005_sl7_coefficients_A33_row_0", metrics)
            self.assertIn("station_based_2p5d_solver_available", metrics)
            self.assertIn("experimental_section_bem_api_available", metrics)
            self.assertIn("experimental_multimode_section_radiation_api_available", metrics)
            self.assertIn("section_pressure_transfer_functions_available", metrics)
            self.assertIn("validated_ma2005_pressure_transfer_functions", metrics)
            self.assertIn("external_pdstrip_station_hull_adapter_available", metrics)
            self.assertIn("external_pdstrip_section_6dof_assembly_available", metrics)
            self.assertIn("external_pdstrip_forward_speed_assembly_available", metrics)
            self.assertIn("a1_closed_cylinder_added_mass_inner_pressure_chain", metrics)
            self.assertIn("a1_heave_time_pressure_chain_closed_cylinder", metrics)
            self.assertTrue((out_dir / "goal_gap_audit.csv").exists())
            self.assertTrue((out_dir / "a1_closed_cylinder_added_mass.csv").exists())
            self.assertTrue((out_dir / "a1_closed_cylinder_added_mass_summary.csv").exists())
            self.assertTrue((out_dir / "a1_closed_cylinder_added_mass_metadata.csv").exists())
            self.assertTrue((out_dir / "a1_heave_time_pressure_chain.csv").exists())
            self.assertTrue((out_dir / "a1_heave_time_pressure_chain_summary.csv").exists())
            self.assertTrue((out_dir / "fridsma_regular_wave_amplitudes_comparison.csv").exists())
            self.assertTrue((out_dir / "fridsma_regular_wave_amplitudes_response_model_comparison.csv").exists())
            self.assertTrue((out_dir / "fridsma_regular_wave_amplitudes_response_model_summary.csv").exists())
            self.assertTrue((out_dir / "figures" / "fridsma_regular_wave_amplitudes_response_model_comparison.png").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_comparison.csv").exists())
            self.assertTrue((out_dir / "ma2005_sl7_coefficients_comparison.csv").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_geometry_audit.csv").exists())
            self.assertTrue((out_dir / "ma2005_sl7_coefficients_geometry_audit.csv").exists())
            self.assertTrue(summary["status"].eq("NOT_EVALUATED").any())
            cylinder_summary = pd.read_csv(out_dir / "a1_closed_cylinder_added_mass_summary.csv")
            self.assertEqual(
                cylinder_summary["diagnostic_conclusion"].iloc[0],
                "closed_cylinder_exposes_inner_pressure_sign_reversal",
            )
            cylinder_row = summary[summary["metric"].eq("a1_closed_cylinder_added_mass_inner_pressure_chain")].iloc[0]
            self.assertEqual(cylinder_row["status"], "INFO")
            heave_chain = pd.read_csv(out_dir / "a1_heave_time_pressure_chain.csv")
            heave_chain_summary = pd.read_csv(out_dir / "a1_heave_time_pressure_chain_summary.csv")
            for column in [
                "checked_chain",
                "pressure_formula",
                "reference_added_mass_formula",
                "expected_heave_force_real_per_m",
                "computed_heave_force_real_per_m",
                "pressure_sign_corrected_heave_force_real_per_m",
                "source_system_relative_residual",
                "potential_alignment_scale_to_analytic",
                "raw_pressure_chain_sign_reversal",
                "heave_time_pressure_chain_status",
                "production_policy",
            ]:
                self.assertIn(column, heave_chain.columns)
            self.assertEqual(
                heave_chain_summary["diagnostic_conclusion"].iloc[0],
                "closed_section_inner_chain_magnitude_recovers_analytic_added_mass_after_explicit_sign_correction",
            )
            self.assertTrue(heave_chain["raw_pressure_chain_sign_reversal"].astype(bool).all())
            self.assertTrue(heave_chain["heave_time_pressure_chain_status"].astype(str).eq("PASS").all())
            self.assertLess(
                float(heave_chain_summary["pressure_sign_corrected_relative_error_finest"].iloc[0]),
                0.02,
            )
            heave_chain_row = summary[summary["metric"].eq("a1_heave_time_pressure_chain_closed_cylinder")].iloc[0]
            self.assertEqual(heave_chain_row["status"], "INFO")
            model_comparison = pd.read_csv(out_dir / "fridsma_regular_wave_amplitudes_response_model_comparison.csv")
            self.assertIn("response_model", model_comparison.columns)
            self.assertIn("model_limit_flag", model_comparison.columns)
            self.assertIn("nonlinear_time_domain", set(model_comparison["response_model"]))
            self.assertTrue(model_comparison["model_limit_flag"].astype(bool).any())
            self.assertIn("fridsma_regular_wave_amplitudes_response_model_diagnostics", metrics)

    def test_fridsma_development_dataset_schema_and_conversion(self):
        path = ROOT / "benchmarks" / "fridsma" / "regular_wave_motion_digitized.csv"
        data = pd.read_csv(path)
        required = {
            "case_id",
            "fn_b",
            "wave_height_over_b",
            "lambda_over_l",
            "heave_rao_m_per_m",
            "pitch_rao_rad_per_m",
            "cg_accel_g",
            "bow_accel_g",
            "running_trim_deg",
            "running_lambda_w",
            "source_note",
        }
        self.assertTrue(required.issubset(data.columns))
        self.assertEqual(len(data), 5)
        lambda_2 = data[data["case_id"].eq("fridsma_config_a_lambda_2")].iloc[0]
        expected_pitch_per_m = 0.80 * 2.0 * math.pi / (2.0 * 1.143)
        self.assertAlmostEqual(lambda_2["pitch_rao_rad_per_m"], expected_pitch_per_m, places=10)
        self.assertAlmostEqual(lambda_2["wave_height_over_b"], 0.111, places=12)
        self.assertAlmostEqual(lambda_2["running_trim_deg"], 4.0, places=12)
        self.assertAlmostEqual(lambda_2["running_lambda_w"], 3.6, places=12)

    def test_amplitude_prediction_uses_prescribed_running_state_when_present(self):
        row = pd.Series(
            {
                "case_id": "prescribed_state",
                "fn_b": 2.66,
                "wave_height_over_b": 0.111,
                "lambda_over_l": 2.0,
                "heave_rao_m_per_m": 0.0,
                "pitch_rao_rad_per_m": 0.0,
                "cg_accel_g": 0.0,
                "bow_accel_g": 0.0,
                "length_m": 1.143,
                "beam_m": 0.2286,
                "deadrise_deg": 20.0,
                "mass_over_rho_b3": 0.608,
                "rho_water_kg_m3": 1000.0,
                "lcg_from_transom_m": 0.46863,
                "kg_above_keel_m": 0.0672084,
                "pitch_radius_gyration_m": 0.286893,
                "running_trim_deg": 4.0,
                "running_lambda_w": 3.6,
            }
        )
        prediction = _amplitude_prediction(row)
        self.assertAlmostEqual(prediction["trim_deg"], 4.0, places=12)
        self.assertAlmostEqual(prediction["lambda_w"], 3.6, places=12)
        self.assertEqual(
            prediction["equilibrium_source"],
            "prescribed_running_state(running_trim_deg,running_lambda_w)",
        )

    def test_ma2005_digitized_dataset_is_compared_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "synthetic",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 41,
                }
            )
            expected = _ma2005_computed_coefficient(base)["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(tmp_path / "out", reference_root)
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            self.assertTrue((tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv").exists())
            self.assertTrue((tmp_path / "out" / "ma2005_wigley_iii_coefficients_status_by_coefficient.csv").exists())
            self.assertTrue((tmp_path / "out" / "figures" / "ma2005_wigley_iii_coefficients_comparison.png").exists())

    def test_ma2005_digitized_dataset_can_use_section_bem_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "synthetic",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="section_bem",
                bem_free_surface_panel_count_per_side=3,
                bem_body_panel_count=8,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="section_bem",
                ma_bem_free_surface_panel_count_per_side=3,
                ma_bem_body_panel_count=8,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "section_bem")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "experimental_2d_free_surface_source_panel_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_matched_bie_provider_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="matched_bie_provider",
                bem_free_surface_panel_count_per_side=4,
                bem_body_panel_count=8,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="matched_bie_provider",
                ma_bem_free_surface_panel_count_per_side=4,
                ma_bem_body_panel_count=8,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "matched_bie_provider")
            a1_discretization_requirement = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_discretization_requirement_audit.csv"
            )
            a1_discretization_requirement_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_discretization_requirement_summary.csv"
            )
            a1_history_convolution_requirement = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_history_convolution_requirement_audit.csv"
            )
            a1_history_convolution_requirement_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_history_convolution_requirement_summary.csv"
            )
            station_contributions = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_station_contributions.csv"
            )
            station_transfer_path = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_station_transfer_path.csv"
            )
            station_transfer_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_station_transfer_path_summary.csv"
            )
            aft_pair_boundary_rhs = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_aft_pair_boundary_rhs.csv"
            )
            aft_pair_boundary_rhs_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_aft_pair_boundary_rhs_summary.csv"
            )
            inner_free_surface_rhs_blocks = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_inner_free_surface_rhs_blocks.csv"
            )
            inner_free_surface_rhs_blocks_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_inner_free_surface_rhs_blocks_summary.csv"
            )
            free_self_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_inner_free_surface_self_block_candidate_detail.csv"
            )
            free_self_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_inner_free_surface_self_block_candidate_summary.csv"
            )
            free_block_coupling_candidate_detail = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_inner_free_surface_block_coupling_candidate_detail.csv"
            )
            free_block_coupling_candidate_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_inner_free_surface_block_coupling_candidate_summary.csv"
            )
            startup_ghost_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_startup_ghost_station_candidate_detail.csv"
            )
            startup_ghost_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_startup_ghost_station_candidate_summary.csv"
            )
            end_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_end_contour_term_candidate_detail.csv"
            )
            end_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_end_contour_term_candidate_summary.csv"
            )
            pitch_split_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_detail.csv"
            )
            pitch_split_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_summary.csv"
            )
            free_surface_marching_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_marching_candidate_detail.csv"
            )
            free_surface_marching_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv"
            )
            local_time_free_surface_cross_probe = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_local_time_free_surface_cross_probe.csv"
            )
            local_time_free_surface_cross_probe_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_local_time_free_surface_cross_probe_summary.csv"
            )
            free_surface_update_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_update_formula_candidate_detail.csv"
            )
            free_surface_update_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_update_formula_candidate_summary.csv"
            )
            free_surface_normal_source_candidate_detail = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_free_surface_normal_derivative_source_candidate_detail.csv"
            )
            free_surface_normal_source_candidate_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_free_surface_normal_derivative_source_candidate_summary.csv"
            )
            startup_gradient_candidate_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_detail.csv"
            )
            startup_gradient_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_summary.csv"
            )
            pressure_gradient_stencil_phase_exclusion = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_audit.csv"
            )
            pressure_gradient_stencil_phase_exclusion_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary.csv"
            )
            ab_mapping_normalization_exclusion = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_ab_mapping_normalization_exclusion_audit.csv"
            )
            ab_mapping_normalization_exclusion_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_ab_mapping_normalization_exclusion_summary.csv"
            )
            coefficient_family_scale_exclusion = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_audit.csv"
            )
            coefficient_family_scale_exclusion_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv"
            )
            eq31_eq32_forward_identity = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_audit.csv"
            )
            eq31_eq32_forward_identity_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv"
            )
            complex_forward_identity = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_complex_forward_identity_audit.csv"
            )
            complex_forward_identity_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_complex_forward_identity_summary.csv"
            )
            projection_derivative_balance = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_projection_derivative_balance_audit.csv"
            )
            projection_derivative_balance_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_projection_derivative_balance_summary.csv"
            )
            projection_transport = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_projection_transport_audit.csv"
            )
            projection_transport_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_projection_transport_summary.csv"
            )
            geometry_transport_balance = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_geometry_transport_balance_audit.csv"
            )
            geometry_transport_balance_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv"
            )
            station_geometry_transport_closure = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_geometry_transport_closure_audit.csv"
            )
            station_geometry_transport_closure_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_geometry_transport_closure_summary.csv"
            )
            fixed_control_surface_transport_gap = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_fixed_control_surface_transport_gap_audit.csv"
            )
            fixed_control_surface_transport_gap_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_fixed_control_surface_transport_gap_summary.csv"
            )
            zero_m3_geometry_transport_blocker_trace = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_zero_m3_geometry_transport_blocker_trace.csv"
            )
            zero_m3_geometry_transport_blocker_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_zero_m3_geometry_transport_blocker_summary.csv"
            )
            interior_mi_transport_consistency = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_interior_mi_transport_consistency_audit.csv"
            )
            interior_mi_transport_consistency_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_interior_mi_transport_consistency_summary.csv"
            )
            row_measure_transport = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_row_measure_transport_audit.csv"
            )
            row_measure_transport_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_row_measure_transport_summary.csv"
            )
            row_measure_transport_direction_candidate = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_detail.csv"
            )
            row_measure_transport_direction_candidate_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_summary.csv"
            )
            row_measure_mapping_candidate = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_detail.csv"
            )
            row_measure_mapping_candidate_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_summary.csv"
            )
            row_measure_mapping_candidate_overview = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_overview.csv"
            )
            station_forward_identity = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_forward_identity_audit.csv"
            )
            station_forward_identity_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv"
            )
            startup_gradient_station_detail = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_station_detail.csv"
            )
            startup_gradient_station_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_station_summary.csv"
            )
            end_pressure_closure_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_end_pressure_closure_detail.csv"
            )
            end_pressure_closure_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_end_pressure_closure_summary.csv"
            )
            stokes_end_lever_consistency = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_audit.csv"
            )
            stokes_end_lever_consistency_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary.csv"
            )
            body_potential_source_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_body_potential_source_audit.csv"
            )
            body_potential_source_audit_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_matched_body_potential_source_audit_summary.csv"
            )
            heave_time_pressure_station_scale = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_audit.csv"
            )
            heave_time_pressure_station_scale_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_summary.csv"
            )
            heave_pressure_radiation_check = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_pressure_radiation_check.csv"
            )
            heave_pressure_radiation_check_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_pressure_radiation_check_summary.csv"
            )
            heave_free_normal_to_body_potential = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_audit.csv"
            )
            heave_free_normal_to_body_potential_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_summary.csv"
            )
            pressure_gradient_startup_spike = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_audit.csv"
            )
            pressure_gradient_startup_spike_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_summary.csv"
            )
            eq30_component_contribution = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_component_contribution_audit.csv"
            )
            eq30_component_contribution_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv"
            )
            station_mapping_gradient = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_mapping_gradient_audit.csv"
            )
            station_mapping_gradient_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv"
            )
            station_marching_direction = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_marching_direction_audit.csv"
            )
            station_marching_direction_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_station_marching_direction_summary.csv"
            )
            aft_terminal_end_closure = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_aft_terminal_end_closure_audit.csv"
            )
            aft_terminal_end_closure_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary.csv"
            )
            self.assertGreater(len(a1_discretization_requirement), 0)
            self.assertEqual(len(a1_discretization_requirement_summary), 1)
            for column in [
                "quantity",
                "configured_value",
                "a1_recommended_value",
                "configured_over_recommended_ratio",
                "status",
                "a1_source",
                "diagnostic_consequence",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, a1_discretization_requirement.columns)
            self.assertIn(
                "body_contour_panel_count_n1",
                set(a1_discretization_requirement["quantity"].astype(str)),
            )
            self.assertIn(
                "inner_free_surface_panel_count_n2",
                set(a1_discretization_requirement["quantity"].astype(str)),
            )
            self.assertTrue(
                a1_discretization_requirement["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertGreaterEqual(
                int(a1_discretization_requirement_summary["fail_count"].iloc[0]),
                1,
            )
            self.assertIn(
                "configured_validation_grid_below_a1_wigley_transverse_recommendations",
                set(a1_discretization_requirement_summary["diagnostic_conclusion"].astype(str)),
            )
            self.assertGreater(len(a1_history_convolution_requirement), 0)
            self.assertEqual(len(a1_history_convolution_requirement_summary), 1)
            for column in [
                "quantity",
                "configured_history_steps",
                "recommended_history_steps",
                "configured_over_recommended_ratio",
                "status",
                "a1_source",
                "diagnostic_consequence",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, a1_history_convolution_requirement.columns)
            self.assertIn(
                "outer_control_surface_history_steps",
                set(a1_history_convolution_requirement["quantity"].astype(str)),
            )
            self.assertTrue(
                a1_history_convolution_requirement["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertGreaterEqual(
                int(a1_history_convolution_requirement_summary["fail_count"].iloc[0]),
                1,
            )
            self.assertIn(
                "configured_history_truncates_a1_eq24_convolution",
                set(a1_history_convolution_requirement_summary["diagnostic_conclusion"].astype(str)),
            )
            self.assertGreater(len(station_contributions), 0)
            for column in [
                "x_m",
                "x_over_l",
                "total_density_value_per_m",
                "time_derivative_density_value_per_m",
                "pressure_gradient_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
            ]:
                self.assertIn(column, station_contributions.columns)
                self.assertTrue(pd.to_numeric(station_contributions[column], errors="coerce").notna().any())
            self.assertGreater(len(body_potential_source_audit), 0)
            self.assertEqual(len(body_potential_source_audit_summary), 1)
            for column in [
                "mode_column",
                "generalized_row",
                "x_over_l",
                "waterplane_beam_m",
                "effective_draft_m",
                "submerged_area_m2",
                "body_normal_velocity_norm",
                "body_potential_norm",
                "body_potential_to_body_normal_velocity_gain",
                "body_potential_norm_to_beam_squared_ratio",
                "body_potential_norm_to_submerged_area_ratio",
                "body_pressure_time_derivative_norm",
                "body_pressure_forward_speed_norm",
                "body_pressure_to_body_potential_gain",
                "body_potential_x_gradient_gain_times_l",
                "total_density_value_per_m",
                "time_derivative_density_value_per_m",
                "pressure_gradient_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
                "dominant_force_density_component",
            ]:
                self.assertIn(column, body_potential_source_audit.columns)
                if column not in {"mode_column", "generalized_row", "dominant_force_density_component"}:
                    self.assertTrue(
                        pd.to_numeric(body_potential_source_audit[column], errors="coerce").notna().any()
                    )
            self.assertGreater(len(heave_time_pressure_station_scale), 0)
            self.assertEqual(len(heave_time_pressure_station_scale_summary), 1)
            for column in [
                "coefficient",
                "station_index",
                "x_over_l",
                "body_potential_to_body_normal_velocity_gain",
                "body_potential_norm_to_submerged_area_ratio",
                "free_surface_potential_to_body_potential_ratio",
                "control_potential_to_body_potential_ratio",
                "inner_free_surface_normal_derivative_to_body_normal_velocity_ratio",
                "time_pressure_to_body_potential_gain",
                "time_derivative_density_value_per_m",
                "station_trapezoid_weight_m",
                "station_time_derivative_contribution_value",
                "station_abs_contribution_share",
                "station_integral_time_component_value",
                "station_integral_minus_reported_time_component",
                "required_global_scale_to_reference_from_time_integral",
                "failure_source",
                "gate_role",
            ]:
                self.assertIn(column, heave_time_pressure_station_scale.columns)
                if column not in {"coefficient", "failure_source", "gate_role"}:
                    self.assertTrue(
                        pd.to_numeric(heave_time_pressure_station_scale[column], errors="coerce").notna().any()
                    )
            for column in [
                "coefficient",
                "time_component_value",
                "station_integral_time_component_value",
                "station_integral_closure_residual",
                "peak_abs_station_x_over_l",
                "time_contribution_abs_centroid_x_over_l",
                "max_free_surface_potential_to_body_potential_ratio",
                "max_control_potential_to_body_potential_ratio",
                "max_inner_free_surface_normal_derivative_to_body_normal_velocity_ratio",
                "required_global_scale_to_reference_from_time_integral",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, heave_time_pressure_station_scale_summary.columns)
            self.assertAlmostEqual(
                float(heave_time_pressure_station_scale_summary["station_integral_closure_residual"].iloc[0]),
                0.0,
                places=9,
            )
            self.assertGreater(len(heave_pressure_radiation_check), 0)
            self.assertEqual(len(heave_pressure_radiation_check_summary), 1)
            for column in [
                "coefficient",
                "checked_chain",
                "time_component_value",
                "station_integral_time_component_value",
                "station_integral_closure_residual",
                "station_integral_closure_status",
                "required_global_scale_to_reference_from_time_integral",
                "closed_section_independent_reference_file",
                "open_section_independent_reference_status",
                "acceptance_status",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, heave_pressure_radiation_check.columns)
            self.assertIn(
                "MISSING_OPEN_WIGLEY_SECTION_RADIATION_PRESSURE_REFERENCE",
                set(heave_pressure_radiation_check["open_section_independent_reference_status"].astype(str)),
            )
            self.assertIn("pending_reference_count", heave_pressure_radiation_check_summary.columns)
            self.assertGreater(len(heave_free_normal_to_body_potential), 0)
            self.assertEqual(len(heave_free_normal_to_body_potential_summary), 1)
            for column in [
                "coefficient",
                "station_index",
                "x_over_l",
                "body_normal_velocity_norm",
                "inner_free_surface_normal_derivative_norm",
                "body_potential_norm",
                "inner_free_surface_normal_derivative_to_body_normal_velocity_ratio",
                "body_potential_to_inner_free_surface_normal_derivative_gain",
                "body_potential_to_body_normal_velocity_gain",
                "station_time_derivative_contribution_value",
                "station_abs_contribution_share",
                "diagnostic_flags",
                "failure_source",
                "gate_role",
            ]:
                self.assertIn(column, heave_free_normal_to_body_potential.columns)
                if column not in {"coefficient", "diagnostic_flags", "failure_source", "gate_role"}:
                    self.assertTrue(
                        pd.to_numeric(heave_free_normal_to_body_potential[column], errors="coerce").notna().any()
                    )
            for column in [
                "coefficient",
                "max_inner_free_surface_normal_derivative_to_body_normal_velocity_ratio",
                "median_inner_free_surface_normal_derivative_to_body_normal_velocity_ratio",
                "max_free_normal_ratio_x_over_l",
                "max_body_potential_to_inner_free_surface_normal_derivative_gain",
                "peak_abs_time_contribution_x_over_l",
                "free_normal_peak_matches_time_peak",
                "free_normal_ratio_to_abs_contribution_share_pearson",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, heave_free_normal_to_body_potential_summary.columns)
            self.assertGreater(len(pressure_gradient_startup_spike), 0)
            self.assertEqual(len(pressure_gradient_startup_spike_summary), 1)
            for column in [
                "coefficient",
                "station_index",
                "x_over_l",
                "station_trapezoid_weight_m",
                "pressure_gradient_density_value_per_m",
                "station_pressure_gradient_contribution_value",
                "station_abs_pressure_gradient_contribution_share",
                "body_potential_x_gradient_gain_times_l",
                "reported_pressure_gradient_component_value",
                "station_integral_pressure_gradient_value",
                "station_integral_minus_reported_pressure_gradient_component",
                "without_first_station_gate_error_ratio",
                "without_first_two_stations_gate_error_ratio",
                "diagnostic_flags",
                "failure_source",
                "gate_role",
            ]:
                self.assertIn(column, pressure_gradient_startup_spike.columns)
                if column not in {"coefficient", "diagnostic_flags", "failure_source", "gate_role"}:
                    self.assertTrue(
                        pd.to_numeric(pressure_gradient_startup_spike[column], errors="coerce").notna().any()
                    )
            for column in [
                "coefficient",
                "reported_pressure_gradient_component_value",
                "station_integral_pressure_gradient_value",
                "station_integral_closure_residual",
                "first_station_x_over_l",
                "first_station_abs_contribution_share",
                "first_two_station_abs_contribution_share",
                "peak_abs_station_x_over_l",
                "peak_abs_station_contribution_share",
                "first_station_is_peak_abs_contribution",
                "without_first_station_gate_error_ratio",
                "without_first_two_stations_gate_error_ratio",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, pressure_gradient_startup_spike_summary.columns)
            self.assertAlmostEqual(
                float(pressure_gradient_startup_spike_summary["station_integral_closure_residual"].iloc[0]),
                0.0,
                places=9,
            )
            self.assertEqual(len(eq30_component_contribution), 1)
            self.assertEqual(len(eq30_component_contribution_summary), 1)
            for column in [
                "coefficient",
                "reference_value",
                "computed_value",
                "gate_error_ratio",
                "status",
                "provider_route",
                "time_derivative_pressure_contribution_value",
                "forward_speed_pressure_gradient_contribution_value",
                "stokes_body_forward_speed_contribution_value",
                "end_contour_contribution_value",
                "current_default_reconstructed_value",
                "eq32_stokes_reconstructed_value",
                "current_force_closure_residual_value",
                "dominant_current_default_component",
                "dominant_four_component",
                "required_time_derivative_scale_if_only_adjusted",
                "required_pressure_gradient_scale_if_only_adjusted",
                "required_stokes_body_scale_if_replacing_gradient",
                "required_end_contour_scale_if_only_adjusted",
                "component_failure_source",
                "candidate_policy",
                "remaining_blocker",
            ]:
                self.assertIn(column, eq30_component_contribution.columns)
            for column in [
                "row_count",
                "pass_count",
                "fail_count",
                "max_gate_error_ratio",
                "max_abs_current_force_closure_residual_value",
                "finite_numeric_outputs",
                "dominant_current_default_component_counts",
                "failure_source_counts",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, eq30_component_contribution_summary.columns)
            self.assertEqual(
                eq30_component_contribution["provider_route"].iloc[0],
                "matched_bie_station_sweep",
            )
            self.assertGreaterEqual(len(station_mapping_gradient), 1)
            self.assertEqual(len(station_mapping_gradient_summary), 1)
            for column in [
                "coefficient",
                "coefficient_status",
                "component_failure_source",
                "dominant_current_default_component",
                "peak_pressure_gradient_x_mid_over_l",
                "body_potential_adjacent_relative_jump_at_peak",
                "body_panel_mid_y_adjacent_relative_jump_at_peak",
                "station_waterplane_beam_adjacent_relative_jump_at_peak",
                "body_potential_x_gradient_gain_times_l_pair_max_at_peak",
                "mapping_risk_flags",
                "diagnostic_conclusion",
                "candidate_policy",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, station_mapping_gradient.columns)
            for column in [
                "row_count",
                "forward_gradient_failure_count",
                "high_mapping_risk_count",
                "peak_near_aft_startup_count",
                "max_body_potential_adjacent_relative_jump_at_peak",
                "max_station_waterplane_beam_adjacent_relative_jump_at_peak",
                "max_body_potential_x_gradient_gain_times_l_pair_at_peak",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, station_mapping_gradient_summary.columns)
            self.assertGreaterEqual(len(station_marching_direction), 1)
            self.assertEqual(len(station_marching_direction_summary), 1)
            for column in [
                "coefficient",
                "provider_route",
                "solve_order_first_index",
                "solve_order_last_index",
                "solve_order_first_x_over_l",
                "solve_order_last_x_over_l",
                "solve_order_first_local_time_s",
                "solve_order_last_local_time_s",
                "solve_order_x_over_l_monotonic_decreasing",
                "solve_order_local_time_monotonic_increasing",
                "solve_order_matches_a1_local_time",
                "selected_forward_speed_force_density_peak_x_over_l",
                "transfer_peak_pressure_gradient_x_mid_over_l",
                "pressure_gradient_peak_near_aft_end",
                "pressure_gradient_peak_near_marching_start",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, station_marching_direction.columns)
            for column in [
                "row_count",
                "a1_marching_match_count",
                "a1_marching_mismatch_count",
                "aft_to_bow_storage_count",
                "pressure_gradient_peak_near_aft_end_count",
                "pressure_gradient_peak_near_bow_start_count",
                "pressure_gradient_peak_near_marching_start_count",
                "min_solve_order_first_x_over_l",
                "max_solve_order_first_x_over_l",
                "min_solve_order_last_x_over_l",
                "max_solve_order_last_x_over_l",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, station_marching_direction_summary.columns)
            self.assertTrue(
                station_marching_direction["solve_order_matches_a1_local_time"].astype(str).eq("True").all()
            )
            self.assertGreaterEqual(len(aft_terminal_end_closure), 1)
            self.assertEqual(len(aft_terminal_end_closure_summary), 1)
            for column in [
                "coefficient",
                "provider_route",
                "pressure_gradient_integral_value",
                "stokes_body_forward_integral_value",
                "current_end_contour_integral_value",
                "required_end_contour_integral_to_close_identity_value",
                "required_end_contour_scale_to_close_identity",
                "required_end_contour_scale_abs",
                "current_forward_identity_residual_value",
                "abs_forward_identity_residual_sum",
                "terminal_x_0p10_abs_share",
                "peak_abs_residual_x_over_l",
                "configured_end_station_x_over_l",
                "endpoint_forward_gradient_integral_value",
                "end_to_endpoint_forward_ratio_abs",
                "terminal_band_explains_residual",
                "shared_end_scale_candidate_row_decision",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, aft_terminal_end_closure.columns)
            for column in [
                "row_count",
                "finite_required_end_scale_count",
                "min_abs_required_end_contour_scale",
                "median_abs_required_end_contour_scale",
                "max_abs_required_end_contour_scale",
                "required_end_contour_scale_abs_spread",
                "terminal_x_0p10_high_share_count",
                "terminal_x_0p10_abs_share_min",
                "terminal_x_0p10_abs_share_median",
                "terminal_x_0p10_abs_share_max",
                "end_to_endpoint_forward_ratio_abs_min",
                "end_to_endpoint_forward_ratio_abs_median",
                "end_to_endpoint_forward_ratio_abs_max",
                "row_decision_counts",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, aft_terminal_end_closure_summary.columns)
            self.assertGreater(len(pressure_gradient_stencil_phase_exclusion), 0)
            self.assertGreater(len(pressure_gradient_stencil_phase_exclusion_summary), 0)
            for column in [
                "candidate_name",
                "coefficient",
                "gate_error_ratio",
                "current_default_gate_error_ratio_by_coefficient",
                "gate_ratio_delta_vs_current",
                "forward_gradient_component_value",
                "candidate_gate_status",
                "stencil_phase_row_decision",
                "candidate_default_gate_eligible",
                "candidate_exclusion_reason",
                "gate_role",
            ]:
                self.assertIn(column, pressure_gradient_stencil_phase_exclusion.columns)
            for column in [
                "candidate_name",
                "pass_count",
                "fail_count",
                "improved_row_count",
                "worsened_row_count",
                "breaks_currently_passing_coefficient_count",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "candidate_default_decision",
                "candidate_exclusion_reason",
            ]:
                self.assertIn(column, pressure_gradient_stencil_phase_exclusion_summary.columns)
            self.assertGreater(len(ab_mapping_normalization_exclusion), 0)
            self.assertGreater(len(ab_mapping_normalization_exclusion_summary), 0)
            for column in [
                "candidate_name",
                "candidate_class",
                "coefficient",
                "reference_value",
                "candidate_value",
                "raw_computed_value",
                "documented_normalization_scale",
                "required_normalization_scale",
                "required_scale_over_documented",
                "candidate_gate_error_ratio",
                "current_gate_error_ratio",
                "candidate_gate_status",
                "candidate_row_decision",
                "candidate_default_gate_eligible",
                "candidate_exclusion_reason",
                "gate_role",
            ]:
                self.assertIn(column, ab_mapping_normalization_exclusion.columns)
            for column in [
                "candidate_name",
                "candidate_class",
                "pass_count",
                "fail_count",
                "improved_row_count",
                "worsened_row_count",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "median_required_scale_over_documented",
                "required_scale_over_documented_spread",
                "candidate_default_decision",
                "candidate_exclusion_reason",
            ]:
                self.assertIn(column, ab_mapping_normalization_exclusion_summary.columns)
            self.assertIn(
                "per_coefficient_required_scale",
                set(ab_mapping_normalization_exclusion_summary["candidate_name"].astype(str)),
            )
            self.assertGreater(len(coefficient_family_scale_exclusion), 0)
            self.assertGreater(len(coefficient_family_scale_exclusion_summary), 0)
            for column in [
                "candidate_name",
                "candidate_class",
                "candidate_group_key",
                "candidate_group_size",
                "candidate_group_scale",
                "coefficient",
                "prefix",
                "row_family",
                "column_family",
                "matrix_cell",
                "diagonal_kind",
                "reference_value",
                "current_computed_value",
                "candidate_value",
                "required_scale_to_reference",
                "required_scale_over_candidate_group_scale",
                "candidate_gate_error_ratio",
                "current_gate_error_ratio",
                "candidate_gate_status",
                "candidate_row_decision",
                "candidate_default_gate_eligible",
                "candidate_exclusion_reason",
                "gate_role",
            ]:
                self.assertIn(column, coefficient_family_scale_exclusion.columns)
            for column in [
                "candidate_name",
                "candidate_class",
                "group_count",
                "pass_count",
                "fail_count",
                "improved_row_count",
                "worsened_row_count",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "median_candidate_group_scale",
                "candidate_group_scale_abs_spread",
                "median_required_scale_over_candidate_group_scale",
                "required_scale_over_candidate_group_scale_spread",
                "candidate_default_decision",
                "candidate_exclusion_reason",
            ]:
                self.assertIn(column, coefficient_family_scale_exclusion_summary.columns)
            self.assertIn(
                "matrix_cell_shared_ab_scale",
                set(coefficient_family_scale_exclusion_summary["candidate_name"].astype(str)),
            )
            self.assertGreater(len(eq31_eq32_forward_identity), 0)
            self.assertGreater(len(eq31_eq32_forward_identity_summary), 0)
            for column in [
                "candidate_name",
                "candidate_class",
                "coefficient",
                "reference_value",
                "candidate_reference_value",
                "current_computed_value",
                "candidate_value",
                "time_derivative_component_value",
                "forward_speed_pressure_gradient_component_value",
                "stokes_body_forward_speed_component_value",
                "end_contour_component_value",
                "eq31_direct_time_plus_gradient_value",
                "eq32_stokes_time_plus_body_plus_end_value",
                "current_hybrid_time_plus_gradient_plus_end_value",
                "forward_identity_residual_value",
                "forward_identity_residual_over_effective_tolerance",
                "current_minus_eq31_direct_value",
                "current_minus_eq32_stokes_value",
                "candidate_gate_error_ratio",
                "candidate_gate_status",
                "candidate_row_decision",
                "candidate_default_gate_eligible",
                "candidate_exclusion_reason",
                "gate_role",
            ]:
                self.assertIn(column, eq31_eq32_forward_identity.columns)
            for column in [
                "candidate_name",
                "candidate_class",
                "pass_count",
                "fail_count",
                "improved_row_count",
                "worsened_row_count",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "median_forward_identity_residual_over_effective_tolerance",
                "max_forward_identity_residual_over_effective_tolerance",
                "median_abs_current_minus_eq31_direct_value",
                "median_abs_current_minus_eq32_stokes_value",
                "candidate_default_decision",
                "candidate_exclusion_reason",
            ]:
                self.assertIn(column, eq31_eq32_forward_identity_summary.columns)
            self.assertIn(
                "eq32_stokes_time_plus_body_plus_end",
                set(eq31_eq32_forward_identity_summary["candidate_name"].astype(str)),
            )
            self.assertIn(
                "forward_identity_gradient_minus_body_end",
                set(eq31_eq32_forward_identity_summary["candidate_name"].astype(str)),
            )
            self.assertGreater(len(complex_forward_identity), 0)
            self.assertEqual(len(complex_forward_identity_summary), 1)
            for column in [
                "matrix_cell",
                "pair_status",
                "a_omega_e_sqrt_l_over_g",
                "b_omega_e_sqrt_l_over_g",
                "omega_bar_delta",
                "omega_rad_s",
                "complex_identity_residual_norm",
                "pressure_gradient_to_stokes_plus_end_abs_ratio",
                "pressure_gradient_to_stokes_plus_end_phase_deg",
                "required_complex_scale_abs",
                "required_complex_scale_phase_deg",
                "best_sign_candidate",
                "best_sign_residual_norm",
                "identity_status",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, complex_forward_identity.columns)
            for column in [
                "detail_row_count",
                "matrix_cell_count",
                "pairable_ab_complex_count",
                "unpairable_frequency_or_missing_count",
                "identity_pass_count",
                "identity_fail_count",
                "paired_cells",
                "unpaired_cells",
                "median_complex_identity_residual_norm",
                "max_complex_identity_residual_norm",
                "max_current_force_closure_residual_norm",
                "best_sign_candidate_counts",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, complex_forward_identity_summary.columns)
            self.assertGreaterEqual(int(complex_forward_identity_summary["matrix_cell_count"].iloc[0]), 1)
            self.assertIn(
                complex_forward_identity["pair_status"].astype(str).iloc[0],
                {
                    "paired_same_frequency_ab_complex_reconstruction",
                    "missing_a_or_b_component",
                    "missing_matching_hull_speed_pair",
                    "frequency_mismatch_unpaired",
                },
            )
            self.assertGreater(len(projection_derivative_balance), 0)
            self.assertEqual(len(projection_derivative_balance_summary), 1)
            for column in [
                "coefficient",
                "matrix_cell",
                "ab_frequency_pair_status",
                "pressure_gradient_integral_value",
                "projection_derivative_proxy_integral_value",
                "stokes_body_forward_integral_value",
                "end_contour_integral_value",
                "stokes_plus_end_integral_value",
                "gradient_minus_projection_derivative_value",
                "gradient_minus_stokes_plus_end_value",
                "projection_derivative_minus_stokes_plus_end_value",
                "gradient_projection_derivative_residual_norm",
                "gradient_stokes_end_residual_norm",
                "projection_derivative_stokes_end_residual_norm",
                "projection_derivative_pair_role",
                "candidate_default_gate_eligible",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, projection_derivative_balance.columns)
            for column in [
                "row_count",
                "finite_row_count",
                "same_frequency_pair_count",
                "frequency_mismatch_or_missing_count",
                "gradient_projection_derivative_pass_count",
                "gradient_stokes_end_pass_count",
                "projection_derivative_stokes_end_pass_count",
                "max_gradient_projection_derivative_residual_norm",
                "max_gradient_stokes_end_residual_norm",
                "max_projection_derivative_stokes_end_residual_norm",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, projection_derivative_balance_summary.columns)
            self.assertGreater(len(projection_transport_summary), 0)
            for column in [
                "coefficient",
                "matrix_cell",
                "pair_status",
                "direct_pressure_gradient_density_value_per_m",
                "projection_transport_derivative_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
                "direct_minus_transport_density_value_per_m",
                "transport_minus_stokes_density_value_per_m",
                "direct_pressure_gradient_station_contribution_value",
                "projection_transport_station_contribution_value",
                "direct_minus_transport_station_contribution_value",
                "candidate_default_gate_eligible",
                "candidate_exclusion_reason",
                "gate_role",
            ]:
                self.assertIn(column, projection_transport.columns)
            for column in [
                "coefficient",
                "matrix_cell",
                "ab_frequency_pair_status",
                "direct_pressure_gradient_integral_value",
                "projection_transport_integral_value",
                "projection_endpoint_jump_value",
                "stokes_body_forward_integral_value",
                "end_contour_integral_value",
                "stokes_plus_end_integral_value",
                "direct_minus_transport_integral_value",
                "transport_minus_endpoint_jump_value",
                "direct_minus_stokes_end_integral_value",
                "transport_minus_stokes_end_integral_value",
                "direct_transport_residual_norm",
                "transport_endpoint_jump_residual_norm",
                "direct_stokes_end_residual_norm",
                "transport_stokes_end_residual_norm",
                "diagnostic_conclusion",
                "remaining_blocker",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, projection_transport_summary.columns)
            self.assertTrue(
                projection_transport_summary["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertGreater(len(geometry_transport_balance_summary), 0)
            for column in [
                "coefficient",
                "matrix_cell",
                "ab_frequency_pair_status",
                "direct_pressure_gradient_integral_value",
                "projection_transport_integral_value",
                "stokes_plus_end_integral_value",
                "inferred_geometry_transport_value",
                "required_geometry_transport_to_close_stokes_end_value",
                "geometry_transport_balance_residual_value",
                "geometry_transport_balance_residual_norm",
                "inferred_to_required_geometry_transport_ratio",
                "inferred_required_same_sign",
                "diagnostic_conclusion",
                "remaining_blocker",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, geometry_transport_balance.columns)
            for column in [
                "row_count",
                "finite_row_count",
                "same_frequency_pair_count",
                "geometry_transport_balance_pass_count",
                "geometry_transport_balance_fail_count",
                "opposite_sign_count",
                "wrong_magnitude_count",
                "median_geometry_transport_balance_residual_norm",
                "max_geometry_transport_balance_residual_norm",
                "max_abs_inferred_geometry_transport_value",
                "max_abs_required_geometry_transport_value",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, geometry_transport_balance_summary.columns)
            self.assertTrue(
                geometry_transport_balance_summary["path_diagnostic_status"].astype(str).eq("INFO").all()
            )
            for column in [
                "coefficient",
                "matrix_cell",
                "pair_status",
                "station_index",
                "x_over_l",
                "is_configured_end_station",
                "direct_pressure_gradient_station_contribution_value",
                "projection_transport_station_contribution_value",
                "stokes_body_forward_station_contribution_value",
                "end_contour_station_contribution_value",
                "inferred_geometry_transport_station_contribution_value",
                "required_geometry_transport_station_contribution_value",
                "station_geometry_transport_residual_value",
                "station_abs_residual_share_of_total_abs",
                "diagnostic_flags",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, station_geometry_transport_closure.columns)
            for column in [
                "coefficient",
                "geometry_transport_integral_residual_norm",
                "abs_station_geometry_transport_residual_sum",
                "peak_abs_residual_station_index",
                "peak_abs_residual_x_over_l",
                "configured_end_abs_residual_share",
                "residual_abs_centroid_x_over_l",
                "station_integral_closure_residual",
                "diagnostic_conclusion",
                "remaining_blocker",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, station_geometry_transport_closure_summary.columns)
            if not station_geometry_transport_closure.empty:
                self.assertTrue(
                    station_geometry_transport_closure["candidate_default_gate_eligible"]
                    .astype(str)
                    .str.lower()
                    .eq("false")
                    .all()
                )
            if not station_geometry_transport_closure_summary.empty:
                self.assertTrue(
                    station_geometry_transport_closure_summary["path_diagnostic_status"].astype(str).eq("INFO").all()
                )
                self.assertLess(
                    float(
                        pd.to_numeric(
                            station_geometry_transport_closure_summary["station_integral_closure_residual"],
                            errors="coerce",
                        )
                        .abs()
                        .max()
                    ),
                    1e-9,
                )
            for column in [
                "coefficient",
                "product_rule_closure_residual_norm",
                "eq31_eq32_proxy_residual_norm",
                "interior_distributed_abs_share",
                "normal_variation_abs_share",
                "boundary_proxy_abs_share",
                "a1_trace",
                "diagnostic_conclusion",
                "blocker_status",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, fixed_control_surface_transport_gap.columns)
            for column in [
                "row_count",
                "open_blocker_count",
                "max_eq31_eq32_proxy_residual_norm",
                "median_interior_distributed_abs_share",
                "median_boundary_proxy_abs_share",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, fixed_control_surface_transport_gap_summary.columns)
            if not fixed_control_surface_transport_gap_summary.empty:
                self.assertTrue(
                    fixed_control_surface_transport_gap_summary["path_diagnostic_status"].astype(str).eq("INFO").all()
                )
            self.assertGreater(len(zero_m3_geometry_transport_blocker_trace), 0)
            self.assertEqual(len(zero_m3_geometry_transport_blocker_summary), 1)
            for column in [
                "trace_item",
                "target_coefficients",
                "evidence_source",
                "supports_default_geometry_transport_change",
                "blocks_default_geometry_transport_change",
                "diagnostic_status",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, zero_m3_geometry_transport_blocker_trace.columns)
            for column in [
                "current_target_fail_count",
                "trace_item_count",
                "blocking_trace_count",
                "supporting_default_geometry_transport_change_count",
                "product_rule_closure_residual_max",
                "eq31_eq32_proxy_residual_norm_max",
                "median_interior_distributed_abs_share",
                "median_normal_variation_abs_share",
                "best_force_route",
                "best_direction_candidate",
                "end_contour_mixed_interaction_count",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, zero_m3_geometry_transport_blocker_summary.columns)
            self.assertFalse(
                zero_m3_geometry_transport_blocker_trace[
                    "supports_default_geometry_transport_change"
                ].astype(bool).any()
            )
            self.assertFalse(
                zero_m3_geometry_transport_blocker_trace["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                zero_m3_geometry_transport_blocker_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            for column in [
                "coefficient",
                "matrix_cell",
                "station_index",
                "x_over_l",
                "projection_transport_station_contribution_value",
                "stokes_body_forward_station_contribution_value",
                "transport_minus_stokes_mi_station_contribution_value",
                "transport_to_stokes_mi_ratio",
                "transport_stokes_same_sign",
                "diagnostic_flags",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, interior_mi_transport_consistency.columns)
            for column in [
                "coefficient",
                "projection_transport_interior_integral_value",
                "stokes_body_forward_interior_integral_value",
                "transport_minus_stokes_interior_integral_value",
                "transport_stokes_interior_residual_norm",
                "least_squares_transport_over_stokes_scale",
                "least_squares_scaled_residual_norm",
                "transport_stokes_opposite_sign_fraction",
                "transport_stokes_same_sign_fraction",
                "residual_abs_centroid_x_over_l",
                "diagnostic_conclusion",
                "remaining_blocker",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, interior_mi_transport_consistency_summary.columns)
            if not interior_mi_transport_consistency.empty:
                self.assertTrue(
                    interior_mi_transport_consistency["candidate_default_gate_eligible"]
                    .astype(str)
                    .str.lower()
                    .eq("false")
                    .all()
                )
            if not interior_mi_transport_consistency_summary.empty:
                self.assertTrue(
                    interior_mi_transport_consistency_summary["path_diagnostic_status"].astype(str).eq("INFO").all()
                )
            for column in [
                "coefficient",
                "row_family",
                "column_family",
                "station_index",
                "x_over_l",
                "row_measure_norm",
                "row_measure_x_gradient_norm",
                "stokes_m_measure_norm",
                "row_measure_gradient_to_stokes_m_norm_ratio",
                "row_measure_gradient_stokes_m_alignment",
                "row_measure_transport_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
                "transport_minus_stokes_density_value_per_m",
                "transport_plus_stokes_density_value_per_m",
                "transport_to_stokes_density_ratio",
                "transport_to_negative_stokes_density_ratio",
                "diagnostic_flags",
                "candidate_policy",
                "gate_role",
            ]:
                self.assertIn(column, row_measure_transport.columns)
            for column in [
                "coefficient",
                "row_family",
                "column_family",
                "row_measure_transport_integral_value",
                "stokes_body_forward_integral_value",
                "transport_minus_stokes_integral_value",
                "transport_plus_stokes_integral_value",
                "transport_stokes_residual_norm",
                "transport_negative_stokes_residual_norm",
                "least_squares_transport_over_stokes_scale",
                "least_squares_transport_over_negative_stokes_scale",
                "least_squares_scaled_residual_norm",
                "transport_stokes_opposite_sign_fraction",
                "transport_stokes_same_sign_fraction",
                "abs_station_transport_negative_stokes_residual_sum",
                "residual_abs_centroid_x_over_l",
                "median_row_gradient_to_stokes_m_norm_ratio",
                "median_row_gradient_stokes_m_alignment",
                "diagnostic_conclusion",
                "remaining_blocker",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, row_measure_transport_summary.columns)
            if not row_measure_transport.empty:
                self.assertTrue(
                    row_measure_transport["candidate_policy"]
                    .astype(str)
                    .str.contains("diagnostic-only", regex=False)
                    .all()
                )
            if not row_measure_transport_summary.empty:
                self.assertTrue(
                    row_measure_transport_summary["path_diagnostic_status"].astype(str).eq("INFO").all()
                )
            self.assertGreater(len(row_measure_transport_direction_candidate), 0)
            self.assertEqual(
                set(row_measure_transport_direction_candidate_summary["candidate_name"].astype(str)),
                {"current_equal_panel_x_derivative", "reversed_x_derivative"},
            )
            for column in [
                "candidate_name",
                "candidate_x_derivative_sign",
                "coefficient",
                "row_family",
                "column_family",
                "candidate_transport_integral_value",
                "negative_stokes_target_integral_value",
                "candidate_negative_stokes_residual_norm",
                "least_squares_candidate_over_negative_stokes_scale",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, row_measure_transport_direction_candidate.columns)
            for column in [
                "candidate_name",
                "row_count",
                "closed_row_count",
                "sign_reversed_row_count",
                "zero_mi_nonzero_candidate_row_count",
                "median_candidate_negative_stokes_residual_norm",
                "max_candidate_negative_stokes_residual_norm",
                "median_candidate_over_negative_stokes_scale",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
                "path_diagnostic_status",
            ]:
                self.assertIn(column, row_measure_transport_direction_candidate_summary.columns)
            self.assertTrue(
                row_measure_transport_direction_candidate["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertTrue(
                row_measure_transport_direction_candidate_summary["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertTrue(
                row_measure_transport_direction_candidate_summary["path_diagnostic_status"]
                .astype(str)
                .eq("INFO")
                .all()
            )
            self.assertGreater(len(row_measure_mapping_candidate), 0)
            self.assertGreater(len(row_measure_mapping_candidate_summary), 0)
            self.assertEqual(
                set(row_measure_mapping_candidate_overview["candidate_name"].astype(str)),
                {
                    "current_equal_panel_x_derivative",
                    "heave_projection_leibniz_endpoint_flux_pitch_current",
                    "mapped_fixed_y_central",
                    "mapped_normalized_y_central",
                    "mapped_normalized_arclength_central",
                },
            )
            for column in [
                "candidate_name",
                "coefficient",
                "row_family",
                "column_family",
                "station_index",
                "x_over_l",
                "candidate_row_measure_x_gradient_norm",
                "candidate_transport_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
                "candidate_to_negative_stokes_density_ratio",
                "candidate_default_gate_eligible",
                "gate_role",
            ]:
                self.assertIn(column, row_measure_mapping_candidate.columns)
            for column in [
                "candidate_name",
                "coefficient",
                "candidate_transport_integral_value",
                "negative_stokes_target_integral_value",
                "candidate_negative_stokes_residual_norm",
                "least_squares_candidate_over_negative_stokes_scale",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
                "path_diagnostic_status",
            ]:
                self.assertIn(column, row_measure_mapping_candidate_summary.columns)
            for column in [
                "candidate_name",
                "row_count",
                "closed_row_count",
                "median_candidate_negative_stokes_residual_norm",
                "median_candidate_over_negative_stokes_scale",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
                "path_diagnostic_status",
            ]:
                self.assertIn(column, row_measure_mapping_candidate_overview.columns)
            self.assertTrue(
                row_measure_mapping_candidate["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertTrue(
                row_measure_mapping_candidate_overview["path_diagnostic_status"].astype(str).eq("INFO").all()
            )
            self.assertGreater(len(stokes_end_lever_consistency), 0)
            self.assertEqual(len(stokes_end_lever_consistency_summary), 1)
            for column in [
                "coefficient",
                "row_family",
                "column_family",
                "provider_route",
                "pressure_gradient_component_value",
                "stokes_body_forward_component_value",
                "end_contour_component_value",
                "stokes_plus_end_value",
                "forward_identity_residual_value",
                "forward_identity_residual_over_effective_tolerance",
                "forward_identity_status",
                "stokes_mi_expected_zero",
                "stokes_zero_status",
                "endpoint_forward_gradient_integral_value",
                "endpoint_stokes_body_forward_integral_value",
                "end_to_endpoint_forward_ratio_abs",
                "end_lever_minus_station_moment_lever_m",
                "end_lever_consistency_status",
                "diagnostic_flags",
                "diagnostic_conclusion",
                "remaining_blocker",
                "gate_role",
            ]:
                self.assertIn(column, stokes_end_lever_consistency.columns)
                if column not in {
                    "coefficient",
                    "row_family",
                    "column_family",
                    "provider_route",
                    "forward_identity_status",
                    "stokes_mi_expected_zero",
                    "stokes_zero_status",
                    "end_to_endpoint_forward_ratio_abs",
                    "end_lever_consistency_status",
                    "diagnostic_flags",
                    "diagnostic_conclusion",
                    "remaining_blocker",
                    "gate_role",
                }:
                    self.assertTrue(
                        pd.to_numeric(stokes_end_lever_consistency[column], errors="coerce").notna().any()
                    )
            for column in [
                "row_count",
                "identity_pass_count",
                "identity_fail_count",
                "heave_row_count",
                "heave_row_stokes_zero_pass_count",
                "end_lever_consistency_pass_count",
                "max_abs_forward_identity_residual_value",
                "max_forward_identity_residual_over_effective_tolerance",
                "max_abs_end_lever_delta_m",
                "endpoint_ratio_finite_count",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, stokes_end_lever_consistency_summary.columns)
            self.assertGreater(len(station_forward_identity), 0)
            self.assertGreater(len(station_forward_identity_summary), 0)
            for column in [
                "coefficient",
                "station_index",
                "x_over_l",
                "trapz_weight_m",
                "is_configured_end_station",
                "pressure_gradient_density_value_per_m",
                "stokes_body_forward_density_value_per_m",
                "endpoint_end_equivalent_density_value_per_m",
                "pressure_gradient_station_contribution_value",
                "stokes_body_forward_station_contribution_value",
                "end_contour_station_contribution_value",
                "station_forward_identity_residual_value",
                "station_abs_residual_share_of_total_abs",
                "station_residual_to_pressure_gradient_abs_ratio",
                "station_residual_to_stokes_plus_end_abs_ratio",
                "diagnostic_flags",
                "failure_source",
                "gate_role",
            ]:
                self.assertIn(column, station_forward_identity.columns)
                if column not in {
                    "coefficient",
                    "is_configured_end_station",
                    "diagnostic_flags",
                    "failure_source",
                    "gate_role",
                }:
                    self.assertTrue(pd.to_numeric(station_forward_identity[column], errors="coerce").notna().any())
            for column in [
                "coefficient",
                "pressure_gradient_integral_value",
                "stokes_body_forward_integral_value",
                "end_contour_integral_value",
                "reported_forward_identity_residual_value",
                "station_integral_forward_identity_residual_value",
                "station_integral_closure_residual",
                "abs_forward_identity_residual_sum",
                "peak_abs_residual_station_index",
                "peak_abs_residual_x_over_l",
                "peak_abs_residual_share",
                "first_station_abs_residual_share",
                "configured_end_abs_residual_share",
                "residual_abs_centroid_x_over_l",
                "diagnostic_conclusion",
                "remaining_blocker",
            ]:
                self.assertIn(column, station_forward_identity_summary.columns)
            self.assertLess(
                float(pd.to_numeric(station_forward_identity_summary["station_integral_closure_residual"]).abs().max()),
                1e-9,
            )
            for column in [
                "coefficient",
                "mode_column",
                "generalized_row",
                "peak_body_potential_x_over_l",
                "peak_body_potential_norm",
                "peak_time_derivative_density_abs_per_m",
                "peak_pressure_gradient_density_abs_per_m",
                "max_body_potential_to_body_normal_velocity_gain",
                "max_body_potential_norm_to_submerged_area_ratio",
                "max_body_potential_x_gradient_gain_times_l",
                "dominant_force_density_component",
            ]:
                self.assertIn(column, body_potential_source_audit_summary.columns)
                if column not in {"coefficient", "mode_column", "generalized_row", "dominant_force_density_component"}:
                    self.assertTrue(
                        math.isfinite(float(body_potential_source_audit_summary[column].iloc[0]))
                    )
            self.assertGreater(len(station_transfer_path), 0)
            self.assertEqual(len(station_transfer_summary), 1)
            for column in [
                "x_mid_over_l",
                "free_surface_potential_norm_left",
                "body_potential_norm_left",
                "body_to_free_surface_potential_gain_left",
                "body_potential_adjacent_relative_jump",
                "body_potential_adjacent_phase_deg",
                "body_potential_x_gradient_gain_times_l_pair_max",
                "phase_aligned_gradient_gain_to_raw_gain_ratio_pair_max",
                "pressure_gradient_density_abs_pair_max",
                "pressure_gradient_density_pair_cancellation_index",
            ]:
                self.assertIn(column, station_transfer_path.columns)
                self.assertTrue(pd.to_numeric(station_transfer_path[column], errors="coerce").notna().any())
            for column in [
                "peak_pressure_gradient_x_mid_over_l",
                "peak_pressure_gradient_density_abs_pair_max",
                "max_body_potential_x_gradient_gain_times_l_pair",
                "max_body_potential_adjacent_relative_jump",
                "pressure_gradient_density_sign_change_pairs",
            ]:
                self.assertIn(column, station_transfer_summary.columns)
                self.assertTrue(math.isfinite(float(station_transfer_summary[column].iloc[0])))
            self.assertEqual(len(aft_pair_boundary_rhs), 2)
            self.assertEqual(len(aft_pair_boundary_rhs_summary), 1)
            for column in [
                "x_over_l",
                "body_phi_solution_norm",
                "body_phi_n_known_norm",
                "control_phi_solution_norm",
                "control_phi_n_solution_norm",
                "matched_rhs_total_norm",
                "matched_rhs_body_normal_velocity_norm",
                "matched_rhs_inner_free_surface_potential_norm",
                "matched_rhs_outer_control_history_norm",
                "matched_rhs_source_sum_relative_residual",
                "body_pressure_forward_speed_norm",
                "pressure_gradient_density_value_per_m",
            ]:
                self.assertIn(column, aft_pair_boundary_rhs.columns)
                self.assertTrue(pd.to_numeric(aft_pair_boundary_rhs[column], errors="coerce").notna().any())
            for column in [
                "peak_pressure_gradient_station_local_index",
                "peak_pressure_gradient_x_over_l",
                "peak_pressure_gradient_density_abs",
                "max_rhs_body_normal_velocity_to_total_ratio",
                "max_rhs_source_sum_relative_residual",
            ]:
                self.assertIn(column, aft_pair_boundary_rhs_summary.columns)
                self.assertTrue(math.isfinite(float(aft_pair_boundary_rhs_summary[column].iloc[0])))
            self.assertGreater(len(inner_free_surface_rhs_blocks), 0)
            self.assertEqual(len(inner_free_surface_rhs_blocks_summary), 1)
            for column in [
                "x_over_l",
                "row_block_name",
                "free_surface_panel_index",
                "free_surface_panel_y_m",
                "free_surface_potential_abs",
                "matrix_column_norm",
                "row_block_contribution_norm",
                "row_block_free_rhs_norm",
                "total_free_rhs_norm",
                "row_block_to_total_free_rhs_norm_ratio",
                "panel_to_row_block_free_rhs_norm_ratio",
                "panel_to_total_free_rhs_norm_ratio",
            ]:
                self.assertIn(column, inner_free_surface_rhs_blocks.columns)
            for column in [
                "dominant_station_local_index",
                "dominant_x_over_l",
                "dominant_free_surface_panel_index",
                "dominant_free_surface_panel_y_m",
                "dominant_row_block_contribution_norm",
                "dominant_panel_to_total_free_rhs_norm_ratio",
                "max_row_block_to_total_free_rhs_norm_ratio",
            ]:
                self.assertIn(column, inner_free_surface_rhs_blocks_summary.columns)
                self.assertTrue(math.isfinite(float(inner_free_surface_rhs_blocks_summary[column].iloc[0])))
            self.assertEqual(
                set(free_self_candidate_detail["candidate_name"]),
                {
                    "current_default",
                    "free_self_diagonal_removed",
                    "free_self_diagonal_opposite_sign",
                    "inner_a_normalized_by_2pi",
                },
            )
            self.assertEqual(len(free_self_candidate_detail), 4)
            self.assertEqual(len(free_self_candidate_summary), 4)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "inner_a_scale",
                "inner_diagonal_sign",
                "inner_free_surface_self_diagonal_scale",
            ]:
                self.assertIn(column, free_self_candidate_detail.columns)
                self.assertTrue(pd.to_numeric(free_self_candidate_detail[column], errors="coerce").notna().any())
            for column in [
                "candidate_name",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_self_candidate_summary.columns)
            self.assertEqual(
                set(free_block_coupling_candidate_detail["candidate_name"]),
                {
                    "current_default",
                    "known_phi_free_rhs_removed",
                    "known_phi_free_rhs_flipped",
                    "unknown_phi_n_free_column_removed",
                    "unknown_phi_n_free_column_flipped",
                    "both_free_blocks_removed",
                    "known_phi_free_rhs_one_over_2pi",
                    "unknown_phi_n_free_column_one_over_2pi",
                    "both_free_blocks_one_over_2pi",
                    "known_phi_free_rhs_2pi",
                    "unknown_phi_n_free_column_2pi",
                    "both_free_blocks_2pi",
                },
            )
            self.assertEqual(len(free_block_coupling_candidate_detail), 12)
            self.assertEqual(len(free_block_coupling_candidate_summary), 12)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "known_potential_rhs_scale",
                "unknown_normal_column_scale",
                "matched_heave_free_surface_potential_norm_max",
                "matched_heave_inner_free_surface_normal_derivative_norm_max",
                "matched_selected_body_pressure_to_body_potential_gain_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_block_coupling_candidate_detail.columns)
                if column != "candidate_gate_status":
                    self.assertTrue(
                        pd.to_numeric(
                            free_block_coupling_candidate_detail[column],
                            errors="coerce",
                        ).notna().any()
                    )
            for column in [
                "candidate_name",
                "known_potential_rhs_scale",
                "unknown_normal_column_scale",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_heave_free_surface_potential_norm_max",
                "median_heave_inner_free_surface_normal_derivative_norm_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_block_coupling_candidate_summary.columns)
            self.assertEqual(
                set(startup_ghost_candidate_detail["candidate_name"]),
                {
                    "current_default",
                    "ghost_aft_pressure_plus_end",
                    "ghost_aft_pressure_no_end",
                    "ghost_aft_forward_only_removed_keep_time_end",
                    "ghost_aft_time_only_removed_keep_forward_end",
                    "bow_pressure_excluded_plus_end",
                    "both_end_pressure_excluded_plus_end",
                },
            )
            self.assertEqual(len(startup_ghost_candidate_detail), 7)
            self.assertEqual(len(startup_ghost_candidate_summary), 7)
            for column in [
                "computed_value",
                "raw_computed_value",
                "raw_to_reference_raw_ratio",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "candidate_gate_status",
            ]:
                self.assertIn(column, startup_ghost_candidate_detail.columns)
                if column not in {"candidate_gate_status", "raw_to_reference_raw_ratio"}:
                    self.assertTrue(
                        pd.to_numeric(startup_ghost_candidate_detail[column], errors="coerce").notna().any()
                    )
            for column in [
                "candidate_name",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "candidate_gate_status",
            ]:
                self.assertIn(column, startup_ghost_candidate_summary.columns)
            self.assertEqual(
                set(end_candidate_detail["candidate_name"]),
                {
                    "current_default",
                    "end_removed",
                    "end_flipped",
                    "end_half_scale",
                    "end_double_scale",
                },
            )
            self.assertEqual(len(end_candidate_detail), 5)
            self.assertEqual(len(end_candidate_summary), 5)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "end_term_scale",
                "base_time_plus_pressure_gradient_value",
                "end_term_component_value",
                "candidate_end_contribution_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, end_candidate_detail.columns)
                if column != "candidate_gate_status":
                    self.assertTrue(pd.to_numeric(end_candidate_detail[column], errors="coerce").notna().any())
            for column in [
                "candidate_name",
                "end_term_scale",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "candidate_gate_status",
            ]:
                self.assertIn(column, end_candidate_summary.columns)
            self.assertEqual(
                set(pitch_split_candidate_detail["candidate_name"]),
                {
                    "current_combined",
                    "pitch_oscillation_only",
                    "pitch_forward_only",
                    "pitch_body_condition_zero",
                },
            )
            self.assertEqual(len(pitch_split_candidate_detail), 4)
            self.assertEqual(len(pitch_split_candidate_summary), 4)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "pitch_oscillation_scale",
                "pitch_forward_speed_scale",
                "candidate_affects_pitch_radiation_column",
                "candidate_recomputed_matched_bie",
                "candidate_gate_status",
            ]:
                self.assertIn(column, pitch_split_candidate_detail.columns)
                if column not in {
                    "candidate_affects_pitch_radiation_column",
                    "candidate_recomputed_matched_bie",
                    "candidate_gate_status",
                }:
                    self.assertTrue(pd.to_numeric(pitch_split_candidate_detail[column], errors="coerce").notna().any())
            self.assertFalse(pitch_split_candidate_detail["candidate_affects_pitch_radiation_column"].astype(bool).any())
            self.assertFalse(pitch_split_candidate_detail["candidate_recomputed_matched_bie"].astype(bool).any())
            for column in [
                "candidate_name",
                "pitch_oscillation_scale",
                "pitch_forward_speed_scale",
                "affected_pitch_radiation_column_count",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "candidate_gate_status",
            ]:
                self.assertIn(column, pitch_split_candidate_summary.columns)
            self.assertEqual(
                set(free_surface_marching_candidate_detail["candidate_name"]),
                {
                    "current_marching",
                    "free_surface_marching_disabled",
                    "free_surface_velocity_zero",
                    "free_surface_velocity_half",
                    "free_surface_time_step_half",
                    "free_surface_two_substeps_per_station",
                    "free_surface_time_step_quarter",
                    "free_surface_velocity_flipped",
                    "outer_history_rhs_disabled",
                },
            )
            self.assertEqual(len(free_surface_marching_candidate_detail), 9)
            self.assertEqual(len(free_surface_marching_candidate_summary), 9)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "use_free_surface_marching",
                "time_step_scale",
                "free_surface_substeps_per_station",
                "free_surface_velocity_scale",
                "history_rhs_scale",
                "matched_heave_free_surface_potential_norm_max",
                "matched_selected_body_pressure_to_body_potential_gain_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_marching_candidate_detail.columns)
                if column not in {"use_free_surface_marching", "candidate_gate_status"}:
                    self.assertTrue(
                        pd.to_numeric(free_surface_marching_candidate_detail[column], errors="coerce").notna().any()
                    )
            self.assertIn(
                "False",
                set(free_surface_marching_candidate_detail["use_free_surface_marching"].astype(str)),
            )
            for column in [
                "candidate_name",
                "use_free_surface_marching",
                "time_step_scale",
                "free_surface_substeps_per_station",
                "free_surface_velocity_scale",
                "history_rhs_scale",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_heave_free_surface_potential_norm_max",
                "median_selected_body_pressure_to_body_potential_gain_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_marching_candidate_summary.columns)
            self.assertEqual(
                set(local_time_free_surface_cross_probe["candidate_name"]),
                {
                    "default",
                    "no_free_surface_marching",
                    "local_phase_fd_gradient",
                    "local_phase_chain_gradient",
                    "local_phase_fd_no_free_surface_marching",
                    "local_phase_chain_no_free_surface_marching",
                },
            )
            self.assertEqual(len(local_time_free_surface_cross_probe), 6)
            self.assertEqual(len(local_time_free_surface_cross_probe_summary), 6)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "use_free_surface_marching",
                "apply_local_time_phase",
                "local_time_phase_gradient_correction",
                "matched_time_derivative_component_value",
                "matched_pressure_gradient_component_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, local_time_free_surface_cross_probe.columns)
                if column not in {
                    "use_free_surface_marching",
                    "apply_local_time_phase",
                    "local_time_phase_gradient_correction",
                    "candidate_gate_status",
                }:
                    self.assertTrue(
                        pd.to_numeric(local_time_free_surface_cross_probe[column], errors="coerce").notna().any()
                    )
            for column in [
                "candidate_name",
                "use_free_surface_marching",
                "apply_local_time_phase",
                "local_time_phase_gradient_correction",
                "pass_count",
                "max_gate_error_ratio",
                "worst_coefficient",
                "a33_gate_error_ratio",
                "a33_gate_status",
                "diagnostic_conclusion",
            ]:
                self.assertIn(column, local_time_free_surface_cross_probe_summary.columns)
            self.assertEqual(
                set(free_surface_update_candidate_detail["candidate_name"]),
                {
                    "current_eq19_22",
                    "reverse_local_time",
                    "dynamic_gravity_sign_flipped",
                    "potential_uses_previous_elevation",
                    "potential_uses_average_elevation",
                    "reverse_time_and_dynamic_sign",
                },
            )
            self.assertEqual(len(free_surface_update_candidate_detail), 6)
            self.assertEqual(len(free_surface_update_candidate_summary), 6)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "free_surface_time_direction_sign",
                "free_surface_dynamic_gravity_sign",
                "free_surface_potential_elevation_level",
                "matched_heave_free_surface_potential_increment_to_normal_derivative_gain_max",
                "matched_heave_free_surface_potential_increment_normal_derivative_phase_deg_median",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_update_candidate_detail.columns)
                if column not in {"free_surface_potential_elevation_level", "candidate_gate_status"}:
                    self.assertTrue(
                        pd.to_numeric(free_surface_update_candidate_detail[column], errors="coerce").notna().any()
                    )
            self.assertIn(
                "previous",
                set(free_surface_update_candidate_detail["free_surface_potential_elevation_level"].astype(str)),
            )
            for column in [
                "candidate_name",
                "free_surface_time_direction_sign",
                "free_surface_dynamic_gravity_sign",
                "free_surface_potential_elevation_level",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_heave_free_surface_increment_gain_max",
                "median_heave_free_surface_increment_phase_deg",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_update_candidate_summary.columns)
            self.assertEqual(
                set(free_surface_normal_source_candidate_detail["candidate_name"]),
                {
                    "current_raw",
                    "real_part_only",
                    "imaginary_part_only",
                    "phase_lead_90",
                    "phase_lag_90",
                    "body_velocity_norm_normalized",
                },
            )
            self.assertEqual(len(free_surface_normal_source_candidate_detail), 6)
            self.assertEqual(len(free_surface_normal_source_candidate_summary), 6)
            for column in [
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "free_surface_normal_derivative_source",
                "matched_heave_inner_free_surface_normal_derivative_norm_max",
                "matched_heave_free_surface_potential_increment_to_normal_derivative_gain_max",
                "matched_selected_body_pressure_to_body_potential_gain_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_normal_source_candidate_detail.columns)
                if column not in {"free_surface_normal_derivative_source", "candidate_gate_status"}:
                    self.assertTrue(
                        pd.to_numeric(
                            free_surface_normal_source_candidate_detail[column],
                            errors="coerce",
                        ).notna().any()
                    )
            self.assertIn(
                "imaginary_part_only",
                set(free_surface_normal_source_candidate_detail["free_surface_normal_derivative_source"].astype(str)),
            )
            for column in [
                "candidate_name",
                "free_surface_normal_derivative_source",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_heave_inner_free_surface_normal_derivative_norm_max",
                "median_heave_free_surface_increment_gain_max",
                "candidate_gate_status",
            ]:
                self.assertIn(column, free_surface_normal_source_candidate_summary.columns)
            self.assertEqual(
                set(startup_gradient_candidate_detail["candidate_name"]),
                {
                    "current_default",
                    "scheme_central",
                    "scheme_forward",
                    "scheme_backward",
                    "phase_aligned_central",
                    "phase_aligned_forward",
                    "phase_aligned_backward",
                    "mapped_fixed_y_central",
                    "mapped_fixed_y_forward",
                    "mapped_fixed_y_backward",
                    "mapped_normalized_y_central",
                    "mapped_normalized_y_forward",
                    "mapped_normalized_y_backward",
                    "startup_aft_gradient_zero",
                    "startup_aft_gradient_copy_second",
                    "startup_first_pair_gradient_average",
                },
            )
            self.assertEqual(len(startup_gradient_candidate_detail), 16)
            self.assertEqual(len(startup_gradient_candidate_summary), 16)
            for column in [
                "computed_value",
                "raw_computed_value",
                "raw_to_reference_raw_ratio",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "time_component_value",
                "forward_gradient_component_value",
                "end_component_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, startup_gradient_candidate_detail.columns)
                if column not in {"candidate_gate_status", "raw_to_reference_raw_ratio"}:
                    self.assertTrue(
                        pd.to_numeric(startup_gradient_candidate_detail[column], errors="coerce").notna().any()
                    )
            for column in [
                "candidate_name",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_forward_gradient_component_value",
                "max_abs_forward_gradient_component_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, startup_gradient_candidate_summary.columns)
            self.assertEqual(
                set(startup_gradient_station_detail["candidate_name"]),
                {
                    "current_default",
                    "scheme_central",
                    "scheme_forward",
                    "scheme_backward",
                    "phase_aligned_central",
                    "phase_aligned_forward",
                    "phase_aligned_backward",
                    "mapped_fixed_y_central",
                    "mapped_fixed_y_forward",
                    "mapped_fixed_y_backward",
                    "mapped_normalized_y_central",
                    "mapped_normalized_y_forward",
                    "mapped_normalized_y_backward",
                    "startup_aft_gradient_zero",
                    "startup_aft_gradient_copy_second",
                    "startup_first_pair_gradient_average",
                },
            )
            candidate_station_counts = startup_gradient_station_detail.groupby("candidate_name").size()
            self.assertEqual(len(set(candidate_station_counts.astype(int))), 1)
            self.assertGreater(int(candidate_station_counts.iloc[0]), 1)
            self.assertEqual(len(startup_gradient_station_summary), 16)
            for column in [
                "x_over_l",
                "trapz_weight_m",
                "current_density_value_per_m",
                "candidate_density_value_per_m",
                "candidate_station_integral_delta_vs_current",
                "current_gradient_norm",
                "candidate_gradient_norm",
                "candidate_gradient_peak_phase_delta_vs_current_deg",
            ]:
                self.assertIn(column, startup_gradient_station_detail.columns)
                self.assertTrue(pd.to_numeric(startup_gradient_station_detail[column], errors="coerce").notna().any())
            for column in [
                "candidate_name",
                "coefficient",
                "total_forward_gradient_integral_delta_vs_current",
                "dominant_delta_station_index",
                "dominant_delta_x_over_l",
                "dominant_station_delta_share_of_total_abs_delta",
                "max_gradient_peak_phase_delta_abs_deg",
            ]:
                self.assertIn(column, startup_gradient_station_summary.columns)
            self.assertEqual(len(end_pressure_closure_detail), 3)
            self.assertEqual(len(end_pressure_closure_summary), 1)
            for column in [
                "endpoint_label",
                "x_over_l",
                "trapz_weight_m",
                "endpoint_forward_gradient_integral_value",
                "endpoint_total_pressure_integral_value",
                "end_term_component_value",
                "end_to_endpoint_forward_ratio",
                "end_to_endpoint_pressure_ratio",
                "endpoint_forward_plus_end_value",
                "end_lever_minus_station_moment_lever_m",
            ]:
                self.assertIn(column, end_pressure_closure_detail.columns)
                if column not in {"endpoint_label", "end_to_endpoint_forward_ratio", "end_to_endpoint_pressure_ratio"}:
                    self.assertTrue(pd.to_numeric(end_pressure_closure_detail[column], errors="coerce").notna().any())
            for column in [
                "coefficient",
                "endpoint_label",
                "endpoint_forward_gradient_integral_value",
                "end_term_component_value",
                "end_to_endpoint_forward_ratio_abs",
                "end_lever_minus_station_moment_lever_m",
            ]:
                self.assertIn(column, end_pressure_closure_summary.columns)
            self.assertEqual(comparison["provider_route"].iloc[0], "matched_bie_station_sweep")
            self.assertEqual(comparison["provider_formulation"].iloc[0], "matched_bie")
            self.assertAlmostEqual(float(comparison["matched_inner_a_scale"].iloc[0]), 1.0)
            self.assertAlmostEqual(float(comparison["matched_inner_diagonal_sign"].iloc[0]), -1.0)
            self.assertAlmostEqual(
                float(comparison["matched_inner_free_surface_self_diagonal_scale"].iloc[0]),
                1.0,
            )
            self.assertAlmostEqual(
                float(comparison["matched_inner_free_surface_known_potential_rhs_scale"].iloc[0]),
                1.0,
            )
            self.assertAlmostEqual(
                float(comparison["matched_inner_free_surface_unknown_normal_column_scale"].iloc[0]),
                1.0,
            )
            self.assertIn("matched_sweep", comparison["solver_status"].iloc[0])
            self.assertIn("ma2005_eq34_normalization_formula", comparison.columns)
            self.assertIn("rho*displacement_volume", comparison["ma2005_eq34_normalization_formula"].iloc[0])
            self.assertEqual(int(comparison["ma2005_eq34_documented_length_power"].iloc[0]), 0)
            self.assertTrue(math.isfinite(float(comparison["ma2005_required_normalization_scale"].iloc[0])))
            self.assertIn("ma2005_candidate_length_power_2_value", comparison.columns)
            self.assertIn(
                comparison["ma2005_best_length_power_candidate_status"].iloc[0],
                {"PASS", "FAIL"},
            )
            for column in [
                "matched_time_derivative_component_value",
                "matched_pressure_gradient_component_value",
                "matched_end_term_component_value",
                "matched_force_closure_residual_value",
                "matched_candidate_time_only_value",
                "matched_candidate_time_only_raw_to_reference_raw_ratio",
                "matched_candidate_time_plus_pressure_gradient_value",
                "matched_candidate_time_plus_pressure_gradient_raw_to_reference_raw_ratio",
                "matched_candidate_time_plus_pressure_gradient_plus_end_value",
                "matched_candidate_time_plus_pressure_gradient_plus_end_raw_to_reference_raw_ratio",
                "matched_candidate_time_plus_stokes_body_value",
                "matched_candidate_time_plus_stokes_body_raw_to_reference_raw_ratio",
                "matched_candidate_time_plus_stokes_body_plus_end_value",
                "matched_candidate_time_plus_stokes_body_plus_end_raw_to_reference_raw_ratio",
                "matched_candidate_time_plus_pressure_gradient_plus_stokes_body_value",
                "matched_candidate_time_plus_pressure_gradient_plus_stokes_body_raw_to_reference_raw_ratio",
                "matched_candidate_all_terms_value",
                "matched_candidate_all_terms_raw_to_reference_raw_ratio",
                "matched_candidate_best_value",
                "matched_candidate_best_raw_to_reference_raw_ratio",
                "matched_candidate_best_abs_relative_error",
                "matched_pressure_sign_candidate_time_derivative_flipped_keep_gradient_end_value",
                "matched_pressure_sign_candidate_time_derivative_flipped_keep_gradient_end_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_pressure_gradient_flipped_keep_time_end_value",
                "matched_pressure_sign_candidate_pressure_gradient_flipped_keep_time_end_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_body_pressure_flipped_keep_end_value",
                "matched_pressure_sign_candidate_body_pressure_flipped_keep_end_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_body_pressure_and_end_flipped_value",
                "matched_pressure_sign_candidate_body_pressure_and_end_flipped_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_all_terms_flipped_value",
                "matched_pressure_sign_candidate_all_terms_flipped_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_best_value",
                "matched_pressure_sign_candidate_best_raw_to_reference_raw_ratio",
                "matched_pressure_sign_candidate_best_abs_relative_error",
                "matched_heave_free_surface_potential_norm_max",
                "matched_heave_inner_free_surface_normal_derivative_norm_max",
                "matched_heave_free_surface_potential_increment_to_normal_derivative_gain_max",
                "matched_heave_free_surface_potential_increment_normal_derivative_phase_deg_median",
                "matched_heave_body_pressure_to_body_potential_gain_max",
                "matched_heave_body_pressure_forward_to_time_norm_ratio_max",
                "matched_selected_pressure_time_formula_ratio_median",
                "matched_selected_pressure_forward_formula_ratio_median",
                "matched_selected_body_potential_x_gradient_norm_max",
                "matched_selected_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_body_potential_x_gradient_characteristic_length_min",
                "matched_selected_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_adjacent_body_potential_relative_jump_max",
                "matched_selected_adjacent_body_potential_symmetric_norm_ratio_max",
                "matched_selected_adjacent_body_potential_phase_deg_abs_max",
                "matched_selected_adjacent_body_potential_real_alignment_min",
                "matched_station_waterplane_beam_adjacent_relative_jump_max",
                "matched_station_effective_draft_adjacent_relative_jump_max",
                "matched_station_submerged_area_adjacent_relative_jump_max",
                "matched_station_waterplane_beam_gradient_to_beam_gain_max",
                "matched_station_effective_draft_gradient_to_draft_gain_max",
                "matched_station_submerged_area_gradient_to_area_gain_max",
                "matched_station_waterplane_beam_gradient_peak_x_over_l",
                "matched_station_submerged_area_gradient_peak_x_over_l",
                "matched_selected_body_potential_norm_to_beam_squared_ratio_max",
                "matched_selected_body_potential_norm_to_submerged_area_ratio_max",
                "matched_selected_body_potential_norm_to_beam_squared_peak_x_over_l",
                "matched_selected_body_potential_norm_to_submerged_area_peak_x_over_l",
                "matched_selected_central_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_forward_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_backward_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_central_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_forward_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_backward_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_phase_aligned_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_phase_aligned_body_potential_x_gradient_characteristic_length_min",
                "matched_selected_phase_aligned_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_phase_aligned_gradient_gain_to_raw_gain_ratio_median",
                "matched_selected_phase_aligned_central_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_phase_aligned_forward_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_phase_aligned_backward_body_potential_x_gradient_to_potential_gain_max",
                "matched_selected_phase_aligned_central_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_phase_aligned_forward_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_phase_aligned_backward_body_potential_x_gradient_gain_times_hull_length_max",
                "matched_selected_phase_aligned_adjacent_body_potential_relative_jump_max",
                "matched_selected_phase_aligned_adjacent_body_potential_phase_deg_abs_max",
                "matched_selected_phase_aligned_adjacent_body_potential_real_alignment_min",
                "matched_body_panel_mid_y_adjacent_relative_jump_max",
                "matched_body_panel_mid_z_adjacent_relative_jump_max",
                "matched_body_panel_normal_adjacent_relative_jump_max",
                "matched_body_panel_length_adjacent_relative_jump_max",
                "matched_selected_body_pressure_to_body_potential_gain_max",
                "matched_selected_body_pressure_forward_to_time_norm_ratio_max",
                "matched_selected_generalized_force_to_pressure_norm_gain_max",
                "matched_selected_total_force_density_peak_x_over_l",
                "matched_selected_time_derivative_force_density_peak_x_over_l",
                "matched_selected_forward_speed_force_density_peak_x_over_l",
                "matched_selected_total_force_density_abs_centroid_x_over_l",
                "matched_selected_time_derivative_force_density_abs_centroid_x_over_l",
                "matched_selected_forward_speed_force_density_abs_centroid_x_over_l",
                "matched_selected_total_force_density_peak_to_integral_abs_ratio",
                "matched_selected_time_derivative_force_density_peak_to_integral_abs_ratio",
                "matched_selected_forward_speed_force_density_peak_to_integral_abs_ratio",
                "matched_selected_total_density_positive_integral_value",
                "matched_selected_total_density_negative_integral_value",
                "matched_selected_total_density_cancellation_index",
                "matched_selected_time_derivative_density_positive_integral_value",
                "matched_selected_time_derivative_density_negative_integral_value",
                "matched_selected_time_derivative_density_cancellation_index",
                "matched_selected_forward_speed_density_positive_integral_value",
                "matched_selected_forward_speed_density_negative_integral_value",
                "matched_selected_forward_speed_density_cancellation_index",
                "matched_selected_stokes_body_forward_density_positive_integral_value",
                "matched_selected_stokes_body_forward_density_negative_integral_value",
                "matched_selected_stokes_body_forward_density_cancellation_index",
                "matched_aft_active_station_x_over_l",
                "matched_aft_active_station_waterplane_beam",
                "matched_aft_active_station_effective_draft",
                "matched_aft_active_station_submerged_area",
                "matched_aft_active_station_body_panel_length_sum",
                "matched_aft_active_station_body_panel_length_max",
                "matched_aft_active_station_body_panel_normal_z_norm",
                "matched_aft_active_station_heave_generalized_row_norm",
                "matched_aft_active_station_pitch_generalized_row_norm",
                "matched_selected_aft_active_body_potential_norm",
                "matched_selected_aft_active_body_potential_x_gradient_norm",
                "matched_selected_aft_active_body_potential_x_gradient_to_potential_gain",
                "matched_selected_aft_active_body_pressure_norm",
                "matched_selected_aft_active_body_pressure_time_derivative_norm",
                "matched_selected_aft_active_body_pressure_forward_speed_norm",
                "matched_selected_aft_active_body_pressure_forward_to_time_norm_ratio",
                "matched_selected_aft_active_total_force_density_abs",
                "matched_selected_aft_active_time_derivative_force_density_abs",
                "matched_selected_aft_active_forward_speed_force_density_abs",
                "matched_selected_pressure_integral_excluding_aft_active_station_value",
                "matched_selected_pressure_integral_excluding_aft_active_station_raw_to_reference_raw_ratio",
                "matched_selected_pressure_integral_excluding_bow_active_station_value",
                "matched_selected_pressure_integral_excluding_bow_active_station_raw_to_reference_raw_ratio",
                "matched_selected_pressure_integral_excluding_end_active_stations_value",
                "matched_selected_pressure_integral_excluding_end_active_stations_raw_to_reference_raw_ratio",
                "matched_selected_time_integral_excluding_aft_active_station_value",
                "matched_selected_forward_integral_excluding_aft_active_station_value",
                "matched_selected_coefficient_raw_from_total_force",
                "matched_selected_reference_raw_coefficient",
                "matched_selected_raw_to_reference_raw_ratio",
                "matched_selected_required_scale_to_reference",
                "matched_heave_eq24_outer_control_relative_residual_max",
            ]:
                self.assertIn(column, comparison.columns)
                self.assertTrue(math.isfinite(float(comparison[column].iloc[0])))
            self.assertAlmostEqual(
                float(comparison["matched_selected_pressure_time_formula_ratio_median"].iloc[0]),
                1.0,
            )
            self.assertIn(
                comparison["matched_dominant_force_component"].iloc[0],
                {"body_pressure", "time_derivative", "pressure_gradient", "stokes_body_forward", "end_term"},
            )
            self.assertIn(
                comparison["matched_candidate_best_combination"].iloc[0],
                {
                    "time_only",
                    "time_plus_pressure_gradient",
                    "time_plus_pressure_gradient_plus_end",
                    "time_plus_stokes_body",
                    "time_plus_stokes_body_plus_end",
                    "time_plus_pressure_gradient_plus_stokes_body",
                    "all_terms",
                },
            )
            self.assertIn(
                comparison["matched_pressure_sign_candidate_best_combination"].iloc[0],
                {
                    "time_derivative_flipped_keep_gradient_end",
                    "pressure_gradient_flipped_keep_time_end",
                    "body_pressure_flipped_keep_end",
                    "body_pressure_and_end_flipped",
                    "all_terms_flipped",
                },
            )
            pressure_sign_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pressure_sign_candidate_detail.csv"
            )
            pressure_sign_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pressure_sign_candidate_summary.csv"
            )
            force_assembly_route_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_force_assembly_route_candidate_detail.csv"
            )
            force_assembly_route_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_force_assembly_route_candidate_summary.csv"
            )
            eq30_balance_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_detail.csv"
            )
            eq30_balance_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv"
            )
            eq30_scale_fit_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_component_scale_fit_detail.csv"
            )
            eq30_scale_fit_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary.csv"
            )
            gate1_failure_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_failure_audit.csv"
            )
            gate1_failure_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_failure_summary.csv"
            )
            gate1_remaining_blocker_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_remaining_blocker_audit.csv"
            )
            gate1_remaining_blocker_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_remaining_blocker_summary.csv"
            )
            literature_traceability_gap_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_literature_traceability_gap_audit.csv"
            )
            literature_traceability_gap_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_literature_traceability_gap_summary.csv"
            )
            journee_table_reference_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_table_reference_audit.csv"
            )
            journee_table_reference_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_table_reference_summary.csv"
            )
            gate1_reference_trace = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_reference_trace.csv"
            )
            gate1_reference_trace_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_reference_trace_summary.csv"
            )
            a1_frequency_ladder_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_frequency_ladder_audit.csv"
            )
            a1_frequency_ladder_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_a1_frequency_ladder_summary.csv"
            )
            journee_frequency_gate_probe = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_frequency_gate_probe.csv"
            )
            journee_frequency_gate_probe_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_frequency_gate_probe_summary.csv"
            )
            reference_pairing_policy_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_reference_pairing_policy_audit.csv"
            )
            reference_pairing_policy_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_reference_pairing_policy_summary.csv"
            )
            journee_coefficient_frequency_trend_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_coefficient_frequency_trend_audit.csv"
            )
            journee_coefficient_frequency_trend_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_coefficient_frequency_trend_summary.csv"
            )
            journee_component_frequency_trend_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_component_frequency_trend_audit.csv"
            )
            journee_component_frequency_trend_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_component_frequency_trend_summary.csv"
            )
            body_potential_frequency_entry_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_potential_frequency_entry_audit.csv"
            )
            body_potential_frequency_entry_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_potential_frequency_entry_summary.csv"
            )
            journee_complex_scale_phase_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_complex_scale_phase_audit.csv"
            )
            journee_complex_scale_phase_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_journee_complex_scale_phase_summary.csv"
            )
            coefficient_conversion_chain_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_coefficient_conversion_chain_audit.csv"
            )
            coefficient_conversion_chain_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_coefficient_conversion_chain_summary.csv"
            )
            body_condition_unit_chain_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_condition_unit_chain_audit.csv"
            )
            body_condition_unit_chain_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_condition_unit_chain_summary.csv"
            )
            time_pressure_scale_origin_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_time_pressure_scale_origin_audit.csv"
            )
            time_pressure_scale_origin_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_time_pressure_scale_origin_summary.csv"
            )
            time_pressure_formula_unit_chain_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_time_pressure_formula_unit_chain_audit.csv"
            )
            time_pressure_formula_unit_chain_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_time_pressure_formula_unit_chain_summary.csv"
            )
            body_potential_normalization_trace_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_potential_normalization_trace_audit.csv"
            )
            body_potential_normalization_trace_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_body_potential_normalization_trace_summary.csv"
            )
            phi_phi_n_kernel_normalization_trace_audit = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_phi_phi_n_kernel_normalization_trace_audit.csv"
            )
            phi_phi_n_kernel_normalization_trace_summary = pd.read_csv(
                tmp_path
                / "out"
                / "ma2005_wigley_iii_coefficients_phi_phi_n_kernel_normalization_trace_summary.csv"
            )
            shared_body_potential_scale_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_shared_body_potential_scale_audit.csv"
            )
            shared_body_potential_scale_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_shared_body_potential_scale_summary.csv"
            )
            free_surface_longitudinal_staggering_audit = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_longitudinal_staggering_audit.csv"
            )
            free_surface_longitudinal_staggering_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_free_surface_longitudinal_staggering_summary.csv"
            )
            rhs_source_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_rhs_source_decomposition_detail.csv"
            )
            rhs_source_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_rhs_source_decomposition_summary.csv"
            )
            inner_state_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_inner_free_surface_state_marching_detail.csv"
            )
            inner_state_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_inner_free_surface_state_marching_summary.csv"
            )
            self.assertEqual(
                set(pressure_sign_summary["candidate_name"]),
                {
                    "current_default",
                    "time_derivative_flipped_keep_gradient_end",
                    "pressure_gradient_flipped_keep_time_end",
                    "body_pressure_flipped_keep_end",
                    "body_pressure_and_end_flipped",
                    "all_terms_flipped",
                },
            )
            self.assertEqual(len(pressure_sign_detail), 6)
            self.assertIn("candidate_gate_status", pressure_sign_summary.columns)
            self.assertEqual(
                set(force_assembly_route_summary["force_assembly_route"]),
                {
                    "current_hybrid_pressure_gradient_plus_end",
                    "eq31_pressure_gradient_only",
                    "eq32_stokes_body_plus_end",
                    "eq32_stokes_body_only",
                    "eq31_pressure_gradient_plus_row_measure_transport",
                    "eq31_pressure_gradient_minus_row_measure_transport",
                    "eq31_pressure_gradient_plus_row_measure_transport_plus_end",
                    "eq31_pressure_gradient_minus_row_measure_transport_plus_end",
                    "all_terms_pressure_gradient_stokes_end",
                },
            )
            self.assertGreater(len(force_assembly_route_detail), 0)
            self.assertTrue(
                force_assembly_route_summary["candidate_default_gate_eligible"]
                .astype(str)
                .str.lower()
                .eq("false")
                .all()
            )
            self.assertEqual(
                set(eq30_balance_summary["candidate_name"]),
                {
                    "current_default",
                    "time_only_no_gradient_no_end",
                    "time_plus_gradient_no_end",
                    "gradient_removed_keep_time_end",
                    "gradient_flipped_keep_time_end",
                    "gradient_half_keep_time_end",
                    "gradient_double_keep_time_end",
                    "time_removed_keep_gradient_end",
                    "time_flipped_keep_gradient_end",
                    "time_half_keep_gradient_end",
                    "time_double_keep_gradient_end",
                    "end_flipped_keep_pressure",
                    "time_plus_stokes_plus_end",
                    "all_terms_include_stokes",
                },
            )
            self.assertEqual(len(eq30_balance_detail), 14)
            for column in [
                "computed_value",
                "raw_computed_value",
                "raw_to_reference_raw_ratio",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "time_derivative_pressure_scale",
                "forward_speed_pressure_gradient_scale",
                "stokes_body_forward_speed_scale",
                "end_contour_scale",
                "time_derivative_component_value",
                "forward_speed_pressure_gradient_component_value",
                "stokes_body_forward_speed_component_value",
                "end_contour_component_value",
                "candidate_time_derivative_contribution_value",
                "candidate_forward_speed_pressure_gradient_contribution_value",
                "candidate_stokes_body_forward_speed_contribution_value",
                "candidate_end_contour_contribution_value",
                "current_force_closure_residual_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, eq30_balance_detail.columns)
                if column not in {"candidate_gate_status", "raw_to_reference_raw_ratio"}:
                    self.assertTrue(pd.to_numeric(eq30_balance_detail[column], errors="coerce").notna().any())
            current_eq30 = eq30_balance_detail[eq30_balance_detail["candidate_name"].eq("current_default")].iloc[0]
            reconstructed = (
                float(current_eq30["candidate_time_derivative_contribution_value"])
                + float(current_eq30["candidate_forward_speed_pressure_gradient_contribution_value"])
                + float(current_eq30["candidate_stokes_body_forward_speed_contribution_value"])
                + float(current_eq30["candidate_end_contour_contribution_value"])
            )
            self.assertAlmostEqual(float(current_eq30["computed_value"]), reconstructed)
            self.assertLess(abs(float(current_eq30["current_force_closure_residual_value"])), 1e-9)
            for column in [
                "candidate_name",
                "time_derivative_pressure_scale",
                "forward_speed_pressure_gradient_scale",
                "stokes_body_forward_speed_scale",
                "end_contour_scale",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "median_time_derivative_contribution_value",
                "median_forward_speed_pressure_gradient_contribution_value",
                "median_stokes_body_forward_speed_contribution_value",
                "median_end_contour_contribution_value",
                "max_abs_current_force_closure_residual_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, eq30_balance_summary.columns)
            self.assertEqual(
                set(eq30_scale_fit_summary["fit_name"]),
                {
                    "least_squares_time_only",
                    "least_squares_gradient_only",
                    "least_squares_time_gradient",
                    "least_squares_time_gradient_end",
                    "least_squares_time_gradient_stokes_end",
                },
            )
            self.assertEqual(len(eq30_scale_fit_detail), 5)
            self.assertEqual(len(eq30_scale_fit_summary), 5)
            for column in [
                "fit_name",
                "fit_component_set",
                "fit_rank",
                "reference_value",
                "computed_value",
                "raw_computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "time_derivative_fit_scale",
                "pressure_gradient_fit_scale",
                "stokes_body_forward_fit_scale",
                "end_term_fit_scale",
                "time_derivative_fit_contribution_value",
                "pressure_gradient_fit_contribution_value",
                "stokes_body_forward_fit_contribution_value",
                "end_term_fit_contribution_value",
                "candidate_gate_status",
            ]:
                self.assertIn(column, eq30_scale_fit_detail.columns)
                if column not in {"fit_name", "fit_component_set", "candidate_gate_status"}:
                    self.assertTrue(pd.to_numeric(eq30_scale_fit_detail[column], errors="coerce").notna().any())
            for column in [
                "fit_name",
                "fit_component_set",
                "fit_rank",
                "row_count",
                "pass_fraction",
                "median_gate_error_ratio",
                "max_gate_error_ratio",
                "improved_row_count",
                "worsened_row_count",
                "time_derivative_fit_scale",
                "pressure_gradient_fit_scale",
                "stokes_body_forward_fit_scale",
                "end_term_fit_scale",
                "candidate_gate_status",
            ]:
                self.assertIn(column, eq30_scale_fit_summary.columns)
                if column not in {"fit_name", "fit_component_set", "candidate_gate_status"}:
                    self.assertTrue(pd.to_numeric(eq30_scale_fit_summary[column], errors="coerce").notna().any())
            self.assertEqual(len(gate1_failure_audit), 1)
            self.assertGreaterEqual(len(gate1_failure_summary), 8)
            for column in [
                "coefficient",
                "reference_value",
                "computed_value",
                "gate_error_ratio",
                "status",
                "provider_route",
                "gate1_current_status",
                "time_derivative_pressure_contribution_value",
                "forward_speed_pressure_gradient_contribution_value",
                "stokes_body_forward_speed_contribution_value",
                "end_contour_contribution_value",
                "current_force_closure_residual_value",
                "dominant_eq30_component",
                "rhs_source_decomposition_evidence",
                "inner_free_surface_state_marching_evidence",
                "failure_source",
                "excluded_pressure_balance_candidate_evidence",
                "excluded_component_scale_fit_evidence",
                "excluded_full_four_component_scale_fit_evidence",
                "excluded_family_scale_candidate_evidence",
                "excluded_eq31_eq32_forward_identity_evidence",
                "excluded_free_surface_marching_candidate_evidence",
                "excluded_local_time_free_surface_cross_probe_evidence",
                "station_forward_identity_localization_evidence",
                "section_force_derivative_path_evidence",
                "station_mapping_gradient_evidence",
                "station_marching_direction_evidence",
                "aft_terminal_end_closure_evidence",
                "stokes_end_lever_consistency_evidence",
                "complex_forward_identity_evidence",
                "projection_derivative_balance_evidence",
                "projection_transport_evidence",
                "geometry_transport_balance_evidence",
                "candidate_policy",
                "remaining_blocker",
            ]:
                self.assertIn(column, gate1_failure_audit.columns)
            for column in [
                "requirement",
                "expected",
                "actual",
                "requirement_status",
                "gate1_current_status",
                "evidence",
                "source_file",
            ]:
                self.assertIn(column, gate1_failure_summary.columns)
            self.assertIn("provider_route_preserved", set(gate1_failure_summary["requirement"]))
            self.assertIn("current_default_gate", set(gate1_failure_summary["requirement"]))
            self.assertIn("full_four_component_scale_fit_exclusion", set(gate1_failure_summary["requirement"]))
            self.assertIn("coefficient_family_scale_fit_exclusion", set(gate1_failure_summary["requirement"]))
            self.assertIn("eq31_eq32_forward_identity_exclusion", set(gate1_failure_summary["requirement"]))
            self.assertIn("complex_forward_identity_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("projection_derivative_balance_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("projection_transport_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("geometry_transport_balance_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("eq30_component_contribution_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("station_mapping_gradient_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("station_marching_direction_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("aft_terminal_end_closure_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("stokes_end_lever_consistency_audit", set(gate1_failure_summary["requirement"]))
            self.assertIn("free_surface_marching_time_step_exclusion", set(gate1_failure_summary["requirement"]))
            self.assertIn(
                "local_time_pressure_free_surface_cross_probe",
                set(gate1_failure_summary["requirement"]),
            )
            self.assertIn("station_forward_identity_localization", set(gate1_failure_summary["requirement"]))
            self.assertIn("section_force_derivative_path_localization", set(gate1_failure_summary["requirement"]))
            self.assertIn("rhs_source_decomposition", set(gate1_failure_summary["requirement"]))
            self.assertIn("inner_free_surface_state_marching", set(gate1_failure_summary["requirement"]))
            self.assertEqual(gate1_failure_audit["provider_route"].iloc[0], "matched_bie_station_sweep")
            self.assertIn(gate1_failure_audit["gate1_current_status"].iloc[0], {"PASS", "PENDING"})
            self.assertGreater(len(gate1_remaining_blocker_audit), 0)
            self.assertEqual(len(gate1_remaining_blocker_summary), 1)
            for column in [
                "blocker_id",
                "blocker_status",
                "remaining_blocker",
                "default_fix_allowed_by_current_evidence",
                "evidence_strength",
                "next_required_evidence",
            ]:
                self.assertIn(column, gate1_remaining_blocker_audit.columns)
            for column in [
                "remaining_blocker_count",
                "open_blockers",
                "current_materials_or_theory_gap_count",
                "compression_status",
                "literature_traceability_status",
                "literature_confirmed_gate1_gap_count",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, gate1_remaining_blocker_summary.columns)
            self.assertGreater(len(literature_traceability_gap_audit), 0)
            self.assertEqual(len(literature_traceability_gap_summary), 1)
            for column in [
                "gap_id",
                "gate1_relevant",
                "target_coefficients",
                "available_literature_evidence",
                "missing_evidence",
                "traceability_status",
                "source_references",
            ]:
                self.assertIn(column, literature_traceability_gap_audit.columns)
            for column in [
                "gate1_relevant_gap_count",
                "confirmed_gate1_relevant_gap_count",
                "future_validation_data_gap_count",
                "all_gate1_relevant_gaps_confirmed",
                "traceability_status",
            ]:
                self.assertIn(column, literature_traceability_gap_summary.columns)
            self.assertGreater(len(journee_table_reference_audit), 0)
            self.assertEqual(len(journee_table_reference_summary), 1)
            for column in [
                "coefficient",
                "current_omega_e_sqrt_l_over_g",
                "current_reference_value",
                "nearest_journee_omega_e_sqrt_l_over_g",
                "nearest_journee_reference_value",
                "audit_status",
            ]:
                self.assertIn(column, journee_table_reference_audit.columns)
            for column in [
                "matched_row_count",
                "frequency_mismatch_count",
                "value_close_count",
                "external_integrated_reference_status",
                "default_promotion_allowed_by_journee_table",
            ]:
                self.assertIn(column, journee_table_reference_summary.columns)
            self.assertGreater(len(gate1_reference_trace), 0)
            self.assertEqual(len(gate1_reference_trace_summary), 1)
            for column in [
                "gate1_row",
                "coefficient",
                "gate1_omega_e_sqrt_l_over_g",
                "gate1_reference_value",
                "source_figure",
                "ma_source_row_matched",
                "nearest_journee_omega_e_sqrt_l_over_g",
                "journee_omega_abs_delta",
                "journee_frequency_close",
                "reference_trace_status",
            ]:
                self.assertIn(column, gate1_reference_trace.columns)
            for column in [
                "row_count",
                "source_row_match_count",
                "journee_nearest_match_count",
                "journee_frequency_mismatch_count",
                "journee_value_close_count",
                "reference_trace_status",
            ]:
                self.assertIn(column, gate1_reference_trace_summary.columns)
            self.assertGreater(len(a1_frequency_ladder_audit), 0)
            self.assertEqual(len(a1_frequency_ladder_summary), 1)
            for column in [
                "source",
                "coefficient",
                "omega_e_sqrt_l_over_g",
                "nearest_a1_circular_frequency_rad_s",
                "nearest_a1_omega_sqrt_l_over_g",
                "omega_abs_delta_to_a1_ladder",
                "omega_rel_delta_to_a1_ladder",
                "a1_ladder_match",
                "frequency_trace_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, a1_frequency_ladder_audit.columns)
            for column in [
                "gate1_row_count",
                "gate1_ladder_match_count",
                "gate1_ladder_mismatch_count",
                "journee_row_count",
                "journee_ladder_match_count",
                "journee_ladder_mismatch_count",
                "frequency_trace_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, a1_frequency_ladder_summary.columns)
            self.assertIn(
                "gate1_sparse_ma_figure_row",
                set(a1_frequency_ladder_audit["source"].astype(str)),
            )
            self.assertFalse(a1_frequency_ladder_audit["candidate_default_gate_eligible"].astype(bool).any())
            self.assertFalse(a1_frequency_ladder_summary["candidate_default_gate_eligible"].astype(bool).any())
            self.assertGreater(len(journee_frequency_gate_probe), 0)
            self.assertEqual(len(journee_frequency_gate_probe_summary), 1)
            for column in [
                "coefficient",
                "current_gate_omega_e_sqrt_l_over_g",
                "journee_omega_e_sqrt_l_over_g",
                "reference_value",
                "computed_value",
                "gate_error_ratio",
                "status",
                "provider_route",
            ]:
                self.assertIn(column, journee_frequency_gate_probe.columns)
            for column in [
                "row_count",
                "pass_count",
                "fail_count",
                "max_gate_error_ratio",
                "median_gate_error_ratio",
                "diagnostic_conclusion",
            ]:
                self.assertIn(column, journee_frequency_gate_probe_summary.columns)
            self.assertGreater(len(reference_pairing_policy_audit), 0)
            self.assertEqual(len(reference_pairing_policy_summary), 1)
            for column in [
                "evidence_item",
                "evidence_source",
                "policy_implication",
                "allows_default_reference_switch",
                "allows_equation_candidate_promotion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, reference_pairing_policy_audit.columns)
            for column in [
                "active_hard_gate_reference_policy",
                "reference_pairing_conclusion",
                "default_reference_switch_allowed",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, reference_pairing_policy_summary.columns)
            self.assertFalse(reference_pairing_policy_audit["allows_default_reference_switch"].astype(bool).any())
            self.assertFalse(reference_pairing_policy_audit["candidate_default_gate_eligible"].astype(bool).any())
            self.assertFalse(reference_pairing_policy_summary["candidate_default_gate_eligible"].astype(bool).any())
            self.assertGreater(len(journee_coefficient_frequency_trend_audit), 0)
            self.assertEqual(len(journee_coefficient_frequency_trend_summary), 1)
            for column in [
                "coefficient",
                "reference_frequency_sensitivity_ratio",
                "computed_frequency_sensitivity_ratio",
                "computed_to_reference_sensitivity_ratio",
                "required_scale_max_over_min_abs",
                "computed_values_invariant",
                "reference_values_variant",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_coefficient_frequency_trend_audit.columns)
            for column in [
                "coefficient_count",
                "frequency_invariant_computed_count",
                "required_scale_varying_count",
                "affected_coefficients",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_coefficient_frequency_trend_summary.columns)
            self.assertFalse(
                journee_coefficient_frequency_trend_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                journee_coefficient_frequency_trend_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(journee_component_frequency_trend_audit), 0)
            self.assertEqual(len(journee_component_frequency_trend_summary), 1)
            for column in [
                "coefficient",
                "component_name",
                "component_frequency_sensitivity_ratio",
                "component_to_reference_sensitivity_ratio",
                "component_values_invariant",
                "computed_values_invariant",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_component_frequency_trend_audit.columns)
            for column in [
                "component_row_count",
                "frequency_invariant_component_count",
                "computed_frequency_invariant_count",
                "affected_components",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_component_frequency_trend_summary.columns)
            self.assertFalse(
                journee_component_frequency_trend_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                journee_component_frequency_trend_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(body_potential_frequency_entry_audit), 0)
            self.assertEqual(len(body_potential_frequency_entry_summary), 1)
            for column in [
                "coefficient",
                "radiation_mode",
                "body_condition_frequency_sensitivity_ratio",
                "body_potential_frequency_sensitivity_ratio",
                "body_potential_to_condition_sensitivity_ratio",
                "time_pressure_to_potential_frequency_gain_median",
                "forward_pressure_to_potential_gradient_proxy_median",
                "body_potential_tracks_body_condition",
                "body_potential_frequency_filter_missing",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, body_potential_frequency_entry_audit.columns)
            for column in [
                "coefficient_count",
                "tracked_body_condition_count",
                "body_potential_filter_missing_count",
                "computed_frequency_invariant_count",
                "affected_coefficients",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, body_potential_frequency_entry_summary.columns)
            self.assertFalse(
                body_potential_frequency_entry_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                body_potential_frequency_entry_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(journee_complex_scale_phase_audit), 0)
            self.assertEqual(len(journee_complex_scale_phase_summary), 1)
            for column in [
                "matrix_cell",
                "required_complex_scale_abs",
                "required_complex_scale_phase_deg",
                "least_squares_real_scale_residual_norm",
                "a_required_scale",
                "b_required_scale",
                "a_b_required_scale_log10_abs_delta",
                "same_real_scale_plausible",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_complex_scale_phase_audit.columns)
            for column in [
                "pair_count",
                "real_scale_plausible_count",
                "ab_scale_consistent_count",
                "complex_scale_abs_max_over_min",
                "complex_scale_phase_span_deg",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, journee_complex_scale_phase_summary.columns)
            self.assertFalse(journee_complex_scale_phase_audit["candidate_default_gate_eligible"].astype(bool).any())
            self.assertFalse(journee_complex_scale_phase_summary["candidate_default_gate_eligible"].astype(bool).any())
            self.assertGreater(len(coefficient_conversion_chain_audit), 0)
            self.assertGreater(len(coefficient_conversion_chain_summary), 0)
            for column in [
                "coefficient",
                "variant_name",
                "reference_value",
                "computed_value",
                "gate_error_ratio",
                "gate_ratio_delta_vs_current",
                "status",
            ]:
                self.assertIn(column, coefficient_conversion_chain_audit.columns)
            for column in [
                "variant_name",
                "row_count",
                "pass_count",
                "fail_count",
                "max_gate_error_ratio",
                "diagnostic_conclusion",
            ]:
                self.assertIn(column, coefficient_conversion_chain_summary.columns)
            self.assertGreater(len(body_condition_unit_chain_audit), 0)
            self.assertGreater(len(body_condition_unit_chain_summary), 0)
            for column in [
                "coefficient",
                "variant_name",
                "reference_value",
                "computed_value",
                "scale_factor_applied_to_current_value",
                "gate_error_ratio",
                "phase_rotation_not_represented",
                "status",
            ]:
                self.assertIn(column, body_condition_unit_chain_audit.columns)
            for column in [
                "variant_name",
                "row_count",
                "pass_count",
                "fail_count",
                "max_gate_error_ratio",
                "median_gate_error_ratio",
                "diagnostic_conclusion",
            ]:
                self.assertIn(column, body_condition_unit_chain_summary.columns)
            self.assertGreater(len(time_pressure_scale_origin_audit), 0)
            self.assertEqual(len(time_pressure_scale_origin_summary), 1)
            for column in [
                "coefficient",
                "required_scale_to_reference",
                "nearest_simple_constant",
                "one_over_pi_squared_gate_error_ratio",
                "length_power2_gate_error_ratio",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, time_pressure_scale_origin_audit.columns)
            for column in [
                "row_count",
                "required_scale_min",
                "required_scale_max",
                "nearest_simple_constant_counts",
                "one_over_pi_squared_pass_count",
                "length_power2_pass_count",
                "diagnostic_conclusion",
            ]:
                self.assertIn(column, time_pressure_scale_origin_summary.columns)
            self.assertFalse(time_pressure_scale_origin_audit["candidate_default_gate_eligible"].astype(bool).any())
            self.assertFalse(
                time_pressure_scale_origin_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(time_pressure_formula_unit_chain_audit), 0)
            self.assertEqual(len(time_pressure_formula_unit_chain_summary), 1)
            for column in [
                "trace_item",
                "evidence_source",
                "supports_default_time_pressure_change",
                "blocks_default_time_pressure_change",
                "diagnostic_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, time_pressure_formula_unit_chain_audit.columns)
            for column in [
                "trace_item_count",
                "blocking_trace_count",
                "supporting_default_change_count",
                "one_over_pi_squared_formula_traced",
                "harmonic_sign_flip_global",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, time_pressure_formula_unit_chain_summary.columns)
            self.assertFalse(
                time_pressure_formula_unit_chain_audit["supports_default_time_pressure_change"].astype(bool).any()
            )
            self.assertFalse(
                time_pressure_formula_unit_chain_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                time_pressure_formula_unit_chain_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(body_potential_normalization_trace_audit), 0)
            self.assertEqual(len(body_potential_normalization_trace_summary), 1)
            for column in [
                "trace_item",
                "evidence_source",
                "supports_default_body_potential_rescale",
                "blocks_default_body_potential_rescale",
                "diagnostic_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, body_potential_normalization_trace_audit.columns)
            for column in [
                "trace_item_count",
                "blocking_trace_count",
                "supporting_default_rescale_count",
                "open_section_median_potential_norm_ratio_min",
                "open_section_median_potential_norm_ratio_max",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, body_potential_normalization_trace_summary.columns)
            self.assertFalse(
                body_potential_normalization_trace_audit["supports_default_body_potential_rescale"].astype(bool).any()
            )
            self.assertFalse(
                body_potential_normalization_trace_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                body_potential_normalization_trace_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(phi_phi_n_kernel_normalization_trace_audit), 0)
            self.assertEqual(len(phi_phi_n_kernel_normalization_trace_summary), 1)
            for column in [
                "trace_item",
                "a1_source",
                "code_source",
                "supports_default_kernel_normalization_change",
                "blocks_default_kernel_normalization_change",
                "diagnostic_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, phi_phi_n_kernel_normalization_trace_audit.columns)
            for column in [
                "trace_item_count",
                "blocking_trace_count",
                "supporting_default_normalization_change_count",
                "current_inner_a_scale_unique",
                "current_inner_b_scale_unique",
                "current_inner_diagonal_sign_unique",
                "pi_kernel_supporting_trace_count",
                "default_promotable_conversion_count",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, phi_phi_n_kernel_normalization_trace_summary.columns)
            self.assertFalse(
                phi_phi_n_kernel_normalization_trace_audit[
                    "supports_default_kernel_normalization_change"
                ].astype(bool).any()
            )
            self.assertFalse(
                phi_phi_n_kernel_normalization_trace_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                phi_phi_n_kernel_normalization_trace_summary["candidate_default_gate_eligible"]
                .astype(bool)
                .any()
            )
            self.assertGreater(len(shared_body_potential_scale_audit), 0)
            self.assertGreater(len(shared_body_potential_scale_summary), 0)
            for column in [
                "scale_candidate",
                "source_group",
                "coefficient",
                "projected_value",
                "projected_gate_error_ratio",
                "projected_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, shared_body_potential_scale_audit.columns)
            for column in [
                "scale_candidate",
                "total_pass_count",
                "time_pressure_pass_count",
                "zero_m3_pass_count",
                "max_projected_gate_error_ratio",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, shared_body_potential_scale_summary.columns)
            self.assertIn("one_over_pi_squared", set(shared_body_potential_scale_summary["scale_candidate"]))
            self.assertIn("time_pressure", set(shared_body_potential_scale_audit["source_group"]))
            if pd.to_numeric(
                shared_body_potential_scale_summary["zero_m3_row_count"],
                errors="coerce",
            ).fillna(0).gt(0).any():
                self.assertIn("zero_m3_mapped_conservative", set(shared_body_potential_scale_audit["source_group"]))
            self.assertFalse(shared_body_potential_scale_audit["candidate_default_gate_eligible"].astype(bool).any())
            self.assertFalse(shared_body_potential_scale_summary["candidate_default_gate_eligible"].astype(bool).any())
            self.assertGreater(len(free_surface_longitudinal_staggering_audit), 0)
            self.assertEqual(len(free_surface_longitudinal_staggering_summary), 1)
            for column in [
                "coefficient",
                "candidate_name",
                "a1_staggering_role",
                "time_step_scale",
                "free_surface_substeps_per_station",
                "gate_error_ratio",
                "formula_trace_status",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, free_surface_longitudinal_staggering_audit.columns)
            for column in [
                "row_count",
                "a1_half_step_pass_count",
                "a1_two_substeps_pass_count",
                "no_marching_pass_count",
                "a1_half_step_a33_gate_error_ratio",
                "a1_half_step_a53_gate_error_ratio",
                "a1_two_substeps_a33_gate_error_ratio",
                "a1_two_substeps_a53_gate_error_ratio",
                "diagnostic_conclusion",
                "candidate_default_gate_eligible",
            ]:
                self.assertIn(column, free_surface_longitudinal_staggering_summary.columns)
            self.assertFalse(
                free_surface_longitudinal_staggering_audit["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertFalse(
                free_surface_longitudinal_staggering_summary["candidate_default_gate_eligible"].astype(bool).any()
            )
            self.assertGreater(len(rhs_source_detail), 0)
            self.assertGreater(len(rhs_source_summary), 0)
            for column in [
                "coefficient",
                "dominant_source_by_median_body_potential_ratio",
                "source_median_body_potential_ratios",
                "source_median_rhs_ratios",
                "source_reconstruction_status",
                "gate_role",
            ]:
                self.assertIn(column, rhs_source_summary.columns)
            self.assertTrue(rhs_source_summary["source_reconstruction_status"].astype(str).eq("PASS").all())
            self.assertGreater(len(inner_state_detail), 0)
            self.assertGreater(len(inner_state_summary), 0)
            for column in [
                "coefficient",
                "state_reconstruction_status",
                "max_update_relative_residual",
                "max_transfer_relative_residual",
                "peak_potential_after_x_over_l",
                "update_kind_counts",
                "gate_role",
            ]:
                self.assertIn(column, inner_state_summary.columns)
            self.assertTrue(inner_state_summary["state_reconstruction_status"].astype(str).eq("PASS").all())
            gate1_report = tmp_path / "out" / "ma2005_wigley_iii_coefficients_gate1_failure_report.md"
            self.assertTrue(gate1_report.exists())
            self.assertIn("Gate 1 Failure Audit", gate1_report.read_text(encoding="utf-8"))
            info = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_pressure_sign_candidate_summary")]
            self.assertEqual(info["status"].iloc[0], "INFO")
            force_route_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_force_assembly_route_candidate_summary")
            ]
            self.assertEqual(force_route_info["status"].iloc[0], "INFO")
            eq30_balance_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary")
            ]
            self.assertEqual(eq30_balance_info["status"].iloc[0], "INFO")
            eq30_scale_fit_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_eq30_component_scale_fit_summary")
            ]
            self.assertEqual(eq30_scale_fit_info["status"].iloc[0], "INFO")
            a1_discretization_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_a1_discretization_requirement_summary")
            ]
            self.assertEqual(a1_discretization_info["status"].iloc[0], "INFO")
            a1_history_convolution_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_a1_history_convolution_requirement_summary")
            ]
            self.assertEqual(a1_history_convolution_info["status"].iloc[0], "INFO")
            ab_mapping_normalization_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_ab_mapping_normalization_exclusion_summary")
            ]
            self.assertEqual(ab_mapping_normalization_info["status"].iloc[0], "INFO")
            coefficient_family_scale_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary")
            ]
            self.assertEqual(coefficient_family_scale_info["status"].iloc[0], "INFO")
            eq31_eq32_forward_identity_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary")
            ]
            self.assertEqual(eq31_eq32_forward_identity_info["status"].iloc[0], "INFO")
            complex_forward_identity_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_complex_forward_identity_summary")
            ]
            self.assertEqual(complex_forward_identity_info["status"].iloc[0], "INFO")
            projection_derivative_balance_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_projection_derivative_balance_summary")
            ]
            self.assertEqual(projection_derivative_balance_info["status"].iloc[0], "INFO")
            projection_transport_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_projection_transport_summary")
            ]
            self.assertEqual(projection_transport_info["status"].iloc[0], "INFO")
            geometry_transport_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_geometry_transport_balance_summary")
            ]
            self.assertEqual(geometry_transport_info["status"].iloc[0], "INFO")
            station_geometry_transport_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_station_geometry_transport_closure_summary"
                )
            ]
            if not station_geometry_transport_info.empty:
                self.assertEqual(station_geometry_transport_info["status"].iloc[0], "INFO")
            fixed_control_surface_transport_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_fixed_control_surface_transport_gap_summary"
                )
            ]
            if not fixed_control_surface_transport_info.empty:
                self.assertEqual(fixed_control_surface_transport_info["status"].iloc[0], "INFO")
            zero_m3_geometry_transport_blocker_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_zero_m3_geometry_transport_blocker_summary"
                )
            ]
            if not zero_m3_geometry_transport_blocker_info.empty:
                self.assertEqual(zero_m3_geometry_transport_blocker_info["status"].iloc[0], "INFO")
            interior_mi_transport_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_interior_mi_transport_consistency_summary"
                )
            ]
            if not interior_mi_transport_info.empty:
                self.assertEqual(interior_mi_transport_info["status"].iloc[0], "INFO")
            row_measure_transport_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_row_measure_transport_summary")
            ]
            if not row_measure_transport_info.empty:
                self.assertEqual(row_measure_transport_info["status"].iloc[0], "INFO")
            row_measure_transport_direction_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_summary"
                )
            ]
            if not row_measure_transport_direction_info.empty:
                self.assertEqual(row_measure_transport_direction_info["status"].iloc[0], "INFO")
            row_measure_mapping_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_overview")
            ]
            if not row_measure_mapping_info.empty:
                self.assertEqual(row_measure_mapping_info["status"].iloc[0], "INFO")
            eq30_component_contribution_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_eq30_component_contribution_summary")
            ]
            self.assertEqual(eq30_component_contribution_info["status"].iloc[0], "INFO")
            heave_pressure_radiation_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_heave_pressure_radiation_check")
            ]
            self.assertEqual(heave_pressure_radiation_info["status"].iloc[0], "INFO")
            station_mapping_gradient_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_station_mapping_gradient_summary")
            ]
            self.assertEqual(station_mapping_gradient_info["status"].iloc[0], "INFO")
            station_marching_direction_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_station_marching_direction_summary")
            ]
            self.assertEqual(station_marching_direction_info["status"].iloc[0], "INFO")
            aft_terminal_end_closure_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_aft_terminal_end_closure_summary")
            ]
            self.assertEqual(aft_terminal_end_closure_info["status"].iloc[0], "INFO")
            stokes_end_lever_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_stokes_end_lever_consistency_summary")
            ]
            self.assertEqual(stokes_end_lever_info["status"].iloc[0], "INFO")
            station_forward_identity_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_station_forward_identity_summary")
            ]
            self.assertEqual(station_forward_identity_info["status"].iloc[0], "INFO")
            gate1_failure_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_gate1_failure_audit")
            ]
            self.assertEqual(gate1_failure_info["status"].iloc[0], "INFO")
            gate1_remaining_blocker_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_gate1_remaining_blocker_summary")
            ]
            self.assertEqual(gate1_remaining_blocker_info["status"].iloc[0], "INFO")
            literature_traceability_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_literature_traceability_gap_summary")
            ]
            self.assertEqual(literature_traceability_info["status"].iloc[0], "INFO")
            journee_table_reference_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_journee_table_reference_summary")
            ]
            self.assertEqual(journee_table_reference_info["status"].iloc[0], "INFO")
            gate1_reference_trace_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_gate1_reference_trace_summary")
            ]
            self.assertEqual(gate1_reference_trace_info["status"].iloc[0], "INFO")
            a1_frequency_ladder_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_a1_frequency_ladder_summary")
            ]
            self.assertEqual(a1_frequency_ladder_info["status"].iloc[0], "INFO")
            journee_frequency_gate_probe_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_journee_frequency_gate_probe_summary")
            ]
            self.assertEqual(journee_frequency_gate_probe_info["status"].iloc[0], "INFO")
            reference_pairing_policy_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_reference_pairing_policy_summary")
            ]
            self.assertEqual(reference_pairing_policy_info["status"].iloc[0], "INFO")
            journee_coefficient_frequency_trend_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_journee_coefficient_frequency_trend_summary")
            ]
            self.assertEqual(journee_coefficient_frequency_trend_info["status"].iloc[0], "INFO")
            journee_component_frequency_trend_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_journee_component_frequency_trend_summary")
            ]
            self.assertEqual(journee_component_frequency_trend_info["status"].iloc[0], "INFO")
            body_potential_frequency_entry_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_body_potential_frequency_entry_summary")
            ]
            self.assertEqual(body_potential_frequency_entry_info["status"].iloc[0], "INFO")
            journee_complex_scale_phase_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_journee_complex_scale_phase_summary")
            ]
            self.assertEqual(journee_complex_scale_phase_info["status"].iloc[0], "INFO")
            coefficient_conversion_chain_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_coefficient_conversion_chain_summary")
            ]
            self.assertEqual(coefficient_conversion_chain_info["status"].iloc[0], "INFO")
            body_condition_unit_chain_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_body_condition_unit_chain_summary")
            ]
            self.assertEqual(body_condition_unit_chain_info["status"].iloc[0], "INFO")
            time_pressure_scale_origin_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_time_pressure_scale_origin_summary")
            ]
            self.assertEqual(time_pressure_scale_origin_info["status"].iloc[0], "INFO")
            time_pressure_formula_unit_chain_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_time_pressure_formula_unit_chain_summary")
            ]
            self.assertEqual(time_pressure_formula_unit_chain_info["status"].iloc[0], "INFO")
            body_potential_normalization_trace_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_body_potential_normalization_trace_summary")
            ]
            self.assertEqual(
                body_potential_normalization_trace_info["status"].iloc[0],
                body_potential_normalization_trace_summary["path_diagnostic_status"].iloc[0],
            )
            phi_phi_n_kernel_normalization_trace_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_phi_phi_n_kernel_normalization_trace_summary"
                )
            ]
            self.assertEqual(phi_phi_n_kernel_normalization_trace_info["status"].iloc[0], "INFO")
            shared_body_potential_scale_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_shared_body_potential_scale_summary")
            ]
            self.assertEqual(shared_body_potential_scale_info["status"].iloc[0], "INFO")
            free_surface_longitudinal_staggering_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_free_surface_longitudinal_staggering_summary"
                )
            ]
            self.assertEqual(free_surface_longitudinal_staggering_info["status"].iloc[0], "INFO")
            body_potential_source_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_matched_body_potential_source_audit_summary")
            ]
            self.assertEqual(body_potential_source_info["status"].iloc[0], "INFO")
            rhs_source_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_rhs_source_decomposition_summary")
            ]
            self.assertEqual(rhs_source_info["status"].iloc[0], "INFO")
            inner_state_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_inner_free_surface_state_marching_summary")
            ]
            self.assertEqual(inner_state_info["status"].iloc[0], "INFO")
            heave_time_station_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_summary")
            ]
            self.assertEqual(heave_time_station_info["status"].iloc[0], "INFO")
            heave_free_normal_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_summary")
            ]
            self.assertEqual(heave_free_normal_info["status"].iloc[0], "INFO")
            pressure_gradient_spike_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_summary")
            ]
            self.assertEqual(pressure_gradient_spike_info["status"].iloc[0], "INFO")
            transfer_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_matched_station_transfer_path_summary")
            ]
            self.assertEqual(transfer_info["status"].iloc[0], "INFO")
            aft_pair_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_matched_aft_pair_boundary_rhs_summary")
            ]
            self.assertEqual(aft_pair_info["status"].iloc[0], "INFO")
            free_rhs_block_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_matched_inner_free_surface_rhs_block_summary"
                )
            ]
            self.assertEqual(free_rhs_block_info["status"].iloc[0], "INFO")
            free_self_candidate_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_inner_free_surface_self_block_candidate_summary"
                )
            ]
            self.assertEqual(free_self_candidate_info["status"].iloc[0], "INFO")
            free_block_coupling_candidate_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_inner_free_surface_block_coupling_candidate_summary"
                )
            ]
            self.assertEqual(free_block_coupling_candidate_info["status"].iloc[0], "INFO")
            startup_ghost_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_startup_ghost_station_candidate_summary")
            ]
            self.assertEqual(startup_ghost_info["status"].iloc[0], "INFO")
            end_candidate_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_end_contour_term_candidate_summary")
            ]
            self.assertEqual(end_candidate_info["status"].iloc[0], "INFO")
            startup_gradient_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_summary")
            ]
            self.assertEqual(startup_gradient_info["status"].iloc[0], "INFO")
            pressure_gradient_stencil_exclusion_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary"
                )
            ]
            self.assertEqual(pressure_gradient_stencil_exclusion_info["status"].iloc[0], "INFO")
            startup_gradient_station_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_station_summary"
                )
            ]
            self.assertEqual(startup_gradient_station_info["status"].iloc[0], "INFO")
            pitch_split_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_summary")
            ]
            self.assertEqual(pitch_split_info["status"].iloc[0], "INFO")
            free_surface_marching_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary")
            ]
            self.assertEqual(free_surface_marching_info["status"].iloc[0], "INFO")
            local_time_free_surface_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_local_time_free_surface_cross_probe_summary"
                )
            ]
            self.assertEqual(local_time_free_surface_info["status"].iloc[0], "INFO")
            free_surface_update_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_free_surface_update_formula_candidate_summary")
            ]
            self.assertEqual(free_surface_update_info["status"].iloc[0], "INFO")
            free_surface_normal_source_info = summary[
                summary["metric"].eq(
                    "ma2005_wigley_iii_coefficients_free_surface_normal_derivative_source_candidate_summary"
                )
            ]
            self.assertEqual(free_surface_normal_source_info["status"].iloc[0], "INFO")
            end_pressure_info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_matched_end_pressure_closure_summary")
            ]
            self.assertEqual(end_pressure_info["status"].iloc[0], "INFO")
            self.assertLess(abs(float(comparison["matched_force_closure_residual_value"].iloc[0])), 1e-9)

    def test_ma2005_matched_bie_pitch_coordinate_audit_for_pitch_related_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A35",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="matched_bie_provider",
                bem_free_surface_panel_count_per_side=4,
                bem_body_panel_count=8,
            )["computed_value"]
            pd.DataFrame([{**base.to_dict(), "reference_value": expected}]).to_csv(
                data_dir / "wigley_iii_coefficients_digitized.csv",
                index=False,
            )
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="matched_bie_provider",
                ma_bem_free_surface_panel_count_per_side=4,
                ma_bem_body_panel_count=8,
            )
            detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_row_coordinate_audit_detail.csv"
            )
            audit_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_row_coordinate_audit_summary.csv"
            )
            pitch_split_detail = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_detail.csv"
            )
            pitch_split_summary = pd.read_csv(
                tmp_path / "out" / "ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_summary.csv"
            )
            self.assertGreater(len(detail), 1)
            self.assertEqual(len(audit_summary), 1)
            self.assertEqual(len(pitch_split_detail), 4)
            self.assertEqual(len(pitch_split_summary), 4)
            self.assertTrue(pitch_split_detail["candidate_affects_pitch_radiation_column"].astype(bool).all())
            self.assertTrue(pitch_split_detail["candidate_recomputed_matched_bie"].astype(bool).all())
            self.assertEqual(
                set(pitch_split_detail["candidate_name"]),
                {
                    "current_combined",
                    "pitch_oscillation_only",
                    "pitch_forward_only",
                    "pitch_body_condition_zero",
                },
            )
            current = pitch_split_detail[pitch_split_detail["candidate_name"].eq("current_combined")].iloc[0]
            self.assertAlmostEqual(float(current["computed_value"]), float(expected))
            self.assertEqual(int(pitch_split_summary["affected_pitch_radiation_column_count"].iloc[0]), 1)
            for column in [
                "pitch_base_lever_arm_m",
                "pitch_radiation_lever_arm_m",
                "pitch_moment_lever_arm_m",
                "pitch_moment_to_radiation_lever_ratio",
                "pitch_body_condition_oscillation_norm",
                "pitch_body_condition_forward_speed_norm",
                "pitch_body_condition_forward_to_oscillation_norm_ratio",
                "pressure_gradient_density_value_per_m",
            ]:
                self.assertIn(column, detail.columns)
                self.assertTrue(pd.to_numeric(detail[column], errors="coerce").notna().any())
            for column in [
                "max_forward_to_oscillation_norm_ratio",
                "dominant_pressure_gradient_station_index",
                "dominant_pressure_gradient_x_over_l",
                "moment_radiation_lever_ratio_min",
                "moment_radiation_lever_ratio_max",
            ]:
                self.assertIn(column, audit_summary.columns)
                self.assertTrue(math.isfinite(float(audit_summary[column].iloc[0])))
            info = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_pitch_row_coordinate_audit_summary")
            ]
            self.assertEqual(info["status"].iloc[0], "INFO")

    def test_ma2005_digitized_dataset_can_use_pdstrip_style_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "synthetic",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="pdstrip_style",
                bem_free_surface_panel_count_per_side=10,
                bem_body_panel_count=12,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="pdstrip_style",
                ma_bem_free_surface_panel_count_per_side=10,
                ma_bem_body_panel_count=12,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "pdstrip_style")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "experimental_pdstrip_style_section_solver_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_forward_speed_2p5d_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "B35",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="strip_2p5d_forward",
                bem_free_surface_panel_count_per_side=8,
                bem_body_panel_count=12,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="strip_2p5d_forward",
                ma_bem_free_surface_panel_count_per_side=8,
                ma_bem_body_panel_count=12,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "strip_2p5d_forward")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "experimental_pdstrip_like_forward_speed_assembly_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_pdstrip_step_forward_speed_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "B35",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="strip_2p5d_pdstrip_step",
                bem_free_surface_panel_count_per_side=8,
                bem_body_panel_count=12,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="strip_2p5d_pdstrip_step",
                ma_bem_free_surface_panel_count_per_side=8,
                ma_bem_body_panel_count=12,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "strip_2p5d_pdstrip_step")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "experimental_pdstrip_step_forward_speed_assembly_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_hybrid_forward_coupling_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A53",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="hybrid_forward_coupling",
                bem_free_surface_panel_count_per_side=8,
                bem_body_panel_count=12,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="hybrid_forward_coupling",
                ma_bem_free_surface_panel_count_per_side=8,
                ma_bem_body_panel_count=12,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "hybrid_forward_coupling")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "diagnostic_prototype_diagonal_forward_coupling_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_hybrid_pressure_damping_coupling_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 2.5,
                    "coefficient": "B35",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            expected = _ma2005_computed_coefficient(
                base,
                hydro_model="hybrid_pressure_damping_coupling",
                bem_free_surface_panel_count_per_side=3,
                bem_body_panel_count=8,
            )["computed_value"]
            data = pd.DataFrame([{**base.to_dict(), "reference_value": expected}])
            data.to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            summary = validate_goal_gap_audit(
                tmp_path / "out",
                reference_root,
                ma_hydro_model="hybrid_pressure_damping_coupling",
                ma_bem_free_surface_panel_count_per_side=3,
                ma_bem_body_panel_count=8,
            )
            ma_rows = summary[summary["benchmark"].eq("ma2005_wigley_iii_coefficients")]
            self.assertIn("PASS", set(ma_rows["status"]))
            comparison = pd.read_csv(tmp_path / "out" / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(comparison["hydro_model"].iloc[0], "hybrid_pressure_damping_coupling")
            self.assertEqual(
                comparison["solver_status"].iloc[0],
                "diagnostic_prototype_diagonal_forward_added_pressure_damping_coupling_not_validated",
            )

    def test_ma2005_digitized_dataset_can_use_pressure_transfer_forward_models(self):
        base = pd.Series(
            {
                "hull": "wigley_iii",
                "speed_case": "Fn0.4",
                "omega_e_sqrt_l_over_g": 1.0,
                "coefficient": "A35",
                "reference_value": 0.0,
                "normalization": "auto",
                "length_m": 1.0,
                "beam_m": 0.1,
                "draft_m": 0.0625,
                "station_count": 5,
            }
        )
        continuous = _ma2005_computed_coefficient(
            base,
            hydro_model="pressure_transfer_forward",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=8,
        )
        step = _ma2005_computed_coefficient(
            base,
            hydro_model="pressure_transfer_pdstrip_step",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=8,
        )
        damping_continuous = _ma2005_computed_coefficient(
            base,
            hydro_model="pressure_transfer_pdstrip_damping_forward",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=8,
        )
        damping_step = _ma2005_computed_coefficient(
            base,
            hydro_model="pressure_transfer_pdstrip_damping_pdstrip_step",
            bem_free_surface_panel_count_per_side=3,
            bem_body_panel_count=8,
        )
        self.assertEqual(continuous["hydro_model"], "pressure_transfer_forward")
        self.assertEqual(step["hydro_model"], "pressure_transfer_pdstrip_step")
        self.assertEqual(damping_continuous["hydro_model"], "pressure_transfer_pdstrip_damping_forward")
        self.assertEqual(damping_step["hydro_model"], "pressure_transfer_pdstrip_damping_pdstrip_step")
        self.assertEqual(
            continuous["solver_status"],
            "experimental_pressure_transfer_forward_speed_assembly_not_validated",
        )
        self.assertEqual(
            step["solver_status"],
            "experimental_pressure_transfer_pdstrip_step_forward_speed_assembly_not_validated",
        )
        self.assertEqual(
            damping_continuous["solver_status"],
            "diagnostic_pressure_transfer_added_pdstrip_style_damping_forward_speed_assembly_not_validated",
        )
        self.assertEqual(
            damping_step["solver_status"],
            "diagnostic_pressure_transfer_added_pdstrip_style_damping_pdstrip_step_forward_speed_assembly_not_validated",
        )
        self.assertTrue(math.isfinite(float(continuous["raw_value"])))
        self.assertTrue(math.isfinite(float(step["raw_value"])))
        self.assertTrue(math.isfinite(float(damping_continuous["raw_value"])))
        self.assertTrue(math.isfinite(float(damping_step["raw_value"])))

    def test_ma2005_digitized_dataset_can_use_external_pdstrip_sections_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            parsed = self._synthetic_pdstrip_sectionresults(tmp_path / "sectionresults", station_count=3)
            fake_result = SimpleNamespace(status="PASS", parsed=parsed, message="mocked external PDSTRIP")
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 3,
                }
            )
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections", return_value=fake_result):
                calc = _ma2005_computed_coefficient(base, hydro_model="external_pdstrip_sections")
            self.assertEqual(calc["hydro_model"], "external_pdstrip_sections")
            self.assertEqual(
                calc["solver_status"],
                "external_pdstrip_section_radiation_zero_speed_assembly_not_validated",
            )
            self.assertGreater(float(calc["raw_value"]), 0.0)

    def test_ma2005_external_pdstrip_sections_can_reuse_persistent_sectionresults_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_dir = tmp_path / "pdstrip_cache"
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 3,
                }
            )
            work_dir = _ma2005_external_pdstrip_cache_work_dir(cache_dir, base, 1025.0, 9.80665)
            work_dir.mkdir(parents=True)
            self._synthetic_pdstrip_sectionresults(work_dir / "sectionresults", station_count=3)
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections") as runner:
                calc = _ma2005_computed_coefficient(
                    base,
                    hydro_model="external_pdstrip_sections",
                    external_pdstrip_cache_dir=cache_dir,
                )
            runner.assert_not_called()
            self.assertEqual(calc["hydro_model"], "external_pdstrip_sections")
            self.assertGreater(float(calc["raw_value"]), 0.0)

    def test_ma2005_digitized_dataset_can_use_external_pdstrip_forward_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            parsed = self._synthetic_pdstrip_sectionresults(tmp_path / "sectionresults", station_count=3)
            fake_result = SimpleNamespace(status="PASS", parsed=parsed, message="mocked external PDSTRIP")
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "B35",
                    "reference_value": 0.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 3,
                }
            )
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections", return_value=fake_result):
                continuous = _ma2005_computed_coefficient(base, hydro_model="external_pdstrip_forward")
                step = _ma2005_computed_coefficient(base, hydro_model="external_pdstrip_pdstrip_step")
            self.assertEqual(continuous["hydro_model"], "external_pdstrip_forward")
            self.assertEqual(
                continuous["solver_status"],
                "external_pdstrip_section_forward_speed_assembly_not_validated",
            )
            self.assertEqual(step["hydro_model"], "external_pdstrip_pdstrip_step")
            self.assertEqual(
                step["solver_status"],
                "external_pdstrip_section_pdstrip_step_forward_speed_assembly_not_validated",
            )
            self.assertTrue(math.isfinite(float(continuous["raw_value"])))
            self.assertTrue(math.isfinite(float(step["raw_value"])))

    def test_ma2005_hydro_model_diagnostics_are_optional_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "synthetic",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            pd.DataFrame([base.to_dict()]).to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            out_dir = tmp_path / "out"
            parsed = self._synthetic_pdstrip_sectionresults(tmp_path / "sectionresults", station_count=5)
            fake_result = SimpleNamespace(status="PASS", parsed=parsed, message="mocked external PDSTRIP")
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections", return_value=fake_result):
                summary = validate_goal_gap_audit(
                    out_dir,
                    reference_root,
                    ma_compare_hydro_models=True,
                    ma_bem_free_surface_panel_count_per_side=3,
                    ma_bem_body_panel_count=8,
                )
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_diagnostics.csv").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_status.csv").exists())
            self.assertTrue(
                (out_dir / "ma2005_wigley_iii_coefficients_hydro_model_status_by_coefficient.csv").exists()
            )
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_gap_summary.csv").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_blocker_ranking.csv").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_conflict_summary.csv").exists())
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_hydro_model_scale_audit.csv").exists())
            self.assertTrue(
                (out_dir / "ma2005_wigley_iii_coefficients_hydro_model_scale_audit_summary.csv").exists()
            )
            self.assertTrue(
                (out_dir / "ma2005_wigley_iii_coefficients_coefficient_frequency_shape_audit.csv").exists()
            )
            self.assertTrue(
                (out_dir / "ma2005_wigley_iii_coefficients_coefficient_frequency_shape_summary.csv").exists()
            )
            self.assertTrue((out_dir / "ma2005_wigley_iii_coefficients_normalization_sensitivity.csv").exists())
            self.assertTrue(
                (out_dir / "ma2005_wigley_iii_coefficients_normalization_sensitivity_summary.csv").exists()
            )
            diagnostics = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_diagnostics.csv")
            self.assertIn("normalization_scale", diagnostics.columns)
            self.assertIn("displacement_volume_m3", diagnostics.columns)
            self.assertIn("ma2005_eq34_normalization_formula", diagnostics.columns)
            self.assertIn("ma2005_candidate_length_power_1_gate_error_ratio", diagnostics.columns)
            self.assertTrue(diagnostics["ma2005_eq34_normalization_formula"].astype(str).str.len().gt(0).all())
            self.assertEqual(
                set(diagnostics["hydro_model"]),
                {
                    "matched_bie_provider",
                    "prototype",
                    "section_bem",
                    "pdstrip_style",
                    "strip_2p5d_forward",
                    "strip_2p5d_pdstrip_step",
                    "pressure_transfer_forward",
                    "pressure_transfer_pdstrip_step",
                    "pressure_transfer_pdstrip_damping_forward",
                    "pressure_transfer_pdstrip_damping_pdstrip_step",
                    "hybrid_forward_coupling",
                    "hybrid_pressure_damping_coupling",
                },
            )
            gap_summary = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_gap_summary.csv")
            self.assertIn("overall_best", set(gap_summary["summary_type"]))
            self.assertIn("coefficient_best", set(gap_summary["summary_type"]))
            self.assertIn("blocker_coefficients", gap_summary.columns)
            blocker_ranking = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_blocker_ranking.csv")
            self.assertIn("priority_rank", blocker_ranking.columns)
            self.assertIn("best_pressure_transfer_model", blocker_ranking.columns)
            self.assertIn("next_evidence_needed", blocker_ranking.columns)
            conflict_summary = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_conflict_summary.csv")
            self.assertIn("row_best_model_split", conflict_summary.columns)
            self.assertIn("row_best_model_trace", conflict_summary.columns)
            self.assertIn("single_model_full_pass_available", conflict_summary.columns)
            scale_audit = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_scale_audit.csv")
            self.assertIn("required_magnitude_multiplier", scale_audit.columns)
            self.assertIn("correction_direction", scale_audit.columns)
            scale_summary = pd.read_csv(
                out_dir / "ma2005_wigley_iii_coefficients_hydro_model_scale_audit_summary.csv"
            )
            self.assertIn("scale_audit_status", scale_summary.columns)
            self.assertIn("log_multiplier_slope_vs_omega_hat", scale_summary.columns)
            shape_audit = pd.read_csv(
                out_dir / "ma2005_wigley_iii_coefficients_coefficient_frequency_shape_audit.csv"
            )
            self.assertIn("best_fit_scaled_computed_value", shape_audit.columns)
            self.assertIn("shape_status", shape_audit.columns)
            shape_summary = pd.read_csv(
                out_dir / "ma2005_wigley_iii_coefficients_coefficient_frequency_shape_summary.csv"
            )
            self.assertIn("signed_shape_correlation", shape_summary.columns)
            self.assertIn("best_fit_normalized_shape_rmse", shape_summary.columns)
            self.assertIn("computed_minus_reference_log_slope", shape_summary.columns)
            normalization_audit = pd.read_csv(
                out_dir / "ma2005_wigley_iii_coefficients_normalization_sensitivity.csv"
            )
            self.assertIn("normalization_candidate", normalization_audit.columns)
            self.assertIn("ma2005_displacement_volume", set(normalization_audit["normalization_candidate"]))
            normalization_summary = pd.read_csv(
                out_dir / "ma2005_wigley_iii_coefficients_normalization_sensitivity_summary.csv"
            )
            self.assertIn("diagnosis", normalization_summary.columns)
            self.assertIn("abs_candidate_over_reference_spread", normalization_summary.columns)
            info_rows = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_diagnostics")]
            self.assertEqual(info_rows["status"].iloc[0], "INFO")
            gap_info_rows = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_gap_summary")]
            self.assertEqual(gap_info_rows["status"].iloc[0], "INFO")
            ranking_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_blocker_ranking")
            ]
            self.assertEqual(ranking_info_rows["status"].iloc[0], "INFO")
            conflict_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_conflict_summary")
            ]
            self.assertEqual(conflict_info_rows["status"].iloc[0], "INFO")
            scale_info_rows = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_scale_audit")]
            self.assertEqual(scale_info_rows["status"].iloc[0], "INFO")
            shape_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_coefficient_frequency_shape_audit")
            ]
            self.assertEqual(shape_info_rows["status"].iloc[0], "INFO")
            normalization_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_normalization_sensitivity")
            ]
            self.assertEqual(normalization_info_rows["status"].iloc[0], "INFO")

    def test_ma2005_hydro_model_diagnostics_can_filter_slow_external_pdstrip_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            rows = [
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 2.0,
                    "coefficient": "B33",
                    "reference_value": 1.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                },
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 2.5,
                    "coefficient": "B35",
                    "reference_value": 0.1,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                },
            ]
            pd.DataFrame(rows).to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            out_dir = tmp_path / "out"
            parsed = self._synthetic_pdstrip_sectionresults(tmp_path / "sectionresults", station_count=5)
            fake_result = SimpleNamespace(status="PASS", parsed=parsed, message="mocked external PDSTRIP")
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections", return_value=fake_result):
                summary = validate_goal_gap_audit(
                    out_dir,
                    reference_root,
                    ma_compare_hydro_models=True,
                    ma_compare_external_pdstrip=True,
                    ma_compare_row_limit=1,
                    ma_compare_coefficients=("A33", "B33"),
                    ma_bem_free_surface_panel_count_per_side=3,
                    ma_bem_body_panel_count=8,
            )
            diagnostics = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_hydro_model_diagnostics.csv")
            self.assertEqual(len(diagnostics), 15)
            self.assertEqual(set(diagnostics["coefficient"]), {"A33"})
            self.assertTrue(
                {
                    "pressure_transfer_forward",
                    "pressure_transfer_pdstrip_step",
                    "pressure_transfer_pdstrip_damping_forward",
                    "pressure_transfer_pdstrip_damping_pdstrip_step",
                    "hybrid_pressure_damping_coupling",
                    "external_pdstrip_sections",
                    "external_pdstrip_forward",
                    "external_pdstrip_pdstrip_step",
                }.issubset(set(diagnostics["hydro_model"]))
            )
            comparison = pd.read_csv(out_dir / "ma2005_wigley_iii_coefficients_comparison.csv")
            self.assertEqual(len(comparison), 3)
            info = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_hydro_model_diagnostics")].iloc[0]
            self.assertIn("row_limit=1", info["note"])
            self.assertIn("coefficients=A33,B33", info["note"])

    def test_ma2005_external_section_profiles_are_optional_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 1.0,
                    "coefficient": "A33",
                    "reference_value": 1.0,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            pd.DataFrame([base.to_dict()]).to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            out_dir = tmp_path / "out"
            parsed = self._synthetic_pdstrip_sectionresults(tmp_path / "sectionresults", station_count=5)
            fake_result = SimpleNamespace(status="PASS", parsed=parsed, message="mocked external PDSTRIP")
            with mock.patch("planing_seakeeping.validation.run_pdstrip_station_hull_sections", return_value=fake_result):
                summary = validate_goal_gap_audit(
                    out_dir,
                    reference_root,
                    ma_compare_hydro_models=True,
                    ma_compare_external_pdstrip=True,
                    ma_external_pdstrip_section_profiles=True,
                    ma_compare_row_limit=1,
                    ma_compare_coefficients=("A33",),
                    ma_bem_free_surface_panel_count_per_side=2,
                    ma_bem_body_panel_count=4,
                )
            profile_path = out_dir / "ma2005_wigley_iii_coefficients_external_section_profiles.csv"
            profile_summary_path = out_dir / "ma2005_wigley_iii_coefficients_external_section_profile_summary.csv"
            frequency_shape_path = out_dir / "ma2005_wigley_iii_coefficients_external_section_frequency_shape_summary.csv"
            self.assertTrue(profile_path.exists())
            self.assertTrue(profile_summary_path.exists())
            self.assertTrue(frequency_shape_path.exists())
            profiles = pd.read_csv(profile_path)
            profile_summary = pd.read_csv(profile_summary_path)
            self.assertIn("external_added_mass_per_m", profiles.columns)
            self.assertIn("active_only_strip_weight_m", profiles.columns)
            self.assertIn("endpoint_closure_weight_delta_m", profiles.columns)
            self.assertIn("pdstrip_style_added_mass_per_m", profiles.columns)
            self.assertIn("pdstrip_style_a33_contribution", profiles.columns)
            self.assertIn("collocation_a33_contribution", profiles.columns)
            self.assertIn("external_to_pdstrip_style_added_ratio", profiles.columns)
            self.assertEqual(len(profiles), 5)
            self.assertIn("external_a33_integral", profile_summary.columns)
            self.assertIn("external_b35_integral", profile_summary.columns)
            self.assertIn("pdstrip_style_b55_integral", profile_summary.columns)
            self.assertIn("endpoint_closure_delta_ratio_vs_active", profile_summary.columns)
            frequency_shape = pd.read_csv(frequency_shape_path)
            self.assertIn("external_b33_log_abs_slope", frequency_shape.columns)
            self.assertIn("external_to_pdstrip_style_b33_ratio_spread", frequency_shape.columns)
            self.assertIn("shape_status", frequency_shape.columns)
            info = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_external_section_profiles")]
            self.assertEqual(info["status"].iloc[0], "INFO")

    def test_ma2005_panel_convergence_is_optional_diagnostic_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            row = {
                "hull": "wigley_iii",
                "speed_case": "Fn0.4",
                "omega_e_sqrt_l_over_g": 2.5,
                "coefficient": "B53",
                "reference_value": -0.08,
                "normalization": "auto",
                "length_m": 1.0,
                "beam_m": 0.1,
                "draft_m": 0.0625,
                "station_count": 3,
            }
            pd.DataFrame([row]).to_csv(data_dir / "wigley_iii_coefficients_digitized.csv", index=False)
            out_dir = tmp_path / "out"
            summary = validate_goal_gap_audit(
                out_dir,
                reference_root,
                ma_panel_convergence=True,
                ma_compare_row_limit=1,
                ma_compare_coefficients=("B53",),
                ma_bem_free_surface_panel_count_per_side=2,
                ma_bem_body_panel_count=4,
            )
            convergence_path = out_dir / "ma2005_wigley_iii_coefficients_panel_convergence.csv"
            convergence_summary_path = out_dir / "ma2005_wigley_iii_coefficients_panel_convergence_summary.csv"
            self.assertTrue(convergence_path.exists())
            self.assertTrue(convergence_summary_path.exists())
            convergence = pd.read_csv(convergence_path)
            self.assertEqual(set(convergence["hydro_model"]), {"pressure_transfer_forward", "pressure_transfer_pdstrip_step"})
            self.assertEqual(set(convergence["refinement_label"]), {"base", "medium", "fine"})
            convergence_summary = pd.read_csv(convergence_summary_path)
            self.assertIn("max_adjacent_rel_change", convergence_summary.columns)
            self.assertIn("panel_change_to_reference_gap_ratio", convergence_summary.columns)
            self.assertIn("convergence_status", convergence_summary.columns)
            self.assertTrue(_ma2005_panel_convergence_report_lines(out_dir))
            info = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_panel_convergence")]
            self.assertEqual(info["status"].iloc[0], "INFO")

    def test_ma2005_coupling_variant_sweep_is_optional_diagnostic_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "ma2005"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "hull": "wigley_iii",
                    "speed_case": "Fn0.4",
                    "omega_e_sqrt_l_over_g": 2.5,
                    "coefficient": "B35",
                    "reference_value": 0.13,
                    "normalization": "auto",
                    "length_m": 1.0,
                    "beam_m": 0.1,
                    "draft_m": 0.0625,
                    "station_count": 5,
                }
            )
            pitch_damping = base.copy()
            pitch_damping["coefficient"] = "B55"
            pitch_damping["reference_value"] = 0.02
            pd.DataFrame([base.to_dict(), pitch_damping.to_dict()]).to_csv(
                data_dir / "wigley_iii_coefficients_digitized.csv",
                index=False,
            )
            out_dir = tmp_path / "out"
            summary = validate_goal_gap_audit(
                out_dir,
                reference_root,
                ma_compare_hydro_models=True,
                ma_coupling_station_contributions=True,
                ma_bem_free_surface_panel_count_per_side=8,
                ma_bem_body_panel_count=12,
            )
            sweep_path = out_dir / "ma2005_wigley_iii_coefficients_coupling_variant_sweep.csv"
            status_path = out_dir / "ma2005_wigley_iii_coefficients_coupling_variant_status.csv"
            sign_audit_path = out_dir / "ma2005_wigley_iii_coefficients_pdstrip_step_sign_audit.csv"
            pitch_axis_path = out_dir / "ma2005_wigley_iii_coefficients_pitch_axis_sensitivity.csv"
            pitch_axis_summary_path = out_dir / "ma2005_wigley_iii_coefficients_pitch_axis_sensitivity_summary.csv"
            station_path = out_dir / "ma2005_wigley_iii_coefficients_coupling_station_contributions.csv"
            station_summary_path = out_dir / "ma2005_wigley_iii_coefficients_coupling_station_contribution_summary.csv"
            station_figure = out_dir / "figures" / "ma2005_wigley_iii_coefficients_coupling_station_contributions.png"
            self.assertTrue(sweep_path.exists())
            self.assertTrue(status_path.exists())
            self.assertTrue(sign_audit_path.exists())
            self.assertTrue(pitch_axis_path.exists())
            self.assertTrue(pitch_axis_summary_path.exists())
            self.assertTrue(station_path.exists())
            self.assertTrue(station_summary_path.exists())
            self.assertTrue(station_figure.exists())
            sweep = pd.read_csv(sweep_path)
            self.assertIn("current_transpose", set(sweep["variant"]))
            self.assertIn("gate_error_ratio", sweep.columns)
            sign_audit = pd.read_csv(sign_audit_path)
            self.assertIn("current_median_gate_error_ratio", sign_audit.columns)
            self.assertIn("accumulator_median_gate_error_ratio", sign_audit.columns)
            self.assertIn("current_sign_match_fraction", sign_audit.columns)
            self.assertIn("sign_audit_status", sign_audit.columns)
            self.assertIn("B35", set(sign_audit["coefficient"]))
            pitch_axis = pd.read_csv(pitch_axis_path)
            self.assertIn("pitch_axis_variant", pitch_axis.columns)
            self.assertIn("axis_offset_over_l", pitch_axis.columns)
            self.assertIn("raw_current_55", pitch_axis.columns)
            self.assertIn("B55", set(pitch_axis["coefficient"]))
            pitch_axis_summary = pd.read_csv(pitch_axis_summary_path)
            self.assertIn("improves_over_current_lcg", pitch_axis_summary.columns)
            self.assertIn("diagnosis", pitch_axis_summary.columns)
            station = pd.read_csv(station_path)
            self.assertIn("normalized_station_contribution", station.columns)
            self.assertIn("abs_fraction_of_source_total_abs", station.columns)
            self.assertIn("pressure_clipped", set(station["source"]))
            self.assertEqual({"B35", "B55"}, set(station["coefficient"]))
            station_summary = pd.read_csv(station_summary_path)
            self.assertIn("predicted_value", station_summary.columns)
            self.assertIn("required_magnitude_multiplier", station_summary.columns)
            self.assertIn("cancellation_ratio_abs_total_over_sum_abs", station_summary.columns)
            self.assertIn("abs_contribution_centroid_x_over_l", station_summary.columns)
            self.assertIn("pressure_clipped", set(station_summary["source"]))
            info_rows = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_coupling_variant_sweep")]
            self.assertEqual(info_rows["status"].iloc[0], "INFO")
            sign_info_rows = summary[summary["metric"].eq("ma2005_wigley_iii_coefficients_pdstrip_step_sign_audit")]
            self.assertEqual(sign_info_rows["status"].iloc[0], "INFO")
            pitch_axis_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_pitch_axis_sensitivity")
            ]
            self.assertEqual(pitch_axis_info_rows["status"].iloc[0], "INFO")
            station_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_coupling_station_contributions")
            ]
            self.assertEqual(station_info_rows["status"].iloc[0], "INFO")
            station_summary_info_rows = summary[
                summary["metric"].eq("ma2005_wigley_iii_coefficients_coupling_station_contribution_summary")
            ]
            self.assertEqual(station_summary_info_rows["status"].iloc[0], "INFO")

    def test_amplitude_dataset_is_compared_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "fridsma"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "case_id": "synthetic",
                    "fn_b": 3.0,
                    "wave_height_over_b": 0.02,
                    "lambda_over_l": 0.8,
                    "heave_rao_m_per_m": 0.0,
                    "pitch_rao_rad_per_m": 0.0,
                    "cg_accel_g": 0.0,
                    "bow_accel_g": 0.0,
                    "length_m": 6.5,
                    "beam_m": 1.0,
                    "deadrise_deg": 20.0,
                    "mass_over_rho_b3": 1.28,
                    "lcg_over_b": 2.13,
                    "vcg_over_b": 0.25,
                    "r55_over_b": 1.3,
                }
            )
            prediction = _amplitude_prediction(base)
            data = pd.DataFrame(
                [
                    {
                        **base.to_dict(),
                        "heave_rao_m_per_m": prediction["computed_heave_rao_m_per_m"],
                        "pitch_rao_rad_per_m": prediction["computed_pitch_rao_rad_per_m"],
                        "cg_accel_g": prediction["computed_cg_accel_g"],
                        "bow_accel_g": prediction["computed_bow_accel_g"],
                    }
                ]
            )
            data.to_csv(data_dir / "regular_wave_motion_digitized.csv", index=False)
            summary = validate_goal_gap_audit(tmp_path / "out", reference_root)
            amp_rows = summary[summary["benchmark"].eq("fridsma_regular_wave_amplitudes")]
            self.assertIn("PASS", set(amp_rows["status"]))
            self.assertTrue((tmp_path / "out" / "fridsma_regular_wave_amplitudes_comparison.csv").exists())
            self.assertTrue((tmp_path / "out" / "fridsma_regular_wave_amplitudes_residual_summary.csv").exists())
            self.assertTrue((tmp_path / "out" / "fridsma_regular_wave_amplitudes_shape_audit.csv").exists())
            self.assertTrue((tmp_path / "out" / "fridsma_regular_wave_amplitudes_shape_summary.csv").exists())
            self.assertTrue((tmp_path / "out" / "figures" / "fridsma_regular_wave_amplitudes_comparison.png").exists())
            comparison = pd.read_csv(tmp_path / "out" / "fridsma_regular_wave_amplitudes_comparison.csv")
            residual_summary = pd.read_csv(tmp_path / "out" / "fridsma_regular_wave_amplitudes_residual_summary.csv")
            shape_audit = pd.read_csv(tmp_path / "out" / "fridsma_regular_wave_amplitudes_shape_audit.csv")
            shape_summary = pd.read_csv(tmp_path / "out" / "fridsma_regular_wave_amplitudes_shape_summary.csv")
            self.assertIn("lambda_over_l", comparison.columns)
            self.assertIn("time_domain_value", comparison.columns)
            self.assertIn("time_domain_status", comparison.columns)
            self.assertIn("wavelength_band", residual_summary.columns)
            self.assertIn("dominant_bias", residual_summary.columns)
            self.assertIn("recommendation", residual_summary.columns)
            self.assertIn("prediction_model", shape_audit.columns)
            self.assertIn("best_fit_scaled_predicted_value", shape_audit.columns)
            self.assertIn("prediction_model", shape_summary.columns)
            self.assertIn("best_fit_normalized_shape_rmse", shape_summary.columns)
            self.assertIn("shape_status", shape_summary.columns)
            self.assertTrue(pd.to_numeric(comparison["time_domain_value"], errors="coerce").notna().all())
            figure_row = amp_rows[amp_rows["metric"].eq("fridsma_regular_wave_amplitudes_max_relative_error")]
            self.assertIn("figures/fridsma_regular_wave_amplitudes_comparison.png", str(figure_row["note"].iloc[0]))
            residual_info = amp_rows[amp_rows["metric"].eq("fridsma_regular_wave_amplitudes_residual_summary")]
            self.assertEqual(residual_info["status"].iloc[0], "INFO")
            shape_info = amp_rows[amp_rows["metric"].eq("fridsma_regular_wave_amplitudes_shape_audit")]
            self.assertEqual(shape_info["status"].iloc[0], "INFO")

    def test_katayama_amplitude_dataset_accepts_pitch_per_wave_slope(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "katayama"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "case_id": "slope_pitch",
                    "fn_l": 1.21,
                    "wave_height_over_draft": 0.10,
                    "lambda_over_loa": 1.60,
                    "heave_rao_m_per_m": 0.0,
                    "pitch_rao_rad_per_wave_slope": 0.0,
                    "cg_accel_g": 0.0,
                    "bow_accel_g": 0.0,
                    "length_m": 0.625,
                    "beam_m": 0.250,
                    "draft_m": 0.059,
                    "mass_kg": 4.28,
                    "lcg_from_transom_m": 0.285,
                    "kg_above_keel_m": 0.111,
                    "deadrise_deg": 22.0,
                    "pitch_radius_gyration_m": 0.15625,
                }
            )
            prediction = _amplitude_prediction(base)
            wavenumber = 2.0 * math.pi / (base["lambda_over_loa"] * base["length_m"])
            data = pd.DataFrame(
                [
                    {
                        **base.to_dict(),
                        "heave_rao_m_per_m": prediction["computed_heave_rao_m_per_m"],
                        "pitch_rao_rad_per_wave_slope": prediction["computed_pitch_rao_rad_per_m"] / wavenumber,
                        "cg_accel_g": prediction["computed_cg_accel_g"],
                        "bow_accel_g": prediction["computed_bow_accel_g"],
                    }
                ]
            )
            data.to_csv(data_dir / "regular_wave_response_digitized.csv", index=False)

            summary = validate_goal_gap_audit(tmp_path / "out", reference_root)
            amp_rows = summary[summary["benchmark"].eq("katayama_regular_wave_amplitudes")]
            self.assertIn("katayama_regular_wave_amplitudes_dataset_schema", set(amp_rows["metric"]))
            self.assertTrue(amp_rows[~amp_rows["status"].eq("INFO")]["status"].eq("PASS").all())
            comparison = pd.read_csv(tmp_path / "out" / "katayama_regular_wave_amplitudes_comparison.csv")
            residual_summary = pd.read_csv(tmp_path / "out" / "katayama_regular_wave_amplitudes_residual_summary.csv")
            self.assertTrue((tmp_path / "out" / "figures" / "katayama_regular_wave_amplitudes_comparison.png").exists())
            self.assertIn("time_domain_value", comparison.columns)
            self.assertIn("metric_overall", set(residual_summary["summary_type"]))
            pitch_row = comparison[comparison["metric"].eq("pitch_rao_rad_per_m")].iloc[0]
            self.assertEqual(pitch_row["reference_source_column"], "pitch_rao_rad_per_wave_slope")
            self.assertAlmostEqual(pitch_row["reference_value"], prediction["computed_pitch_rao_rad_per_m"])

    def test_katayama_motion_only_amplitude_dataset_keeps_acceleration_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reference_root = tmp_path / "benchmarks"
            data_dir = reference_root / "katayama"
            data_dir.mkdir(parents=True)
            base = pd.Series(
                {
                    "case_id": "motion_only",
                    "fn_l": 1.21,
                    "wave_height_over_draft": 0.10,
                    "lambda_over_loa": 1.60,
                    "heave_rao_m_per_m": 0.0,
                    "pitch_rao_rad_per_wave_slope": 0.0,
                    "length_m": 0.625,
                    "beam_m": 0.250,
                    "draft_m": 0.059,
                    "mass_kg": 4.28,
                    "lcg_from_transom_m": 0.285,
                    "kg_above_keel_m": 0.111,
                    "deadrise_deg": 22.0,
                    "pitch_radius_gyration_m": 0.15625,
                }
            )
            prediction = _amplitude_prediction(base)
            wavenumber = 2.0 * math.pi / (base["lambda_over_loa"] * base["length_m"])
            data = pd.DataFrame(
                [
                    {
                        **base.to_dict(),
                        "heave_rao_m_per_m": prediction["computed_heave_rao_m_per_m"],
                        "pitch_rao_rad_per_wave_slope": prediction["computed_pitch_rao_rad_per_m"] / wavenumber,
                    }
                ]
            )
            data.to_csv(data_dir / "regular_wave_response_digitized.csv", index=False)

            summary = validate_goal_gap_audit(tmp_path / "out", reference_root)
            amp_rows = summary[summary["benchmark"].eq("katayama_regular_wave_amplitudes")]
            comparison = pd.read_csv(tmp_path / "out" / "katayama_regular_wave_amplitudes_comparison.csv")
            self.assertEqual(
                amp_rows[amp_rows["metric"].eq("katayama_regular_wave_amplitudes_dataset_schema")]["status"].iloc[0],
                "PASS",
            )
            self.assertEqual({"heave_rao_m_per_m", "pitch_rao_rad_per_m"}, set(comparison["metric"]))
            self.assertTrue(comparison["status"].eq("PASS").all())
            pending_metrics = set(amp_rows[amp_rows["status"].eq("NOT_EVALUATED")]["metric"])
            self.assertIn("motion_only_cg_accel_g_reference_available", pending_metrics)
            self.assertIn("motion_only_bow_accel_g_reference_available", pending_metrics)


if __name__ == "__main__":
    unittest.main()
