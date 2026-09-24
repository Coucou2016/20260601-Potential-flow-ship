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


SCALAR_METRICS = (
    "kinematic_rms",
    "kinematic_convergence_integral",
    "root_body_eta",
    "interface_s_lambda",
    "measured_s_lambda",
    "solved_dipole_coefficient",
    "body_vertical_force_coefficient",
    "computed_pressure_peak",
    "computed_peak_eta",
    "free_surface_nrmse",
    "pressure_nrmse",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare coupled self-similar wedge continuations started from one "
            "checkpoint at matched pseudo-time and different pseudo-CFL values."
        )
    )
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variation-limit", type=float, default=0.05)
    parser.add_argument("--pseudo-time-limit", type=float, default=0.005)
    return parser


def _relative_change(first: float, second: float) -> float:
    scale = max(abs(first), abs(second), np.finfo(float).eps)
    return abs(second - first) / scale


def _relative_l2(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(float(np.linalg.norm(second)), np.finfo(float).eps)
    return float(np.linalg.norm(first - second) / scale)


def _resample_curve(
    frame: pd.DataFrame,
    *,
    coordinate: str,
    values: tuple[str, ...],
    sample_count: int = 301,
) -> tuple[np.ndarray, ...]:
    ordered = frame.sort_values(coordinate).drop_duplicates(coordinate)
    coordinate_values = ordered[coordinate].to_numpy(dtype=float)
    if len(coordinate_values) < 2 or not np.isfinite(coordinate_values).all():
        raise ValueError(f"Curve coordinate {coordinate!r} is not usable.")
    normalized = (coordinate_values - coordinate_values[0]) / (
        coordinate_values[-1] - coordinate_values[0]
    )
    target = np.linspace(0.0, 1.0, sample_count)
    result: list[np.ndarray] = [target]
    for name in values:
        data = ordered[name].to_numpy(dtype=float)
        if not np.isfinite(data).all():
            raise ValueError(f"Curve value {name!r} is not finite.")
        result.append(np.interp(target, normalized, data))
    return tuple(result)


def _load_run(directory: Path) -> dict[str, Any]:
    source = directory.resolve()
    summary = json.loads(
        (source / "resume_summary.json").read_text(encoding="utf-8")
    )
    history = pd.read_csv(source / "coupled_pseudo_time_history.csv")
    outer = pd.read_csv(source / "coupled_checkpoint_outer_nodes.csv")
    pressure = pd.read_csv(source / "coupled_body_pressure.csv")
    source_state = summary["source_checkpoint"]
    overrides = source_state.get("continuation_config_overrides", {})
    if "pseudo_cfl" in overrides:
        cfl = float(overrides["pseudo_cfl"])
    else:
        metadata = json.loads(
            (source / "coupled_checkpoint.json").read_text(encoding="utf-8")
        )
        cfl = float(metadata["config"]["pseudo_cfl"])
    final = summary["final_state"]
    distributed = summary["post_solve_reference_metrics"]
    scalar = summary["post_solve_scalar_reference_metrics"]
    last = history.iloc[-1]
    metrics = {
        "kinematic_rms": float(final["kinematic_rms"]),
        "kinematic_convergence_integral": float(
            final["kinematic_convergence_integral"]
        ),
        "root_body_eta": float(last["root_body_eta"]),
        "interface_s_lambda": float(final["interface_s_lambda"]),
        "measured_s_lambda": float(final["measured_s_lambda"]),
        "solved_dipole_coefficient": float(final["solved_dipole_coefficient"]),
        "body_vertical_force_coefficient": float(
            final["body_vertical_force_coefficient"]
        ),
        "computed_pressure_peak": float(scalar["computed_pressure_peak"]),
        "computed_peak_eta": float(scalar["computed_peak_eta"]),
        "free_surface_nrmse": float(distributed["free_surface_nrmse"]),
        "pressure_nrmse": float(distributed["pressure_nrmse"]),
    }
    source_time = float(source_state["cumulative_pseudo_time"])
    final_time = float(summary["continuation"]["cumulative_pseudo_time"])
    return {
        "directory": source,
        "name": source.name,
        "cfl": cfl,
        "steps": int(summary["continuation"]["accepted_iterations"]),
        "source_time": source_time,
        "added_time": final_time - source_time,
        "source_hashes": source_state["source_hashes"],
        "root_relative_mismatch": float(final["relative_s_lambda_mismatch"]),
        "metrics": metrics,
        "history": history,
        "outer": outer,
        "pressure": pressure,
    }


def _trajectory_variation(
    coarse: dict[str, Any],
    fine: dict[str, Any],
    *,
    names: tuple[str, ...] = (
        "kinematic_rms",
        "kinematic_convergence_integral",
        "root_body_eta",
    ),
) -> dict[str, float]:
    target = np.linspace(0.0, 1.0, 101)
    compared: dict[str, list[np.ndarray]] = {}
    for run in (coarse, fine):
        history = run["history"]
        selected = history[history["pseudo_time"] >= run["source_time"]].copy()
        added = selected["pseudo_time"].to_numpy(dtype=float) - run["source_time"]
        normalized = added / run["added_time"]
        for name in names:
            compared.setdefault(name, []).append(
                np.interp(target, normalized, selected[name].to_numpy(dtype=float))
            )
    return {
        f"{name}_trajectory_relative_l2": _relative_l2(values[0], values[1])
        for name, values in compared.items()
    }


def _curve_variation(coarse: dict[str, Any], fine: dict[str, Any]) -> dict[str, float]:
    _, coarse_eta = _resample_curve(
        coarse["outer"], coordinate="xi", values=("eta",)
    )
    _, fine_eta = _resample_curve(
        fine["outer"], coordinate="xi", values=("eta",)
    )
    _, coarse_pressure = _resample_curve(
        coarse["pressure"], coordinate="eta", values=("pressure_coefficient",)
    )
    _, fine_pressure = _resample_curve(
        fine["pressure"], coordinate="eta", values=("pressure_coefficient",)
    )
    return {
        "free_surface_eta_relative_l2": _relative_l2(coarse_eta, fine_eta),
        "pressure_curve_relative_l2": _relative_l2(
            coarse_pressure,
            fine_pressure,
        ),
    }


def analyze_time_step_convergence(
    directories: list[Path],
    *,
    variation_limit: float = 0.05,
    pseudo_time_limit: float = 0.005,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if len(directories) < 2:
        raise ValueError("At least two time-step levels are required.")
    runs = sorted((_load_run(path) for path in directories), key=lambda item: -item["cfl"])
    if len({run["cfl"] for run in runs}) != len(runs):
        raise ValueError("Each convergence run must use a distinct pseudo-CFL.")
    source_signatures = {
        json.dumps(run["source_hashes"], sort_keys=True) for run in runs
    }
    same_source = len(source_signatures) == 1
    added_times = np.asarray([run["added_time"] for run in runs], dtype=float)
    pseudo_time_spread = float(
        (np.max(added_times) - np.min(added_times))
        / max(float(np.mean(added_times)), np.finfo(float).eps)
    )

    level_rows = []
    for run in runs:
        level_rows.append(
            {
                "run": run["name"],
                "pseudo_cfl": run["cfl"],
                "accepted_steps": run["steps"],
                "added_pseudo_time": run["added_time"],
                "root_relative_mismatch": run["root_relative_mismatch"],
                **run["metrics"],
            }
        )
    levels = pd.DataFrame(level_rows)

    pair_rows: list[dict[str, Any]] = []
    for coarse, fine in zip(runs[:-1], runs[1:]):
        row: dict[str, Any] = {
            "coarse_cfl": coarse["cfl"],
            "fine_cfl": fine["cfl"],
            "pseudo_time_relative_difference": _relative_change(
                coarse["added_time"], fine["added_time"]
            ),
        }
        for name in SCALAR_METRICS:
            row[f"{name}_relative_change"] = _relative_change(
                coarse["metrics"][name], fine["metrics"][name]
            )
        row.update(_trajectory_variation(coarse, fine))
        row.update(_curve_variation(coarse, fine))
        pair_rows.append(row)
    pairs = pd.DataFrame(pair_rows)
    variation_columns = [
        name
        for name in pairs.columns
        if name.endswith("_relative_change") or name.endswith("_relative_l2")
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
        and pseudo_time_spread <= pseudo_time_limit
        and finest_pass
        and root_mismatch_pass
        else "FAIL"
    )
    report = {
        "status": status,
        "scope": "time_step_convergence_only",
        "physical_validation_status": "FAIL",
        "same_frozen_source_checkpoint": same_source,
        "pseudo_time_relative_spread": pseudo_time_spread,
        "pseudo_time_limit": pseudo_time_limit,
        "variation_limit": variation_limit,
        "finest_pair": {
            "coarse_cfl": float(finest["coarse_cfl"]),
            "fine_cfl": float(finest["fine_cfl"]),
            "variations": finest_variations,
            "root_mismatch_values": [
                float(run["root_relative_mismatch"]) for run in runs[-2:]
            ],
        },
        "interpretation": (
            "PASS proves time-step stability at the frozen grid and state only. "
            "It does not pass the wedge pressure benchmark or Gate 2."
        ),
    }
    return levels, pairs, report


def _plot(output: Path, levels: pd.DataFrame, pairs: pd.DataFrame) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    ordered = levels.sort_values("pseudo_cfl")
    axes[0].plot(ordered["pseudo_cfl"], ordered["kinematic_rms"], "o-")
    axes[0].set(xlabel="Pseudo-CFL", ylabel="Kinematic RMS")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(ordered["pseudo_cfl"], ordered["pressure_nrmse"], "o-", label="pressure NRMSE")
    axes[1].plot(ordered["pseudo_cfl"], ordered["free_surface_nrmse"], "s-", label="free-surface NRMSE")
    axes[1].set(xlabel="Pseudo-CFL", ylabel="Post-solve reference error")
    axes[1].legend()
    axes[1].grid(True, alpha=0.25)
    figure.suptitle("Self-similar wedge time-step convergence")
    figure.savefig(output / "time_step_convergence.png", dpi=180)
    plt.close(figure)


def main() -> int:
    args = _parser().parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    levels, pairs, report = analyze_time_step_convergence(
        args.runs,
        variation_limit=args.variation_limit,
        pseudo_time_limit=args.pseudo_time_limit,
    )
    levels.to_csv(output / "time_step_levels.csv", index=False)
    pairs.to_csv(output / "time_step_pairwise.csv", index=False)
    (output / "time_step_convergence.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    _plot(output, levels, pairs)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
