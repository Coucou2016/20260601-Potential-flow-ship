from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


COEFFICIENTS = ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55")
HEAVE_COEFFICIENTS = {"A33", "A53", "B33", "B53"}
PITCH_COEFFICIENTS = set(COEFFICIENTS) - HEAVE_COEFFICIENTS
CONTEXT_KEYS = (
    "target_identifier",
    "beam_m",
    "deadrise_deg",
    "trim_deg",
    "fn_b",
    "mean_wetted_length_over_b",
    "lcg_from_transom_m",
    "rho_water_kg_m3",
    "gravity_m_s2",
    "matrix_coordinate_contract",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty diagnostic table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    snapshot_path = run_dir / "run_input_snapshot.json"
    coefficients_path = run_dir / "identified_coefficients.csv"
    if not snapshot_path.exists() or not coefficients_path.exists():
        raise FileNotFoundError(f"Missing run snapshot or coefficients in {run_dir}")
    snapshot = _read_json(snapshot_path)
    rows = _read_csv(coefficients_path)
    if not rows:
        raise ValueError(f"No coefficient rows in {coefficients_path}")
    if _as_bool(snapshot.get("response_calibration_used", False)) or any(
        _as_bool(row.get("response_calibration_used", False)) for row in rows
    ):
        raise ValueError("Response-calibrated coefficients are forbidden in the source audit.")
    return snapshot, rows


def _context(snapshot: dict[str, Any]) -> dict[str, Any]:
    source = snapshot.get("derived_target_context", {})
    missing = [key for key in CONTEXT_KEYS if key not in source]
    if missing:
        raise ValueError(f"Run snapshot lacks target context fields: {missing}")
    return {key: source[key] for key in CONTEXT_KEYS}


def _total_values(rows: list[dict[str, str]]) -> tuple[float, dict[str, float]]:
    total = [row for row in rows if row["component"] == "total"]
    coefficients = {row["coefficient"]: float(row["value_nondimensional"]) for row in total}
    if set(coefficients) != set(COEFFICIENTS):
        raise ValueError("The baseline run must contain all eight total coefficients.")
    sigmas = {float(row["sigma"]) for row in total}
    if len(sigmas) != 1:
        raise ValueError("The source audit accepts exactly one nondimensional frequency.")
    return sigmas.pop(), coefficients


def _column_values(
    rows: list[dict[str, str]], expected: set[str]
) -> tuple[float, dict[str, float]]:
    total = [row for row in rows if row["component"] == "total"]
    values = {row["coefficient"]: float(row["value_nondimensional"]) for row in total}
    if set(values) != expected:
        raise ValueError(f"Corrected column does not contain {sorted(expected)}.")
    sigmas = {float(row["sigma"]) for row in total}
    if len(sigmas) != 1:
        raise ValueError("Each corrected column must contain exactly one frequency.")
    return sigmas.pop(), values


def _benchmark_values(
    rows: list[dict[str, str]],
    *,
    sigma: float,
    model_variant: str,
    tolerance: float,
) -> dict[str, float]:
    selected = {
        row["coefficient"]: float(row["value_nondimensional"])
        for row in rows
        if row["model_variant"] == model_variant
        and abs(float(row["omega_sqrt_B_over_g"]) - sigma) <= tolerance
    }
    if set(selected) != set(COEFFICIENTS):
        raise ValueError(
            f"Benchmark lacks all eight {model_variant} coefficients at sigma={sigma}."
        )
    return selected


def _load_center(lcg_over_beam: float, force: float, moment: float) -> float:
    if abs(force) <= 1.0e-12:
        return math.nan
    return lcg_over_beam + moment / force


def audit_longitudinal_load_distribution(
    baseline_run: Path,
    corrected_heave_run: Path,
    corrected_pitch_run: Path,
    *,
    output: Path,
    benchmark: Path,
    frequency_tolerance: float = 5.0e-3,
) -> dict[str, Any]:
    baseline_run = baseline_run.resolve()
    corrected_heave_run = corrected_heave_run.resolve()
    corrected_pitch_run = corrected_pitch_run.resolve()
    output = output.resolve()
    benchmark = benchmark.resolve()
    if frequency_tolerance <= 0.0:
        raise ValueError("frequency_tolerance must be positive.")
    output.mkdir(parents=True, exist_ok=True)

    baseline_snapshot, baseline_rows = _load_run(baseline_run)
    heave_snapshot, heave_rows = _load_run(corrected_heave_run)
    pitch_snapshot, pitch_rows = _load_run(corrected_pitch_run)
    contexts = [_context(value) for value in (baseline_snapshot, heave_snapshot, pitch_snapshot)]
    if contexts[1:] != contexts[:1] * 2:
        raise ValueError("Baseline and corrected runs do not share the same target context.")
    if not bool(heave_snapshot.get("arguments", {}).get("transom_keel_reduction")):
        raise ValueError("The corrected heave source is not the fixed 0.5B keel reduction.")
    if not bool(pitch_snapshot.get("arguments", {}).get("transom_keel_reduction")):
        raise ValueError("The corrected pitch source is not the fixed 0.5B keel reduction.")

    sigma, baseline = _total_values(baseline_rows)
    heave_sigma, corrected_heave = _column_values(heave_rows, HEAVE_COEFFICIENTS)
    pitch_sigma, corrected_pitch = _column_values(pitch_rows, PITCH_COEFFICIENTS)
    if max(abs(heave_sigma - sigma), abs(pitch_sigma - sigma)) > frequency_tolerance:
        raise ValueError("Baseline and corrected runs use different frequencies.")
    corrected = {**corrected_heave, **corrected_pitch}

    benchmark_rows = _read_csv(benchmark)
    target_raw = _benchmark_values(
        benchmark_rows,
        sigma=sigma,
        model_variant="sun_2dt_without_stern_3d_correction",
        tolerance=frequency_tolerance,
    )
    target_corrected = _benchmark_values(
        benchmark_rows,
        sigma=sigma,
        model_variant="sun_2dt_with_stern_3d_correction",
        tolerance=frequency_tolerance,
    )

    component_rows: list[dict[str, Any]] = []
    for row in baseline_rows:
        coefficient = row["coefficient"]
        if coefficient not in COEFFICIENTS:
            continue
        value = float(row["value_nondimensional"])
        total_value = baseline[coefficient]
        component_rows.append(
            {
                "sigma": sigma,
                "coefficient": coefficient,
                "component": row["component"],
                "value_nondimensional": value,
                "fraction_of_calculated_total": (
                    value / total_value if abs(total_value) > 1.0e-12 else math.nan
                ),
                "calculated_total_nondimensional": total_value,
                "source_raw_target_nondimensional": target_raw[coefficient],
                "raw_target_minus_calculated": target_raw[coefficient] - total_value,
            }
        )

    lcg_over_beam = float(contexts[0]["lcg_from_transom_m"]) / float(
        contexts[0]["beam_m"]
    )
    center_rows: list[dict[str, Any]] = []
    for column, force_name, moment_name in (
        ("forced_heave", "B33", "B53"),
        ("forced_pitch", "B35", "B55"),
    ):
        force = baseline[force_name]
        moment = baseline[moment_name]
        target_force = target_raw[force_name]
        target_moment = target_raw[moment_name]
        delta_force = target_force - force
        delta_moment = target_moment - moment
        center_rows.append(
            {
                "sigma": sigma,
                "forced_motion_column": column,
                "force_coefficient": force_name,
                "moment_coefficient": moment_name,
                "lcg_from_transom_over_beam": lcg_over_beam,
                "calculated_force": force,
                "calculated_moment": moment,
                "calculated_center_from_transom_over_beam": _load_center(
                    lcg_over_beam, force, moment
                ),
                "source_raw_target_force": target_force,
                "source_raw_target_moment": target_moment,
                "source_raw_target_center_from_transom_over_beam": _load_center(
                    lcg_over_beam, target_force, target_moment
                ),
                "center_error_over_beam": _load_center(lcg_over_beam, force, moment)
                - _load_center(lcg_over_beam, target_force, target_moment),
                "required_increment_force": delta_force,
                "required_increment_moment": delta_moment,
                "required_increment_center_from_transom_over_beam": _load_center(
                    lcg_over_beam, delta_force, delta_moment
                ),
            }
        )

    delta_rows: list[dict[str, Any]] = []
    for coefficient in COEFFICIENTS:
        calculated_delta = corrected[coefficient] - baseline[coefficient]
        source_delta = target_corrected[coefficient] - target_raw[coefficient]
        delta_rows.append(
            {
                "sigma": sigma,
                "coefficient": coefficient,
                "calculated_raw": baseline[coefficient],
                "calculated_corrected_0p5B": corrected[coefficient],
                "calculated_correction_delta": calculated_delta,
                "source_raw_NUM": target_raw[coefficient],
                "source_corrected_NUM": target_corrected[coefficient],
                "source_correction_delta": source_delta,
                "correction_delta_error": calculated_delta - source_delta,
                "correction_delta_relative_error": (
                    abs(calculated_delta - source_delta) / abs(source_delta)
                    if abs(source_delta) > 1.0e-12
                    else math.nan
                ),
            }
        )

    component_path = output / "coefficient_component_breakdown.csv"
    center_path = output / "damping_load_center_audit.csv"
    delta_path = output / "transom_correction_delta_audit.csv"
    _write_csv(component_path, component_rows)
    _write_csv(center_path, center_rows)
    _write_csv(delta_path, delta_rows)

    manifest: dict[str, Any] = {
        "schema": "sun2007_longitudinal_load_distribution_audit_v1",
        "status": "DIAGNOSTIC_ONLY_NOT_ACCEPTANCE",
        "sigma": sigma,
        "coordinate_contract": contexts[0]["matrix_coordinate_contract"],
        "lcg_from_transom_over_beam": lcg_over_beam,
        "response_calibration_used": False,
        "interpretation_limits": [
            "Required-increment centers are algebraic diagnostics, not fitted load patches.",
            "Sun NUM is a same-model reproduction target, not independent experimental validation.",
            "No correction length or coefficient is inferred from the target response.",
        ],
        "sources": {
            "baseline_run": {
                "directory": str(baseline_run),
                "input_snapshot_sha256": _sha256(baseline_run / "run_input_snapshot.json"),
                "identified_coefficients_sha256": _sha256(
                    baseline_run / "identified_coefficients.csv"
                ),
            },
            "corrected_heave_run": {
                "directory": str(corrected_heave_run),
                "input_snapshot_sha256": _sha256(
                    corrected_heave_run / "run_input_snapshot.json"
                ),
                "identified_coefficients_sha256": _sha256(
                    corrected_heave_run / "identified_coefficients.csv"
                ),
            },
            "corrected_pitch_run": {
                "directory": str(corrected_pitch_run),
                "input_snapshot_sha256": _sha256(
                    corrected_pitch_run / "run_input_snapshot.json"
                ),
                "identified_coefficients_sha256": _sha256(
                    corrected_pitch_run / "identified_coefficients.csv"
                ),
            },
            "benchmark": {
                "path": str(benchmark),
                "sha256": _sha256(benchmark),
                "role": "same_model_NUM_reproduction_not_independent_EFD",
            },
        },
        "outputs": {
            component_path.name: _sha256(component_path),
            center_path.name: _sha256(center_path),
            delta_path.name: _sha256(delta_path),
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Sun 2007 longitudinal load components and source correction deltas."
    )
    parser.add_argument("baseline_run", type=Path)
    parser.add_argument("corrected_heave_run", type=Path)
    parser.add_argument("corrected_pitch_run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmarks/sun2007_troesch_forced_motion_coefficients.csv"),
    )
    parser.add_argument("--frequency-tolerance", type=float, default=5.0e-3)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = audit_longitudinal_load_distribution(
        args.baseline_run,
        args.corrected_heave_run,
        args.corrected_pitch_run,
        output=args.out,
        benchmark=args.benchmark,
        frequency_tolerance=args.frequency_tolerance,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
