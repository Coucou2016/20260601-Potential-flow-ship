from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REQUIRED_COLUMNS = {
    "iteration",
    "pseudo_time",
    "kinematic_rms",
    "root_thickness",
    "root_resolution_ratio",
    "bem_condition_number",
}


def detect_matching_surface_resets(
    history: pd.DataFrame,
    *,
    minimum_relative_jump: float = 0.05,
) -> np.ndarray:
    missing = sorted(REQUIRED_COLUMNS - set(history.columns))
    if missing:
        raise ValueError(f"Matching-cycle history is missing columns: {missing}.")
    if not 0.0 < minimum_relative_jump < 1.0:
        raise ValueError("minimum_relative_jump must lie between zero and one.")
    thickness = pd.to_numeric(history["root_thickness"], errors="raise").to_numpy(
        dtype=float
    )
    resolution = pd.to_numeric(
        history["root_resolution_ratio"], errors="raise"
    ).to_numpy(dtype=float)
    if len(thickness) < 2 or np.any(thickness <= 0.0) or np.any(resolution <= 0.0):
        raise ValueError("Matching-cycle state must contain positive root scales.")
    threshold = 1.0 + float(minimum_relative_jump)
    reset = (thickness[1:] / thickness[:-1] >= threshold) & (
        resolution[1:] / resolution[:-1] >= threshold
    )
    return np.flatnonzero(reset) + 1


def _mode_positive(values: np.ndarray) -> int:
    positive = np.asarray(values, dtype=int)
    positive = positive[positive > 0]
    if positive.size == 0:
        raise ValueError("At least two reset events are required to infer a period.")
    counts = np.bincount(positive)
    return int(np.flatnonzero(counts == counts.max())[0])


def _log_trend(time: np.ndarray, values: np.ndarray) -> dict[str, float]:
    if len(values) < 2 or np.any(values <= 0.0):
        return {
            "exponential_rate_per_pseudo_time": float("nan"),
            "log_linear_r_squared": float("nan"),
            "relative_change_over_window": float("nan"),
        }
    slope, intercept = np.polyfit(time, np.log(values), 1)
    fitted = intercept + slope * time
    centered = np.log(values) - float(np.mean(np.log(values)))
    denominator = float(np.sum(np.square(centered)))
    r_squared = (
        1.0 - float(np.sum(np.square(np.log(values) - fitted))) / denominator
        if denominator > np.finfo(float).eps
        else 1.0
    )
    span = float(time[-1] - time[0])
    return {
        "exponential_rate_per_pseudo_time": float(slope),
        "log_linear_r_squared": r_squared,
        "relative_change_over_window": float(np.exp(slope * span) - 1.0),
    }


