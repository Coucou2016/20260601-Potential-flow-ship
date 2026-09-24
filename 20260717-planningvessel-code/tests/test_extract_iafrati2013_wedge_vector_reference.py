from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "benchmarks" / "iafrati2013_self_similar_wedge"
SOURCE_PDF = FROZEN / "cfg_5-20_arxiv1212.6699v2.pdf"
ARTICLE_PDF = FROZEN / "iafrati2013_arxiv1212.6699v2.pdf"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Iafrati2013VectorReferenceTests(unittest.TestCase):
    def test_frozen_vector_source_and_outer_branch_are_physical(self) -> None:
        self.assertEqual(
            _sha256(SOURCE_PDF),
            "da9adba37a1991bd206154265bebdf8878e1b81eceea8a581cd1afc2b3f11122",
        )
        self.assertEqual(
            _sha256(ARTICLE_PDF),
            "5b13b09118ac32a2a7257ddbdd55f14561c886d2f87a3a58b706e6e51c887559",
        )
        with (FROZEN / "iafrati2013_20deg_outer_free_surface.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 59)
        self.assertTrue(all(float(row["beta_deg"]) == 20.0 for row in rows))
        xi = np.asarray([float(row["x_nondimensional"]) for row in rows])
        eta = np.asarray([float(row["y_nondimensional"]) for row in rows])
        self.assertTrue(np.all(np.diff(xi) > 0.0))
        self.assertTrue(np.all(np.diff(eta) <= 1.0e-12))
        self.assertAlmostEqual(xi[0], 4.3121693121693125)
        self.assertAlmostEqual(eta[0], 0.4404761904761907)
        self.assertAlmostEqual(xi[-1], 40.0)

        manifest = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
        vector = manifest["vector_free_surface_reference"]
        roots = [profile["root_xi"] for profile in vector["candidate_profiles"]]
        self.assertEqual(len(roots), 5)
        self.assertAlmostEqual(min(roots), 4.371693121693122)
        self.assertFalse(manifest["solver_reads_this_file"])
        self.assertEqual(
            manifest["scalar_reference"]["csv_sha256"],
            "e1e3441db748733a95c691d6029b5cb1791556bc2c0e033a4baf0575b34fb8f6",
        )
        self.assertFalse(manifest["response_calibration_used"])
        self.assertEqual(
            vector["role"], "independent_cross_audit_not_acceptance_replacement"
        )

    def test_vector_extraction_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "extract_iafrati2013_wedge_vector_reference.py"),
                    "--source-pdf",
                    str(SOURCE_PDF),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd=ROOT,
            )
            self.assertEqual(
                (out / "iafrati2013_20deg_outer_free_surface.csv").read_bytes(),
                (FROZEN / "iafrati2013_20deg_outer_free_surface.csv").read_bytes(),
            )
            self.assertEqual(
                (out / "manifest.json").read_bytes(),
                (FROZEN / "manifest.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
