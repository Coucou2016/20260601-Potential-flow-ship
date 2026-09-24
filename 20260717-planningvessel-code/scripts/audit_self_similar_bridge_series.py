from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    derive_shallow_water_jet_root_state_from_coupled,
)


@dataclass(frozen=True)
class BridgePoint:
    run: str
    deadrise_deg: float
    formal_exact_objective: float
    root_relative_mismatch: float
    condition_number: float
    dipole_coefficient: float
    root_thickness: float
    interface_s_lambda: float
    measured_s_lambda: float
    root_xi: float
    reconstruction_relative_error: float
    reference_used_during_solve: bool
    summary_file: str
    checkpoint_sha256: str
    outer_nodes_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summary(run: Path) -> tuple[Path, dict[str, object]]:
    candidates = sorted(run.glob("*_summary.json"))
    candidates = [path for path in candidates if path.name != "bridge_series_audit.json"]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one run summary in {run}, found {len(candidates)}.")
    path = candidates[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


def load_bridge_point(run: Path) -> BridgePoint:
    run = run.resolve()
    checkpoint = load_coupled_self_similar_checkpoint(run)
    checkpoint_json_path = run / "coupled_checkpoint.json"
    checkpoint_json = json.loads(checkpoint_json_path.read_text(encoding="utf-8"))
    expected = checkpoint_json["expected_state"]
    summary_path, summary = _summary(run)
    coupled = checkpoint.coupled
    root = coupled.jet_interface.root_state
    measured = derive_shallow_water_jet_root_state_from_coupled(coupled)
    root_mismatch = abs(measured.s_lambda - root.s_lambda) / max(
        abs(root.s_lambda), np.finfo(float).eps
    )
    point = BridgePoint(
        run=str(run),
        deadrise_deg=float(checkpoint.config.deadrise_deg),
        formal_exact_objective=float(coupled.kinematic_convergence_integral),
        root_relative_mismatch=float(root_mismatch),
        condition_number=float(coupled.solution.condition_number),
        dipole_coefficient=float(coupled.dipole_coefficient),
        root_thickness=float(root.thickness),
        interface_s_lambda=float(root.s_lambda),
        measured_s_lambda=float(measured.s_lambda),
        root_xi=float(expected["root_xi"]),
        reconstruction_relative_error=float(
            max(checkpoint.reconstruction_relative_errors.values())
        ),
        reference_used_during_solve=bool(
            summary.get("reference_used_during_solve", True)
        ),
        summary_file=summary_path.name,
        checkpoint_sha256=_sha256(checkpoint_json_path),
        outer_nodes_sha256=_sha256(run / "coupled_checkpoint_outer_nodes.csv"),
    )
    scalars = np.asarray(
        [
            point.deadrise_deg,
            point.formal_exact_objective,
            point.root_relative_mismatch,
            point.condition_number,
            point.dipole_coefficient,
            point.root_thickness,
            point.interface_s_lambda,
            point.measured_s_lambda,
            point.root_xi,
            point.reconstruction_relative_error,
        ],
        dtype=float,
    )
    if not np.isfinite(scalars).all():
        raise ValueError(f"Non-finite bridge state in {run}.")
    return point


def continuity_metrics(previous: BridgePoint, current: BridgePoint) -> dict[str, float]:
    def relative(current_value: float, previous_value: float) -> float:
        return abs(current_value - previous_value) / max(
            abs(previous_value), np.finfo(float).eps
        )

    return {
        "deadrise_step_deg": abs(current.deadrise_deg - previous.deadrise_deg),
        "root_thickness_relative_change": relative(
            current.root_thickness, previous.root_thickness
        ),
        "interface_s_lambda_relative_change": relative(
            current.interface_s_lambda, previous.interface_s_lambda
        ),
        "dipole_relative_change": relative(
            current.dipole_coefficient, previous.dipole_coefficient
        ),
        "root_xi_relative_change": relative(current.root_xi, previous.root_xi),
        "condition_number_ratio": current.condition_number
        / max(previous.condition_number, np.finfo(float).eps),
    }


def within_rounded_upper_limit(value: float, limit: float) -> bool:
    """Compare a derived float with an inclusive limit up to roundoff only."""

    tolerance = 16.0 * np.finfo(float).eps * max(
        1.0,
        abs(float(value)),
        abs(float(limit)),
    )
    return float(value) <= float(limit) + tolerance


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a reference-isolated sequence of formal 320-panel wedge checkpoints."
    )
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--objective-limit", type=float, default=1.0e-3)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--maximum-deadrise-step-deg", type=float, default=0.25)
    parser.add_argument("--continuity-relative-limit", type=float, default=0.05)
    parser.add_argument("--condition-number-ratio-limit", type=float, default=1.10)
    parser.add_argument("--reconstruction-relative-limit", type=float, default=1.0e-12)
    args = parser.parse_args()

    points = [load_bridge_point(path) for path in args.runs]
    transitions = [
        {
            "from_deadrise_deg": previous.deadrise_deg,
            "to_deadrise_deg": current.deadrise_deg,
            **continuity_metrics(previous, current),
        }
        for previous, current in zip(points, points[1:])
    ]
    point_pass = [
        point.formal_exact_objective <= args.objective_limit
        and point.root_relative_mismatch <= args.root_mismatch_limit
        and point.reconstruction_relative_error <= args.reconstruction_relative_limit
        and point.root_thickness > 0.0
        and point.interface_s_lambda > 0.0
        and point.measured_s_lambda > 0.0
        and not point.reference_used_during_solve
        for point in points
    ]
    transition_pass = [
        within_rounded_upper_limit(
            transition["deadrise_step_deg"],
            args.maximum_deadrise_step_deg,
        )
        and max(
            transition["root_thickness_relative_change"],
            transition["interface_s_lambda_relative_change"],
            transition["dipole_relative_change"],
            transition["root_xi_relative_change"],
        )
        <= args.continuity_relative_limit
        and transition["condition_number_ratio"] <= args.condition_number_ratio_limit
        for transition in transitions
    ]
    passed = all(point_pass) and all(transition_pass)

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "bridge_series_points.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        rows = [asdict(point) | {"point_pass": passed_point} for point, passed_point in zip(points, point_pass)]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output / "bridge_series_transitions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        rows = [row | {"transition_pass": passed_transition} for row, passed_transition in zip(transitions, transition_pass)]
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    report = {
        "status": "PASS" if passed else "FAIL",
        "gate": "reference_isolated_self_similar_320_panel_bridge_series",
        "reference_used_during_solve": any(
            point.reference_used_during_solve for point in points
        ),
        "limits": {
            "objective": args.objective_limit,
            "root_mismatch": args.root_mismatch_limit,
            "maximum_deadrise_step_deg": args.maximum_deadrise_step_deg,
            "continuity_relative": args.continuity_relative_limit,
            "condition_number_ratio": args.condition_number_ratio_limit,
            "reconstruction_relative": args.reconstruction_relative_limit,
        },
        "point_pass": point_pass,
        "transition_pass": transition_pass,
        "points": [asdict(point) for point in points],
        "transitions": transitions,
    }
    (output / "bridge_series_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "out": str(output)}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