def analyze_matching_surface_cycles(
    history: pd.DataFrame,
    *,
    minimum_relative_jump: float = 0.05,
    recent_cycle_count: int = 40,
    kinematic_tolerance: float = 1.0e-3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    if recent_cycle_count < 8:
        raise ValueError("recent_cycle_count must be at least eight.")
    frame = history.copy()
    for name in REQUIRED_COLUMNS:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    resets = detect_matching_surface_resets(
        frame, minimum_relative_jump=minimum_relative_jump
    )
    if len(resets) < 3:
        raise ValueError("At least three matching-surface resets are required.")
    modal_period = _mode_positive(np.diff(resets))
    metric_name = "kinematic_rms"
    metric_source = "legacy equal-panel scaled RMS"
    if "kinematic_convergence_integral" in frame.columns:
        convergence_integral = pd.to_numeric(
            frame["kinematic_convergence_integral"],
            errors="coerce",
        )
        if int(np.isfinite(convergence_integral).sum()) >= 2 * modal_period:
            frame["kinematic_convergence_integral"] = convergence_integral
            metric_name = "kinematic_convergence_integral"
            metric_source = (
                "discretization-consistent Iafrati 2013 Eq. (52) integral"
            )
    if metric_name == "kinematic_rms" and "kinematic_integral" in frame.columns:
        integral = pd.to_numeric(frame["kinematic_integral"], errors="coerce")
        if int(np.isfinite(integral).sum()) >= 2 * modal_period:
            frame["kinematic_integral"] = integral
            metric_name = "kinematic_integral"
            metric_source = "Iafrati 2013 Eq. (52), K = integral(S_nu^2 ds)"

    cycle_rows: list[dict[str, object]] = []
    for index, start in enumerate(resets):
        end = int(resets[index + 1] - 1) if index + 1 < len(resets) else len(frame) - 1
        cycle = frame.iloc[int(start) : end + 1]
        state_count = len(cycle)
        complete = state_count == modal_period
        metric = cycle[metric_name].to_numpy(dtype=float)
        metric_finite = bool(np.isfinite(metric).all())
        cycle_rows.append(
            {
                "cycle_index": index,
                "start_iteration": int(cycle.iloc[0]["iteration"]),
                "end_iteration": int(cycle.iloc[-1]["iteration"]),
                "state_count": state_count,
                "complete_modal_cycle": complete,
                "start_pseudo_time": float(cycle.iloc[0]["pseudo_time"]),
                "end_pseudo_time": float(cycle.iloc[-1]["pseudo_time"]),
                "start_kinematic_rms": float(cycle.iloc[0]["kinematic_rms"]),
                "minimum_kinematic_rms": float(cycle["kinematic_rms"].min()),
                "final_kinematic_rms": float(cycle.iloc[-1]["kinematic_rms"]),
                "metric_name": metric_name,
                "metric_finite": metric_finite,
                "start_metric": float(metric[0]) if metric_finite else float("nan"),
                "minimum_metric": (
                    float(np.min(metric)) if metric_finite else float("nan")
                ),
                "final_metric": (
                    float(metric[-1]) if metric_finite else float("nan")
                ),
                "start_root_thickness": float(cycle.iloc[0]["root_thickness"]),
                "final_root_thickness": float(cycle.iloc[-1]["root_thickness"]),
            }
        )
    cycles = pd.DataFrame(cycle_rows)
    complete = cycles[
        cycles["complete_modal_cycle"] & cycles["metric_finite"]
    ].tail(int(recent_cycle_count))
    if len(complete) < 8:
        raise ValueError("Fewer than eight complete modal matching cycles remain.")

    phase_rows: list[dict[str, object]] = []
    for phase in range(modal_period):
        samples: list[tuple[float, float]] = []
        for row in complete.itertuples(index=False):
            source_row = frame.iloc[int(row.start_iteration) + phase]
            samples.append(
                (
                    float(source_row["pseudo_time"]),
                    float(source_row[metric_name]),
                )
            )
        time = np.asarray([item[0] for item in samples], dtype=float)
        residual = np.asarray([item[1] for item in samples], dtype=float)
        phase_rows.append(
            {
                "phase_index": phase,
                "sample_count": len(samples),
                "metric_name": metric_name,
                "first_metric": float(residual[0]),
                "last_metric": float(residual[-1]),
                **_log_trend(time, residual),
            }
        )
    phases = pd.DataFrame(phase_rows)

    reset_rows: list[dict[str, object]] = []
    for reset in resets:
        reset_rows.append(
            {
                "iteration": int(frame.iloc[reset]["iteration"]),
                "pseudo_time": float(frame.iloc[reset]["pseudo_time"]),
                "thickness_jump_ratio": float(
                    frame.iloc[reset]["root_thickness"]
                    / frame.iloc[reset - 1]["root_thickness"]
                ),
                "resolution_jump_ratio": float(
                    frame.iloc[reset]["root_resolution_ratio"]
                    / frame.iloc[reset - 1]["root_resolution_ratio"]
                ),
                "residual_jump_ratio": (
                    float(
                        frame.iloc[reset][metric_name]
                        / frame.iloc[reset - 1][metric_name]
                    )
                    if np.isfinite(frame.iloc[reset][metric_name])
                    and np.isfinite(frame.iloc[reset - 1][metric_name])
                    else float("nan")
                ),
            }
        )
    reset_frame = pd.DataFrame(reset_rows)

    envelope_time = complete["end_pseudo_time"].to_numpy(dtype=float)
    envelope = complete["minimum_metric"].to_numpy(dtype=float)
    envelope_trend = _log_trend(envelope_time, envelope)
    phase_change = phases["relative_change_over_window"].to_numpy(dtype=float)
    phase_r2 = phases["log_linear_r_squared"].to_numpy(dtype=float)
    final_residual = float(frame.iloc[-1][metric_name])
    if final_residual <= kinematic_tolerance:
        classification = "KINEMATIC_CONVERGED"
    elif np.all(phase_change <= -0.02) and np.all(phase_r2 >= 0.9):
        classification = "PHASE_ALIGNED_DECAY"
    elif np.all(np.abs(phase_change) <= 0.01):
        classification = "PHASE_ALIGNED_PLATEAU"
    else:
        classification = "MIXED_OR_INSUFFICIENT_PHASE_TREND"

    rate = float(envelope_trend["exponential_rate_per_pseudo_time"])
    mean_step = float(np.mean(np.diff(frame["pseudo_time"].to_numpy(dtype=float))))
    if rate < 0.0 and final_residual > kinematic_tolerance:
        pseudo_time_to_tolerance = float(
            np.log(kinematic_tolerance / final_residual) / rate
        )
        estimated_steps = float(pseudo_time_to_tolerance / mean_step)
    else:
        pseudo_time_to_tolerance = float("nan")
        estimated_steps = float("nan")

    final_reset = int(resets[-1])
    report = {
        "classification": classification,
        "kinematic_metric": metric_name,
        "kinematic_metric_source": metric_source,
        "physical_validation_status": (
            "PASS" if classification == "KINEMATIC_CONVERGED" else "FAIL"
        ),
        "event_definition": (
            "root_thickness and root_resolution_ratio simultaneously increase "
            f"by at least {minimum_relative_jump:.1%}"
        ),
        "reset_count": len(resets),
        "modal_cycle_length_steps": modal_period,
        "complete_modal_cycle_count": int(cycles["complete_modal_cycle"].sum()),
        "recent_cycle_count": len(complete),
        "final_cycle_phase_index": int(len(frame) - 1 - final_reset),
        "final_kinematic_metric": final_residual,
        "final_kinematic_rms": float(frame.iloc[-1]["kinematic_rms"]),
        "kinematic_tolerance": float(kinematic_tolerance),
        "recent_envelope_trend": envelope_trend,
        "recent_reset_residual_jump": {
            "mean_ratio": float(reset_frame.tail(len(complete))["residual_jump_ratio"].mean()),
            "minimum_ratio": float(reset_frame.tail(len(complete))["residual_jump_ratio"].min()),
            "maximum_ratio": float(reset_frame.tail(len(complete))["residual_jump_ratio"].max()),
        },
        "zero_asymptote_exponential_projection": {
            "estimated_additional_pseudo_time_to_tolerance": pseudo_time_to_tolerance,
            "estimated_additional_steps_to_tolerance": estimated_steps,
            "assumption": (
                "Diagnostic only: recent phase-aligned exponential decay continues "
                "unchanged toward zero. This projection is not an acceptance result."
            ),
        },
        "reference_used": False,
        "interpretation": (
            "Phase-aligned decay distinguishes slow convergence from the sawtooth "
            "introduced by discrete matching-surface resets. Only the original "
            "kinematic tolerance passes the physical prerequisite."
        ),
    }
    return cycles, phases, reset_frame, report


def _plot(
    output: Path,
    history: pd.DataFrame,
    cycles: pd.DataFrame,
    phases: pd.DataFrame,
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4), constrained_layout=True)
    complete = cycles[
        cycles["complete_modal_cycle"] & cycles["metric_finite"]
    ]
    metric_name = str(cycles.iloc[-1]["metric_name"])
    axes[0].semilogy(history["pseudo_time"], history[metric_name], lw=0.8)
    axes[0].semilogy(
        complete["end_pseudo_time"],
        complete["minimum_metric"],
        "o-",
        ms=2.5,
        label="complete-cycle minimum",
    )
    axes[0].set(
        xlabel="Pseudo-time",
        ylabel=metric_name,
        title="Matching-cycle envelope",
    )
    axes[0].grid(True, which="both", alpha=0.25)
    axes[0].legend(frameon=False)

    axes[1].plot(
        phases["phase_index"],
        phases["relative_change_over_window"] * 100.0,
        "o-",
    )
    axes[1].axhline(0.0, color="black", lw=0.8)
    axes[1].set(
        xlabel="Phase index after matching-surface reset",
        ylabel="Residual change over recent window (%)",
        title="Phase-aligned trend",
    )
    axes[1].grid(True, alpha=0.25)
    figure.savefig(output / "matching_surface_cycle_analysis.png", dpi=180)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze phase-aligned self-similar matching-surface cycles."
    )
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--minimum-relative-jump", type=float, default=0.05)
    parser.add_argument("--recent-cycle-count", type=int, default=40)
    parser.add_argument("--kinematic-tolerance", type=float, default=1.0e-3)
    args = parser.parse_args()

    run = args.run.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    history = pd.read_csv(run / "coupled_pseudo_time_history.csv")
    cycles, phases, resets, report = analyze_matching_surface_cycles(
        history,
        minimum_relative_jump=args.minimum_relative_jump,
        recent_cycle_count=args.recent_cycle_count,
        kinematic_tolerance=args.kinematic_tolerance,
    )
    cycles.to_csv(output / "matching_surface_cycles.csv", index=False)
    phases.to_csv(output / "phase_aligned_residual_trends.csv", index=False)
    resets.to_csv(output / "matching_surface_reset_events.csv", index=False)
    (output / "matching_surface_cycle_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    _plot(output, history, cycles, phases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
