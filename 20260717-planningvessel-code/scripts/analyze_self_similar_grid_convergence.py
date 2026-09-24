from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_self_similar_time_step_convergence import (
    SCALAR_METRICS,
    _relative_l2,
    _relative_change,
    _trajectory_variation,
)


GRID_QUALIFYING_SCALAR_METRICS = (
    "solved_dipole_coefficient",
    "body_vertical_force_coefficient",
    "computed_pressure_peak",
    "computed_peak_eta",
)
OPTIONAL_REFERENCE_METRICS = (
    "free_surface_nrmse",
    "pressure_nrmse",
)


REGRID_STATE_QUALIFICATION_FIELDS = (
    "kinematic_rms",
    "solved_dipole_coefficient",
    "body_pressure_max",
    "body_vertical_force_coefficient",
    "measured_s_lambda",
)


def _common_coordinate_relative_l2(
    coarse: pd.DataFrame,
    fine: pd.DataFrame,
    *,
    coordinate: str,
    value: str,
    segment: str | None = None,
    sample_count: int = 301,
) -> float:
    if segment is not None and "segment" in coarse and "segment" in fine:
        coarse = coarse[coarse["segment"] == segment]
        fine = fine[fine["segment"] == segment]
    coarse = coarse.sort_values(coordinate).drop_duplicates(coordinate)
    fine = fine.sort_values(coordinate).drop_duplicates(coordinate)
    coarse_x = coarse[coordinate].to_numpy(dtype=float)
    fine_x = fine[coordinate].to_numpy(dtype=float)
    lower = max(float(np.min(coarse_x)), float(np.min(fine_x)))
    upper = min(float(np.max(coarse_x)), float(np.max(fine_x)))
    if not upper > lower:
        raise ValueError(f"Curves have no common {coordinate} interval.")
    target = np.linspace(lower, upper, sample_count)
    coarse_value = np.interp(
        target, coarse_x, coarse[value].to_numpy(dtype=float)
    )
    fine_value = np.interp(target, fine_x, fine[value].to_numpy(dtype=float))
    return _relative_l2(coarse_value, fine_value)


def _grid_curve_variation(
    coarse: dict[str, Any], fine: dict[str, Any]
) -> dict[str, float]:
    result = {
        "free_surface_eta_relative_l2": _common_coordinate_relative_l2(
            coarse["outer"],
            fine["outer"],
            coordinate="xi",
            value="eta",
        ),
        "body_pressure_curve_relative_l2": _common_coordinate_relative_l2(
            coarse["pressure"],
            fine["pressure"],
            coordinate="eta",
            value="pressure_coefficient",
            segment="body",
        ),
        "full_body_pressure_curve_relative_l2": _common_coordinate_relative_l2(
            coarse["pressure"],
            fine["pressure"],
            coordinate="eta",
            value="pressure_coefficient",
        ),
    }
    if "segment" in coarse["pressure"] and "segment" in fine["pressure"]:
        result["shallow_jet_pressure_curve_relative_l2_diagnostic"] = (
            _common_coordinate_relative_l2(
                coarse["pressure"],
                fine["pressure"],
                coordinate="eta",
                value="pressure_coefficient",
                segment="shallow_jet_body",
            )
        )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare coupled self-similar wedge continuations on explicitly "
            "different outer free-surface grids."
        )
    )
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variation-limit", type=float, default=0.05)
    parser.add_argument("--pseudo-time-limit", type=float, default=0.05)
    parser.add_argument("--geometry-limit", type=float, default=0.001)
    return parser


