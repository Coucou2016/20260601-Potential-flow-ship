from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.config import BoatConfig, PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.longitudinal_response import (
    build_faltinsen_planing_model,
    faltinsen_head_sea_excitation,
    solve_longitudinal_frequency_response,
)
from scripts.run_regular_head_sea_gate2_acceptance import _verify_begovic_sources


COEFFICIENTS = ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55")
RELATIVE_CHANGE_LIMIT = 0.05
HARMONIC_RESIDUAL_LIMIT = 0.05
BVP_RESIDUAL_LIMIT = 1.0e-10
POINT_RESPONSE_ERROR_LIMIT = 0.15


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Begovic target-specific nonlinear 2D+t forced-motion time "
            "convergence and one independent regular-wave response point."
        )
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="SUBSTEPS=PATH",
        help="Repeat for at least three successively refined forced-motion runs.",
    )
    parser.add_argument("--fn-b", type=float, default=2.82)
    parser.add_argument("--case-code", default="C7")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_runs(specifications: list[str]) -> list[tuple[int, Path]]:
    runs: list[tuple[int, Path]] = []
    for specification in specifications:
        label, separator, path_text = specification.partition("=")
        if not separator:
            raise ValueError(f"Run specification must be SUBSTEPS=PATH: {specification!r}.")
        substeps = int(label)
        path = Path(path_text).resolve()
        if substeps <= 0 or not path.is_dir():
            raise ValueError(f"Invalid forced-motion run: {specification!r}.")
        runs.append((substeps, path))
    runs.sort(key=lambda item: item[0])
    if len(runs) < 3 or len({item[0] for item in runs}) != len(runs):
        raise ValueError("At least three unique time-refinement levels are required.")
    if any(fine != 2 * coarse for (coarse, _), (fine, _) in zip(runs, runs[1:])):
        raise ValueError("Successive bem-substep levels must double exactly.")
    return runs


def _csv_boolean(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"false", "0", "no"}:
        return False
    if normalized in {"true", "1", "yes"}:
        return True
    raise ValueError(f"Unrecognized CSV boolean: {value!r}.")


def _total_coefficients(path: Path, *, reprocessed: bool) -> pd.DataFrame:
    if reprocessed:
        sources = (
            path / "savitsky_reprocessed_heave" / "identified_coefficients_reprocessed.csv",
            path / "savitsky_reprocessed_pitch" / "identified_coefficients_reprocessed.csv",
        )
    else:
        sources = (path / "identified_coefficients.csv",)
    frame = pd.concat([pd.read_csv(source) for source in sources], ignore_index=True)
    frame = frame[frame["component"].eq("total")].copy()
    if set(frame["coefficient"]) != set(COEFFICIENTS) or len(frame) != len(COEFFICIENTS):
        raise ValueError(f"Run {path} does not contain one complete total 2x2 A/B matrix.")
    if any(_csv_boolean(value) for value in frame["response_calibration_used"]):
        raise ValueError(f"Run {path} contains response-calibrated coefficients.")
    return frame.set_index("coefficient").loc[list(COEFFICIENTS)]


def _restoring_matrix(path: Path) -> np.ndarray:
    frame = pd.read_csv(path)
    frame = frame[frame["component"].eq("total")]
    row_index = {"heave_force": 0, "pitch_moment": 1}
    column_index = {"heave": 0, "pitch": 1}
    matrix = np.full((2, 2), np.nan, dtype=float)
    for row in frame.itertuples(index=False):
        matrix[row_index[row.row], column_index[row.column]] = float(row.value)
    if not np.isfinite(matrix).all():
        raise ValueError(f"Incomplete total restoring matrix in {path}.")
    return matrix


def _matrix(values: pd.DataFrame, prefix: str) -> np.ndarray:
    return np.asarray(
        [
            [values.loc[prefix + "33", "value_dimensional"], values.loc[prefix + "35", "value_dimensional"]],
            [values.loc[prefix + "53", "value_dimensional"], values.loc[prefix + "55", "value_dimensional"]],
        ],
        dtype=float,
    )


