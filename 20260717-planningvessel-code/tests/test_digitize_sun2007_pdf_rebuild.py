from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.digitize_sun2007_pdf_rebuild import (
    AUDIT_CSV_NAME,
    CURVE_CSV_NAME,
    DEFAULT_OLD_CSV,
    DEFAULT_SOURCE_DIR,
    DIGITIZATION_MANIFEST_NAME,
    SOURCE_MANIFEST_NAME,
    digitize_pdf_rebuild,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / DEFAULT_SOURCE_DIR.relative_to(ROOT)
OLD_CSV = ROOT / DEFAULT_OLD_CSV.relative_to(ROOT)
EXPECTED_CASES = {
    (10.0, "free_surface"),
    (10.0, "pressure"),
    (20.0, "free_surface"),
    (20.0, "pressure"),
    (30.0, "free_surface"),
    (30.0, "pressure"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DigitizeSun2007PdfRebuildTests(unittest.TestCase):
    def test_temporary_directory_run_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            first = digitize_pdf_rebuild(SOURCE_DIR, OLD_CSV, temporary_root / "first")
            second = digitize_pdf_rebuild(SOURCE_DIR, OLD_CSV, temporary_root / "second")

            self.assertEqual(first["curve_csv"].name, CURVE_CSV_NAME)
            self.assertEqual(first["audit_csv"].name, AUDIT_CSV_NAME)
            self.assertEqual(first["manifest"].name, DIGITIZATION_MANIFEST_NAME)
            for name in ("curve_csv", "audit_csv", "manifest"):
                self.assertEqual(first[name].read_bytes(), second[name].read_bytes())

    def test_six_curves_are_nonempty_and_source_hashes_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = digitize_pdf_rebuild(SOURCE_DIR, OLD_CSV, Path(temporary) / "out")
            with outputs["curve_csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            point_counts: dict[tuple[float, str], int] = {}
            for row in rows:
                key = (float(row["beta_deg"]), row["quantity"])
                point_counts[key] = point_counts.get(key, 0) + 1
            self.assertEqual(set(point_counts), EXPECTED_CASES)
            self.assertTrue(all(count > 0 for count in point_counts.values()))

            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["source_input"]["crop_manifest_sha256"],
                _sha256(SOURCE_DIR / SOURCE_MANIFEST_NAME),
            )
            self.assertEqual(len(manifest["source_input"]["images"]), 6)
            for source in manifest["source_input"]["images"]:
                image_path = SOURCE_DIR / source["filename"]
                self.assertTrue(source["verified_against_source_manifest"])
                self.assertEqual(source["sha256"], _sha256(image_path))

    def test_old_reference_is_explicitly_excluded_from_digitization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = digitize_pdf_rebuild(SOURCE_DIR, OLD_CSV, Path(temporary) / "out")
            manifest = json.loads(outputs["manifest"].read_text(encoding="utf-8"))
            self.assertFalse(manifest["reference_data_participates_in_solution"])
            self.assertFalse(manifest["reference_curve_used_for_digitization"])
            self.assertFalse(manifest["reference_curve_used_for_solution"])
            self.assertFalse(manifest["response_calibration_used"])
            self.assertFalse(manifest["old_csv_used_for_calibration"])
            self.assertFalse(manifest["old_csv_used_for_pixel_selection"])
            self.assertFalse(manifest["old_csv_used_for_branch_selection"])
            self.assertEqual(manifest["old_csv_role"], "post_digitization_audit_only")

    def test_bad_input_fails_before_creating_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            bad_source = temporary_root / "bad_pdf_rebuild_inputs"
            shutil.copytree(SOURCE_DIR, bad_source)
            corrupted_image = bad_source / "fig2_6_beta10_free_surface.png"
            corrupted_image.write_bytes(corrupted_image.read_bytes() + b"not-the-manifest-hash")
            output_dir = temporary_root / "should_not_exist"
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                digitize_pdf_rebuild(bad_source, OLD_CSV, output_dir)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
