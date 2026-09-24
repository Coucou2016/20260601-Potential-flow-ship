from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_sun2007_fig2_6_vector import (
    DEFAULT_LEGACY_CSV,
    DEFAULT_RASTER_CSV,
    MANIFEST_FILENAME,
    extract_sun2007_fig2_6_vector,
    extract_vector_rows,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = (
    ROOT
    / "benchmarks"
    / "sun2007_fig2_6_wedge_similarity"
    / "sun2007_boundary_element_method.pdf"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExtractSun2007Fig26VectorTests(unittest.TestCase):
    def test_pdf_only_extraction_selects_six_native_vector_curves(self) -> None:
        extraction = extract_vector_rows(SOURCE_PDF)
        self.assertEqual(extraction.xobject_count, 0)
        self.assertEqual(extraction.color_space_record["alternate"], "/DeviceRGB")
        self.assertEqual(extraction.global_dash_record, {"operation_index": 19, "array": [], "phase": 0.0})
        self.assertEqual(
            [(curve.spec.beta_deg, curve.spec.quantity) for curve in extraction.curves],
            [
                (10.0, "free_surface"),
                (10.0, "pressure"),
                (20.0, "free_surface"),
                (20.0, "pressure"),
                (30.0, "free_surface"),
                (30.0, "pressure"),
            ],
        )
        for curve in extraction.curves:
            self.assertGreater(len(curve.rows), 0)
            if curve.spec.quantity == "free_surface":
                self.assertIsNotNone(curve.fold)
                self.assertEqual(curve.rows[0]["branch_policy"], "content_stream_fold_to_outward_branch")
                self.assertLess(max(row["y_nondimensional"] for row in curve.rows), 0.6)
            else:
                self.assertIsNone(curve.fold)

    def test_artifacts_are_reproducible_and_inputs_remain_read_only(self) -> None:
        protected = (SOURCE_PDF, DEFAULT_RASTER_CSV, DEFAULT_LEGACY_CSV)
        before = {path: _sha256(path) for path in protected}
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            first = temporary_root / "first"
            second = temporary_root / "second"
            first_manifest_path = extract_sun2007_fig2_6_vector(SOURCE_PDF, first)
            second_manifest_path = extract_sun2007_fig2_6_vector(SOURCE_PDF, second)

            self.assertEqual(first_manifest_path.name, MANIFEST_FILENAME)
            self.assertEqual(first_manifest_path.read_bytes(), second_manifest_path.read_bytes())
            manifest = json.loads(first_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"]["page_index_zero_based"], 39)
            self.assertEqual(manifest["source"]["xobject_count"], 0)
            self.assertFalse(manifest["reference_use"]["raster_used_for_path_selection"])
            self.assertFalse(manifest["reference_use"]["legacy_used_for_axis_calibration"])
            self.assertEqual(len(manifest["curves"]), 6)
            self.assertEqual(
                [
                    (curve["panel"], curve["point_count"], curve["vector_row_sha256"])
                    for curve in manifest["curves"]
                ],
                [
                    ("beta10_free_surface", 62, "2e9b34345f55b47e0ca4e51c584921a5cd6d1bd184113926e048e94a170e0f3a"),
                    ("beta10_pressure", 192, "2aa3d841026f28c159314935f86222f58d8ca480ad958abb7f398c0a491bc023"),
                    ("beta20_free_surface", 64, "9d507d3a4d04210ab38f9218b70645e005d9fb0ba4c501171fc6fbe5102d016d"),
                    ("beta20_pressure", 193, "1030896d79136dcda4c1c67bba9c4caf8742891503ce2d482f932c4514efefbb"),
                    ("beta30_free_surface", 68, "768d8bfc180cfd4bbe1dcd808af5112cd0891030c221a52144d64af9b53077a7"),
                    ("beta30_pressure", 184, "55ef2eb453272692f26dbcc23b287c3ef8220ae866c30130f07ca957869df364"),
                ],
            )

            for artifact in manifest["artifacts"].values():
                path = first / artifact["filename"]
                self.assertTrue(path.is_file())
                self.assertEqual(_sha256(path), artifact["sha256"])

            for audit_name in ("raster_audit_csv", "legacy_audit_csv"):
                audit_path = first / manifest["artifacts"][audit_name]["filename"]
                with audit_path.open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 6)
                self.assertTrue(all(int(row["compared_point_count"]) > 0 for row in rows))
                self.assertTrue(
                    all(
                        row["matching_method"]
                        == "post_extraction_nearest_vector_x_no_interpolation_across_dash_gaps"
                        for row in rows
                    )
                )
        self.assertEqual(before, {path: _sha256(path) for path in protected})


if __name__ == "__main__":
    unittest.main()
