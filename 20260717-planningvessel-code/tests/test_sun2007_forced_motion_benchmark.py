from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

import pandas as pd


class Sun2007ForcedMotionBenchmarkTests(unittest.TestCase):
    def test_digitized_benchmark_is_complete_traceable_and_nonreciprocal(self) -> None:
        root = Path(__file__).resolve().parents[1]
        csv_path = root / "benchmarks" / "sun2007_troesch_forced_motion_coefficients.csv"
        manifest_path = csv_path.with_name(csv_path.stem + "_manifest.json")
        table = pd.read_csv(csv_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(len(table), 80)
        self.assertEqual(
            set(table["coefficient"]),
            {"A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55"},
        )
        counts = table.groupby(["model_variant", "coefficient"]).size()
        self.assertTrue((counts == 5).all())
        self.assertTrue((table["digitization_uncertainty_nondimensional"] > 0.0).all())
        self.assertTrue((table["digitization_uncertainty_nondimensional"] <= 0.12).all())

        uncorrected = table[
            table["model_variant"].eq("sun_2dt_without_stern_3d_correction")
        ]
        a35 = uncorrected[uncorrected["coefficient"].eq("A35")].sort_values(
            "omega_sqrt_B_over_g"
        )
        a53 = uncorrected[uncorrected["coefficient"].eq("A53")].sort_values(
            "omega_sqrt_B_over_g"
        )
        self.assertGreater(
            float(a35["value_nondimensional"].iloc[0] - a35["value_nondimensional"].iloc[-1]),
            1.5,
        )
        self.assertTrue((a53["value_nondimensional"] < 0.0).all())
        self.assertGreater(
            float((a35["value_nondimensional"].to_numpy() - a53["value_nondimensional"].to_numpy()).mean()),
            0.5,
        )
        for coefficient in ("B33", "B35", "B53", "B55"):
            values = uncorrected[uncorrected["coefficient"].eq(coefficient)][
                "value_nondimensional"
            ]
            self.assertLess(float(values.max() - values.min()), 0.1)

        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        self.assertEqual(digest, manifest["output_csv_sha256"])
        self.assertFalse(bool(manifest["digitization"]["response_calibration_used"]))
        self.assertEqual(
            manifest["benchmark_role"],
            "same_model_NUM_reproduction_not_independent_EFD",
        )
        evidence = manifest["coordinate_evidence"]
        evidence_path = Path(evidence["image"])
        self.assertTrue(evidence_path.exists())
        self.assertEqual(evidence["pixel_size"], [2080, 2955])
        self.assertEqual(
            hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            evidence["sha256"],
        )
        self.assertEqual(manifest["source_location"], "Sun thesis, printed page 141, PDF page 153, Figs. 7.13-7.14")


if __name__ == "__main__":
    unittest.main()
