from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ALLOWED_CONFIG_DIFFERENCES = {
    "far_radius",
    "free_surface_panels",
    "far_field_panels",
    "symmetry_panels",
    "free_surface_panel_growth",
}

TRANSFORMATION_KEYS = (
    "type",
    "basis",
    "mode_count",
    "global_mode_count",
    "root_support_fraction",
    "fixed_root_node_count",
    "residual_space",
    "root_inner_iterations",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare converged self-similar wedge solutions on successively "
            "larger, density-matched far domains."
        )
    )
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variation-limit", type=float, default=0.05)
    parser.add_argument("--kinematic-limit", type=float, default=1.0e-3)
    parser.add_argument("--density-limit", type=float, default=0.05)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_change(first: float, second: float) -> float:
    scale = max(abs(first), abs(second), np.finfo(float).eps)
    return abs(second - first) / scale


def _common_curve_metrics(
    coarse: pd.DataFrame,
    fine: pd.DataFrame,
    *,
    coordinate: str,
    value: str,
    segment: str | None = None,
    sample_count: int = 1001,
) -> dict[str, float]:
    if segment is not None:
        coarse = coarse[coarse["segment"] == segment]
        fine = fine[fine["segment"] == segment]
    coarse = coarse.sort_values(coordinate).drop_duplicates(coordinate)
    fine = fine.sort_values(coordinate).drop_duplicates(coordinate)
    lower = max(float(coarse[coordinate].min()), float(fine[coordinate].min()))
    upper = min(float(coarse[coordinate].max()), float(fine[coordinate].max()))
    if not upper > lower:
        raise ValueError(f"Curves have no common {coordinate} interval.")
    target = np.linspace(lower, upper, sample_count)
    coarse_values = np.interp(target, coarse[coordinate], coarse[value])
    fine_values = np.interp(target, fine[coordinate], fine[value])
    difference = coarse_values - fine_values
    rmse = float(np.sqrt(np.mean(difference**2)))
    physical_range = max(
        float(np.ptp(coarse_values)),
        float(np.ptp(fine_values)),
        np.finfo(float).eps,
    )
    return {
        "common_coordinate_min": lower,
        "common_coordinate_max": upper,
        "rmse": rmse,
        "nrmse_by_combined_range": rmse / physical_range,
        "relative_l2_diagnostic": float(
            np.linalg.norm(difference)
            / max(float(np.linalg.norm(fine_values)), np.finfo(float).eps)
        ),
        "maximum_absolute_difference": float(np.max(np.abs(difference))),
        "mean_bias_coarse_minus_fine": float(np.mean(difference)),
    }


def _lineage_hashes(directory: Path, metadata: dict[str, Any]) -> set[str]:
    hashes = {_sha256(directory / "coupled_checkpoint.json")}
    current = metadata
    visited: set[Path] = set()
    while "parent_checkpoint" in current:
        parent = current["parent_checkpoint"]
        source_hash = parent.get("source_hashes", {}).get("coupled_checkpoint.json")
        if source_hash:
            hashes.add(str(source_hash))
        parent_path = Path(parent["path"])
        if not parent_path.is_absolute():
            parent_path = (directory / parent_path).resolve()
        metadata_path = parent_path / "coupled_checkpoint.json"
        if metadata_path in visited or not metadata_path.exists():
            break
        visited.add(metadata_path)
        current = json.loads(metadata_path.read_text(encoding="utf-8"))
    return hashes


