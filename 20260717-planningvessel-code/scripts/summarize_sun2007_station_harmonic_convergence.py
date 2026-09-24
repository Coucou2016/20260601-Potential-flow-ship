from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


CUMULATIVE_CHANNELS = (
    "cumulative_sine_vertical_force_n",
    "cumulative_sine_pitch_moment_nm",
    "cumulative_cosine_vertical_force_n",
    "cumulative_cosine_pitch_moment_nm",
)


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


def _read_distribution(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 2:
        raise ValueError(f"Station harmonic distribution is empty: {path}.")
    required = {"x_from_transom_m", *CUMULATIVE_CHANNELS}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}.")
    result = {
        name: np.asarray([float(row[name]) for row in rows], dtype=float)
        for name in required
    }
    x = result["x_from_transom_m"]
    if np.any(np.diff(x) <= 0.0):
        raise ValueError(f"x_from_transom_m must be strictly increasing: {path}.")
    return result


def summarize_station_harmonic_convergence(
    cases: list[tuple[str, Path]],
    *,
    edges_m: list[float],
    output: Path,
    omega_rad_s: float,
    heave_amplitude_m: float,
    rho_water_kg_m3: float,
    beam_m: float,
) -> dict[str, object]:
    if len(cases) < 2:
        raise ValueError("At least two ordered convergence cases are required.")
    edges = np.asarray(edges_m, dtype=float)
    if len(edges) < 2 or np.any(np.diff(edges) <= 0.0):
        raise ValueError("edges_m must contain at least two increasing values.")
    if min(omega_rad_s, heave_amplitude_m, rho_water_kg_m3, beam_m) <= 0.0:
        raise ValueError("Physical scales must be positive.")

    output.mkdir(parents=True, exist_ok=True)
    labels = [label for label, _ in cases]
    distributions: dict[str, dict[str, np.ndarray]] = {}
    resolved_paths: dict[str, Path] = {}
    for label, raw_path in cases:
        if label in distributions:
            raise ValueError(f"Duplicate case label: {label}.")
        path = raw_path.resolve()
        data = _read_distribution(path)
        x = data["x_from_transom_m"]
        if edges[0] < x[0] - 1.0e-12 or edges[-1] > x[-1] + 1.0e-12:
            raise ValueError(
                f"Requested edges [{edges[0]}, {edges[-1]}] exceed {label} range "
                f"[{x[0]}, {x[-1]}]."
            )
        distributions[label] = data
        resolved_paths[label] = path

    interval_rows: list[dict[str, object]] = []
    interval_values: dict[tuple[str, int, str], float] = {}
    for case_order, label in enumerate(labels):
        data = distributions[label]
        x = data["x_from_transom_m"]
        for interval_index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
            for channel in CUMULATIVE_CHANNELS:
                cumulative = data[channel]
                contribution = float(
                    np.interp(upper, x, cumulative) - np.interp(lower, x, cumulative)
                )
                interval_values[(label, interval_index, channel)] = contribution
                interval_rows.append(
                    {
                        "case_order": case_order,
                        "case_label": label,
                        "interval_index": interval_index,
                        "lower_x_m": lower,
                        "upper_x_m": upper,
                        "channel": channel,
                        "interval_contribution": contribution,
                    }
                )

    change_rows: list[dict[str, object]] = []
    pair_summaries: list[dict[str, object]] = []
    a53_scale = -1.0 / (
        omega_rad_s**2 * heave_amplitude_m * rho_water_kg_m3 * beam_m**4
    )
    for coarse, fine in zip(labels[:-1], labels[1:]):
        sine_moment_deltas: list[float] = []
        for interval_index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
            for channel in CUMULATIVE_CHANNELS:
                coarse_value = interval_values[(coarse, interval_index, channel)]
                fine_value = interval_values[(fine, interval_index, channel)]
                delta = fine_value - coarse_value
                row: dict[str, object] = {
                    "coarse_case": coarse,
                    "fine_case": fine,
                    "interval_index": interval_index,
                    "lower_x_m": lower,
                    "upper_x_m": upper,
                    "channel": channel,
                    "coarse_contribution": coarse_value,
                    "fine_contribution": fine_value,
                    "fine_minus_coarse": delta,
                }
                if channel == "cumulative_sine_pitch_moment_nm":
                    row["a53_nondimensional_change"] = delta * a53_scale
                    sine_moment_deltas.append(delta)
                else:
                    row["a53_nondimensional_change"] = ""
                change_rows.append(row)

        total_sine_moment_delta = float(sum(sine_moment_deltas))
        dominant_index = int(np.argmax(np.abs(sine_moment_deltas)))
        dominant_delta = float(sine_moment_deltas[dominant_index])
        pair_summaries.append(
            {
                "coarse_case": coarse,
                "fine_case": fine,
                "total_sine_pitch_moment_change_nm": total_sine_moment_delta,
                "total_a53_nondimensional_change": total_sine_moment_delta * a53_scale,
                "dominant_interval_index": dominant_index,
                "dominant_interval_lower_x_m": float(edges[dominant_index]),
                "dominant_interval_upper_x_m": float(edges[dominant_index + 1]),
                "dominant_interval_sine_pitch_moment_change_nm": dominant_delta,
                "dominant_interval_fraction_of_sum_abs_changes": abs(dominant_delta)
                / max(float(np.sum(np.abs(sine_moment_deltas))), np.finfo(float).eps),
            }
        )

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    interval_path = output / "interval_contributions.csv"
    changes_path = output / "adjacent_interval_changes.csv"
    write_csv(interval_path, interval_rows)
    write_csv(changes_path, change_rows)
    result: dict[str, object] = {
        "schema": "sun2007_station_harmonic_convergence_v1",
        "method": (
            "difference cumulative fitted sectional harmonics over fixed longitudinal "
            "intervals; A53 change follows Sun 2007 Eq. 7.46"
        ),
        "coordinate_contract": (
            "x_from_transom_positive_forward; force_up; moment_bow_up_about_cg; "
            "forced_heave=-amplitude*sin(omega*t)"
        ),
        "edges_m": edges.tolist(),
        "pair_summaries": pair_summaries,
        "response_calibration_used": False,
        "inputs": [
            {
                "label": label,
                "path": str(resolved_paths[label]),
                "sha256": _sha256(resolved_paths[label]),
            }
            for label in labels
        ],
        "outputs": {
            "interval_contributions": interval_path.name,
            "adjacent_interval_changes": changes_path.name,
        },
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Localize Sun fixed-Earth time-convergence changes along the hull."
    )
    parser.add_argument("--case", action="append", type=_parse_case, required=True)
    parser.add_argument("--edge-m", action="append", type=float, required=True)
    parser.add_argument("--omega-rad-s", type=float, required=True)
    parser.add_argument("--heave-amplitude-m", type=float, required=True)
    parser.add_argument("--rho-water-kg-m3", type=float, required=True)
    parser.add_argument("--beam-m", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_station_harmonic_convergence(
        args.case,
        edges_m=args.edge_m,
        output=args.out.resolve(),
        omega_rad_s=args.omega_rad_s,
        heave_amplitude_m=args.heave_amplitude_m,
        rho_water_kg_m3=args.rho_water_kg_m3,
        beam_m=args.beam_m,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
