from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.digitize_sun2007_fig7_4_restoring import (
    PANELS,
    TROESCH_EXPERIMENTAL_PANELS,
    TROESCH_HEAVE_EXPERIMENTAL_PANELS,
    TROESCH_PITCH_EXPERIMENTAL_PANELS,
    digitize,
)


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "sun2007_fig7_4_restoring"
TROESCH_BENCHMARK = ROOT / "benchmarks" / "sun2007_fig7_4_troesch_restoring"


def _sha256(path: Path) -> str:
    with open(str(path), "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


class Sun2007Fig74RestoringBenchmarkTests(unittest.TestCase):
    def test_committed_matrix_is_complete_physical_and_traceable(self) -> None:
        matrix = pd.read_csv(BENCHMARK / "restoring_matrix.csv").set_index("coefficient")
        manifest = json.loads((BENCHMARK / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(set(matrix.index), {"C33", "C35", "C53", "C55"})
        np.testing.assert_allclose(
            matrix.loc[["C33", "C35", "C53", "C55"], "value"],
            [3264.2405760880692, -1104.1036338948552, 804.2237875511472, 305.02450004564474],
            rtol=0.0,
            atol=1.0e-8,
        )
        self.assertTrue((matrix["lower_pixel_envelope"] < matrix["value"]).all())
        self.assertTrue((matrix["value"] < matrix["upper_pixel_envelope"]).all())
        self.assertEqual(manifest["source"]["figure"], "7.4(a-d)")
        self.assertEqual(manifest["source"]["equation"], "7.18")
        self.assertEqual(manifest["source"]["figure_pdf_page_1_based"], 140)
        self.assertFalse(bool(manifest["response_calibration_used"]))

        for source in manifest["sources"]:
            self.assertEqual(_sha256(Path(source["image"])), source["sha256"])
        self.assertEqual(
            _sha256(Path(manifest["source"]["pdf"])),
            manifest["source"]["pdf_sha256"],
        )
        for filename, digest in manifest["generated_files"].items():
            self.assertEqual(_sha256(BENCHMARK / filename), digest)

    def test_digitizer_reproduces_committed_tables(self) -> None:
        source_images = Path(
            json.loads((BENCHMARK / "manifest.json").read_text(encoding="utf-8"))["sources"][0]["image"]
        ).parent
        with tempfile.TemporaryDirectory() as temporary:
            result = digitize(source_images, Path(temporary))
            self.assertEqual(result["point_rows"], 28)
            self.assertEqual(result["matrix_rows"], 4)
            self.assertEqual(len(PANELS), 4)
            for filename in (
                "digitized_points.csv",
                "restoring_matrix.csv",
                "restoring_matrices.csv",
            ):
                self.assertEqual(
                    (Path(temporary) / filename).read_bytes(),
                    (BENCHMARK / filename).read_bytes(),
                )

    def test_troesch_heave_experimental_series_is_separate_and_physical(self) -> None:
        source_images = Path(
            json.loads((BENCHMARK / "manifest.json").read_text(encoding="utf-8"))["sources"][0]["image"]
        ).parent
        with tempfile.TemporaryDirectory() as temporary:
            result = digitize(
                source_images,
                Path(temporary),
                panels=TROESCH_HEAVE_EXPERIMENTAL_PANELS,
                series_label="Troesch_experimental_square_marker",
            )
            matrix = pd.read_csv(Path(temporary) / "restoring_matrix.csv").set_index(
                "coefficient"
            )
            points = pd.read_csv(Path(temporary) / "digitized_points.csv")
            self.assertEqual(result["point_rows"], 14)
            self.assertEqual(result["matrix_rows"], 2)
            self.assertEqual(set(matrix.index), {"C33", "C53"})
            self.assertTrue(
                (points["series"] == "Troesch_experimental_square_marker").all()
            )
            self.assertGreater(float(matrix.loc["C33", "value"]), 3000.0)
            self.assertLess(float(matrix.loc["C33", "value"]), 3400.0)
            self.assertGreater(float(matrix.loc["C53", "value"]), 600.0)
            self.assertLess(float(matrix.loc["C53", "value"]), 720.0)
            self.assertLess(
                float(matrix.loc["C53", "value"]),
                float(
                    pd.read_csv(BENCHMARK / "restoring_matrix.csv")
                    .set_index("coefficient")
                    .loc["C53", "value"]
                ),
            )

    def test_troesch_complete_experimental_series_has_four_physical_slopes(self) -> None:
        source_images = Path(
            json.loads((BENCHMARK / "manifest.json").read_text(encoding="utf-8"))["sources"][0]["image"]
        ).parent
        with tempfile.TemporaryDirectory() as temporary:
            result = digitize(
                source_images,
                Path(temporary),
                panels=TROESCH_EXPERIMENTAL_PANELS,
                series_label="Troesch_experimental_square_marker",
            )
            matrix = pd.read_csv(Path(temporary) / "restoring_matrix.csv").set_index(
                "coefficient"
            )
            self.assertEqual(result["point_rows"], 28)
            self.assertEqual(result["matrix_rows"], 4)
            self.assertEqual(len(TROESCH_PITCH_EXPERIMENTAL_PANELS), 2)
            self.assertEqual(set(matrix.index), {"C33", "C35", "C53", "C55"})
            self.assertGreater(float(matrix.loc["C33", "value"]), 0.0)
            self.assertLess(float(matrix.loc["C35", "value"]), 0.0)
            self.assertGreater(float(matrix.loc["C53", "value"]), 0.0)
            self.assertGreater(float(matrix.loc["C55", "value"]), 0.0)
            self.assertTrue((matrix["response_calibration_used"] == False).all())  # noqa: E712

    def test_committed_troesch_matrix_is_complete_and_reproducible(self) -> None:
        matrix = pd.read_csv(TROESCH_BENCHMARK / "restoring_matrix.csv").set_index(
            "coefficient"
        )
        manifest = json.loads(
            (TROESCH_BENCHMARK / "manifest.json").read_text(encoding="utf-8")
        )
        np.testing.assert_allclose(
            matrix.loc[["C33", "C35", "C53", "C55"], "value"],
            [
                3221.334061771609,
                -905.0589665011021,
                661.5515529976267,
                199.65286706047092,
            ],
            rtol=0.0,
            atol=1.0e-8,
        )
        self.assertEqual(
            manifest["benchmark"],
            "Sun_2007_Fig7.4_Troesch_experimental_square_marker_zero_offset_slopes",
        )
        self.assertFalse(bool(manifest["response_calibration_used"]))
        for filename, digest in manifest["generated_files"].items():
            self.assertEqual(_sha256(TROESCH_BENCHMARK / filename), digest)


if __name__ == "__main__":
    unittest.main()
