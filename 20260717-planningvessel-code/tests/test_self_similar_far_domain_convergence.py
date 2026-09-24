from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.analyze_self_similar_far_domain_convergence import (
    analyze_far_domain_convergence,
)


class SelfSimilarFarDomainConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _write_run(self, radius: float, panels: int, perturbation: float) -> Path:
        output = self.root / f"far_{radius:g}"
        output.mkdir()
        parent_hash = "shared-parent"
        config = {
            "deadrise_deg": 20.0,
            "far_radius": radius,
            "free_surface_panels": panels,
            "far_field_panels": int(round(radius * 1.2)),
            "symmetry_panels": int(round(radius * 0.8)),
            "free_surface_panel_growth": 1.01,
            "body_panels": 48,
        }
        metadata = {
            "config": config,
            "expected_state": {
                "kinematic_integral_linear_exact": 8.0e-4 + perturbation,
                "body_pressure_max": 17.8 + perturbation,
                "body_vertical_force_coefficient": 42.6 + perturbation,
                "solved_dipole_coefficient": 8.1 + perturbation,
                "interface_s_lambda": 2.1,
                "measured_s_lambda": 2.101,
            },
            "files": {"outer_nodes": {"name": "coupled_checkpoint_outer_nodes.csv"}},
            "parent_checkpoint": {
                "path": str(self.root / "missing-parent"),
                "source_hashes": {"coupled_checkpoint.json": parent_hash},
            },
            "state_transformation": {
                "type": "reference_isolated_low_mode_trust_region",
                "basis": "root_local",
                "mode_count": 17,
                "global_mode_count": 16,
                "root_support_fraction": 0.15,
                "fixed_root_node_count": 2,
                "residual_space": "exact_endpoint",
                "root_inner_iterations": 8,
            },
        }
        (output / "coupled_checkpoint.json").write_text(json.dumps(metadata))
        xi = np.linspace(4.3, radius, panels + 1)
        eta = 0.42 * np.exp(-(xi - 4.3) / 2.0) + perturbation
        pd.DataFrame({"xi": xi, "eta": eta}).to_csv(
            output / "coupled_checkpoint_outer_nodes.csv", index=False
        )
        body_eta = np.linspace(-1.0, 0.5, 80)
        pd.DataFrame(
            {
                "eta": body_eta,
                "pressure_coefficient": 10.0 + 3.0 * body_eta + perturbation,
                "segment": "body",
            }
        ).to_csv(output / "coupled_body_pressure.csv", index=False)
        return output

    def test_density_matched_absolute_residual_and_physical_outputs_pass(self) -> None:
        runs = [self._write_run(30.0, 600, 1.0e-6), self._write_run(40.0, 800, 0.0)]
        levels, pairs, report = analyze_far_domain_convergence(runs)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["absolute_kinematic_pass"])
        self.assertTrue(report["density_match_pass"])
        self.assertEqual(len(levels), 2)
        self.assertEqual(len(pairs), 1)

    def test_residual_above_absolute_limit_fails(self) -> None:
        coarse = self._write_run(30.0, 600, 3.0e-4)
        fine = self._write_run(40.0, 800, 0.0)
        _, _, report = analyze_far_domain_convergence([coarse, fine])
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["absolute_kinematic_pass"])


if __name__ == "__main__":
    unittest.main()
