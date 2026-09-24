from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _expected_panel_fractions(config: dict[str, Any]) -> np.ndarray:
    count = int(config["free_surface_panels"])
    mode = str(config.get("coupled_outer_grid_mode", "geometric_root"))
    if mode == "frozen_monitor":
        fractions = np.asarray(
            config.get("coupled_outer_monitor_fractions"),
            dtype=float,
        )
        if fractions.shape != (count + 1,):
            raise ValueError("Frozen monitor fractions do not match the panel count.")
        length = np.diff(fractions)
    elif mode == "double_ended":
        coordinate = np.linspace(0.0, 1.0, count)
        root = float(config["coupled_outer_root_spacing_ratio"])
        far = float(config["coupled_outer_far_spacing_ratio"])
        decay = float(config["coupled_outer_endpoint_decay"])
        length = np.exp(
            np.log(root) * np.power(1.0 - coordinate, decay)
            + np.log(far) * np.power(coordinate, decay)
        )
    else:
        length = np.power(
            float(config["free_surface_panel_growth"]),
            np.arange(count, dtype=float),
        )
    return length / np.sum(length)


def _load_run(run: Path) -> dict[str, Any]:
    summary_path = run / "regrid_summary.json"
    if not summary_path.exists():
        summary_path = run / "resume_summary.json"
    if not summary_path.exists():
        raise ValueError(f"No regrid/resume summary found in {run}.")
    checkpoint_path = run / "coupled_checkpoint.json"
    if not checkpoint_path.exists():
        raise ValueError(f"No coupled checkpoint found in {run}.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    config = checkpoint["config"]
    node_path = run / "coupled_checkpoint_outer_nodes.csv"
    if not node_path.exists():
        raise ValueError(f"No coupled outer-node file found in {run}.")
    nodes = pd.read_csv(node_path)[["xi", "eta"]].to_numpy(dtype=float)
    actual_spacing = np.linalg.norm(np.diff(nodes, axis=0), axis=1)
    actual_spacing /= np.sum(actual_spacing)
    expected_spacing = _expected_panel_fractions(config)
    if actual_spacing.shape != expected_spacing.shape:
        raise ValueError(f"Outer-node count disagrees with the configuration in {run}.")
    grid_error = float(
        np.max(np.abs(actual_spacing - expected_spacing))
        / max(float(np.max(expected_spacing)), np.finfo(float).eps)
    )
    final = summary["final_state"]
    distributed = summary.get("post_solve_reference_metrics", {})
    scalar = summary.get("post_solve_scalar_reference_metrics", {})
    return {
        "run": run.name,
        "path": str(run.resolve()),
        "summary_file": summary_path.name,
        "outer_panels": int(config["free_surface_panels"]),
        "outer_panels_per_radius": float(config["free_surface_panels"])
        / float(config["far_radius"]),
        "far_radius": float(config["far_radius"]),
        "pseudo_cfl": float(config["pseudo_cfl"]),
        "grid_mode": str(config.get("coupled_outer_grid_mode", "geometric_root")),
        "root_spacing_ratio": float(
            config.get("coupled_outer_root_spacing_ratio", np.nan)
        ),
        "far_spacing_ratio": float(
            config.get("coupled_outer_far_spacing_ratio", np.nan)
        ),
        "endpoint_decay": float(config.get("coupled_outer_endpoint_decay", np.nan)),
        "linear_gradient_recovery": str(
            config.get("coupled_linear_gradient_recovery", "element")
        ),
        "linear_corner_treatment": str(
            config.get("coupled_linear_corner_treatment", "shared_node")
        ),
        "linear_cusp_velocity_recovery": str(
            config.get(
                "coupled_linear_cusp_velocity_recovery",
                "connected_average",
            )
        ),
        "completed_iterations": int(checkpoint["completed_iterations"]),
        "cumulative_pseudo_time": float(checkpoint["cumulative_pseudo_time"]),
        "kinematic_integral": float(final["kinematic_integral"]),
        "kinematic_integral_linear_exact": (
            float(final["kinematic_integral_linear_exact"])
            if final.get("kinematic_integral_linear_exact") is not None
            else np.nan
        ),
        "kinematic_acceptance_integral": float(
            final.get("kinematic_convergence_integral")
            if final.get("kinematic_convergence_integral") is not None
            else (
                final["kinematic_integral_linear_exact"]
                if final.get("kinematic_integral_linear_exact") is not None
                else final["kinematic_integral"]
            )
        ),
        "kinematic_rms": float(final["kinematic_rms"]),
        "condition_number": float(final["bem_condition_number"]),
        "free_surface_nrmse": float(distributed.get("free_surface_nrmse", np.nan)),
        "pressure_nrmse": float(distributed.get("pressure_nrmse", np.nan)),
        "pressure_peak_relative_error": float(
            scalar.get(
                "pressure_peak_relative_error",
                distributed.get("pressure_peak_relative_error", np.nan),
            )
        ),
        "pressure_peak_location_relative_error": float(
            scalar.get(
                "pressure_peak_location_relative_error",
                distributed.get("pressure_peak_location_relative_error", np.nan),
            )
        ),
        "reference_used_during_solve": bool(
            summary.get("reference_used_during_solve", True)
        ),
        "grid_distribution_relative_linf": grid_error,
        "grid_contract_pass": bool(grid_error <= 0.01),
    }


def _adjacent_changes(
    frame: pd.DataFrame,
    *,
    sweep: str,
    group_columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        ordered = group.sort_values(sweep, ascending=sweep != "pseudo_cfl")
        if len(ordered) < 2:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        group_data = dict(zip(group_columns, keys))
        for (_, coarse), (_, fine) in zip(
            ordered.iloc[:-1].iterrows(), ordered.iloc[1:].iterrows()
        ):
            coarse_history = pd.read_csv(
                Path(str(coarse["path"])) / "coupled_pseudo_time_history.csv"
            )
            fine_history = pd.read_csv(
                Path(str(fine["path"])) / "coupled_pseudo_time_history.csv"
            )
            common_time = min(
                float(coarse_history["pseudo_time"].iloc[-1]),
                float(fine_history["pseudo_time"].iloc[-1]),
            )
            metric_column = (
                "kinematic_convergence_integral"
                if "kinematic_convergence_integral" in coarse_history.columns
                and "kinematic_convergence_integral" in fine_history.columns
                else "kinematic_integral"
            )
            coarse_k = float(
                np.interp(
                    common_time,
                    coarse_history["pseudo_time"],
                    coarse_history[metric_column],
                )
            )
            fine_k = float(
                np.interp(
                    common_time,
                    fine_history["pseudo_time"],
                    fine_history[metric_column],
                )
            )
            rows.append(
                {
                    "sweep": sweep,
                    **group_data,
                    "coarse_run": coarse["run"],
                    "fine_run": fine["run"],
                    "coarse_level": float(coarse[sweep]),
                    "fine_level": float(fine[sweep]),
                    "comparison_pseudo_time": common_time,
                    "coarse_kinematic_integral": coarse_k,
                    "fine_kinematic_integral": fine_k,
                    "kinematic_integral_relative_change": abs(fine_k - coarse_k)
                    / max(abs(fine_k), np.finfo(float).eps),
                }
            )
    return rows


def analyze_endpoint_convergence(
    runs: list[Path],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not runs:
        raise ValueError("At least one run is required.")
    levels = pd.DataFrame([_load_run(path.resolve()) for path in runs])
    eligible = levels[
        levels["grid_contract_pass"] & ~levels["reference_used_during_solve"]
    ]
    if eligible.empty:
        raise ValueError("No run satisfies the declared grid and reference-isolation contract.")
    pairs = pd.DataFrame(
        _adjacent_changes(
            eligible,
            sweep="outer_panels",
            group_columns=[
                "far_radius",
                "pseudo_cfl",
                "grid_mode",
                "root_spacing_ratio",
                "far_spacing_ratio",
                "endpoint_decay",
                "linear_gradient_recovery",
                "linear_corner_treatment",
                "linear_cusp_velocity_recovery",
            ],
        )
        + _adjacent_changes(
            eligible,
            sweep="far_radius",
            group_columns=[
                "outer_panels_per_radius",
                "pseudo_cfl",
                "grid_mode",
                "root_spacing_ratio",
                "far_spacing_ratio",
                "endpoint_decay",
                "linear_gradient_recovery",
                "linear_corner_treatment",
                "linear_cusp_velocity_recovery",
            ],
        )
        + _adjacent_changes(
            eligible,
            sweep="pseudo_cfl",
            group_columns=[
                "outer_panels",
                "far_radius",
                "grid_mode",
                "root_spacing_ratio",
                "far_spacing_ratio",
                "endpoint_decay",
                "linear_gradient_recovery",
                "linear_corner_treatment",
                "linear_cusp_velocity_recovery",
            ],
        )
    )
    minimum = eligible.loc[eligible["kinematic_acceptance_integral"].idxmin()]
    coverage = {
        "root_spacing_level_count": int(eligible["root_spacing_ratio"].nunique()),
        "far_radius_level_count": int(eligible["far_radius"].nunique()),
        "pseudo_cfl_level_count": int(eligible["pseudo_cfl"].nunique()),
        "outer_panel_level_count": int(eligible["outer_panels"].nunique()),
    }
    metric_pass = bool(
        minimum["kinematic_acceptance_integral"] <= 1.0e-3
        and minimum["free_surface_nrmse"] <= 0.05
        and minimum["pressure_nrmse"] <= 0.10
        and minimum["pressure_peak_relative_error"] <= 0.05
        and minimum["pressure_peak_location_relative_error"] <= 0.05
    )
    coverage_pass = bool(
        coverage["root_spacing_level_count"] >= 3
        and coverage["far_radius_level_count"] >= 3
        and coverage["pseudo_cfl_level_count"] >= 2
        and coverage["outer_panel_level_count"] >= 2
    )
    pair_pass = bool(
        len(pairs) >= 3
        and np.all(pairs["kinematic_integral_relative_change"] <= 0.05)
    )
    accepted = bool(
        metric_pass
        and coverage_pass
        and pair_pass
        and bool(levels["grid_contract_pass"].all())
        and not levels["reference_used_during_solve"].any()
    )
    if accepted:
        classification = "TWENTY_DEG_ENDPOINT_CONVERGENCE_PASS"
    elif not coverage_pass:
        classification = "DIAGNOSTIC_MATRIX_INCOMPLETE"
    elif not metric_pass:
        classification = "PHYSICAL_THRESHOLDS_NOT_MET"
    else:
        classification = "LAST_LEVEL_CHANGE_NOT_CONVERGED"
    report = {
        "status": "self_similar_endpoint_convergence_audit",
        "validated": accepted,
        "reference_used_during_solve": bool(
            levels["reference_used_during_solve"].any()
        ),
        "grid_contract_pass": bool(levels["grid_contract_pass"].all()),
        "grid_contract_failed_runs": levels.loc[
            ~levels["grid_contract_pass"], "run"
        ].tolist(),
        "classification": classification,
        "thresholds": {
            "kinematic_integral_max": 1.0e-3,
            "free_surface_nrmse_max": 0.05,
            "pressure_nrmse_max": 0.10,
            "pressure_peak_relative_error_max": 0.05,
            "pressure_peak_location_relative_error_max": 0.05,
            "last_level_relative_change_max": 0.05,
        },
        "coverage": coverage,
        "coverage_pass": coverage_pass,
        "metric_pass": metric_pass,
        "pair_convergence_pass": pair_pass,
        "best_run": {
            "run": str(minimum["run"]),
            "kinematic_integral": float(minimum["kinematic_integral"]),
            "kinematic_integral_linear_exact": float(
                minimum["kinematic_integral_linear_exact"]
            ),
            "kinematic_acceptance_integral": float(
                minimum["kinematic_acceptance_integral"]
            ),
            "free_surface_nrmse": float(minimum["free_surface_nrmse"]),
            "pressure_nrmse": float(minimum["pressure_nrmse"]),
        },
        "run_count": len(levels),
        "eligible_run_count": len(eligible),
        "pair_count": len(pairs),
    }
    return levels, pairs, report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit double-endpoint grid, far-domain, and time-step convergence."
    )
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    levels, pairs, report = analyze_endpoint_convergence(args.run)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    levels.to_csv(output / "endpoint_convergence_levels.csv", index=False)
    pairs.to_csv(output / "endpoint_convergence_pairs.csv", index=False)
    (output / "endpoint_convergence_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    for radius, group in levels.groupby("far_radius"):
        ordered = group.sort_values("outer_panels")
        axis.plot(
            ordered["outer_panels"],
            ordered["kinematic_acceptance_integral"],
            "o-",
            label=f"R={radius:g}",
        )
    axis.axhline(1.0e-3, color="black", ls="--", lw=1.0, label="K threshold")
    axis.set(xlabel="Outer free-surface panels", ylabel="Iafrati Eq. (52) K")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.savefig(output / "endpoint_convergence.png", dpi=180)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
