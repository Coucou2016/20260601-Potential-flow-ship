from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import shutil

import numpy as np

from planing_seakeeping.forced_motion_identification import extract_forced_motion_column
from scripts.postprocess_sun2007_forced_motion_checkpoint import (
    _coefficient_scale,
    _read_component_loads,
    _read_restoring_matrices,
    _sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Re-identify the available Sun forced-motion columns from a completed run "
            "using one traced external restoring matrix."
        )
    )
    parser.add_argument("source_run", type=Path)
    parser.add_argument("restoring_matrices", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _sigma_label(sigma: float) -> str:
    return f"{float(sigma):.6g}".replace(".", "p")


def reprocess(source_run: Path, restoring_path: Path, output: Path) -> Path:
    source_run = source_run.resolve()
    restoring_path = restoring_path.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    snapshot_path = source_run / "run_input_snapshot.json"
    diagnostics_path = source_run / "run_diagnostics.json"
    if not snapshot_path.exists() or not diagnostics_path.exists():
        raise FileNotFoundError("Source run must contain its input snapshot and diagnostics.")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    arguments = dict(snapshot["arguments"])
    sigmas = [float(value) for value in arguments["sigmas"]]
    if len(sigmas) != 1:
        raise ValueError("Reprocessing requires a one-frequency source run.")
    sigma = sigmas[0]
    beam = float(arguments["beam_m"])
    rho = float(arguments["rho_water_kg_m3"])
    gravity = float(arguments["gravity_m_s2"])
    omega = sigma * math.sqrt(gravity / beam)
    discard_cycles = float(arguments["discard_cycles"])
    retained_cycles = float(arguments["retained_cycles"])
    restoring = _read_restoring_matrices(restoring_path)
    if "total" not in restoring or restoring["total"].shape != (2, 2):
        raise ValueError("External restoring matrix must contain a complete total matrix.")

    rows: list[dict[str, object]] = []
    source_timeseries: list[dict[str, object]] = []
    definitions = {
        "heave": (("A33", 0), ("A53", 1), ("B33", 0), ("B53", 1)),
        "pitch": (("A35", 0), ("A55", 1), ("B35", 0), ("B55", 1)),
    }
    amplitudes = {
        "heave": float(arguments["heave_amplitude_over_beam"]) * beam,
        "pitch": math.radians(float(arguments["pitch_amplitude_deg"])),
    }
    heave_only = bool(arguments.get("heave_only", False))
    pitch_only = bool(arguments.get("pitch_only", False))
    if heave_only and pitch_only:
        raise ValueError("A source run cannot be both heave-only and pitch-only.")
    if heave_only:
        motion_columns = ((0, "heave"),)
    elif pitch_only:
        motion_columns = ((1, "pitch"),)
    else:
        motion_columns = ((0, "heave"), (1, "pitch"))

    for column_index, motion_dof in motion_columns:
        timeseries_path = source_run / (
            f"timeseries_sigma_{_sigma_label(sigma)}_{motion_dof}.csv"
        )
        if not timeseries_path.exists():
            raise FileNotFoundError(timeseries_path)
        time, component_loads = _read_component_loads(timeseries_path)
        source_timeseries.append(
            {
                "motion_dof": motion_dof,
                "path": str(timeseries_path),
                "sha256": _sha256(timeseries_path),
            }
        )
        for component, loads in component_loads.items():
            matrix = restoring.get(component, np.zeros((2, 2), dtype=float))
            identified = extract_forced_motion_column(
                time,
                loads,
                motion_dof=motion_dof,  # type: ignore[arg-type]
                omega_rad_s=omega,
                motion_amplitude=amplitudes[motion_dof],
                restoring_column=matrix[:, column_index],
                discard_cycles=discard_cycles,
                retained_cycles=retained_cycles,
                fitted_harmonics=3,
            )
            for coefficient, row_index in definitions[motion_dof]:
                dimensional = (
                    identified.added_mass_column[row_index]
                    if coefficient.startswith("A")
                    else identified.damping_column[row_index]
                )
                rows.append(
                    {
                        "component": component,
                        "sigma": sigma,
                        "omega_rad_s": omega,
                        "coefficient": coefficient,
                        "value_dimensional": float(dimensional),
                        "value_nondimensional": float(dimensional)
                        / _coefficient_scale(
                            coefficient,
                            beam=beam,
                            rho=rho,
                            gravity=gravity,
                        ),
                        "harmonic_fit_residual_nrmse": float(
                            identified.harmonic_fit.residual_nrmse[row_index]
                        ),
                        "restoring_subtraction": (
                            f"external:{restoring_path.parent.name}/{restoring_path.name}"
                            if np.any(matrix)
                            else "zero_component_decomposition"
                        ),
                        "restoring_matrices_sha256": _sha256(restoring_path),
                        "target_identifier": arguments["target_identifier"],
                        "beam_m": beam,
                        "deadrise_deg": float(arguments["deadrise_deg"]),
                        "trim_deg": float(arguments["trim_deg"]),
                        "fn_b": float(arguments["fn_b"]),
                        "mean_wetted_length_over_b": float(
                            arguments["mean_wetted_length_over_beam"]
                        ),
                        "lcg_from_transom_m": float(arguments["lcg_over_beam"]) * beam,
                        "rho_water_kg_m3": rho,
                        "gravity_m_s2": gravity,
                        "matrix_coordinate_contract": (
                            "heave_up_pitch_bow_up_force_and_moment_about_cg"
                        ),
                        "response_calibration_used": False,
                    }
                )

    rows.sort(key=lambda row: (str(row["component"]), str(row["coefficient"])))
    with (output / "identified_coefficients.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    shutil.copyfile(diagnostics_path, output / "run_diagnostics.json")
    reprocessed_arguments = dict(arguments)
    reprocessed_arguments["restoring_mode"] = "external"
    reprocessed_arguments["restoring_matrix_file"] = str(restoring_path)
    reprocessed_snapshot = {
        **snapshot,
        "schema": "planing_forced_motion_2dt_reprocessed_input_snapshot_v1",
        "arguments": reprocessed_arguments,
        "source_run": str(source_run),
        "source_run_input_snapshot_sha256": _sha256(snapshot_path),
        "source_timeseries": source_timeseries,
        "reprocessed_motion_dofs": [motion_dof for _, motion_dof in motion_columns],
        "response_calibration_used": False,
    }
    (output / "run_input_snapshot.json").write_text(
        json.dumps(reprocessed_snapshot, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    restoring_manifest_path = restoring_path.parent / "manifest.json"
    restoring_manifest = (
        json.loads(restoring_manifest_path.read_text(encoding="utf-8"))
        if restoring_manifest_path.exists()
        else {}
    )
    (output / "restoring_diagnostics.json").write_text(
        json.dumps(
            {
                "mode": "external",
                "source": restoring_manifest.get(
                    "benchmark", "external_reprocessing_restoring_matrix"
                ),
                "source_path": str(restoring_path),
                "source_sha256": _sha256(restoring_path),
                "source_manifest_path": (
                    str(restoring_manifest_path)
                    if restoring_manifest_path.exists()
                    else None
                ),
                "source_manifest_sha256": (
                    _sha256(restoring_manifest_path)
                    if restoring_manifest_path.exists()
                    else None
                ),
                "restoring_matrix": restoring["total"].tolist(),
                "response_calibration_used": False,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    return output


def main() -> int:
    args = _parser().parse_args()
    output = reprocess(args.source_run, args.restoring_matrices, args.out)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
