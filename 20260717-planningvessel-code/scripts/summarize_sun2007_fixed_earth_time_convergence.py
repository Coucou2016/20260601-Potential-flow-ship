from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


COEFFICIENTS = ("A33", "A53", "B33", "B53")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_case(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Each --case must use LABEL=PATH.")
    label, path = value.split("=", 1)
    if not label.strip() or not path.strip():
        raise argparse.ArgumentTypeError("Each --case must use non-empty LABEL=PATH.")
    return label.strip(), Path(path.strip())


def _read_total_coefficients(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["component"] == "total" and row["coefficient"] in COEFFICIENTS
        ]
    result = {row["coefficient"]: row for row in rows}
    missing = sorted(set(COEFFICIENTS) - set(result))
    if missing:
        raise ValueError(f"Missing total coefficients in {path}: {missing}.")
    return result


def _read_reference(path: Path) -> dict[str, tuple[float, float]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["model_variant"] == "sun_2dt_without_stern_3d_correction"
            and abs(float(row["omega_sqrt_B_over_g"]) - 1.4) <= 1.0e-12
            and row["coefficient"] in COEFFICIENTS
        ]
    result = {
        row["coefficient"]: (
            float(row["value_nondimensional"]),
            float(row["digitization_uncertainty_nondimensional"]),
        )
        for row in rows
    }
    missing = sorted(set(COEFFICIENTS) - set(result))
    if missing:
        raise ValueError(f"Missing Fig. 7.13 references in {path}: {missing}.")
    return result


def _source_time_step(reprocessed_csv: Path) -> tuple[float | None, Path | None]:
    manifest_path = reprocessed_csv.parent / "postprocess_manifest.json"
    if not manifest_path.exists():
        return None, None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    timeseries = Path(manifest["timeseries"])
    diagnostics_path = timeseries.parent / "run_diagnostics.json"
    if not diagnostics_path.exists():
        return None, diagnostics_path
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    if not diagnostics:
        return None, diagnostics_path
    return float(diagnostics[0]["time_step_s"]), diagnostics_path


def summarize(
    cases: list[tuple[str, Path]],
    *,
    benchmark_path: Path,
    output: Path,
    relative_limit: float = 0.05,
) -> dict[str, object]:
    if len(cases) < 2:
        raise ValueError("At least two ordered convergence cases are required.")
    output.mkdir(parents=True, exist_ok=True)
    reference = _read_reference(benchmark_path)
    value_rows: list[dict[str, object]] = []
    values_by_case: dict[str, dict[str, float]] = {}
    input_files: list[Path] = [benchmark_path]
    for order, (label, input_path) in enumerate(cases):
        path = input_path.resolve()
        coefficients = _read_total_coefficients(path)
        time_step_s, diagnostics_path = _source_time_step(path)
        input_files.append(path)
        if diagnostics_path is not None and diagnostics_path.exists():
            input_files.append(diagnostics_path)
        values_by_case[label] = {}
        for coefficient in COEFFICIENTS:
            row = coefficients[coefficient]
            value = float(row["value_nondimensional"])
            target, uncertainty = reference[coefficient]
            values_by_case[label][coefficient] = value
            value_rows.append(
                {
                    "case_order": order,
                    "case_label": label,
                    "time_step_s": time_step_s,
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "harmonic_fit_residual_nrmse": float(
                        row["harmonic_fit_residual_nrmse"]
                    ),
                    "sun_fig7_13_value": target,
                    "sun_fig7_13_digitization_uncertainty": uncertainty,
                    "reference_relative_error": abs(value - target)
                    / max(abs(target), 1.0e-15),
                }
            )

    change_rows: list[dict[str, object]] = []
    labels = [label for label, _ in cases]
    for coarse_label, fine_label in zip(labels[:-1], labels[1:]):
        for coefficient in COEFFICIENTS:
            coarse = values_by_case[coarse_label][coefficient]
            fine = values_by_case[fine_label][coefficient]
            _, uncertainty = reference[coefficient]
            absolute_change = abs(fine - coarse)
            relative_change = absolute_change / max(abs(fine), 1.0e-15)
            change_rows.append(
                {
                    "coarse_case": coarse_label,
                    "fine_case": fine_label,
                    "coefficient": coefficient,
                    "coarse_value": coarse,
                    "fine_value": fine,
                    "absolute_change": absolute_change,
                    "relative_change": relative_change,
                    "relative_limit": relative_limit,
                    "strict_relative_status": (
                        "PASS" if relative_change <= relative_limit else "FAIL"
                    ),
                    "change_over_digitization_uncertainty": (
                        absolute_change / uncertainty
                    ),
                    "absolute_change_within_digitization_uncertainty": (
                        absolute_change <= uncertainty
                    ),
                }
            )

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    values_path = output / "coefficient_values.csv"
    changes_path = output / "adjacent_changes.csv"
    write_csv(values_path, value_rows)
    write_csv(changes_path, change_rows)
    latest_pair = change_rows[-len(COEFFICIENTS) :]
    result: dict[str, object] = {
        "schema": "sun2007_fixed_earth_time_convergence_v1",
        "status": (
            "PASS"
            if all(row["strict_relative_status"] == "PASS" for row in latest_pair)
            else "FAIL"
        ),
        "criterion": (
            "all four raw adjacent relative changes must be <=5%; digitization "
            "uncertainty is diagnostic and does not replace the strict gate"
        ),
        "latest_pair": [labels[-2], labels[-1]],
        "relative_limit": relative_limit,
        "failed_coefficients": [
            row["coefficient"]
            for row in latest_pair
            if row["strict_relative_status"] == "FAIL"
        ],
        "response_calibration_used": False,
        "inputs": [
            {"path": str(path.resolve()), "sha256": _sha256(path.resolve())}
            for path in dict.fromkeys(input_files)
        ],
        "outputs": {
            "coefficient_values": values_path.name,
            "adjacent_changes": changes_path.name,
        },
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize source-matched Sun fixed-Earth time convergence."
    )
    parser.add_argument("--case", action="append", type=_parse_case, required=True)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmarks/sun2007_troesch_forced_motion_coefficients.csv"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(
        args.case,
        benchmark_path=args.benchmark.resolve(),
        output=args.out.resolve(),
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
