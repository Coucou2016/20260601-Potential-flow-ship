from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_rao(rao: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    for speed, group in rao.groupby("speed_mps"):
        label = f"{speed:.1f} m/s"
        axes[0].plot(group["wave_period_s"], group["heave_rao_m_per_m"], label=label)
        axes[1].plot(group["wave_period_s"], group["pitch_rao_rad_per_m"], label=label)
        axes[2].plot(group["wave_period_s"], group["bow_accel_rao_mps2_per_m"], label=label)
    axes[0].set_ylabel("Heave RAO (m/m)")
    axes[1].set_ylabel("Pitch RAO (rad/m)")
    axes[2].set_ylabel("Bow accel RAO (m/s^2/m)")
    axes[2].set_xlabel("Wave period (s)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_timeseries(df: pd.DataFrame, path: Path, title: str) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
    axes[0].plot(df["time_s"], df["wave_elevation_m"], color="0.35", label="wave")
    axes[0].plot(df["time_s"], df["heave_m"], label="heave")
    axes[1].plot(df["time_s"], df["pitch_rad"] * 57.295779513, label="pitch")
    axes[2].plot(df["time_s"], df["heave_accel_mps2"] / 9.80665, label="CG vertical")
    axes[2].plot(df["time_s"], df["bow_vertical_accel_mps2"] / 9.80665, label="bow vertical")
    axes[3].plot(df["time_s"], df["surge_m"], label="surge")
    axes[3].plot(df["time_s"], df["sway_m"], label="sway")
    axes[3].plot(df["time_s"], df["roll_rad"], label="roll")
    axes[3].plot(df["time_s"], df["yaw_rad"], label="yaw")
    axes[0].set_ylabel("Elevation (m)")
    axes[1].set_ylabel("Pitch (deg)")
    axes[2].set_ylabel("Accel (g)")
    axes[3].set_ylabel("Other DOF")
    axes[3].set_xlabel("Time (s)")
    fig.suptitle(title)
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_rms(summary: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    axes[0].plot(summary["speed_mps"], summary["heave_m_rms"], marker="o", label="heave RMS")
    axes[0].plot(summary["speed_mps"], summary["pitch_rad_rms"] * 57.295779513, marker="o", label="pitch RMS (deg)")
    axes[1].plot(
        summary["speed_mps"],
        summary["heave_accel_mps2_rms"] / 9.80665,
        marker="o",
        label="CG accel RMS",
    )
    axes[1].plot(
        summary["speed_mps"],
        summary["bow_vertical_accel_mps2_rms"] / 9.80665,
        marker="o",
        label="bow accel RMS",
    )
    axes[0].set_ylabel("Motion RMS")
    axes[1].set_ylabel("Accel RMS (g)")
    axes[1].set_xlabel("Speed (m/s)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
