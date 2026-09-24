from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify long-time coupled wedge residual envelopes."
    )
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kinematic-tolerance", type=float, default=1.0e-3)
    parser.add_argument("--minimum-cycles", type=int, default=5)
    return parser


def analyze_long_time_convergence(
    history: pd.DataFrame,
    *,
    kinematic_tolerance: float = 1.0e-3,
    minimum_cycles: int = 5,
) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {
        "iteration",
        "pseudo_time",
        "kinematic_rms",
        "root_resolution_ratio",
        "bem_condition_number",
    }
    missing = sorted(required - set(history.columns))
    if missing:
        raise ValueError(f"Long-time history is missing columns: {missing}.")
    frame = history.copy()
    for name in required:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    metric_name = "kinematic_rms"
    metric_source = "legacy equal-panel scaled RMS"
    for candidate, source in (
        (
            "kinematic_convergence_integral",
            "discretization-consistent Iafrati Eq. (52) integral",
        ),
        ("kinematic_integral", "midpoint Iafrati Eq. (52) integral"),
    ):
        if candidate not in frame.columns:
            continue
        values = pd.to_numeric(frame[candidate], errors="coerce")
        if int(np.isfinite(values).sum()) >= 3:
            frame[candidate] = values
            frame = frame[np.isfinite(values)].copy()
            metric_name = candidate
            metric_source = source
            break
    if len(frame) < 3:
        raise ValueError("Long-time classification requires at least three states.")
    condition = frame["bem_condition_number"].to_numpy(dtype=float)
    resolution = frame["root_resolution_ratio"].to_numpy(dtype=float)
    condition_ratio = condition[1:] / condition[:-1]
    resolution_change = np.abs(resolution[1:] - resolution[:-1]) / np.maximum(
        np.abs(resolution[:-1]), np.finfo(float).eps
    )
    event = (condition_ratio < 0.75) | (condition_ratio > 1.5) | (
        resolution_change > 0.15
    )
    for topology_column in (
        "shallow_jet_panel_count_per_side",
        "boundary_panel_count",
        "jet_point_count",
    ):
        if topology_column not in frame.columns:
            continue
        topology = pd.to_numeric(frame[topology_column], errors="coerce").to_numpy()
        valid_pair = np.isfinite(topology[1:]) & np.isfinite(topology[:-1])
        event |= valid_pair & (topology[1:] != topology[:-1])
    cycle_id = np.concatenate(([0], np.cumsum(event, dtype=int)))
    frame["cycle_id"] = cycle_id
    cycle_rows = []
    for identifier, cycle in frame.groupby("cycle_id", sort=True):
        residual = cycle[metric_name].to_numpy(dtype=float)
        minimum_index = int(np.argmin(residual))
        minimum_row = cycle.iloc[minimum_index]
        cycle_rows.append(
            {
                "cycle_id": int(identifier),
                "start_iteration": int(cycle.iloc[0]["iteration"]),
                "end_iteration": int(cycle.iloc[-1]["iteration"]),
                "state_count": len(cycle),
                "minimum_iteration": int(minimum_row["iteration"]),
                "minimum_pseudo_time": float(minimum_row["pseudo_time"]),
                "minimum_metric": float(minimum_row[metric_name]),
                "final_metric": float(cycle.iloc[-1][metric_name]),
            }
        )
    cycles = pd.DataFrame(cycle_rows)
    complete_cycles = cycles[cycles["state_count"] >= 2]
    recent = complete_cycles.tail(max(int(minimum_cycles), 8))
    final_residual = float(frame.iloc[-1][metric_name])
    converged = final_residual <= float(kinematic_tolerance)
    normalized_slope = np.nan
    relative_range = np.nan
    if len(recent) >= 2:
        time = recent["minimum_pseudo_time"].to_numpy(dtype=float)
        minima = recent["minimum_metric"].to_numpy(dtype=float)
        slope = float(np.polyfit(time, minima, 1)[0])
        span = max(float(time[-1] - time[0]), np.finfo(float).eps)
        scale = max(float(np.mean(minima)), np.finfo(float).eps)
        normalized_slope = slope * span / scale
        relative_range = float((np.max(minima) - np.min(minima)) / scale)
    enough_cycles = len(complete_cycles) >= int(minimum_cycles)
    descending = enough_cycles and normalized_slope < -0.02
    limit_cycle = (
        enough_cycles
        and abs(normalized_slope) <= 0.01
        and relative_range <= 0.03
        and not converged
    )
    if converged:
        classification = "KINEMATIC_CONVERGED"
    elif descending:
        classification = "DESCENDING_NOT_CONVERGED"
    elif limit_cycle:
        classification = "LIMIT_CYCLE_NOT_CONVERGED"
    else:
        classification = "INSUFFICIENT_OR_NONMONOTONE"
    report = {
        "classification": classification,
        "physical_validation_status": "FAIL",
        "metric_name": metric_name,
        "metric_source": metric_source,
        "kinematic_tolerance": float(kinematic_tolerance),
        "final_kinematic_metric": final_residual,
        "minimum_kinematic_metric": float(frame[metric_name].min()),
        "detected_topology_events": int(np.count_nonzero(event)),
        "complete_cycle_count": len(complete_cycles),
        "recent_cycle_normalized_slope": float(normalized_slope),
        "recent_cycle_relative_range": float(relative_range),
        "interpretation": (
            "Only KINEMATIC_CONVERGED satisfies the residual prerequisite. "
            "DESCENDING_NOT_CONVERGED authorizes checkpoint continuation; a "
            "limit cycle requires event-model diagnosis rather than more steps."
        ),
    }
    return cycles, report


def _plot(
    output: Path,
    history: pd.DataFrame,
    cycles: pd.DataFrame,
    metric_name: str,
) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    metric = pd.to_numeric(history[metric_name], errors="coerce")
    finite = np.isfinite(metric)
    axis.semilogy(history.loc[finite, "pseudo_time"], metric[finite], label="state")
    axis.semilogy(
        cycles["minimum_pseudo_time"],
        cycles["minimum_metric"],
        "o-",
        label="cycle minima",
    )
    axis.set(xlabel="Pseudo-time", ylabel=metric_name.replace("_", " "))
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    figure.savefig(output / "long_time_residual_envelope.png", dpi=180)
    plt.close(figure)


def main() -> int:
    args = _parser().parse_args()
    source = args.run.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    history = pd.read_csv(source / "coupled_pseudo_time_history.csv")
    cycles, report = analyze_long_time_convergence(
        history,
        kinematic_tolerance=args.kinematic_tolerance,
        minimum_cycles=args.minimum_cycles,
    )
    cycles.to_csv(output / "residual_cycles.csv", index=False)
    (output / "long_time_convergence.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    _plot(output, history, cycles, str(report["metric_name"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
