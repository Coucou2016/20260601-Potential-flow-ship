from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.digitize_begovic2020_regular_wave import PDF_SHA256, digitize


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "begovic2020"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Begovic2020BenchmarkTests(unittest.TestCase):
    def test_frozen_source_and_generated_files_match_manifest(self) -> None:
        manifest = json.loads((BENCHMARK / "begovic2020_source_manifest.json").read_text(encoding="utf-8"))
        source = BENCHMARK / manifest["republication_source"]["pdf_path"]
        self.assertEqual(_sha256(source), PDF_SHA256)
        for relative_path, expected_hash in manifest["generated_files"].items():
            self.assertEqual(_sha256(BENCHMARK / relative_path), expected_hash)
        for relative_path, expected_hash in manifest["frozen_supporting_files"].items():
            self.assertEqual(_sha256(BENCHMARK / relative_path), expected_hash)

    def test_measured_running_state_covers_each_wave_test_speed(self) -> None:
        state = pd.read_csv(BENCHMARK / "begovic2014_mono_calm_water_running_state.csv")
        self.assertEqual(state.groupby("fn_b").size().to_dict(), {1.67: 1, 2.26: 1, 2.82: 1})
        np.testing.assert_allclose(state["speed_m_s"], [3.4, 4.6, 5.75], rtol=0.0, atol=1.0e-12)
        np.testing.assert_allclose(
            state["running_trim_deg"], [3.972, 4.174, 4.024], rtol=0.0, atol=1.0e-12
        )
        np.testing.assert_allclose(
            state["mean_wetted_length_m"], [1.49, 1.30, 1.16], rtol=0.0, atol=1.0e-12
        )
        self.assertTrue(state["wetted_length_source_label"].eq("Wetted_Length").all())
        self.assertTrue(
            state["wetted_length_interpretation"].eq("Savitsky_mean_wetted_length").all()
        )

    def test_motion_table_has_three_speeds_and_eight_points_per_speed(self) -> None:
        motion = pd.read_csv(BENCHMARK / "begovic2020_mono_efd_motion_digitized.csv")
        self.assertEqual(len(motion), 24)
        self.assertEqual(motion.groupby("fn_b").size().to_dict(), {1.67: 8, 2.26: 8, 2.82: 8})
        numeric = motion.select_dtypes(include=[np.number]).to_numpy(dtype=float)
        self.assertTrue(np.isfinite(numeric).all())
        self.assertTrue((motion["heave_rao_m_per_m"] > 0.0).all())
        self.assertTrue((motion["pitch_rao_rad_per_wave_slope"] > 0.0).all())

    def test_at_least_four_experimental_peaks_are_internally_bracketed(self) -> None:
        motion = pd.read_csv(BENCHMARK / "begovic2020_mono_efd_motion_digitized.csv")
        resolved: list[tuple[float, str]] = []
        for fn_b, group in motion.groupby("fn_b"):
            group = group.sort_values("lambda_over_l").reset_index(drop=True)
            for metric in ("heave_rao_m_per_m", "pitch_rao_rad_per_wave_slope"):
                peak_index = int(group[metric].to_numpy().argmax())
                if 0 < peak_index < len(group) - 1:
                    resolved.append((float(fn_b), metric))
        self.assertGreaterEqual(len(resolved), 4)
        self.assertGreaterEqual(len({speed for speed, _ in resolved}), 2)
        self.assertEqual({metric for _, metric in resolved}, {"heave_rao_m_per_m", "pitch_rao_rad_per_wave_slope"})
        self.assertNotIn((1.67, "pitch_rao_rad_per_wave_slope"), resolved)

    def test_digitizer_reproduces_committed_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = digitize(BENCHMARK / "source" / "jmse-08-00455-v2.pdf", output)
            self.assertEqual(result["motion_rows"], 24)
            for filename in (
                "begovic2020_mono_hull.csv",
                "begovic2020_regular_wave_conditions.csv",
                "begovic2020_mono_efd_motion_digitized.csv",
                "begovic2020_digitization_audit.csv",
            ):
                self.assertEqual((output / filename).read_bytes(), (BENCHMARK / filename).read_bytes())


if __name__ == "__main__":
    unittest.main()
