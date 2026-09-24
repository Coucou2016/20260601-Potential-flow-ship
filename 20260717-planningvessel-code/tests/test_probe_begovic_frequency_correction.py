from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from planing_seakeeping.planing_frequency_correction import PlaningFrequencyCorrection
from scripts.probe_begovic_frequency_correction import (
    _attach_phase_resolved_excitation,
    _correction_route_specs,
    _load_direct_2dt_wave_excitation,
    _modal_diagnostic_rows,
    _model_term_rows,
    _parser,
)


class BegovicFrequencyCorrectionProbeTests(unittest.TestCase):
    @staticmethod
    def _correction(metadata: dict[str, object]) -> PlaningFrequencyCorrection:
        values = np.zeros((3, 2, 2), dtype=float)
        return PlaningFrequencyCorrection(
            sample_omega_rad_s=np.asarray([1.0, 2.0, 3.0]),
            high_frequency_reference_rad_s=3.0,
            delta_added_mass=values,
            delta_radiation_damping=values,
            raw_added_mass=values,
            raw_radiation_damping=values,
            metadata=metadata,
        )

    def test_cli_accepts_repeated_nonlinear_forced_motion_csv_paths(self) -> None:
        args = _parser().parse_args(
            [
                "--hydrodynamic-correction-source",
                "nonlinear_2dt_csv",
                "--forced-motion-csv",
                "heave.csv",
                "--forced-motion-csv",
                "pitch.csv",
            ]
        )
        self.assertEqual(args.hydrodynamic_correction_source, "nonlinear_2dt_csv")
        self.assertEqual([path.name for path in args.forced_motion_csv], ["heave.csv", "pitch.csv"])

    def test_cli_accepts_target_forced_motion_restoring_matrix(self) -> None:
        args = _parser().parse_args(
            ["--forced-motion-restoring-csv", "restoring_matrices.csv"]
        )

        self.assertEqual(args.forced_motion_restoring_csv.name, "restoring_matrices.csv")

    def test_cli_accepts_explicit_screening_case_codes(self) -> None:
        args = _parser().parse_args(
            ["--case-code", "C8", "--case-code", "C7", "--case-code", "C6"]
        )

        self.assertEqual(args.case_code, ["C8", "C7", "C6"])

    def test_cli_accepts_source_encounter_frequency_coordinate(self) -> None:
        args = _parser().parse_args(
            ["--frequency-coordinate-route", "source_encounter"]
        )

        self.assertEqual(args.frequency_coordinate_route, "source_encounter")

    def test_cli_accepts_source_fixed_half_beam_transom_correction(self) -> None:
        args = _parser().parse_args(
            [
                "--transom-force-cutoff-length-beams",
                "0.5",
                "--transom-force-recovery-profile",
                "linear_ramp",
            ]
        )
        self.assertEqual(args.transom_force_cutoff_length_beams, 0.5)
        self.assertEqual(args.transom_force_recovery_profile, "linear_ramp")

    def test_cli_accepts_square_root_transom_pressure_recovery(self) -> None:
        args = _parser().parse_args(
            ["--transom-force-recovery-profile", "square_root_ramp"]
        )
        self.assertEqual(args.transom_force_recovery_profile, "square_root_ramp")

    def test_cli_defaults_matched_bie_to_actual_wetted_body_geometry(self) -> None:
        args = _parser().parse_args([])
        self.assertEqual(args.wagner_pileup_factor, 1.0)

    def test_cli_accepts_direct_section_bem_excitation_route(self) -> None:
        args = _parser().parse_args(["--excitation-route", "section_bem_station_phase"])
        self.assertEqual(args.excitation_route, "section_bem_station_phase")

    def test_cli_accepts_matched_domain_excitation_route(self) -> None:
        args = _parser().parse_args(["--excitation-route", "matched_domain_station_phase"])
        self.assertEqual(args.excitation_route, "matched_domain_station_phase")

    def test_cli_accepts_repeated_direct_2dt_wave_excitation_paths(self) -> None:
        args = _parser().parse_args(
            [
                "--excitation-route",
                "direct_2dt_wave_csv",
                "--direct-wave-excitation-csv",
                "C8.csv",
                "--direct-wave-excitation-csv",
                "C7.csv",
            ]
        )

        self.assertEqual(args.excitation_route, "direct_2dt_wave_csv")
        self.assertEqual(
            [path.name for path in args.direct_wave_excitation_csv],
            ["C8.csv", "C7.csv"],
        )

    @staticmethod
    def _write_direct_excitation_files(
        directory: Path,
        *,
        calibrated: bool = False,
    ) -> list[Path]:
        paths: list[Path] = []
        for index, omega in enumerate((7.0, 8.0, 9.0)):
            rows = []
            for component, factor in (("total", 1.0), ("bem", 0.8)):
                rows.append(
                    {
                        "case_code": f"C{index}",
                        "omega_e_rad_s": omega,
                        "component": component,
                        "heave_force_real_n_per_m": factor * (10.0 + index),
                        "heave_force_imag_n_per_m": factor * (-2.0 - index),
                        "pitch_moment_real_nm_per_m": factor * (4.0 + index),
                        "pitch_moment_imag_nm_per_m": factor * (3.0 - index),
                        "wave_amplitude_scale": 0.25,
                        "response_calibration_used": calibrated and index == 1,
                    }
                )
            path = directory / f"C{index}.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            paths.append(path)
        return paths

    def test_direct_2dt_wave_loader_preserves_complex_components_and_provenance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = self._write_direct_excitation_files(Path(temporary_directory))

            correction = _load_direct_2dt_wave_excitation(paths)

        np.testing.assert_allclose(correction.sample_omega_rad_s, [7.0, 8.0, 9.0])
        np.testing.assert_allclose(
            correction.excitation_per_wave_amplitude[:, 0],
            [10.0 - 2.0j, 11.0 - 3.0j, 12.0 - 4.0j],
        )
        np.testing.assert_allclose(
            correction.excitation_components["bem"][:, 1],
            0.8 * np.asarray([4.0 + 3.0j, 5.0 + 2.0j, 6.0 + 1.0j]),
        )
        np.testing.assert_allclose(correction.raw_added_mass, 0.0)
        self.assertEqual(correction.metadata["wave_amplitude_scale"], 0.25)
        self.assertEqual(
            correction.metadata["linearization_role"],
            "quarter_source_amplitude_resolved_linearization_sample",
        )
        self.assertEqual(len(correction.metadata["source_csv_sha256"]), 3)
        self.assertFalse(correction.metadata["response_calibration_used"])

    def test_direct_2dt_wave_loader_rejects_response_calibration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = self._write_direct_excitation_files(
                Path(temporary_directory),
                calibrated=True,
            )

            with self.assertRaisesRegex(ValueError, "must not use response calibration"):
                _load_direct_2dt_wave_excitation(paths)

    def test_cli_accepts_planing_base_plus_matched_radiation_matrix_application(self) -> None:
        args = _parser().parse_args(
            [
                "--excitation-route",
                "matched_bie_station_phase",
                "--phase-resolved-matrix-application",
                "planing_base_plus_matched_radiation",
            ]
        )
        self.assertEqual(
            args.phase_resolved_matrix_application,
            "planing_base_plus_matched_radiation",
        )

    def test_cli_accepts_planing_high_frequency_added_plus_matched_damping(self) -> None:
        args = _parser().parse_args(
            [
                "--phase-resolved-matrix-application",
                "planing_high_frequency_added_plus_matched_damping",
            ]
        )
        self.assertEqual(
            args.phase_resolved_matrix_application,
            "planing_high_frequency_added_plus_matched_damping",
        )

    def test_nonlinear_matrix_contract_allows_only_complete_raw_replacement(self) -> None:
        correction = self._correction(
            {
                "source": "sun_nonlinear_2dt_forced_motion_precalculation",
                "application_contract": "replace_with_matched_bie",
            }
        )
        self.assertEqual(
            _correction_route_specs(correction),
            (("nonlinear_2dt_raw_added_and_damping", True, True, "replace_with_matched_bie"),),
        )

    def test_diagnostic_sources_retain_component_decomposition(self) -> None:
        correction = self._correction({"source": "diagnostic"})
        routes = _correction_route_specs(correction)
        self.assertEqual(len(routes), 7)
        self.assertIn(
            ("matched_raw_added_and_damping", True, True, "replace_with_matched_bie"), routes
        )
        self.assertIn(
            (
                "planing_base_plus_matched_radiation",
                True,
                True,
                "planing_base_plus_matched_radiation",
            ),
            routes,
        )

    def test_phase_excitation_can_be_attached_without_changing_complete_abc(self) -> None:
        matrix = self._correction(
            {
                "source": "nonlinear_2dt",
                "application_contract": "replace_with_matched_bie",
                "complete_matrix_contract": "replace_A_B_C_together",
            }
        )
        source = self._correction(
            {
                "source": "matched_bie",
                "head_sea_excitation_formulation": "phase_resolved_test",
            }
        )
        source = PlaningFrequencyCorrection(
            sample_omega_rad_s=source.sample_omega_rad_s,
            high_frequency_reference_rad_s=source.high_frequency_reference_rad_s,
            delta_added_mass=source.delta_added_mass,
            delta_radiation_damping=source.delta_radiation_damping,
            raw_added_mass=source.raw_added_mass,
            raw_radiation_damping=source.raw_radiation_damping,
            metadata=source.metadata,
            excitation_per_wave_amplitude=np.asarray(
                [[1.0 + 2.0j, 3.0 + 4.0j]] * 3
            ),
        )

        combined = _attach_phase_resolved_excitation(matrix, source)

        np.testing.assert_allclose(combined.raw_added_mass, matrix.raw_added_mass)
        np.testing.assert_allclose(
            combined.excitation_per_wave_amplitude,
            source.excitation_per_wave_amplitude,
        )
        self.assertEqual(
            combined.metadata["head_sea_excitation_formulation"],
            "phase_resolved_test",
        )
        self.assertFalse(combined.metadata["response_calibration_used"])

    def test_model_term_export_contains_all_matrices_and_complex_excitation(self) -> None:
        omega = np.asarray([2.0, 3.0])
        values = np.repeat(np.eye(2)[None, :, :], 2, axis=0)
        model = type(
            "Model",
            (),
            {
                "hydrodynamics": type(
                    "Hydro",
                    (),
                    {
                        "solver_omega_rad_s": omega,
                        "encounter_omega_rad_s": omega,
                        "added_mass": values,
                        "radiation_damping": 2.0 * values,
                    },
                )(),
                "rigid_mass": np.eye(2),
                "restoring": 3.0 * values,
                "omega0_rad_s": omega - 1.0,
                "excitation_per_wave_amplitude": np.asarray(
                    [[1.0 + 2.0j, 3.0 + 4.0j], [5.0 + 6.0j, 7.0 + 8.0j]]
                ),
            },
        )()
        rows = _model_term_rows("test", "FnB=0", model)
        self.assertEqual(len(rows), 2 * (4 * 4 + 2))
        terms = {row["term"] for row in rows}
        self.assertEqual(
            terms,
            {
                "rigid_mass",
                "added_mass",
                "radiation_damping",
                "restoring",
                "excitation_per_wave_amplitude",
            },
        )
        excitation = next(row for row in rows if row["term"] == "excitation_per_wave_amplitude")
        self.assertEqual(excitation["value_imag"], 2.0)

    def test_modal_diagnostics_export_response_independent_poles_and_matrix_health(self) -> None:
        omega = np.asarray([2.0, 3.0])
        added = np.zeros((2, 2, 2), dtype=float)
        damping = np.repeat((0.2 * np.eye(2))[None, :, :], 2, axis=0)
        restoring = np.repeat(np.diag([1.0, 4.0])[None, :, :], 2, axis=0)
        model = type(
            "Model",
            (),
            {
                "hydrodynamics": type(
                    "Hydro",
                    (),
                    {
                        "encounter_omega_rad_s": omega,
                        "added_mass": added,
                        "radiation_damping": damping,
                    },
                )(),
                "rigid_mass": np.eye(2),
                "restoring": restoring,
                "omega0_rad_s": omega - 1.0,
            },
        )()

        rows = _modal_diagnostic_rows("test", "FnB=0", model)

        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["symmetric_mass_positive_definite"] for row in rows))
        self.assertTrue(all(row["system_asymptotically_stable"] for row in rows))
        self.assertTrue(all(row["pole_stable"] for row in rows))
        self.assertTrue(all(not row["response_calibration_used"] for row in rows))
        positive_poles = [
            row for row in rows if row["frequency_index"] == 0 and row["pole_imag_rad_s"] > 0.0
        ]
        np.testing.assert_allclose(
            sorted(row["damped_natural_frequency_rad_s"] for row in positive_poles),
            [np.sqrt(1.0 - 0.1**2), np.sqrt(4.0 - 0.1**2)],
        )


if __name__ == "__main__":
    unittest.main()
