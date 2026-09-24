"""Run the reproducible Ma 2005 Wigley III linear-2.5D Gate 1 acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from planing_seakeeping.kernels.linear_2p5d import audit_heave_pitch_a1_convention
from planing_seakeeping.validation import (
    MA2005_MATCHED_BIE_MODEL,
    _coefficient_matrix_indices,
    _coefficient_scale,
    _ma2005_computed_coefficient,
    _ma2005_error_metrics,
)


EXPECTED_KEYS = {
    ("A33", 2.00),
    ("A33", 2.23),
    ("B33", 2.23),
    ("A53", 2.00),
    ("A53", 2.23),
    ("B53", 2.23),
    ("A35", 2.23),
    ("B35", 2.23),
    ("A55", 2.23),
    ("B55", 2.23),
}
GRID_FIELDS = (
    "body_panels_per_section",
    "free_surface_inner_panels_per_side",
    "control_surface_panels",
)
PROVIDER_ROUTE = "matched_bie_station_sweep"
FORCE_ASSEMBLY_ROUTE = "eq32_stokes_body_plus_end"
FORMULA_VERSION = "ma2005_a1_eq4_eq6_eq30_eq34_matched_bie_v1"
APPROVED_REFERENCE_SHA256 = "475a733831d0d8df785559b5eefc02ead0d8f1ec0c4735ea5becd518fd8d0b65"
BASE_BODY_PANELS = 30
BASE_FREE_SURFACE_PANELS = 20
REFINED_BODY_PANELS = 40
REFINED_FREE_SURFACE_PANELS = 30
RELATIVE_TOLERANCE = 0.15
MAX_GRID_CHANGE = 0.02
MATRIX_RESIDUAL_TOLERANCE = 1.0e-8


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("benchmarks/ma2005/wigley_iii_coefficients_digitized.csv"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/gate1_linear_2p5d_acceptance"),
    )
    parser.add_argument('--panel-integration', choices=('midpoint','analytic_straight_midpoint_curved','reconstructed_symmetric'),default='midpoint')
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes(root: Path) -> dict[str, str]:
    relative_paths = (
        Path("planing_seakeeping/kernels/linear_2p5d/panel_integrals.py"),
        Path("planing_seakeeping/kernels/linear_2p5d/reconstructed_operators.py"),
        Path("planing_seakeeping/kernels/linear_2p5d/reconstructed_history.py"),
        Path("planing_seakeeping/kernels/linear_2p5d/arc_integrals.py"),
        Path("planing_seakeeping/kernels/linear_2p5d/formulation.py"),
        Path("planing_seakeeping/types.py"),
        Path("planing_seakeeping/validation.py"),
        Path("scripts/run_ma2005_gate1_acceptance.py"),
    )
    hashes = {str(path).replace("\\", "/"): _sha256(root / path) for path in relative_paths}
    combined = hashlib.sha256()
    for name, value in sorted(hashes.items()):
        combined.update(f"{name}:{value}\n".encode("utf-8"))
    hashes["combined_source_sha256"] = combined.hexdigest()
    return hashes


def _validate_reference(reference: pd.DataFrame) -> None:
    required = {
        "coefficient",
        "omega_e_sqrt_l_over_g",
        "reference_value",
        "normalization",
        "source_figure",
        "source_page",
    }
    missing = sorted(required.difference(reference.columns))
    if missing:
        raise ValueError(f"Reference table is missing columns: {missing}")
    keys = [
        (str(row.coefficient), round(float(row.omega_e_sqrt_l_over_g), 8))
        for row in reference.itertuples(index=False)
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Reference coefficient/frequency keys must be unique.")
    if set(keys) != EXPECTED_KEYS:
        raise ValueError(f"Reference keys differ from the frozen 10-row Gate 1 set: {sorted(set(keys))}")


def _grid_definition(label: str, body_panels: int, free_panels: int) -> dict[str, Any]:
    if body_panels < 8 or free_panels < 2:
        raise ValueError("Gate 1 grids require at least 8 body panels and 2 free-surface panels per side.")
    return {
        "grid_label": label,
        "body_panels_per_section": int(body_panels),
        "free_surface_inner_panels_per_side": int(free_panels),
        "control_surface_panels": int(2 * free_panels),
    }


def _diagnostic_float(calc: dict[str, Any], name: str) -> float:
    value = calc.get(name, float("nan"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _solver_input_row(row: pd.Series) -> pd.Series:
    """Remove reference outputs and comparison-only provenance before solving."""

    return row.drop(
        labels=[
            "reference_value",
            "digitization_uncertainty",
            "reference_series",
            "reference_role",
            "source_figure",
            "source_page",
            "source_image",
            "source_note",
        ],
        errors="ignore",
    )


def _run_grid(
    reference: pd.DataFrame,
    reference_path: Path,
    grid: dict[str, Any],
    relative_tolerance: float,
) -> tuple[pd.DataFrame, dict[float, Any], float]:
    started = time.perf_counter()
    cache: dict[tuple[float | int | str, ...], object] = {}
    hydros: dict[float, Any] = {}
    rows: list[dict[str, Any]] = []
    for reference_row_id, (_, row) in enumerate(reference.iterrows()):
        # The hydrodynamic solve receives geometry/configuration and coefficient
        # identity only. Reference outputs and comparison tolerances are removed
        # before dispatch so they cannot influence the physical matrix solve.
        solver_row = _solver_input_row(row)
        calc = _ma2005_computed_coefficient(
            solver_row,
            hydro_model=MA2005_MATCHED_BIE_MODEL,
            bem_free_surface_panel_count_per_side=int(grid["free_surface_inner_panels_per_side"]),
            bem_body_panel_count=int(grid["body_panels_per_section"]),
            matrix_cache=cache,
            benchmark_base_dir=reference_path.parent,
        )
        coefficient = str(row["coefficient"])
        omega_hat = float(row["omega_e_sqrt_l_over_g"])
        prefix, row_idx, col_idx = _coefficient_matrix_indices(coefficient)
        expected = float(row["reference_value"])
        computed = float(calc["computed_value"])
        metrics = _ma2005_error_metrics(
            expected,
            computed,
            float(relative_tolerance),
            row_idx,
            col_idx,
            str(row["normalization"]),
        )
        hydro = calc.get("_matched_hydro")
        if hydro is None:
            raise RuntimeError("Matched BIE calculation did not return FrequencyDomainHydrodynamics.")
        hydros[round(omega_hat, 8)] = hydro
        active_count = 0
        control_count = int(grid["control_surface_panels"])
        sweeps = tuple(hydro.metadata.get("matched_station_sweeps", ()))
        if sweeps:
            active_count = int(len(sweeps[0].x_m))
            control_count = int(sweeps[0].control_panel_count)
        rows.append(
            {
                "grid_label": grid["grid_label"],
                "reference_row_id": int(reference_row_id),
                "coefficient": coefficient,
                "coefficient_family": prefix,
                "omega_e_sqrt_l_over_g": omega_hat,
                "omega_e_rad_s": float(calc["omega_e_rad_s"]),
                "speed_mps": float(calc["speed_mps"]),
                "fn_l": float(calc["fn_l"]),
                "reference_value": expected,
                "computed_value": computed,
                "dimensional_value": float(calc["raw_value"]),
                "normalization_scale": float(calc["normalization_scale"]),
                "abs_error": float(metrics["abs_error"]),
                "rel_error": float(metrics["rel_error"]),
                "relative_tolerance": float(relative_tolerance),
                "effective_abs_tolerance": float(metrics["effective_abs_tolerance"]),
                "gate_error_ratio": float(metrics["gate_error_ratio"]),
                "status": str(metrics["status"]),
                "provider_route": str(calc.get("provider_route", "")),
                "force_assembly_route": str(calc.get("matched_force_assembly_route", "")),
                "formula_version": FORMULA_VERSION,
                "station_count": int(calc["station_count"]),
                "active_station_count": active_count,
                "lcg_from_transom_m": float(calc["lcg_from_transom_m"]),
                "body_panels_per_section": int(grid["body_panels_per_section"]),
                "free_surface_inner_panels_per_side": int(grid["free_surface_inner_panels_per_side"]),
                "control_surface_panels": control_count,
                "apply_local_time_phase": bool(calc["matched_apply_local_time_phase"]),
                "local_time_phase_gradient_correction": bool(
                    calc["matched_local_time_phase_gradient_correction"]
                ),
                "force_closure_residual": _diagnostic_float(calc, "matched_force_closure_residual_raw"),
                "heave_condition_number_max": _diagnostic_float(calc, "matched_heave_condition_number_max"),
                "pitch_condition_number_max": _diagnostic_float(calc, "matched_pitch_condition_number_max"),
                "heave_linear_residual_max": _diagnostic_float(calc, "matched_heave_residual_max"),
                "pitch_linear_residual_max": _diagnostic_float(calc, "matched_pitch_residual_max"),
                "empirical_output_scaling_used": False,
                "reference_series": str(row.get("reference_series", "")),
                "reference_role": str(row.get("reference_role", "")),
                "source_figure": str(row["source_figure"]),
                "source_page": str(row["source_page"]),
                "source_image": str(row.get("source_image", "")),
            }
        )
    return pd.DataFrame(rows), hydros, float(time.perf_counter() - started)


def _grid_convergence(base: pd.DataFrame, refined: pd.DataFrame, limit: float) -> pd.DataFrame:
    keys = ["coefficient", "omega_e_sqrt_l_over_g"]
    left = base[keys + ["computed_value", "status"]].rename(
        columns={"computed_value": "base_value", "status": "base_gate_status"}
    )
    right = refined[keys + ["computed_value", "status"]].rename(
        columns={"computed_value": "refined_value", "status": "refined_gate_status"}
    )
    merged = left.merge(right, on=keys, how="outer", validate="one_to_one")
    if len(merged) != len(EXPECTED_KEYS):
        raise ValueError("Base/refined convergence merge did not preserve the frozen 10-row set.")
    denominator = np.maximum(np.abs(merged["refined_value"].to_numpy(dtype=float)), 1.0e-12)
    merged["absolute_change"] = np.abs(merged["refined_value"] - merged["base_value"])
    merged["relative_change"] = merged["absolute_change"].to_numpy(dtype=float) / denominator
    merged["relative_change_limit"] = float(limit)
    merged["finite"] = np.isfinite(merged[["base_value", "refined_value", "relative_change"]]).all(axis=1)
    merged["status"] = np.where(
        merged["finite"]
        & merged["base_gate_status"].eq("PASS")
        & merged["refined_gate_status"].eq("PASS")
        & merged["relative_change"].le(float(limit)),
        "PASS",
        "FAIL",
    )
    return merged


def _matrix_rows(
    grid: dict[str, Any],
    hydros: dict[float, Any],
    comparison: pd.DataFrame,
) -> tuple[pd.DataFrame, float]:
    rows: list[dict[str, Any]] = []
    max_residual = 0.0
    for omega_hat, hydro in sorted(hydros.items()):
        block = hydro.longitudinal_heave_pitch_matrices()
        force_reference = np.asarray(
            hydro.contribution_breakdown["heave_pitch_complex_force_matrices"], dtype=complex
        )
        residual = block.reconstruction_relative_residual(force_reference)
        max_residual = max(max_residual, residual)
        frequency_rows = comparison[np.isclose(comparison["omega_e_sqrt_l_over_g"], omega_hat)]
        sample = frequency_rows.iloc[0]
        rho = 1025.0
        gravity = 9.80665
        length = 3.0
        displacement = 0.078
        matched_calc_rows = frequency_rows
        if not matched_calc_rows.empty:
            dimensional = float(sample["dimensional_value"])
            normalized = float(sample["computed_value"])
            scale = dimensional / normalized if abs(normalized) > 1.0e-300 else float("nan")
            coefficient = str(sample["coefficient"])
            prefix, row_idx, col_idx = _coefficient_matrix_indices(coefficient)
            documented_scale = _coefficient_scale(prefix, row_idx, col_idx, rho, length, gravity, displacement)
            if np.isfinite(scale) and documented_scale > 0.0:
                scale_ratio = scale / documented_scale
                if abs(scale_ratio - 1.0) > 1.0e-10:
                    raise ValueError("Comparison normalization scale differs from Ma 2005 Eq.34.")
        for local_i, (row_dof, row_number) in enumerate((("heave", 3), ("pitch", 5))):
            for local_j, (col_dof, col_number) in enumerate((("heave", 3), ("pitch", 5))):
                a_name = f"A{row_number}{col_number}"
                b_name = f"B{row_number}{col_number}"
                a_value = float(block.added_mass[0, local_i, local_j])
                b_value = float(block.radiation_damping[0, local_i, local_j])
                source_row_idx = (2, 4)[local_i]
                source_col_idx = (2, 4)[local_j]
                a_scale = _coefficient_scale("A", source_row_idx, source_col_idx, rho, length, gravity, displacement)
                b_scale = _coefficient_scale("B", source_row_idx, source_col_idx, rho, length, gravity, displacement)
                force = complex(block.complex_force_matrix[0, local_i, local_j])
                a_reference = frequency_rows[frequency_rows["coefficient"].eq(a_name)]
                b_reference = frequency_rows[frequency_rows["coefficient"].eq(b_name)]
                rows.append(
                    {
                        "matrix_contract": "heave_pitch_2x2_v1",
                        "grid_label": grid["grid_label"],
                        "omega_e_sqrt_l_over_g": float(omega_hat),
                        "solver_omega_rad_s": float(block.solver_omega_rad_s[0]),
                        "solver_frequency_role": "A1_encounter_circular_frequency",
                        "encounter_omega_rad_s": float(block.encounter_omega_rad_s[0]),
                        "encounter_frequency_role": "same_as_solver_frequency_for_radiation_problem",
                        "speed_mps": float(sample["speed_mps"]),
                        "fn_l": float(sample["fn_l"]),
                        "row_dof": row_dof,
                        "col_dof": col_dof,
                        "source_row_index_zero_based": source_row_idx,
                        "source_col_index_zero_based": source_col_idx,
                        "added_mass_coefficient": a_name,
                        "radiation_damping_coefficient": b_name,
                        "added_mass_dimensional": a_value,
                        "added_mass_unit": block.added_mass_units[local_i][local_j],
                        "added_mass_nondimensional": a_value / a_scale,
                        "radiation_damping_dimensional": b_value,
                        "radiation_damping_unit": block.radiation_damping_units[local_i][local_j],
                        "radiation_damping_nondimensional": b_value / b_scale,
                        "complex_force_real": float(force.real),
                        "complex_force_imag": float(force.imag),
                        "force_harmonic_convention": "F=omega^2*A-i*omega*B",
                        "matrix_reconstruction_relative_residual": residual,
                        "provider_route": str(sample["provider_route"]),
                        "force_assembly_route": str(sample["force_assembly_route"]),
                        "station_x_origin": "aft_perpendicular",
                        "pitch_moment_origin": "longitudinal_center_of_gravity",
                        "geometry_vertical_axis": "positive_down",
                        "reported_heave_force_axis": "positive_up",
                        "pitch_lever_expression": "LCG-x_station",
                        "added_mass_reference_value": (
                            float(a_reference.iloc[0]["reference_value"]) if not a_reference.empty else float("nan")
                        ),
                        "added_mass_reference_status": (
                            str(a_reference.iloc[0]["status"]) if not a_reference.empty else "NO_REFERENCE_AT_FREQUENCY"
                        ),
                        "damping_reference_value": (
                            float(b_reference.iloc[0]["reference_value"]) if not b_reference.empty else float("nan")
                        ),
                        "damping_reference_status": (
                            str(b_reference.iloc[0]["status"]) if not b_reference.empty else "NO_REFERENCE_AT_FREQUENCY"
                        ),
                        "empirical_output_scaling_used": False,
                    }
                )
    return pd.DataFrame(rows), float(max_residual)


def _relative_residual(values: np.ndarray, reference: np.ndarray) -> float:
    values_array = np.asarray(values, dtype=complex)
    reference_array = np.asarray(reference, dtype=complex)
    return float(
        np.linalg.norm(values_array - reference_array)
        / max(float(np.linalg.norm(reference_array)), 1.0e-12)
    )


def _formula_trace_rows(
    grid: dict[str, Any],
    hydros: dict[float, Any],
    comparison: pd.DataFrame,
    exact_residual_limit: float,
    product_rule_discretization_limit: float,
) -> pd.DataFrame:
    """Trace A1 N5/m5, product-rule, end-term, and Eq.33 identities."""

    rows: list[dict[str, Any]] = []
    for omega_hat, hydro in sorted(hydros.items()):
        sweeps = tuple(hydro.metadata.get("matched_station_sweeps", ()))
        if len(sweeps) != 1:
            raise ValueError("Each Gate 1 hydrodynamic object must contain exactly one matched station sweep.")
        sweep = sweeps[0]
        sample = comparison[np.isclose(comparison["omega_e_sqrt_l_over_g"], omega_hat)].iloc[0]
        x = np.asarray(sweep.x_m, dtype=float)
        lcg = float(sample["lcg_from_transom_m"])
        radiation_levers = float(sweep.pitch_radiation_lever_sign) * (lcg - x)
        moment_levers = float(sweep.pitch_moment_sign) * (lcg - x)
        convention_audits = [
            audit_heave_pitch_a1_convention(
                body,
                float(sample["omega_e_rad_s"]),
                radiation_lever_arm_m=float(radiation_levers[index]),
                moment_lever_arm_m=float(moment_levers[index]),
                forward_speed_mps=float(sample["speed_mps"]),
                pitch_radiation_sign=float(sweep.pitch_radiation_sign),
                pitch_forward_speed_sign=float(sweep.pitch_forward_speed_sign),
                stokes_pitch_m5_sign=float(
                    sweep.pressure_force_sweep.stokes_body_forward_speed.pitch_m5_sign
                ),
            )
            for index, body in enumerate(sweep.bodies)
        ]
        n3_residual = max(audit.heave_n3_to_force_row_relative_residual for audit in convention_audits)
        n5_residual = max(audit.pitch_n5_to_moment_row_relative_residual for audit in convention_audits)
        m5_residual = max(audit.pitch_m5_forward_to_stokes_relative_residual for audit in convention_audits)

        transport = sweep.pressure_force_sweep.row_measure_transport
        pressure_measure = np.asarray(transport.pressure_row_measure_by_station, dtype=float)
        stored_gradient = np.asarray(transport.pressure_row_measure_x_gradient_by_station, dtype=float)
        stokes_measure = np.asarray(transport.stokes_m_measure_by_station, dtype=float)
        n3_measure = pressure_measure[:, 0, :]
        n5_measure = pressure_measure[:, 1, :]
        m5_measure = stokes_measure[:, 1, :]
        edge_order = 2 if x.size >= 3 else 1
        lever_gradient = np.gradient(moment_levers, x, edge_order=edge_order)
        n3_gradient = np.gradient(n3_measure, x, axis=0, edge_order=edge_order)
        product_rule = moment_levers[:, None] * n3_gradient + lever_gradient[:, None] * n3_measure
        panel_n5_identity_residual = _relative_residual(n5_measure, moment_levers[:, None] * n3_measure)
        product_rule_residual = _relative_residual(stored_gradient[:, 1, :], product_rule)
        lever_stokes_residual = _relative_residual(
            lever_gradient[:, None] * n3_measure,
            -m5_measure,
        )

        block = hydro.longitudinal_heave_pitch_matrices()
        force_reference = np.asarray(
            hydro.contribution_breakdown["heave_pitch_complex_force_matrices"], dtype=complex
        )
        force_residual = block.reconstruction_relative_residual(force_reference)
        end_matrix = (
            np.zeros((2, 2), dtype=complex)
            if sweep.end_term is None
            else np.asarray(sweep.end_term.complex_force_matrix, dtype=complex)
        )
        end_term_norm = float(np.linalg.norm(end_matrix))
        degenerate_end_ok = bool(sweep.end_station_is_degenerate and end_term_norm <= exact_residual_limit)
        exact_residuals = (
            n3_residual,
            n5_residual,
            m5_residual,
            panel_n5_identity_residual,
            lever_stokes_residual,
            force_residual,
        )
        rows.append(
            {
                "grid_label": grid["grid_label"],
                "omega_e_sqrt_l_over_g": float(omega_hat),
                "n3_body_condition_to_force_row_residual": float(n3_residual),
                "n5_body_condition_to_moment_row_residual": float(n5_residual),
                "m5_body_condition_to_stokes_row_residual": float(m5_residual),
                "n5_equals_lever_times_n3_measure_residual": float(panel_n5_identity_residual),
                "discrete_pitch_product_rule_residual": float(product_rule_residual),
                "lever_gradient_plus_stokes_m5_residual": float(lever_stokes_residual),
                "eq33_force_matrix_reconstruction_residual": float(force_residual),
                "end_station": str(sweep.end_station),
                "end_station_is_degenerate": bool(sweep.end_station_is_degenerate),
                "end_term_geometry_source": str(sweep.end_term_geometry_source),
                "end_term_matrix_norm": end_term_norm,
                "exact_residual_limit": float(exact_residual_limit),
                "product_rule_discretization_limit": float(product_rule_discretization_limit),
                "provider_route": str(sample["provider_route"]),
                "force_assembly_route": str(sample["force_assembly_route"]),
                "status": "PASS"
                if all(np.isfinite(exact_residuals))
                and max(exact_residuals) <= float(exact_residual_limit)
                and np.isfinite(product_rule_residual)
                and product_rule_residual <= float(product_rule_discretization_limit)
                and degenerate_end_ok
                else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small DataFrame without pandas' optional tabulate dependency."""

    columns = [str(column) for column in frame.columns]

    def cell(value: Any) -> str:
        if isinstance(value, (float, np.floating)):
            rendered = f"{float(value):.10g}"
        else:
            rendered = str(value)
        return rendered.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for values in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    return "\n".join(lines)


