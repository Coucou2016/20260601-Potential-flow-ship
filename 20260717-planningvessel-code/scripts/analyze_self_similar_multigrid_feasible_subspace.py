from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from scripts.diagnose_self_similar_low_mode_line_search import (
    angle_bisector_normals,
    maximum_midpoint_displacement_ratio,
)
from scripts.diagnose_self_similar_multigrid_trust_region import (
    _grid_residual_and_state,
    _rebuild_grids,
    multigrid_shape_basis,
    normalized_multigrid_residual,
)


def root_constrained_linear_reachability(
    jacobian: np.ndarray,
    residual: np.ndarray,
    root_jacobian: np.ndarray,
    basis: np.ndarray,
    source_nodes: np.ndarray,
    normals: np.ndarray,
    *,
    trust_radius: float,
) -> dict[str, float | int]:
    """Measure the best linear residual reduction with zero root increment."""

    matrix = np.asarray(jacobian, dtype=float)
    vector = np.asarray(residual, dtype=float)
    constraint = np.asarray(root_jacobian, dtype=float)
    shape = np.asarray(basis, dtype=float)
    coordinates = np.asarray(source_nodes, dtype=float)
    normal = np.asarray(normals, dtype=float)
    if (
        matrix.ndim != 2
        or vector.shape != (matrix.shape[0],)
        or constraint.ndim != 2
        or constraint.shape[1] != matrix.shape[1]
        or shape.shape != (len(coordinates), matrix.shape[1])
        or coordinates.ndim != 2
        or coordinates.shape[1] != 2
        or normal.shape != coordinates.shape
        or not all(
            np.isfinite(item).all()
            for item in (matrix, vector, constraint, shape, coordinates, normal)
        )
    ):
        raise ValueError("Reachability arrays have incompatible shapes or values.")
    if not np.isfinite(trust_radius) or trust_radius <= 0.0:
        raise ValueError("trust_radius must be positive and finite.")
    source_objective = float(np.dot(vector, vector))
    if source_objective <= 0.0:
        raise ValueError("Reachability requires a non-zero residual.")

    _, singular_values, right = np.linalg.svd(constraint, full_matrices=True)
    leading = float(singular_values[0]) if len(singular_values) else 0.0
    tolerance = max(constraint.shape) * np.finfo(float).eps * leading
    rank = int(np.count_nonzero(singular_values > tolerance))
    nullspace = right[rank:].T
    if nullspace.shape[1] == 0:
        step = np.zeros(matrix.shape[1], dtype=float)
        reduced_condition = float("inf")
    else:
        reduced = matrix @ nullspace
        coefficients, _, _, _ = np.linalg.lstsq(reduced, -vector, rcond=None)
        step = nullspace @ coefficients
        reduced_condition = float(np.linalg.cond(reduced))

    predicted = vector + matrix @ step
    displacement = shape @ step
    trial_nodes = coordinates + displacement[:, None] * normal
    displacement_ratio = maximum_midpoint_displacement_ratio(
        coordinates, trial_nodes
    )
    trust_scale = min(
        1.0,
        trust_radius / max(displacement_ratio, np.finfo(float).eps),
    )
    trust_step = trust_scale * step
    trust_predicted = vector + matrix @ trust_step
    root_increment = constraint @ step
    return {
        "root_rank": rank,
        "nullspace_dimension": int(nullspace.shape[1]),
        "linear_floor_objective_ratio": float(
            np.dot(predicted, predicted) / source_objective
        ),
        "trust_limited_objective_ratio": float(
            np.dot(trust_predicted, trust_predicted) / source_objective
        ),
        "coefficient_step_norm": float(np.linalg.norm(step)),
        "maximum_displacement_ratio": float(displacement_ratio),
        "trust_scale": float(trust_scale),
        "maximum_absolute_root_increment": float(
            np.max(np.abs(root_increment), initial=0.0)
        ),
        "reduced_jacobian_condition_number": reduced_condition,
    }


def residual_segment_energy_fractions(
    residual: np.ndarray,
    panel_midpoint_fraction: np.ndarray,
    segment_edges: np.ndarray,
) -> np.ndarray:
    """Return exact-vector residual energy fractions over arc-length segments."""

    vector = np.asarray(residual, dtype=float)
    midpoint = np.asarray(panel_midpoint_fraction, dtype=float)
    edges = np.asarray(segment_edges, dtype=float)
    if (
        vector.shape != (2 * len(midpoint),)
        or edges.ndim != 1
        or len(edges) < 2
        or edges[0] != 0.0
        or edges[-1] != 1.0
        or np.any(np.diff(edges) <= 0.0)
        or np.any(midpoint < 0.0)
        or np.any(midpoint > 1.0)
        or not all(np.isfinite(item).all() for item in (vector, midpoint, edges))
    ):
        raise ValueError("Residual segmentation arrays are invalid.")
    panel_energy = np.sum(np.square(vector.reshape(-1, 2)), axis=1)
    total = float(np.sum(panel_energy))
    if total <= 0.0:
        raise ValueError("Residual segmentation requires non-zero energy.")
    fractions = np.empty(len(edges) - 1, dtype=float)
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        mask = (midpoint >= lower) & (
            midpoint <= upper if index == len(fractions) - 1 else midpoint < upper
        )
        fractions[index] = float(np.sum(panel_energy[mask]) / total)
    return fractions


