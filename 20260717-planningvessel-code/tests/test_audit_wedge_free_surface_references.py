from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZHAO = Path("benchmarks/sun2007_fig2_6_wedge_similarity/fig2_6_zhao_faltinsen_similarity_curves.csv")
LEGACY = Path(
    "benchmarks/sun2007_fig2_6_wedge_similarity/legacy_column_median_v1/"
    "fig2_6_zhao_faltinsen_similarity_curves.csv"
)
IAFRATI = Path(
    "benchmarks/iafrati2013_self_similar_wedge/"
    "iafrati2013_20deg_outer_free_surface.csv"
)
NATIVE_VECTOR = Path(
    "benchmarks/sun2007_fig2_6_wedge_similarity/native_vector_v1/"
    "sun2007_fig2_6_vector_similarity_curves.csv"
)
CANDIDATE = Path(
    "outputs/self_similar_wedge_20deg_grid80_quadratic_root_aitken20_"
    "resume100_cfl025_v83/coupled_checkpoint_outer_nodes.csv"
)
FROZEN = ROOT / "outputs" / "wedge_free_surface_reference_audit_20260825"


class WedgeFreeSurfaceReferenceAuditTests(unittest.TestCase):
    def test_frozen_audit_preserves_dual_reference_decision(self) -> None:
        report = json.loads(
            (FROZEN / "free_surface_reference_audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["status"], "REFERENCE_DISCREPANCY_REQUIRES_DUAL_REPORTING")
        self.assertFalse(report["reference_used_during_solve"])
        changes = {row["beta_deg"]: row for row in report["legacy_digitization_changes"]}
        self.assertEqual(changes[10.0]["removed_legacy_columns"], [272])
        self.assertEqual(changes[10.0]["changed_shared_columns"], [273, 274, 281, 289])
        self.assertEqual(changes[20.0]["changed_shared_columns"], [])
        self.assertEqual(changes[30.0]["changed_shared_columns"], [])

        candidate = report["candidate_metrics"]
        self.assertAlmostEqual(
            candidate["same_abscissae_zhao"]["nrmse_by_reference_range"],
            0.15632152235980054,
        )
        self.assertAlmostEqual(
            candidate["same_abscissae_iafrati"]["nrmse_by_reference_range"],
            0.050217502424911874,
        )
        self.assertAlmostEqual(
            candidate["full_iafrati_overlap"]["nrmse_by_reference_range"],
            0.07313914114154076,
        )

    def test_reference_audit_tables_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "audit_wedge_free_surface_references.py"),
                    "--zhao",
                    str(ZHAO),
                    "--zhao-legacy",
                    str(LEGACY),
                    "--iafrati",
                    str(IAFRATI),
                    "--candidate",
                    str(CANDIDATE),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd=ROOT,
            )
            self.assertEqual(
                (out / "free_surface_reference_pointwise.csv").read_bytes(),
                (FROZEN / "free_surface_reference_pointwise.csv").read_bytes(),
            )
            self.assertEqual(
                (out / "free_surface_reference_audit.json").read_bytes(),
                (FROZEN / "free_surface_reference_audit.json").read_bytes(),
            )

    def test_native_vector_can_be_audited_against_frozen_curve_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "audit_wedge_free_surface_references.py"),
                    "--zhao",
                    str(NATIVE_VECTOR),
                    "--zhao-legacy",
                    str(ZHAO),
                    "--iafrati",
                    str(IAFRATI),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd=ROOT,
            )
            report = json.loads(
                (out / "free_surface_reference_audit.json").read_text(
                    encoding="utf-8"
                )
            )
            changes = report["legacy_digitization_changes"]
            self.assertEqual(len(changes), 3)
            self.assertTrue(
                all(
                    row["comparison_mode"] == "dimensionless_curve_interpolation"
                    for row in changes
                )
            )
            self.assertTrue((out / "free_surface_reference_audit.png").is_file())


if __name__ == "__main__":
    unittest.main()