def _load_run(directory: Path) -> dict[str, Any]:
    source = directory.resolve()
    metadata_path = source / "coupled_checkpoint.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    config = metadata["config"]
    state = metadata["expected_state"]
    outer_path = source / "low_mode_trust_region_final_outer_nodes.csv"
    if not outer_path.exists():
        outer_path = source / metadata["files"]["outer_nodes"]["name"]
    pressure_path = source / "coupled_body_pressure.csv"
    if not pressure_path.exists():
        raise ValueError(f"Run {source} has no coupled body-pressure artifact.")
    interface = float(state["interface_s_lambda"])
    measured = float(state["measured_s_lambda"])
    return {
        "directory": source,
        "name": source.name,
        "config": config,
        "transformation": metadata.get("state_transformation", {}),
        "lineage_hashes": _lineage_hashes(source, metadata),
        "far_radius": float(config["far_radius"]),
        "panel_count": int(config["free_surface_panels"]),
        "panel_density": float(config["free_surface_panels"])
        / float(config["far_radius"]),
        "kinematic_integral": float(state["kinematic_integral_linear_exact"]),
        "pressure_peak": float(state["body_pressure_max"]),
        "vertical_force": float(state["body_vertical_force_coefficient"]),
        "dipole_coefficient": float(state["solved_dipole_coefficient"]),
        "root_relative_mismatch": abs(measured - interface)
        / max(abs(interface), np.finfo(float).eps),
        "outer": pd.read_csv(outer_path),
        "pressure": pd.read_csv(pressure_path),
        "checkpoint_sha256": _sha256(metadata_path),
    }


def _config_signature(config: dict[str, Any]) -> str:
    retained = {
        key: value
        for key, value in config.items()
        if key not in ALLOWED_CONFIG_DIFFERENCES
    }
    return json.dumps(retained, sort_keys=True)


def _transformation_signature(transformation: dict[str, Any]) -> str:
    retained = {key: transformation.get(key) for key in TRANSFORMATION_KEYS}
    return json.dumps(retained, sort_keys=True)