def residual_interval_energy_fraction(
    residual: np.ndarray,
    panel_midpoint_fraction: np.ndarray,
    *,
    lower: float,
    upper: float,
) -> float:
    """Return residual energy in one arc interval independent of report bins."""

    vector = np.asarray(residual, dtype=float)
    midpoint = np.asarray(panel_midpoint_fraction, dtype=float)
    if (
        vector.shape != (2 * len(midpoint),)
        or midpoint.ndim != 1
        or not np.isfinite(vector).all()
        or not np.isfinite(midpoint).all()
        or not np.isfinite(lower)
        or not np.isfinite(upper)
        or lower < 0.0
        or upper > 1.0
        or lower >= upper
        or np.any(midpoint < 0.0)
        or np.any(midpoint > 1.0)
    ):
        raise ValueError("Residual interval arrays or bounds are invalid.")
    panel_energy = np.sum(np.square(vector.reshape(-1, 2)), axis=1)
    total = float(np.sum(panel_energy))
    if total <= 0.0:
        raise ValueError("Residual interval requires non-zero energy.")
    mask = (midpoint >= lower) & (midpoint <= upper)
    return float(np.sum(panel_energy[mask]) / total)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit multigrid residual reachability inside the linearized root "
            "constraint nullspace without using physical reference data."
        )
    )
    parser.add_argument("--trust-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--prefix-mode-counts", type=int, nargs="+", default=(16, 32, 64, 128)
    )
    parser.add_argument("--trust-radius", type=float, default=0.25)
    parser.add_argument("--grid-objective-limit", type=float, default=1.0e-3)
    parser.add_argument(
        "--segment-edges",
        type=float,
        nargs="+",
        default=(0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0),
    )
    return parser


