from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "benchmarks" / "self_similar_wedge_reference_contract.json"


class SelfSimilarWedgeReferenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_is_reference_isolated_and_covers_all_angles(self) -> None:
        self.assertFalse(self.contract["used_during_solve"])
        self.assertFalse(self.contract["response_calibration_used"])
        self.assertEqual(
            [case["deadrise_deg"] for case in self.contract["cases"]],
            [10.0, 20.0, 30.0],
        )

    def test_contract_freezes_stage_thresholds(self) -> None:
        metrics = self.contract["acceptance_metrics"]
        self.assertEqual(metrics["outer_free_surface_nrmse_limit"], 0.05)
        self.assertEqual(metrics["pressure_curve_nrmse_limit"], 0.10)
        self.assertEqual(metrics["pressure_peak_relative_error_limit"], 0.05)
        self.assertEqual(
            metrics["pressure_peak_location_relative_error_limit"], 0.05
        )
        self.assertEqual(
            metrics["integrated_vertical_force_relative_error_limit"], 0.05
        )

    def test_coordinate_mapping_matches_source_axes_and_solver_convention(self) -> None:
        definition = self.contract["problem_definition"]
        self.assertEqual(
            definition["canonical_coordinates"],
            {
                "xi": "y_horizontal/(V*t)",
                "eta": "z_vertical_up/(V*t)",
            },
        )
        evidence = definition["coordinate_mapping_evidence"]
        self.assertIn("y/(Vt)=xi", evidence["mapping"])
        self.assertIn("z/(Vt)=eta", evidence["mapping"])

    def test_declared_local_reference_hashes_match(self) -> None:
        for reference in self.contract["reference_catalog"].values():
            for field in (
                "artifact",
                "manifest",
                "source_pdf",
                "pdf_panel_rebuild_manifest",
                "pdf_redigitization_manifest",
                "pdf_redigitization_csv",
                "pdf_redigitization_legacy_audit",
                "provenance_bundle_manifest",
                "superseded_legacy_artifact",
                "native_vector_reference_audit",
            ):
                relative = reference.get(field)
                expected = reference.get(f"{field}_sha256")
                if relative is None or expected is None:
                    continue
                path = ROOT / "benchmarks" / relative
                self.assertTrue(path.is_file(), path)
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

    def test_unresolved_reference_conflict_cannot_be_reported_as_frozen(self) -> None:
        self.assertNotEqual(self.contract["contract_status"], "FROZEN")
        twenty = next(
            case for case in self.contract["cases"] if case["deadrise_deg"] == 20.0
        )
        self.assertEqual(twenty["case_status"], "REFERENCE_CONFLICT")
        self.assertTrue(self.contract["pending_fields"])

    def test_sun_native_vector_is_primary_but_uncertainty_remains_open(self) -> None:
        sun = self.contract["reference_catalog"][
            "sun2007_zhao_faltinsen_fig2_6"
        ]
        self.assertEqual(
            sun["source_pdf_status"], "VERIFIED_SHA256_AND_FIGURE_PAGE"
        )
        self.assertEqual(
            sun["declared_source_images_status"],
            "MISSING_LEGACY_JPEG_BYTES_NOT_REQUIRED_FOR_PRIMARY",
        )
        self.assertEqual(
            sun["deterministic_pdf_panel_crops_status"],
            "SUPPORTING_RASTER_AUDIT_ONLY",
        )
        self.assertEqual(
            sun["role"],
            "source_native_vector_primary_frozen_before_physical_rescore",
        )
        self.assertFalse(
            sun["source_representation_resolution"]["solver_result_consulted"]
        )
        self.assertNotIn(
            "resolve the legacy-JPEG CSV versus deterministic-PDF redigitization conflict without selecting the curve closer to the solver",
            self.contract["pending_fields"],
        )
        self.assertNotIn(
            "Sun 2007 source PDF, bibliographic version and SHA-256",
            self.contract["pending_fields"],
        )
        ten = next(
            case for case in self.contract["cases"] if case["deadrise_deg"] == 10.0
        )
        self.assertEqual(ten["case_status"], "PENDING_UNCERTAINTY_RULE")


if __name__ == "__main__":
    unittest.main()
