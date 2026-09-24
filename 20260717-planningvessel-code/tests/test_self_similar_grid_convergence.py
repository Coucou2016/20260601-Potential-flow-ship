from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_grid_convergence import analyze_grid_convergence


class SelfSimilarGridConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _write_run(self, panels: int, perturbation: float, *, regrid: bool) -> Path:
        output = self.root / f"grid_{panels}"
        output.mkdir()
        source = {
            "source_hashes": {"state": "frozen"},
            "continuation_config_overrides": {"pseudo_cfl": 0.1},
        }
        continuation = {"accepted_iterations": panels // 10}
        summary = {
            "source_checkpoint": source,
            "continuation": continuation,
            "final_state": {
                "kinematic_rms": 0.3 + perturbation,
                # Legacy summaries used this name before the canonical
                # convergence-integral field was added.
                "kinematic_integral_linear_exact": 0.02 + perturbation,
                "interface_s_lambda": 3.0 + perturbation,
                "measured_s_lambda": 3.01 + perturbation,
                "relative_s_lambda_mismatch": 0.01,
                "solved_dipole_coefficient": 6.0 + perturbation,
                "body_vertical_force_coefficient": 30.0 + perturbation,
            },
            "post_solve_reference_metrics": {
                "free_surface_nrmse": 0.2 + perturbation,
                "pressure_nrmse": 0.3 + perturbation,
            },
            "post_solve_scalar_reference_metrics": {
                "computed_pressure_peak": 14.0 + perturbation,
                "computed_peak_eta": 0.4 + perturbation,
            },
        }
        if regrid:
            continuation["pseudo_time"] = 0.1
            summary["regrid"] = {
                "geometry_relative_l2": 1.0e-5,
                "state_relative_changes": {
                    name: 1.0e-3 for name in REGRID_FIELDS
                },
            }
            (output / "regrid_summary.json").write_text(json.dumps(summary))
        else:
            source["cumulative_pseudo_time"] = 1.0
            continuation["cumulative_pseudo_time"] = 1.1
            (output / "resume_summary.json").write_text(json.dumps(summary))
        (output / "coupled_checkpoint.json").write_text(
            json.dumps(
                {"config": {"free_surface_panels": panels, "pseudo_cfl": 0.1}}
            )
        )
        pd.DataFrame(
            {
                "pseudo_time": ([1.0, 1.05, 1.1] if not regrid else [0.0, 0.05, 0.1]),
                "kinematic_rms": [0.4, 0.35, 0.3 + perturbation],
                "root_body_eta": [0.3, 0.35, 0.4 + perturbation],
            }
        ).to_csv(output / "coupled_pseudo_time_history.csv", index=False)
        x = np.linspace(1.0, 5.0, panels + 1)
        pd.DataFrame({"xi": x, "eta": 0.5 - 0.1 * x + perturbation}).to_csv(
            output / "coupled_checkpoint_outer_nodes.csv", index=False
        )
        eta = np.linspace(0.0, 1.0, panels)
        pd.DataFrame(
            {"eta": eta, "pressure_coefficient": 1.0 + eta + perturbation}
        ).to_csv(output / "coupled_body_pressure.csv", index=False)
        return output

    def _remove_reference_metrics(self, run: Path) -> None:
        name = "regrid_summary.json" if (run / "regrid_summary.json").exists() else "resume_summary.json"
        path = run / name
        summary = json.loads(path.read_text())
        summary["post_solve_reference_metrics"] = {
            "status": "REFERENCE_NOT_AVAILABLE"
        }
        summary["post_solve_scalar_reference_metrics"] = {
            "status": "REFERENCE_NOT_AVAILABLE"
        }
        path.write_text(json.dumps(summary))

    def test_two_level_grid_convergence_passes_with_scope_warning(self) -> None:
        runs = [
            self._write_run(80, 0.001, regrid=False),
            self._write_run(120, 0.0, regrid=True),
        ]
        levels, pairs, report = analyze_grid_convergence(runs)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(levels), 2)
        self.assertEqual(len(pairs), 1)
        self.assertFalse(report["three_level_trend_established"])
        self.assertEqual(report["physical_validation_status"], "FAIL")

    def test_grid_convergence_is_reference_optional_and_k_change_is_diagnostic(self) -> None:
        coarse = self._write_run(80, 1.0e-6, regrid=False)
        fine = self._write_run(120, 0.0, regrid=True)
        self._remove_reference_metrics(coarse)
        self._remove_reference_metrics(fine)
        coarse_summary = json.loads((coarse / "resume_summary.json").read_text())
        fine_summary = json.loads((fine / "regrid_summary.json").read_text())
        coarse_summary["final_state"]["kinematic_integral_linear_exact"] = 2.0e-3
        fine_summary["final_state"]["kinematic_integral_linear_exact"] = 1.0e-3
        (coarse / "resume_summary.json").write_text(json.dumps(coarse_summary))
        (fine / "regrid_summary.json").write_text(json.dumps(fine_summary))

        levels, pairs, report = analyze_grid_convergence([coarse, fine])

        self.assertEqual(report["status"], "PASS")
        self.assertNotIn("free_surface_nrmse", levels.columns)
        self.assertAlmostEqual(
            pairs.iloc[0]["kinematic_convergence_integral_relative_change"],
            0.5,
        )
        self.assertAlmostEqual(
            report["finest_pair"][
                "diagnostic_kinematic_convergence_integral_relative_change"
            ],
            0.5,
        )

    def test_three_level_interpretation_matches_machine_field(self) -> None:
        runs = [
            self._write_run(80, 2.0e-4, regrid=False),
            self._write_run(120, 1.0e-4, regrid=True),
            self._write_run(160, 0.0, regrid=True),
        ]

        _, _, report = analyze_grid_convergence(runs)

        self.assertTrue(report["three_level_trend_established"])
        self.assertIn("three-level trend", report["interpretation"])
        self.assertNotIn("third grid is needed", report["interpretation"])


REGRID_FIELDS = (
    "kinematic_rms",
    "solved_dipole_coefficient",
    "body_pressure_max",
    "body_vertical_force_coefficient",
    "measured_s_lambda",
)


if __name__ == "__main__":
    unittest.main()
