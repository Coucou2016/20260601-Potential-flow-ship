from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from scripts.diagnose_self_similar_newton_krylov import formal_outer_state


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_change(coarse: float, fine: float) -> float:
    return abs(fine - coarse) / max(abs(fine), 1.0e-12)


def _deadrise_scope_token(deadrise_deg: float) -> str:
    return f"{deadrise_deg:g}".replace("-", "m").replace(".", "p")


def evaluate_numerical_gate(
    levels: list[dict[str, Any]],
    *,
    expected_panels: tuple[int, ...] = (320, 640, 1280),
    expected_deadrise_deg: float = 12.75,
    deadrise_tolerance: float = 1.0e-12,
    objective_limit: float = 1.0e-3,
    root_mismatch_limit: float = 1.0e-3,
    variation_limit: float = 0.05,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(levels, key=lambda item: int(item["outer_panel_count"]))
    actual_panels = tuple(int(item["outer_panel_count"]) for item in ordered)
    if actual_panels != expected_panels:
        raise ValueError(
            f"Expected panel sequence {expected_panels}, received {actual_panels}."
        )
    pair_rows: list[dict[str, Any]] = []
    for coarse, fine in zip(ordered[:-1], ordered[1:]):
        pair_rows.append(
            {
                "coarse_panel_count": int(coarse["outer_panel_count"]),
                "fine_panel_count": int(fine["outer_panel_count"]),
                "kinematic_integral_relative_change": _relative_change(
                    float(coarse["kinematic_integral_linear_exact"]),
                    float(fine["kinematic_integral_linear_exact"]),
                ),
                "vertical_force_relative_change": _relative_change(
                    float(coarse["body_vertical_force_coefficient"]),
                    float(fine["body_vertical_force_coefficient"]),
                ),
            }
        )
    finite_pass = all(
        bool(item["finite"])
        and np.isfinite(float(item["kinematic_integral_linear_exact"]))
        and np.isfinite(float(item["root_relative_mismatch"]))
        and np.isfinite(float(item["body_vertical_force_coefficient"]))
        for item in ordered
    )
    absolute_gate_pass = all(
        float(item["kinematic_integral_linear_exact"]) <= objective_limit
        and float(item["root_relative_mismatch"]) <= root_mismatch_limit
        for item in ordered
    )
    finest = pair_rows[-1]
    finest_pair_pass = (
        finest["kinematic_integral_relative_change"] <= variation_limit
        and finest["vertical_force_relative_change"] <= variation_limit
    )
    reference_isolation_pass = all(
        item.get("reference_used_during_solve") is False for item in ordered
    )
    deadrise_consistency_pass = all(
        np.isfinite(float(item["deadrise_deg"]))
        and abs(float(item["deadrise_deg"]) - expected_deadrise_deg)
        <= deadrise_tolerance
        for item in ordered
    )
    status = (
        "PASS"
        if finite_pass
        and absolute_gate_pass
        and finest_pair_pass
        and reference_isolation_pass
        and deadrise_consistency_pass
        else "FAIL"
    )
    deadrise_label = f"{expected_deadrise_deg:g}"
    report = {
        "status": status,
        "scope": (
            f"{_deadrise_scope_token(expected_deadrise_deg)}deg_"
            "three_grid_numerical_gate_only"
        ),
        "physical_validation_status": "NOT_EVALUATED",
        "metric": "Iafrati 2013 Eq. (52), exact piecewise-linear K",
        "integration_formula": "sum(ds*(r_left^2+r_left*r_right+r_right^2)/3)",
        "relative_change_formula": "abs(fine-coarse)/max(abs(fine),1e-12)",
        "expected_panel_sequence": list(expected_panels),
        "expected_deadrise_deg": expected_deadrise_deg,
        "deadrise_tolerance": deadrise_tolerance,
        "objective_limit": objective_limit,
        "root_mismatch_limit": root_mismatch_limit,
        "variation_limit": variation_limit,
        "checkpoint_verification_tolerance": 1.0e-12,
        "finite_pass": finite_pass,
        "absolute_gate_pass": absolute_gate_pass,
        "finest_pair_pass": finest_pair_pass,
        "reference_isolation_pass": reference_isolation_pass,
        "deadrise_consistency_pass": deadrise_consistency_pass,
        "finest_pair": finest,
        "interpretation": (
            f"PASS closes only the declared {deadrise_label}-degree three-grid numerical "
            "gate. It does not prove wedge pressure or whole-vessel validation."
        ),
    }
    return pair_rows, report


def _load_level(directory: Path) -> dict[str, Any]:
    source = directory.resolve()
    checkpoint_path = source / "coupled_checkpoint.json"
    metadata = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    coupled = load_coupled_self_similar_checkpoint(
        source, verification_tolerance=1.0e-12
    ).coupled
    formal = formal_outer_state(coupled)
    values = np.asarray(
        [
            formal.exact_objective,
            formal.root_relative_mismatch,
            formal.condition_number,
            coupled.body_vertical_force_coefficient,
            coupled.dipole_coefficient,
        ],
        dtype=float,
    )
    return {
        "run": source.name,
        "path": str(source),
        "deadrise_deg": float(metadata["config"]["deadrise_deg"]),
        "outer_panel_count": int(metadata["config"]["free_surface_panels"]),
        "kinematic_integral_linear_exact": formal.exact_objective,
        "root_relative_mismatch": formal.root_relative_mismatch,
        "body_vertical_force_coefficient": float(
            coupled.body_vertical_force_coefficient
        ),
        "solved_dipole_coefficient": float(coupled.dipole_coefficient),
        "bem_condition_number": formal.condition_number,
        "finite": bool(np.isfinite(values).all()),
        "reference_used_during_solve": metadata.get(
            "reference_used_during_solve"
        ),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "outer_nodes_sha256": _sha256(
            source / metadata["files"]["outer_nodes"]["name"]
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a declared-deadrise 320/640/1280 self-similar wedge "
            "numerical gate from arbitrary formal checkpoints."
        )
    )
    parser.add_argument("--runs", type=Path, nargs=3, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--deadrise-deg", type=float, default=12.75)
    parser.add_argument("--objective-limit", type=float, default=1.0e-3)
    parser.add_argument("--root-mismatch-limit", type=float, default=1.0e-3)
    parser.add_argument("--variation-limit", type=float, default=0.05)
    return parser


def main() -> int:
    args = _parser().parse_args()
    levels = [_load_level(path) for path in args.runs]
    pairs, report = evaluate_numerical_gate(
        levels,
        expected_deadrise_deg=args.deadrise_deg,
        objective_limit=args.objective_limit,
        root_mismatch_limit=args.root_mismatch_limit,
        variation_limit=args.variation_limit,
    )
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sorted(levels, key=lambda item: item["outer_panel_count"])).to_csv(
        output / "numerical_gate_levels.csv", index=False
    )
    pd.DataFrame(pairs).to_csv(output / "numerical_gate_pairs.csv", index=False)
    (output / "numerical_gate.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
