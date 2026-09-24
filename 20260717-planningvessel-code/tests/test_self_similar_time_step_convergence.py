from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_time_step_convergence import (
    analyze_time_step_convergence,
)


class SelfSimilarTimeStepConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _write_run(self, name: str, cfl: float, perturbation: float) -> Path:
        output = self.root / name
        output.mkdir()
        source_hashes = {"state": "frozen"}
        summary = {
            "source_checkpoint": {
                "cumulative_pseudo_time": 1.0,
                "source_hashes": source_hashes,
                "continuation_config_overrides": {"pseudo_cfl": cfl},
            },
            "continuation": {
                "accepted_iterations": int(round(1.0 / cfl)),
                "cumulative_pseudo_time": 1.1,
            },
            "final_state": {
                "kinematic_rms": 0.3 + perturbation,
                "kinematic_convergence_integral": 0.2 + perturbation,
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
        (output / "resume_summary.json").write_text(json.dumps(summary))
        pd.DataFrame(
            {
                "pseudo_time": [1.0, 1.05, 1.1],
                "kinematic_rms": [0.4, 0.35, 0.3 + perturbation],
                "kinematic_convergence_integral": [
                    0.3,
                    0.25,
                    0.2 + perturbation,
                ],
                "root_body_eta": [0.3, 0.35, 0.4 + perturbation],
            }
        ).to_csv(output / "coupled_pseudo_time_history.csv", index=False)
        x = np.linspace(1.0, 5.0, 10)
        pd.DataFrame({"xi": x, "eta": 0.5 - 0.1 * x + perturbation}).to_csv(
            output / "coupled_checkpoint_outer_nodes.csv", index=False
        )
        eta = np.linspace(0.0, 1.0, 10)
        pd.DataFrame(
            {
                "eta": eta,
                "pressure_coefficient": 1.0 + eta + perturbation,
            }
        ).to_csv(output / "coupled_body_pressure.csv", index=False)
        return output

    def test_matched_three_level_convergence_passes(self) -> None:
        runs = [
            self._write_run("coarse", 0.2, 0.002),
            self._write_run("medium", 0.1, 0.001),
            self._write_run("fine", 0.05, 0.0),
        ]
        levels, pairs, report = analyze_time_step_convergence(runs)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(levels), 3)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(report["physical_validation_status"], "FAIL")

    def test_different_source_checkpoint_fails(self) -> None:
        runs = [
            self._write_run("coarse", 0.2, 0.0),
            self._write_run("fine", 0.1, 0.0),
        ]
        summary_path = runs[-1] / "resume_summary.json"
        summary = json.loads(summary_path.read_text())
        summary["source_checkpoint"]["source_hashes"] = {"state": "different"}
        summary_path.write_text(json.dumps(summary))
        _, _, report = analyze_time_step_convergence(runs)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["same_frozen_source_checkpoint"])


if __name__ == "__main__":
    unittest.main()
