from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.rebuild_sun2007_fig2_6_from_pdf import (
    FIGURE_PAGE_INDEX_ZERO_BASED,
    MANIFEST_FILENAME,
    rebuild_from_pdf,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = (
    ROOT
    / "benchmarks"
    / "sun2007_fig2_6_wedge_similarity"
    / "sun2007_boundary_element_method.pdf"
)

EXPECTED_OUTPUTS = (
    ("fig2_6_beta10_free_surface.png", (808, 608)),
    ("fig2_6_beta10_pressure.png", (848, 608)),
    ("fig2_6_beta20_free_surface.png", (808, 608)),
    ("fig2_6_beta20_pressure.png", (848, 608)),
    ("fig2_6_beta30_free_surface.png", (808, 608)),
    ("fig2_6_beta30_pressure.png", (848, 608)),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RebuildSun2007Fig26FromPdfTests(unittest.TestCase):
    def test_six_fixed_panel_outputs_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            first_dir = temporary_root / "first"
            second_dir = temporary_root / "second"

            first_manifest_path = rebuild_from_pdf(SOURCE_PDF, first_dir)
            second_manifest_path = rebuild_from_pdf(SOURCE_PDF, second_dir)

            self.assertEqual(first_manifest_path.name, MANIFEST_FILENAME)
            self.assertEqual(second_manifest_path.name, MANIFEST_FILENAME)
            self.assertEqual(first_manifest_path.read_bytes(), second_manifest_path.read_bytes())

            first_manifest = json.loads(first_manifest_path.read_text(encoding="utf-8"))
            second_manifest = json.loads(second_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(first_manifest["source_pdf"]["page_index_zero_based"], 39)
            self.assertEqual(first_manifest["source_pdf"]["page_index_zero_based"], FIGURE_PAGE_INDEX_ZERO_BASED)
            self.assertEqual(first_manifest["render"]["rendered_page_size_px"], [1996, 2836])

            first_outputs = first_manifest["outputs"]
            second_outputs = second_manifest["outputs"]
            self.assertEqual(len(first_outputs), 6)
            self.assertEqual(len(second_outputs), 6)
            self.assertEqual(
                [(record["filename"], tuple(record["size_px"])) for record in first_outputs],
                list(EXPECTED_OUTPUTS),
            )
            self.assertEqual(
                [record["sha256"] for record in first_outputs],
                [record["sha256"] for record in second_outputs],
            )

            for record in first_outputs:
                image_path = first_dir / record["filename"]
                self.assertTrue(image_path.is_file())
                self.assertEqual(_sha256(image_path), record["sha256"])
                with Image.open(image_path) as image:
                    self.assertEqual(image.size, tuple(record["size_px"]))

            self.assertEqual(len(list(first_dir.glob("*.png"))), 6)
            self.assertEqual(len(list(second_dir.glob("*.png"))), 6)

    def test_out_of_bounds_page_fails_before_creating_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "should_not_exist"
            with self.assertRaisesRegex(ValueError, "out of bounds"):
                rebuild_from_pdf(SOURCE_PDF, output_dir, page_index=190)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
