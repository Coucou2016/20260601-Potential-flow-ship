from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planing_seakeeping.kernels.nonlinear_2dt.self_similar_checkpoint import (
    load_coupled_self_similar_checkpoint,
)
from planing_seakeeping.kernels.nonlinear_2dt.self_similar_wedge import (
    _constrain_coupled_outer_nodes,
    _coupled_outer_pseudo_velocity,
    _reconstruct_coupled_root_nodes,
    _relocate_underresolved_coupled_jet_interface,
    _resample_coupled_outer_nodes,
    _smooth_oscillatory_coupled_outer_nodes,
    _trim_shallow_angle_coupled_root_panels,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit every first-stage regrid operation after an RK update."
    )
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=14)
    return parser


def main() -> int:
    args = _parser().parse_args()
    checkpoint = load_coupled_self_similar_checkpoint(args.checkpoint.resolve())
    coupled = checkpoint.coupled
    config = coupled.config
    old = np.column_stack(
        (
            coupled.outer_free_surface.node_xi,
            coupled.outer_free_surface.node_eta,
        )
    )
    velocity = _coupled_outer_pseudo_velocity(coupled)
    panel_length = np.diff(coupled.outer_free_surface.arc_length)
    panel_speed = 0.5 * (
        np.linalg.norm(velocity[:-1], axis=1)
        + np.linalg.norm(velocity[1:], axis=1)
    )
    initial_step = float(config.pseudo_cfl) * float(
        np.min(panel_length / np.maximum(panel_speed, np.finfo(float).eps))
    )
    beta = np.deg2rad(config.deadrise_deg)
    body_tangent = np.asarray([np.cos(beta), np.sin(beta)])

    def metrics(nodes: np.ndarray) -> dict[str, object]:
        segment = np.diff(nodes, axis=0)
        projection = segment @ body_tangent
        return {
            "node_count": len(nodes),
            "root_xi": float(nodes[0, 0]),
            "root_eta": float(nodes[0, 1]),
            "first_panel_length": float(np.linalg.norm(segment[0])),
            "first_body_tangent_projection": float(projection[0]),
            "minimum_body_tangent_projection": float(np.min(projection)),
        }

    rows: list[dict[str, object]] = []
    for attempt in range(int(args.attempts)):
        time_step = initial_step * 0.5**attempt
        row: dict[str, object] = {
            "attempt": attempt,
            "time_step": time_step,
        }
        stage = "raw"
        try:
            nodes = _constrain_coupled_outer_nodes(
                config,
                old + time_step * velocity,
                allow_reversed_root=True,
            )
            row[stage] = metrics(nodes)
            stage = "angle_trim"
            nodes = _trim_shallow_angle_coupled_root_panels(config, nodes)
            row[stage] = metrics(nodes)
            stage = "smoothing"
            nodes = _smooth_oscillatory_coupled_outer_nodes(config, nodes)
            row[stage] = metrics(nodes)
            stage = "resample"
            nodes = _resample_coupled_outer_nodes(config, nodes)
            row[stage] = metrics(nodes)
            stage = "root_reconstruction"
            nodes = _reconstruct_coupled_root_nodes(config, nodes)
            row[stage] = metrics(nodes)
            stage = "resolution_relocation"
            nodes = _relocate_underresolved_coupled_jet_interface(config, nodes)
            row[stage] = metrics(nodes)
            row["status"] = "PASS"
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
            row["status"] = "FAIL"
            row["failed_stage"] = stage
            row["reason"] = str(error)
        rows.append(row)

    result = {
        "status": "rk2_first_stage_regrid_diagnostic",
        "source_checkpoint": str(args.checkpoint.resolve()),
        "initial_time_step": initial_step,
        "old_geometry": metrics(old),
        "rows": rows,
    }
    output = args.out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