def _coefficient_convergence(
    runs: list[tuple[int, Path]],
    *,
    reprocessed: bool,
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    tables = {
        substeps: _total_coefficients(path, reprocessed=reprocessed)
        for substeps, path in runs
    }
    rows: list[dict[str, Any]] = []
    for coefficient in COEFFICIENTS:
        previous_value: float | None = None
        for substeps, _ in runs:
            table = tables[substeps]
            value = float(table.loc[coefficient, "value_dimensional"])
            relative_change = np.nan
            if previous_value is not None:
                relative_change = abs(value - previous_value) / max(abs(value), 1.0e-30)
            rows.append(
                {
                    "restoring_route": (
                        "fixed_savitsky_faltinsen" if reprocessed else "native_nonlinear_2dt"
                    ),
                    "bem_substeps_per_plane": substeps,
                    "coefficient": coefficient,
                    "value_dimensional": value,
                    "value_nondimensional": float(
                        table.loc[coefficient, "value_nondimensional"]
                    ),
                    "relative_change_from_previous": relative_change,
                    "harmonic_fit_residual_nrmse": float(
                        table.loc[coefficient, "harmonic_fit_residual_nrmse"]
                    ),
                    "response_calibration_used": False,
                }
            )
            previous_value = value
    return pd.DataFrame(rows), tables


def _boat_and_target(
    root: Path,
    fn_b: float,
    case_code: str,
) -> tuple[BoatConfig, Any, pd.Series, pd.Series]:
    hull_table, motion_table, running_table, _, _ = _verify_begovic_sources(root)
    hull = hull_table.iloc[0]
    target_rows = motion_table[
        np.isclose(motion_table["fn_b"], fn_b)
        & motion_table["case_code"].astype(str).eq(case_code)
    ]
    running_rows = running_table[np.isclose(running_table["fn_b"], fn_b)]
    if len(target_rows) != 1 or len(running_rows) != 1:
        raise ValueError(f"Begovic Fn_B={fn_b:g}, case={case_code!r} is not unique.")
    target = target_rows.iloc[0]
    running = running_rows.iloc[0]
    boat = BoatConfig(
        length_m=float(hull["length_overall_m"]),
        beam_m=float(hull["beam_m"]),
        deadrise_deg=float(hull["deadrise_deg"]),
        mass_kg=float(hull["mass_kg_from_weight"]),
        lcg_m=float(hull["lcg_from_transom_m"]),
        vcg_m=float(hull["vcg_m"]),
        pitch_radius_gyration_m=float(hull["pitch_radius_gyration_m"]),
        rho_water_kg_m3=1000.0,
        gravity_m_s2=9.80665,
        wetted_lengths_type=1,
    )
    equilibrium = make_prescribed_equilibrium(
        boat,
        float(running["speed_m_s"]),
        PrescribedRunningStateConfig(
            enabled=True,
            trim_deg=float(running["running_trim_deg"]),
            lambda_w=float(running["mean_wetted_length_m"]) / boat.beam_m,
        ),
    )
    return boat, equilibrium, target, running


def _response_rows(
    runs: list[tuple[int, Path]],
    native_tables: dict[int, pd.DataFrame],
    fixed_tables: dict[int, pd.DataFrame],
    *,
    root: Path,
    fn_b: float,
    case_code: str,
) -> list[dict[str, Any]]:
    boat, equilibrium, target, running = _boat_and_target(root, fn_b, case_code)
    savitsky = compute_hydro_matrices(boat, equilibrium)
    base = build_faltinsen_planing_model(
        boat,
        equilibrium,
        savitsky,
        np.asarray([float(target["wavelength_m"])], dtype=float),
        np.asarray([float(target["wave_amplitude_m"])], dtype=float),
        point_x_forward_m=boat.length_m - boat.lcg_m,
        phase_length_m=float(running["mean_wetted_length_m"]),
        metadata={"response_calibration_used": False},
    )
    rows: list[dict[str, Any]] = []
    for substeps, path in runs:
        for route, table, restoring in (
            (
                "native_nonlinear_2dt_ABC",
                native_tables[substeps],
                _restoring_matrix(path / "restoring_matrices.csv"),
            ),
            ("fixed_savitsky_faltinsen_ABC", fixed_tables[substeps], savitsky.restoring),
        ):
            added = _matrix(table, "A")[None, :, :]
            damping = _matrix(table, "B")[None, :, :]
            restoring_values = np.asarray(restoring, dtype=float)[None, :, :]
            excitation = faltinsen_head_sea_excitation(
                added,
                damping,
                restoring_values,
                base.omega0_rad_s,
                base.hydrodynamics.encounter_omega_rad_s,
                base.wavenumber_rad_m,
                equilibrium.speed_through_water_mps,
                heave_finite_length_factor=base.heave_finite_length_factor,
                pitch_finite_length_factor=base.pitch_finite_length_factor,
            )
            model = replace(
                base,
                hydrodynamics=replace(
                    base.hydrodynamics,
                    added_mass=added,
                    radiation_damping=damping,
                ),
                restoring=restoring_values,
                excitation_per_wave_amplitude=excitation,
            )
            response = solve_longitudinal_frequency_response(model).iloc[0]
            reference_heave = float(target["heave_rao_m_per_m"])
            reference_pitch = float(target["pitch_rao_rad_per_wave_slope"])
            rows.append(
                {
                    "bem_substeps_per_plane": substeps,
                    "route": route,
                    "fn_b": fn_b,
                    "case_code": case_code,
                    "encounter_omega_rad_s": float(response["omega_e_rad_s"]),
                    "heave_rao_m_per_m": float(response["heave_rao_m_per_m"]),
                    "reference_heave_rao_m_per_m": reference_heave,
                    "heave_relative_error": abs(
                        float(response["heave_rao_m_per_m"]) - reference_heave
                    )
                    / reference_heave,
                    "pitch_rao_rad_per_wave_slope": float(
                        response["pitch_rao_rad_per_wave_slope"]
                    ),
                    "reference_pitch_rao_rad_per_wave_slope": reference_pitch,
                    "pitch_relative_error": abs(
                        float(response["pitch_rao_rad_per_wave_slope"]) - reference_pitch
                    )
                    / reference_pitch,
                    "dynamic_condition_number": float(response["dynamic_condition_number"]),
                    "equation_relative_residual": float(
                        response["equation_relative_residual"]
                    ),
                    "phase_length_source": "reported_savitsky_mean_wetted_length",
                    "phase_length_m": float(running["mean_wetted_length_m"]),
                    "excitation_formulation": "faltinsen_eq9_110_to_9_117",
                    "response_calibration_used": False,
                }
            )
    return rows


def _numerical_diagnostics(runs: list[tuple[int, Path]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for substeps, path in runs:
        diagnostics = json.loads((path / "run_diagnostics.json").read_text(encoding="utf-8"))
        if len(diagnostics) != 1:
            raise ValueError(f"Time-convergence run {path} must contain exactly one frequency.")
        item = diagnostics[0]
        rows.append(
            {
                "bem_substeps_per_plane": substeps,
                "omega_rad_s": float(item["omega_rad_s"]),
                "time_step_s": float(item["time_step_s"]),
                "maximum_potential_bvp_residual": max(
                    float(item["heave_max_potential_residual"]),
                    float(item["pitch_max_potential_residual"]),
                ),
                "maximum_pressure_bvp_residual": max(
                    float(item["heave_max_pressure_residual"]),
                    float(item["pitch_max_pressure_residual"]),
                ),
                "maximum_bvp_condition_number": max(
                    float(item["heave_max_potential_condition_number"]),
                    float(item["pitch_max_potential_condition_number"]),
                ),
                "response_calibration_used": False,
                "input_snapshot_sha256": _sha256(path / "run_input_snapshot.json"),
                "identified_coefficients_sha256": _sha256(path / "identified_coefficients.csv"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = _parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    runs = _parse_runs(args.run)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)

    native, native_tables = _coefficient_convergence(runs, reprocessed=False)
    fixed, fixed_tables = _coefficient_convergence(runs, reprocessed=True)
    responses = pd.DataFrame(
        _response_rows(
            runs,
            native_tables,
            fixed_tables,
            root=root,
            fn_b=float(args.fn_b),
            case_code=str(args.case_code),
        )
    )
    diagnostics = _numerical_diagnostics(runs)
    native.to_csv(output / "native_2dt_time_convergence.csv", index=False)
    fixed.to_csv(output / "fixed_savitsky_time_convergence.csv", index=False)
    responses.to_csv(output / "response_time_convergence.csv", index=False)
    diagnostics.to_csv(output / "numerical_diagnostics.csv", index=False)

    finest = runs[-1][0]
    previous = runs[-2][0]
    native_last = native[native["bem_substeps_per_plane"].eq(finest)]
    fixed_last = fixed[fixed["bem_substeps_per_plane"].eq(finest)]
    response_last = responses[
        responses["bem_substeps_per_plane"].eq(finest)
        & responses["route"].eq("native_nonlinear_2dt_ABC")
    ].iloc[0]
    summary = {
        "schema": "begovic_target_2dt_time_convergence_audit_v1",
        "fn_b": float(args.fn_b),
        "case_code": str(args.case_code),
        "coarse_to_fine_substeps": [item[0] for item in runs],
        "last_pair": [previous, finest],
        "native_2dt_maximum_last_pair_relative_change": float(
            native_last["relative_change_from_previous"].max()
        ),
        "fixed_savitsky_maximum_last_pair_relative_change": float(
            fixed_last["relative_change_from_previous"].max()
        ),
        "maximum_finest_harmonic_fit_residual_nrmse": float(
            native_last["harmonic_fit_residual_nrmse"].max()
        ),
        "maximum_bvp_residual": float(
            diagnostics[
                ["maximum_potential_bvp_residual", "maximum_pressure_bvp_residual"]
            ].to_numpy(dtype=float).max()
        ),
        "finest_native_heave_relative_error": float(response_last["heave_relative_error"]),
        "finest_native_pitch_relative_error": float(response_last["pitch_relative_error"]),
        "response_calibration_used": False,
        "checks": {
            "native_2dt_last_pair_all_coefficients_le_5pct": bool(
                native_last["relative_change_from_previous"].max()
                <= RELATIVE_CHANGE_LIMIT
            ),
            "finest_harmonic_residuals_le_5pct": bool(
                native_last["harmonic_fit_residual_nrmse"].max()
                <= HARMONIC_RESIDUAL_LIMIT
            ),
            "all_bvp_residuals_le_1e_minus_10": bool(
                diagnostics[
                    ["maximum_potential_bvp_residual", "maximum_pressure_bvp_residual"]
                ].to_numpy(dtype=float).max()
                <= BVP_RESIDUAL_LIMIT
            ),
            "single_point_heave_error_le_15pct": bool(
                response_last["heave_relative_error"] <= POINT_RESPONSE_ERROR_LIMIT
            ),
            "single_point_pitch_error_le_15pct": bool(
                response_last["pitch_relative_error"] <= POINT_RESPONSE_ERROR_LIMIT
            ),
        },
        "status": "single_frequency_prototype_pass_not_gate2_acceptance",
        "limitations": [
            "Only one Begovic frequency at one speed is audited.",
            "The native nonlinear 2D+t restoring matrix has not undergone an independent spatial Richardson study.",
            "Gate 2 still requires the frozen multi-speed frequency coverage and aggregate metrics.",
        ],
    }
    summary["prototype_pass"] = bool(all(summary["checks"].values()))
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
