from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT.parent / "20260729-文献收集" / "md" / "A3_images"
FROZEN = ROOT / "benchmarks" / "sun2007_fig2_6_wedge_similarity"
LEGACY = FROZEN / "legacy_column_median_v1"


class Sun2007Fig26DigitizationTests(unittest.TestCase):
    def test_frozen_benchmark_has_all_three_angles_and_quantities(self) -> None:
        with (FROZEN / "fig2_6_zhao_faltinsen_similarity_curves.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        cases = {(float(row["beta_deg"]), row["quantity"]) for row in rows}
        self.assertEqual(
            cases,
            {
                (10.0, "free_surface"),
                (10.0, "pressure"),
                (20.0, "free_surface"),
                (20.0, "pressure"),
                (30.0, "free_surface"),
                (30.0, "pressure"),
            },
        )
        self.assertTrue(all(row["reference_curve"].endswith("blue_dashed") for row in rows))
        free_surface = [row for row in rows if row["quantity"] == "free_surface"]
        self.assertTrue(
            all(
                row["branch_policy"]
                == "bottommost_contiguous_cluster_monotone_outer_branch"
                for row in free_surface
            )
        )

        # The legacy 10-degree extraction blended two separated branches at
        # pixel x=273 and retained an upper-only dash at x=272.
        beta10 = {
            int(row["pixel_x"]): float(row["pixel_y_median"])
            for row in free_surface
            if float(row["beta_deg"]) == 10.0
        }
        self.assertNotIn(272, beta10)
        self.assertEqual(beta10[273], 152.0)

        beta20_pressure = [
            row
            for row in rows
            if float(row["beta_deg"]) == 20.0 and row["quantity"] == "pressure"
        ]
        peak = max(float(row["y_nondimensional"]) for row in beta20_pressure)
        self.assertGreater(peak, 17.0)
        self.assertLess(peak, 18.5)

        manifest = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
        calibration = next(
            source["calibration"]
            for source in manifest["sources"]
            if source["beta_deg"] == 20.0 and source["quantity"] == "pressure"
        )
        self.assertEqual(calibration["y_pixel_at_value_1"], 21.0)
        self.assertEqual(calibration["y_value_1"], 20.0)
        self.assertEqual(
            manifest["supersedes"]["csv_sha256"],
            "27501c457dbe61fa2ad9c2bea020ed66780cb7ab6214f3c3f7317d045eb8c994",
        )

    def test_legacy_column_median_artifact_is_preserved(self) -> None:
        manifest = json.loads((LEGACY / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["csv_sha256"],
            "27501c457dbe61fa2ad9c2bea020ed66780cb7ab6214f3c3f7317d045eb8c994",
        )

    @unittest.skipUnless(SOURCE_DIR.is_dir(), "A3 extracted source images are unavailable")
    def test_free_surface_points_are_observed_bottommost_pixel_clusters(self) -> None:
        from scripts.digitize_sun2007_fig2_6_wedge_similarity import (
            SPECS,
            _contiguous_pixel_runs,
        )

        with (FROZEN / "fig2_6_zhao_faltinsen_similarity_curves.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))

        for spec in (item for item in SPECS if item.quantity == "free_surface"):
            rgb = np.asarray(Image.open(SOURCE_DIR / spec.image_name).convert("RGB"), dtype=np.int16)
            red, green, blue = np.moveaxis(rgb, -1, 0)
            mask = (blue >= 115) & ((blue - red) >= 25) & ((blue - green) >= 12)
            x0, y0, x1, y1 = spec.roi
            roi_mask = np.zeros(mask.shape, dtype=bool)
            roi_mask[y0 : y1 + 1, x0 : x1 + 1] = True
            mask &= roi_mask

            curve = [
                row
                for row in rows
                if float(row["beta_deg"]) == spec.beta_deg
                and row["quantity"] == "free_surface"
            ]
            running_lower_row: float | None = None
            for row in curve:
                pixel_x = int(row["pixel_x"])
                observed_rows = np.flatnonzero(mask[:, pixel_x])
                clusters = _contiguous_pixel_runs(observed_rows)
                bottommost = max(clusters, key=lambda values: float(np.median(values)))
                selected = float(row["pixel_y_median"])
                self.assertEqual(selected, float(np.median(bottommost)))
                if running_lower_row is not None:
                    self.assertGreaterEqual(selected, running_lower_row - 1.0)
                running_lower_row = (
                    selected
                    if running_lower_row is None
                    else max(running_lower_row, selected)
                )

    @unittest.skipUnless(SOURCE_DIR.is_dir(), "A3 extracted source images are unavailable")
    def test_digitization_is_byte_reproducible_from_source_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "digitize_sun2007_fig2_6_wedge_similarity.py"),
                    "--source-dir",
                    ".",
                    "--out",
                    str(out),
                ],
                check=True,
                cwd=SOURCE_DIR,
            )
            self.assertEqual(
                (out / "fig2_6_zhao_faltinsen_similarity_curves.csv").read_bytes(),
                (FROZEN / "fig2_6_zhao_faltinsen_similarity_curves.csv").read_bytes(),
            )
            generated = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            frozen = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
            generated.pop("source_directory")
            frozen.pop("source_directory")
            self.assertEqual(
                generated,
                {key: frozen[key] for key in generated},
            )
            self.assertIn("native_pdf_vector_extraction", frozen)
            self.assertIn("reference_resolution_policy", frozen)


if __name__ == "__main__":
    unittest.main()
