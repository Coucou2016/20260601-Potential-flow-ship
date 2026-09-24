from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.digitize_troesch1992_experimental_coefficients import digitize


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "troesch1992_experimental_forced_motion_coefficients.csv"


def test_experimental_digitization_is_visible_only_and_traceable(tmp_path: Path) -> None:
    result = digitize(tmp_path / "troesch.csv")
    assert result["rows"] == 46
    table = pd.read_csv(result["output"])
    assert set(table["coefficient"]) == {
        "A33",
        "A35",
        "A53",
        "A55",
        "B33",
        "B35",
        "B53",
        "B55",
    }
    assert (table["series"] == "EXP_filled_marker").all()
    assert (table["marker_visibility"] == "isolated_visible").all()
    assert (table["response_calibration_used"] == False).all()  # noqa: E712
    assert table["omega_sqrt_B_over_g"].between(0.82, 2.01).all()
    assert (table["digitization_uncertainty_nondimensional"] > 0.0).all()
    assert (table["frequency_digitization_uncertainty"] > 0.0).all()


def test_committed_experimental_benchmark_reproduces_byte_for_byte(tmp_path: Path) -> None:
    result = digitize(tmp_path / BENCHMARK.name)
    assert Path(result["output"]).read_bytes() == BENCHMARK.read_bytes()
    manifest_path = BENCHMARK.with_name(BENCHMARK.stem + "_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["benchmark_role"] == "independent_EFD_digitization_not_acceptance_calibration"
    assert manifest["digitization"]["response_calibration_used"] is False
    assert manifest["digitization"]["visible_marker_count"] == 46
    assert hashlib.sha256(BENCHMARK.read_bytes()).hexdigest() == manifest["output_csv_sha256"]
    evidence = Path(manifest["coordinate_evidence"]["image"])
    assert evidence.exists()
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == manifest["coordinate_evidence"]["sha256"]