def analyze_far_domain_convergence(
    directories: list[Path],
    *,
    variation_limit: float = 0.05,
    kinematic_limit: float = 1.0e-3,
    density_limit: float = 0.05,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if len(directories) < 2:
        raise ValueError("At least two far-domain levels are required.")
    runs = sorted((_load_run(path) for path in directories), key=lambda run: run["far_radius"])
    if len({run["far_radius"] for run in runs}) != len(runs):
        raise ValueError("Each run must use a distinct far radius.")
    same_config = len({_config_signature(run["config"]) for run in runs}) == 1
    same_algorithm = len(
        {_transformation_signature(run["transformation"]) for run in runs}
    ) == 1
    common_lineage = set.intersection(*(run["lineage_hashes"] for run in runs))

    levels = pd.DataFrame(
        [
            {
                "run": run["name"],
                "far_radius": run["far_radius"],
                "outer_panel_count": run["panel_count"],
                "panels_per_radius": run["panel_density"],
                "kinematic_convergence_integral": run["kinematic_integral"],
                "kinematic_absolute_pass": (
                    run["kinematic_integral"] <= kinematic_limit
                ),
                "pressure_peak": run["pressure_peak"],
                "vertical_force": run["vertical_force"],
                "dipole_coefficient": run["dipole_coefficient"],
                "root_relative_mismatch": run["root_relative_mismatch"],
                "checkpoint_sha256": run["checkpoint_sha256"],
            }
            for run in runs
        ]
    )

    pair_rows: list[dict[str, Any]] = []
    for coarse, fine in zip(runs[:-1], runs[1:]):
        free_surface = _common_curve_metrics(
            coarse["outer"], fine["outer"], coordinate="xi", value="eta"
        )
        pressure = _common_curve_metrics(
            coarse["pressure"],
            fine["pressure"],
            coordinate="eta",
            value="pressure_coefficient",
            segment="body",
        )
        pair_rows.append(
            {
                "coarse_far_radius": coarse["far_radius"],
                "fine_far_radius": fine["far_radius"],
                "panel_density_relative_change": _relative_change(
                    coarse["panel_density"], fine["panel_density"]
                ),
                "coarse_kinematic_integral": coarse["kinematic_integral"],
                "fine_kinematic_integral": fine["kinematic_integral"],
                "kinematic_relative_change_diagnostic": _relative_change(
                    coarse["kinematic_integral"], fine["kinematic_integral"]
                ),
                "free_surface_nrmse_by_combined_range": free_surface[
                    "nrmse_by_combined_range"
                ],
                "free_surface_relative_l2_diagnostic": free_surface[
                    "relative_l2_diagnostic"
                ],
                "free_surface_maximum_absolute_difference": free_surface[
                    "maximum_absolute_difference"
                ],
                "pressure_curve_nrmse_by_combined_range": pressure[
                    "nrmse_by_combined_range"
                ],
                "pressure_curve_relative_l2_diagnostic": pressure[
                    "relative_l2_diagnostic"
                ],
                "pressure_peak_relative_change": _relative_change(
                    coarse["pressure_peak"], fine["pressure_peak"]
                ),
                "vertical_force_relative_change": _relative_change(
                    coarse["vertical_force"], fine["vertical_force"]
                ),
                "dipole_coefficient_relative_change": _relative_change(
                    coarse["dipole_coefficient"], fine["dipole_coefficient"]
                ),
            }
        )
    pairs = pd.DataFrame(pair_rows)
    finest = pairs.iloc[-1]
    primary_variations = {
        name: float(finest[name])
        for name in (
            "free_surface_nrmse_by_combined_range",
            "pressure_curve_nrmse_by_combined_range",
            "pressure_peak_relative_change",
            "vertical_force_relative_change",
            "dipole_coefficient_relative_change",
        )
    }
    absolute_kinematic_pass = bool(
        levels["kinematic_absolute_pass"].iloc[-2:].all()
    )
    density_pass = bool(
        float(finest["panel_density_relative_change"]) <= density_limit
    )
    physical_variation_pass = all(
        value <= variation_limit for value in primary_variations.values()
    )
    status = (
        "PASS"
        if same_config
        and same_algorithm
        and bool(common_lineage)
        and absolute_kinematic_pass
        and density_pass
        and physical_variation_pass
        else "FAIL"
    )
    report = {
        "status": status,
        "scope": "far_domain_convergence_only",
        "physical_validation_status": "FAIL",
        "same_non_far_configuration": same_config,
        "same_final_shape_algorithm": same_algorithm,
        "common_lineage_checkpoint_hashes": sorted(common_lineage),
        "kinematic_limit": kinematic_limit,
        "variation_limit": variation_limit,
        "density_limit": density_limit,
        "absolute_kinematic_pass": absolute_kinematic_pass,
        "density_match_pass": density_pass,
        "physical_variation_pass": physical_variation_pass,
        "finest_pair": {
            "coarse_far_radius": float(finest["coarse_far_radius"]),
            "fine_far_radius": float(finest["fine_far_radius"]),
            "primary_variations": primary_variations,
            "kinematic_relative_change_diagnostic": float(
                finest["kinematic_relative_change_diagnostic"]
            ),
            "free_surface_relative_l2_diagnostic": float(
                finest["free_surface_relative_l2_diagnostic"]
            ),
        },
        "interpretation": (
            "The kinematic integral is a residual with an absolute zero target. "
            "Each level must satisfy the absolute tolerance; its near-zero "
            "relative change is reported diagnostically but is not substituted "
            "for convergence of the free surface, pressure, and load outputs."
        ),
    }
    return levels, pairs, report


def _plot(output: Path, runs: list[dict[str, Any]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for run in runs:
        label = f"R={run['far_radius']:g}, N={run['panel_count']}"
        axes[0].plot(run["outer"]["xi"], run["outer"]["eta"], label=label)
        body = run["pressure"][run["pressure"]["segment"] == "body"]
        axes[1].plot(body["eta"], body["pressure_coefficient"], label=label)
    axes[0].set(xlabel="xi", ylabel="eta", title="Outer free surface")
    axes[1].set(xlabel="eta on wedge", ylabel="Cp", title="Body pressure")
    for axis in axes:
        axis.grid(True, alpha=0.25)
        axis.legend()
    figure.savefig(output / "far_domain_convergence.png", dpi=180)
    plt.close(figure)


def main() -> int:
    args = _parser().parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    levels, pairs, report = analyze_far_domain_convergence(
        args.runs,
        variation_limit=args.variation_limit,
        kinematic_limit=args.kinematic_limit,
        density_limit=args.density_limit,
    )
    levels.to_csv(output / "far_domain_levels.csv", index=False)
    pairs.to_csv(output / "far_domain_pairwise.csv", index=False)
    (output / "far_domain_convergence.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    _plot(output, sorted((_load_run(path) for path in args.runs), key=lambda run: run["far_radius"]))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