def _load_run(directory: Path) -> dict[str, Any]:
    source = directory.resolve()
    resume_path = source / "resume_summary.json"
    regrid_path = source / "regrid_summary.json"
    if resume_path.exists():
        summary = json.loads(resume_path.read_text(encoding="utf-8"))
        source_state = summary["source_checkpoint"]
        source_time = float(source_state["cumulative_pseudo_time"])
        final_time = float(summary["continuation"]["cumulative_pseudo_time"])
        regrid = None
    elif regrid_path.exists():
        summary = json.loads(regrid_path.read_text(encoding="utf-8"))
        source_state = summary["source_checkpoint"]
        source_time = 0.0
        final_time = float(summary["continuation"]["pseudo_time"])
        regrid = summary["regrid"]
    else:
        raise ValueError(f"Run {source} has no resume or regrid summary.")
    metadata = json.loads(
        (source / "coupled_checkpoint.json").read_text(encoding="utf-8")
    )
    panel_count = int(metadata["config"]["free_surface_panels"])
    overrides = source_state.get("continuation_config_overrides", {})
    cfl = float(overrides.get("pseudo_cfl", metadata["config"]["pseudo_cfl"]))
    history = pd.read_csv(source / "coupled_pseudo_time_history.csv")
    final = summary["final_state"]
    distributed = summary["post_solve_reference_metrics"]
    scalar = summary["post_solve_scalar_reference_metrics"]
    pressure = pd.read_csv(source / "coupled_body_pressure.csv")
    pressure_values = pressure["pressure_coefficient"].to_numpy(dtype=float)
    pressure_peak_index = int(np.argmax(pressure_values))
    kinematic_convergence_integral = final.get(
        "kinematic_convergence_integral",
        final.get("kinematic_integral_linear_exact", final.get("kinematic_integral")),
    )
    if kinematic_convergence_integral is None:
        raise ValueError(
            f"Run {source} has no exact kinematic convergence integral."
        )
    metrics = {
        "kinematic_rms": float(final["kinematic_rms"]),
        "kinematic_convergence_integral": float(kinematic_convergence_integral),
        "root_body_eta": float(history.iloc[-1]["root_body_eta"]),
        "interface_s_lambda": float(final["interface_s_lambda"]),
        "measured_s_lambda": float(final["measured_s_lambda"]),
        "solved_dipole_coefficient": float(final["solved_dipole_coefficient"]),
        "body_vertical_force_coefficient": float(
            final["body_vertical_force_coefficient"]
        ),
        "computed_pressure_peak": float(
            scalar.get(
                "computed_pressure_peak",
                final.get("body_pressure_max", pressure_values[pressure_peak_index]),
            )
        ),
        "computed_peak_eta": float(
            scalar.get(
                "computed_peak_eta",
                pressure["eta"].iloc[pressure_peak_index],
            )
        ),
    }
    for name in OPTIONAL_REFERENCE_METRICS:
        if name in distributed and distributed[name] is not None:
            value = float(distributed[name])
            if np.isfinite(value):
                metrics[name] = value
    return {
        "directory": source,
        "name": source.name,
        "panel_count": panel_count,
        "cfl": cfl,
        "root_state_recovery": metadata["config"].get(
            "coupled_root_state_recovery",
            "first_panel_midpoint",
        ),
        "linear_gradient_recovery": metadata["config"].get(
            "coupled_linear_gradient_recovery",
            "element",
        ),
        "linear_corner_treatment": metadata["config"].get(
            "coupled_linear_corner_treatment",
            "shared_node",
        ),
        "linear_cusp_velocity_recovery": metadata["config"].get(
            "coupled_linear_cusp_velocity_recovery",
            "connected_average",
        ),
        "steps": int(summary["continuation"]["accepted_iterations"]),
        "source_time": source_time,
        "added_time": final_time - source_time,
        "source_hashes": source_state["source_hashes"],
        "root_relative_mismatch": float(final["relative_s_lambda_mismatch"]),
        "metrics": metrics,
        "history": history,
        "outer": pd.read_csv(source / "coupled_checkpoint_outer_nodes.csv"),
        "pressure": pressure,
        "regrid": regrid,
    }