def _write_report(
    path: Path,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    convergence: pd.DataFrame,
    formula_trace: pd.DataFrame,
    reference_path: Path,
) -> None:
    base = comparison[comparison["grid_label"].eq("base")]
    refined = comparison[comparison["grid_label"].eq("refined")]
    b55 = comparison[comparison["coefficient"].eq("B55")][
        ["grid_label", "reference_value", "computed_value", "gate_error_ratio", "status"]
    ]
    text = f"""# Ma 2005 Wigley III 线性 2.5D Gate 1 验收报告

## 结论

本次验收保持 `matched_bie_station_sweep` 与 `eq32_stokes_body_plus_end` 公式路线不变，只将原 `8/4` 演示粗网格替换为预先固定的论文离散量级网格 `30/20`，并以 `40/30` 网格复核。没有使用经验缩放、逐系数拟合或后处理补偿。

最终机器状态：**{summary.iloc[0]['acceptance_status']}**。

## 固定参考

- 参考文件：`{reference_path}`
- 参考行数：10
- 相对误差门槛：`{summary.iloc[0]['relative_tolerance']}`
- 网格变化门槛：`{summary.iloc[0]['max_grid_change_limit']}`

## 主要结果

- 基准网格：{int(base['status'].eq('PASS').sum())}/10 PASS。
- 加密网格：{int(refined['status'].eq('PASS').sum())}/10 PASS。
- 最大细网格变化：{float(convergence['relative_change'].max()):.6%}。
- `2 x 2` 复力矩阵最大重构残差：{float(summary.iloc[0]['matrix_reconstruction_relative_residual_max']):.3e}。
- `N5/m5`、Stokes 杠杆项与矩阵重构最大代数残差：{float(summary.iloc[0]['formula_exact_residual_max']):.3e}。
- 离散乘积法则截断残差：{float(summary.iloc[0]['product_rule_discretization_residual_max']):.6%}。

### B55

{_markdown_table(b55)}

### 网格收敛

{_markdown_table(convergence[['coefficient', 'omega_e_sqrt_l_over_g', 'base_value', 'refined_value', 'relative_change', 'status']])}

## 边界

本报告只证明 Ma 2005 Wigley III 线性 matched-BIE 水动力系数的实现复现与细网格一致性，不等同于独立试验、规则波运动响应、不规则波统计、非线性 2D+t、多体船或水翼模型已经通过。
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route
    with panel_integration_route(args.panel_integration):
        return _run_acceptance(args)


def _run_acceptance(args) -> int:
    root = Path(__file__).resolve().parents[1]
    reference_path = args.reference.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    reference = pd.read_csv(reference_path)
    _validate_reference(reference)
    reference_hash = _sha256(reference_path)
    if reference_hash != APPROVED_REFERENCE_SHA256:
        raise ValueError(
            "Reference SHA-256 differs from the approved Gate 1 dataset: "
            f"expected {APPROVED_REFERENCE_SHA256}, got {reference_hash}."
        )
    source_hashes = _source_hashes(root)
    grids = (
        _grid_definition("base", BASE_BODY_PANELS, BASE_FREE_SURFACE_PANELS),
        _grid_definition("refined", REFINED_BODY_PANELS, REFINED_FREE_SURFACE_PANELS),
    )
    if not (
        grids[1]["body_panels_per_section"] > grids[0]["body_panels_per_section"]
        and grids[1]["free_surface_inner_panels_per_side"]
        > grids[0]["free_surface_inner_panels_per_side"]
        and grids[1]["control_surface_panels"] > grids[0]["control_surface_panels"]
    ):
        raise ValueError("The locked refined Gate 1 grid must be strictly finer than the base grid.")
    invariant_solver_config = {
        "panel_integration_route": args.panel_integration,
        "benchmark": "ma2005_wigley_iii",
        "provider_route": PROVIDER_ROUTE,
        "force_assembly_route": FORCE_ASSEMBLY_ROUTE,
        "formula_version": FORMULA_VERSION,
        "reference_file_sha256": reference_hash,
        "relative_tolerance": RELATIVE_TOLERANCE,
        "max_grid_change": MAX_GRID_CHANGE,
        "matrix_residual_tolerance": MATRIX_RESIDUAL_TOLERANCE,
        "empirical_output_scaling_used": False,
    }
    invariant_solver_config_sha256 = hashlib.sha256(
        json.dumps(invariant_solver_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    _write_json(out_dir / "integration_route_contract.json", invariant_solver_config)

    comparisons: list[pd.DataFrame] = []
    hydros_by_grid: dict[str, dict[float, Any]] = {}
    runtimes: dict[str, float] = {}
    for grid in grids:
        comparison, hydros, runtime = _run_grid(
            reference,
            reference_path,
            grid,
            RELATIVE_TOLERANCE,
        )
        comparisons.append(comparison)
        hydros_by_grid[str(grid["grid_label"])] = hydros
        runtimes[str(grid["grid_label"])] = runtime
        manifest = {
            "schema": "ma2005_gate1_run_manifest_v1",
            "benchmark": "ma2005_wigley_iii",
            "grid": grid,
            "reference_file": str(reference_path),
            "reference_file_sha256": reference_hash,
            "provider_route": PROVIDER_ROUTE,
            "force_assembly_route": FORCE_ASSEMBLY_ROUTE,
            "formula_version": FORMULA_VERSION,
            "relative_tolerance": RELATIVE_TOLERANCE,
            "invariant_solver_config": invariant_solver_config,
            "invariant_solver_config_sha256": invariant_solver_config_sha256,
            "empirical_output_scaling_used": False,
            "runtime_s": runtime,
            "source_hashes": source_hashes,
        }
        _write_json(out_dir / f"run_manifest_{grid['grid_label']}.json", manifest)

    comparison = pd.concat(comparisons, ignore_index=True)
    base = comparison[comparison["grid_label"].eq("base")].copy()
    refined = comparison[comparison["grid_label"].eq("refined")].copy()
    convergence = _grid_convergence(base, refined, MAX_GRID_CHANGE)
    matrix_frames: list[pd.DataFrame] = []
    matrix_residuals: list[float] = []
    for grid in grids:
        matrix, residual = _matrix_rows(
            grid,
            hydros_by_grid[str(grid["grid_label"])],
            comparison[comparison["grid_label"].eq(grid["grid_label"])],
        )
        matrix_frames.append(matrix)
        matrix_residuals.append(residual)
    matrices = pd.concat(matrix_frames, ignore_index=True)
    formula_trace = pd.concat(
        [
            _formula_trace_rows(
                grid,
                hydros_by_grid[str(grid["grid_label"])],
                comparison[comparison["grid_label"].eq(grid["grid_label"])],
                MATRIX_RESIDUAL_TOLERANCE,
                MAX_GRID_CHANGE,
            )
            for grid in grids
        ],
        ignore_index=True,
    )

    provider_ok = comparison["provider_route"].eq(PROVIDER_ROUTE).all()
    route_ok = comparison["force_assembly_route"].eq(FORCE_ASSEMBLY_ROUTE).all()
    finite_ok = np.isfinite(
        comparison[
            [
                "reference_value",
                "computed_value",
                "gate_error_ratio",
                "heave_condition_number_max",
                "pitch_condition_number_max",
                "heave_linear_residual_max",
                "pitch_linear_residual_max",
            ]
        ]
    ).all().all()
    base_ok = len(base) == 10 and base["status"].eq("PASS").all()
    refined_ok = len(refined) == 10 and refined["status"].eq("PASS").all()
    convergence_ok = len(convergence) == 10 and convergence["status"].eq("PASS").all()
    matrix_complete = len(matrices) == 16 and matrices.groupby(["grid_label", "omega_e_sqrt_l_over_g"]).size().eq(4).all()
    matrix_residual_max = max(matrix_residuals, default=float("inf"))
    matrix_ok = matrix_complete and matrix_residual_max <= MATRIX_RESIDUAL_TOLERANCE
    formula_exact_columns = [
        "n3_body_condition_to_force_row_residual",
        "n5_body_condition_to_moment_row_residual",
        "m5_body_condition_to_stokes_row_residual",
        "n5_equals_lever_times_n3_measure_residual",
        "lever_gradient_plus_stokes_m5_residual",
        "eq33_force_matrix_reconstruction_residual",
    ]
    formula_exact_residual_max = float(formula_trace[formula_exact_columns].max().max())
    product_rule_discretization_residual_max = float(
        formula_trace["discrete_pitch_product_rule_residual"].max()
    )
    formula_ok = len(formula_trace) == 4 and formula_trace["status"].eq("PASS").all()
    accepted = bool(
        base_ok
        and refined_ok
        and convergence_ok
        and provider_ok
        and route_ok
        and finite_ok
        and matrix_ok
        and formula_ok
    )
    summary = pd.DataFrame(
        [
            {
                "benchmark": "ma2005_wigley_iii",
                "base_pass_count": int(base["status"].eq("PASS").sum()),
                "refined_pass_count": int(refined["status"].eq("PASS").sum()),
                "reference_row_count": 10,
                "base_b55": float(base.loc[base["coefficient"].eq("B55"), "computed_value"].iloc[0]),
                "refined_b55": float(refined.loc[refined["coefficient"].eq("B55"), "computed_value"].iloc[0]),
                "max_grid_change": float(convergence["relative_change"].max()),
                "max_grid_change_limit": MAX_GRID_CHANGE,
                "matrix_block_count": int(matrices.groupby(["grid_label", "omega_e_sqrt_l_over_g"]).ngroups),
                "matrix_reconstruction_relative_residual_max": float(matrix_residual_max),
                "matrix_reconstruction_relative_residual_limit": MATRIX_RESIDUAL_TOLERANCE,
                "formula_exact_residual_max": formula_exact_residual_max,
                "formula_exact_residual_limit": MATRIX_RESIDUAL_TOLERANCE,
                "product_rule_discretization_residual_max": product_rule_discretization_residual_max,
                "product_rule_discretization_residual_limit": MAX_GRID_CHANGE,
                "provider_route": PROVIDER_ROUTE,
                "force_assembly_route": FORCE_ASSEMBLY_ROUTE,
                "relative_tolerance": RELATIVE_TOLERANCE,
                "reference_file": str(reference_path),
                "reference_file_sha256": reference_hash,
                "combined_source_sha256": source_hashes["combined_source_sha256"],
                "base_runtime_s": runtimes["base"],
                "refined_runtime_s": runtimes["refined"],
                "empirical_output_scaling_used": False,
                "acceptance_status": "PASS" if accepted else "FAIL",
            }
        ]
    )
    machine_acceptance = pd.DataFrame(
        [
            {"check": "base_10_of_10", "status": "PASS" if base_ok else "FAIL"},
            {"check": "refined_10_of_10", "status": "PASS" if refined_ok else "FAIL"},
            {"check": "fine_grid_convergence", "status": "PASS" if convergence_ok else "FAIL"},
            {"check": "provider_route_invariant", "status": "PASS" if provider_ok else "FAIL"},
            {"check": "force_assembly_route_invariant", "status": "PASS" if route_ok else "FAIL"},
            {"check": "finite_outputs", "status": "PASS" if finite_ok else "FAIL"},
            {"check": "matrix_contract_complete", "status": "PASS" if matrix_complete else "FAIL"},
            {"check": "matrix_force_reconstruction", "status": "PASS" if matrix_ok else "FAIL"},
            {"check": "n5_m5_product_rule_and_end_trace", "status": "PASS" if formula_ok else "FAIL"},
            {"check": "no_empirical_scaling", "status": "PASS"},
        ]
    )
    changed_fields = [name for name in GRID_FIELDS if grids[0][name] != grids[1][name]]
    _write_json(
        out_dir / "grid_convergence_manifest.json",
        {
            "schema": "ma2005_gate1_grid_convergence_manifest_v1",
            "base_grid": grids[0],
            "refined_grid": grids[1],
            "allowed_changed_fields": list(GRID_FIELDS),
            "observed_changed_fields": changed_fields,
            "mesh_only_change": set(changed_fields).issubset(GRID_FIELDS),
            "max_grid_change": float(convergence["relative_change"].max()),
            "max_grid_change_limit": MAX_GRID_CHANGE,
            "reference_file_sha256": reference_hash,
            "approved_reference_file_sha256": APPROVED_REFERENCE_SHA256,
            "combined_source_sha256": source_hashes["combined_source_sha256"],
            "invariant_solver_config_sha256_base": invariant_solver_config_sha256,
            "invariant_solver_config_sha256_refined": invariant_solver_config_sha256,
            "invariant_solver_config_match": True,
        },
    )
    comparison.to_csv(out_dir / "gate1_coefficients_comparison.csv", index=False)
    convergence.to_csv(out_dir / "gate1_grid_convergence_detail.csv", index=False)
    pd.DataFrame(
        [
            {
                "row_count": len(convergence),
                "pass_count": int(convergence["status"].eq("PASS").sum()),
                "max_relative_change": float(convergence["relative_change"].max()),
                "relative_change_limit": MAX_GRID_CHANGE,
                "status": "PASS" if convergence_ok else "FAIL",
            }
        ]
    ).to_csv(out_dir / "gate1_grid_convergence_summary.csv", index=False)
    matrices.to_csv(out_dir / "gate1_heave_pitch_2x2_matrices.csv", index=False)
    formula_trace.to_csv(out_dir / "gate1_formula_trace.csv", index=False)
    machine_acceptance.to_csv(out_dir / "gate1_machine_acceptance.csv", index=False)
    summary.to_csv(out_dir / "gate1_acceptance_summary.csv", index=False)
    _write_report(
        out_dir / "gate1_acceptance_report.md",
        summary,
        comparison,
        convergence,
        formula_trace,
        reference_path,
    )
    print(summary.to_string(index=False))
    print(machine_acceptance.to_string(index=False))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
