from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REQUIRED_COLUMNS = (
    "iteration",
    "kinematic_integral",
    "root_thickness",
    "root_resolution_ratio",
    "bem_condition_number",
    "jet_point_count",
    "shallow_jet_panel_count_per_side",
    "boundary_panel_count",
)


def jet_topology_event_frame(
    history: pd.DataFrame,
    *,
    minimum_root_jump: float = 0.05,
) -> pd.DataFrame:
    missing = [name for name in REQUIRED_COLUMNS if name not in history.columns]
    if missing:
        raise ValueError(f"Jet-topology history is missing columns: {missing}.")
    if not 0.0 < float(minimum_root_jump) < 1.0:
        raise ValueError("minimum_root_jump must lie between zero and one.")
    frame = history.copy()
    numeric = set(REQUIRED_COLUMNS) | {
        "provisional_matching_surface_shift_panels",
        "final_matching_surface_shift_panels",
        "rk2_rejected_attempt_count",
    }
    for name in numeric & set(frame.columns):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    frame = frame.dropna(subset=list(REQUIRED_COLUMNS)).reset_index(drop=True)
    if len(frame) < 4:
        raise ValueError("Jet-topology analysis requires at least four recorded states.")
    if np.any(frame["jet_point_count"] < 3) or np.any(
        frame["boundary_panel_count"] <= 0
    ):
        raise ValueError("Jet and boundary topology counts must be positive.")

    frame["raw_shallow_water_step_count"] = frame["jet_point_count"] - 1
    frame["raw_step_count_is_even"] = (
        frame["raw_shallow_water_step_count"].astype(int) % 2 == 0
    )
    thickness_ratio = frame["root_thickness"] / frame["root_thickness"].shift(1)
    resolution_ratio = (
        frame["root_resolution_ratio"] / frame["root_resolution_ratio"].shift(1)
    )
    threshold = 1.0 + float(minimum_root_jump)
    frame["root_state_jump"] = (thickness_ratio >= threshold) & (
        resolution_ratio >= threshold
    )
    frame["boundary_panel_count_change"] = (
        frame["boundary_panel_count"].diff().fillna(0.0) != 0.0
    )
    frame["raw_step_parity_change"] = (
        frame["raw_step_count_is_even"]
        != frame["raw_step_count_is_even"].shift(1)
    ).fillna(False)
    frame["condition_number_ratio"] = (
        frame["bem_condition_number"] / frame["bem_condition_number"].shift(1)
    )
    provisional = frame.get(
        "provisional_matching_surface_shift_panels",
        pd.Series(np.zeros(len(frame))),
    ).fillna(0.0)
    final = frame.get(
        "final_matching_surface_shift_panels",
        pd.Series(np.zeros(len(frame))),
    ).fillna(0.0)
    frame["explicit_matching_surface_adjustment"] = (provisional > 0.0) | (
        final > 0.0
    )
    return frame


def jet_topology_summary(frame: pd.DataFrame) -> dict[str, object]:
    jumps = frame[frame["root_state_jump"]]
    jump_count = len(jumps)
    boundary_coincidence = int(jumps["boundary_panel_count_change"].sum())
    parity_coincidence = int(jumps["raw_step_parity_change"].sum())
    groups: list[dict[str, object]] = []
    for (panels, even), group in frame.groupby(
        ["boundary_panel_count", "raw_step_count_is_even"],
        sort=True,
    ):
        groups.append(
            {
                "boundary_panel_count": int(panels),
                "raw_step_count_is_even": bool(even),
                "state_count": len(group),
                "kinematic_integral_mean": float(group["kinematic_integral"].mean()),
                "condition_number_median": float(group["bem_condition_number"].median()),
            }
        )
    boundary_changes = int(frame["boundary_panel_count_change"].sum())
    if jump_count and boundary_changes == 0:
        classification = "FIXED_TOPOLOGY_DOES_NOT_REMOVE_ROOT_CYCLE"
    elif jump_count and boundary_coincidence == jump_count:
        classification = "TOPOLOGY_CHANGE_COINCIDENT_BUT_NOT_YET_CAUSAL"
    else:
        classification = "MIXED_TOPOLOGY_AND_ROOT_EVENTS"
    return {
        "status": "self_similar_shallow_jet_topology_diagnostic",
        "validated": False,
        "reference_used": False,
        "classification": classification,
        "state_count": len(frame),
        "iteration_start": int(frame.iloc[0]["iteration"]),
        "iteration_end": int(frame.iloc[-1]["iteration"]),
        "root_state_jump_count": jump_count,
        "boundary_panel_change_count": boundary_changes,
        "root_jumps_with_boundary_panel_change": boundary_coincidence,
        "root_jump_boundary_change_fraction": (
            float(boundary_coincidence / jump_count) if jump_count else 0.0
        ),
        "root_jumps_with_raw_step_parity_change": parity_coincidence,
        "explicit_matching_surface_adjustment_count": int(
            frame["explicit_matching_surface_adjustment"].sum()
        ),
        "rk2_rejected_attempt_total": int(
            frame.get("rk2_rejected_attempt_count", pd.Series([0.0])).fillna(0.0).sum()
        ),
        "kinematic_integral": {
            "mean": float(frame["kinematic_integral"].mean()),
            "minimum": float(frame["kinematic_integral"].min()),
            "maximum": float(frame["kinematic_integral"].max()),
            "range": float(frame["kinematic_integral"].max() - frame["kinematic_integral"].min()),
        },
        "condition_number": {
            "minimum": float(frame["bem_condition_number"].min()),
            "maximum": float(frame["bem_condition_number"].max()),
        },
        "topology_groups": groups,
        "interpretation": (
            "Coincidence identifies a mechanism candidate, not proof of physical "
            "causation. A fixed-topology counterfactual is required."
        ),
    }


def _plot(output: Path, frame: pd.DataFrame) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(10.0, 6.8), constrained_layout=True)
    axes[0].plot(frame["iteration"], frame["kinematic_integral"], "o-", ms=3.0)
    jumps = frame[frame["root_state_jump"]]
    axes[0].scatter(
        jumps["iteration"],
        jumps["kinematic_integral"],
        marker="x",
        s=45,
        color="tab:red",
        label="root-state jump",
    )
    axes[0].set(ylabel="Iafrati Eq. (52) K")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(frameon=False)
    axes[1].plot(
        frame["iteration"],
        frame["bem_condition_number"],
        "o-",
        ms=3.0,
        label="BEM condition number",
    )
    second = axes[1].twinx()
    second.step(
        frame["iteration"],
        frame["boundary_panel_count"],
        where="mid",
        color="tab:orange",
        label="boundary panel count",
    )
    axes[1].set(xlabel="Cumulative iteration", ylabel="Condition number")
    second.set(ylabel="Boundary panel count")
    axes[1].grid(True, alpha=0.25)
    figure.savefig(output / "jet_topology_cycle_diagnostic.png", dpi=180)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit shallow-jet topology against self-similar residual cycles."
    )
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--minimum-root-jump", type=float, default=0.05)
    args = parser.parse_args()

    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    history = pd.read_csv(args.run.resolve() / "coupled_pseudo_time_history.csv")
    frame = jet_topology_event_frame(
        history,
        minimum_root_jump=args.minimum_root_jump,
    )
    summary = jet_topology_summary(frame)
    frame.to_csv(output / "jet_topology_events.csv", index=False)
    (output / "jet_topology_analysis.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    _plot(output, frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
