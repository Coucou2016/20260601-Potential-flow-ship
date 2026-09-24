from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scaled_error(
    left: np.ndarray,
    right: np.ndarray,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> tuple[float, float]:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    if a.shape != b.shape:
        return float("inf"), float("inf")
    common_nan = np.isnan(a) & np.isnan(b)
    if np.any(np.isnan(a) ^ np.isnan(b)):
        return float("inf"), float("inf")
    a = a[~common_nan]
    b = b[~common_nan]
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        return float("inf"), float("inf")
    difference = np.abs(a - b)
    scale = absolute_tolerance + relative_tolerance * np.maximum(np.abs(a), np.abs(b))
    return (
        float(np.max(difference, initial=0.0)),
        float(np.max(difference / scale, initial=0.0)),
    )


def compare_checkpoint_outputs(
    direct_directory: str | Path,
    chained_directory: str | Path,
    *,
    absolute_tolerance: float = 1.0e-9,
    relative_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    direct = Path(direct_directory).resolve()
    chained = Path(chained_directory).resolve()
    history_name = "coupled_pseudo_time_history.csv"
    outer_name = "coupled_checkpoint_outer_nodes.csv"
    summary_name = "resume_summary.json"
    checkpoint_name = "coupled_checkpoint.json"
    for directory in (direct, chained):
        for name in (history_name, outer_name, summary_name, checkpoint_name):
            if not (directory / name).exists():
                raise ValueError(f"Missing checkpoint comparison file: {directory / name}")

    direct_history = pd.read_csv(direct / history_name)
    chained_history = pd.read_csv(chained / history_name)
    if list(direct_history.columns) != list(chained_history.columns):
        raise ValueError("Checkpoint history columns differ.")
    history_results: dict[str, dict[str, float | bool]] = {}
    for name in direct_history.columns:
        absolute, scaled = _scaled_error(
            direct_history[name].to_numpy(dtype=float),
            chained_history[name].to_numpy(dtype=float),
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        )
        history_results[name] = {
            "maximum_absolute_difference": absolute,
            "maximum_scaled_error": scaled,
            "passed": scaled <= 1.0,
        }

    direct_outer = pd.read_csv(direct / outer_name).loc[:, ["xi", "eta"]].to_numpy()
    chained_outer = pd.read_csv(chained / outer_name).loc[:, ["xi", "eta"]].to_numpy()
    outer_absolute, outer_scaled = _scaled_error(
        direct_outer,
        chained_outer,
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )

    direct_summary = json.loads((direct / summary_name).read_text(encoding="utf-8"))
    chained_summary = json.loads((chained / summary_name).read_text(encoding="utf-8"))
    direct_state = direct_summary["final_state"]
    chained_state = chained_summary["final_state"]
    if set(direct_state) != set(chained_state):
        raise ValueError("Checkpoint final-state fields differ.")
    state_results: dict[str, dict[str, float | bool]] = {}
    for name in direct_state:
        absolute, scaled = _scaled_error(
            np.asarray([direct_state[name]], dtype=float),
            np.asarray([chained_state[name]], dtype=float),
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        )
        state_results[name] = {
            "absolute_difference": absolute,
            "scaled_error": scaled,
            "passed": scaled <= 1.0,
        }
    direct_iteration = int(direct_summary["continuation"]["completed_iterations"])
    chained_iteration = int(chained_summary["continuation"]["completed_iterations"])
    completed_iteration_match = direct_iteration == chained_iteration
    passed = (
        completed_iteration_match
        and outer_scaled <= 1.0
        and all(bool(item["passed"]) for item in history_results.values())
        and all(bool(item["passed"]) for item in state_results.values())
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "direct_directory": str(direct),
        "chained_directory": str(chained),
        "absolute_tolerance": absolute_tolerance,
        "relative_tolerance": relative_tolerance,
        "completed_iteration": {
            "direct": direct_iteration,
            "chained": chained_iteration,
            "passed": completed_iteration_match,
        },
        "outer_nodes": {
            "maximum_absolute_difference": outer_absolute,
            "maximum_scaled_error": outer_scaled,
            "passed": outer_scaled <= 1.0,
        },
        "history": history_results,
        "final_state": state_results,
        "checkpoint_sha256": {
            "direct": _sha256(direct / checkpoint_name),
            "chained": _sha256(chained / checkpoint_name),
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify direct and chained self-similar checkpoint continuation."
    )
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--chained", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--absolute-tolerance", type=float, default=1.0e-9)
    parser.add_argument("--relative-tolerance", type=float, default=1.0e-9)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.absolute_tolerance <= 0.0 or args.relative_tolerance <= 0.0:
        raise ValueError("Checkpoint comparison tolerances must be positive.")
    result = compare_checkpoint_outputs(
        args.direct,
        args.chained,
        absolute_tolerance=args.absolute_tolerance,
        relative_tolerance=args.relative_tolerance,
    )
    output = args.out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
