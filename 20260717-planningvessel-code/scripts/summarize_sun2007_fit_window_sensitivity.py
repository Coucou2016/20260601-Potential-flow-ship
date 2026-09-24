from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


CASES = (
    (16, "0.00-1.50", "outputs/sun2007_sigma14_fit_window_body24_sub16_d0p0_r1p5"),
    (16, "0.25-1.75", "outputs/sun2007_sigma14_fit_window_body24_sub16_d0p25_r1p5"),
    (16, "0.50-2.00", "outputs/sun2007_sigma14_fixed_jet_body24_sub16_heave_fig7p4_restoring"),
    (16, "0.25-2.00", "outputs/sun2007_sigma14_fit_window_body24_sub16_d0p25_r1p75"),
    (32, "0.00-1.50", "outputs/sun2007_sigma14_fit_window_body24_sub32_d0p0_r1p5"),
    (32, "0.25-1.75", "outputs/sun2007_sigma14_fit_window_body24_sub32_d0p25_r1p5"),
    (32, "0.50-2.00", "outputs/sun2007_sigma14_fixed_jet_body24_sub32_heave_fig7p4_restoring"),
    (32, "0.25-2.00", "outputs/sun2007_sigma14_fit_window_body24_sub32_d0p25_r1p75"),
)
COEFFICIENTS = ("A33", "A53", "B33", "B53")
POST_TRANSIENT_WINDOWS = ("0.25-1.75", "0.50-2.00", "0.25-2.00")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs" / "sun2007_sigma14_diagnostic_summary"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    sources: dict[str, str] = {}
    for substeps, window, relative_directory in CASES:
        directory = root / relative_directory
        coefficient_path = directory / "identified_coefficients_reprocessed.csv"
        manifest_path = directory / "postprocess_manifest.json"
        if not coefficient_path.is_file() or not manifest_path.is_file():
            raise FileNotFoundError(f"Fit-window case is incomplete: {directory}")
        sources[str(coefficient_path)] = _sha256(coefficient_path)
        sources[str(manifest_path)] = _sha256(manifest_path)
        table = pd.read_csv(coefficient_path)
        total = table[table["component"].eq("total")].set_index("coefficient")
        for coefficient in COEFFICIENTS:
            rows.append(
                {
                    "body_panels_per_side": 24,
                    "bem_substeps_per_plane": substeps,
                    "fit_window_cycles": window,
                    "coefficient": coefficient,
                    "value_nondimensional": float(
                        total.loc[coefficient, "value_nondimensional"]
                    ),
                    "harmonic_fit_residual_nrmse": float(
                        total.loc[coefficient, "harmonic_fit_residual_nrmse"]
                    ),
                    "restoring_subtraction": str(
                        total.loc[coefficient, "restoring_subtraction"]
                    ),
                    "response_calibration_used": False,
                }
            )
    raw = pd.DataFrame(rows)
    raw_path = output / "sigma14_heave_fit_window_sensitivity.csv"
    raw.to_csv(raw_path, index=False)

    checks: list[dict[str, object]] = []
    for substeps in (16, 32):
        selected = raw[
            raw["bem_substeps_per_plane"].eq(substeps)
            & raw["fit_window_cycles"].isin(POST_TRANSIENT_WINDOWS)
        ]
        for coefficient in COEFFICIENTS:
            values = selected[selected["coefficient"].eq(coefficient)][
                "value_nondimensional"
            ].to_numpy(dtype=float)
            reference = float(
                selected[
                    selected["coefficient"].eq(coefficient)
                    & selected["fit_window_cycles"].eq("0.50-2.00")
                ]["value_nondimensional"].iloc[0]
            )
            relative_span = float((values.max() - values.min()) / max(abs(reference), 1.0e-12))
            checks.append(
                {
                    "check": "post_transient_fit_window_sensitivity",
                    "bem_substeps_per_plane": substeps,
                    "fit_window_cycles": "0.25-1.75|0.50-2.00|0.25-2.00",
                    "coefficient": coefficient,
                    "relative_change": relative_span,
                    "limit": 0.05,
                    "status": "PASS" if relative_span <= 0.05 else "FAIL",
                }
            )
    for window in POST_TRANSIENT_WINDOWS:
        for coefficient in COEFFICIENTS:
            values = raw[
                raw["fit_window_cycles"].eq(window)
                & raw["coefficient"].eq(coefficient)
            ].set_index("bem_substeps_per_plane")["value_nondimensional"]
            coarse = float(values.loc[16])
            refined = float(values.loc[32])
            relative_change = abs(refined - coarse) / max(abs(refined), 1.0e-12)
            checks.append(
                {
                    "check": "time_step_16_to_32_by_fit_window",
                    "bem_substeps_per_plane": "16_to_32",
                    "fit_window_cycles": window,
                    "coefficient": coefficient,
                    "relative_change": relative_change,
                    "limit": 0.05,
                    "status": "PASS" if relative_change <= 0.05 else "FAIL",
                }
            )
    checks_path = output / "sigma14_heave_fit_window_checks.csv"
    with checks_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(checks[0]))
        writer.writeheader()
        writer.writerows(checks)

    manifest = {
        "source": "Sun_2007_sigma1p4_fit_window_sensitivity",
        "interpretation": (
            "Post-transient window stability is evaluated separately from 16-to-32 "
            "BEM-substep convergence; no response calibration is used."
        ),
        "source_sha256": sources,
        "raw_csv": str(raw_path),
        "raw_csv_sha256": _sha256(raw_path),
        "checks_csv": str(checks_path),
        "checks_csv_sha256": _sha256(checks_path),
        "response_calibration_used": False,
    }
    (output / "sigma14_heave_fit_window_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    print(checks_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