def _pivot(path: Path, index: str, rows: list[int] | None = None) -> np.ndarray:
    frame = pd.read_csv(path)
    table = frame.pivot(index=index, columns="shape_mode", values="value")
    if rows is not None:
        table = table.reindex(index=rows)
    matrix = table.sort_index().sort_index(axis=1).to_numpy(dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError(f"Saved matrix is incomplete: {path}")
    return matrix


def main() -> int:
    args = _parser().parse_args()
    run = args.trust_run.resolve()
    summary = json.loads(
        (run / "multigrid_trust_region_summary.json").read_text(encoding="utf-8")
    )
    if bool(summary.get("reference_used_during_solve", True)):
        raise ValueError("Reference-contaminated trust runs cannot be audited.")
    objective_counts = tuple(int(item) for item in summary["objective_panel_counts"])
    objective_weights = tuple(float(item) for item in summary["objective_panel_weights"])
    constraint_counts = tuple(
        int(item) for item in summary["root_constraint_panel_counts"]
    )
    if len(objective_counts) != len(objective_weights):
        raise ValueError("Objective panel counts and weights do not align.")
    weight_by_grid = dict(zip(objective_counts, objective_weights))
    all_counts = tuple(sorted(set(objective_counts) | set(constraint_counts)))

    source = load_coupled_self_similar_checkpoint(Path(summary["source_checkpoint"]))
    rebuilt = _rebuild_grids(
        source,
        source.coupled,
        all_counts,
        outer_shape_dipole_coefficient=source.outer_shape_dipole_coefficient,
        root_inner_iterations=int(summary.get("root_inner_iterations", 0)),
    )
    residual_by_grid: dict[int, np.ndarray] = {}
    state_by_grid: dict[int, object] = {}
    for count, coupled in rebuilt.items():
        residual_by_grid[count], state_by_grid[count] = _grid_residual_and_state(
            coupled
        )
    source_objective = {
        count: float(state_by_grid[count].exact_objective)
        for count in objective_counts
    }
    residual = normalized_multigrid_residual(
        {count: residual_by_grid[count] for count in objective_counts},
        source_objective,
        weight_by_grid,
    )
    jacobian = _pivot(
        run / "multigrid_trust_region_jacobians.csv", "residual_row"
    )
    root_jacobian = _pivot(
        run / "multigrid_trust_region_root_jacobians.csv",
        "panel_count",
        list(constraint_counts),
    )
    if jacobian.shape[0] != len(residual) or jacobian.shape[1] != root_jacobian.shape[1]:
        raise ValueError("Saved Jacobian dimensions do not match the frozen source.")

    prefixes = tuple(sorted(set(int(item) for item in args.prefix_mode_counts)))
    if not prefixes or prefixes[0] < 1 or prefixes[-1] > jacobian.shape[1]:
        raise ValueError("Mode prefixes must fit the saved Jacobian.")
    source_nodes = np.column_stack(
        (
            source.coupled.outer_free_surface.node_xi,
            source.coupled.outer_free_surface.node_eta,
        )
    )
    normals = angle_bisector_normals(source_nodes)
    source_labels = np.asarray(source.coupled.boundary.panel_labels, dtype=object)
    source_panel_length = source.coupled.boundary.panel_length_m[
        source_labels == "outer_free_surface"
    ]
    full_basis = multigrid_shape_basis(
        source_panel_length,
        jacobian.shape[1],
        basis=str(summary.get("basis", "dct")),
        global_mode_count=int(summary.get("global_mode_count", 2)),
        local_support_fraction=float(summary.get("local_support_fraction", 0.15)),
    )
    prefix_rows: list[dict[str, float | int]] = []
    for count in prefixes:
        metrics = root_constrained_linear_reachability(
            jacobian[:, :count],
            residual,
            root_jacobian[:, :count],
            full_basis[:, :count],
            source_nodes,
            normals,
            trust_radius=args.trust_radius,
        )
        prefix_rows.append({"mode_count": count, **metrics})

    edges = np.asarray(args.segment_edges, dtype=float)
    segment_rows: list[dict[str, float | int]] = []
    far_energy_by_grid: list[float] = []
    for count in objective_counts:
        coupled = rebuilt[count]
        labels = np.asarray(coupled.boundary.panel_labels, dtype=object)
        length = coupled.boundary.panel_length_m[labels == "outer_free_surface"]
        arc = np.concatenate(([0.0], np.cumsum(length)))
        midpoint = 0.5 * (arc[:-1] + arc[1:]) / arc[-1]
        fractions = residual_segment_energy_fractions(
            residual_by_grid[count], midpoint, edges
        )
        far_energy_by_grid.append(
            residual_interval_energy_fraction(
                residual_by_grid[count], midpoint, lower=0.90, upper=1.0
            )
        )
        for lower, upper, fraction in zip(edges[:-1], edges[1:], fractions):
            segment_rows.append(
                {
                    "panel_count": count,
                    "arc_fraction_lower": float(lower),
                    "arc_fraction_upper": float(upper),
                    "residual_energy_fraction": float(fraction),
                }
            )

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prefix_rows).to_csv(
        output / "feasible_subspace_prefix.csv", index=False
    )
    pd.DataFrame(segment_rows).to_csv(
        output / "residual_segment_energy.csv", index=False
    )
    final_prefix = prefix_rows[-1]
    far_energy = max(far_energy_by_grid)
    required_reduction = max(
        1.0 - args.grid_objective_limit / source_objective[count]
        for count in objective_counts
    )
    reachable_reduction = 1.0 - float(
        final_prefix["trust_limited_objective_ratio"]
    )
    change_basis = bool(
        required_reduction > 0.10
        and reachable_reduction < 0.02
        and far_energy > 0.50
    )
    result = {
        "status": "reference_isolated_feasible_subspace_diagnostic",
        "validated": False,
        "production_enabled": False,
        "reference_used_during_solve": False,
        "trust_run": str(run),
        "source_checkpoint": str(Path(summary["source_checkpoint"]).resolve()),
        "basis": str(summary.get("basis", "dct")),
        "global_mode_count": int(summary.get("global_mode_count", 2)),
        "local_support_fraction": float(
            summary.get("local_support_fraction", 0.15)
        ),
        "objective_panel_counts": list(objective_counts),
        "root_constraint_panel_counts": list(constraint_counts),
        "mode_prefixes": list(prefixes),
        "grid_objective_limit": args.grid_objective_limit,
        "maximum_required_grid_relative_reduction": float(required_reduction),
        "finest_prefix_reachable_relative_reduction": float(reachable_reduction),
        "maximum_far_endpoint_energy_fraction": float(far_energy),
        "recommendation": (
            "change_to_endpoint_local_basis_before_more_global_dct_modes"
            if change_basis
            else "global_dct_extension_not_ruled_out"
        ),
        "interpretation": (
            "This is a linearized numerical-space diagnostic only; it does not "
            "provide wedge physical-validation or Gate 2 credit."
        ),
    }
    (output / "feasible_subspace_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