def analyze_grid_convergence(
    directories: list[Path],
    *,
    variation_limit: float = 0.05,
    pseudo_time_limit: float = 0.05,
    geometry_limit: float = 0.001,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if len(directories) < 2:
        raise ValueError("At least two spatial grid levels are required.")
    runs = sorted((_load_run(path) for path in directories), key=lambda item: item["panel_count"])
    if len({run["panel_count"] for run in runs}) != len(runs):
        raise ValueError("Each convergence run must use a distinct panel count.")
    same_source = len(
        {json.dumps(run["source_hashes"], sort_keys=True) for run in runs}
    ) == 1
    same_cfl = len({run["cfl"] for run in runs}) == 1
    same_root_recovery = len({run["root_state_recovery"] for run in runs}) == 1
    same_linear_algorithm = len(
        {
            (
                run["linear_gradient_recovery"],
                run["linear_corner_treatment"],
                run["linear_cusp_velocity_recovery"],
            )
            for run in runs
        }
    ) == 1
    times = np.asarray([run["added_time"] for run in runs], dtype=float)
    pseudo_time_spread = float(
        (np.max(times) - np.min(times))
        / max(float(np.mean(times)), np.finfo(float).eps)
    )

    level_rows = []
    regrid_qualification_pass = True
    for run in runs:
        row = {
            "run": run["name"],
            "outer_panel_count": run["panel_count"],
            "pseudo_cfl": run["cfl"],
            "root_state_recovery": run["root_state_recovery"],
            "linear_gradient_recovery": run["linear_gradient_recovery"],
            "linear_corner_treatment": run["linear_corner_treatment"],
            "linear_cusp_velocity_recovery": run[
                "linear_cusp_velocity_recovery"
            ],
            "accepted_steps": run["steps"],
            "added_pseudo_time": run["added_time"],
            "root_relative_mismatch": run["root_relative_mismatch"],
            **run["metrics"],
        }
        if run["regrid"] is not None:
            regrid = run["regrid"]
            row["regrid_geometry_relative_l2"] = float(
                regrid["geometry_relative_l2"]
            )
            selected = {
                name: float(regrid["state_relative_changes"][name])
                for name in REGRID_STATE_QUALIFICATION_FIELDS
                if not (
                    name == "measured_s_lambda"
                    and regrid.get("source_root_state_recovery")
                    != regrid.get("target_root_state_recovery")
                )
            }
            row["regrid_maximum_selected_state_change"] = max(selected.values())
            regrid_qualification_pass &= (
                row["regrid_geometry_relative_l2"] <= geometry_limit
                and row["regrid_maximum_selected_state_change"] <= variation_limit
            )
        level_rows.append(row)
    levels = pd.DataFrame(level_rows)

    pair_rows: list[dict[str, Any]] = []
    for coarse, fine in zip(runs[:-1], runs[1:]):
        row: dict[str, Any] = {
            "coarse_panel_count": coarse["panel_count"],
            "fine_panel_count": fine["panel_count"],
            "pseudo_time_relative_difference": _relative_change(
                coarse["added_time"], fine["added_time"]
            ),
        }
        for name in SCALAR_METRICS:
            if name in coarse["metrics"] and name in fine["metrics"]:
                row[f"{name}_relative_change"] = _relative_change(
                    coarse["metrics"][name], fine["metrics"][name]
                )
        matched_trajectory_available = (
            coarse["added_time"] > np.finfo(float).eps
            and fine["added_time"] > np.finfo(float).eps
        )
        row["matched_pseudo_time_trajectory_available"] = (
            matched_trajectory_available
        )
        if matched_trajectory_available:
            trajectory_names = ["kinematic_rms", "root_body_eta"]
            if all(
                "kinematic_convergence_integral" in run["history"].columns
                for run in (coarse, fine)
            ):
                trajectory_names.append("kinematic_convergence_integral")
            row.update(
                _trajectory_variation(
                    coarse,
                    fine,
                    names=tuple(trajectory_names),
                )
            )
        row.update(_grid_curve_variation(coarse, fine))
        pair_rows.append(row)
    pairs = pd.DataFrame(pair_rows)
    variation_columns = [
        f"{name}_relative_change" for name in GRID_QUALIFYING_SCALAR_METRICS
    ] + [
        "free_surface_eta_relative_l2",
        "body_pressure_curve_relative_l2",
        "full_body_pressure_curve_relative_l2",
    ]
    finest = pairs.iloc[-1]
    finest_variations = {
        name: float(finest[name]) for name in variation_columns
    }
    finest_pass = all(value <= variation_limit for value in finest_variations.values())
    root_mismatch_pass = all(
        run["root_relative_mismatch"] <= variation_limit for run in runs[-2:]
    )
    status = (
        "PASS"
        if same_source
        and same_cfl
        and same_root_recovery
        and same_linear_algorithm
        and pseudo_time_spread <= pseudo_time_limit
        and regrid_qualification_pass
        and finest_pass
        and root_mismatch_pass
        else "FAIL"
    )
    report = {
        "status": status,
        "scope": "spatial_grid_convergence_only",
        "physical_validation_status": "FAIL",
        "grid_level_count": len(runs),
        "three_level_trend_established": len(runs) >= 3,
        "same_frozen_source_checkpoint": same_source,
        "same_pseudo_cfl": same_cfl,
        "same_root_state_recovery": same_root_recovery,
        "same_linear_algorithm": same_linear_algorithm,
        "pseudo_time_relative_spread": pseudo_time_spread,
        "pseudo_time_limit": pseudo_time_limit,
        "variation_limit": variation_limit,
        "geometry_limit": geometry_limit,
        "regrid_qualification_pass": bool(regrid_qualification_pass),
        "finest_pair": {
            "coarse_panel_count": int(finest["coarse_panel_count"]),
            "fine_panel_count": int(finest["fine_panel_count"]),
            "variations": finest_variations,
            "root_mismatch_values": [
                float(run["root_relative_mismatch"]) for run in runs[-2:]
            ],
            "diagnostic_kinematic_convergence_integral_relative_change": float(
                finest["kinematic_convergence_integral_relative_change"]
            ),
        },
        "interpretation": (
            "PASS proves spatial stability and a three-level trend for the frozen "
            "state and matched continuation only; the wedge pressure benchmark "
            "remains failed."
            if len(runs) >= 3
            else "PASS proves two-level spatial stability for the frozen state and "
            "matched continuation only. A third grid is needed for an observed "
            "trend, and the wedge pressure benchmark remains failed."
        ),
    }
    return levels, pairs, report


def _plot(output: Path, levels: pd.DataFrame) -> None:
    ordered = levels.sort_values("outer_panel_count")
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    axes[0].plot(ordered["outer_panel_count"], ordered["kinematic_rms"], "o-")
    axes[0].set(xlabel="Outer free-surface panels", ylabel="Kinematic RMS")
    axes[0].grid(True, alpha=0.25)
    if {"pressure_nrmse", "free_surface_nrmse"}.issubset(ordered.columns):
        axes[1].plot(ordered["outer_panel_count"], ordered["pressure_nrmse"], "o-", label="pressure NRMSE")
        axes[1].plot(ordered["outer_panel_count"], ordered["free_surface_nrmse"], "s-", label="free-surface NRMSE")
        axes[1].set(ylabel="Post-solve reference error")
    else:
        axes[1].plot(
            ordered["outer_panel_count"],
            ordered["kinematic_convergence_integral"],
            "o-",
            label="exact kinematic integral",
        )
        axes[1].set_yscale("log")
        axes[1].set(ylabel="Reference-isolated diagnostic")
    axes[1].set(xlabel="Outer free-surface panels")
    axes[1].legend()
    axes[1].grid(True, alpha=0.25)
    figure.suptitle("Self-similar wedge spatial-grid convergence")
    figure.savefig(output / "grid_convergence.png", dpi=180)
    plt.close(figure)


def main() -> int:
    args = _parser().parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    levels, pairs, report = analyze_grid_convergence(
        args.runs,
        variation_limit=args.variation_limit,
        pseudo_time_limit=args.pseudo_time_limit,
        geometry_limit=args.geometry_limit,
    )
    levels.to_csv(output / "grid_levels.csv", index=False)
    pairs.to_csv(output / "grid_pairwise.csv", index=False)
    (output / "grid_convergence.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    _plot(output, levels)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
