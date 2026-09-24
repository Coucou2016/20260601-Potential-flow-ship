from __future__ import annotations

import numpy as np
import pandas as pd


DOF_COLUMNS = ["surge_m", "sway_m", "heave_m", "roll_rad", "pitch_rad", "yaw_rad"]


def make_sixdof_timeseries(
    time_s: np.ndarray,
    heave_m: np.ndarray,
    pitch_rad: np.ndarray,
    heave_velocity_mps: np.ndarray,
    pitch_rate_rad_s: np.ndarray,
    heave_acc_mps2: np.ndarray,
    pitch_acc_rad_s2: np.ndarray,
    bow_x_from_cg_m: float,
    wave_elevation_m: np.ndarray,
) -> pd.DataFrame:
    zeros = np.zeros_like(time_s)
    bow_vertical = heave_m - bow_x_from_cg_m * pitch_rad
    bow_acc = heave_acc_mps2 - bow_x_from_cg_m * pitch_acc_rad_s2
    return pd.DataFrame(
        {
            "time_s": time_s,
            "surge_m": zeros,
            "sway_m": zeros,
            "heave_m": heave_m,
            "roll_rad": zeros,
            "pitch_rad": pitch_rad,
            "yaw_rad": zeros,
            "surge_velocity_mps": zeros,
            "sway_velocity_mps": zeros,
            "heave_velocity_mps": heave_velocity_mps,
            "roll_rate_rad_s": zeros,
            "pitch_rate_rad_s": pitch_rate_rad_s,
            "yaw_rate_rad_s": zeros,
            "heave_accel_mps2": heave_acc_mps2,
            "pitch_accel_rad_s2": pitch_acc_rad_s2,
            "bow_vertical_m": bow_vertical,
            "bow_vertical_accel_mps2": bow_acc,
            "wave_elevation_m": wave_elevation_m,
        }
    )


def rms_after(df: pd.DataFrame, discard_initial_s: float) -> dict[str, float]:
    sub = df[df["time_s"] >= discard_initial_s]
    if sub.empty:
        sub = df
    result: dict[str, float] = {}
    for col in ["heave_m", "pitch_rad", "heave_accel_mps2", "bow_vertical_accel_mps2"]:
        values = sub[col].to_numpy(dtype=float)
        result[f"{col}_rms"] = float(np.sqrt(np.mean(values**2)))
    return result
